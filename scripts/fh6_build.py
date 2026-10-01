# -*- coding: utf-8 -*-
"""
FH6 调校速查 · 页面构建

读 data/ 下的结构化数据 → 生成单文件离线网页 + Markdown
   FH6-调校速查.html   （三个标签页：本周赛事 / 季节赛限定车 / 各模式车辆榜）
   FH6-调校速查.md

数据源：
   data/week_guide.json  当周攻略（vgover）→ 游戏内类别限制原文 + 推荐车 + 调校码
   data/weeks.json       18 周季节赛（腾讯文档）→ 限定车 / 调校师 / 码
   data/groups.json      14 个组别车辆榜（腾讯文档）→ 各模式上榜车
"""
import os, json, re, html, io, datetime

import fh6_catalog

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")


def load(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


def esc(s):
    return html.escape(str(s or ""))


def digits(s):
    """从 '882 293 766' 提取 882293766"""
    d = re.sub(r"\D", "", s or "")
    return d if len(d) == 9 else ""


def code_btn(code, small=False):
    if not code:
        return "<span class='dash'>—</span>"
    return ("<button class='code%s' data-c='%s' title='点击复制'>%s<span class='cp'>复制</span></button>"
            % (" small" if small else "", code, code))


# ─────────────── 当周赛事：结构化 ───────────────
KIND_ORDER = ["每周挑战", "季节锦标赛", "终极考验", "漂移冲分赛", "危险标志",
              "测速区间", "测速照相", "拓荒者门", "拓荒者", "计时赛", "照片挑战",
              "寻宝游戏", "每日挑战", "每月劲敌", "地平线乐玩", "地平线特技派对",
              "收藏品", "捉迷藏", "淘汰之王", "山道对决", "直线车友赛"]
KIND_TAG = {
    "每周挑战": ("必须用", "hard"), "季节锦标赛": ("按类别", "class"),
    "终极考验": ("按类别", "class"), "山道对决": ("按类别", "class"),
    "危险标志": ("推荐车", "single"), "测速区间": ("推荐车", "single"),
    "测速照相": ("推荐车", "single"), "拓荒者": ("推荐车", "single"),
    "拓荒者门": ("推荐车", "single"), "计时赛": ("推荐车", "single"),
    "漂移冲分赛": ("推荐车", "single"), "漂移区域": ("推荐车", "single"),
    "每月劲敌": ("试驾车", "trial"), "照片挑战": ("按条件", "cond"),
    "寻宝游戏": ("任意车", "free"), "每日挑战": ("任意车", "free"),
    "地平线乐玩": ("任意车", "free"), "地平线特技派对": ("任意车", "free"),
    "收藏品": ("任意车", "free"), "捉迷藏": ("任意车", "free"),
    "淘汰之王": ("任意车", "free"),
}


def norm_week(guide):
    """vgover 攻略 → 统一活动结构"""
    NOISE = ("www.", "访问", "攻略专区", "图文攻略", "更多游戏资讯", "点击查看",
             "电玩帮", "未经授权", "原文链接")

    out = []
    for e in guide.get("events", []):
        f = e.get("fields", {})
        kind = e.get("kind") or "其他"
        name = e.get("name") or e.get("raw", "")
        # 限制原文：优先「类型 + 等级」；照片/寻宝类取各自的要求字段
        car_req = f.get("车辆要求", "")
        lvl_req = f.get("等级要求", "")
        if car_req.startswith("类型"):
            car_req = car_req.split("-", 1)[-1].strip()
        limit = " · ".join([x for x in (car_req, lvl_req) if x])
        if not limit:
            for k in ("拍摄要求", "寻宝地点", "任务要求", "活动要求", "完成条件"):
                if f.get(k):
                    limit = f[k]
                    break
        subs = [s for s in e.get("items", [])
                if s and not any(k in s for k in NOISE)]
        note = f.get("备注", "") or f.get("注", "")
        if len(note) > 110:
            note = note[:110] + "…"
        out.append({
            "kind": kind, "name": name,
            "limit": limit,
            "car_req": car_req, "lvl_req": lvl_req,
            "points": f.get("分数奖励", ""),
            "rec_car": f.get("推荐车辆", ""),
            "code": digits(f.get("调校代码", "")),
            "code_raw": f.get("调校代码", ""),
            "reward": f.get("奖励") or f.get("车辆奖励", ""),
            "obtain": f.get("车辆获取", ""),
            "note": note,
            "subs": subs,
            "fields": f,
        })

    def key(e):
        try:
            return KIND_ORDER.index(e["kind"])
        except ValueError:
            return 99
    return sorted(out, key=key)


# ─────────────── HTML ───────────────
def value_pane(nw, cat, guide):
    """⓪ 本周值不值得做 —— 按「买不到」+「我没有」两条判据"""
    items = fh6_catalog.reward_items(nw)
    rows, stars = [], []
    for it in items:
        car = cat.match_name(it["text"])
        if car:
            st, tag, why = cat.verdict(car)
            rows.append({
                "text": it["text"], "event": it["event"], "kind": it["kind"],
                "name": cat.name(car), "cid": car.get("id"), "rarity": cat.rarity(car),
                "src": "／".join(cat.sources(car)), "cost": car.get("cost") or 0,
                "star": st, "tag": tag, "why": why, "known": True,
            })
        else:
            rows.append({
                "text": it["text"], "event": it["event"], "kind": it["kind"],
                "name": it["text"], "cid": "", "rarity": "—", "src": "—", "cost": 0,
                "star": 0, "tag": "未能定位",
                "why": "车型库里没找到这台，不猜——按游戏内实际为准", "known": False,
            })
        stars.append(rows[-1]["star"])
    rows.sort(key=lambda r: (-r["star"], r["name"]))

    n_car = len(rows)
    n_hard = sum(1 for r in rows if r["tag"] == "买不到")
    best = max(stars) if stars else 0
    if not rows:
        lvl, big = 0, "本周奖励里没有车"
        why = "本周 %d 个活动的奖励都是点数 / 抽奖 / 外观件，没有车辆奖励。" % len(nw)
    elif best >= 3:
        lvl, big = 3, "值得做"
        why = ("本周 %d 台奖励车里，有 <b>%d 台车展买不到</b>——错过这周就得靠抽奖碰运气或等复刻。"
               % (n_car, n_hard))
    elif best == 2:
        lvl, big = 2, "可以做，但不是刚需"
        if n_hard:
            why = ("本周 %d 台奖励车里没有只能靠季节赛拿的；有 %d 台车展买不到，值得顺手做掉。"
                   % (n_car, n_hard))
        else:
            why = ("本周 %d 台奖励车<b>车展都能买到</b>，但档位／价位不低（传奇或百万级），"
                   "顺手做掉等于白拿一笔、不做也不亏。" % n_car)
    else:
        lvl, big = 1, "可以不急"
        why = "本周 %d 台奖励车<b>都能在车展直接买到</b>，随手做拿个折扣即可，不做也不损失。" % n_car

    cards = []
    for r in rows:
        v = "v%d" % min(3, r["star"])
        meta = ["<span>%s</span>" % esc(r["rarity"])]
        if r["src"] != "—":
            meta.append("<span>%s</span>" % esc(r["src"]))
        if r["cost"]:
            meta.append("<span>车展价 %s CR</span>" % "{:,}".format(r["cost"]))
        cards.append(
            "<article class='rc %s' data-cid='%s' data-txt='%s' data-star='%d' data-tag='%s'>"
            "<div class='rhead'><span class='stars'>%s</span>"
            "<span class='pill %s'>%s</span></div>"
            "<h4>%s</h4>"
            "<div class='rmeta'>%s</div>"
            "<div class='rwhy'>%s</div>"
            "<div class='rev'>来自：%s%s</div></article>" % (
                v, esc(str(r["cid"])),
                esc((r["name"] + r["text"] + r["event"]).lower()),
                r["star"], esc(r["tag"]),
                "★" * r["star"] + "☆" * (3 - r["star"]),
                {"买不到": "no", "能买到": "yes"}.get(r["tag"], "unk"), esc(r["tag"]),
                esc(r["name"]), "".join(meta), r["why"],
                esc(r["kind"]), (" · " + esc(r["event"])) if r["event"] else ""))

    others = [e for e in nw if not any(e["name"] == r["event"] and e["kind"] == r["kind"]
                                       for r in rows)]
    o_rows = "".join(
        "<tr><td class='k'>%s</td><td class='nm'>%s</td><td class='rw'>%s</td></tr>" % (
            esc(e["kind"]), esc(e["name"]), esc(e["reward"] or "—")) for e in others)

    body = ["<div class='vsum v%d' id='vsum'><div class='vbig'>%s</div><div class='vwhy'>%s</div></div>"
            % (lvl, big, why),
            "<div class='bar'><input id='q0' placeholder='搜索奖励车 / 活动名 …'>"
            "<span id='c0' class='cnt'></span>"
            "<button class='btn pri' id='scan-pick'>读存档 · 本地比对</button>"
            "<input type='file' id='scan-file' webkitdirectory directory multiple hidden></div>",
            "<div class='scan' id='scan' hidden><div id='scan-out'></div></div>",
            "<div class='rgrid'>%s</div>" % "".join(cards)]
    if o_rows:
        body.append("<details class='sec'><summary>本周其余活动（奖励不是车）"
                    "<span class='wkstat'>%d 项</span></summary><div class='tw'>"
                    "<table><thead><tr><th>类型</th><th>活动</th><th>奖励</th></tr></thead>"
                    "<tbody>%s</tbody></table></div></details>" % (len(others), o_rows))
    body.append(
        "<details class='sec'><summary>判据是怎么定的 · 以及哪里可能不准</summary>"
        "<div class='notes' style='border:none;margin:0;border-radius:0'>"
        "<ul>"
        "<li><b>第一判据「买不到」</b>：看这台车的获取途径里有没有「车展」。没有 = 买不到。"
        "三星＝只能靠季节赛事 / 车房宝物 / 秘藏座驾；两星＝车展买不到，或档位是传奇 / 极限竞速特别版；"
        "一星＝车展随时能买。</li>"
        "<li><b>第二判据「我没有」</b>：<b>本页不读加密内容</b>。FH6 的完整车库清单在存档 "
        "<code>C_ProfileData</code> 里且是加密的，社区没有公开解密实现。本页只读存档里两处不加密的地方——"
        "顶层摘要里写明的车库车辆总数，以及 <code>Livery_&lt;序号&gt;</code> / <code>Tuning_&lt;序号&gt;</code> "
        "目录名里的车辆序号。所以它只能确认<b>您涂装过或调校过的车</b>；其余标「未见」，"
        "而<b>「未见」不等于没有</b>。</li>"
        "<li><b>可能不准的地方</b>：获取途径来自社区整理，游戏版本更新后可能变；"
        "奖励车名是从攻略文案里抽的，个别会有笔误（比如把 Dino 写成 Dion），"
        "这类词本页会标「未能定位」而不是硬凑一个。</li>"
        "</ul></div></details>")

    return ("<div class='curbar'><b>%s</b><span class='tag'>本周</span>"
            "<span class='dt'>%s</span><span class='dt'>· 季节每周四晚 22:30（北京时间）更新</span></div>"
            % (esc(guide.get("title") or "-"), esc(guide.get("date") or ""))), \
           "".join(body), n_car, n_hard


# 站外入口：B 站「地平线六车辆数据库」的外壳页。
# 用外壳地址而不是内层 app 地址 —— 内层带版本号（...-v13574/），官方升级后会变，写死就会失效。
TOY_URL = "https://www.bilibili.com/toy/forzahorizon6/index.html"


def build_html(guide, weeks, groups, ts, cat=None):
    nw = norm_week(guide) if guide else []
    cur = weeks[0] if weeks else {"title": "-", "date": "-", "events": []}

    # 标题：S5 · 英国汽车 · 冬季（主题从周标题里取，season 只补一次）
    series = guide.get("series", "")
    season = guide.get("season", "")
    theme = ""
    mt = re.match(r"系列赛\s*\d+\s*(.+?)\s*[夏秋春冬]季", cur.get("title", "") or "")
    if not mt:
        mt = re.match(r"[SＳ]\s*\d+\s*(.+?)\s*[夏秋春冬]季", guide.get("title", "") or "")
    if mt:
        theme = mt.group(1).strip()
    cur_title = " ".join(x for x in [series, theme, season] if x) or (cur.get("title") or "-")

    # ---- Tab1: 本周赛事 ----
    def ev_card(e):
        tag, cls = KIND_TAG.get(e["kind"], ("活动", "free"))
        subs = "".join("<div class='sub'>· %s</div>" % esc(s) for s in e["subs"][:8])
        limit_html = ("<div class='limit'><span class='lk'>游戏限制</span><b>%s</b></div>"
                      % esc(e["limit"])) if e["limit"] else ""
        meta = []
        if e["rec_car"]:
            meta.append("<span class='rec'>推荐 <b>%s</b></span>" % esc(e["rec_car"]))
        if e["points"]:
            meta.append("<span class='pts'>%s</span>" % esc(e["points"]))
        if e["reward"]:
            meta.append("<span class='rwd'>奖励 %s</span>" % esc(e["reward"]))
        return ("<article class='ev' data-txt='%s'>"
                "<div class='evh'><span class='badge %s'>%s</span>"
                "<span class='kind'>%s</span><span class='evn'>%s</span></div>"
                "%s<div class='evm'>%s%s</div>%s%s</article>") % (
            esc((e["kind"] + e["name"] + e["limit"] + e["rec_car"] + e["code"]).lower()),
            cls, tag, esc(e["kind"]), esc(e["name"]), limit_html,
            "".join(meta),
            ("<span class='cdwrap'>%s</span>" % code_btn(e["code"], True)) if e["code"] else "",
            ("<div class='note'>%s</div>" % esc(e["note"])) if e["note"] else "",
            subs)

    week_body = "".join(ev_card(e) for e in nw)
    # 社区表当周（第二套方案）
    comm_rows = []
    for e in cur.get("events", []):
        if e.get("code") or e.get("tuner"):
            comm_rows.append(
                "<tr><td class='k'>%s</td><td class='nm'>%s</td><td class='car'>%s</td>"
                "<td class='tn'>%s</td><td>%s</td><td class='rw'>%s</td></tr>" % (
                    esc(e["type"]), esc(e["name"]), esc(e["car"]),
                    esc(e["tuner"] or "—"), code_btn(e["code"], True), esc(e["reward"])))
    comm_tbl = ("<details class='sec' open><summary>社区表另一套方案（%s）"
                "<span class='wkstat'>%d 条带调校 · 来自腾讯文档</span></summary>"
                "<div class='tw'><table><thead><tr><th>类型</th><th>活动</th>"
                "<th>限定车辆/条件</th><th>调校师</th><th>调校码</th><th>奖励</th></tr></thead>"
                "<tbody>%s</tbody></table></div></details>"
                % (esc(cur.get("date", "")), len(comm_rows), "".join(comm_rows)))

    # ---- Tab2: 季节赛限定车 ----
    LEVELS = ["硬性指定车型", "类别限定", "推荐用车", "品牌/条件限定", "无车辆限制"]
    LVCLS = {"硬性指定车型": "hard", "类别限定": "class", "推荐用车": "single",
             "品牌/条件限定": "cond", "无车辆限制": "free"}
    LVICON = {"硬性指定车型": "必须用", "类别限定": "按类别", "推荐用车": "推荐",
              "品牌/条件限定": "条件", "无车辆限制": "任意"}

    def week_block(i, w):
        trs = []
        for e in w["events"]:
            subs = "".join("<div class='sub'>%s %s</div>" % (esc(s["name"]), esc(s["text"]))
                           for s in e.get("subs", []))
            limit = e["level"] != "无车辆限制"
            trs.append(
                "<tr data-limit='%d' data-txt='%s'><td><span class='badge %s'>%s</span>"
                "<span class='kind s'>%s</span></td><td class='nm'>%s%s</td><td class='car'>%s</td>"
                "<td class='tn'>%s</td><td>%s</td><td class='rw'>%s</td></tr>" % (
                    limit, esc((e["type"] + e["name"] + e["car"] + e["code"] +
                                e["tuner"] + e["reward"]).lower()),
                    LVCLS[e["level"]], LVICON[e["level"]], esc(e["type"]),
                    esc(e["name"]), subs, esc(e["car"]), esc(e["tuner"] or ""),
                    code_btn(e["code"], True), esc(e["reward"])))
        return ("<details class='wk' %s><summary><span class='wkname'>%s</span>"
                "<span class='wkdate'>%s</span><span class='wkstat'>%d 项 · %d 个限定</span>"
                "</summary><div class='tw'><table><thead><tr><th>类型</th><th>活动名称</th>"
                "<th>社区表推荐车 / 条件</th><th>调校师</th><th>调校码</th><th>奖励</th></tr></thead>"
                "<tbody>%s</tbody></table></div></details>"
                % ("open" if i == 0 else "", esc(w["title"]), esc(w["date"]),
                   len(w["events"]),
                   sum(1 for e in w["events"] if e["level"] != "无车辆限制"), "".join(trs)))

    weeks_body = "".join(week_block(i, w) for i, w in enumerate(weeks))

    # 车型索引
    idx = {}
    for w in weeks:
        for e in w["events"]:
            if e["level"] not in ("硬性指定车型", "类别限定", "推荐用车"):
                continue
            nm = re.sub(r"^(拥有并驾驶|驾驶|使用)\s*", "", e["car"]).strip()
            nm = re.sub(r"\s*完成.*$", "", nm).strip()
            if len(nm) < 4:
                continue
            if not (re.match(r"^(19|20)\d{2}\s", nm) or e["level"] == "硬性指定车型"):
                continue
            if re.search(r"完成|获得|达成|拍摄|停车", nm):
                continue
            d = idx.setdefault(nm, {"car": nm, "n": 0, "codes": [], "weeks": [], "types": set()})
            d["n"] += 1
            d["weeks"].append(w["date"])
            d["types"].add(e["type"])
            if e["code"]:
                d["codes"].append((e["tuner"], e["code"]))
    cars = sorted(idx.values(), key=lambda d: (-d["n"], d["car"]))
    car_rows = "".join(
        "<tr><td class='nm'>%s</td><td class='cen'>%d</td><td class='car'>%s</td>"
        "<td class='tn'>%s</td><td>%s</td><td class='rw'>%s</td></tr>" % (
            esc(d["car"]), d["n"], esc("、".join(sorted(d["types"]))),
            esc(d["codes"][0][0]) if d["codes"] else "—",
            code_btn(d["codes"][0][1], True) if d["codes"] else "<span class='dash'>—</span>",
            esc(d["weeks"][-1]))
        for d in cars if d["n"] >= 2)

    # ---- Tab3: 各模式车辆榜 ----
    def group_block(g):
        es = [e for e in g["entries"] if e.get("车辆型号")]
        if not es:
            return ""
        rows = "".join(
            "<tr><td class='nm'>%s</td><td class='car'>%s</td><td class='cen'>%s</td>"
            "<td class='tn'>%s</td><td class='tn'>%s</td><td class='tn'>%s</td>"
            "<td class='tn'>%s</td><td class='rw'>%s</td></tr>" % (
                esc(e.get("车辆型号", "")), esc(e.get("制造商", "")),
                esc(e.get("竞争力", "")), esc(e.get("轮胎", "")), esc(e.get("驱动", "")),
                esc(e.get("难度", "")), "/".join(esc(x) for x in (e.get("调校师") or [])[:4]),
                esc(e.get("备注", ""))[:60])
            for e in es)
        return ("<details class='wk'><summary><span class='wkname'>%s</span>"
                "<span class='wkstat'>%d 台车上榜</span></summary><div class='tw'>"
                "<table><thead><tr><th>车辆</th><th>制造商</th><th>竞争力</th><th>轮胎</th>"
                "<th>驱动</th><th>难度</th><th>调校师（按推荐序）</th><th>备注</th></tr></thead>"
                "<tbody>%s</tbody></table></div></details>" % (esc(g["name"]), len(es), rows))

    groups_body = "".join(group_block(g) for g in groups)
    n_cars = sum(len([e for e in g["entries"] if e.get("车辆型号")]) for g in groups)
    n_lock = sum(1 for w in weeks for e in w["events"] if e["level"] != "无车辆限制")
    n_code = sum(1 for w in weeks for e in w["events"] if e["code"])

    HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>地平线 6 · 本周值不值得做（附调校速查）</title>
<meta name="description" content="极限竞速：地平线6 —— 本周季节赛值不值得做：奖励车是否车展买不到、稀有度、车展价，并可在本地读取存档比对；附当周活动限制原文、推荐车与 9 位调校码。">
<meta name="theme-color" content="#0d6c54">
<meta property="og:title" content="地平线 6 · 调校速查">
<meta property="og:description" content="本周季节赛值不值得做（奖励车是否买不到） + 当周限制原文与调校码">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230d6c54'/%3E%3Ctext x='32' y='46' font-family='system-ui,sans-serif' font-size='40' font-weight='700' fill='%23ffffff' text-anchor='middle'%3E6%3C/text%3E%3C/svg%3E">
<style>
:root{--bg:#f5f6f8;--card:#fff;--line:#e3e6ea;--tx:#1b2027;--tx2:#5b6472;--acc:#0d6c54}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 18px 70px}
header.top{padding:22px 26px;background:linear-gradient(135deg,#0d6c54,#12996f);color:#fff;border-radius:16px}
.htop{display:flex;gap:16px;align-items:flex-start;justify-content:space-between}
.htop h1{min-width:0}
.xnav{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:1px;padding:10px 15px;border-radius:11px;text-decoration:none;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.42);color:#fff;font-size:13.5px;font-weight:600;line-height:1.25;white-space:nowrap}
.xnav i{font-style:normal;font-size:11px;font-weight:400;opacity:.88}
.xnav:hover{background:rgba(255,255,255,.28)}
header.top h1{margin:0 0 6px;font-size:23px}
header.top p{margin:4px 0 0;opacity:.92;font-size:13px}
.kpis{display:flex;gap:22px;margin-top:14px;flex-wrap:wrap}
.kpi b{display:block;font-size:21px;line-height:1.2}.kpi span{font-size:12px;opacity:.85}
.tabs{display:flex;gap:8px;margin:18px 0 12px;flex-wrap:wrap}
.tabs button{font:600 14px/1 inherit;padding:10px 18px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--tx2);cursor:pointer}
.tabs button.on{background:var(--acc);border-color:var(--acc);color:#fff}
.pane{display:none}.pane.on{display:block}
.curbar{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 16px;margin-bottom:12px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
.curbar b{font-size:15px}.curbar .tag{background:#0d6c54;color:#fff;font-size:11px;padding:2px 8px;border-radius:20px}
.curbar .dt{color:var(--tx2);font-size:13px}
.evgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(342px,1fr));gap:10px}
.ev{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 14px}
.evh{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.evn{font-weight:700}.kind{color:var(--tx2);font-size:12px}
.kind.s{display:block;font-size:11px;margin-top:3px}
.limit{margin:9px 0 7px;padding:7px 10px;background:#fff8e8;border:1px solid #f0dfb4;border-radius:8px;font-size:13px}
.limit .lk{display:inline-block;font-size:10.5px;background:#a3600a;color:#fff;border-radius:4px;padding:1px 6px;margin-right:7px;vertical-align:1px}
.limit b{color:#7a4700}
.evm{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:12px;color:var(--tx2)}
.rec{background:#eef7f3;border-radius:6px;padding:2px 8px}
.rec b{color:#0a5742}
.pts{background:#f2ecfe;color:#6d34d6;border-radius:6px;padding:2px 8px;font-weight:600}
.rwd{background:#f3f5f8;border-radius:6px;padding:2px 8px}
.cdwrap{margin-left:auto}
.sub{margin-top:5px;font-size:12px;color:var(--tx2);padding-left:8px;border-left:2px solid #e3e6ea}
.note{margin-top:6px;font-size:12px;color:#8a6d1f;background:#fffdf3;border-radius:6px;padding:5px 8px}
.badge{font-size:11px;padding:2px 7px;border-radius:5px;font-weight:600;white-space:nowrap}
.hard{background:#fdecec;color:#b32d2d}.class{background:#fef4e2;color:#a3600a}
.single{background:#e9f0ff;color:#1f4fd8}.cond{background:#f2ecfe;color:#6d34d6}
.free{background:#f0f1f3;color:#7b8494}.trial{background:#e8f6f1;color:#0a6b52}
button.code{font:600 12.5px/1 ui-monospace,Consolas,monospace;letter-spacing:.5px;background:#eef7f3;border:1px solid #bfe0d4;color:#0a5742;border-radius:7px;padding:5px 9px;cursor:pointer}
button.code:hover{background:#dcefe7}
button.code.small{padding:3px 7px;font-size:12px}
button.code .cp{font-weight:400;font-size:10px;opacity:.6;margin-left:3px}
button.code.done{background:#0d6c54;color:#fff}
.bar{display:flex;gap:10px;align-items:center;margin:14px 0 10px;flex-wrap:wrap}
.bar input{flex:1;min-width:190px;padding:9px 12px;border:1px solid var(--line);border-radius:9px;font-size:13px}
.bar label{font-size:13px;color:var(--tx2);display:flex;gap:6px;align-items:center;background:var(--card);border:1px solid var(--line);padding:8px 12px;border-radius:9px;cursor:pointer}
details.wk,details.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:9px;overflow:hidden}
details.wk summary,details.sec summary{cursor:pointer;padding:12px 16px;display:flex;gap:14px;align-items:center;list-style:none;font-weight:600}
summary::-webkit-details-marker{display:none}
details.wk summary::before{content:"▸";color:#9aa3b0;font-weight:400;transition:.2s}
details.wk[open] summary::before{transform:rotate(90deg)}
.wkname{flex:1}.wkdate{color:var(--tx2);font-weight:400;font-size:12.5px}
.wkstat{color:#98a1af;font-weight:400;font-size:12px}
.tw{overflow-x:auto;border-top:1px solid var(--line)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#fafbfc;text-align:left;padding:8px 12px;font-weight:600;color:var(--tx2);font-size:12px;white-space:nowrap;border-bottom:1px solid var(--line)}
td{padding:8px 12px;border-bottom:1px solid #f0f2f4;vertical-align:top}
tbody tr:last-child td{border-bottom:none}
td.nm{font-weight:600}td.car{color:#0a4f3d}td.k{color:var(--tx2);white-space:nowrap}
td.tn{color:var(--tx2);font-size:12.5px}td.rw{color:var(--tx2);white-space:nowrap}
td.cen{text-align:center;font-weight:600;color:#0a5742}
.dash{color:#c6ccd4}
.notes{margin-top:24px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px}
.notes h3{margin:0 0 10px;font-size:15px}.notes li{margin:5px 0;color:var(--tx2);font-size:13px}
.notes b{color:var(--tx)}
.toast{position:fixed;left:50%;bottom:34px;transform:translateX(-50%) translateY(20px);background:#1b2027;color:#fff;padding:9px 18px;border-radius:9px;font-size:13px;opacity:0;pointer-events:none;transition:.22s}
.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
/* ── ⓪ 本周值不值得做 ── */
.vsum{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:12px;display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}
.vsum .vbig{font-size:19px;font-weight:700;line-height:1.3}
.vsum .vwhy{color:var(--tx2);font-size:13px;flex:1 1 240px;min-width:200px}
.v3{border-left:5px solid #b32d2d}.v2{border-left:5px solid #a3600a}
.v1{border-left:5px solid #7b8494}.v0{border-left:5px solid #d7dbe0}
.rgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(318px,1fr));gap:10px;margin-top:10px}
.rc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.rc.v3{border-left:5px solid #b32d2d}.rc.v2{border-left:5px solid #a3600a}
.rc.v1{border-left:5px solid #98a1af}.rc.v0{border-left:5px solid #d7dbe0;opacity:.75}
.rc h4{margin:0;font-size:15px}
.rhead{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.stars{color:#d1891b;font-size:13px;letter-spacing:1px;white-space:nowrap}
.pill{font-size:11px;padding:2px 8px;border-radius:20px;font-weight:600;white-space:nowrap}
.pill.no{background:#fdecec;color:#b32d2d}
.pill.yes{background:#f0f1f3;color:#7b8494}
.pill.unk{background:#f2ecfe;color:#6d34d6}
.rmeta{margin-top:7px;display:flex;gap:6px;flex-wrap:wrap;font-size:12.5px;color:var(--tx2)}
.rmeta span{background:#f3f5f8;border-radius:6px;padding:2px 8px}
.rwhy{margin-top:7px;font-size:12.5px;color:#7a4700;background:#fff8e8;border-radius:7px;padding:6px 9px}
.rev{margin-top:6px;font-size:12px;color:var(--tx2)}
.own{margin-top:7px;font-size:12.5px;font-weight:600}
.own.y{color:#0a5742}.own.n{color:#98a1af}
.btn{font:600 13px/1 inherit;padding:9px 16px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--tx);cursor:pointer}
.btn.pri{background:var(--acc);border-color:var(--acc);color:#fff}
.btn:hover{border-color:#c3cad3}
.cnt{font-size:12.5px;color:var(--tx2);margin-left:2px}
.scan{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0 4px;font-size:13px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.scan .warn{color:#8a6d1f;background:#fffdf3;border-radius:8px;padding:8px 11px;font-size:12.5px;flex:1 1 100%;margin:0}
.scan .kv{display:flex;gap:16px;flex-wrap:wrap}
.scan .kv b{font-size:16px;display:block}
.scan .kv span{font-size:11.5px;color:var(--tx2)}
.tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}
.tag2{font-size:11.5px;background:#eef7f3;color:#0a5742;border-radius:6px;padding:2px 7px}
/* ── 移动端适配 ── */
@media (max-width:720px){
.wrap{padding:14px 12px 56px}
header.top{padding:18px 18px;border-radius:14px}
.htop{flex-direction:column;align-items:stretch;gap:10px}
.xnav{flex-direction:row;justify-content:center;gap:7px;padding:9px 13px}
header.top h1{font-size:19px;line-height:1.35}
header.top p{font-size:12px}
.kpis{gap:14px 20px;margin-top:12px}
.kpi b{font-size:18px}
.tabs{position:sticky;top:0;z-index:20;background:var(--bg);gap:6px;padding:9px 0;margin:8px 0;display:grid;grid-template-columns:repeat(2,1fr)}
.tabs button{width:100%;padding:10px 6px;font-size:12.5px;text-align:center;white-space:nowrap}
.tl{display:none}
.curbar{padding:11px 13px;gap:9px;margin-bottom:10px}
.evgrid{grid-template-columns:1fr;gap:9px}
.rgrid{grid-template-columns:1fr;gap:9px}
.vsum{padding:12px 14px}.vsum .vbig{font-size:17px}
.ev{padding:12px 13px}
.cdwrap{margin-left:0;width:100%}
.limit{margin:8px 0 6px;padding:7px 9px;font-size:12.5px}
.bar{gap:8px;margin:12px 0 9px}
.bar input{min-width:0;flex:1 1 100%}
.bar label{flex:1 1 auto;justify-content:center;padding:8px 10px}
details.wk summary,details.sec summary{padding:11px 13px;gap:8px;flex-wrap:wrap}
.wkname{flex:1 1 100%}
.tw{-webkit-overflow-scrolling:touch}
table{font-size:12.5px}
th,td{padding:7px 9px}
.notes{padding:15px 16px;margin-top:18px}
.notes li{font-size:12.5px}
button.code{padding:6px 10px}
}
@media (max-width:400px){
header.top h1{font-size:17px}
.kpi b{font-size:16px}.kpi span{font-size:11px}
.tabs button{font-size:12px;padding:9px 2px}
th,td{padding:6px 7px}
}
</style></head><body><div class="wrap">
<header class="top">
  <div class="htop">
    <h1>地平线 6 · 本周值不值得做</h1>
    <a class="xnav" href="__TOYURL__" target="_blank" rel="noopener">车辆数据库<i>站外 · B站 ↗</i></a>
  </div>
  <p>本周奖励车<b>是否车展买不到</b> · 稀有度 · 车展价 · 可在本地读存档比对「我有没有」<br>
     附：当周赛事限制原文 + 推荐车 + 调校码 · 季节赛限定车 · 各模式车辆榜 · 单文件离线可用</p>
  <div class="kpis">
    <div class="kpi"><b>__NVAL__</b><span>本周奖励车（__NHARD__ 台买不到）</span></div>
    <div class="kpi"><b>__NCUR__</b><span>当周活动条目</span></div>
    <div class="kpi"><b>__NW__</b><span>个赛季周（含历史）</span></div>
    <div class="kpi"><b>__NCARS__</b><span>台各模式上榜车</span></div>
    <div class="kpi"><b>__TS__</b><span>数据快照时间</span></div>
  </div>
</header>
<div id="tabanchor"></div>
<div class="tabs">
  <button class="on" data-p="p0">⓪ 值不值得做<span class="tl">（本周奖励）</span></button>
  <button data-p="p1">① 本周赛事<span class="tl">（含限制原文）</span></button>
  <button data-p="p2">② 季节赛限定车<span class="tl">（__NW__ 周历史）</span></button>
  <button data-p="p3">③ 各模式车辆榜</button>
</div>

<div class="pane on" id="p0">
__VALBODY__
</div>

<div class="pane" id="p1">
  <div class="curbar">
    <b>__CURTITLE__</b><span class="tag">当周有效</span><span class="dt">__CURDATE__</span>
    <span class="dt">· 季节每周四晚 22:30（北京时间）更新</span>
  </div>
  <div class="bar"><input id="q1" placeholder="搜索活动名 / 限制 / 车名 / 调校码 …"></div>
  <div class="evgrid">__WEEKBODY__</div>
  __COMMTBL__
</div>

<div class="pane" id="p2">
  <div class="bar"><input id="q2" placeholder="搜索车名 / 活动名 / 调校师 / 调校码 …">
    <label><input type="checkbox" id="onlyLock"> 只看有限定车辆</label></div>
  __WEEKSBODY__
  <details class="wk"><summary><span class="wkname">按车型索引 · 反复被季节赛用到的车</span>
   <span class="wkstat">共 __NCIDX__ 台（列出现 ≥2 次的）</span></summary>
   <div class="tw"><table><thead><tr><th>车辆</th><th>次数</th><th>活动类型</th>
   <th>最新调校师</th><th>最新调校码</th><th>最近一次</th></tr></thead><tbody>__CARROWS__</tbody>
   </table></div></details>
</div>

<div class="pane" id="p3">
  <div class="bar"><input id="q3" placeholder="搜索车名 / 制造商 / 调校师 …"></div>
  __GROUPSBODY__
</div>

<div class="notes">
  <h3>怎么用这份表</h3>
  <ul>
    <li><b>⓪ 值不值得做</b>：先看<b>「买不到」</b>——那台车的获取途径里没有「车展」，
        也就是这周不拿、之后就得靠抽奖碰运气或等复刻。三颗星＝只能靠季节赛事/车房宝物/秘藏座驾拿到；
        两颗星＝车展买不到或档位很高（传奇／极限竞速特别版）；一颗星＝车展随时能买，不急。</li>
    <li><b>「我有没有」这一列怎么来的</b>：FH6 的完整车库清单在存档里是<b>加密</b>的，
        社区目前没有公开的解密实现，所以这一列<b>不读加密内容</b>。它读的是存档里两处不加密的地方——
        顶层的存档摘要（写明了车库车辆总数）与 <code>Livery_&lt;序号&gt;/Tuning_&lt;序号&gt;</code> 目录名。
        因此它只能标出<b>您涂装过或调校过的车</b>，其余显示「未见」——「未见」<b>不等于没有</b>，只是这份存档没提供证据。</li>
    <li><b>读档会改变结论</b>：存档里确认您已经有的奖励车，星级会<b>下调</b>（已有的重复车不太值得再跑一趟）；
        「未见」的车<b>不做任何上调</b>——因为「未见」不等于没有。顶部那句结论会跟着重算。</li>
    <li>存档全程在您浏览器内读取，<b>不上传任何内容</b>，也不写入存档目录。</li>
    <li><b>① 本周赛事</b>里每张卡片的黄色块是<b>游戏内的限制原文</b>（如「皮卡和四轮驱动车 · B 600」），
        照它选车就不会被拦在赛外；蓝色「推荐」徽标来自中文／英文攻略实测验证过的调校师。</li>
    <li><b>红色「必须用」</b>＝每周挑战，必须拥有并驾驶指定那一台车（通常是 4 个步骤按顺序做完）。</li>
    <li><b>橙色「按类别」</b>＝终极考验 / 季节锦标赛，按车辆类别 + 性能等级限车。</li>
    <li><b>蓝色「推荐车」</b>＝危险标志 / 测速区间 / 测速照相 / 拓荒者门 / 漂移冲分赛，
        游戏本身不限具体车型（但可能限国家或等级），表里给的是能一把过的车 + 调校。</li>
    <li><b>调校码是车型锁的</b>：年份差一位就搜不到。装的时候走「载入调校 → 共享调校 → 输入 9 位码」。</li>
    <li><b>② 季节赛限定车</b>可以当备车清单用：跨周反复被指定的车（如本田 Beat、路虎 Defender）值得常驻车库。</li>
    <li><b>③ 各模式车辆榜</b>是社区维护的 Meta 榜，标了竞争力档位（Meta+ / Meta / T0.5…）与推荐调校师，
        想自己配车时按榜单找车、再按调校师名搜调校。</li>
  </ul>
  <h3 style="margin-top:16px">数据来源与可信度</h3>
  <ul>
    <li><b>当周限制原文</b>：vgover（电玩帮）季节赛攻略，逐条对照英文来源 TheXboxHub 交叉验证；
        两者给的推荐车不同，属于不同调校师的方案，均可用。</li>
    <li><b>季节赛限定车 / 各模式车辆榜</b>：腾讯文档「地平线6线上车辆调校推荐」，逐格解出（非抄录）。</li>
    <li>原表个别单元格有笔误（如「调教代码」、日期漏「日」字、某周日期区间偏长），本页按原样保留，未做臆改。</li>
    <li><b>奖励车的稀有度与获取途径</b>：社区库 Nova's Autoshow（<a href="https://forza.nerdyderg.com" target="_blank" rel="noopener">forza.nerdyderg.com</a>）；
        中文车名与车辆序号取自 B站小玩具「<a href="https://www.bilibili.com/toy/forzahorizon6/index.html" target="_blank" rel="noopener">地平线六车辆数据库</a>」（作者 Dr.Hydra）。两者均非官方数据。</li>
    <li>「奖励车是不是车展买不到」是按获取途径字段判断的，<b>游戏版本更新后可能变化</b>；以游戏内「车展」实际是否在售为准。</li>
    <li>数据快照：__TS_FULL__　·　页面由 <code>scripts/update.py</code> 自动生成。</li>
  </ul>
</div>
</div><div class="toast" id="toast">已复制</div>
<script>window.__CAT__=__CATJSON__;</script>
<script>
document.addEventListener('click',function(ev){
  var b=ev.target.closest('button.code'); if(!b) return;
  var t=b.getAttribute('data-c');
  function fb(){
    var s=document.createElement('textarea');
    s.value=t; s.setAttribute('readonly',''); s.style.position='fixed'; s.style.top='-1000px';
    document.body.appendChild(s); s.select(); s.setSelectionRange(0,t.length);
    try{document.execCommand('copy')}catch(e){}
    document.body.removeChild(s);
  }
  function done(){
    var o=b.innerHTML; b.classList.add('done'); b.innerHTML='已复制 ✓';
    var tt=document.getElementById('toast'); tt.classList.add('on');
    setTimeout(function(){b.classList.remove('done'); b.innerHTML=o; tt.classList.remove('on')},1100);
  }
  if(navigator.clipboard&&window.isSecureContext){
    navigator.clipboard.writeText(t).then(done,function(){fb();done()});
  }else{fb();done()}
});
document.querySelectorAll('.tabs button').forEach(function(x){
  x.addEventListener('click',function(){
    document.querySelectorAll('.tabs button').forEach(function(y){y.classList.remove('on')});
    document.querySelectorAll('.pane').forEach(function(y){y.classList.remove('on')});
    x.classList.add('on'); document.getElementById(x.getAttribute('data-p')).classList.add('on');
    var a=document.getElementById('tabanchor');
    if(a){var t=a.getBoundingClientRect().top+window.scrollY;
      if(window.scrollY>t) window.scrollTo({top:t,behavior:'smooth'});}
  });
});
function bindSearch(qid, scope, lockId){
  var q=document.getElementById(qid); if(!q) return;
  var lk=lockId?document.getElementById(lockId):null;
  function apply(){
    var kw=q.value.trim().toLowerCase(), on=lk&&lk.checked;
    document.querySelectorAll(scope+' details.wk').forEach(function(d){
      var vis=0;
      d.querySelectorAll('tbody tr').forEach(function(tr){
        var ok=(!kw||(tr.getAttribute('data-txt')||'').indexOf(kw)>=0)&&(!on||tr.getAttribute('data-limit')==='1');
        tr.style.display=ok?'':'none'; if(ok)vis++;
      });
      d.style.display=vis?'':'none'; if(kw&&vis) d.open=true;
    });
    var vn=0;
    document.querySelectorAll(scope+' .ev, '+scope+' .rc').forEach(function(c){
      var ok=!kw||(c.getAttribute('data-txt')||'').indexOf(kw)>=0;
      c.style.display=ok?'':'none'; if(ok&&c.className.indexOf('rc')>=0)vn++;
    });
    var cn=document.getElementById('c'+qid.slice(1));
    if(cn) cn.textContent=kw?('筛出 '+vn+' 台'):'';
  }
  q.addEventListener('input',apply); if(lk) lk.addEventListener('change',apply);
}
bindSearch('q0','#p0'); bindSearch('q1','#p1'); bindSearch('q2','#p2','onlyLock'); bindSearch('q3','#p3');
// ── 存档体检：完全在本地读，一个字节都不外传 ──
(function(){
  var pick=document.getElementById('scan-pick'), inp=document.getElementById('scan-file');
  if(!pick||!inp) return;
  var out=document.getElementById('scan-out'), box=document.getElementById('scan');
  var RE_ID=/(?:^|[/])(?:Livery|Tuning)_([0-9]+)_/i, RE_META=/[0-9]{9,}_[0-9A-F]{4,}[.]json$/i;
  function b64u(b){
    try{var s=atob((b||'').replace(/[^A-Za-z0-9+/=]/g,'')),u=new Uint8Array(s.length);
      for(var i=0;i<s.length;i++)u[i]=s.charCodeAt(i);
      return new TextDecoder('utf-8').decode(u);}catch(e){return '';}
  }
  function esc(x){return String(x).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  pick.addEventListener('click',function(){inp.click();});
  inp.addEventListener('change',function(){
    var fs=inp.files; if(!fs||!fs.length) return;
    var ids={}, metaFile=null, i, n;
    for(i=0;i<fs.length;i++){
      var p=fs[i].webkitRelativePath||fs[i].name, m=RE_ID.exec(p);
      if(m) ids[parseInt(m[1],10)]=1;
      if(RE_META.test(p)) metaFile=fs[i];
    }
    var idList=Object.keys(ids).map(Number);
    function render(txt){
      var CAT=window.__CAT__||{}, known=[], lines=[];
      idList.sort(function(a,b){return a-b;});
      for(var k=0;k<idList.length;k++) if(CAT[idList[k]]) known.push(CAT[idList[k]]);
      var cards=document.querySelectorAll('.rc[data-cid]');
      for(var c=0;c<cards.length;c++){
        var cid=parseInt(cards[c].getAttribute('data-cid'),10);
        var el=cards[c].querySelector('.own');
        if(!el){el=document.createElement('div');el.className='own';cards[c].appendChild(el);}
        var st=parseInt(cards[c].getAttribute('data-star'),10)||0;
        var se=cards[c].querySelector('.stars');
        if(ids[cid]){
          var ns=Math.max(0,st-2);
          el.className='own y';
          el.textContent=(st>0&&ns<st)
            ? '★ 存档里确认您有这台（优先级已下调）'
            : '★ 存档里确认您有这台';
          if(se) se.textContent='★'.repeat(ns)+'☆'.repeat(3-ns);
          cards[c].setAttribute('data-star-eff',ns);
        }else{
          el.className='own n';
          el.textContent='· 存档里未见这台（≠ 没有，见下方说明）';
          cards[c].setAttribute('data-star-eff',st);
        }
      }
      // 按「排除掉您已有的」重算顶部结论
      (function(){
        var best=0,nHard=0,nCar=0,nOwned=0;
        var cs=document.querySelectorAll('.rc[data-cid]');
        for(var q=0;q<cs.length;q++){
          nCar++;
          var owned=!!ids[parseInt(cs[q].getAttribute('data-cid'),10)];
          var eff=parseInt(cs[q].getAttribute('data-star-eff'),10)||0;
          if(owned)nOwned++;
          if(eff>best)best=eff;
          if(!owned&&cs[q].getAttribute('data-tag')==='买不到')nHard++;
        }
        var vs=document.getElementById('vsum'); if(!vs||!nCar) return;
        var big,why;
        if(best>=3){big='值得做';
          why='排除掉您已有的之后，还有 <b>'+nHard+' 台车展买不到</b>——错过这周就得靠抽奖碰运气或等复刻。';}
        else if(best===2){big='可以做，但不是刚需';
          why='排除掉您已有的之后，剩下的车车展都买得到，但档位／价位不低，顺手做掉等于白拿一笔。';}
        else if(nOwned===nCar){big='本周可以跳过';
          why='本周 '+nCar+' 台奖励车，<b>存档里都确认您已经有了</b>——做不做都行。';}
        else {big='可以不急';
          why='剩下的奖励车<b>都能在车展直接买到</b>，随手做拿个折扣即可，不做也不损失。';}
        vs.className='vsum v'+Math.min(3,best);
        vs.querySelector('.vbig').textContent=big;
        vs.querySelector('.vwhy').innerHTML=why
          +'<br><span style="font-size:12px">（此结论已按您存档里确认已有的车做了下调；「未见」的车不参与下调。）</span>';
      })();
      var head='';
      if(txt){
        var flat='',ci=0; for(ci=0;ci<txt.length;ci++){var ch=txt.charCodeAt(ci);
          flat+=(ch===10||ch===13||ch===9)?' · ':txt.charAt(ci);}
        head='<div class="warn"><b>存档摘要</b>（这段是明文，直接读到的）：'+esc(flat)+'</div>';
      } else {
        head='<div class="warn">没读到存档摘要——请选到 <code>pgs</code> 或它下面任意一层（选到 <code>ContainersRoot</code> 也可以）。</div>';
      }
      var kv='<div class="kv">'
        +'<div><b>'+idList.length+'</b><span>识别到的车辆序号</span></div>'
        +'<div><b>'+known.length+'</b><span>其中能在车型库对上</span></div>'
        +'<div><b>'+fs.length+'</b><span>读取的文件数</span></div></div>';
      var tags = known.length
        ? '<div class="tags">'+known.slice(0,60).map(function(x){return '<span class="tag2">'+esc(x)+'</span>';}).join('')
          +(known.length>60?'<span class="tag2">…还有 '+(known.length-60)+' 台</span>':'')+'</div>'
        : '';
      out.innerHTML = head + kv
        + '<p class="warn">能识别出「您涂装过 / 调校过的车」，是因为存档里 <code>Livery_&lt;序号&gt;</code>、'
        + '<code>Tuning_&lt;序号&gt;</code> 这些目录名用的是不加密的车辆序号。完整车库清单在 '
        + '<code>C_ProfileData</code> 里且是<b>加密</b>的，本页不读它——所以「未见」<b>不等于您没有</b>。</p>'
        + tags;
      box.hidden=false;
    }
    if(metaFile){ metaFile.text().then(function(t){
        var sd=''; try{ sd=b64u(JSON.parse(t).Context.SaveDescription); }catch(e){}
        render(sd);
      }, function(){ render(''); });
    } else { render(''); }
  });
})();

// 支持用 #p0/#p1/#p2/#p3 直接定位标签页
(function(){var h=location.hash.replace('#','');
 if(h){var b=document.querySelector('.tabs button[data-p="'+h+'"]'); if(b) b.click();}})();
</script></body></html>"""

    if cat is None:
        cat = fh6_catalog.Catalog(fh6_catalog.fetch_catalog(verbose=False))
    val_head, val_body, n_val, n_hard = value_pane(nw, cat, guide)
    cat_names = json.dumps(
        {str(c["id"]): (c.get("short") or c.get("model") or "")
         for c in cat.cars if isinstance(c.get("id"), int)},
        ensure_ascii=False).replace("<", "\\u003c")

    HTML = (HTML.replace("__NCUR__", str(len(nw)))
                .replace("__NW__", str(len(weeks)))
                .replace("__NCARS__", str(n_cars))
                .replace("__TS__", esc(ts))
                .replace("__TS_FULL__", esc(ts))
                .replace("__TOYURL__", TOY_URL)
                .replace("__CURTITLE__", esc(cur_title))
                .replace("__CURDATE__", esc(guide.get("date") or cur.get("date", "")))
                .replace("__WEEKBODY__", week_body)
                .replace("__COMMTBL__", comm_tbl)
                .replace("__WEEKSBODY__", weeks_body)
                .replace("__NCIDX__", str(len(cars)))
                .replace("__CARROWS__", car_rows)
                .replace("__GROUPSBODY__", groups_body)
                .replace("__VALBODY__", val_head + val_body)
                .replace("__CATJSON__", cat_names)
                .replace("__NVAL__", str(n_val))
                .replace("__NHARD__", str(n_hard)))
    return HTML, nw, cars


# ─────────────── Markdown ───────────────
def build_md(guide, weeks, groups, ts, nw):
    md = io.StringIO()
    md.write("# 地平线 6 · 调校速查\n\n")
    md.write("> 数据快照：%s\n> 当周限制原文来自 vgover（中文）／TheXboxHub（英文）交叉核对；"
             "季节赛与车辆榜来自腾讯文档逐格解出\n\n" % ts)
    md.write("> 车辆数据库（B站 · Dr.Hydra）：%s\n\n" % TOY_URL)
    md.write("## ⓪ 本周值不值得做\n\n")
    md.write("| 奖励车 | 星级 | 结论 | 稀有度 | 获取途径 | 车展价 | 来自 |\n|---|---|---|---|---|---|---|\n")
    try:
        _cat = fh6_catalog.Catalog(fh6_catalog.fetch_catalog(verbose=False))
        for _it in fh6_catalog.reward_items(nw):
            _c = _cat.match_name(_it["text"])
            if _c:
                _st, _tag, _ = _cat.verdict(_c)
                md.write("| %s | %s | %s | %s | %s | %s | %s |\n" % (
                    _cat.name(_c), "★" * _st, _tag, _cat.rarity(_c),
                    "／".join(_cat.sources(_c)), "{:,}".format(_c.get("cost") or 0),
                    _it["kind"]))
            else:
                md.write("| %s |  | 未能定位 |  |  |  | %s |\n" % (
                    _it["text"].replace("|", "/"), _it["kind"]))
    except Exception as _e:
        md.write("| （目录抓取失败：%s） |  |  |  |  |  |  |\n" % _e)
    md.write("\n")
    md.write("## ① 本周赛事（%s %s，%s）\n\n"
             % (guide.get("series", ""), guide.get("season", ""), guide.get("date", "")))
    md.write("| 类型 | 活动 | 游戏限制原文 | 推荐车 | 调校码 | 分数 | 奖励 |\n|---|---|---|---|---|---|---|\n")
    for e in nw:
        md.write("| %s | %s | %s | %s | %s | %s | %s |\n" % (
            e["kind"], e["name"].replace("|", "/"), e["limit"].replace("|", "/"),
            e["rec_car"].replace("|", "/"), e["code"] or "—",
            e["points"], e["reward"].replace("|", "/")))
    md.write("\n")
    md.write("## ② 季节赛限定车（全 %d 周）\n\n" % len(weeks))
    for i, w in enumerate(weeks):
        md.write("\n### %s（%s）%s\n\n" % (w["title"], w["date"], " ← 当周" if i == 0 else ""))
        md.write("| 类型 | 活动 | 限定车辆/条件 | 调校师 | 调校码 | 奖励 |\n|---|---|---|---|---|---|\n")
        for e in w["events"]:
            md.write("| %s | %s | %s | %s | %s | %s |\n" % (
                e["type"], e["name"].replace("|", "/"), e["car"].replace("|", "/"),
                e["tuner"], e["code"] or "—", e["reward"].replace("|", "/")))
    md.write("\n## ③ 各模式车辆榜\n\n")
    for g in groups:
        es = [e for e in g["entries"] if e.get("车辆型号")]
        if not es:
            continue
        md.write("\n### %s（%d 台）\n\n" % (g["name"], len(es)))
        md.write("| 车辆 | 竞争力 | 轮胎 | 驱动 | 难度 | 调校师 |\n|---|---|---|---|---|---|\n")
        for e in es:
            md.write("| %s | %s | %s | %s | %s | %s |\n" % (
                e.get("车辆型号", "").replace("|", "/"), e.get("竞争力", ""),
                e.get("轮胎", ""), e.get("驱动", ""), e.get("难度", ""),
                "/".join(e.get("调校师") or [])[:60]))
    return md.getvalue()


def main():
    guide = load("week_guide.json", {})
    weeks = load("weeks.json", [])
    groups = load("groups.json", [])
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        cat = fh6_catalog.Catalog(fh6_catalog.fetch_catalog(verbose=True))
    except Exception as ex:
        print("  [目录] 抓取失败，改用本地缓存：%r" % (ex,))
        cat = fh6_catalog.Catalog(json.load(io.open(os.path.join(DATA, "catalog.json"), encoding="utf-8")))
    html_text, nw, cars = build_html(guide, weeks, groups, ts, cat)
    out_html = os.path.join(BASE, "FH6-调校速查.html")
    open(out_html, "w", encoding="utf-8").write(html_text)

    # 同步一份到站点目录（供发布为在线网站 / GitHub Pages，根路径即主页）
    # 目录名用 docs 是 GitHub Pages 的约定：仓库设置里选「main 分支 /docs 文件夹」即可上线
    site = os.path.join(BASE, "docs")
    os.makedirs(site, exist_ok=True)
    open(os.path.join(site, "index.html"), "w", encoding="utf-8").write(html_text)
    md = build_md(guide, weeks, groups, ts, nw)
    out_md = os.path.join(BASE, "FH6-调校速查.md")
    open(out_md, "w", encoding="utf-8").write(md)
    print("OK  html=%.0f KB  md=%.0f KB | 当周 %d 项 · %d 周 · %d 台车 · 目录 %d 台"
          % (len(html_text) / 1024, len(md) / 1024, len(nw), len(weeks),
             sum(len([e for e in g["entries"] if e.get("车辆型号")]) for g in groups),
             len(cat.cars)))
    return out_html


if __name__ == "__main__":
    main()
