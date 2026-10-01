# -*- coding: utf-8 -*-
"""fh6_catalog 回归自测 —— 改匹配逻辑后必跑

用法：
    python scripts/test_catalog.py
判据：所有断言通过则打印 PASS；任何一条失败请先修匹配器，别先改预期。
"""
import io, os, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fh6_catalog as C
import fh6_build as B

DATA = os.path.join(os.path.dirname(HERE), "data")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def main():
    cat = C.Catalog(json.load(io.open(os.path.join(DATA, "catalog.json"), encoding="utf-8")))
    print("目录 %d 台 · 索引键 %d · 歧义键 %d"
          % (len(cat.cars), len(cat._idx_all),
             sum(1 for v in cat._idx_all.values() if len(v) > 1)))

    # ── 1) 货币/外观类奖励不能被当成车 ──
    print("\n[1] 非车辆奖励必须过滤")
    for t in ["100,000 CR", "120,000 CR", "抽奖", "点数 ×5", "服装：赛车手套",
              "喇叭：生日快乐", "经验值", "徽章：新手"]:
        check(not C.reward_items([{"name": "x", "kind": "k", "reward": t}]),
              "过滤：%s" % t)
    check(bool(C.reward_items([{"name": "x", "kind": "k", "reward": "Peel P50"}])),
          "保留：Peel P50")

    # ── 2) 文案尾巴要能剥干净 ──
    print("\n[2] 年份/括注尾巴")
    for raw, want in [("Peel P50", "Peel P50"),
                      ("Peel P50 - 1962 年", "Peel P50"),
                      ("Audi RS6", "Audi RS6"),
                      ("Porsche 911", "Porsche 911"),
                      ("BMW M3 1997", "BMW M3"),
                      ("捷豹 C-X75 - 2010 年（每周挑战所需）", "捷豹 C-X75")]:
        check(C.core(raw) == want, "core(%r) == %r" % (raw, want))

    # ── 3) 曾踩过的坑：宁缺勿错 ──
    print("\n[3] 曾踩过的坑")
    for text, want in [("Peel P50 - 1962 年", "Peel P50"),
                       ("MG Metro 6R4 - 1986 年", "MG Metro 6R4"),
                       ("Reliant Supervan III - 1972 年", "Reliant Supervan"),
                       ("捷豹 C-X75 - 2010 年（每周挑战所需）", "捷豹 C-X75"),
                       ("兰博基尼 Tecnica", "Huracán Tecnica"),
                       ("雪佛兰 Corvette '53", "Corvette '53"),
                       ("本田 2000", None)]:      # S2000 歧义 → 必须放弃
        c = cat.match_name(text)
        got = cat.name(c) if c else None
        check(got == want, "%s -> %s（期望 %s）" % (text, got, want))

    # ── 4) 同名键不得乱挑 ──
    print("\n[4] 歧义键不得随机挑一台")
    for key in ["civictyper", "m5", "corvettezr1"]:
        check(cat._uniq(key) is None, "歧义键 %s → 唯一命中为 None" % key)

    # ── 5) 全库自洽：每台车名（含尾巴格式）都要回到本车 ──
    print("\n[5] 全库自洽扫描")
    n = ok = miss = 0
    dupname = 0
    for c in cat.cars:
        sh = c.get("short") or c.get("model")
        if not sh:
            continue
        for text in (sh, "%s - %s 年" % (sh, c.get("year") or ""), "%s（每周挑战所需）" % sh):
            n += 1
            r = cat.match_name(text)
            if r is None:
                miss += 1
            elif r.get("id") == c.get("id"):
                ok += 1
            elif cat.name(r) == cat.name(c):
                dupname += 1          # 库里同名重复车，无害
    check(miss == 0, "零漏匹（%d 次试验）" % n)
    check(ok + dupname == n, "无真匹错（同名重复 %d 例）" % dupname)
    print("     回到本车 %d/%d = %.2f%%" % (ok, n, 100.0 * ok / n))

    print()
    if fails:
        print("FAIL —— %d 条未通过：" % len(fails))
        for f in fails:
            print("   ·", f)
        return 1
    print("PASS —— 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
