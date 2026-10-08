# coding=utf-8
# 黄果短剧 TVBox 爬虫
# API: https://huangguoai.com
# 封面解密: https://huangguo.wulii.de5.net
# 来源: ForwardWidget Huangguo_TuT.js 转换

import json
from urllib.parse import quote, urlencode
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.api_base = "https://huangguoai.com"
        self.cover_proxy = "https://huangguo.wulii.de5.net"
        self.cover_token = "hg8f3a2c91b7e04d6a"

        # ext 格式: apiBase||coverProxy||coverToken
        if extend:
            parts = [p.strip() for p in extend.strip().split("||")]
            if len(parts) >= 1 and parts[0].startswith("http"):
                self.api_base = parts[0].rstrip("/")
            if len(parts) >= 2 and parts[1]:
                self.cover_proxy = parts[1].rstrip("/")
            if len(parts) >= 3 and parts[2]:
                self.cover_token = parts[2]

        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
            "Referer": "https://huangguoai.com/"
        }

        # 分类映射（tid -> 搜索关键词，空则用热门/最新接口）
        self.cate_map = {
            "hot": "",
            "new": "",
            "rank": "",
            "ai_huanlian": "AI换脸",
            "ai_mogai": "AI魔改",
            "duanju": "短剧",
            "manju": "漫剧",
            "dushi": "都市",
            "xiandai": "现代",
            "xiaoyuan": "校园",
            "xiangcun": "乡村",
            "gufeng": "古风",
            "chuanyue": "穿越",
            "chongsheng": "重生",
            "xitong": "系统",
            "xiuxian": "修仙",
            "hougong": "后宫",
            "zhuixu": "赘婿",
            "nixi": "逆袭",
            "bazong": "霸总",
            "haomen": "豪门",
            "tianchong": "甜宠",
            "nuelian": "虐恋",
            "shunv": "熟女",
            "luanlun": "乱伦",
            "muzi": "母子",
            "renqi": "人妻",
            "juru": "巨乳",
            "heisi": "黑丝",
            "bangongshi": "办公室",
        }

    def getName(self):
        return "黄果"

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        classes = [
            {"type_id": "hot", "type_name": "热门"},
            {"type_id": "new", "type_name": "最新"},
            {"type_id": "rank", "type_name": "排行榜"},
            {"type_id": "ai_huanlian", "type_name": "AI换脸"},
            {"type_id": "ai_mogai", "type_name": "AI魔改"},
            {"type_id": "duanju", "type_name": "短剧"},
            {"type_id": "manju", "type_name": "漫剧"},
            {"type_id": "dushi", "type_name": "都市"},
            {"type_id": "xiandai", "type_name": "现代"},
            {"type_id": "xiaoyuan", "type_name": "校园"},
            {"type_id": "xiangcun", "type_name": "乡村"},
            {"type_id": "gufeng", "type_name": "古风"},
            {"type_id": "chuanyue", "type_name": "穿越"},
            {"type_id": "chongsheng", "type_name": "重生"},
            {"type_id": "xitong", "type_name": "系统"},
            {"type_id": "xiuxian", "type_name": "修仙"},
            {"type_id": "hougong", "type_name": "后宫"},
            {"type_id": "zhuixu", "type_name": "赘婿"},
            {"type_id": "nixi", "type_name": "逆袭"},
            {"type_id": "bazong", "type_name": "霸总"},
            {"type_id": "haomen", "type_name": "豪门"},
            {"type_id": "tianchong", "type_name": "甜宠"},
            {"type_id": "nuelian", "type_name": "虐恋"},
            {"type_id": "shunv", "type_name": "熟女"},
            {"type_id": "luanlun", "type_name": "乱伦"},
            {"type_id": "muzi", "type_name": "母子"},
            {"type_id": "renqi", "type_name": "人妻"},
            {"type_id": "juru", "type_name": "巨乳"},
            {"type_id": "heisi", "type_name": "黑丝"},
            {"type_id": "bangongshi", "type_name": "办公室"},
        ]
        return {"class": classes, "list": []}

    def homeVideoContent(self):
        return self.categoryContent("hot", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        items = self._fetch_list(tid, page)
        videos = [self._to_vod(it) for it in items if it]
        return {
            "list": videos,
            "page": page,
            "pagecount": 999,
            "limit": 24,
            "total": 999999
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else str(ids)
        vid = vid.replace("hgai:", "").split(":")[0]
        if not vid:
            return {"list": []}

        data = self._http_json(f"{self.api_base}/api/videos/{quote(vid)}")
        d = (data or {}).get("data") or {}
        title = (d.get("title") or vid).strip()
        cover = self._proxied_cover(self._abs_cover(d.get("cover") or ""))
        desc = (d.get("description") or "").strip()

        eps = d.get("episodes") if isinstance(d.get("episodes"), list) else []
        play_list = []
        if eps:
            for i, ep in enumerate(eps):
                n = ep.get("ep_num") or ep.get("episode") or (i + 1)
                name = (ep.get("title") or f"第{n}集").strip()
                play_list.append(f"{name}${vid}:{n}")
        else:
            play_list.append(f"第1集${vid}:1")

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": desc,
            "vod_play_from": "黄果",
            "vod_play_url": "#".join(play_list),
            "type_name": "短剧",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": ""
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        items = self._fetch_by_search(key, page, strict_tag=False)
        videos = [self._to_vod(it) for it in items if it]
        return {"list": videos, "page": page}

    def playerContent(self, flag, id, vipFlags):
        # id 格式: videoId:ep  或  纯 videoId
        parts = str(id).replace("hgai:", "").split(":")
        vid = parts[0]
        ep = parts[1] if len(parts) > 1 else "1"
        if not vid:
            return {"parse": 1, "url": id, "header": self.headers}

        data = self._http_json(
            f"{self.api_base}/api/videos/{quote(vid)}/play?ep={quote(str(ep))}"
        )
        url = ""
        if data:
            url = (
                (data.get("data") or {}).get("video_url")
                or data.get("video_url")
                or ""
            )
        url = (url or "").strip()

        if url:
            return {
                "parse": 0,
                "url": url,
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": "https://huangguoai.com/",
                    "X-Forward-Skip-Redirect-Probe": "1"
                }
            }
        return {"parse": 1, "url": id, "header": self.headers}

    # ==================== 内部 ====================

    def _http_json(self, url):
        try:
            r = self.fetch(url, headers=self.headers)
            text = r.text if hasattr(r, "text") else str(r.content)
            return json.loads(text)
        except Exception:
            return None

    def _qs(self, obj):
        parts = []
        for k, v in (obj or {}).items():
            if v is None or v == "":
                continue
            parts.append(f"{quote(str(k))}={quote(str(v))}")
        return ("?" + "&".join(parts)) if parts else ""

    def _abs_cover(self, cover):
        cover = (cover or "").strip()
        if not cover:
            return ""
        if cover.startswith("http://") or cover.startswith("https://"):
            return cover
        if cover.startswith("//"):
            return "https:" + cover
        return self.api_base + ("" if cover.startswith("/") else "/") + cover

    def _proxied_cover(self, enc_url):
        """封面为 AES 密文，必须走解密代理"""
        enc_url = (enc_url or "").strip()
        if not enc_url:
            return ""
        if not self.cover_proxy:
            return enc_url
        q = {"url": enc_url}
        if self.cover_token:
            q["token"] = self.cover_token
        # 结果: https://proxy/?url=xxx&token=yyy
        return self.cover_proxy.rstrip("/") + "/" + self._qs(q)

    def _extract_items(self, data):
        if not data:
            return []
        d = data.get("data") if isinstance(data, dict) and "data" in data else data
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("items", "list", "results"):
                if isinstance(d.get(k), list):
                    return d[k]
        return []

    def _to_vod(self, it):
        if not it:
            return None
        vid = str(it.get("id") or it.get("video_id") or it.get("vod_id") or "").strip()
        if not vid:
            return None
        title = (it.get("title") or it.get("vod_name") or it.get("name") or vid).strip()
        enc = self._abs_cover(it.get("cover") or it.get("vod_pic") or it.get("pic") or "")
        cover = self._proxied_cover(enc)
        ep = it.get("episode_count") or it.get("total_episodes") or ""
        if it.get("is_finished"):
            remark = f"全{ep}集" if ep else "全集"
        elif ep:
            remark = f"更新至{ep}集"
        else:
            remark = ""
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_remarks": remark
        }

    def _fetch_by_search(self, keyword, page, strict_tag=False):
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        page = int(page) or 1
        collected = []
        seen = set()
        max_page = page + 2 if strict_tag else page
        for p in range(page, max_page + 1):
            data = self._http_json(
                f"{self.api_base}/api/search{self._qs({'q': keyword, 'page': p})}"
            )
            batch = self._extract_items(data)
            if not batch:
                break
            for it in batch:
                vid = str(it.get("id") or it.get("video_id") or "").strip()
                if not vid or vid in seen:
                    continue
                if strict_tag:
                    tags = it.get("tags") or []
                    hit = False
                    if isinstance(tags, list):
                        hit = any(str(t) == keyword for t in tags)
                    title = (it.get("title") or "").strip()
                    if not hit and title.startswith(keyword):
                        hit = True
                    if not hit:
                        continue
                seen.add(vid)
                collected.append(it)
            if len(collected) >= 24:
                break
        return collected[:24]

    def _fetch_list(self, tid, page):
        page = int(page) or 1
        tid = (tid or "hot").strip()
        items = []

        # 排行榜
        if tid in ("rank", "ranks"):
            try:
                rank = self._http_json(
                    f"{self.api_base}/api/ranks/hot{self._qs({'page': page})}"
                )
                items = self._extract_items(rank)
            except Exception:
                pass

        # 关键词分类（严格匹配 tag）
        kw = self.cate_map.get(tid)
        if not items and kw:
            items = self._fetch_by_search(kw, page, strict_tag=True)

        # 热门 / 最新
        if not items:
            sort = "new" if tid == "new" else "hot"
            data = self._http_json(
                f"{self.api_base}/api/videos{self._qs({'page': page, 'page_size': 24, 'sort': sort})}"
            )
            items = self._extract_items(data)

        return items