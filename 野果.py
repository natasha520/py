# coding=utf-8
# 野果短剧 TVBox 爬虫
# 站点: https://yeguodj.com
# API: https://www.yeguodj.com/api.php （AES-CBC 响应）
# 封面: 需解密代理


import json
import base64
from urllib.parse import quote
from base.spider import Spider

try:
    from Crypto.Cipher import AES
except Exception:
    try:
        from Cryptodome.Cipher import AES
    except Exception:
        AES = None


class Spider(Spider):
    def init(self, extend=""):
        self.api_base = "https://www.yeguodj.com/api.php"
        self.cover_proxy = "https://huangguo.wulii.de5.net"
        self.cover_token = "hg8f3a2c91b7e04d6a"

        # ext: apiBase||coverProxy||coverToken
        if extend:
            parts = [p.strip() for p in extend.strip().split("||")]
            if len(parts) >= 1 and parts[0].startswith("http"):
                self.api_base = parts[0].rstrip("/")
            if len(parts) >= 2 and parts[1]:
                self.cover_proxy = parts[1].rstrip("/")
            if len(parts) >= 3 and parts[2]:
                self.cover_token = parts[2]

        self.api_key = b"2acf7e91e9864673"
        self.api_iv = b"1c29882d3ddfcfd6"

        self.ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://yeguodj.com/",
            "Origin": "https://yeguodj.com"
        }

        # 分类: tid -> (mode, value)  mode=bg 用 background, setting 用 setting
        self.cate_map = {
            "home": ("home", None),
            "explore": ("explore", None),
            "rank": ("rank", None),
            "dushi": ("bg", 40),
            "xiandai": ("bg", 39),
            "xiaoyuan": ("bg", 47),
            "gudai": ("bg", 41),
            "xiangcun": ("bg", 42),
            "zhichang": ("bg", 44),
            "chongsheng": ("setting", 26),
            "chuanyue": ("setting", 27),
            "xitong": ("setting", 28),
            "nixi": ("setting", 53),
            "mogai": ("setting", 56),
        }

    def getName(self):
        return "野果短剧"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        classes = [
            {"type_id": "home", "type_name": "首页推荐"},
            {"type_id": "explore", "type_name": "发现"},
            {"type_id": "rank", "type_name": "排行榜"},
            {"type_id": "dushi", "type_name": "都市"},
            {"type_id": "xiandai", "type_name": "现代"},
            {"type_id": "xiaoyuan", "type_name": "校园"},
            {"type_id": "gudai", "type_name": "古代"},
            {"type_id": "xiangcun", "type_name": "乡村"},
            {"type_id": "zhichang", "type_name": "职场"},
            {"type_id": "chongsheng", "type_name": "重生"},
            {"type_id": "chuanyue", "type_name": "穿越"},
            {"type_id": "xitong", "type_name": "系统"},
            {"type_id": "nixi", "type_name": "逆袭"},
            {"type_id": "mogai", "type_name": "魔改"},
        ]
        return {"class": classes, "list": []}

    def homeVideoContent(self):
        return self.categoryContent("home", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = self._fetch_list(tid, page)
        videos = [v for v in (self._to_vod(it) for it in items) if v]
        return {
            "list": videos,
            "page": page,
            "pagecount": 999,
            "limit": 24,
            "total": 999999
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else str(ids)
        p = self._parse_link(raw)
        if not p["id"]:
            return {"list": []}

        d = self._api_post("/api/playlet/detail", {
            "video_id": self._num_or_str(p["id"])
        })
        info = self._unwrap(d)
        if info.get("video_id") is None and isinstance(info.get("data"), dict):
            info = info["data"]

        title = (info.get("title") or p["id"]).strip()
        cover = self._proxied_cover(
            (info.get("cover") or info.get("cover_img") or "").strip()
        )
        desc = (info.get("description") or info.get("intro") or "").strip()

        eps = info.get("episodes") if isinstance(info.get("episodes"), list) else []
        play_list = []
        if eps:
            for i, ep in enumerate(eps):
                n = ep.get("sort") or ep.get("episode") or (i + 1)
                eid = str(ep.get("id") or ep.get("episode_id") or "").strip()
                name = (ep.get("title") or f"第{n}集").strip()
                # 格式: videoId:集序号:episodeId
                play_id = f"{p['id']}:{n}" + (f":{eid}" if eid else "")
                play_list.append(f"{name}${play_id}")
        else:
            play_list.append(f"第1集${p['id']}:1")

        vod = {
            "vod_id": p["id"],
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": desc,
            "vod_play_from": "野果",
            "vod_play_url": "#".join(play_list),
            "type_name": "短剧",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        d = self._api_post("/api/search/result", {
            "keyword": key,
            "page": page
        })
        items = self._list_from_payload(d.get("data") if d else None)
        videos = [v for v in (self._to_vod(it) for it in items) if v]
        return {"list": videos, "page": page}

    def playerContent(self, flag, id, vipFlags):
        p = self._parse_link(id)
        if not p["id"]:
            return {"parse": 1, "url": id, "header": self.headers}

        ep = p["ep"] or "1"
        episode_id = p["episodeId"]

        # 没有 episode_id 时从详情反查
        if not episode_id:
            try:
                det = self._api_post("/api/playlet/detail", {
                    "video_id": self._num_or_str(p["id"])
                })
                info0 = self._unwrap(det)
                if info0.get("video_id") is None and isinstance(info0.get("data"), dict):
                    info0 = info0["data"]
                eps0 = info0.get("episodes") if isinstance(info0.get("episodes"), list) else []
                for i, e0 in enumerate(eps0):
                    if (
                        str(e0.get("sort")) == str(ep)
                        or str(e0.get("episode")) == str(ep)
                        or str(i + 1) == str(ep)
                    ):
                        episode_id = str(e0.get("id") or e0.get("episode_id") or "").strip()
                        break
                if not episode_id and eps0:
                    episode_id = str(eps0[0].get("id") or eps0[0].get("episode_id") or "").strip()
            except Exception:
                pass

        body = {"video_id": self._num_or_str(p["id"])}
        if episode_id:
            body["episode_id"] = self._num_or_str(episode_id)
        else:
            body["ep"] = self._num_or_str(ep)

        d = self._api_post("/api/playlet/play", body)
        info = self._unwrap(d)
        if info.get("video_url") is None and isinstance(info.get("data"), dict):
            info = info["data"]

        url = (info.get("video_url") or info.get("video_url_h265") or "").strip()
        if not url and isinstance(info.get("episodeAll"), list):
            for e in info["episodeAll"]:
                if str(e.get("id")) == str(episode_id) or str(e.get("sort") or e.get("index")) == str(ep):
                    url = (e.get("video_url") or "").strip()
                    break

        if url:
            return {
                "parse": 0,
                "url": url,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": "https://yeguodj.com/",
                    "Origin": "https://yeguodj.com",
                    "X-Forward-Skip-Redirect-Probe": "1"
                }
            }
        return {"parse": 1, "url": id, "header": self.headers}

    # ==================== 内部 ====================

    def _num_or_str(self, v):
        s = str(v).strip()
        try:
            return int(s)
        except Exception:
            return s

    def _aes_cbc_decrypt(self, b64_text):
        if AES is None:
            raise Exception("缺少 Crypto 库，无法解密 API")
        raw = base64.b64decode(b64_text)
        cipher = AES.new(self.api_key, AES.MODE_CBC, self.api_iv)
        plain = cipher.decrypt(raw)
        # PKCS7 unpad
        pad = plain[-1]
        if isinstance(pad, str):
            pad = ord(pad)
        if 1 <= pad <= 16:
            plain = plain[:-pad]
        return plain.decode("utf-8", errors="ignore")

    def _api_post(self, path, body=None):
        url = self.api_base.rstrip("/") + path
        payload = body or {}
        try:
            r = self.post(url, headers=self.headers, data=json.dumps(payload, ensure_ascii=False))
            text = r.text if hasattr(r, "text") else str(r.content)
        except Exception:
            # 部分环境 post 签名不同，再试 fetch + 手动
            try:
                r = self.fetch(url, headers=self.headers, method="POST", data=json.dumps(payload))
                text = r.text if hasattr(r, "text") else str(r.content)
            except Exception as e:
                raise Exception(f"请求失败: {path} {e}")

        try:
            d = json.loads(text)
        except Exception:
            raise Exception(f"非 JSON 响应: {path}")

        # 加密 data 字段
        if isinstance(d.get("data"), str) and len(d["data"]) > 20:
            try:
                plain = self._aes_cbc_decrypt(d["data"])
                d["data"] = json.loads(plain)
            except Exception as e:
                raise Exception(f"API 解密失败: {e}")
        return d

    def _unwrap(self, d):
        if not d:
            return {}
        x = d.get("data") if isinstance(d, dict) and "data" in d else d
        if isinstance(x, dict) and isinstance(x.get("data"), dict):
            return x["data"]
        return x if isinstance(x, dict) else {}

    def _qs(self, obj):
        parts = []
        for k, v in (obj or {}).items():
            if v is None or v == "":
                continue
            parts.append(f"{quote(str(k))}={quote(str(v))}")
        return ("?" + "&".join(parts)) if parts else ""

    def _proxied_cover(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not self.cover_proxy:
            return url
        q = {"url": url}
        if self.cover_token:
            q["token"] = self.cover_token
        return self.cover_proxy.rstrip("/") + "/" + self._qs(q)

    def _to_vod(self, it):
        if not it:
            return None
        vid = str(it.get("video_id") if it.get("video_id") is not None else it.get("id") or "").strip()
        if not vid:
            return None
        title = (it.get("title") or it.get("video_title") or it.get("name") or vid).strip()
        cover = self._proxied_cover(
            (it.get("cover") or it.get("cover_img") or it.get("pic") or "").strip()
        )
        ep = it.get("episode_count") or it.get("episodes") or it.get("total_serial") or ""
        remark = (it.get("update_status") or it.get("serialize_status_text") or "").strip()
        if not remark and ep:
            remark = f"更新至{ep}集"
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_remarks": remark
        }

    def _list_from_payload(self, data):
        inner = self._unwrap({"data": data}) if not isinstance(data, list) else {}
        if isinstance(data, list):
            arr = data
        else:
            arr = (
                (inner.get("list") if isinstance(inner, dict) else None)
                or (inner.get("top_list") if isinstance(inner, dict) else None)
                or (inner if isinstance(inner, list) else [])
            )
        if not isinstance(arr, list):
            # 再试原始 data
            if isinstance(data, dict):
                arr = data.get("list") or data.get("top_list") or []
            else:
                arr = []
        return arr if isinstance(arr, list) else []

    def _parse_link(self, link):
        s = str(link or "").strip().replace("yeguodj:", "yeguo:")
        if s.startswith("yeguo:"):
            s = s[6:]
        parts = s.split(":")
        return {
            "id": (parts[0] if parts else "").strip(),
            "ep": (parts[1] if len(parts) > 1 else "").strip(),
            "episodeId": (parts[2] if len(parts) > 2 else "").strip()
        }

    def _fetch_list(self, tid, page):
        page = int(page) or 1
        tid = (tid or "home").strip()
        mode, val = self.cate_map.get(tid, ("explore", None))

        if mode == "home":
            if page > 1:
                d = self._api_post("/api/theater/exploreList", {"page": page, "limit": 24})
                return self._list_from_payload(d.get("data") if d else None)
            d = self._api_post("/api/home/homePage", {})
            inner = self._unwrap(d)
            lst = list(inner.get("top_list") or [])
            mods = (inner.get("modules") or {}).get("list") or []
            for m in mods:
                if isinstance(m, dict) and isinstance(m.get("list"), list):
                    lst.extend(m["list"])
                elif isinstance(m, dict) and m.get("video_id"):
                    lst.append(m)
            # 去重
            seen = set()
            out = []
            for it in lst:
                v = self._to_vod(it)
                if not v or v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                out.append(it)
            return out

        if mode == "rank":
            d = self._api_post("/api/theater/videoRank", {"page": page, "limit": 24})
            return self._list_from_payload(d.get("data") if d else None)

        if mode == "bg":
            body = {"page": page, "limit": 24, "background": val}
            d = self._api_post("/api/theater/exploreList", body)
            return self._list_from_payload(d.get("data") if d else None)

        if mode == "setting":
            body = {"page": page, "limit": 24, "setting": val}
            d = self._api_post("/api/theater/exploreList", body)
            return self._list_from_payload(d.get("data") if d else None)

        # explore 默认
        d = self._api_post("/api/theater/exploreList", {"page": page, "limit": 24})
        return self._list_from_payload(d.get("data") if d else None)