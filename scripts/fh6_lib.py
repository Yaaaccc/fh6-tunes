# -*- coding: utf-8 -*-
"""
FH6 调校速查 · 数据获取与解析库

两个数据源：
  1) 腾讯文档「地平线6线上车辆调校推荐」—— 免登录，匿名可读（实测无需 cookie）
     抓 opendoc 接口 → related_sheet(zlib+base64) → protobuf 网格
  2) vgover（电玩帮）当周季节赛攻略 —— 服务端渲染，直接抓 HTML
     提供**游戏内类别限制原文**（如「类型-皮卡和四轮驱动车 / 等级 B 600」）

用法：
    python fh6_lib.py fetch        # 抓取全部数据源 → data/
    python fh6_lib.py selftest     # 用本地样本自检解析器
"""
import os, re, json, time, base64, zlib, html as _html
import urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")

DOC_ID = "DYWZVRWR0dnh3aHhZ"
SHEET_URL = "https://docs.qq.com/sheet/" + DOC_ID

TABS = [
    ("o07r66", "引言"),
    ("zq302z", "季节赛 每周更新"),
    ("wo9pik", "新车调校速递"),
    ("hyckqg", "R 998公路"),
    ("0qjakc", "S2 900公路"),
    ("oamijc", "S1 800公路"),
    ("cub4i9", "S1 800泥地"),
    ("65s65w", "S1 800越野"),
    ("mmc7rv", "A 700公路"),
    ("1gx397", "A 700泥地"),
    ("w6mrz3", "A 700越野"),
    ("noe86s", "B 600公路"),
    ("ga0lb0", "B 600泥地"),
    ("vwauu6", "B 600越野"),
    ("jkbmtz", "C 500公路"),
    ("zok2jk", "C 500泥地"),
]


# ─────────────────────────── 网络 ───────────────────────────
def http_get(url, referer=None, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if referer:
        req.add_header("Referer", referer)
    return urllib.request.urlopen(req, timeout=timeout).read()


def fetch_tencent_tab(tab, max_row=1400):
    """抓一个分页，返回原始 JSONP 文本。免登录、无需 cookie。"""
    url = ("https://docs.qq.com/dop-api/opendoc?tab=%s&u=&noEscape=1&enableSmartsheetSplit=1"
           "&startrow=0&endrow=60&needSheetState=1&sliceStates=1&block_start_col=0"
           "&block_end_col=31&block_start_row=0&block_end_row=%d&id=%s&normal=1"
           "&outformat=1&wb=1&nowb=0&callback=cb&xsrf=&t=%d"
           % (tab, max_row, DOC_ID, int(time.time() * 1000) % 100000000))
    return http_get(url, referer=SHEET_URL).decode("utf-8", errors="replace")


def fetch_vgover(url):
    return http_get(url, referer="https://www.vgover.com/").decode("utf-8", errors="replace")


# ─────────────────── protobuf 极简解析 ───────────────────
def _varint(buf, i):
    shift = 0; val = 0
    while True:
        b = buf[i]; i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7


def pb_parse(buf, start=0, end=None):
    if end is None:
        end = len(buf)
    out = []; i = start
    while i < end:
        tag, i = _varint(buf, i)
        f, w = tag >> 3, tag & 7
        if w == 0:
            v, i = _varint(buf, i); out.append((f, 0, v))
        elif w == 2:
            ln, i = _varint(buf, i); out.append((f, 2, buf[i:i + ln])); i += ln
        elif w == 5:
            out.append((f, 5, buf[i:i + 4])); i += 4
        elif w == 1:
            out.append((f, 1, buf[i:i + 8])); i += 8
        else:
            raise ValueError("bad wire %d at %d" % (w, i))
    return out


def parse_sheet_grid(raw_text):
    """JSONP 原文 → {(row, col): text} 网格 + 字符串池。

    结构要点（2026-09 实测）：
      blob → f1 → payload(含多个 f5 块，块内 f1=kind)
        kind=18 且最大的块 = 真实数据 → f19
          f19.f6  = 单元格：f1=行号, f2=列号, f3.f1=类型标记(4=文本),
                    f3.f2={f1:N} → 字符串池索引 N（**f3.f4 是陷阱，不是值**）
          f19.f5  = 字符串池：每条 {f1: string}
    """
    m = re.match(r"^\s*\w+\((.*)\);?\s*$", raw_text, re.S)
    if not m:
        raise RuntimeError("不是合法的 JSONP 响应")
    data = json.loads(m.group(1))
    t0 = data["clientVars"]["collab_client_vars"]["initialAttributedText"]["text"][0]
    blob = zlib.decompress(base64.b64decode(t0["block_datas"][0]["related_sheet"]))
    payload = pb_parse(blob)[0][2]

    data_block = None
    for v in sorted([v for f, w, v in pb_parse(payload) if f == 5 and w == 2],
                    key=len, reverse=True):
        try:
            if any(ff == 19 for ff, _, _ in pb_parse(v)):
                data_block = v
                break
        except Exception:
            continue
    if data_block is None:
        raise RuntimeError("未找到 kind=18 数据块")

    subs = pb_parse([v for f, w, v in pb_parse(data_block) if f == 19][0])

    pool = []
    for the_f, w, v in pb_parse([v for f, w, v in subs if f == 5][0]):
        txt = ""
        for a, b, c in pb_parse(v):
            if a == 1 and b == 2:
                txt = c.decode("utf-8", errors="replace")
        pool.append(txt)

    grid = {}
    for c in [c for f, w, c in subs if f == 6]:
        ff = pb_parse(c)
        rowv = [v for f, w, v in ff if f == 1]
        colv = [v for f, w, v in ff if f == 2]
        row = rowv[0] if rowv else 0
        col = colv[0] if colv else 0
        pay = [v for f, w, v in ff if f == 3]
        typ = None; idx = 0
        if pay:
            for a, b, v2 in pb_parse(pay[0]):
                if a == 1 and b == 0:
                    typ = v2
                elif a == 2 and b == 2:
                    for x, y, z in pb_parse(v2):
                        if x == 1 and y == 0:
                            idx = z
        if typ is not None and 0 <= idx < len(pool):
            grid[(row, col)] = pool[idx]
    return grid, pool


# ─────────────────── 语义层：季节赛各周 ───────────────────
DATE_RE = re.compile(r"\d+\s*月\s*\d+\s*日?\s*至\s*\d+\s*月\s*\d+\s*日")
TITLE_RE = re.compile(r"^系列赛\s*\d")
NOTE_RE = re.compile(r"调[校教]\s*师\s*[:：]\s*(.+?)\s*调[校教]\s*代码\s*[:：]\s*(\d{9})")
YEAR_CAR = re.compile(r"^(19|20)\d{2}\s")

# 活动类型 → 限制强度
HARD = {"每周挑战"}
CLASS = {"终极考验", "季节锦标赛", "山道对决", "直线车友赛", "迷你锦标赛"}
SINGLE = {"危险标志", "测速区间", "测速照相", "拓荒者", "拓荒者门", "计时赛",
          "漂移区域", "漂移冲分赛", "每月劲敌", "劲敌", "越野攀爬"}
COND = {"照片挑战"}
MERGE = {"每日挑战", "每周挑战"}


def build_weeks(grid):
    """网格 → 按赛季周组织的活动列表（含车辆限制强度分级）"""
    maxr = max(r for r, _ in grid) if grid else 0
    hdrs = [r for r in sorted({r for r, _ in grid} | {0})
            if grid.get((r, 0)) == "活动类型" and grid.get((r, 2)) == "活动名称"]
    weeks = []
    for k, H in enumerate(hdrs):
        hi = (hdrs[k + 1] - 13) if k + 1 < len(hdrs) else maxr + 1
        title = date = ""
        for r in range(max(0, H - 13), H):
            for c in sorted(cc for rr, cc in grid if rr == r):
                s = grid.get((r, c), "")
                if not date:
                    d = DATE_RE.search(s)
                    if d:
                        date = d.group(0)
                if not title and TITLE_RE.match(s) and "进度" not in s:
                    title = s
        ev, cur = [], ""
        for r in range(H + 1, hi):
            row = {c: grid[(r, c)] for rr, c in grid if rr == r}
            if not row:
                continue
            if row.get(0):
                cur = row[0]
            name, car = row.get(2, ""), row.get(4, "")
            note, rw = row.get(8, ""), row.get(15, "")
            if not (name or car):
                continue
            mm = NOTE_RE.search(note)
            ev.append({"type": row.get(0) or cur, "name": name, "car": car, "note": note,
                       "tuner": mm.group(1).strip() if mm else "",
                       "code": mm.group(2) if mm else "", "reward": rw})
        # 合并同类型多行（每日挑战 7 条、每周挑战 4 步）
        merged = []
        for e in ev:
            if e["type"] in MERGE and merged and merged[-1]["type"] == e["type"]:
                merged[-1]["subs"].append({"name": e["name"], "text": e["car"] or e["note"]})
                if not merged[-1]["car"]:
                    merged[-1]["car"] = e["car"]
                if not merged[-1]["code"] and e["code"]:
                    merged[-1]["code"] = e["code"]
                    merged[-1]["tuner"] = e["tuner"]
                    merged[-1]["note"] = e["note"]
            else:
                e2 = dict(e); e2["subs"] = []
                merged.append(e2)
        for e in merged:
            carname = re.sub(r"^(拥有并驾驶|驾驶|使用)\s*", "", e["car"]).strip()
            iscar = bool(YEAR_CAR.match(carname))
            if e["type"] in HARD:
                e["level"] = "硬性指定车型"
            elif e["type"] in COND:
                e["level"] = "品牌/条件限定"
            elif iscar and e["type"] in CLASS:
                e["level"] = "类别限定"
            elif iscar:
                e["level"] = "推荐用车"
            else:
                e["level"] = "无车辆限制"
        weeks.append({"title": title, "date": date, "hdr": H, "events": merged})
    return weeks


# ─────────────────── 语义层：组别页（车辆榜） ───────────────────
HEADER_NAMES = {"竞争力", "制造商", "车辆型号", "驱动", "难度", "轮胎", "定位",
                "调校师", "备注", "获取方式", "等级", "赛事", "车辆排行榜"}
CAR_COLS = ("竞争力", "制造商", "车辆型号", "驱动", "难度", "轮胎", "定位", "备注", "获取方式")


def parse_group_entries(grid):
    """组别页网格 → 车辆榜条目

    难点：原表用**合并单元格**，同一辆车挂多个调校师时，车名等列只在首行出现；
    另外部分单元格残留了表头文本（如「车辆型号」「驱动」），需过滤。
    """
    rows = {}
    for (r, c), v in grid.items():
        rows.setdefault(r, {})[c] = v
    if not rows:
        return []

    hdr_row = None
    for r in sorted(rows):
        vals = {v for v in rows[r].values() if isinstance(v, str)}
        if "车辆型号" in vals and ("制造商" in vals or "竞争力" in vals):
            hdr_row = r
            break
    if hdr_row is None:
        return []
    cols = dict(rows[hdr_row])

    entries = []
    for r in sorted(rows):
        if r <= hdr_row:
            continue
        d = rows[r]
        if not d:
            continue
        rec = {}
        for c, v in d.items():
            nm = cols.get(c) or ("额外调校师%d" % c)
            if isinstance(v, str) and v.strip() in HEADER_NAMES:
                continue          # 过滤残留表头文本
            rec[nm] = v

        if rec.get("车辆型号") or rec.get("制造商"):
            rec["调校师"] = [rec["调校师"]] if rec.get("调校师") else []
            for k in list(rec):
                if k.startswith("额外调校师") and rec[k]:
                    rec["调校师"].append(rec[k])
                    del rec[k]
            entries.append(rec)
        else:
            # 附属行：只补调校师名（合并单元格的续行）
            if entries:
                for k in ("调校师",):
                    if rec.get(k):
                        entries[-1]["调校师"].append(rec[k])
                for k in list(rec):
                    if k.startswith("额外调校师") and rec[k]:
                        entries[-1]["调校师"].append(rec[k])
    # 去掉没有车名的噪点
    entries = [e for e in entries if (e.get("车辆型号") or "").strip()]
    return entries


# ─────────────────── vgover 当周攻略解析 ───────────────────
def _strip(s):
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


TOKEN_RE = re.compile(r"<(h2|h3|blockquote|li|p)\b[^>]*>(.*?)</\1>", re.S | re.I)


def parse_vgover(html_text):
    """vgover 季节赛攻略页 → {title, season, date, series, events[]}

    结构：h2=活动（以「- 」开头），h3=字段（「• 字段名：值」），blockquote/li=子任务
    """
    doc = html_text
    # 文章主标题
    mt = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S | re.I)
    title = _strip(mt.group(1)) if mt else ""
    # 面包屑/正文中的赛季信息
    season = date = series = ""
    for pat, key in ((r"季节[：:]\s*</?[^>]*>?\s*([夏秋春冬]季)", "season"),):
        pass
    ms = re.search(r"季节[：:]\s*(?:<[^>]+>)*\s*([夏秋春冬]季)", doc)
    if ms:
        season = ms.group(1)
    md = re.search(r"活动时间[：:]\s*(?:<[^>]+>)*\s*([0-9]{4}\s*年\s*\d+\s*月\s*\d+\s*日\s*[-–~]\s*\d+\s*月\s*\d+\s*日)", doc)
    if not md:
        md = re.search(r"([0-9]{4}\s*年\s*\d+\s*月\s*\d+\s*日\s*[-–~]\s*\d+\s*月\s*\d+\s*日)", doc)
    if md:
        date = re.sub(r"\s+", "", md.group(1))
    mr = re.search(r"([SＳ]\s*\d+)\s*(?:系列赛)?", doc)
    if mr:
        series = re.sub(r"\s+", "", mr.group(1)).upper()

    tokens = []
    for m in TOKEN_RE.finditer(doc):
        tag, inner = m.group(1).lower(), m.group(2)
        if tag == "blockquote":
            items = [_strip(x) for x in re.findall(r"<p\b[^>]*>(.*?)</p>", inner, re.S | re.I)]
            items = [x for x in items if x]
            if items:
                tokens.append(("quote", items))
        else:
            t = _strip(inner)
            if t:
                tokens.append((tag, t))

    events = []
    cur = None
    started = False
    for tag, val in tokens:
        if not isinstance(val, str):
            if tag == "quote" and started and cur is not None:
                cur["items"].extend(val)
            continue
        # vgover 的活动标题有时是 h2、有时嵌在大活动下写成 h3（如「- 地平线乐玩：极速连接」）
        if tag in ("h2", "h3") and (val.startswith("- ") or val.startswith("－ ")
                                    or val.startswith("— ")):
                started = True
                nm = val[2:].strip()
                cur = {"raw": nm, "kind": "", "name": nm, "fields": {}, "items": []}
                for sp in ("：", ":"):
                    if sp in nm:
                        k, _, v = nm.partition(sp)
                        cur["kind"], cur["name"] = k.strip(), v.strip()
                        break
                events.append(cur)
                continue
        if tag == "h2":
            if started:
                cur = None          # 非活动 h2 = 新章节，结束当前活动收集
            continue
        if not started or cur is None:
            continue
        if tag == "h3":
            v = val.lstrip("•· ").strip()
            if "：" in v:
                k, _, vv = v.partition("：")
                cur["fields"][k.strip()] = vv.strip()
            elif ":" in v:
                k, _, vv = v.partition(":")
                cur["fields"][k.strip()] = vv.strip()
            else:
                cur.setdefault("notes", []).append(v)
        elif tag == "quote":
            cur["items"].extend(val)
        elif tag in ("li", "p"):
            if len(val) < 300:
                cur["items"].append(val)

    # 过滤掉没有实质内容的块（纯图片章节、页脚导流）
    KNOWN_KINDS = {"每周挑战", "每日挑战", "照片挑战", "寻宝游戏", "季节锦标赛",
                   "终极考验", "漂移冲分赛", "漂移区域", "危险标志", "测速区间",
                   "测速照相", "拓荒者门", "拓荒者", "计时赛", "每月劲敌", "劲敌",
                   "地平线乐玩", "地平线特技派对", "收藏品", "捉迷藏", "淘汰之王",
                   "山道对决", "直线车友赛", "迷你锦标赛", "越野攀爬"}
    events = [e for e in events if e["kind"] in KNOWN_KINDS or e["fields"]]
    return {"title": title, "season": season, "date": date, "series": series,
            "events": events, "src": ""}


# ─────────────────── 主流程 ───────────────────
def fetch_all(verbose=True):
    t_start = time.time()
    out = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tabs": {}, "errors": []}

    # 1) 腾讯文档：顺序抓全部分页（附带限速，避免触发风控）
    for tab, name in TABS:
        for attempt in (1, 2, 3):
            try:
                raw = fetch_tencent_tab(tab)
                json.dump({"name": name, "raw": raw},
                          open(os.path.join(DATA, "raw_%s.json" % tab), "w", encoding="utf-8"),
                          ensure_ascii=False)
                out["tabs"][tab] = name
                if verbose:
                    print("  [腾讯文档] %-16s OK  %d KB (%.0fs)"
                          % (name, len(raw) // 1024, time.time() - t_start))
                break
            except Exception as e:
                if attempt == 3:
                    out["errors"].append("腾讯文档 %s: %s" % (name, e))
                    if verbose:
                        print("  [腾讯文档] %-16s FAIL %s" % (name, e))
                    out["tabs"][tab] = None
                else:
                    time.sleep(2 * attempt)
        time.sleep(0.4)

    # 2) 解析季节赛页
    raw_path = os.path.join(DATA, "raw_zq302z.json")
    if os.path.exists(raw_path):
        try:
            raw = json.load(open(raw_path, encoding="utf-8"))["raw"]
            grid, pool = parse_sheet_grid(raw)
            weeks = build_weeks(grid)
            json.dump(weeks, open(os.path.join(DATA, "weeks.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            out["weeks"] = len(weeks)
            out["weeks_range"] = [weeks[0]["date"] if weeks else "",
                                  weeks[-1]["date"] if weeks else ""]
            if verbose:
                print("  [解析] 季节赛周次: %d 周（%s）" % (len(weeks), weeks[0]["date"] if weeks else "-"))
        except Exception as e:
            out["errors"].append("解析季节赛页: %s" % e)
            if verbose:
                print("  [解析] 季节赛页 FAIL %s" % e)

    # 3) 各组别页 → 车辆榜
    try:
        groups = []
        for tab, name in TABS:
            p = os.path.join(DATA, "raw_%s.json" % tab)
            if not os.path.exists(p) or tab in ("zq302z", "o07r66"):
                continue
            raw = json.load(open(p, encoding="utf-8"))["raw"]
            grid, pool = parse_sheet_grid(raw)
            groups.append({"tab": tab, "name": name, "entries": parse_group_entries(grid)})
        json.dump(groups, open(os.path.join(DATA, "groups.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        out["groups"] = len(groups)
        if verbose:
            print("  [解析] 组别页: %d 个" % len(groups))
    except Exception as e:
        out["errors"].append("解析组别页: %s" % e)
        if verbose:
            print("  [解析] 组别页 FAIL %s" % e)

    # 4) 当周攻略（vgover）—— URL 由 state.json 指定，没有就跳过
    st_path = os.path.join(DATA, "state.json")
    st = {}
    if os.path.exists(st_path):
        try:
            st = json.load(open(st_path, encoding="utf-8"))
        except Exception:
            st = {}
    wurl = st.get("week_guide_url")
    if wurl:
        try:
            html_text = fetch_vgover(wurl)
            wk = parse_vgover(html_text)
            wk["src"] = wurl
            json.dump(wk, open(os.path.join(DATA, "week_guide.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            out["week_guide"] = {"url": wurl, "events": len(wk["events"]),
                                 "title": wk["title"], "date": wk["date"]}
            if verbose:
                print("  [vgover] %s | %s 活动 %d 项" % (wk["title"][:46], wk["date"], len(wk["events"])))
        except Exception as e:
            out["errors"].append("抓取当周攻略: %s" % e)
            if verbose:
                print("  [vgover] FAIL %s" % e)

    out["elapsed_sec"] = round(time.time() - t_start, 1)
    return out


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "fetch":
        print("=== 开始抓取 ===")
        r = fetch_all()
        json.dump(r, open(os.path.join(DATA, "last_fetch.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("=== 完成 %.1fs | 错误 %d ===" % (r["elapsed_sec"], len(r["errors"])))
        for e in r["errors"]:
            print("   !", e)
    elif cmd == "selftest":
        p = sys.argv[2]
        txt = open(p, encoding="utf-8", errors="replace").read()
        if p.endswith(".html"):
            r = parse_vgover(txt)
            print("标题:", r["title"])
            print("赛季:", r["season"], "| 日期:", r["date"], "| 系列:", r["series"])
            for e in r["events"]:
                print("  [%s] %s" % (e["kind"], e["name"]))
                for k, v in e["fields"].items():
                    print("      %s = %s" % (k, v[:70]))
                for it in e["items"][:3]:
                    print("      · %s" % it[:70])
        else:
            grid, pool = parse_sheet_grid(txt)
            print("cells:", len(grid), "| pool:", len(pool))
            ws = build_weeks(grid)
            print("weeks:", len(ws))
            for w in ws[:3]:
                print("  %-34s %-24s events=%d" % (w["title"], w["date"], len(w["events"])))
