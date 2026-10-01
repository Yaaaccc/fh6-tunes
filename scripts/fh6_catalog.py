# -*- coding: utf-8 -*-
"""
fh6_catalog.py —— 车型目录（稀有度 / 获取途径 / 车展价）与「值不值得做」判据

数据来源（页面上必须署名）：
  · 稀有度与获取途径：社区库 Nova's Autoshow —— https://forza.nerdyderg.com
  · 中文车名 / 中文档位名 / 车辆序号：B站小玩具「地平线六车辆数据库」整理，作者 Dr.Hydra
    https://www.bilibili.com/toy/forzahorizon6/index.html

为什么不用上游 /api/cars 当底本：它的 id 是 "1998_nissan_silvia_ks_aero" 这种字符串，
**没有游戏内部的车辆序号**；而存档里 Livery_<序号> / Tuning_<序号> 要拿序号去对，
所以必须用带 int id 的中文版目录。

⚠️ 两个已踩过的坑（都实测过，别改回去）：
  1. **稀有度是 1 起的，0 表示「未定级」**。玩具自己的 filters.js 写的是
     `labels[tier - 1]`，且注释说明「Tier 0 是 unknown（交通车与尚未录入的车）」。
     用 0 起会整体错一位（传奇会被显示成极限竞速特别版）。
  2. **匹配奖励车名不能宽松**。曾用「包含关系」兜底，把「兰博基尼 Tecnica」匹到了
     「本田 e '22」。宁可返回 None（页面上标「未能定位」），也不要匹错。
"""
import os, re, io, json, gzip, zlib, difflib, collections
import urllib.request, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")

SHELL_URL = "https://www.bilibili.com/toy/forzahorizon6/index.html"

ACQ_KEYS = ["autoshow", "wheelspin", "seasonal", "progression",
            "barn_find", "treasure", "dlc", "aftermarket"]
ACQ_NAMES = ["车展", "抽奖", "季节赛事", "剧情", "车房宝物", "秘藏座驾", "商店附加内容", "改装车"]

# rarity 是 1 起的；0 = 未定级
RARITY_NAMES = ["普通", "稀有", "史诗", "传奇", "极限竞速特别版", "车房宝物", "秘藏座驾"]
RARITY_UNKNOWN = "未定级"

# 真正稀缺的来源 / 档位
HARD_SOURCES = ("季节赛事", "车房宝物", "秘藏座驾")
HARD_RARITY = ("秘藏座驾", "车房宝物")
HIGH_RARITY = ("传奇", "极限竞速特别版", "秘藏座驾", "车房宝物")


# ────────────────────── 抓取 ──────────────────────
def _get(url, referer=None, timeout=60):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if referer:
        h["Referer"] = referer
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            raw = zlib.decompress(raw, -15)
    return raw


def resolve_toy_base(verbose=True):
    """从 B站外壳页取出 iframe 真身地址，返回目录根 URL（跟版本号走，不写死）"""
    html = _get(SHELL_URL, referer="https://www.bilibili.com/").decode("utf-8", "replace")
    m = re.search(r'<iframe[^>]*\bsrc="([^"]+)"', html)
    if not m:
        raise RuntimeError("外壳页里找不到 iframe src（B站玩具结构可能变了）")
    base = m.group(1)
    base = base[: base.rindex("/") + 1]
    if verbose:
        print("  [目录] 真身:", base)
    return base


def _read_cache(path):
    """返回 (缓存天数 or None, 数据 or None)"""
    try:
        d = json.load(io.open(path, encoding="utf-8"))
        if not d.get("cars"):
            return None, None
        t = d.get("_fetched_at") or ""
        if t:
            dt = datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            return (datetime.datetime.now() - dt).days, d
        return None, d
    except Exception:
        return None, None


def fetch_catalog(verbose=True, force=False, max_age_days=14):
    """取车型目录。缓存默认 14 天有效（车型表很少变，但也不能永不更新）；
       离线（FH6_OFFLINE=1）或抓取失败时，一律沿用已有缓存，保证页面还能生成。"""
    path = os.path.join(DATA, "catalog.json")
    age, d = _read_cache(path)
    have = d is not None
    offline = os.environ.get("FH6_OFFLINE") == "1"

    if have and not force and (offline or age is None or age < max_age_days):
        if verbose:
            print("  [目录] 用本地缓存：%d 台（%s）"
                  % (len(d["cars"]), ("%d 天前" % age) if age is not None else "时间未知"))
        return d
    if offline:
        if have:
            if verbose:
                print("  [目录] 离线模式，沿用缓存：%d 台" % len(d["cars"]))
            return d
        raise RuntimeError("离线模式且没有本地缓存 %s" % path)

    try:
        base = resolve_toy_base(verbose=verbose)
        raw = _get(base + "data/catalog.zh.json", referer="https://www.bilibili.com/")
        nd = json.loads(raw.decode("utf-8"))
        nd["_source_base"] = base
        nd["_fetched_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(DATA, exist_ok=True)
        io.open(path, "w", encoding="utf-8").write(json.dumps(nd, ensure_ascii=False))
        if verbose:
            print("  [目录] 已抓取：%d 台（%d 字节）" % (len(nd.get("cars", [])), len(raw)))
        return nd
    except Exception as ex:
        if have:
            if verbose:
                print("  [目录] 抓取失败（%r），沿用缓存：%d 台" % (ex, len(d["cars"])))
            return d
        raise


# ────────────────────── 名字归一 ──────────────────────
_PUNCT = re.compile(r"[\s\-_/,\.\'\`\u2019\"·、（）()\[\]！!：:#＆&]+")
# 年份尾巴：攻略文案里写作「 - 1962 年」「 1972」「 '86」，都要能剥掉。
# 关键：年份前必须是行首或分隔符（空格/短横），否则「Peel P50」的 50 会被误剥成「Peel P」。
_YEAR_TAIL = re.compile(r"(?:^|[\s\-–—]+)(?:(?:19|20)\d{2}\s*年?|\d{2}\s*年)\s*$")
# 末尾的中文括注，如「（每周挑战所需）」。含中文字才剥，
# 免得把「Silvia (S15)」这种正名里的英文括号一起剥掉。
_TAIL_PAREN = re.compile(r"[（(][^（()）]*[\u3400-\u9fff][^（()）]*[）)]\s*$")
_TOKEN = re.compile(r"[a-z]+|\d+")


def strip_notes(s):
    """剥掉文案尾巴：先摘中文括注，再摘年份"""
    t = (s or "").strip()
    for _ in range(3):
        n = _TAIL_PAREN.sub("", t).strip()
        if n == t:
            break
        t = n
    return t


def norm(s):
    return _PUNCT.sub("", (s or "").lower())


def core(s):
    return _YEAR_TAIL.sub("", strip_notes(s)).strip()


def _toks(s):
    return tuple(sorted(_TOKEN.findall(norm(s))))


def _bag(s):
    return collections.Counter(norm(s))


def _jac(a, b):
    u = sum((a | b).values())
    return (sum((a & b).values()) / u) if u else 0.0


# ────────────────────── 目录 ──────────────────────
class Catalog(object):
    def __init__(self, d):
        self.raw = d
        self.makes = {str(k): v for k, v in (d.get("makes") or {}).items()}
        self.cars = d.get("cars") or []
        self.by_id = {}
        self._idx = {}          # 键 → 第一台（向后兼容）
        self._idx_all = {}      # 键 → [所有同键的车]
        for c in self.cars:
            cid = c.get("id")
            if isinstance(cid, int):
                self.by_id[cid] = c
            seen = set()
            for k in (c.get("short"), c.get("model")):
                if not k:
                    continue
                for cand in (norm(k), norm(core(k))):
                    if not cand or cand in seen:
                        continue
                    seen.add(cand)
                    self._idx_all.setdefault(cand, []).append(c)
                    self._idx.setdefault(cand, c)
        self._keys = list(self._idx.keys())
        self._multi = {k for k, v in self._idx_all.items() if len(v) > 1}
        # 厂商名，长的优先（「梅赛德斯-奔驰」要先于「梅赛德斯」）
        self._mk_sorted = sorted(
            ((norm(v), v) for v in self.makes.values() if v), key=lambda x: -len(x[0]))

    # ---- 属性 ----
    def sources(self, c):
        a = c.get("acq") or 0
        return [ACQ_NAMES[i] for i in range(len(ACQ_KEYS)) if (a >> i) & 1]

    def rarity(self, c):
        r = c.get("rarity")
        if isinstance(r, int) and r >= 1 and r <= len(RARITY_NAMES):
            return RARITY_NAMES[r - 1]
        return RARITY_UNKNOWN

    def name(self, c):
        return c.get("short") or c.get("model") or ""

    def make_of(self, c):
        return self.makes.get(str(c.get("make")), "")

    def match_id(self, cid):
        return self.by_id.get(cid)

    # ---- 名字匹配（分层，宁缺勿错）----
    def _uniq(self, key):
        """键唯一命中才算数，否则宁可放弃"""
        got = self._idx_all.get(key)
        return got[0] if got and len(got) == 1 else None

    def match_name(self, text):
        """奖励文案 → 目录条目。分层匹配，layers 记录命中的是哪一层，便于排查。"""
        self.last_layer = None
        if not text:
            return None
        raw = strip_notes(text)
        nr = norm(raw)          # 保留年份
        n = norm(core(raw))     # 剥掉年份
        if not n:
            return None

        # L1 精确（先带年份、再去掉年份）。**也要唯一命中**：
        #   model 字段带年份的车（Civic Type R / M5 / Corvette ZR1）会让去掉年份的键
        #   同时指向 4~7 台车，此时随机挑一台就是硬凑，宁可交给后面的层或直接放弃。
        for cand in (nr, n):
            got = self._uniq(cand)
            if got:
                self.last_layer = "L1"
                return got

        # L2 去掉厂商前缀后精确。**必须唯一命中**，否则会出现
        #    「雪佛兰 Corvette '53」被匹到第一台叫 corvette 的车（'67）这种错。
        for src in (nr, n):
            for mk_n, mk in self._mk_sorted:
                if mk_n and src.startswith(mk_n) and len(src) > len(mk_n):
                    got = self._uniq(src[len(mk_n):])
                    if got:
                        self.last_layer = "L2"
                        return got

        # L3 词元多重集相同（「奥迪 #2 S1」↔「#2 奥迪 S1」）
        tq = _toks(core(raw))
        if len(tq) >= 2:
            same = [c for k, c in self._idx.items() if _toks(k) == tq]
            if len(same) == 1:
                self.last_layer = "L3"
                return same[0]

        # L4 编辑距离，阈值卡高 + 长度约束
        if len(n) >= 5:
            best = difflib.get_close_matches(n, self._keys, n=1, cutoff=0.92)
            if best and abs(len(best[0]) - len(n)) <= 3:
                got = self._uniq(best[0])
                if got:
                    self.last_layer = "L4"
                    return got

        # L5 厂商一致时，允许「模型名被包含」（「兰博基尼 Tecnica」↔「Huracán Tecnica」）
        qmk = next((mk for mk_n, mk in self._mk_sorted if mk_n and mk_n in n), None)
        if qmk:
            part = n
            for mk_n, mk in self._mk_sorted:
                if mk == qmk and part.startswith(mk_n):
                    part = part[len(mk_n):]
                    break
            if len(part) >= 4:
                hits = [c for k, c in self._idx.items()
                        if part in k and self.make_of(c) == qmk]
                ids = {c.get("id") for c in hits}
                if len(ids) == 1:
                    self.last_layer = "L5"
                    return hits[0]

        # L6 厂商一致 + 字符袋高度重合，且与第二名胜出足够多
        qbag = _bag(core(raw))
        scored = []
        for k, c in self._idx.items():
            if qmk and self.make_of(c) != qmk:
                continue
            v = _jac(qbag, _bag(k))
            if v >= 0.62:
                scored.append((v, c))
        if scored:
            scored.sort(key=lambda x: -x[0])
            if len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.06:
                self.last_layer = "L6"
                return scored[0][1]
        return None

    # ---- 判据 ----
    def verdict(self, c, owned=None):
        """返回 (星级 0-3, 标签, 理由文案)"""
        src, rar = self.sources(c), self.rarity(c)
        buyable = "车展" in src
        hard = [s for s in src if s in HARD_SOURCES]
        cost = c.get("cost") or 0
        price = "{:,} CR".format(cost) if cost else "—"
        pricey = cost >= 1000000        # 车展价七位数 → 白拿省一大笔

        if hard and not buyable:
            star, tag = 3, "买不到"
            why = "只能靠「%s」获得，车展买不到" % "／".join(hard)
        elif rar in HARD_RARITY:
            star, tag = 3, "买不到"
            why = "%s，车展买不到" % rar
        elif not buyable:
            star, tag = 2, "买不到"
            why = "车展买不到，来源：%s" % ("／".join(src) or "未知")
        elif rar in HIGH_RARITY or pricey:
            star, tag = 2, "能买到"
            why = "%s，车展可直购（%s）" % (rar, price)
            if pricey:
                why += "，白拿省一大笔"
        else:
            star, tag = 1, "能买到"
            why = "%s，车展可直购（%s）" % (rar, price)

        if owned is True:
            star = max(0, star - 2)
            why += "；您已有"
        return star, tag, why


# ────────────────────── 本周奖励车 ──────────────────────
NOT_A_CAR = re.compile(
    r"点数|抽奖|服装|服饰|喇叭|表情|徽章|LINK|Link|经验|技能点|货币|金币"
    r"|\bCR\b|\bcr\b|奖励$|^—$")


def reward_items(events):
    """从活动列表挑出「奖励是一台车」的条目"""
    out = []
    for e in events or []:
        r = (e.get("reward") or "").strip()
        if not r or NOT_A_CAR.search(r):
            continue
        out.append({"event": e.get("name") or "", "kind": e.get("kind") or "", "text": r})
    return out
