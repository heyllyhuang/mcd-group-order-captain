#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦拼单团长 —— 拼单战报生成器

把一次拼单的结果变成一张**可以发朋友圈/群里的战报**。
团长会自发分享 —— 这样作品就自带传播属性。

输入：split_bill.py 的 JSON 输出（或任何符合该结构的数据）
输出：一张自包含的 HTML 战报，可直接截图分享

用法：
    python battle_report.py --demo
    python battle_report.py --demo --out battle-report.html
    python battle_report.py --input result.json --team "渠道推广部" --out 战报.html
"""

import argparse
import datetime
import json
import os
import sys

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦麦拼单战报</title>
<style>
  :root{--red:#DA291C;--yellow:#FFC72C;--ink:#1F1B18;--ink2:#6B6259;--line:#EDE7DF;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#F2EEE9;font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,sans-serif;
       color:var(--ink);display:flex;justify-content:center;padding:26px 16px}
  .card{width:440px;background:#fff;border-radius:20px;overflow:hidden;
        box-shadow:0 12px 34px rgba(31,27,24,.14)}
  .head{background:linear-gradient(135deg,#DA291C 0%,#B01E13 100%);color:#fff;
        padding:22px 24px 18px;position:relative;overflow:hidden}
  .head::after{content:"";position:absolute;right:-36px;top:-42px;width:140px;height:140px;
               border-radius:50%;background:var(--yellow);opacity:.2}
  .kicker{font-size:12px;opacity:.92;letter-spacing:.4px;position:relative}
  .head h1{font-size:21px;font-weight:800;margin-top:6px;position:relative;letter-spacing:.3px}
  .hero{padding:24px 24px 18px;text-align:center;border-bottom:1px dashed var(--line)}
  .hero-label{font-size:12.5px;color:var(--ink2)}
  .hero-num{font-size:48px;font-weight:800;color:var(--red);line-height:1.12;
            margin:4px 0 2px;font-variant-numeric:tabular-nums;letter-spacing:-1.5px}
  .hero-sub{font-size:12.5px;color:var(--ink2)}
  .grid{display:flex;padding:16px 14px;gap:8px}
  .g{flex:1;text-align:center;background:#FFFCF6;border:1px solid var(--line);
     border-radius:12px;padding:11px 4px}
  .g b{display:block;font-size:19px;font-weight:800;font-variant-numeric:tabular-nums}
  .g span{font-size:11.5px;color:var(--ink2)}
  .block{padding:4px 24px 16px}
  .bt{font-size:12.5px;font-weight:700;color:var(--ink2);margin-bottom:9px;
      padding-top:10px;border-top:1px solid var(--line)}
  .bd{display:flex;justify-content:space-between;font-size:13px;padding:4px 0}
  .bd b{color:var(--red);font-variant-numeric:tabular-nums}
  .aw{display:flex;align-items:center;gap:9px;font-size:13px;padding:5px 0}
  .aw .ico{font-size:15px}
  .aw .t{color:var(--ink2);flex:0 0 76px}
  .aw .n{font-weight:700}
  .aw .v{margin-left:auto;color:var(--ink2);font-size:12px;font-variant-numeric:tabular-nums}
  .foot{padding:14px 24px 20px;background:#FFFDF8;border-top:1.5px dashed var(--line);
        font-size:11px;color:var(--ink2);text-align:center;line-height:1.7}
  .foot b{color:var(--ink)}
</style>
</head>
<body>
  <div class="card">
    <div class="head">
      <div class="kicker">__TEAM__ · __DATE__</div>
      <h1>🍟 麦麦拼单战报</h1>
    </div>

    <div class="hero">
      <div class="hero-label">本次共省</div>
      <div class="hero-num">¥__SAVED__</div>
      <div class="hero-sub">__DISCOUNT_LINE__</div>
    </div>

    <div class="grid">
      <div class="g"><b>__PEOPLE__</b><span>人参与</span></div>
      <div class="g"><b>__ITEMS__</b><span>件商品</span></div>
      <div class="g"><b>¥__PER__</b><span>人均</span></div>
    </div>

    <div class="block">
      <div class="bt">钱是怎么省下来的</div>
      __BREAKDOWN__
    </div>

    <div class="block">
      <div class="bt">本单之最</div>
      __AWARDS__
    </div>

    <div class="foot">
      由 <b>麦麦拼单团长</b> 生成 · 基于麦当劳 MCP<br>
      示例数据，实际价格以麦当劳官方渠道为准
    </div>
  </div>
</body>
</html>
"""


def build(data, team="", date=None):
    s = data.get("summary", {})
    people = data.get("per_person", [])
    date = date or datetime.date.today().isoformat()

    orig = float(s.get("orig_total", 0))
    payable = float(s.get("payable_total", 0))
    saved = float(s.get("discount_total", 0))
    n = int(s.get("people", len(people))) or 1

    if saved > 0 and orig > 0:
        disc = payable / orig * 10
        discount_line = "相当于打了 %.1f 折（原价 ¥%.1f）" % (disc, orig)
    elif saved == 0:
        discount_line = "这次没吃到优惠，已按最优方式组合（原价 ¥%.1f）" % orig
    else:
        discount_line = "原价 ¥%.1f" % orig

    # 省钱拆解
    parts = []
    if s.get("promo_save"):
        parts.append(("第二份半价 / 限购名额", float(s["promo_save"])))
    if s.get("shared_discount"):
        parts.append(("满减券", float(s["shared_discount"])))
    if s.get("person_discount"):
        parts.append(("专属券", float(s["person_discount"])))
    if parts:
        breakdown = "".join(
            '<div class="bd"><span>%s</span><b>−¥%.1f</b></div>' % (k, v) for k, v in parts)
        breakdown += '<div class="bd" style="border-top:1px solid #EDE7DF;margin-top:5px;padding-top:7px">' \
                     '<span>实付</span><b>¥%.1f</b></div>' % payable
    else:
        breakdown = '<div class="bd"><span>本次未产生优惠</span><b>¥%.1f</b></div>' % payable

    # 本单之最（只谈消费内容，不涉及个人特征）
    awards = []
    if people:
        by_orig = sorted(people, key=lambda p: -float(p.get("orig", 0)))
        top = by_orig[0]
        light = by_orig[-1]
        awards.append(("🏆", "最大单", top.get("name", "?"),
                       "¥%.1f" % float(top.get("orig", 0))))
        if len(by_orig) > 1 and light.get("name") != top.get("name"):
            awards.append(("🍃", "最清淡", light.get("name", "?"),
                           "¥%.1f" % float(light.get("orig", 0))))
        by_pay = sorted(people, key=lambda p: -float(p.get("payable", 0)))
        # 与「最大单」同名时跳过，避免重复展示同一个人
        if by_pay[0].get("name") != top.get("name"):
            awards.append(("🧮", "付得最多", by_pay[0].get("name", "?"),
                           "¥%.1f" % float(by_pay[0].get("payable", 0))))
    award_html = "".join(
        '<div class="aw"><span class="ico">%s</span><span class="t">%s</span>'
        '<span class="n">%s</span><span class="v">%s</span></div>' % a for a in awards)

    html = TEMPLATE
    for k, v in {
        "__TEAM__": team or "拼单团",
        "__DATE__": date,
        "__SAVED__": "%.1f" % saved,
        "__DISCOUNT_LINE__": discount_line,
        "__PEOPLE__": str(n),
        "__ITEMS__": str(s.get("items", 0)),
        "__PER__": "%.1f" % (payable / n),
        "__BREAKDOWN__": breakdown,
        "__AWARDS__": award_html,
    }.items():
        html = html.replace(k, v)
    return html


DEMO = {
    "mode": "A",
    "summary": {
        "people": 5, "items": 7,
        "orig_total": 187.0, "promo_save": 15.8, "shared_discount": 15.0,
        "person_discount": 5.0, "discount_total": 35.8, "payable_total": 151.2,
        "saved_pct": 19.1,
    },
    "per_person": [
        {"name": "小张", "orig": 36.0, "payable": 29.1},
        {"name": "小李", "orig": 26.5, "payable": 21.4},
        {"name": "小王", "orig": 44.0, "payable": 35.6},
        {"name": "老王", "orig": 47.0, "payable": 38.0},
        {"name": "团长", "orig": 33.5, "payable": 27.1},
    ],
}


def main():
    ap = argparse.ArgumentParser(description="麦麦拼单团长 · 战报生成")
    ap.add_argument("--input", "-i", help="结算 JSON（split_bill.py --json 的输出）")
    ap.add_argument("--out", "-o", default="battle-report.html", help="输出 HTML 路径")
    ap.add_argument("--team", default="", help="团队名称")
    ap.add_argument("--demo", action="store_true", help="用内置示例运行")
    args = ap.parse_args()

    if args.demo:
        data = DEMO
    elif args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    else:
        ap.error("请提供 --input <文件> 或 --demo")

    html = build(data, team=args.team)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 战报已生成：%s" % os.path.abspath(args.out))
    print("   用浏览器打开后截图，即可分享到群里 / 朋友圈")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
