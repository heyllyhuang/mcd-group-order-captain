#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦拼单团长 —— 促销侦察

团餐方案要真的对上「当天的活动」，先得把促销盘清楚。
本脚本把三类来源统一成一张清单，并判断每个促销对「多人团餐」到底有没有用：

    ① 当月活动   ← campaign-calendar
    ② 可用券     ← available-coupons / query-store-coupons
    ③ 商品特价   ← 菜单 / 活动页（MCP 拿不到的部分，人工或读页面补）

关键产出是 **「需确认」列**——把 MCP 拿不到、必须人工核实的字段显式列出来，
避免把「限购 2 份」当成「不限量」用错。

用法：
    python promo_scan.py --demo
    python promo_scan.py --input promo.json
    python promo_scan.py --input promo.json --json
"""

import argparse
import json
import sys
import unicodedata

# ---------------------------------------------------------------- 工具


def r1(x):
    return round(x + 1e-9, 1)


def _w(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def pad(s, width, align="left"):
    s = str(s)
    d = width - _w(s)
    if d <= 0:
        return s
    return (" " * d + s) if align == "right" else (s + " " * d)


KIND_LABEL = {
    "limit_price": "单品特价",
    "second_half": "第二份半价",
    "threshold_coupon": "满减券",
    "product_coupon": "单品券",
    "free_delivery": "免配送费",
    "unknown": "未知类型",
}

# ---------------------------------------------------------------- 分析


def analyze(p):
    """判断一条促销对多人团餐的适用性，并列出必须人工确认的字段。"""
    kind = p.get("kind", "unknown")
    limit = p.get("limit")
    scope = p.get("scope")  # per_order / per_account / None
    confirm = []

    if kind in ("limit_price", "second_half"):
        if limit is None:
            confirm.append("限购数量")
        if scope is None:
            confirm.append("限购范围(按单/按人)")

    if kind == "threshold_coupon":
        fit, rank = "🟢 高", 3
        why = "金额越大越好用；一单一券 → 配合拆单收益最大"
    elif kind == "second_half":
        if scope == "per_order":
            fit, rank = "🟢 高", 3
            why = "每单限购，多点或拆单可反复吃名额"
        elif scope == "per_account":
            fit, rank = "🔴 低", 1
            why = "按人限购，团餐只能吃一遍，别指望它"
        else:
            fit, rank = "🟡 中", 2
            why = "范围未知，按「每单」保守估计"
    elif kind == "limit_price":
        if scope == "per_order":
            fit, rank = "🟢 高", 3
            why = "每单限 N 份特价，拆单可多吃名额"
        elif scope == "per_account":
            fit, rank = "🟡 中", 2
            why = "每账号限 N 份，超出部分按原价"
        else:
            fit, rank = "🟡 中", 2
            why = "范围未知，按保守估计"
    elif kind == "product_coupon":
        fit, rank = "🟡 中", 2
        why = "单品券只对指定商品生效，注意与满减券是否互斥"
    elif kind == "free_delivery":
        fit, rank = "🟢 高", 3
        why = "拆单的天然对价，门槛越低越适合拆"
    else:
        fit, rank = "🟡 中", 2
        why = "未识别的活动类型，建议人工核实"

    # 力度
    strength = ""
    if kind == "limit_price" and p.get("orig_price") is not None:
        strength = "省 %.1f/份" % r1(float(p["orig_price"]) - float(p.get("price", 0)))
    elif kind == "threshold_coupon":
        strength = "满 %.0f 减 %.0f" % (float(p.get("threshold", 0)), float(p.get("discount", 0)))
    elif kind == "second_half":
        strength = "第 2 件半价"
    elif kind == "product_coupon":
        strength = "减 %.1f" % float(p.get("discount", 0))
    elif kind == "free_delivery":
        strength = "免 ¥%.1f" % float(p.get("fee", 0))

    # 限购描述
    if kind == "threshold_coupon":
        po = p.get("per_order")
        limit_desc = ("每单 %s 张" % po) if po else "每单 1 张"
    elif limit is None and scope is None:
        limit_desc = "未知 ❓"
    elif limit is None:
        limit_desc = "不限量?"
    else:
        limit_desc = "%s %s 份" % ({"per_order": "每单", "per_account": "每人"}.get(scope, "?"), limit)

    return {
        "name": p.get("name", "(未命名)"),
        "kind": kind,
        "kind_label": KIND_LABEL.get(kind, "未知类型"),
        "strength": strength,
        "limit_desc": limit_desc,
        "fit": fit,
        "rank": rank,
        "why": why,
        "confirm": confirm,
        "period": p.get("period", ""),
        "product": p.get("product", ""),
    }


def scan(data):
    promos = data.get("promos", [])
    analyzed = [analyze(p) for p in promos]
    analyzed.sort(key=lambda x: -x["rank"])

    need_confirm = [a for a in analyzed if a["confirm"]]
    stackable = [a["name"] for a in analyzed if a["kind"] == "threshold_coupon"]
    product_promos = [a["name"] for a in analyzed if a["kind"] in ("limit_price", "second_half", "product_coupon")]

    tips = []
    if product_promos and stackable:
        tips.append("单品特价/半价 与 满减券 通常可叠加：先吃单品特价，再用满减券结算")
    if any(a["kind"] == "limit_price" or a["kind"] == "second_half" for a in analyzed):
        tips.append("含限购类活动 → 先查清「按单限」还是「按人限」，这决定拆单有没有用")
    if not promos:
        tips.append("未提供任何促销信息，请先跑一次 campaign-calendar + available-coupons")

    return {
        "total": len(analyzed),
        "items": analyzed,
        "need_confirm": [{"name": a["name"], "fields": a["confirm"]} for a in need_confirm],
        "high_fit": [a["name"] for a in analyzed if a["rank"] == 3],
        "low_fit": [a["name"] for a in analyzed if a["rank"] == 1],
        "tips": tips,
    }


# ---------------------------------------------------------------- 渲染


def render(res):
    W = (22, 12, 14, 12, 8)
    line = "-" * sum(W)
    L = []
    L.append("=" * sum(W))
    L.append("  促销侦察 · 共 %d 条" % res["total"])
    L.append("=" * sum(W))
    if res["total"]:
        L.append(pad("活动名称", W[0]) + pad("类型", W[1]) + pad("力度", W[2])
                 + pad("限购", W[3]) + pad("团餐适用", W[4]))
        L.append(line)
        for a in res["items"]:
            L.append(pad(a["name"], W[0]) + pad(a["kind_label"], W[1]) + pad(a["strength"], W[2])
                     + pad(a["limit_desc"], W[3]) + pad(a["fit"], W[4]))
            L.append("  └ " + a["why"])
            if a["period"]:
                L.append("    有效期：" + a["period"])
        L.append(line)

    if res["need_confirm"]:
        L.append("  ⚠️ 以下字段 MCP 拿不到，必须人工确认：")
        for n in res["need_confirm"]:
            L.append("     · %s → %s" % (n["name"], "、".join(n["fields"])))
    if res["high_fit"]:
        L.append("  🟢 团餐优先用：" + "、".join(res["high_fit"]))
    if res["low_fit"]:
        L.append("  🔴 团餐别指望：" + "、".join(res["low_fit"]))
    for t in res["tips"]:
        L.append("  💡 " + t)
    L.append("=" * sum(W))
    return "\n".join(L)


# ---------------------------------------------------------------- 示例


DEMO = {
    "promos": [
        {"name": "巨无霸套餐特价", "kind": "limit_price", "product": "巨无霸套餐",
         "orig_price": 36.0, "price": 29.0, "limit": 2, "scope": "per_order",
         "period": "10.01-10.31"},
        {"name": "麦乐鸡第二份半价", "kind": "second_half", "product": "麦乐鸡(5块)",
         "limit": 1, "scope": "per_account", "period": "每周五"},
        {"name": "满50减15券", "kind": "threshold_coupon", "threshold": 50.0,
         "discount": 15.0, "per_order": 1},
        {"name": "满59免配送费", "kind": "free_delivery", "fee": 9.0, "threshold": 59.0},
        {"name": "某新品券", "kind": "product_coupon", "discount": 5.0},
    ]
}


# ---------------------------------------------------------------- 入口


def main():
    ap = argparse.ArgumentParser(description="麦麦拼单团长 · 促销侦察")
    ap.add_argument("--input", "-i", help="促销 JSON 文件")
    ap.add_argument("--demo", action="store_true", help="用内置示例运行")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args()

    if args.demo:
        data = DEMO
    elif args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    else:
        ap.error("请提供 --input <文件> 或 --demo")

    res = scan(data)
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render(res))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
