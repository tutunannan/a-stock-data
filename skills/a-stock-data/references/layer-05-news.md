> 本文件 = 单文件版 SKILL.md 的 Layer 5 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。
> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。

## Layer 5: 新闻层

### 5.1 东财个股新闻（直连 search-api-web）

```python
import requests
import re
import json

def eastmoney_stock_news(code: str, page_size: int = 20) -> list[dict]:
    """
    东财个股新闻（JSONP 接口）。
    返回: [{title, content, time, source, url}]
    """
    # 构造 JSONP 参数
    cb = "jQuery_news"
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_params = json.dumps({
        "uid": "",
        "keyword": code,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                  "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": ""}},
    }, separators=(',', ':'))
    params = {"cb": cb, "param": inner_params}
    headers = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
    r = em_get(url, params=params, headers=headers, timeout=15)

    # 解析 JSONP
    text = r.text
    json_str = text[text.index("(") + 1 : text.rindex(")")]
    d = json.loads(json_str)

    rows = []
    # 东财实际返回里 result.cmsArticleWebOld 直接就是文章列表（非 {list:[...]} 嵌套）
    articles = d.get("result", {}).get("cmsArticleWebOld", []) or []
    for a in articles:
        rows.append({
            "title": re.sub(r'<[^>]+>', '', a.get("title", "")),
            "content": re.sub(r'<[^>]+>', '', a.get("content", ""))[:200],
            "time": a.get("date", ""),
            "source": a.get("mediaName", ""),
            "url": a.get("url", ""),
        })
    return rows

# 用法
news = eastmoney_stock_news("688017")
for n in news[:5]:
    print(f"  {n['time']} | {n['source']} | {n['title']}")
```

> **⚠️ 间歇性返回空（#18）：** 部分大陆住宅 IP 调本接口会只拿到 `passportWeb`（股民资料）而无 `cmsArticleWebOld`（文章列表）——这是东财对该 IP 的间歇风控，非代码问题。代码已对空结果安全返回 `[]`；遇到时隔几分钟或换网络重试即可。

### 5.2 财联社快讯（直连 cls.cn，v1 API + 本地签名）✅ 已复活（2026-07）

> **✅ 2026-07 复活：** 旧接口 `cls.cn/nodeapi/telegraphList` 2026-05 下线（站点改
> Next.js，旧址返回 HTML 而非 JSON，#14）。现走新版 `cls.cn/v1/roll/get_roll_list`——它
> 强制校验 `sign`，但签名**纯本地计算、无需任何 key**：`sign = md5(sha1(按 key 字典序
> 拼接的 query 串))`。财联社快讯偏 A 股财经、时效强，与 §5.3 东财 7×24 **互为独立备份**
> （两条不同源、不同风控面，一条被封另一条仍在）。2026-07-11 实测 errno=0 正常返回。

```python
import requests
import hashlib
from datetime import datetime

def cls_telegraph(page_size: int = 50) -> list[dict]:
    """
    财联社电报（全市场实时快讯）。v1 API + 本地签名，零 key。
    返回: [{title, content, time}]  time 已转为 'YYYY-MM-DD HH:MM:SS'
    """
    params = {"appName": "CailianpressWeb", "os": "web", "sv": "7.7.5",
              "last_time": "", "refresh_type": "1", "rn": str(page_size)}
    # 签名：md5(sha1(按 key 字典序拼接的 query 串))，纯本地算、无需 key
    qs = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sign = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
    url = f"https://www.cls.cn/v1/roll/get_roll_list?{qs}&sign={sign}"
    headers = {"User-Agent": UA, "Referer": "https://www.cls.cn/"}
    r = requests.get(url, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in (d.get("data") or {}).get("roll_data") or []:   # #46 同因
        ts = item.get("ctime")
        t = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        rows.append({
            "title": item.get("title", "") or item.get("brief", ""),
            "content": item.get("content", "") or item.get("brief", ""),
            "time": t,
        })
    return rows

# 用法
news = cls_telegraph()
for n in news[:10]:
    print(f"  {n['time']} | {n['title'][:60]}")
```

### 5.3 东财全球资讯（7x24）

```python
import requests

import uuid

def eastmoney_global_news(page_size: int = 50) -> list[dict]:
    """
    东方财富全球财经资讯（7x24 滚动）。
    返回: [{title, summary, time}]
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web", "biz": "web_724",
        "fastColumn": "102", "sortEnd": "",
        "pageSize": str(page_size),
        "req_trace": str(uuid.uuid4()),
    }
    headers = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json()

    rows = []
    for item in (d.get("data") or {}).get("fastNewsList") or []:  # #46 同因
        rows.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", "")[:200],
            "time": item.get("showTime", ""),
        })
    return rows

# 用法
news = eastmoney_global_news()
for n in news[:10]:
    print(f"  {n['time']} | {n['title']}")
```

### 5.4 华尔街见闻 7×24 快讯（V3.9.0 新增）

新闻层第三个来源，与 §5.2 财联社、§5.3 东财互为备份。`channel` 常用 `global-channel`（要闻）/ `a-stock-channel`（A 股）。
`importance` 取见闻的 score 字段，实测只有 1 / 2，100 条里约 6 条为 2（头条级快讯）。时间为北京时间。
翻页：把返回表的 `attrs['next_cursor']` 传给下一次的 `cursor`。

<!-- v39-wscn-lives:start -->
```python
import re
from datetime import datetime, timedelta, timezone

WSCN_LIVES_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
_CN_TZ = timezone(timedelta(hours=8))


@_v39_contract
def wallstreetcn_lives(channel="global-channel", limit=50, cursor=None):
    """华尔街见闻 7×24 快讯（新闻层第三来源，与 §5.2 财联社 / §5.3 东财互备）。

    channel: global-channel（要闻，默认）/ a-stock-channel（A 股）等频道名。
    limit ≤ 100。翻页：把返回表的 attrs['next_cursor'] 传给下一次的 cursor。
    importance 取见闻的 score 字段：实测只有 1 / 2，100 条里约 6 条为 2（头条级快讯）。时间为北京时间。
    """
    if not re.fullmatch(r"[a-z0-9-]+-channel", str(channel)):
        raise ValueError("channel 形如 'global-channel' / 'a-stock-channel'")
    if not 1 <= int(limit) <= 100:
        raise ValueError("limit 范围 1–100")
    params = {"channel": channel, "limit": int(limit)}
    if cursor:
        params["cursor"] = cursor
    response = _v39_http(WSCN_LIVES_URL, params=params)
    payload = _v39_json(response)
    if not isinstance(payload, dict) or payload.get("code") != 20000 or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"华尔街见闻返回错误: {str(payload)[:200]}")
    items = _v39_rows(payload["data"].get("items"), "华尔街见闻快讯的 items")
    rows = []
    try:
        for item in items:
            stamp = item["display_time"]
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
                raise TypeError(f"display_time={stamp!r}")
            rows.append({"id": item["id"],
                         "time": datetime.fromtimestamp(stamp, _CN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                         "title": item.get("title") or "",
                         "content": (item.get("content_text") or "").strip(),
                         "importance": item.get("score"),
                         "channels": ",".join(_v39_labels(item.get("channels"), "快讯 channels")),
                         "url": item.get("uri") or ""})
    except (KeyError, TypeError, AttributeError, ValueError, OverflowError, OSError) as exc:
        raise RuntimeError(f"华尔街见闻快讯条目格式改变: {type(exc).__name__}: {exc}") from exc
    if not rows:
        raise RuntimeError(f"华尔街见闻 {channel} 返回 0 条（频道名可能不存在）")
    frame = _v39_frame(rows, "wallstreetcn", response.url)
    frame.attrs["next_cursor"] = payload["data"].get("next_cursor")
    return frame
```
<!-- v39-wscn-lives:end -->

### 5.5 央视《新闻联播》文字稿（V3.9.0 新增）

央视网官方页面：当日条目标题 + 逐条正文（`with_content=True` 约 15 次请求）。页面结构 2016 / 2019 / 2021 年改过三次，
三种写法都能解析。个别老视频已被下架，其 `content` 为 None（标题仍在）。当晚约 20:00 后更新，未发布抛 `ValueError`。
**内容以时政为主：可用于政策信号研究，做短视频文案时不要引用。**

<!-- v39-cctv-news:start -->
```python
import html as _html
import re
import time

CCTV_DAY_URL = "https://tv.cctv.com/lm/xwlb/day/{ymd}.shtml"


def _cctv_body(url):
    text = _v39_http(url).content.decode("utf-8", "replace")
    if len(text) < 1000 and "error.html" in text:
        return None                         # 单条视频已被央视下架（页面只剩跳错误页的脚本）
    match = (re.search(r'<div class="content_area"[^>]*>(.*?)</div>', text, re.S)
             or re.search(r'<div class="cnt_bd"[^>]*>(.*?)</div>', text, re.S))
    if not match:
        raise RuntimeError(f"新闻联播正文页结构改变: {url}")
    body = re.sub(r"</p>|<br\s*/?>", "\n", match.group(1))
    body = _html.unescape(re.sub(r"<[^>]+>", "", body))
    body = "\n".join(line.strip() for line in body.splitlines() if line.strip())
    return re.sub(r"^央视网消息\s*[（(]新闻联播[)）]\s*[：:]", "", body)


@_v39_contract
def cctv_news(date, with_content=True):
    """央视《新闻联播》当日条目（央视网官方页面）— 标题 + 文字稿。

    with_content=True 会逐条打开详情页取正文（约 15 次请求）；False 只要标题和链接。
    个别老视频已被下架，其 content 为 None（标题仍在）。
    内容以时政为主：可用于政策信号研究，**做短视频文案时不要引用**。
    """
    ymd = _v39_date(date).replace("-", "")
    url = CCTV_DAY_URL.format(ymd=ymd)
    response = _v39_http(url, allow_status=(404,))
    if response.status_code == 404:
        raise ValueError(f"{date} 没有新闻联播页面（日期过早或尚未发布，当晚约 20:00 后更新）")
    text = response.content.decode("utf-8", "replace")
    rows = []
    # 央视网改版过三次：2016 标题是 <a> 的文本，2019–2020 在 <div class="title">，
    # 2021 起在 <a title="">。逐个 <li> 按这三种位置依次找。
    for chunk in text.split("<li")[1:]:
        link = re.search(r'href="([^"]*/VIDE[^"]+)"', chunk)
        if not link:
            continue
        href = link.group(1)
        title = (re.search(r'title="([^"]+)"', chunk) or re.search(r'class="title">(.*?)</div>', chunk, re.S)
                 or re.search(r"<a[^>]*>(.*?)</a>", chunk, re.S))
        title = _html.unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else ""
        if not title or re.match(r"《新闻联播》\s*\d{8}|新闻联播完整版", title):
            continue                        # 第一条是整期节目视频，不是单条新闻
        title = re.sub(r"^\[视频\]", "", title).strip()
        rows.append({"date": _v39_date(ymd), "title": title,
                     "url": ("https:" + href) if href.startswith("//") else href})
    if not rows:
        raise RuntimeError(f"新闻联播 {ymd} 页面没有解析出条目，结构可能已变")
    if with_content:
        for row in rows:
            row["content"] = _cctv_body(row["url"])
            time.sleep(0.2)
    return _v39_frame(rows, "cctv", url)
```
<!-- v39-cctv-news:end -->

```python
flash = wallstreetcn_lives("a-stock-channel", limit=50)
more = wallstreetcn_lives("a-stock-channel", limit=50, cursor=flash.attrs["next_cursor"])
xwlb = cctv_news("2026-09-18", with_content=False)
```

---
