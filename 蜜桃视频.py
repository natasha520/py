# coding=utf-8
# 蜜桃视频 TVBox 爬虫
# 源站: https://honeypeach.cc · HMAC 签名 API + PoW

import json
import time
import random
import hashlib
import hmac
from urllib.parse import quote, unquote
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.base = "https://honeypeach.cc"
        if extend and extend.strip().startswith("http"):
            self.base = extend.strip().rstrip("/")

        self.ua = (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Referer": self.base + "/"
        }

        # 会话
        self._sid = ""
        self._skey = ""
        self._exp = 0
        self._dev = ""

        self.searchable = ["video", "duanju", "caibian", "shortv", "guochan"]

        # type_id -> (module_key, default_cat)
        # cat 格式: code|src|sub
        self.cate_map = {
            "video_new": ("video", "new|missav|"),
            "video_release": ("video", "release|missav|"),
            "video_chinese": ("video", "chinese-subtitle|missav|"),
            "video_madou": ("video", "madou|missav|"),
            "video_uncensored": ("video", "uncensored-leak|missav|"),
            "video_hot": ("video", "monthly-hot|missav|"),
            "duanju": ("duanju", "tuijian|huangguo|0"),
            "caibian": ("caibian", "0|huangdou|0"),
            "shortv": ("shortv", "all|dongman|0"),
            "heiliao": ("heiliao", "0|huangdou|0"),
            "live": ("live", "girls||"),
            "guochan": ("guochan", "||"),
        }

    def getName(self):
        return "蜜桃视频"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        classes = [
            {"type_id": "video_new", "type_name": "最近更新"},
            {"type_id": "video_release", "type_name": "新作上市"},
            {"type_id": "video_chinese", "type_name": "中文字幕"},
            {"type_id": "video_madou", "type_name": "麻豆传媒"},
            {"type_id": "video_uncensored", "type_name": "无码流出"},
            {"type_id": "video_hot", "type_name": "热门"},
            {"type_id": "duanju", "type_name": "蜜桃短剧"},
            {"type_id": "caibian", "type_name": "擦边短剧"},
            {"type_id": "shortv", "type_name": "蜜桃动漫"},
            {"type_id": "heiliao", "type_name": "黑料吃瓜"},
            {"type_id": "live", "type_name": "蜜桃直播"},
            {"type_id": "guochan", "type_name": "国产精品"},
        ]
        return {"class": classes, "list": []}

    def homeVideoContent(self):
        return self.categoryContent("video_new", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        key, cat = self.cate_map.get(tid, ("video", "new|missav|"))
        # 支持 extend 里传 cat
        if isinstance(extend, dict) and extend.get("cat"):
            cat = extend["cat"]
        items = self._load_module(key, cat, page)
        return {
            "list": items,
            "page": page,
            "pagecount": 999,
            "limit": 24,
            "total": 999999
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else str(ids)
        p = self._parse_link(raw)
        if not p["key"] or not p["id"]:
            return {"list": []}

        qs = []
        if p["src"]:
            qs.append("src=" + quote(p["src"]))
        if p["sub"]:
            qs.append("sub=" + quote(p["sub"]))
        data = self._api_get(
            f"/api/detail/{quote(p['key'])}/{quote(p['id'])}",
            "&".join(qs)
        )
        det = (data or {}).get("detail") or {}
        if not det:
            return {"list": []}

        title = p["listTitle"] or (det.get("title") or p["id"]).strip()
        cover = self._abs_url(det.get("cover") or "")
        desc = (det.get("desc") or "").strip()
        remarks = f"共{det['ep_count']}集" if det.get("ep_count") else (det.get("date") or "")

        eps = det.get("episodes") or []
        if not eps:
            eps = [{"ep": 1, "name": "正片"}]

        play_list = []
        for i, e in enumerate(eps):
            ep = str(e.get("ep") if e.get("ep") is not None else i + 1)
            ep_name = (e.get("name") or "").replace("$", " ").replace("#", " ").strip()
            if len(eps) == 1:
                ep_name = title
            else:
                if not ep_name or ep_name in ("正片", "播放"):
                    ep_name = f"{title} 第{ep}集"
                elif not ep_name.startswith(title):
                    ep_name = f"{title} {ep_name}"
            # play id: key|id|src|sub|ep||title
            play_id = (
                f"{quote(p['key'])}|{quote(p['id'])}|"
                f"{quote(p['src'])}|{quote(p['sub'])}|{quote(ep)}"
                f"||{quote(title)}"
            )
            play_list.append(f"{ep_name}${play_id}")

        vod = {
            "vod_id": raw,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": "\n".join([x for x in [remarks, desc] if x]),
            "vod_play_from": "蜜桃",
            "vod_play_url": "#".join(play_list),
            "type_name": "视频",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": remarks
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        out = []
        seen = set()
        for mod in self.searchable:
            try:
                data = self._api_get(
                    "/api/search",
                    f"key={quote(mod)}&kw={quote(key)}&page={page}"
                )
                for row in (data or {}).get("list") or []:
                    v = self._map_item(row, mod, "", "")
                    if v and v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        out.append(v)
            except Exception:
                pass
        return {"list": out, "page": page}

    def playerContent(self, flag, id, vipFlags):
        p = self._parse_link(id)
        if not p["key"] or not p["id"]:
            return {"parse": 1, "url": id, "header": self.headers}

        ep = p["ep"] or "1"
        qs = []
        if p["src"]:
            qs.append("src=" + quote(p["src"]))
        if p["sub"]:
            qs.append("sub=" + quote(p["sub"]))
        data = self._api_get(
            f"/api/play/{quote(p['key'])}/{quote(p['id'])}/{quote(ep)}",
            "&".join(qs)
        )
        pl = (data or {}).get("play") or {}
        if pl.get("locked"):
            return {"parse": 1, "url": id, "header": self.headers}

        src = (pl.get("src") or "").strip()
        proxy = (pl.get("src_proxy") or "").strip()
        hdrs = {"User-Agent": self.ua, "Referer": self.base + "/"}

        # 优先直连，没有再用中转
        url = self._abs_url(src) or self._abs_url(proxy)
        if url:
            return {"parse": 0, "url": url, "header": hdrs}
        return {"parse": 1, "url": id, "header": self.headers}

    # ==================== 会话 / 签名 ====================

    def _rnd(self, n=10):
        chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(random.choice(chars) for _ in range(n))

    def _dev_id(self):
        if not self._dev:
            self._dev = self._rnd(12) + hex(int(time.time() * 1000))[2:]
        return self._dev

    def _rotate_dev(self):
        self._dev = "zp" + self._rnd(24)
        self._sid = ""
        self._skey = ""
        self._exp = 0

    @staticmethod
    def _hp_hash(s):
        h = 0x811C9DC5
        for ch in s:
            h ^= ord(ch)
            h = (h * 0x01000193) & 0xFFFFFFFF
        return h

    def _hp_pow(self, chal, nonce):
        h = self._hp_hash(chal + ":" + nonce)
        for _ in range(4):
            h = self._hp_hash(f"{h:08x}" + chal)
        return f"{h:08x}"

    def _hp_solve(self, chal, bits=12):
        bits = int(bits or 12)
        want = "0" * (bits >> 2)
        n = 0
        while n < 20000000:
            nx = format(n, "x")
            hx = self._hp_pow(chal, nx)
            if hx.startswith(want):
                return f"{chal}.{nx}"
            n += 1
        return ""

    def _handshake(self):
        q = "dev=" + quote(self._dev_id())
        r = self.fetch(
            f"{self.base}/api/handshake?{q}",
            headers={"User-Agent": self.ua, "Accept": "application/json"}
        )
        body = self._parse_json(r)
        if body.get("need_chal"):
            tok = self._hp_solve(str(body["need_chal"]), body.get("bits") or 12)
            if not tok:
                raise Exception("蜜桃 PoW 失败")
            r = self.fetch(
                f"{self.base}/api/handshake?{q}&c={quote(tok)}",
                headers={"User-Agent": self.ua, "Accept": "application/json"}
            )
            body = self._parse_json(r)
        if body.get("sid") and body.get("skey"):
            self._sid = str(body["sid"])
            self._skey = str(body["skey"])
            self._exp = int(body.get("exp") or 0)
            return
        raise Exception("蜜桃握手失败: " + str(body.get("msg") or body.get("err") or "no sid"))

    def _ensure_session(self, force=False):
        now = time.time()
        if not force and self._sid and self._skey and now < self._exp - 60:
            return
        self._handshake()

    @staticmethod
    def _sha256_hex(msg):
        if isinstance(msg, str):
            msg = msg.encode("utf-8")
        return hashlib.sha256(msg).hexdigest()

    def _hmac_sha256_hex(self, key_hex, msg_str):
        key = bytes.fromhex(key_hex)
        return hmac.new(key, msg_str.encode("utf-8"), hashlib.sha256).hexdigest()

    def _api_get(self, path, query=""):
        query = (query or "").strip()
        self._ensure_session(False)

        def once():
            ts = str(int(time.time()))
            nonce = self._rnd(8) + format(int(time.time() * 1000), "x")
            bh = self._sha256_hex("")
            canon = f"GET\n{path}\n{query}\n{bh}\n{ts}\n{nonce}\n{self._sid}"
            sig = self._hmac_sha256_hex(self._skey, canon)
            url = self.base + path + (("?" + query) if query else "")
            r = self.fetch(url, headers={
                "User-Agent": self.ua,
                "Accept": "application/json",
                "X-Hp-Sid": self._sid,
                "X-Hp-Ts": ts,
                "X-Hp-Nonce": nonce,
                "X-Hp-Sign": sig,
                "Referer": self.base + "/"
            })
            status = getattr(r, "status_code", None) or getattr(r, "status", 200) or 200
            body = self._parse_json(r)
            return status, body

        status, body = once()
        if status == 401:
            self._ensure_session(True)
            status, body = once()
        if self._is_rate_limited(body, status):
            self._rotate_dev()
            self._ensure_session(True)
            status, body = once()
        return body

    @staticmethod
    def _is_rate_limited(body, status):
        if status == 429:
            return True
        err = str((body or {}).get("err") or (body or {}).get("msg") or "").lower()
        if not err:
            return False
        keys = ("rl_sid", "rl_dev", "rl_ip", "rate", "limit", "toomany", "busy")
        return any(k in err for k in keys)

    def _parse_json(self, r):
        try:
            text = r.text if hasattr(r, "text") else str(r.content)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            return json.loads(text) if text else {}
        except Exception:
            return {}

    # ==================== 业务 ====================

    def _abs_url(self, u):
        u = (u or "").strip()
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return self.base + u
        return self.base + "/" + u

    def _safe_dec(self, v):
        v = (v or "").strip()
        if not v:
            return ""
        try:
            return unquote(v)
        except Exception:
            return v

    def _parse_link(self, link):
        list_title = ""
        if isinstance(link, dict):
            list_title = (link.get("title") or link.get("name") or "").strip()
            link = link.get("link") or link.get("id") or ""
        link = str(link or "").strip()
        if link.startswith("mt://"):
            link = link[5:]
        emb = ""
        if "||" in link:
            link, emb = link.split("||", 1)
            try:
                emb = unquote(emb)
            except Exception:
                pass
        parts = link.split("|")
        while len(parts) < 5:
            parts.append("")
        return {
            "key": self._safe_dec(parts[0]),
            "id": self._safe_dec(parts[1]),
            "src": self._safe_dec(parts[2]),
            "sub": self._safe_dec(parts[3]),
            "ep": self._safe_dec(parts[4]) or "1",
            "listTitle": list_title or emb or ""
        }

    def _parse_cat(self, raw, fallback=""):
        raw = (raw or fallback or "").strip()
        parts = raw.split("|")
        while len(parts) < 3:
            parts.append("")
        return {"cat": parts[0].strip(), "src": parts[1].strip(), "sub": parts[2].strip()}

    def _map_item(self, it, key, src, sub):
        if not it or it.get("id") is None:
            return None
        iid = str(it["id"])
        s = (it.get("src") or src or "").strip()
        title = (it.get("title") or iid).strip()
        link = (
            f"mt://{quote(key)}|{quote(iid)}|{quote(s)}|{quote(sub or '')}"
            f"||{quote(title)}"
        )
        return {
            "vod_id": link,
            "vod_name": title,
            "vod_pic": self._abs_url(it.get("cover") or ""),
            "vod_remarks": (it.get("remark") or "").strip()
        }

    def _load_module(self, key, cat_raw, page):
        pc = self._parse_cat(cat_raw)
        if not pc["cat"]:
            pc = self._parse_cat("new|missav|")
        q = f"key={quote(key)}&cat={quote(pc['cat'])}&page={page}"
        if pc["src"]:
            q += f"&src={quote(pc['src'])}"
        if pc["sub"] != "":
            q += f"&sub={quote(pc['sub'])}"
        data = self._api_get("/api/module", q)
        out = []
        for row in (data or {}).get("list") or []:
            v = self._map_item(row, key, pc["src"], pc["sub"])
            if v:
                out.append(v)
        return out