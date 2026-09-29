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
def build_html(guide, weeks, groups, ts):
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
<title>地平线 6 · 调校速查（本周赛事 / 季节赛限定车 / 各模式车辆榜）</title>
<meta name="description" content="极限竞速：地平线6 调校速查 —— 当周季节赛事的游戏内车辆限制原文、推荐车与 9 位调校码，18 周季节赛限定车历史，14 个组别的各模式车辆榜。数据逐周自动更新。">
<meta name="theme-color" content="#0d6c54">
<meta property="og:title" content="地平线 6 · 调校速查">
<meta property="og:description" content="当周赛事限制原文 + 推荐车 + 调校码 · 季节赛限定车 · 各模式车辆榜">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230d6c54'/%3E%3Ctext x='32' y='46' font-family='system-ui,sans-serif' font-size='40' font-weight='700' fill='%23ffffff' text-anchor='middle'%3E6%3C/text%3E%3C/svg%3E">
<style>
:root{--bg:#f5f6f8;--card:#fff;--line:#e3e6ea;--tx:#1b2027;--tx2:#5b6472;--acc:#0d6c54}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.6 "Microsoft YaHei","PingFang SC",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 18px 70px}
header.top{padding:22px 26px;background:linear-gradient(135deg,#0d6c54,#12996f);color:#fff;border-radius:16px}
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
/* ── 移动端适配 ── */
@media (max-width:720px){
.wrap{padding:14px 12px 56px}
header.top{padding:18px 18px;border-radius:14px}
header.top h1{font-size:19px;line-height:1.35}
header.top p{font-size:12px}
.kpis{gap:14px 20px;margin-top:12px}
.kpi b{font-size:18px}
.tabs{position:sticky;top:0;z-index:20;background:var(--bg);gap:6px;padding:9px 0;margin:8px 0;display:grid;grid-template-columns:repeat(3,1fr)}
.tabs button{width:100%;padding:10px 4px;font-size:13px;text-align:center;white-space:nowrap}
.tl{display:none}
.curbar{padding:11px 13px;gap:9px;margin-bottom:10px}
.evgrid{grid-template-columns:1fr;gap:9px}
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
  <h1>地平线 6 · 调校速查</h1>
  <p>当周赛事的<b>游戏内限制原文</b> + 推荐车 + 调校码 · 季节赛限定车 · 各模式车辆榜<br>
     数据逐格解出社区维护表，并交叉核对中文／英文攻略 · 单文件离线可用</p>
  <div class="kpis">
    <div class="kpi"><b>__NCUR__</b><span>当周活动条目</span></div>
    <div class="kpi"><b>__NW__</b><span>个赛季周（含历史）</span></div>
    <div class="kpi"><b>__NCARS__</b><span>台各模式上榜车</span></div>
    <div class="kpi"><b>__TS__</b><span>数据快照时间</span></div>
  </div>
</header>
<div id="tabanchor"></div>
<div class="tabs">
  <button class="on" data-p="p1">① 本周赛事<span class="tl">（含限制原文）</span></button>
  <button data-p="p2">② 季节赛限定车<span class="tl">（__NW__ 周历史）</span></button>
  <button data-p="p3">③ 各模式车辆榜</button>
</div>

<div class="pane on" id="p1">
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
    <li>数据快照：__TS_FULL__　·　页面由 <code>scripts/update.py</code> 自动生成。</li>
  </ul>
</div>
</div><div class="toast" id="toast">已复制</div>
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
    document.querySelectorAll(scope+' .ev').forEach(function(c){
      var ok=!kw||(c.getAttribute('data-txt')||'').indexOf(kw)>=0;
      c.style.display=ok?'':'none';
    });
  }
  q.addEventListener('input',apply); if(lk) lk.addEventListener('change',apply);
}
bindSearch('q1','#p1'); bindSearch('q2','#p2','onlyLock'); bindSearch('q3','#p3');
// 支持用 #p1/#p2/#p3 直接定位标签页
(function(){var h=location.hash.replace('#','');
 if(h){var b=document.querySelector('.tabs button[data-p="'+h+'"]'); if(b) b.click();}})();
</script></body></html>"""

    HTML = (HTML.replace("__NCUR__", str(len(nw)))
                .replace("__NW__", str(len(weeks)))
                .replace("__NCARS__", str(n_cars))
                .replace("__TS__", esc(ts))
                .replace("__TS_FULL__", esc(ts))
                .replace("__CURTITLE__", esc(cur_title))
                .replace("__CURDATE__", esc(guide.get("date") or cur.get("date", "")))
                .replace("__WEEKBODY__", week_body)
                .replace("__COMMTBL__", comm_tbl)
                .replace("__WEEKSBODY__", weeks_body)
                .replace("__NCIDX__", str(len(cars)))
                .replace("__CARROWS__", car_rows)
                .replace("__GROUPSBODY__", groups_body))
    return HTML, nw, cars


# ─────────────── Markdown ───────────────
def build_md(guide, weeks, groups, ts, nw):
    md = io.StringIO()
    md.write("# 地平线 6 · 调校速查\n\n")
    md.write("> 数据快照：%s\n> 当周限制原文来自 vgover（中文）／TheXboxHub（英文）交叉核对；"
             "季节赛与车辆榜来自腾讯文档逐格解出\n\n" % ts)
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
    html_text, nw, cars = build_html(guide, weeks, groups, ts)
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
    print("OK  html=%.0f KB  md=%.0f KB | 当周 %d 项 · %d 周 · %d 台车"
          % (len(html_text) / 1024, len(md) / 1024, len(nw), len(weeks),
             sum(len([e for e in g["entries"] if e.get("车辆型号")]) for g in groups)))
    return out_html


if __name__ == "__main__":
    main()
