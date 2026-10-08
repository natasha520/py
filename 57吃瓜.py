# coding=utf-8
# 57吃瓜 TVBox 爬虫
# 站点: https://57cg4.com
# 来源: ForwardWidget CG57_TuT.js 转换

import re
from urllib.parse import quote, unquote
from base.spider import Spider

class Spider(Spider):
    def init(self, extend=""):
        self.host = "https://57cg4.com"
        # 可选：封面代理前缀（防盗链），例如 https://images.weserv.nl/?url=
        self.cover_proxy = ""
        if extend:
            # 支持 ext 传 baseUrl 或 coverProxy，格式：baseUrl||coverProxy
            parts = extend.strip().split("||")
            if parts[0].startswith("http"):
                self.host = parts[0].rstrip("/")
            if len(parts) > 1 and parts[1]:
                self.cover_proxy = parts[1].strip()

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/"
        }

    def getName(self):
        return "57吃瓜"

    def isVideoFormat(self, url):
        return bool(re.search(r"\.m3u8|\.mp4", url, re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "hot", "type_name": "热门"},
            {"type_id": "home", "type_name": "首页最新"},
            {"type_id": "jrcg", "type_name": "今日吃瓜"},
            {"type_id": "aichengduanju", "type_name": "成人AI短剧"},
            {"type_id": "mrds", "type_name": "每日大赛"},
            {"type_id": "wanghong", "type_name": "网红黑料"},
            {"type_id": "video", "type_name": "网黄合集"},
            {"type_id": "cheating", "type_name": "出轨劈腿"},
            {"type_id": "live", "type_name": "直播擦边"},
        ]
        result["class"] = classes
        result["list"] = []
        return result

    def homeVideoContent(self):
        return self.categoryContent("hot", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        page = int(pg) if pg else 1
        url = self._list_url(tid, page)
        html = self.fetch(url, headers=self.headers).text
        videos = self._parse_list(html)
        result["list"] = videos
        result["page"] = page
        result["pagecount"] = 999
        result["limit"] = 24
        result["total"] = 999999
        return result

    def detailContent(self, ids):
        result = {}
        id_ = ids[0] if isinstance(ids, list) else str(ids)
        # 兼容 /events/123/ 或纯数字
        m = re.search(r"events/(\d+)", id_)
        if m:
            id_ = m.group(1)
        id_ = re.sub(r"[^0-9]", "", id_)
        if not id_:
            return {"list": []}

        page_url = f"{self.host}/events/{id_}/"
        html = self.fetch(page_url, headers={
            **self.headers,
            "Referer": page_url
        }).text

        title = self._extract_title(html, id_)
        cover = self._wrap_cover(self._extract_cover(html))
        sources = self._extract_play(html)

        # 简介
        desc = ""
        dm = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if dm:
            desc = self._decode_html(dm.group(1))

        # 播放列表
        play_list = []
        for i, s in enumerate(sources):
            name = s.get("name") or "播放"
            if len(sources) > 1:
                name = f"{name}{i + 1}"
            play_list.append(f"{name}${s['url']}")

        # 如果没有直接地址，把详情页交给解析
        if not play_list:
            play_list = [f"正片${page_url}"]

        vod = {
            "vod_id": id_,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": desc,
            "vod_play_from": "57吃瓜",
            "vod_play_url": "#".join(play_list),
            "type_name": "吃瓜",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": ""
        }
        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {}
        page = int(pg) if pg else 1
        url = f"{self.host}/search/?q={quote(key)}"
        if page > 1:
            url += f"&page={page}"
        html = self.fetch(url, headers=self.headers).text
        videos = self._parse_list(html)
        result["list"] = videos
        result["page"] = page
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {}
        url = id.strip()
        # 已是直链
        if re.search(r"\.m3u8|\.mp4", url, re.I) and url.startswith("http"):
            result["parse"] = 0
            result["url"] = url
            result["header"] = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
                "Origin": self.host
            }
            return result

        # 传入的是详情页或 events id，再提取一次
        if re.search(r"events/\d+", url) or url.isdigit():
            m = re.search(r"events/(\d+)", url)
            eid = m.group(1) if m else re.sub(r"[^0-9]", "", url)
            page_url = f"{self.host}/events/{eid}/"
            html = self.fetch(page_url, headers={
                **self.headers,
                "Referer": page_url
            }).text
            sources = self._extract_play(html)
            if sources:
                result["parse"] = 0
                result["url"] = sources[0]["url"]
                result["header"] = {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": page_url,
                    "Origin": self.host
                }
                return result

        # 兜底交给解析
        result["parse"] = 1
        result["url"] = url if url.startswith("http") else f"{self.host}/events/{url}/"
        result["header"] = self.headers
        return result

    # ==================== 内部工具 ====================

    def _list_url(self, category, page):
        page = int(page) if page else 1
        category = (category or "hot").strip()
        if category in ("home", ""):
            return self.host + "/" if page <= 1 else f"{self.host}/page/{page}/"
        path = f"{self.host}/{category}/"
        if page > 1:
            path += f"?page={page}"
        return path

    def _abs_url(self, u):
        u = (u or "").strip()
        if not u:
            return ""
        if re.match(r"^https?://", u, re.I):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return self.host + "/" + u

    def _wrap_cover(self, url):
        url = self._abs_url(url)
        if not url:
            return ""
        proxy = self.cover_proxy
        if not proxy:
            return url
        if re.search(r"[?&](url|u|src)=$", proxy) or proxy.endswith("="):
            return proxy + quote(url, safe="")
        sep = "&url=" if "?" in proxy else "?url="
        return proxy + sep + quote(url, safe="")

    def _decode_html(self, s):
        s = (s or "").strip()
        return (
            s.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&nbsp;", " ")
        )

    def _clean_title(self, title):
        raw = self._decode_html(title)
        if not raw:
            return ""
        prefixes = [
            "AI成人短剧", "成人AI短剧", "每日大赛", "今日吃瓜",
            "网红黑料", "网黄合集", "出轨劈腿", "直播擦边",
            "社会事件", "明星八卦", "热门事件", "热门", "每日大"
        ]
        out = raw
        changed = True
        while changed:
            changed = False
            out = out.strip()
            for p in prefixes:
                if out.startswith(p):
                    out = re.sub(r"^[\s\-_|｜·:：]+", "", out[len(p):])
                    changed = True
                    break
        return out.strip() or raw

    def _parse_list(self, html):
        if not html:
            return []
        out = []
        seen = set()
        # 优先完整 <a href="/events/ID/">...</a>
        for m in re.finditer(r'<a[^>]+href="/events/(\d+)/"[^>]*>([\s\S]*?)</a>', html, re.I):
            eid = m.group(1)
            if eid in seen:
                continue
            body = m.group(0)
            im = re.search(
                r'(?:src|data-src|data-original)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                body, re.I
            )
            if not im:
                im = re.search(
                    r'(?:src|data-src)=["\'](/[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                    body, re.I
                )
            if not im:
                continue  # 无封面跳过
            seen.add(eid)

            title = ""
            tm = re.search(r'alt=["\']([^"\']{2,200})["\']', body, re.I)
            if tm:
                title = tm.group(1)
            if not title:
                tm = re.search(r'title=["\']([^"\']{2,200})["\']', body, re.I)
                if tm:
                    title = tm.group(1)
            if not title:
                tm = re.search(r"<h[123][^>]*>([^<]{2,200})</h", body, re.I)
                if tm:
                    title = tm.group(1)
            title = self._clean_title(title) or f"事件 {eid}"
            cover = self._wrap_cover(im.group(1))

            out.append({
                "vod_id": eid,
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": ""
            })

        # 兜底切分
        if not out:
            parts = re.split(r'(?=<a[^>]+href="/events/\d+/")', html, flags=re.I)
            for p in parts:
                mm = re.search(r'href="/events/(\d+)/"', p, re.I)
                if not mm or mm.group(1) in seen:
                    continue
                eid = mm.group(1)
                im = re.search(
                    r'(?:src|data-src|data-original)="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                    p, re.I
                )
                if not im:
                    continue
                seen.add(eid)
                t2 = re.search(r'alt="([^"]{2,200})"', p, re.I) or re.search(r'title="([^"]{2,200})"', p, re.I)
                title = self._clean_title(t2.group(1)) if t2 else f"事件 {eid}"
                out.append({
                    "vod_id": eid,
                    "vod_name": title,
                    "vod_pic": self._wrap_cover(im.group(1)),
                    "vod_remarks": ""
                })
        return out

    def _extract_play(self, html):
        sources = []
        seen = set()

        def add(url, name):
            url = (url or "").strip()
            if not url or url in seen:
                return
            if not re.match(r"^https?://", url, re.I):
                return
            seen.add(url)
            sources.append({"name": name or "播放", "url": url})

        for u in re.findall(r'https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*', html, re.I):
            add(u, "HLS")
        for u in re.findall(r'https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*', html, re.I):
            add(u, "MP4")
        # json 字段兜底
        for field in re.findall(
            r'["\'](?:url|play_url|playUrl|src|file|video)["\']\s*:\s*["\'](https?://[^"\']+)["\']',
            html, re.I
        ):
            if re.search(r"\.m3u8", field, re.I):
                add(field, "HLS")
            elif re.search(r"\.mp4", field, re.I):
                add(field, "MP4")
        return sources

    def _extract_title(self, html, fallback=""):
        m = re.search(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if m:
            return self._clean_title(m.group(1))
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']', html, re.I)
        if m:
            return self._clean_title(m.group(1))
        m = re.search(r"<h1[^>]*>([^<]{2,200})</h1>", html, re.I)
        if m:
            return self._clean_title(m.group(1))
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            return self._clean_title(re.sub(r"\s*[-|_｜].*57.*", "", m.group(1)).strip())
        return fallback or ""

    def _extract_cover(self, html):
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if m:
            return self._abs_url(m.group(1))
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html, re.I)
        if m:
            return self._abs_url(m.group(1))
        m = re.search(
            r'(?:src|data-src)="(https?://s\.chigua\.media/media/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html, re.I
        )
        if m:
            return m.group(1)
        return ""