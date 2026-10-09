#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦拼单团长 —— 配餐规划 与 买单策略

两个子命令：
    plan   按人数生成配餐方案（吃饱 / 吃好 / 不浪费），出三档对比
    pay    算出最划算的买法：吃满限购名额 + 拆单策略

纯标准库，无第三方依赖。

用法：
    python plan_order.py plan --demo
    python plan_order.py plan --people 12 --budget 400 --scene afternoon
    python plan_order.py plan --input plan.json
    python plan_order.py pay  --demo
    python plan_order.py pay  --input cart.json
"""

import argparse
import json
import sys
import unicodedata

# ---------------------------------------------------------------- 工具


def r1(x):
    return round(x + 1e-9, 1)


def _w(s):
    """字符串显示宽度（CJK 字符算 2 格）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s, width, align="left"):
    """按显示宽度补齐，保证中文表格列对齐。"""
    s = str(s)
    d = width - _w(s)
    if d <= 0:
        return s
    return (" " * d + s) if align == "right" else (s + " " * d)


# ---------------------------------------------------------------- 配餐规划

SCENE = {
    "afternoon": {"label": "下午茶", "side": 0.7, "drink": 0.8},
    "meal": {"label": "正餐", "side": 0.8, "drink": 1.0},
    "overtime": {"label": "加班餐", "side": 0.6, "drink": 0.9},
}

DEFAULT_ITEMS = {
    "main": {"name": "麦辣鸡腿堡(单点)", "price": 22.0},
    "combo": {"name": "麦辣鸡腿堡套餐", "price": 32.0},
    "side": {"name": "薯条(大)", "price": 13.0},
    "drink": {"name": "可口可乐(中)", "price": 9.5},
}


def plan_mode(data):
    n = int(data.get("people", 0))
    if n <= 0:
        raise ValueError("people 必须大于 0")

    scene_key = data.get("scene", "afternoon")
    scene = SCENE.get(scene_key, SCENE["afternoon"])
    items = data.get("items", DEFAULT_ITEMS)
    budget = data.get("budget_total")

    # 三条线：主食人手一份，小食与饮料按比例共享（不是人手一份）
    main_n = n
    side_n = max(1, round(n * scene["side"]))
    drink_n = max(1, round(n * scene["drink"]))

    def eff(k):
        """取有效价：有活动价就用活动价，否则用原价。"""
        it = items[k]
        return float(it.get("promo_price", it["price"]))

    p_main, p_combo = eff("main"), eff("combo")
    p_side, p_drink = eff("side"), eff("drink")

    # 记录本方案用到的当天活动，提醒团长价格有时效
    promo_used = []
    for k, label in (("main", "主食"), ("combo", "套餐"), ("side", "小食"), ("drink", "饮料")):
        it = items[k]
        if it.get("promo_price") is not None and float(it["promo_price"]) < float(it["price"]):
            promo_used.append("%s %s：活动价 %.1f（原价 %.1f，省 %.1f/份）"
                              % (label, it["name"], float(it["promo_price"]),
                                 float(it["price"]), r1(float(it["price"]) - float(it["promo_price"]))))

    plans = []

    # 省钱版：全员单点主食 + 少量共享小食，饮料自带
    cheap_side = max(1, round(side_n * 0.6))
    cheap_total = r1(p_main * main_n + p_side * cheap_side)
    plans.append({
        "name": "省钱版",
        "detail": "%s×%d ＋ %s×%d（饮料自带）"
                  % (items["main"]["name"], main_n, items["side"]["name"], cheap_side),
        "total": cheap_total,
        "per": r1(cheap_total / n),
        "fit": "预算紧、只求吃饱",
        "components": [(items["main"]["name"], main_n), (items["side"]["name"], cheap_side)],
    })

    # 均衡版：全员套餐（含薯条+可乐）+ 补少量共享小食
    bal_side = max(1, round(side_n * 0.4))
    bal_total = r1(p_combo * main_n + p_side * bal_side)
    plans.append({
        "name": "均衡版",
        "detail": "%s×%d ＋ 追加%s×%d"
                  % (items["combo"]["name"], main_n, items["side"]["name"], bal_side),
        "total": bal_total,
        "per": r1(bal_total / n),
        "fit": "通用推荐，人人有主食有饮料",
        "components": [(items["combo"]["name"], main_n), (items["side"]["name"], bal_side)],
    })

    # 体面版：全员套餐 + 足量共享小食 + 追加饮料
    prem_side = side_n
    prem_drink = max(1, round(drink_n * 0.5))
    prem_total = r1(p_combo * main_n + p_side * prem_side + p_drink * prem_drink)
    plans.append({
        "name": "体面版",
        "detail": "%s×%d ＋ %s×%d ＋ %s×%d"
                  % (items["combo"]["name"], main_n, items["side"]["name"], prem_side,
                     items["drink"]["name"], prem_drink),
        "total": prem_total,
        "per": r1(prem_total / n),
        "fit": "请客 / 重要场合",
        "components": [(items["combo"]["name"], main_n), (items["side"]["name"], prem_side),
                       (items["drink"]["name"], prem_drink)],
    })

    # 推荐：有预算就选不超过预算的最高档；没预算默认均衡版
    recommend = "均衡版"
    if budget:
        affordable = [p for p in plans if p["total"] <= float(budget)]
        recommend = affordable[-1]["name"] if affordable else "省钱版（超预算，建议压到人均 %.1f 以内）" % (float(budget) / n)

    return {
        "scene": scene["label"],
        "people": n,
        "budget_total": float(budget) if budget else None,
        "portion": {"main": main_n, "side": side_n, "drink": drink_n},
        "plans": plans,
        "recommend": recommend,
        "promo_used": promo_used,
        "note": "小食按人数 ×%.0f%% 配、饮料 ×%.0f%% 配——不是人手一份，这正是「不浪费」的关键。"
                % (scene["side"] * 100, scene["drink"] * 100),
    }


def render_plan(res):
    W = (8, 48, 9, 9)
    line = "-" * sum(W)
    L = []
    L.append("=" * sum(W))
    L.append("  团餐配餐方案 · %s · %d 人" % (res["scene"], res["people"]))
    L.append("=" * sum(W))
    p = res["portion"]
    L.append("  建议份数：主食 %d 份 / 小食 %d 份 / 饮料 %d 份" % (p["main"], p["side"], p["drink"]))
    L.append(line)
    L.append(pad("方案", W[0]) + pad("内容", W[1]) + pad("总价", W[2], "right") + pad("人均", W[3], "right"))
    L.append(line)
    for pl in res["plans"]:
        L.append(pad(pl["name"], W[0]) + pad(pl["detail"], W[1])
                 + pad("%.1f" % pl["total"], W[2], "right") + pad("%.1f" % pl["per"], W[3], "right"))
        L.append(pad("", W[0]) + pad("└ " + pl["fit"], W[1]))
    L.append(line)
    L.append("  ⭐ 推荐：%s" % res["recommend"])
    if res["budget_total"]:
        L.append("  预算合计：¥%.1f" % res["budget_total"])
    if res.get("promo_used"):
        L.append("")
        L.append("  🔖 本方案已用当天的活动（价格有时效，下单前请复核）：")
        for x in res["promo_used"]:
            L.append("     · " + x)
    L.append("  💡 %s" % res["note"])
    L.append("=" * sum(W))
    return "\n".join(L)


# ---------------------------------------------------------------- 买单策略


def alloc_units(units, k):
    """把单份商品尽量均衡地分到 k 单（贵的先分给当前最轻的单）。"""
    loads = [0.0] * k
    buckets = [[] for _ in range(k)]
    for u in sorted(units, key=lambda x: -x["unit_price"]):
        i = min(range(k), key=lambda j: loads[j])
        buckets[i].append(u)
        loads[i] += u["unit_price"]
    return buckets


def price_bucket(bucket, coupons, delivery):
    """算一单的价格：商品小计（含每单限购）+ 最优满减券 + 配送费。"""
    subtotal = 0.0
    used = {}
    for u in bucket:
        promo = u.get("promo")
        if promo and promo.get("kind") == "limit_price" and promo.get("scope") == "per_order":
            got = used.get(u["name"], 0)
            if got < promo.get("limit", 0):
                subtotal += float(promo["price"])
                used[u["name"]] = got + 1
                continue
        subtotal += u["unit_price"]
    subtotal = r1(subtotal)

    best, best_name = 0.0, None
    for c in coupons:
        if subtotal >= float(c.get("threshold", 0)) and float(c.get("discount", 0)) > best:
            best = float(c["discount"])
            best_name = c["name"]

    fee = 0.0
    d_fee = float(delivery.get("fee", 0))
    d_free = float(delivery.get("free_threshold", 0))
    if d_fee > 0 and subtotal < d_free:
        fee = d_fee

    return {"subtotal": subtotal, "coupon": r1(best), "coupon_name": best_name,
            "fee": r1(fee), "net": r1(subtotal - best + fee), "qty": len(bucket)}


def expand_units(items):
    """把 items 展开成一个个单份商品，并处理 per_account 限购。"""
    units = []
    for it in items:
        qty = int(it.get("qty", 1))
        promo = it.get("promo")
        limit_left = None
        if promo and promo.get("kind") == "limit_price" and promo.get("scope") == "per_account":
            limit_left = int(promo.get("limit", 0))
        for _ in range(qty):
            u = {"name": it["name"], "unit_price": float(it["unit_price"]), "promo": promo}
            if limit_left is not None and limit_left > 0:
                u["unit_price"] = float(promo["price"])
                limit_left -= 1
                u["promo"] = None  # 已按特价计入，不再重复享受
            units.append(u)
    return units


def pay_mode(data):
    items = data.get("items", [])
    if not items:
        raise ValueError("items 不能为空")
    coupons = data.get("coupons", [])
    delivery = data.get("delivery", {"fee": 0.0, "free_threshold": 0.0})
    max_split = int(data.get("max_split", 6))

    units = expand_units(items)
    total_qty = len(units)

    rows = []
    for k in range(1, max_split + 1):
        if k > total_qty:
            break
        buckets = alloc_units(units, k)
        priced = [price_bucket(b, coupons, delivery) for b in buckets]
        rows.append({
            "split": k,
            "qty_per": [p["qty"] for p in priced],
            "subtotal": r1(sum(p["subtotal"] for p in priced)),
            "coupon": r1(sum(p["coupon"] for p in priced)),
            "fee": r1(sum(p["fee"] for p in priced)),
            "net": r1(sum(p["net"] for p in priced)),
        })

    best = min(rows, key=lambda r: r["net"])
    baseline = rows[0]
    saving = r1(baseline["net"] - best["net"])

    return {
        "total_qty": total_qty,
        "coupons": coupons,
        "delivery": delivery,
        "rows": rows,
        "best": best,
        "baseline": baseline,
        "saving_vs_single": saving,
    }


def render_pay(res):
    W = (9, 24, 11, 9, 10, 11)
    line = "-" * sum(W)
    L = []
    L.append("=" * sum(W))
    L.append("  买单策略 · 共 %d 份" % res["total_qty"])
    L.append("=" * sum(W))
    if res["coupons"]:
        cs = " / ".join("%s(满%.0f减%.0f)" % (c.get("name", "券"), c.get("threshold", 0),
                                             c.get("discount", 0)) for c in res["coupons"])
        L.append("  可用券：%s" % cs)
    d = res["delivery"]
    if d.get("fee", 0):
        L.append("  配送费：每单 ¥%.1f，满 ¥%.1f 免运" % (d["fee"], d.get("free_threshold", 0)))
    L.append(line)
    L.append(pad("拆单数", W[0]) + pad("每单份数", W[1]) + pad("商品小计", W[2], "right")
             + pad("券", W[3], "right") + pad("配送费", W[4], "right") + pad("净付", W[5], "right"))
    L.append(line)
    for r in res["rows"]:
        mark = "  ← 推荐" if r["split"] == res["best"]["split"] else ""
        L.append(pad("%d 单" % r["split"], W[0]) + pad("×".join(str(q) for q in r["qty_per"]), W[1])
                 + pad("%.1f" % r["subtotal"], W[2], "right") + pad("%.1f" % r["coupon"], W[3], "right")
                 + pad("%.1f" % r["fee"], W[4], "right") + pad("%.1f" % r["net"], W[5], "right") + mark)
    L.append(line)
    b = res["best"]
    L.append("  ⭐ 最优：拆成 %d 单，净付 ¥%.1f" % (b["split"], b["net"]))
    if res["saving_vs_single"] > 0:
        L.append("  💰 比不拆单（¥%.1f）省 ¥%.1f" % (res["baseline"]["net"], res["saving_vs_single"]))
    elif res["saving_vs_single"] < 0:
        L.append("  ⚠️ 拆单反而更贵 ¥%.1f，建议不拆" % abs(res["saving_vs_single"]))
    else:
        L.append("  ℹ️ 拆不拆一个价，建议不拆（省事）")
    L.append("=" * sum(W))
    return "\n".join(L)


# ---------------------------------------------------------------- 示例


PLAN_DEMO = {
    "people": 12,
    "budget_total": 400,
    "scene": "afternoon",
    "items": DEFAULT_ITEMS,
}

PAY_DEMO = {
    "max_split": 6,
    "delivery": {"fee": 9.0, "free_threshold": 59.0},
    "coupons": [{"name": "满50减15", "threshold": 50.0, "discount": 15.0, "per_order": 1}],
    "items": [
        {"name": "巨无霸套餐", "qty": 10, "unit_price": 36.0,
         "promo": {"kind": "limit_price", "scope": "per_order", "limit": 2, "price": 29.0}},
    ],
}


# ---------------------------------------------------------------- 入口


def main():
    ap = argparse.ArgumentParser(description="麦麦拼单团长 · 配餐规划 / 买单策略")
    ap.add_argument("mode", choices=["plan", "pay"], help="plan=配餐规划，pay=买单策略")
    ap.add_argument("--input", "-i", help="JSON 输入文件")
    ap.add_argument("--demo", action="store_true", help="用内置示例运行")
    ap.add_argument("--people", type=int, help="人数（plan 模式快捷参数）")
    ap.add_argument("--budget", type=float, help="总预算（plan 模式快捷参数）")
    ap.add_argument("--scene", default="afternoon",
                    choices=["afternoon", "meal", "overtime"], help="场景（plan 模式）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    args = ap.parse_args()

    if args.mode == "plan":
        if args.demo:
            data = PLAN_DEMO
        elif args.input:
            with open(args.input, encoding="utf-8") as f:
                data = json.load(f)
        elif args.people:
            data = {"people": args.people, "budget_total": args.budget, "scene": args.scene}
        else:
            ap.error("plan 模式请提供 --demo / --input / --people")
        res = plan_mode(data)
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render_plan(res))
    else:
        if args.demo:
            data = PAY_DEMO
        elif args.input:
            with open(args.input, encoding="utf-8") as f:
                data = json.load(f)
        else:
            ap.error("pay 模式请提供 --demo / --input")
        res = pay_mode(data)
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render_pay(res))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
