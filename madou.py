#!/usr/bin/env python3
# coding=utf-8
"""
麻豆社 TVBox/影视仓 Python Spider  (修复版 v3)
站点: https://madou.club  归档结构: /category/{分类名}

v3 修复:
  1) 补 import os —— 原代码 _http_get_urllib 引用 os.environ 触发 NameError,
     被裸 except 吞掉,导致 urllib 通道(含代理支持)永远静默失败。
  2) 分类 URL 动态解析: 先从首页导航发现真实归档地址并缓存; 发现不到再依次
     回退探测 /category/{名}/(带斜杠优先)、/tag/{名}/、/{名}/, 含小写变体,
     取第一个能解析出视频的地址作为该分类的固定地址。
  3) 列表解析 4 层回退: excerpt 文章块 -> 任意 article 块 -> 缩略图锚点 ->
     扁平 .html 链接整页扫描,兼容任意列表页结构。
  4) detailContent 封面增加 og:image / twitter:image meta 回退。
  5) localProxy 按 TVBox 规范返回 3 元组。
  6) extend 支持 {"host": "...", "debug": true} 打印诊断日志。
"""
import os
import re
import json
import time
import random
import threading
import requests
import urllib3
from urllib.parse import quote

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 常量 ====================
HOST = "https://madou.club"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# TVBox 传的英文 ID -> 站点上的分类名称
CATEGORY_MAP = {
    "home": "home",
    "latest": "home",
    "madou": "麻豆传媒",
    "hkd": "HongKongDoll",
    "guodong": "果冻传媒",
    "mitao": "蜜桃影像",
    "tianmei": "天美传媒",
    "jingdong": "精东影业",
    "jy91": "91制片厂",
    "huangjia": "皇家华人",
    "tuzi": "兔子先生",
    "xingkong": "星空无限传媒",
    "aidou": "爱豆",
    "daoyan": "麻豆导演系列",
    "daxiang": "大象传媒",
    "maozhua": "猫爪影像",
    "xingba": "杏吧",
    "lebo": "乐播传媒",
    "psycho": "PsychoPornTW",
    "fanwai": "麻豆番外篇",
    "huaxu": "麻豆花絮",
}

MODULES = [
    {"type_id": "home", "type_name": "最新"},
    {"type_id": "madou", "type_name": "麻豆传媒"},
    {"type_id": "hkd", "type_name": "HongKongDoll"},
    {"type_id": "guodong", "type_name": "果冻传媒"},
    {"type_id": "mitao", "type_name": "蜜桃影像"},
    {"type_id": "tianmei", "type_name": "天美传媒"},
    {"type_id": "jingdong", "type_name": "精东影业"},
    {"type_id": "jy91", "type_name": "91制片厂"},
    {"type_id": "huangjia", "type_name": "皇家华人"},
    {"type_id": "tuzi", "type_name": "兔子先生"},
    {"type_id": "xingkong", "type_name": "星空无限传媒"},
    {"type_id": "aidou", "type_name": "爱豆"},
    {"type_id": "daoyan", "type_name": "麻豆导演系列"},
    {"type_id": "daxiang", "type_name": "大象传媒"},
    {"type_id": "maozhua", "type_name": "猫爪影像"},
    {"type_id": "xingba", "type_name": "杏吧"},
    {"type_id": "lebo", "type_name": "乐播传媒"},
    {"type_id": "psycho", "type_name": "PsychoPornTW"},
    {"type_id": "fanwai", "type_name": "麻豆番外篇"},
    {"type_id": "huaxu", "type_name": "麻豆花絮"},
]

CACHE_TTLS = {"list": 300, "detail": 180, "home": 300, "search": 120, "play": 60}

_RE_ARTICLE_EXCERPT = re.compile(r'<article[^>]*class="[^"]*excerpt[^"]*"[^>]*>[\s\S]*?<\/article>', re.I)
_RE_ARTICLE_ANY = re.compile(r'<article[^>]*>[\s\S]*?<\/article>', re.I)
_RE_THUMB_HREF = re.compile(r'<a[^>]+class="[^"]*(?:thumbnail|thumb|pic|img)[^"]*"[^>]+href="([^"]+)"', re.I)
_RE_TITLE = re.compile(r'<h2[^>]*>\s*<a[^>]*>([^<]+)<\/a>', re.I)
_RE_IMG = re.compile(r'(?:data-src|data-original|data-thumb|src)=["\']([^"\']+)["\']', re.I)
_RE_IFRAME_SRC = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
_RE_VAR_TOKEN = re.compile(r'var\s+token\s*=\s*["\']([^"\']*)["\']', re.I)
_RE_VAR_M3U8 = re.compile(r'var\s+m3u8\s*=\s*["\']([^"\']+)["\']', re.I)

_IMG_EXT = re.compile(r'-\d+x\d+(\.(?:jpg|jpeg|png|webp))', re.I)
_JUNK_IMG = re.compile(r'thumb\.png|logo\.png|avatar|loading|placeholder|blank|grey|gray', re.I)


def _rand_device():
    hex_chars = "0123456789abcdef"
    return "h5:" + "".join(hex_chars[int(random.random() * 16)] for _ in range(32))


def _clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _abs_url(base, url):
    url = _clean(url)
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return base.rstrip("/") + "/" + url.lstrip("/")


def _decode_html(s):
    s = _clean(s)
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))


class Spider:
    def __init__(self):
        self.name = "麻豆社"
        self.host = HOST
        self.ua = UA
        self.debug = False
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=30, pool_maxsize=30)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._cache = {}
        self._cache_lock = threading.Lock()
        # 分类真实归档地址表: tid -> url (首页导航发现 + 回退探测, 成功后缓存)
        self._cat_urls = {}
        self._cat_lock = threading.Lock()
        self._home_html = ("", 0.0)

    # ==================== TVBox 生命周期 ====================
    def getDependence(self):
        return []

    def destroy(self):
        try:
            self._session.close()
        except Exception:
            pass

    def getName(self):
        return self.name

    def init(self, extend=""):
        self.debug = False
        if extend:
            ext = _clean(extend)
            if ext.startswith("{"):
                try:
                    d = json.loads(ext)
                    self.host = str(d.get("host", self.host)).rstrip("/")
                    self.debug = bool(d.get("debug", False))
                except Exception:
                    pass

    def homeContent(self, filter):
        return {"class": MODULES, "filters": {}}

    def homeVideoContent(self):
        html = self._get_home_html()
        videos = self._parse_list_html(html)
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1
        except Exception:
            page = 1

        tid = str(tid)
        if tid in ("home", "latest", ""):
            url = self.host + "/" if page <= 1 else self.host + "/page/%d/" % page
            html = self._http_get(url)
            videos = self._parse_list_html(html) if html else []
            pagecount = self._parse_total_pages(html) if html else 0
            if pagecount <= 0:
                pagecount = page + 1 if videos else page
            return {"page": page, "pagecount": pagecount, "limit": len(videos),
                    "total": pagecount * 20, "list": videos}

        base_url = self._resolve_category_url(tid)
        if not base_url:
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        url = base_url if page <= 1 else base_url.rstrip("/") + "/page/%d/" % page
        html = self._http_get(url)
        videos = self._parse_list_html(html) if html else []

        # 该分类首页都解析不出东西 -> 换下一个候选地址重试一次
        if page == 1 and not videos:
            alt = self._resolve_category_url(tid, force_next=True)
            if alt and alt != base_url:
                html = self._http_get(alt)
                videos = self._parse_list_html(html) if html else []
                if videos:
                    url = alt

        pagecount = self._parse_total_pages(html) if html else 0
        if pagecount <= 0:
            pagecount = page + 1 if videos else page
        return {"page": page, "pagecount": pagecount, "limit": len(videos),
                "total": pagecount * 20, "list": videos}

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        raw_id = _clean(ids)
        if not raw_id:
            return {"list": []}

        url = raw_id if raw_id.startswith("http") else self.host + "/" + raw_id.lstrip("/")

        cache_key = ("detail", url)
        with self._cache_lock:
            hit = self._cache.get(cache_key)
            if hit and time.time() - hit[0] < CACHE_TTLS["detail"]:
                return hit[1]

        html = self._http_get(url)
        if not html:
            return {"list": []}

        # 标题: 多层回退
        title = ""
        m = re.search(r'<h1[^>]+class="[^"]*article-title[^"]*"[^>]*>([^<]+)', html, re.I)
        if not m:
            m = re.search(r'<h1[^>]*>([^<]{2,200})<\/h1>', html, re.I)
        if not m:
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
        if not m:
            m = re.search(r'<title>([^<]+)<\/title>', html, re.I)
        if m:
            title = _decode_html(m.group(1).replace("—", "-").split("-")[0].split("|")[0])

        # 封面: og:image -> twitter:image -> /covers/ 大图 -> 首个 img
        cover = ""
        for pat in (r'<meta\s+property="og:image"\s+content="([^"]+)"',
                    r'<meta\s+name="twitter:image"\s+content="([^"]+)"'):
            cm = re.search(pat, html, re.I)
            if cm:
                cover = _abs_url(self.host, _IMG_EXT.sub(r'\1', cm.group(1)))
                if cover:
                    break
        if not cover:
            cm = re.search(r'(?:data-src|src)=["\'](https?:\/\/[^"\']*\/covers\/[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
            if cm:
                cover = _abs_url(self.host, _IMG_EXT.sub(r'\1', cm.group(1)))
        if not cover:
            m = re.search(r'<img[^>]+(?:data-src|src)="([^"]+)"', html, re.I)
            if m and not _JUNK_IMG.search(m.group(1)):
                cover = _abs_url(self.host, m.group(1))

        share_url = self._extract_share_url(html)
        play_link = share_url if share_url else url

        vod = {
            "vod_id": raw_id,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": "",
            "vod_play_from": "麻豆社",
            "vod_play_url": "播放$" + play_link,
        }
        result = {"list": [vod]}
        with self._cache_lock:
            self._cache[cache_key] = (time.time(), result)
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
            if page < 1:
                page = 1
        except Exception:
            page = 1

        keyword = _clean(key)
        if not keyword:
            return {"page": page, "pagecount": page, "limit": 0, "total": 0, "list": []}

        url = (self.host + "/?s=" + quote(keyword)) if page <= 1 \
            else self.host + "/page/%d/?s=%s" % (page, quote(keyword))
        html = self._http_get(url)
        videos = self._parse_list_html(html) if html else []
        pagecount = self._parse_total_pages(html) if html else 0
        if pagecount <= 0:
            pagecount = page + 1 if videos else page
        return {"page": page, "pagecount": pagecount, "limit": len(videos),
                "total": pagecount * 20, "list": videos}

    def playerContent(self, flag, id, vipFlags):
        play_url = _clean(id)
        if not play_url:
            return {"parse": 1, "url": "", "header": {}}

        header = {"User-Agent": self.ua, "Referer": self.host + "/"}

        # 直链 -> 直接播
        if play_url.startswith("http") and any(ext in play_url.lower() for ext in (".m3u8", ".mp4", ".flv")):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": play_url, "header": header}

        # dash 分享页 -> 解析 var token / var m3u8
        if "madou.club/share/" in play_url:
            play_data = self._resolve_play_from_share(play_url)
            if play_data and play_data.get("url"):
                h = dict(header)
                h["Origin"] = "https://dash.madou.club"
                return {"parse": 0, "jx": 0, "playUrl": "", "url": play_data["url"], "header": h}

        return {"parse": 1, "jx": 0, "playUrl": "", "url": play_url, "header": header}

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(ext in url.lower() for ext in (".m3u8", ".mp4", ".flv", ".ts", ".mkv"))

    def manualVideoCheck(self):
        return True

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def action(self, action):
        return {}

    # ==================== 分类地址解析(核心修复) ====================
    def _resolve_category_url(self, tid, force_next=False):
        """返回分类归档页基础地址; force_next=True 时跳过已缓存地址换下一个候选。"""
        with self._cat_lock:
            cached = self._cat_urls.get(tid)
        if cached and not force_next:
            return cached

        slug = CATEGORY_MAP.get(tid, tid)
        candidates = []

        # 1. 从首页导航/侧栏发现真实地址 (最可靠: 站点自己怎么链就怎么抓)
        nav = self._discover_nav_urls()
        if tid in nav:
            candidates.append(nav[tid])

        # 2. 常见归档路径回退 (带斜杠优先 + 小写变体, 兼容严格的路由配置)
        names = [slug]
        if slug.lower() not in names:
            names.append(slug.lower())
        for name in names:
            q = quote(name)
            for cand in ("/category/" + q + "/", "/category/" + q,
                         "/tag/" + q + "/", "/tag/" + q,
                         "/" + q + "/"):
                u = self.host + cand
                if u not in candidates:
                    candidates.append(u)

        if force_next and cached and cached in candidates:
            idx = candidates.index(cached)
            candidates = candidates[idx + 1:]

        for u in candidates:
            try:
                html = self._http_get(u, timeout=15)
            except Exception:
                html = ""
            if not html:
                continue
            if self._parse_list_html(html):
                with self._cat_lock:
                    self._cat_urls[tid] = u
                return u
        return ""

    def _discover_nav_urls(self):
        """解析首页导航菜单, 建立 tid -> 归档地址 映射 (带 1h 缓存)。"""
        now = time.time()
        if now - self._home_html[1] < 3600 and self._home_html[0]:
            html = self._home_html[0]
        else:
            html = self._http_get(self.host + "/", timeout=15)
            self._home_html = (html, now)
        found = {}
        if not html:
            return found
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]{1,80}?)<\/a>', html, re.I):
            href, inner = m.group(1), m.group(2)
            text = _decode_html(re.sub(r'<[^>]+>', '', inner))
            if not text:
                continue
            for tid, slug in CATEGORY_MAP.items():
                if tid in ("home", "latest"):
                    continue
                if tid in found:
                    continue
                if text == slug or text.lower() == slug.lower():
                    if href.startswith("/") or self.host.split("//")[-1].split("/")[0] in href:
                        found[tid] = _abs_url(self.host, href)
        return found

    # ==================== HTTP ====================
    def _get_home_html(self):
        now = time.time()
        if now - self._home_html[1] < CACHE_TTLS["home"] and self._home_html[0]:
            return self._home_html[0]
        html = self._http_get(self.host + "/")
        self._home_html = (html, now)
        return html

    def _http_get(self, url, timeout=20):
        """urllib 优先(支持环境变量代理), requests 兜底; 全程异常返回空串。"""
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
        }
        try:
            import ssl
            import urllib.request
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers)
            proxy_host = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
            if proxy_host:
                proxy = urllib.request.ProxyHandler({"https": proxy_host, "http": proxy_host})
                opener = urllib.request.build_opener(proxy, urllib.request.HTTPSHandler(context=ctx))
            else:
                opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            with opener.open(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        err = ""
        try:
            r = self._session.get(url, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200:
                if self.debug:
                    arts = len(_RE_ARTICLE_ANY.findall(r.text))
                    print("[麻豆][net] 200 %s | %dB | article=%d | html链接=%d" %
                          (url, len(r.text), arts, len(re.findall(r'\.html"', r.text))))
                return r.text
            err = "HTTP %d" % r.status_code
        except Exception as e:
            err = type(e).__name__
        if self.debug:
            print("[麻豆][net] FAIL %s | %s" % (url, err))
        return ""

    # ==================== 解析 ====================
    def _parse_list_html(self, html):
        if not html:
            return []
        if self.debug:
            print("[麻豆][parse] excerpt块=%d article块=%d" %
                  (len(_RE_ARTICLE_EXCERPT.findall(html)), len(_RE_ARTICLE_ANY.findall(html))))
        videos = []
        seen = set()

        # 4 层回退: excerpt 文章块 -> 任意 article 块 -> 缩略图锚点块 -> 扁平 .html 链接
        blocks = _RE_ARTICLE_EXCERPT.findall(html)
        if not blocks:
            blocks = _RE_ARTICLE_ANY.findall(html)
        if not blocks:
            blocks = [m.group(0) for m in re.finditer(
                r'<a[^>]+class="[^"]*(?:thumbnail|thumb|pic|img)[^"]*"[^>]*>[\s\S]{0,600}?</a>', html, re.I)]
        if not blocks:
            blocks = [m.group(0) for m in re.finditer(
                r'<a[^>]+href="(?:https?://[^/"]+)?/[^"/]+\.html"[^>]*>[\s\S]{0,500}?</a>', html, re.I)]

        for block in blocks:
            link = ""
            m = _RE_THUMB_HREF.search(block)
            if not m:
                m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"', block, re.I)
            if not m:
                m = re.search(r'href="((?:https?://[^"\']+)?/[^"\']+?\.html)"', block, re.I)
            if not m:
                continue
            link = _abs_url(self.host, m.group(1))
            if not link or link in seen:
                continue
            seen.add(link)

            title = ""
            m = _RE_TITLE.search(block)
            if m:
                title = _decode_html(m.group(1))
            if not title:
                m = re.search(r'title="([^"]+)"', block, re.I)
                if m:
                    title = _decode_html(m.group(1))
            if not title:
                m = re.search(r'alt="([^"]+)"', block, re.I)
                if m:
                    title = _decode_html(m.group(1))
            if not title:
                title = link.rsplit("/", 1)[-1]

            cover = ""
            for m in _RE_IMG.finditer(block):
                u = m.group(1)
                if not u or _JUNK_IMG.search(u):
                    continue
                cover = _abs_url(self.host, _IMG_EXT.sub(r'\1', u))
                if cover:
                    break

            videos.append({"vod_id": link, "vod_name": title, "vod_pic": cover, "vod_remarks": ""})

        return videos

    def _extract_share_url(self, html):
        for m in _RE_IFRAME_SRC.finditer(html):
            src = m.group(1)
            if "madou.club/share/" in src:
                return src
        m = re.search(r'https?://[a-z0-9.-]*madou\.club/share/[a-zA-Z0-9]+', html, re.I)
        if m:
            return m.group(0)
        return ""

    def _resolve_play_from_share(self, share_url):
        if not share_url:
            return None
        try:
            html = self._http_get(share_url)
            if not html:
                return None
            token_m = _RE_VAR_TOKEN.search(html)
            m3u8_m = _RE_VAR_M3U8.search(html)
            if not m3u8_m:
                return None
            path = m3u8_m.group(1)
            dm = re.match(r'^(https?://[^/]+)', share_url, re.I)
            dash_base = dm.group(1) if dm else "https://dash.madou.club"
            if path.startswith("/"):
                path = dash_base + path
            elif not re.match(r'^https?://', path, re.I):
                path = dash_base.rstrip("/") + "/" + path.lstrip("/")
            token = token_m.group(1) if token_m else ""
            if token:
                path += ("&" if "?" in path else "?") + "token=" + token
            return {"url": path}
        except Exception:
            return None

    def _parse_total_pages(self, html):
        if not html:
            return 0
        nums = re.findall(r'/page/(\d+)/', html)
        if nums:
            try:
                return max(int(p) for p in nums)
            except Exception:
                pass
        return 0


if __name__ == "__main__":
    s = Spider()
    print("站点:", s.name, "| 分类数:", len(MODULES))