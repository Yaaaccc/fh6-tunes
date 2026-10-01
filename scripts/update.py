# -*- coding: utf-8 -*-
"""
FH6 调校速查 · 一键更新

流程：抓取（腾讯文档 + vgover 当周攻略） → 生成页面 → 校验 → 记日志

用法：
    python update.py                          # 完整更新
    python update.py --set-guide-url <URL>    # 指定当周攻略地址后再更新
    python update.py --no-fetch               # 只用现有数据重建页面
    python update.py --quiet                  # 精简输出

退出码：0 = 成功；1 = 有硬错误（抓取全失败 / 构建失败）
"""
import os, sys, json, io, re, time, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
DATA = os.path.join(BASE, "data")
sys.path.insert(0, HERE)


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_state():
    p = os.path.join(DATA, "state.json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    json.dump(st, open(os.path.join(DATA, "state.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def log_line(text):
    p = os.path.join(BASE, "更新日志.md")
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write("# FH6 调校速查 · 更新日志\n\n")
            f.write("| 时间 | 当周赛季 | 活动 | 周次 | 车辆榜 | 结果 |\n|---|---|---|---|---|---|\n")
        f.write(text + "\n")


def main():
    argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    quiet = "--quiet" in argv
    no_fetch = "--no-fetch" in argv
    st = load_state()

    if "--set-guide-url" in argv:
        url = argv[argv.index("--set-guide-url") + 1]
        st["week_guide_url"] = url
        save_state(st)
        if not quiet:
            print("已设置当周攻略地址：%s" % url)

    t0 = time.time()
    problems = []
    retry_min = 0
    if "--retry-min" in argv:
        retry_min = int(argv[argv.index("--retry-min") + 1])
        retry_min = max(0, min(retry_min, 120))

    # ── 1) 抓取（可等待换季）──
    if not no_fetch:
        import fh6_lib
        old_week = st.get("last_week")
        deadline = time.time() + retry_min * 60
        while True:
            if not quiet:
                print("—— 抓取数据 ——")
            r = fh6_lib.fetch_all(verbose=not quiet)
            json.dump(r, open(os.path.join(DATA, "last_fetch.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            problems = r.get("errors", [])
            try:
                _w = json.load(open(os.path.join(DATA, "weeks.json"), encoding="utf-8"))
                new_week = _w[0]["title"] if _w else ""
            except Exception:
                new_week = ""
            if len(problems) > 8:
                print("!! 抓取失败过多，可能网络不通。已保留上次数据，不覆盖页面。")
                log_line("| %s | - | - | - | - | ❌ 抓取失败（%d 个错误），已保留旧页面 |"
                         % (now(), len(problems)))
                return 1
            if not retry_min or not old_week or new_week != old_week:
                break
            if time.time() >= deadline:
                if not quiet:
                    print("  等待 %.0f 分钟仍未见换周（社区表当周仍是「%s」），先按现状生成"
                          % (retry_min, new_week))
                break
            if not quiet:
                print("  社区表当周仍是「%s」，尚未换周 —— 5 分钟后再试" % new_week)
            time.sleep(300)

    # ── 2) 构建 ──
    if not quiet:
        print("—— 生成页面 ——")
    if no_fetch:
        # 构建阶段会取车型目录；--no-fetch 时连它也不去碰网络
        os.environ["FH6_OFFLINE"] = "1"
    import fh6_build
    out_html = fh6_build.main()

    # ── 3) 校验 ──
    weeks = json.load(open(os.path.join(DATA, "weeks.json"), encoding="utf-8"))
    guide = {}
    gp = os.path.join(DATA, "week_guide.json")
    if os.path.exists(gp):
        guide = json.load(open(gp, encoding="utf-8"))
    groups = json.load(open(os.path.join(DATA, "groups.json"), encoding="utf-8"))

    cur_week = weeks[0]["title"] if weeks else ""
    cur_date = weeks[0]["date"] if weeks else ""
    g_date = guide.get("date", "")
    n_ev = len(guide.get("events", []))
    n_car = sum(len([e for e in g["entries"] if e.get("车辆型号")]) for g in groups)

    # 周次是否真的换了
    changed = (st.get("last_week") != cur_week)

    warn = []
    if not guide:
        warn.append("当周攻略缺失（week_guide.json）——限制原文一栏会空")
    elif g_date:
        # 攻略日期与腾讯文档当周日期比对（只比「月/日 至 月/日」主体）
        a = set(re.findall(r"\d+月\d+日", g_date.replace(" ", "")))
        b = set(re.findall(r"\d+月\d+日", cur_date.replace(" ", "")))
        if a and b and not (a & b):
            warn.append("当周攻略日期(%s) 与社区表当周(%s) 不一致，可能攻略尚未更新" % (g_date, cur_date))
    if not weeks:
        warn.append("季节赛数据为空")

    # ── 4) 落盘状态 + 日志 ──
    st["last_run"] = now()
    st["last_week"] = cur_week
    st["last_date"] = cur_date
    st["last_stats"] = {"events": n_ev, "weeks": len(weeks), "cars": n_car}
    st.setdefault("history", [])
    if changed:
        st["history"].append({"week": cur_week, "date": cur_date, "at": now()})
        st["history"] = st["history"][-40:]
    save_state(st)

    flag = "🔄 换季" if changed else "✅ 更新"
    res = "%s 当周 %d 项 · %d 周 · %d 台车" % (flag, n_ev, len(weeks), n_car)
    if warn:
        res += " ｜⚠ " + "；".join(warn)
    log_line("| %s | %s | %d | %d | %d | %s |"
             % (now(), cur_week or "-", n_ev, len(weeks), n_car,
                (flag + (" ⚠ " + "；".join(warn) if warn else ""))))

    if not quiet:
        print("—— 结果 ——")
        print("  页面：%s（%.0f KB）" % (os.path.relpath(out_html, BASE),
                                        os.path.getsize(out_html) / 1024))
        print("  当周：%s %s · %d 项活动" % (cur_week, cur_date, n_ev))
        print("  数据：%d 个赛季周（含历史） · %d 台各模式上榜车" % (len(weeks), n_car))
        print("  耗时：%.1fs" % (time.time() - t0))
        for w in warn:
            print("  ⚠ %s" % w)
        for p in problems[:6]:
            print("  ! %s" % p)
        if changed:
            print("  🔄 检测到换季，页面已刷新到最新一周")
    return 0


if __name__ == "__main__":
    sys.exit(main())
