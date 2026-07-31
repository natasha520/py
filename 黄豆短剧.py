# -*- coding: utf-8 -*-
import gzip
import hashlib
import hmac
import json
import os
import time
import uuid
import requests

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

class _AESCBC:
    @staticmethod
    def encrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).encrypt(_AESCBC.pad(data))
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            enc = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).encryptor()
            return enc.update(_AESCBC.pad(data)) + enc.finalize()

    @staticmethod
    def decrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            plain = dec.update(data) + dec.finalize()
        return _AESCBC.unpad(plain)

    @staticmethod
    def pad(data):
        n = 16 - len(data) % 16
        return data + bytes([n]) * n

    @staticmethod
    def unpad(data):
        n = data[-1] if data else 0
        return data[:-n] if 1 <= n <= 16 else data

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://hdmgdj.com/"
        self.api = self.host + "/api"
        self.name = "黄豆短剧"
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"
        self.session_id = uuid.uuid4().hex
        self.device_id = self.session_id
        self.token = ""
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "*/*", "Origin": self.host, "Referer": self.host + "/home", "Content-Type": "application/octet-stream"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.class_cache = None
        self.filter_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("base_url") or self.host).rstrip("/")
                self.api = self.host + "/api"
                self.token = cfg.get("token", self.token)
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/home"
                self.session.headers.update(self.headers)
            except Exception:
                None

    def getName(self):
        return self.name

    def homeContent(self, filter):
        data = self._api("/drama/list", {"page": "1", "page_size": "18"})
        classes = self._classes()
        return {"class": classes, "filters": self._filters(classes), "list": [self._vod(x) for x in self._list(data)], "parse": 0, "jx": 0}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        if tid == "yuandou":
            data = self._api("/drama/navBlock", {"code": "yuandou", "tab": "recommend", "page": str(pg)})
            items = self._nav_items(data)
        else:
            req = {"page": str(pg), "page_size": "18"}
            if tid and tid not in ("all", "recommend"):
                tabs = self._nav_filter(tid)
                idx = self._int(extend.get("sub"), 0)
                sub = tabs[idx] if tabs and 0 <= idx < len(tabs) else {}
                flt = sub.get("filter", {}) if isinstance(sub, dict) else {}
                req["cat_id"] = flt.get("cat_id", "")
                if flt.get("tag_id"):
                    req["tag_id"] = flt.get("tag_id", "")
                req["order"] = flt.get("order", "") or extend.get("order", "")
            elif extend.get("order"):
                req["order"] = extend.get("order")
            if extend.get("update_status"):
                req["update_status"] = extend.get("update_status")
            data = self._api("/drama/list", req)
            items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def detailContent(self, ids):
        vid = str(ids[0]).replace("rp_", "")
        obj = self._api("/drama/detail", {"id": vid})
        data = obj.get("data", obj) if isinstance(obj, dict) else {}
        if not isinstance(data, dict):
            return {"list": []}
        data = self._unlock(data)
        vod_id = self._sid(data.get("id") or data.get("drama_id") or vid)
        name = data.get("name") or data.get("title") or data.get("t") or vod_id
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        count = self._int(data.get("episode_count") or data.get("free_episodes"), len(eps) or 1)
        play = []
        if eps:
            for i, ep in enumerate(eps, 1):
                seq = ep.get("seq") or ep.get("episode") or ep.get("ep") or i
                play.append("%s$%s|%s" % (ep.get("name") or ep.get("title") or "第%s集" % seq, vod_id, seq))
        else:
            play = ["第%s集$%s|%s" % (i, vod_id, i) for i in range(1, count + 1)]
        vod = {"vod_id": vod_id, "vod_name": name, "vod_pic": self._pic(data), "type_name": data.get("category") or data.get("type") or "", "vod_year": "", "vod_area": "", "vod_remarks": data.get("update_label") or "全%s集" % count, "vod_actor": "", "vod_director": "", "vod_content": data.get("description") or data.get("summary") or name, "vod_play_from": self.name, "vod_play_url": "#".join(play)}
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        data = self._api("/drama/list", {"page": str(pg), "page_size": "18", "keywords": str(key)})
        items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags):
        vid, seq = self._split(id)
        obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, True)
        data = obj.get("data", {}) if isinstance(obj, dict) else {}
        url = data.get("m3u8") or data.get("url") or self._hls(vid, seq)
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/home", "Origin": self.host}}

    def _api(self, path, data=None, silent=False):
        path = "/" + path.lstrip("/")
        rid = str(uuid.uuid4())
        key = self._key(rid)
        iv = os.urandom(16)
        raw = json.dumps({"token": self.token or "", "deviceId": self.device_id, "data": data or {}}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body = iv + _AESCBC.encrypt(gzip.compress(raw), key, iv)
        ts = int(time.time())
        sign = hashlib.sha256(("Dart|%s|%s|%s|%s" % (self.session_id, rid, ts, path)).encode("utf-8")).hexdigest() + "-" + str(ts)
        h = dict(self.headers)
        h.update({"version": self.version, "deviceType": self.device_type, "time": str(ts), "sign": sign, "requestId": rid, "sessionId": self.session_id, "deviceBrand": "", "deviceModel": "", "systemName": "", "systemVersion": ""})
        try:
            r = self.session.post(self.api + path, data=body, headers=h, timeout=20, verify=False)
            r.raise_for_status()
            return self._decode(r.content, rid)
        except Exception:
            return {}

    def _key(self, rid):
        return hmac.new(self.platform_key.encode("utf-8"), bytes.fromhex(str(rid).replace("-", "")), hashlib.sha256).digest()

    def _decode(self, blob, rid):
        if not blob or len(blob) < 32 or (len(blob) - 16) % 16 != 0:
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                return {}
        plain = _AESCBC.decrypt(blob[16:], self._key(rid), blob[:16])
        if plain[:2] == b"\x1f\x8b":
            plain = gzip.decompress(plain)
        return json.loads(plain.decode("utf-8"))

    def _classes(self):
        if self.class_cache:
            return self.class_cache
        arr = [{"type_id": "all", "type_name": "全部短剧"}]
        data = self._api("/drama/navList", {})
        for item in self._list(data.get("data", data) if isinstance(data, dict) else data):
            tid = str(item.get("code") or item.get("id") or item.get("cat_id") or "")
            name = item.get("name") or item.get("title") or tid
            if tid and name:
                arr.append({"type_id": tid, "type_name": name})
        self.class_cache = arr
        return arr

    def _filters(self, classes):
        common = [{"key": "order", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}, {"key": "update_status", "name": "状态", "value": [{"n": "全部", "v": ""}, {"n": "连载", "v": "0"}, {"n": "完结", "v": "1"}]}]
        fs = {}
        for c in classes:
            tid = c["type_id"]
            tabs = self._nav_filter(tid) if tid not in ("all", "yuandou") else []
            fs[tid] = ([{"key": "sub", "name": "子分类", "value": [{"n": t.get("name", "默认"), "v": str(i)} for i, t in enumerate(tabs)]}] if tabs else []) + common
        return fs

    def _nav_filter(self, code):
        if code not in self.filter_cache:
            data = self._api("/drama/navFilter", {"code": str(code)})
            self.filter_cache[code] = self._list(data.get("data", data) if isinstance(data, dict) else data)
        return self.filter_cache.get(code, [])

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("data"), dict):
            return self._list(data["data"])
        return []

    def _nav_items(self, data):
        blocks = self._list(data.get("data", data) if isinstance(data, dict) else data)
        items = []
        for b in blocks:
            if isinstance(b, dict) and isinstance(b.get("items"), list):
                items += b.get("items")
            elif isinstance(b, dict) and (b.get("id") or b.get("drama_id")):
                items.append(b)
        return items

    def _vod(self, item):
        item = item or {}
        vid = self._sid(item.get("id") or item.get("drama_id") or "")
        remarks = item.get("update_label") or item.get("corner") or ("全%s集" % item.get("episode_count") if item.get("episode_count") else "")
        return {"vod_id": vid, "vod_name": item.get("name") or item.get("title") or item.get("t") or vid, "vod_pic": self._pic(item), "vod_remarks": remarks}

    def _pic(self, item):
        return item.get("img_y") or item.get("img_x") or item.get("img") or item.get("cover") or item.get("pic") or ""

    def _unlock(self, d):
        eps = d.get("episodes")
        if isinstance(eps, list):
            for ep in eps:
                if isinstance(ep, dict):
                    ep["is_buy"] = True
                    ep["type"] = "free"
                    ep["price"] = 0
                    ep["methods"] = []
        d.update({"pay_type": "free", "money": 0, "episode_price": 0, "points_price": 0, "can_vip_watch": True, "is_buy_whole": True, "vip_episodes": [], "coin_episodes": [], "points_episodes": []})
        return d

    def _sid(self, x):
        return str(x or "").replace("rp_", "")

    def _split(self, x):
        p = str(x).split("|", 1)
        return self._sid(p[0]), p[1] if len(p) > 1 and p[1] else "1"

    def _hls(self, vid, seq):
        return "%s/api/drama/hls/%s/%s/play.m3u8?line=free" % (self.host, self._sid(vid), seq)

    def _int(self, x, d=0):
        try:
            return int(x)
        except Exception:
            return d
                # 如果列表为空，用首页第一页数据
                if not result["list"]:
                    dramas_data = self._get('/dramas?page=1&size=20')
                    if dramas_data and isinstance(dramas_data, dict):
                        for item in dramas_data.get('list', []):
                            result["list"].append(self._parse_vod(item))

        except Exception as e:
            print(e)

        return result

    def categoryContent(self, tid, pg, filter, extend):
        """分类页"""
        result = {
            "page": pg,
            "pagecount": 999,
            "limit": 20,
            "total": 99999,
            "list": [],
            "parse": 0,
            "jx": 0,
        }

        try:
            # 分类ID是genre id
            data = self._get(f'/dramas?genreId={tid}&page={pg}&size=20')
            if data and isinstance(data, dict):
                lst = data.get('list', [])
                total = data.get('total', 0)
                result["total"] = total
                result["pagecount"] = (total + 19) // 20 if total else 999
                for item in lst:
                    result["list"].append(self._parse_vod(item))

        except Exception as e:
            print(e)

        return result

    def detailContent(self, ids):
        """详情页"""
        result = {
            "list": [],
            "parse": 0,
            "jx": 0,
        }

        try:
            vid = ids[0]
            data = self._get(f'/dramas/{vid}')

            if data and isinstance(data, dict):
                episodes = data.get('episodes', [])

                # 组装播放地址
                play_url_parts = []
                for ep in episodes:
                    ep_title = ep.get('title', f"第{ep.get('ep', 0)}集")
                    play_url = ep.get('playUrl', '')
                    if play_url:
                        play_url_parts.append(f"{ep_title}${play_url}")

                cover = data.get('cover', '')
                # 加密海报走本地代理解密
                if cover and ('encryptimages' in cover or '.bng' in cover):
                    try:
                        cover = f"{self.getProxyUrl()}&url={urllib.parse.quote(cover)}"
                    except Exception:
                        pass

                vod = {
                    "vod_id": str(data['id']),
                    "vod_name": data.get('t', ''),
                    "vod_pic": cover,
                    "type_name": data.get('sub', ''),
                    "vod_year": '',
                    "vod_area": '',
                    "vod_remarks": f"{data.get('serial', '')}·{data.get('plays', '')}播放",
                    "vod_actor": '',
                    "vod_director": '未知',
                    "vod_content": data.get('summary', '') or data.get('t', ''),
                    "vod_play_from": '黄豆短剧',
                    "vod_play_url": '#'.join(play_url_parts),
                }
                result["list"].append(vod)

        except Exception as e:
            print(e)

        return result

    def searchContent(self, key, quick, pg="1"):
        """搜索"""
        result = {
            "page": pg,
            "pagecount": 999,
            "limit": 20,
            "total": 99999,
            "list": [],
            "parse": 0,
            "jx": 0,
        }

        try:
            data = self._get(f'/search?kw={urllib.parse.quote(key)}&page={pg}&size=20')
            if data and isinstance(data, dict):
                lst = data.get('list', [])
                total = data.get('total', 0)
                result["total"] = total
                result["pagecount"] = (total + 19) // 20 if total else 0
                for item in lst:
                    result["list"].append(self._parse_vod(item))

        except Exception as e:
            print(e)

        return result

    def _proxy(self):
        """返回可被播放器访问的代理地址。
        getProxyUrl() 默认是 127.0.0.1，但安卓播放器是独立进程，连不到
        壳 App 的 localhost；换成设备局域网 IP 后，无论 spider 在本机还是
        PC，播放器都能跨进程/跨设备取到解密后的 m3u8 与 key。"""
        import socket
        base = self.getProxyUrl()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = '127.0.0.1'
        return base.replace('127.0.0.1', ip)

    def playerContent(self, flag, id, vipFlags):
        """播放页 - 用代理伺服解密后的 m3u8（key 由客户端现算并注入）"""
        result = {
            "parse": 0,
            "playUrl": "",
            "url": self.error_play_url,
            "jx": 0,
            "header": "",
        }
        if id:
            result["url"] = f"{self._proxy()}&type=m3u8&url={urllib.parse.quote(id)}"
        return result

    def _build_m3u8_with_key(self, url):
        """构建 m3u8 内容（用本地计算的 key 替换原 key URI，ts 改成绝对地址）"""
        import re
        if not url:
            return None
        try:
            r = self.session.get(url, timeout=15, verify=False)
            content = r.text
            # 计算并注入自定义 key
            key_bytes = self._get_key_bytes(url)
            if key_bytes:
                key_uri = f"{self._proxy()}&type=key&url={urllib.parse.quote(url)}"
                content = re.sub(
                    r'(#EXT-X-KEY:.*?URI=")[^"]*(")',
                    r'\1' + key_uri + r'\2',
                    content
                )
            # 把相对路径的 ts 改成绝对路径
            base_url = url.rsplit('/', 1)[0] + '/'
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.startswith('http'):
                        new_lines.append(line)
                    else:
                        new_lines.append(base_url + line)
                else:
                    new_lines.append(line)
            return '\n'.join(new_lines)
        except Exception as e:
            print(f"_build_m3u8_with_key error: {e}")
            return None

    def _get_key_bytes(self, url):
        """从 m3u8 URL 计算解密 key（与站点一致：md5('xnaichanping'+video_id+version)）"""
        import hashlib
        import re
        m = re.search(r'/hls/([0-9a-f]{64})/', url)
        if not m:
            return None
        video_id = m.group(1)
        ver_match = re.search(r'[?&]version=([^&#]+)', url)
        version = ver_match.group(1) if ver_match else 'v1'
        key_str = "xnaichanping" + video_id + version
        return hashlib.md5(key_str.encode()).digest()

    def localProxy(self, param):
        """本地代理 - 解密海报图片 / 伺服 m3u8 与自定义 key"""
        try:
            ptype = param.get('type', 'img')
            if ptype == 'm3u8':
                m3u8_url = param.get('url', '')
                content = self._build_m3u8_with_key(m3u8_url)
                if content:
                    return [200, 'application/vnd.apple.mpegurl', content.encode('utf-8')]
                return [404, 'text/plain', b'not found']
            if ptype == 'key':
                key_url = param.get('url', '')
                key_bytes = self._get_key_bytes(key_url)
                if key_bytes:
                    return [200, 'text/plain', key_bytes]
                return [404, 'text/plain', b'not found']

            # 默认：解密海报图片（封面为服务端加密，必须解密后返回）
            url = param['url']
            r = self.session.get(url, timeout=15, verify=False)
            decrypted = self._aes_decrypt_img(r.content, url)
            # 确定图片类型
            content_type = "image/jpeg"
            if decrypted[:8] == b'\x89PNG\r\n\x1a\n':
                content_type = "image/png"
            elif decrypted[:6] in (b'GIF87a', b'GIF89a'):
                content_type = "image/gif"
            elif decrypted[:4] == b'RIFF' and decrypted[8:12] == b'WEBP':
                content_type = "image/webp"
            return [200, content_type, decrypted]
        except Exception as e:
            print(f"localProxy error: {e}")
            return [500, 'text/html', b'']

    def _aes_decrypt_img(self, encrypted, url):
        """AES 解密图片 - 网站自定义 CBC 算法"""
        import hashlib
        import re
        from Crypto.Cipher import AES

        # 提取 imageId (64位哈希)
        m = re.search(r'([0-9a-f]{64})', url)
        if not m:
            return encrypted
        image_id = m.group(1)

        # 提取 version
        ver_match = re.search(r'[?&]version=([^&#]+)', url)
        version = ver_match.group(1) if ver_match else 'v1'

        # 计算解密 key
        prefix = "xnaichanping"
        key_str = prefix + image_id + version
        key_bytes = hashlib.md5(key_str.encode()).digest()

        # 网站自定义 CBC 解密 (mC 函数)
        t = len(encrypted) // 16
        if t < 1:
            return encrypted

        iv = bytes(16)  # IV=0

        # 取最后一块 XOR 16
        last_block = encrypted[(t - 1) * 16:t * 16]
        a = bytes([b ^ 16 for b in last_block])

        # 加密 a
        cipher_enc = AES.new(key_bytes, AES.MODE_CBC, iv)
        o = cipher_enc.encrypt(a)[:16]

        # 扩展密文并解密
        extended = encrypted + o
        cipher_dec = AES.new(key_bytes, AES.MODE_CBC, iv)
        c = cipher_dec.decrypt(extended)

        # 自定义 CBC：每块 XOR 前一块密文
        u = bytearray(len(c))
        u[:16] = c[:16]
        for f in range(1, t):
            for h in range(16):
                u[f * 16 + h] = c[f * 16 + h] ^ encrypted[(f - 1) * 16 + h]

        # 去掉 padding
        d = u[-1]
        if 1 <= d <= 16:
            u = u[:-d]

        return bytes(u)

    # ==================== 内部方法 ====================

    def _parse_vod(self, item):
        """解析视频条目 - 海报用 getProxyUrl 代理解密"""
        cover = item.get('cover', '')
        # 加密海报走本地代理解密
        if cover and ('encryptimages' in cover or '.bng' in cover):
            try:
                cover = f"{self.getProxyUrl()}&url={urllib.parse.quote(cover)}"
            except Exception:
                pass
        return {
            "vod_id": str(item['id']),
            "vod_name": item.get('t', ''),
            "vod_pic": cover,
            "vod_remarks": f"{item.get('serial', '')}·{item.get('eps', 0)}集",
        }

    def _get(self, path):
        """发送 GET 请求"""
        url = self.API_BASE + path
        try:
            r = self.session.get(url, timeout=15, verify=False)
            resp = r.json()
            if resp.get('code') == 0 and resp.get('data') is not None:
                return resp['data']
            return None
        except Exception as e:
            print(e)
            return None


# 调试用
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    s = Spider()
    s.init()

    print('=== 首页 ===')
    home = s.homeContent(True)
    print(f'分类: {len(home["class"])}个')
    for c in home['class']:
        print(f'  {c["type_id"]}: {c["type_name"]}')
    print(f'推荐: {len(home["list"])}个')
    for v in home['list'][:5]:
        print(f'  {v["vod_id"]}: {v["vod_name"]} - {v["vod_remarks"]}')
    print()

    print('=== 分类1（都市）第1页 ===')
    cr = s.categoryContent('1', 1, True, {})
    print(f'总数: {cr["total"]}, 本页: {len(cr["list"])}个')
    for v in cr['list'][:5]:
        print(f'  {v["vod_id"]}: {v["vod_name"]}')
    print()

    print('=== 搜索 穿越 ===')
    sr = s.searchContent('穿越', False, '1')
    print(f'结果: {len(sr["list"])}个, 总数: {sr["total"]}')
    for v in sr['list'][:5]:
        print(f'  {v["vod_id"]}: {v["vod_name"]}')
    print()

    if sr['list']:
        vid = sr['list'][0]['vod_id']
        print(f'=== 详情 {vid} ===')
        dr = s.detailContent([vid])
        if dr['list']:
            v = dr['list'][0]
            print(f'标题: {v["vod_name"]}')
            print(f'分类: {v["type_name"]}')
            print(f'备注: {v["vod_remarks"]}')
            print(f'播放源: {v["vod_play_from"]}')
            play_urls = v["vod_play_url"].split('#')
            print(f'集数: {len(play_urls)}集')
            print(f'第一集: {play_urls[0][:80]}...')
