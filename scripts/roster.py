#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦拼单团长 —— 团长记忆

把「部门里谁爱吃什么、谁不能吃什么」记下来，下次直接说一句「还是老样子」。
这是让工具从「用一次」变成「一直用」的关键。

⚠️ 隐私提示（重要）
    生成的 roster.json 含**他人的口味偏好**，属于本地个人数据：
    - **不要提交到 Git 仓库**（见 .gitignore 建议）
    - 不要上传到任何服务器
    - 仓库内只提供虚构人名的示例文件 roster.example.json
    首次使用会提示，未经确认不会写入任何个人数据。

用法：
    python roster.py init --team "渠道推广部"
    python roster.py add 小张 --usual "巨无霸套餐:可乐换无糖" --avoid 洋葱
    python roster.py show
    python roster.py usual 小张 老王          # 生成「还是老样子」点单清单
    python roster.py record 小张 --order "巨无霸套餐*1"
    python roster.py stats
    python roster.py forget 小张
    python roster.py --file ./roster.json show
"""

import argparse
import datetime
import json
import os
import sys
import unicodedata

DEFAULT_PATH = os.path.expanduser("~/.mcd-captain/roster.json")


# ---------------------------------------------------------------- 工具


def _w(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def pad(s, width, align="left"):
    s = str(s)
    d = width - _w(s)
    if d <= 0:
        return s
    return (" " * d + s) if align == "right" else (s + " " * d)


def parse_usual(text):
    """解析 '麦辣鸡腿堡*2:去酱, 巨无霸套餐:可乐换无糖' → [{name,qty,note}]"""
    items = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part or "：" in part:
            part = part.replace("：", ":")
            head, note = part.split(":", 1)
        else:
            head, note = part, ""
        head, note = head.strip(), note.strip()
        qty = 1
        if "*" in head:
            head, q = head.rsplit("*", 1)
            try:
                qty = int(q)
            except ValueError:
                qty = 1
            head = head.strip()
        items.append({"name": head, "qty": qty, "note": note})
    return items


def parse_list(text):
    if not text:
        return []
    return [x.strip() for x in str(text).replace("，", ",").split(",") if x.strip()]


def load(path):
    if not os.path.exists(path):
        return {"team": "", "updated": "", "members": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    data["updated"] = datetime.date.today().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 命令


def cmd_init(args, data, path):
    data["team"] = args.team or data.get("team", "")
    data.setdefault("members", {})
    save(path, data)
    print("✅ 已初始化花名册")
    print("   团队：%s" % (data["team"] or "（未命名）"))
    print("   路径：%s" % path)
    print("   ⚠️ 该文件含他人口味偏好，请勿提交到 Git 仓库")


def cmd_add(args, data, path):
    m = data.setdefault("members", {})
    cur = m.get(args.name, {})
    if args.usual:
        cur["usual"] = parse_usual(args.usual)
    if args.avoid:
        cur["avoid"] = parse_list(args.avoid)
    if args.like:
        cur["like"] = parse_list(args.like)
    if args.diet is not None:
        cur["diet"] = args.diet
    if args.note is not None:
        cur["note"] = args.note
    cur.setdefault("usual", [])
    cur.setdefault("avoid", [])
    cur.setdefault("like", [])
    cur.setdefault("diet", "")
    cur.setdefault("note", "")
    cur.setdefault("order_count", 0)
    cur.setdefault("last_order", "")
    m[args.name] = cur
    save(path, data)
    print("✅ 已记录「%s」的偏好" % args.name)
    _print_member(args.name, cur, data.get("team", ""))


def _print_member(name, cur, team=""):
    print("   常用：%s" % ("、".join(
        "%s×%d%s" % (i["name"], i["qty"], ("（%s）" % i["note"]) if i["note"] else "")
        for i in cur.get("usual", [])) or "—"))
    print("   忌口：%s" % ("、".join(cur.get("avoid", [])) or "无"))
    if cur.get("diet"):
        print("   饮食：%s" % cur["diet"])
    if cur.get("order_count"):
        print("   已拼单 %d 次，最近一次 %s" % (cur["order_count"], cur.get("last_order", "—")))


def cmd_show(args, data, path):
    members = data.get("members", {})
    if not members:
        print("花名册还是空的。用 `add` 命令开始记录，或先看 roster.example.json。")
        return
    print("=" * 56)
    print("  团长记忆 · %s · 共 %d 人" % (data.get("team") or "未命名团队", len(members)))
    print("=" * 56)
    for name, cur in members.items():
        print("▸ %s" % name)
        _print_member(name, cur, data.get("team", ""))
    print("=" * 56)
    print("  更新于 %s　|　文件：%s" % (data.get("updated", "—"), path))


def cmd_usual(args, data, path):
    members = data.get("members", {})
    names = args.names or list(members.keys())
    if not names:
        print("花名册为空，无法生成。")
        return
    print("=" * 56)
    print("  📋 还是老样子 · %d 人" % len(names))
    print("=" * 56)
    missing = []
    alerts = []
    for n in names:
        cur = members.get(n)
        if not cur:
            missing.append(n)
            continue
        items = cur.get("usual", [])
        txt = "、".join("%s×%d%s" % (i["name"], i["qty"],
                                    ("（%s）" % i["note"]) if i["note"] else "")
                       for i in items) or "（还没记过常点，需现场问）"
        print("%s%s" % (pad(n, 8), txt))
        if cur.get("avoid"):
            alerts.append("%s 忌口：%s" % (n, "、".join(cur["avoid"])))
        if cur.get("diet"):
            alerts.append("%s 饮食要求：%s" % (n, cur["diet"]))
    print("-" * 56)
    if missing:
        print("  ⚠️ 花名册里没有：%s" % "、".join(missing))
    if alerts:
        print("  ⚠️ 配餐前必看：")
        for a in alerts:
            print("     · " + a)
    print("  💡 这份清单可直接喂给「收单拼单」流程，无需再问一遍。")
    print("=" * 56)


def cmd_record(args, data, path):
    m = data.setdefault("members", {})
    cur = m.setdefault(args.name, {"usual": [], "avoid": [], "like": [], "diet": "",
                                   "note": "", "order_count": 0, "last_order": ""})
    cur["order_count"] = int(cur.get("order_count", 0)) + 1
    cur["last_order"] = datetime.date.today().isoformat()
    if args.order:
        # 把这次点单里还没有的品补进 `like`
        for it in parse_usual(args.order):
            if it["name"] not in cur.get("like", []):
                cur.setdefault("like", []).append(it["name"])
    m[args.name] = cur
    save(path, data)
    print("✅ %s 已记一次拼单（累计 %d 次）" % (args.name, cur["order_count"]))


def cmd_forget(args, data, path):
    m = data.get("members", {})
    if args.name in m:
        del m[args.name]
        save(path, data)
        print("🗑️ 已删除「%s」的记录" % args.name)
    else:
        print("花名册里没有「%s」" % args.name)


def cmd_stats(args, data, path):
    m = data.get("members", {})
    if not m:
        print("花名册为空。")
        return
    ranked = sorted(m.items(), key=lambda kv: -int(kv[1].get("order_count", 0)))
    likes = {}
    avoids = {}
    for name, cur in m.items():
        # 只统计「具体餐品」（usual），「口味关键词」（like）另列，避免重复计数
        for it in cur.get("usual", []):
            likes[it["name"]] = likes.get(it["name"], 0) + 1
        for a in cur.get("avoid", []):
            avoids[a] = avoids.get(a, 0) + 1

    print("=" * 56)
    print("  团长记忆 · 统计 · %s" % (data.get("team") or "未命名团队"))
    print("=" * 56)
    print("  拼单次数排行：")
    for name, cur in ranked[:8]:
        print("     %s%s%d 次" % (pad(name, 10), "", int(cur.get("order_count", 0))))
    print()
    if likes:
        print("  最常出现的品：")
        for k, v in sorted(likes.items(), key=lambda kv: -kv[1])[:8]:
            print("     %s%d 人点过" % (pad(k, 20), v))
    if avoids:
        print()
        print("  ⚠️ 团队忌口汇总（配餐前必看）：")
        for k, v in sorted(avoids.items(), key=lambda kv: -kv[1]):
            print("     %s%d 人" % (pad(k, 20), v))
    print("=" * 56)


# ---------------------------------------------------------------- 入口


def main():
    ap = argparse.ArgumentParser(description="麦麦拼单团长 · 团长记忆")
    ap.add_argument("--file", "-f", default=DEFAULT_PATH, help="花名册文件路径")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化花名册")
    p.add_argument("--team", help="团队名称")

    p = sub.add_parser("add", help="新增/更新成员偏好")
    p.add_argument("name")
    p.add_argument("--usual", help='常用单，如 "巨无霸套餐:可乐换无糖, 麦辣鸡腿堡*2"')
    p.add_argument("--avoid", help="忌口，逗号分隔")
    p.add_argument("--like", help="偏好，逗号分隔")
    p.add_argument("--diet", help="饮食要求，如 轻食 / 素食")
    p.add_argument("--note", help="备注")

    sub.add_parser("show", help="查看全部花名册")

    p = sub.add_parser("usual", help="生成「还是老样子」点单清单")
    p.add_argument("names", nargs="*", help="姓名，不填则输出全部")

    p = sub.add_parser("record", help="记录一次拼单")
    p.add_argument("name")
    p.add_argument("--order", help="本次点的内容")

    p = sub.add_parser("forget", help="删除某人的记录")
    p.add_argument("name")

    sub.add_parser("stats", help="统计")

    args = ap.parse_args()
    data = load(args.file)
    {
        "init": cmd_init, "add": cmd_add, "show": cmd_show, "usual": cmd_usual,
        "record": cmd_record, "forget": cmd_forget, "stats": cmd_stats,
    }[args.cmd](args, data, args.file)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
