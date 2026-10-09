#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦拼单团长 —— 拆账与凑单优化计算

纯标准库实现，无第三方依赖。

用法：
    python split_bill.py --input order.json
    python split_bill.py --input order.json --mode C
    python split_bill.py --input order.json --json        # 输出结构化 JSON
    python split_bill.py --demo                           # 用内置示例跑一遍

三种拆账模式：
    A 按原价比例分摊（默认，最公平）
    B 平均分摊优惠（点得差不多时最快）
    C 精确到人（专属券只减本人，共享券按原价比例分摊）

金额精度统一 0.1 元，并用最大余额法保证「各人应付之和 == 整单实付」。
"""

import argparse
import json
import math
import sys

# ---------------------------------------------------------------- 数值工具


def largest_remainder(raw, target):
    """按最大余额法把 raw 调整为合计严格等于 target（0.1 元精度）的列表。"""
    n = len(raw)
    if n == 0:
        return []
    units = round(target * 10)
    base = [math.floor(v * 10 + 1e-9) for v in raw]
    rem = [v * 10 - b for v, b in zip(raw, base)]
    short = units - sum(base)
    order = sorted(range(n), key=lambda i: rem[i], reverse=True)
    i = 0
    while short > 0:
        base[order[i % n]] += 1
        short -= 1
        i += 1
    while short < 0:
        base[order[(n - 1 - i) % n]] -= 1
        short += 1
        i += 1
    return [b / 10 for b in base]


def distribute_by_weights(total, weights):
    """按权重分摊 total，合计严格等于 total。"""
    n = len(weights)
    if n == 0:
        return []
    w_sum = sum(weights)
    if w_sum <= 0:
        raw = [total / n] * n
    else:
        raw = [total * (w / w_sum) for w in weights]
    return largest_remainder(raw, total)


def half_price_total(qty, unit_price):
    """第二份半价：每两份一组，第 2、4、6… 份半价。"""
    pairs = qty // 2
    return (qty - pairs) * unit_price + pairs * unit_price * 0.5


def r1(x):
    return round(x + 1e-9, 1)


# ---------------------------------------------------------------- 核心计算


def build(data, mode="A", thresholds=(30, 50, 80, 100)):
    people = data.get("people", [])
    if not people:
        raise ValueError("order.json 里没有 people 数据")

    # --- 1. 逐人逐项计算原价 / 第二份半价优惠
    for p in people:
        items = p.get("items", [])
        p["_orig"] = 0.0
        p["_promo_save"] = 0.0
        for it in items:
            qty = it.get("qty", 1)
            unit = float(it.get("unit_price", 0))
            full = qty * unit
            if it.get("second_half") and qty >= 2:
                actual = half_price_total(qty, unit)
                it["_save"] = r1(full - actual)
            else:
                it["_save"] = 0.0
            it["_full"] = r1(full)
            p["_orig"] = r1(p["_orig"] + full)
            p["_promo_save"] = r1(p["_promo_save"] + it["_save"])

    # --- 2. 整单汇总
    orig_total = r1(sum(p["_orig"] for p in people))
    promo_save = r1(sum(p["_promo_save"] for p in people))
    shared_discount = float(data.get("shared_discount", 0.0))
    person_discounts = {k: float(v) for k, v in data.get("person_discounts", {}).items()}
    person_discount_total = r1(sum(person_discounts.values()))

    total_discount = r1(promo_save + shared_discount + person_discount_total)
    payable_total = r1(orig_total - total_discount)
    if payable_total < 0:
        payable_total = 0.0
        total_discount = orig_total

    # --- 3. 拆账
    orig_list = [p["_orig"] for p in people]
    n = len(people)
    payable = [0.0] * n

    if mode == "A":
        payable = distribute_by_weights(payable_total, orig_list)

    elif mode == "B":
        per_discount = total_discount / n
        raw = [o - per_discount for o in orig_list]
        payable = largest_remainder(raw, payable_total)

    elif mode == "C":
        shared_total = r1(total_discount - person_discount_total)
        raw = []
        for p in people:
            own = person_discounts.get(p.get("name", ""), 0.0)
            share = shared_total * (p["_orig"] / orig_total) if orig_total > 0 else 0.0
            raw.append(p["_orig"] - own - share)
        payable = largest_remainder(raw, payable_total)

    else:
        raise ValueError("mode 只支持 A / B / C")

    for p, pay in zip(people, payable):
        p["_payable"] = r1(pay)

    # --- 4. 凑单建议
    gap_suggestion = None
    candidates = sorted(t for t in thresholds if t > payable_total)
    if candidates:
        nxt = candidates[0]
        gap_suggestion = {
            "next_threshold": nxt,
            "gap": r1(nxt - payable_total),
            "hint": "再补 %.1f 元到 %d 元档，如有满减券可触发下一档优惠"
            % (r1(nxt - payable_total), nxt),
        }

    # --- 5. 第二份半价漏检提示
    promo_hints = []
    for p in people:
        for it in p.get("items", []):
            if it.get("qty", 1) >= 2 and not it.get("second_half"):
                promo_hints.append(
                    "%s 点了 %d 份「%s」，若该品参加第二份半价，可再省 ¥%.1f"
                    % (p.get("name", "?"), it["qty"], it["name"],
                       r1(it["qty"] * float(it.get("unit_price", 0)) * 0.5 * (it["qty"] // 2)))
                )

    # --- 6. 自检
    check_sum = r1(sum(p["_payable"] for p in people))
    consistent = abs(check_sum - payable_total) < 0.05

    return {
        "mode": mode,
        "summary": {
            "people": n,
            "items": sum(len(p.get("items", [])) for p in people),
            "orig_total": orig_total,
            "promo_save": promo_save,
            "shared_discount": shared_discount,
            "person_discount": person_discount_total,
            "discount_total": total_discount,
            "payable_total": payable_total,
            "saved_pct": r1(total_discount / orig_total * 100) if orig_total else 0.0,
        },
        "per_person": [
            {
                "name": p.get("name", "?"),
                "tag": p.get("tag", ""),
                "items": [
                    {"name": it["name"], "qty": it.get("qty", 1),
                     "unit_price": float(it.get("unit_price", 0)),
                     "full": it["_full"], "save": it["_save"]}
                    for it in p.get("items", [])
                ],
                "orig": p["_orig"],
                "payable": p["_payable"],
            }
            for p in people
        ],
        "gap_suggestion": gap_suggestion,
        "promo_hints": promo_hints,
        "check": {"sum_of_payable": check_sum, "payable_total": payable_total,
                  "consistent": consistent},
        "meta": {"store": data.get("store", ""), "date": data.get("date", "")},
    }


# ---------------------------------------------------------------- 文本渲染


def render(result):
    s = result["summary"]
    meta = result["meta"]
    lines = []
    lines.append("=" * 46)
    lines.append("  麦麦拼单结算单" + (f"  ·  {meta['store']}" if meta.get("store") else ""))
    lines.append("=" * 46)
    if meta.get("date"):
        lines.append(f"  日期：{meta['date']}")
    lines.append(f"  {s['people']} 人 · {s['items']} 件 · 拆账模式 {result['mode']}")
    lines.append("-" * 46)
    lines.append(f"{'昵称':<10}{'原价':>8}{'应付':>10}")
    lines.append("-" * 46)
    for p in result["per_person"]:
        tag = f"  [{p['tag']}]" if p.get("tag") else ""
        lines.append(f"{p['name']:<10}{p['orig']:>8.1f}{p['payable']:>10.1f}{tag}")
    lines.append("-" * 46)
    lines.append(f"{'合计':<10}{s['orig_total']:>8.1f}{s['payable_total']:>10.1f}")
    lines.append("-" * 46)
    lines.append(f"  优惠明细：第二份半价 -{s['promo_save']:.1f} / "
                 f"共享券 -{s['shared_discount']:.1f} / 专属券 -{s['person_discount']:.1f}")
    lines.append(f"  共省 ¥{s['discount_total']:.1f}（{s['saved_pct']:.1f}%）")
    lines.append("=" * 46)

    if result["gap_suggestion"]:
        g = result["gap_suggestion"]
        lines.append(f"  💡 凑单提示：{g['hint']}")
    for h in result["promo_hints"]:
        lines.append(f"  💡 {h}")

    c = result["check"]
    lines.append("")
    lines.append(f"  [自检] 各人应付之和 ¥{c['sum_of_payable']:.1f} "
                 f"{'==' if c['consistent'] else '!='} 整单实付 ¥{c['payable_total']:.1f}"
                 f"  {'✅ 通过' if c['consistent'] else '❌ 不一致，请检查输入'}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 示例数据


DEMO = {
    "store": "麦当劳(科韵路店)",
    "date": "2026-10-09",
    "shared_discount": 15.0,
    "person_discounts": {"小张": 5.0},
    "people": [
        {"name": "小张", "tag": "碳水战神", "items": [
            {"name": "巨无霸套餐", "qty": 1, "unit_price": 36.0},
        ]},
        {"name": "小李", "tag": "减肥未遂", "items": [
            {"name": "烤鸡沙拉", "qty": 1, "unit_price": 26.5},
        ]},
        {"name": "小王", "tag": "", "items": [
            {"name": "麦辣鸡腿堡", "qty": 2, "unit_price": 22.0, "second_half": True},
        ]},
        {"name": "老王", "tag": "", "items": [
            {"name": "板烧鸡腿堡套餐", "qty": 1, "unit_price": 34.0},
            {"name": "薯条(大)", "qty": 1, "unit_price": 13.0},
        ]},
        {"name": "团长", "tag": "薅券担当", "items": [
            {"name": "麦乐鸡(5块)", "qty": 1, "unit_price": 14.5},
            {"name": "可口可乐(中)", "qty": 2, "unit_price": 9.5, "second_half": True},
        ]},
    ],
}


# ---------------------------------------------------------------- 入口


def main():
    ap = argparse.ArgumentParser(description="麦麦拼单团长 · 拆账计算")
    ap.add_argument("--input", "-i", help="order.json 路径")
    ap.add_argument("--mode", "-m", default="A", choices=["A", "B", "C"],
                    help="拆账模式：A 按原价比例（默认）/ B 平均分摊 / C 精确到人")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ap.add_argument("--demo", action="store_true", help="用内置示例数据运行")
    args = ap.parse_args()

    if args.demo:
        data = DEMO
    elif args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    else:
        ap.error("请指定 --input <文件> 或 --demo")

    result = build(data, mode=args.mode)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
