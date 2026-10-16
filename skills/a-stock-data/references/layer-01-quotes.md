> 本文件 = 单文件版 SKILL.md 的 Layer 1 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。
> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。

## Layer 1: 行情层（实时，不封IP）

> **V3.10.0 起本层重排：能用的在前，2026-09 起失效的 mootdx 行情命令移到最后（§1.7，留档）。**
> 旧编号 → 新编号：1.2→1.1 腾讯实时、1.5→1.2 腾讯 K 线、1.6→1.3 通达信盘后包、1.3→1.5 百度、1.4→1.6 新浪复权因子、1.1→1.7 mootdx；
> §1.4 腾讯逐笔为新增。CHANGELOG 与文件开头的历史版本说明里写的仍是旧编号。

### 1.1 腾讯财经 API — PE/PB/市值/换手率/涨跌停/指数/ETF

HTTP GET，GBK 编码，`~` 分隔 88 个字段，不封IP。

```python
import urllib.request

def tencent_quote(codes: list[str]) -> dict[str, dict]:
    """
    批量拉取腾讯财经实时行情。
    codes: ["688017", "300476", "002463"]
    也支持指数: ["000001", "000300", "399006"]
    也支持ETF: ["510050", "510300"]
    返回: {code: {name, price, pe_ttm, pb, mcap, ...}}
    """
    # 前缀路由：与全局 get_prefix() 一致。5x 沪ETF / 000300 等沪指数不能落到 sz（会返回空或错票）。
    SH_INDEX = {"000300", "000905", "000016", "000688", "000852", "000010"}   # 沪指数白名单
    prefixed = []
    key_of = {}          # 带前缀的查询键 → 调用方原始写法，保证结果键与入参一一对应
    for c in codes:
        low = c.lower()
        if low.startswith(("sh", "sz", "bj")):        # 显式前缀透传，解决 000001 等歧义
            p = low
        elif c.startswith("92"):                      # 北交所 920 号段须先于 9x 判断
            p = f"bj{c}"
        elif c in SH_INDEX or c.startswith(("5", "6", "9")):
            p = f"sh{c}"
        elif c.startswith(("4", "8")):
            p = f"bj{c}"
        else:
            p = f"sz{c}"
        prefixed.append(p)
        key_of[p] = c    # 显式前缀入参原样返回，裸代码返回裸代码

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        # 用入参原样做键：批量里同时传 sh000001 与 sz000001 时，若都退回裸 6 位码
        # 会撞成同一个键、后者静默覆盖前者，显式前缀这个特性就白做了。
        code = key_of.get(key, key[2:])
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_amt":   float(vals[31]) if vals[31] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,
            "amount_wan":   float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "amplitude_pct":float(vals[43]) if vals[43] else 0,
            # ⚠️ 44=流通市值、45=总市值（曾标反）。总股本≠流通股本时差数倍，见上方踩坑提醒二
            "float_mcap_yi":float(vals[44]) if vals[44] else 0,
            "mcap_yi":      float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "vol_ratio":    float(vals[49]) if vals[49] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
        # 僵尸报价检测：腾讯对「已迁移的北交所老码 / 长期停牌股」照样返回 HTTP 200 +
        # 一份定格在最后交易日的报价（成交量 0、最新价==昨收），不报任何错。
        # 直接拿去算估值会得出完全错误的结论（实测 bj832982 报 112.60，真实新码 920982 为 131.74）。
        q = result[code]
        q["is_stale"] = (q["amount_wan"] == 0 and q["price"] == q["last_close"] and q["price"] > 0)
        if q["is_stale"] and key[2:4] in ("43", "83", "87"):
            q["stale_reason"] = "北交所老号段，多数已迁至 920xxx，请按名称反查现行代码"
        elif q["is_stale"]:
            q["stale_reason"] = "成交量为 0（停牌 / 未开盘 / 废码），报价非当日真实成交"
    return result

# 用法: 个股
quotes = tencent_quote(["688017", "300476", "002463"])
for code, q in quotes.items():
    print(f"{q['name']}({code}): {q['price']}元 PE={q['pe_ttm']} PB={q['pb']} 市值={q['mcap_yi']}亿")

# 用法: 指数 — sh000001=上证指数, sh000300=沪深300, sz399006=创业板指
index_quotes = tencent_quote(["000001", "000300", "399006"])

# 用法: ETF — sh510050=上证50ETF, sh510300=沪深300ETF
etf_quotes = tencent_quote(["510050", "510300"])
```

#### 腾讯财经字段索引速查（实测校准 2026-05-03）

| 索引 | 含义 | 示例 |
|------|------|------|
| 1 | 名称 | 绿的谐波 |
| 3 | 当前价 | 224.12 |
| 4 | 昨收 | 215.01 |
| 5 | 今开 | 214.10 |
| 9-18 | 买一~买五(价+量) | |
| 19-28 | 卖一~卖五(价+量) | |
| 31 | 涨跌额 | 9.11 |
| 32 | 涨跌幅% | 4.24 |
| 33 | 最高 | 229.62 |
| 34 | 最低 | 214.10 |
| 37 | 成交额(万) | 187040 |
| 38 | 换手率% | 4.55 |
| **39** | **PE(TTM)** | 300.45 |
| **43** | **振幅%（不是PB！）** | 7.22 |
| **44** | **流通市值(亿)** | 410.88 |
| **45** | **总市值(亿)** | 410.88 |
| **46** | **PB(市净率)** | 11.51 |
| **47** | **涨停价** | 258.01 |
| **48** | **跌停价** | 172.01 |
| 49 | 量比 | 1.20 |
| **52** | **PE(静)** | 314.76 |

> **踩坑提醒一：** 网上很多教程把索引 43 写成 PB，实测是振幅%。PB 在索引 46。
>
> **踩坑提醒二（2026-07-26 修正）：** **44 是流通市值、45 才是总市值**，此前本表标反了。
> 多数股票两者相等，所以看不出来；但**总股本 ≠ 流通股本的票（科创板/次新股/有限售股）会差出数倍**。
> 实测中船特气(688146)：`f[44]=356.15亿`(流通股本 1.45亿股)、`f[45]=1300.61亿`(总股本 5.29亿股)，**差 3.65 倍**。
> 用市值做筛选时取错会把大市值公司误判成小盘股。可用 `f[45] ÷ 现价` 反推总股本核对（与东财 `f84` 一致）。
> 参考：东财 push2 的 `f116`=总市值 / `f117`=流通市值 方向与腾讯相反，实测确认无误，勿混用。

### 1.2 腾讯 K 线 — 日/周/月前后复权 + 1~60 分钟（V3.9.0 新增 · #52）

§1.7 mootdx K 线失效（#52）后的主力 K 线源。三个入口是同一后端、限流各自独立：某入口返回空或异常时冷却 120 秒、换下一个，
三个都不可用才抛错（#52 实测单入口约 600 次后返回空 JSON）。**只支持沪深**：腾讯对北交所只返回最新 1 根日线、
区间和分钟线都是空的（2026-09-20 实测 920021 / 920982 / 920185），函数遇北交所代码直接抛 `ValueError`，北交所日线用 §1.3。

| 参数 | 说明 |
|---|---|
| `period` | `day` / `week` / `month`：默认前复权，可 `adjust='hfq'` 或 `adjust=''`（不复权）；`m1` / `m5` / `m15` / `m30` / `m60`：只有不复权、只能取最近 ≤320 根 |
| `start` / `end` | 仅日周月可用，自动按段翻页（单段 <640 根）；不给 `start` 时取最近 `count` 根（≤640） |
| 返回列 | `code` / `adjust`（仅日周月）/ `date` / `open` / `high` / `low` / `close` / `volume`；分钟线另有 `turnover_rate_pct`，日期列名为 `datetime` |
| `volume` 单位 | **科创板（688 / 689）是股**，其余是手：沪深主板、创业板、B 股、ETF（含科创板 ETF 588）、LOF、REITs 1 手 = 100 股 / 份，可转债 1 手 = 10 张，指数也是手；日周月线、分钟线、复权与否都是这个规则 |

> ⚠️ **腾讯前复权是等差口径**（逐次减去每股分红）：茅台 2020-01-02 原始价 1130.00、腾讯 qfq 870.741，差额正是此后累计分红；
> 高分红老股早年会被减成负数（茅台 2015 年约 -117.6）。本函数遇到 ≤0 价格直接抛错。**长区间回测请取 `adjust=''`，
> 再用 §1.6 的比例因子复权**。本接口**没有成交额**，需要成交额用 §1.3。

> ⚠️ **成交量按股对账前先看这几条**（#57，2026-10-05 对照通达信盘后包与 Baostock 实测）：
> - **整手取整**：科创板以外，日线的量是当日总股数取整到手——2020-03-11 起基本是四舍五入（实测差 −52～+50 股），更早是舍去零头（差 −99～0 股），
>   日线不会回填，周 / 月线是日线相加。分钟线**最近一个交易日**也是逐根整手，要到下一个交易日才回填成精确股数（会出现 34967.59 这样的小数手），
>   回填后当日各根合计与盘后包逐股一致；确切的回填时点没测出来。科创板的分钟量当天就是精确股数。
>   ⇒ **最近一个交易日的分钟量别拿来按股精确对账**。本函数 m1 最多 320 根（约 1.3 天），要拿整天已回填的数据用 m5 / m60（320 根约 6 / 80 个交易日）。
> - **1 分钟线**每天 241 根：09:30 那根只有开盘集合竞价（竞价没成交就没有这根），m5 及以上把竞价并进第一根。
>   13:01 那根的开盘价是上午收盘价、不是午后第一笔，用 m1 自己合成 5 分钟线时 13:05 的开盘价会和腾讯原生 m5 / Baostock 对不上。
> - **深市分钟边界**：整分那一刻（hh:mm:00）的成交，腾讯算进下一根（m1、原生 m5 都是；11:30:00 那一刻例外，留在 11:30 那根），Baostock 算进上一根，所以深市逐根量价对不上
>   （改按开始时刻分桶也拼不回来）、全天合计一致；沪市已回填的日子腾讯原生 m5 与 Baostock 5 分钟逐根一致。
> - **没有成交的分钟**：当天第一笔成交以前沪深都没有行（集合竞价没成交时连 09:30 那根也没有；09-30 抽 54 只沪深 B 股，第一笔晚于 09:30 的 43 只都从第一笔那分钟才有行）。
>   第一笔以后，沪市没有成交的分钟给一根量为 0、四个价基本都等于上一根收盘的行，不缺行；深市大多也这样，但会整根缺失
>   （09-30 抽 51 只低成交深市股，25 只共缺 64 分钟，抽查的缺失分钟逐笔里都没有成交）。按分钟格点对齐时要自己处理缺行。

<!-- v39-tencent-kline:start -->
```python
import time
from datetime import date, datetime, timedelta

# 三个入口是同一后端，但限流各自独立（#52 实测单域名约 600 次后返回空 JSON）。
TENCENT_KLINE_HOSTS = ["https://web.ifzq.gtimg.cn",
                       "https://proxy.finance.qq.com/ifzqgtimg",
                       "https://ifzq.gtimg.cn"]
_TENCENT_HOST_COOLDOWN = 120          # 某入口失败后暂停使用的秒数
_tencent_host_down_until = {}
_TENCENT_MINUTES = ("m1", "m5", "m15", "m30", "m60")
_TENCENT_SPAN_DAYS = {"day": 700, "week": 3650, "month": 18250}   # 每段 < 640 根


def _tencent_kline_call(path, param):
    """按顺序尝试三个入口；空响应或异常视为该入口被限流，冷却后换下一个。返回 (data, 实际成功的入口)。"""
    errors = []
    for host in TENCENT_KLINE_HOSTS:
        if _tencent_host_down_until.get(host, 0) > time.time():
            continue
        try:
            response = _v39_http(host + path, params={"param": param},
                                 headers={"Referer": "https://gu.qq.com/"}, timeout=(8, 20))
            payload = _v39_json(response) if response.text.strip() else {}
        except RuntimeError as exc:
            errors.append(f"{host}: {type(exc.__cause__ or exc).__name__}")
            _tencent_host_down_until[host] = time.time() + _TENCENT_HOST_COOLDOWN
            continue
        if not isinstance(payload, dict):    # 顶层变成数组 / 字符串：当作这个入口坏了，换下一个
            errors.append(f"{host}: 顶层是 {type(payload).__name__}，不是对象")
            _tencent_host_down_until[host] = time.time() + _TENCENT_HOST_COOLDOWN
            continue
        if payload.get("msg") == "param error":
            raise ValueError(f"腾讯 K 线参数错误（区间过长或代码不存在）: {param}")
        if isinstance(payload.get("data"), dict) and payload["data"]:
            return payload["data"], host
        errors.append(f"{host}: 空响应")
        _tencent_host_down_until[host] = time.time() + _TENCENT_HOST_COOLDOWN
    raise RuntimeError("腾讯 K 线三个入口均不可用（可能被限流，稍后重试）: " + "; ".join(errors))


@_v39_contract
def tencent_kline(code, period="day", adjust=None, start=None, end=None, count=320):
    """腾讯 K 线 — 日/周/月（默认前复权）与 1/5/15/30/60 分钟（不复权）。

    period: day / week / month / m1 / m5 / m15 / m30 / m60
    adjust: None=日周月默认 qfq、分钟默认不复权；可显式传 'qfq' / 'hfq' / ''（不复权）
    start/end: 仅日周月可用，'YYYY-MM-DD'；给了 start 会自动按段分页（单次最多 640 根）
    count: 不给 start 时取最近 count 根；日周月 ≤ 640，分钟 ≤ 320
    成交量单位：科创板（688/689）是股，其余是手；科创板以外，最近一个交易日的分钟量是整手、下一个交易日才回填成精确股数（见 §1.2 说明）。
    本接口**没有成交额**，需要成交额用 §1.3 通达信盘后包。
    不支持北交所：腾讯对北交所只返回最新 1 根日线，区间与分钟线为空（2026-09-20 实测），直接抛 ValueError。
    """
    period = str(period).lower()
    if get_prefix(code) == "bj":
        raise ValueError("腾讯 K 线不支持北交所（只返回最新 1 根日线、分钟线为空）；"
                         "北交所日线请用 §1.3 tdx_daily_package(date) 按交易日取")
    symbol = get_prefix(code) + norm_ticker(code)
    if period in _TENCENT_MINUTES:
        if adjust not in (None, ""):
            raise ValueError("分钟线只有不复权数据，adjust 请留空")
        if start or end:
            raise ValueError("分钟线只能取最近 count 根，不支持 start/end")
        if not 1 <= int(count) <= 320:
            raise ValueError("分钟线 count 范围 1–320")
        data, host = _tencent_kline_call("/appstock/app/kline/mkline", f"{symbol},{period},,{int(count)}")
        node = data.get(symbol)
        if not isinstance(node, dict) or not isinstance(node.get(period), list):
            raise RuntimeError(f"腾讯分钟线 {symbol} 的返回里没有 {period} 列表，格式可能已变")
        rows, seen = [], set()
        try:
            for item in node[period]:
                stamp = datetime.strptime(item[0], "%Y%m%d%H%M")
                if stamp in seen:
                    raise RuntimeError(f"腾讯分钟线 {symbol} 同一时刻 {stamp} 出现两次，结果不可信")
                seen.add(stamp)
                rows.append({"datetime": stamp.strftime("%Y-%m-%d %H:%M"),
                             "open": _v39_req_num(item[1], "open"), "high": _v39_req_num(item[3], "high"),
                             "low": _v39_req_num(item[4], "low"), "close": _v39_req_num(item[2], "close"),
                             "volume": _v39_req_num(item[5], "volume"),
                             # 第 8 个字段是换手率「基点」，÷100 才是百分数；它不是成交额。
                             "turnover_rate_pct": _v39_num(item[7]) / 100 if len(item) > 7
                             and _v39_num(item[7]) is not None else None})
        except (ValueError, TypeError, IndexError, KeyError) as exc:      # 源格式变了（行变短 / 变成对象），不是参数错
            raise RuntimeError(f"腾讯分钟线 {symbol} 行格式改变: {exc}") from exc
        if not rows:
            raise RuntimeError(f"腾讯分钟线 {symbol} {period} 返回 0 根")
        frame = _v39_frame(rows, "tencent", host + "/appstock/app/kline/mkline")
        frame.insert(0, "code", symbol)
        return frame

    if period not in _TENCENT_SPAN_DAYS:
        raise ValueError("period 只能是 day/week/month 或 m1/m5/m15/m30/m60")
    adjust = "qfq" if adjust is None else adjust
    if adjust not in ("qfq", "hfq", ""):
        raise ValueError("adjust 只能是 'qfq' / 'hfq' / ''")
    if start:
        first = datetime.strptime(_v39_date(start), "%Y-%m-%d").date()
        last = datetime.strptime(_v39_date(end), "%Y-%m-%d").date() if end else date.today()
        if first > last:
            raise ValueError("start 不能晚于 end")
        windows, cursor = [], first
        while cursor <= last:
            stop = min(cursor + timedelta(days=_TENCENT_SPAN_DAYS[period] - 1), last)
            windows.append((cursor.isoformat(), stop.isoformat(), 640))
            cursor = stop + timedelta(days=1)
    else:
        if end:
            raise ValueError("只给 end 时请同时给 start")
        if not 1 <= int(count) <= 640:
            raise ValueError("日周月 count 范围 1–640")
        windows = [("", "", int(count))]

    by_date, used_hosts = {}, []
    for s, e, n in windows:
        data, host = _tencent_kline_call("/appstock/app/fqkline/get",
                                         f"{symbol},{period},{s},{e},{n},{adjust}")
        if host not in used_hosts:
            used_hosts.append(host)
        node = data.get(symbol)
        # 有除权的标的返回 qfqday / hfqweek…；从未除权的标的（以及指数）只返回 day/week/month，
        # 此时复权价与原始价相同。只认其中一个 key 会静默丢掉另一类标的（#52 补充）。
        # 复权 key 在就只用它：它为空而 day 有数据时，拿 day 顶上就是把原始价标成复权价，直接抛错。
        # 空列表是正常的（上市前、长期停牌的区间，实测 688981 在 2019 年返回 day=[]）；
        # 连这两个 key 都没有说明返回格式变了，不能把这一段当成 0 根跳过。
        key = adjust + period
        if not isinstance(node, dict) or not isinstance(node.get(key, node.get(period)), list):
            raise RuntimeError(f"腾讯 K 线 {symbol} {s or '最近'}~{e or ''} 的返回里没有 {key} / {period}，"
                               "格式可能已变")
        items = node.get(key, node.get(period))
        if key != period and key in node and not items and node.get(period):
            raise RuntimeError(f"腾讯 K 线 {symbol} {s}~{e} 的 {key} 为空、{period} 却有数据，"
                               "不能拿原始价冒充复权价")
        try:
            for item in items:
                day = _v39_src_date(item[0])
                # 每段只接受段内日期（实测腾讯按 K 线日期过滤，周 / 月线也不越界）；
                # 越界说明拿到的是别的请求或缓存页，只按总区间过滤会把缺掉的几段静默吞掉
                if s and not s <= day <= e:
                    raise RuntimeError(f"腾讯 K 线 {symbol} 请求 {s}~{e} 却返回了 {day}，结果不可信")
                if day in by_date:          # 各段互不重叠，同一天出现两次只能是源数据有问题
                    raise RuntimeError(f"腾讯 K 线 {symbol} 日期 {day} 出现两次，结果不可信")
                # 必填数值走 _v39_req_num：float() 会把 true 读成 1.0、把 'nan' 放进结果
                by_date[day] = {"date": day, "open": _v39_req_num(item[1], "open"),
                                "high": _v39_req_num(item[3], "high"), "low": _v39_req_num(item[4], "low"),
                                "close": _v39_req_num(item[2], "close"), "volume": _v39_req_num(item[5], "volume")}
        except (ValueError, TypeError, IndexError, KeyError) as exc:      # 源格式变了（行变短 / 变成对象），不是参数错
            raise RuntimeError(f"腾讯 K 线 {symbol} 行格式改变: {exc}") from exc
    rows = [by_date[k] for k in sorted(by_date)]
    if start:
        rows = [r for r in rows if windows[0][0] <= r["date"] <= windows[-1][1]]
    if not rows:
        raise RuntimeError(f"腾讯 K 线 {symbol} {period} 在所给区间内 0 根（未上市/停牌区间/代码有误）")
    # 腾讯 qfq 是「逐次减去每股分红」的等差口径（茅台 2020-01-02：原始 1130.00，qfq 870.741，
    # 差额 259.259 正是此后累计分红），高分红股的早年价格会被减成负数（茅台 2015 年 -117.6）。
    # 负价不能拿去算收益率，直接拒绝；长区间请用 adjust='' 再按 §1.6 比例口径复权。
    if any(min(r["open"], r["high"], r["low"], r["close"]) <= 0 for r in rows):
        raise RuntimeError(f"腾讯 {adjust or '原始'} 价格出现 ≤0（等差复权口径的副作用）；"
                           "请改用 adjust='' 取不复权价，再用 §1.6 sina_adjust_factor + apply_adjust")
    # 分段请求可能落在不同入口，source_url 列出实际用到的全部入口
    frame = _v39_frame(rows, "tencent", " | ".join(h + "/appstock/app/fqkline/get" for h in used_hosts))
    frame.insert(0, "code", symbol)
    frame.insert(1, "adjust", adjust or "none")
    return frame
```
<!-- v39-tencent-kline:end -->

```python
day = tencent_kline("600519", start="2025-01-01")            # 前复权日线，自动分段
raw = tencent_kline("600519", adjust="", count=250)            # 不复权 → 可交给 §1.6 apply_adjust
m5 = tencent_kline("300750", period="m5", count=96)           # 最近 96 根 5 分钟线
idx = tencent_kline("sh000001", period="week", count=100)     # 指数（上证指数要写 sh 前缀）
```

### 1.3 通达信官网盘后包 — 某交易日全市场日线含成交额（V3.9.0 新增 · #52）

通达信官网每天发布的增量数据包（HTTP 下载约 2.7MB），一次拿到**沪深北全部证券**当日的昨收、开高低收、成交量（股）、
成交额（元）。它走 HTTP，和 §1.7 失效的 TCP 行情命令是两条路。适合收盘后全市场截面筛选、每日落库。
二进制布局参考 [jing2uo/tdx2db](https://github.com/jing2uo/tdx2db)（MIT），已与腾讯收盘价对拍。
非交易日、或当天包还没发布（通常收盘后数小时）抛 `ValueError`，不返回空表。

<!-- v39-tdx-package:start -->
```python
import io
import math
import re
import struct
import zipfile
import zlib

TDX_PACKAGE_URL = "https://www.tdx.com.cn/products/data/data/g4day/{ymd}.zip"
# 盘后包从这一天起带北交所文件（2026-09-20 二分实测：20220505 无、20220506 有）
TDX_BJ_FIRST_DAY = "20220506"
# 每个市场有收盘价的最少行数。2026-09-20 实测 2021-08-16 ~ 2026-09-18 共 11 个包的最小值：
# 沪 16202、深 3641（2022 年以前深市大部分代码当日无价）、京 87（2022-05-06），下限取明显低于最小值的整数
TDX_MIN_PRICED = {"sh": 10000, "sz": 3000, "bj": 50}


def _tdx_parse_package(content, ymd):
    """解析通达信每日增量包：每个市场一对 .cod（代码表，150 字节/条）+ .md1（行情块，512 字节/块）。
    布局参考 jing2uo/tdx2db（MIT）的 tdx/merge.go，已用 600519/000001/920000 与腾讯收盘价对拍。"""
    archive = zipfile.ZipFile(io.BytesIO(content))
    names = set(archive.namelist())
    rows = []
    for market in ("sh", "sz", "bj"):
        cod_name, md1_name = f"{market}{ymd[2:]}.cod", f"{market}{ymd[2:]}.md1"
        if (market == "bj" and ymd < TDX_BJ_FIRST_DAY
                and cod_name not in names and md1_name not in names):
            continue            # 这天之前的包还没有北交所文件；之后缺文件按格式改变报错
        if cod_name not in names or md1_name not in names:
            raise RuntimeError(f"通达信盘后包缺少 {cod_name}/{md1_name}，格式可能已变")
        cod, md1 = archive.read(cod_name), archive.read(md1_name)
        if len(cod) % 150 or len(md1) % 512:
            raise RuntimeError(f"{market} 代码表或行情块长度不是整块，文件可能被截断")
        if len(cod) // 150 != len(md1) // 512:
            raise RuntimeError(f"{market} 代码表 {len(cod) // 150} 条、行情块 {len(md1) // 512} 块，对不上")
        before, codes, seqs = len(rows), set(), set()
        for offset in range(0, len(cod), 150):
            record = cod[offset:offset + 150]
            # 11 个真实包（2021-08 ~ 2026-09）的代码全是 6 位 ASCII 数字；用 replace 解码会把坏字节变成 '\ufffd00000' 放行
            code = record[0:6].rstrip(b"\x00 ").decode("ascii", "replace")
            seq = struct.unpack("<H", record[32:34])[0]
            if not re.fullmatch(r"[0-9]{6}", code):
                raise RuntimeError(f"通达信盘后包 {market} 代码表出现非 6 位数字代码 {code!r}，格式可能已变")
            if code in codes or seq in seqs:
                raise RuntimeError(f"通达信盘后包 {market} 代码表有重复的代码 / 行情块序号（{code!r}, seq={seq}）")
            codes.add(code)
            seqs.add(seq)
            block = md1[seq * 512:(seq + 1) * 512]
            if len(block) != 512:
                raise RuntimeError(f"{market}{code} 行情块越界（seq={seq}）")
            prev_close = struct.unpack("<d", block[4:12])[0]
            open_, high, low, close = struct.unpack("<4d", block[12:44])
            amount = struct.unpack("<d", block[72:80])[0]
            # NaN 能绕过 close <= 0 被当成有价记录计入下限；11 个真实包里没有一个非有限值
            if not all(math.isfinite(v) for v in (prev_close, open_, high, low, close, amount)):
                raise RuntimeError(f"通达信盘后包 {market}{code} 行情块出现非有限数值，文件可能已损坏")
            if close <= 0:
                continue        # 880/881 等通达信自编板块指数当日无价，整块为 0，不是证券
            volume = struct.unpack("<Q", block[56:64])[0]
            raw_name = record[40:72].split(b"\x00")[0]
            try:                # replace 会把坏字节变成「�」当成正常名称返回（11 个真实包实测零替换字符）
                name = raw_name.decode("gbk").strip()
            except UnicodeDecodeError as exc:
                raise RuntimeError(f"通达信盘后包 {market}{code} 的名称不是 GBK，文件可能已损坏") from exc
            if not name:
                raise RuntimeError(f"通达信盘后包 {market}{code} 有价格却没有名称，文件可能已损坏")
            rows.append({"date": f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}", "market": market,
                         "code": code,
                         "name": name,
                         "prev_close": round(prev_close, 4), "open": round(open_, 4),
                         "high": round(high, 4), "low": round(low, 4),
                         "close": round(close, 4), "volume": volume,
                         "amount": round(amount, 2)})
        # 逐市场核对下限：只检查总行数会让沪深撑过门槛、北交所静默缺失
        if len(rows) - before < TDX_MIN_PRICED[market]:
            raise RuntimeError(f"通达信盘后包 {market} 市场只有 {len(rows) - before} 条有价记录"
                               f"（实测下限 {TDX_MIN_PRICED[market]}），文件可能残缺或格式已变")
    return rows


@_v39_contract
def tdx_daily_package(date):
    """通达信官网每日盘后包 — 某一交易日沪深北全部证券的日线（含成交额）。

    走 HTTP 下载（约 2.7MB），与 #52 失效的 TCP 行情命令是两条路。
    个股 volume 单位是「股」、amount 单位是「元」；指数等特殊代码的 volume 为通达信原值。
    非交易日或当日包尚未发布时官网返回 404，本函数抛 ValueError，不返回空表。
    历史包实测 2022-01-04、2023-01-03 可取，2021-01-04 已 404，未逐日验证；
    2022-05-06 之前的包没有北交所文件，只返回沪深，之后缺北交所文件会报错。
    某个市场有价记录少于 TDX_MIN_PRICED 的实测下限、代码不是 6 位数字或重复、行情块序号重复、
    代码表与行情块条数对不上、价格 / 成交额不是有限数，
    都按文件残缺抛 RuntimeError，不把部分市场当全市场返回。
    """
    ymd = _v39_date(date).replace("-", "")
    url = TDX_PACKAGE_URL.format(ymd=ymd)
    response = _v39_http(url, timeout=(10, 90), allow_status=(404,))
    if response.status_code == 404:
        raise ValueError(f"{date} 没有通达信盘后包：非交易日、当日包尚未发布（通常收盘后数小时），或早于官网保留范围（实测 2021-01-04 已没有）")
    if not response.content.startswith(b"PK"):
        raise RuntimeError("通达信盘后包不是 zip 文件，可能是错误页")
    try:
        rows = _tdx_parse_package(response.content, ymd)
    except (zipfile.BadZipFile, zlib.error, EOFError) as exc:      # 以 PK 开头但压缩包坏了 / 下载被截断
        raise RuntimeError(f"通达信盘后包 {url} 无法解压: {type(exc).__name__}: {exc}") from exc
    return _v39_frame(rows, "tdx", url)
```
<!-- v39-tdx-package:end -->

```python
snap = tdx_daily_package("2026-09-18")
print(len(snap), snap[snap.code == "600519"][["close", "volume", "amount"]])
```

### 1.4 腾讯逐笔成交 — 当日分笔明细（V3.10.0 新增 · 替代 §1.7 mootdx `transaction`）

§1.7 mootdx `transaction()` 2026-09 起返回空（#52）后的逐笔来源：腾讯行情页「成交明细」接口，一页 70 笔，逐页翻到空页为止，
全天 60–70 页、约 20–30 秒（复用连接；连接失败、等响应超时、429 / 5xx 自动重试）。先执行 Prerequisites 的 V3.9.0 共用 helper。

- **只有最近一个交易日**，没有历史；覆盖沪深个股（含创业板、科创板）与 ETF。北交所、指数没有，直接抛 `ValueError`。
- 是约 3 秒一笔的**分笔**（同一时刻撮合的多笔合并成一笔），不是交易所 Level-2 逐笔委托 / 逐笔成交。
  09:25 那一笔就是开盘集合竞价的撮合结果。
- `volume` 单位「手」（科创板也是手，和 §1.2 K 线不同：科创板按股成交、这里每笔取整成手，全天累加与真实股数有误差，成交越清淡越大：09-30 实测 688981 +0.013%、688001 −0.052%，成交清淡的 688184 +0.20%、688459 −0.16%）、`amount` 单位元；`side`：B = 主动买、S = 主动卖、M = 中性（集合竞价、盘后定价多为 M）。
- 收盘后 15:05–15:30 的盘后定价（固定价格）成交也在结果里（`time` 晚于 15:00:59 的行）；实测沪深主板、创业板、科创板、ETF 都有，
  不计入腾讯行情的当日成交额。
- **完整性核对：** 收盘后调用时，连续竞价段（≤ 15:00:59）的成交额合计要与腾讯行情快照的当日成交额相符，差超过 0.1% + 1000 元抛 `RuntimeError`
  （2026-09-22 实测 000001 / 600519 / 300750 / 688981 / 159915 / 000002 / 603286 相差 0–285 元）。
  盘中调用拿到的是截至取数时刻的逐笔，成交额还在变，不做这项核对，也不保证完整（翻页途中遇到空页就当作结束）。
- 腾讯偶尔缓存了盘后某一页的旧版本，会缺几笔盘后成交（实测 300750 缺 6 笔、159915 缺 7 笔，都在 15:14 以后）。
  连续竞价段缺号直接抛 `RuntimeError`，稍后重试；盘后段中间缺的序号记在 `frame.attrs["missing_seq"]`，末尾缺的从序号上看不出来。
- **`frame.attrs["complete"]`**：15:31 以后调用（看取数前那次快照的时刻），再用快照的盘后成交额（下标 58 的字段，万元）核对 15:00:59 以后的各笔，
  差不超过「笔数 + 1」元算对上（每笔金额取整到元）。
  `True` = 序号连续，连续竞价段和盘后定价的金额都对上；`False` = 盘后定价有缺笔（中间缺号，或末尾缺的金额超出容差），稍后重试；
  `None` = 没有缺号，但还在盘中、不到 15:31，或快照没有这个字段，没法核对。
  末尾缺的笔金额小时看不出来：低价 ETF 一笔 1–2 手只有几十元，落在容差里仍是 `True`（09-30 的 512170 盘后 46 笔、容差 47 元，缺一笔 1 手 35 元判不出）。
  2026-10-05 实测 10 只（沪深主板、创业板、科创板、ETF）09-30 的盘后各笔合计与该字段差 0–3 元。
- 开盘前（9:25 撮合前）调用可能拿不到上一交易日的逐笔。

<!-- v310-tencent-ticks:start -->
```python
import re
import time

TENCENT_TICK_URL = "https://stock.gtimg.cn/data/index.php"
TENCENT_QT_URL = "https://qt.gtimg.cn/q="
_TICK_MAX_PAGES = 300            # 一页 70 笔；2026-09-22 实测最活跃的票全天约 4800 笔 / 69 页
_TICK_SESSION_END = "15:00:59"   # 连续竞价 + 收盘集合竞价到此为止（科创板收盘那笔在 15:00:02），之后是盘后定价


def _tencent_qt_snapshot(symbol):
    """腾讯行情快照 → (交易日 'YYYY-MM-DD', 时刻 'HHMMSS', 当日成交额 元, 盘后定价成交额 元)。代码不存在抛 ValueError。
    盘后定价成交额是下标 58 的字段（万元、4 位小数）；字段没有或认不出时为 None，只是不做盘后核对。"""
    response = _v39_http(TENCENT_QT_URL + symbol, timeout=(5, 15), session=V39_RETRY_SESSION)
    text = response.content.decode("gbk", "replace")
    if "v_pv_none_match" in text:
        raise ValueError(f"腾讯没有 {symbol} 这个代码")
    match = re.search(rf'v_{symbol}="([^"]*)"', text)
    if not match:
        raise RuntimeError(f"腾讯行情快照 {symbol} 的返回里没有 v_{symbol} 变量，格式可能已变")
    fields = match.group(1).split("~")
    if len(fields) < 36 or not re.fullmatch(r"[0-9]{14}", fields[30]):
        raise RuntimeError(f"腾讯行情快照 {symbol} 字段数 {len(fields)} 或时间字段不对，格式可能已变")
    parts = fields[35].split("/")          # 「最新价/成交量/成交额(元)」；科创板的成交量是股、其余是手，所以只用成交额
    if len(parts) != 3:
        raise RuntimeError(f"腾讯行情快照 {symbol} 的价/量/额字段是 {fields[35]!r}，格式可能已变")
    after_hours = fields[58] if len(fields) > 58 else ""
    after_hours = round(float(after_hours) * 1e4, 2) if re.fullmatch(r"\d+(\.\d+)?", after_hours) else None
    return _v39_src_date(fields[30][:8]), fields[30][8:], _v39_req_num(parts[2], "成交额"), after_hours


def _tencent_tick_page(symbol, page):
    """第 page 页逐笔（0 起）→ 记录列表；翻过最后一页时腾讯返回空内容，返回 None。"""
    response = _v39_http(TENCENT_TICK_URL, params={"appn": "detail", "action": "data", "c": symbol, "p": page},
                         timeout=(5, 15), session=V39_RETRY_SESSION)
    text = response.content.decode("gbk", "replace").strip()
    if not text:
        return None
    match = re.fullmatch(rf'v_detail_data_{symbol}=\[(\d+),"([^"]*)"\];?', text)
    if not match or int(match.group(1)) != page:
        raise RuntimeError(f"腾讯逐笔 {symbol} 第 {page} 页不是预期格式: {text[:80]!r}")
    if not match.group(2):
        return None
    records = []
    try:
        for item in match.group(2).split("|"):
            seq, clock, price, change, volume, amount, side = item.split("/")
            if not re.fullmatch(r"\d\d:\d\d:\d\d", clock) or side not in ("B", "S", "M"):
                raise ValueError(item)
            records.append({"seq": int(seq), "time": clock, "price": _v39_req_num(price, "price"),
                            "change": _v39_req_num(change, "change"), "volume": _v39_req_num(volume, "volume"),
                            "amount": _v39_req_num(amount, "amount"), "side": side})
    except ValueError as exc:      # 字段数不对 / 序号不是整数 / 方向认不出：源格式变了，不是参数错
        raise RuntimeError(f"腾讯逐笔 {symbol} 第 {page} 页记录格式改变: {exc}") from exc
    return records


@_v39_contract
def tencent_ticks(code):
    """腾讯逐笔成交（分笔）— 最近一个交易日的全部成交明细，沪深个股与 ETF。

    一行一笔：date / code / time / seq（腾讯序号）/ price / change（较上一笔）/ volume（手）/ amount（元）/
    side（B 主动买 · S 主动卖 · M 中性）。约 3 秒一笔的分笔，不是 Level-2 逐笔。
    北交所、指数、代码不存在、当日没有成交抛 ValueError。收盘后调用会用行情快照的当日成交额核对连续竞价段，
    对不上抛 RuntimeError；盘后定价段腾讯偶尔缺几笔：中间缺的序号在 frame.attrs["missing_seq"]，
    15:31 以后再用快照的盘后成交额核对，结果在 frame.attrs["complete"]（True 对上 / False 有缺 / None 没法核对；
    低价 ETF 一两手的小额缺笔可能看不出）。
    """
    prefix, ticker = get_prefix(code), norm_ticker(code)
    if prefix == "bj":
        raise ValueError("腾讯逐笔不支持北交所（返回空）；北交所日线见 §1.3 tdx_daily_package")
    if (prefix, ticker[:3]) in (("sh", "000"), ("sz", "399")):
        raise ValueError(f"{prefix}{ticker} 是指数，没有逐笔成交")
    symbol = prefix + ticker
    day, clock, amount_before, after_hours_before = _tencent_qt_snapshot(symbol)
    if amount_before == 0:
        raise ValueError(f"{symbol} 在 {day} 没有成交（停牌、尚未开盘或集合竞价未撮合）")
    rows, missing = [], []
    for page in range(_TICK_MAX_PAGES):
        records = _tencent_tick_page(symbol, page)
        if records is None:
            break
        for r in records:
            expected = rows[-1]["seq"] + 1 if rows else 0
            if r["seq"] < expected or (rows and r["time"] < rows[-1]["time"]):
                raise RuntimeError(f"腾讯逐笔 {symbol} 序号或时间倒退（第 {page} 页 {r['seq']} {r['time']}），结果不可信")
            if r["seq"] > expected:
                if r["time"] <= _TICK_SESSION_END:
                    raise RuntimeError(f"腾讯逐笔 {symbol} 缺序号 {expected}–{r['seq'] - 1}（{r['time']} 之前，第 {page} 页），"
                                       "腾讯该页缓存不完整，稍后重试")
                missing.extend(range(expected, r["seq"]))
            rows.append(r)
        time.sleep(0.1)
    else:
        raise RuntimeError(f"腾讯逐笔 {symbol} 翻到第 {_TICK_MAX_PAGES} 页仍未结束，格式可能已变")
    if not rows:
        if clock < "092500":
            raise ValueError(f"{symbol} 集合竞价尚未撮合（{clock}），还没有逐笔")
        raise RuntimeError(f"{symbol} 在 {day} 成交 {amount_before:.0f} 元，腾讯逐笔却为空："
                           "开盘前腾讯可能已清空上一交易日的明细，否则是接口变了")
    day_after, clock_after, amount_after, after_hours_after = _tencent_qt_snapshot(symbol)
    if day_after != day:
        raise RuntimeError(f"取数期间交易日从 {day} 变成 {day_after}，请重试")
    session = sum(r["amount"] for r in rows if r["time"] <= _TICK_SESSION_END)
    # 两次快照成交额相同说明取数期间没有新成交（收盘后 / 午休 / 停牌），此时连续竞价段逐笔合计应与当日成交额相符
    if amount_after == amount_before and abs(session - amount_before) > amount_before * 0.001 + 1000:
        raise RuntimeError(f"腾讯逐笔 {symbol} 连续竞价段成交额 {session:.0f} 元，与行情快照 {amount_before:.0f} 元对不上，"
                           "逐笔可能不全")
    # 盘后定价 15:30 结束（深市最后一笔可能正好在 15:30:00）。取数前的快照已在 15:31 以后、两次快照一致时，
    # 15:00:59 以后各笔成交额合计应等于快照的盘后成交额（每笔取整到元，差不超过笔数 + 1 元）；
    # 中间缺号、末尾缺笔都会对不上，但末尾缺的金额小于容差（低价 ETF 一两手）时看不出。盘中 / 15:31 前没法核对，记 None。
    after_hours = [r["amount"] for r in rows if r["time"] > _TICK_SESSION_END]
    complete = None
    if missing:
        complete = False
    elif (amount_after == amount_before and after_hours_before is not None
          and after_hours_after == after_hours_before and clock >= "153100"):
        complete = abs(sum(after_hours) - after_hours_before) <= len(after_hours) + 1
    frame = _v39_frame(rows, "tencent", f"{TENCENT_TICK_URL}?appn=detail&action=data&c={symbol}",
                       ["time", "seq", "price", "change", "volume", "amount", "side"])
    frame.insert(0, "date", day)
    frame.insert(1, "code", symbol)
    frame.attrs["missing_seq"] = missing
    frame.attrs["complete"] = complete
    return frame
```
<!-- v310-tencent-ticks:end -->

```python
ticks = tencent_ticks("000001")                     # 平安银行最近一个交易日全部分笔
ticks.attrs["complete"]                             # 15:31 以后：True 对上 / False 盘后有缺笔；盘中为 None
auction = ticks[ticks.time < "09:30:00"]            # 开盘集合竞价撮合那一笔（科创板在 09:25:0x）
buy = ticks.loc[ticks.side == "B", "amount"].sum()  # 主动买入额
etf = tencent_ticks("510300")                       # ETF 同样可用
```

### 1.5 百度股市通 K线 — 带MA5/MA10/MA20（V3.0 新增）

**核心价值：** 返回时自带均线数据，无需本地计算。

```python
import requests

def baidu_kline_with_ma(code: str, start_time: str = "") -> dict:
    """百度股市通K线 — 独有能力: 返回时自带 ma5/ma10/ma20 均价"""
    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    d = r.json()
    result = d.get("Result", {})
    md = result.get("newMarketData", {})
    keys = md.get("keys", [])  # includes: ma5avgprice, ma10avgprice, ma20avgprice
    rows = md.get("marketData", "").split(";")
    return {"keys": keys, "rows": rows}

# 用法
data = baidu_kline_with_ma("600519")
print("字段:", data["keys"][:10])
print("最近5根K线:", data["rows"][-5:])
# keys 包含: time, open, close, high, low, volume, amount, ma5avgprice, ma10avgprice, ma20avgprice 等
```

### 1.6 新浪复权因子 — qfq / hfq（V3.7.0 新增）

**核心价值：** §1.7 `tdx_client().bars()`、§1.2 `tencent_kline(adjust='')`、§1.3 `tdx_daily_package()` 返回的是**不复权**数据，跨除权日直接比价必然出错。
本端点给出复权因子序列，一次 HTTP、约 1.8KB、零鉴权。

```python
import json
import re

import requests


def sina_adjust_factor(code: str, kind: str = "qfq") -> list:
    """新浪复权因子序列 — kind='qfq'(前复权) | 'hfq'(后复权)，按日期倒序（最新在前）"""
    if kind not in ("qfq", "hfq"):
        raise ValueError(f"kind 只能是 'qfq' 或 'hfq'，收到 {kind!r}")
    # 数字位用 norm_ticker() 剥掉前后缀（否则 "sz000016" 会拼成 "szsz000016" ——
    # zfill(6) 对 8 字符输入不做任何事）。
    raw = str(code).strip()
    digits = norm_ticker(raw)
    # 市场：**显式写法优先**——前缀或 `.SH` 后缀直接采信（V3.7.1 起 get_prefix() 也认后缀，
    # 本地显式匹配保留，语义不变）。都没写显式市场时，才用 get_prefix() 按号段推断
    # （它已处理 92 必须先于 9x）。
    m = re.match(r"^(sh|sz|bj)", raw, re.I) or re.search(r"\.(sh|sz|bj|xshg|xshe)$", raw, re.I)
    prefix = {"xshg": "sh", "xshe": "sz"}.get(m.group(1).lower(), m.group(1).lower()) if m else get_prefix(digits)
    symbol = f"{prefix}{digits}"
    url = f"https://finance.sina.com.cn/realstock/company/{symbol}/{kind}.js"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0",
                                   "Referer": "https://finance.sina.com.cn/"}, timeout=10)
    r.raise_for_status()
    # 🔴 响应形如 `var sh600519qfq={...}` 且**末尾挂着 /* base64 */ 注释块**，
    #    不能用 $ 锚定正则。从第一个 { 起用 raw_decode，让解析器自己在 JSON 结束处停下。
    text = r.text
    brace = text.find("{")
    if brace < 0:
        raise RuntimeError(f"新浪复权因子响应无 JSON（{symbol}/{kind}）: {text[:120]}")
    try:
        data, _ = json.JSONDecoder().raw_decode(text[brace:])
    except json.JSONDecodeError as e:
        raise RuntimeError(f"新浪复权因子 JSON 解析失败（{symbol}/{kind}）: {e}") from e
    return [{"date": it["d"], "factor": float(it["f"])} for it in data.get("data", [])]


def apply_adjust(bars, factors: list, kind: str = "qfq",
                 price_keys=("open", "high", "low", "close")):
    """把复权因子套到不复权 K 线上。

    `bars` 接受两种形态：
      - **§1.7 `tdx_client().bars()` 的 DataFrame**（日期列名是 `datetime`）或 §1.2 `tencent_kline(adjust='')` 的 DataFrame（`date` 列）→ 返回 DataFrame
      - list[dict]（需含 `date` 键）→ 返回 list[dict]

    🔴 **qfq 与 hfq 的运算方向相反，必须传对 kind**：
      - `qfq`（前复权）因子是**除数**：`前复权价 = 不复权价 ÷ factor`
      - `hfq`（后复权）因子是**乘数**：`后复权价 = 不复权价 × factor`
    传错方向不会报错，只会把历史价格放大/缩小几倍（见下方实测对照表）。

    因子表是「生效日 → 因子」的阶梯，每根 K 线取**不晚于它**的最近一个因子。
    """
    if kind not in ("qfq", "hfq"):
        raise ValueError(f"kind 只能是 'qfq' 或 'hfq'，收到 {kind!r}")
    # 🔴 因子为空时绝不能「原样返回」—— 那会把不复权价当成复权价交出去，
    #    调用方拿到的数字看着正常却是错的（新浪对不支持的标的就返回空 data）。
    if not factors:
        raise ValueError(
            "复权因子列表为空，无法复权。请先确认 sina_adjust_factor() 是否取到数据"
            "（新浪对不支持的标的会返回空 data），不要用未复权价继续计算。"
        )

    is_df = hasattr(bars, "columns") and hasattr(bars, "to_dict")
    if is_df:
        # mootdx bars() 的日期列叫 datetime，且可能带时分秒，统一截成 YYYY-MM-DD
        date_col = next((c for c in ("date", "datetime") if c in bars.columns), None)
        if date_col is None:
            raise ValueError(f"DataFrame 需含 date 或 datetime 列，实际列={list(bars.columns)}")
        rows = bars.to_dict("records")
        for r in rows:
            r["date"] = str(r[date_col])[:10]
    else:
        rows = [dict(b) for b in bars]
        for r in rows:
            if "date" not in r:
                raise ValueError(f"每根 K 线需含 'date' 键，实际键={sorted(r)}")
            r["date"] = str(r["date"])[:10]

    fac = sorted(factors, key=lambda x: x["date"])
    out, i, cur = [], 0, None
    for bar in sorted(rows, key=lambda b: b["date"]):
        while i < len(fac) and fac[i]["date"] <= bar["date"]:
            cur = fac[i]["factor"]
            i += 1
        # 🔴 早于最早因子日的 K 线不能原样放行 —— 那会让一份结果里混着「已复权」和
        #    「未复权」两种价格且无从分辨。新浪的因子表通常带 1900-01-01 哨兵
        #    （实测 600519/000001/300750/688981/000004/601398 六只均是），
        #    真出现未覆盖行，说明因子表异常，必须显式失败。
        if cur is None:
            raise RuntimeError(
                f"K 线日期 {bar['date']} 早于因子序列最早日 {fac[0]['date']}，"
                "无法复权；不返回未复权价以免与已复权行混淆。"
            )
        if cur == 0:
            raise RuntimeError(f"复权因子为 0（{bar['date']}），无法换算")
        nb = dict(bar)
        for k in price_keys:
            if k in nb and nb[k] is not None:
                v = float(nb[k])
                nb[k] = round(v / cur if kind == "qfq" else v * cur, 4)
        nb["adj_factor"] = cur
        out.append(nb)
    if is_df:
        import pandas as pd
        res = pd.DataFrame(out)
        # mootdx 的 bars() 带 DatetimeIndex，重建 DataFrame 会退化成 RangeIndex，
        # 下游按时间切片 / resample / 时间对齐 join 都会失效。按排序后的顺序还原索引。
        if getattr(bars, "index", None) is not None and not isinstance(
            bars.index, pd.RangeIndex
        ):
            order = sorted(range(len(bars)), key=lambda n: str(bars.iloc[n][date_col])[:10])
            res.index = bars.index[order]
            res.index.name = bars.index.name
        return res
    return out


# 用法
qfq = sina_adjust_factor("600519", "qfq")
hfq = sina_adjust_factor("600519", "hfq")
print(len(qfq), "条 | 最新", qfq[0], "| 最早", qfq[-1])
# 实测 2026-08-19：33 条
#   qfq 最新 {'date': '2026-06-26', 'factor': 1.0}          ← 前复权以最新为基准
#   hfq 最早 {'date': '1900-01-01', 'factor': 1.0}          ← 后复权以最早为基准

bars = [{"date": "2015-01-05", "close": 202.52}]         # 茅台当日不复权收盘价
print(apply_adjust(bars, qfq, kind="qfq"))                # → 143.46（前复权，除法）
print(apply_adjust(bars, hfq, kind="hfq"))                # → 1274.28（后复权，乘法）
```

**方向实测对照（2026-08-19，以 baostock `adjustflag` 为基准交叉验证）**

| 日期 | 不复权 | baostock 前复权 | `raw × qfq` | `raw ÷ qfq` |
|------|--------|----------------|-------------|-------------|
| 2015-01-05 | 202.52 | **143.46** | 285.90 ❌ | **143.46** ✅ |
| 2026-08-14 | 1341.99 | 1341.99 | 1341.99 ✅ | 1341.99 ✅ |

> `qfq` 因子恒 ≥ 1 且越往历史越大，**乘上去会把历史价格放大**，必须做除法。
> 2026 那行两种算法都对，是因为最新日因子恰为 1.0 —— **只用最近日期做验证会漏掉这个 bug**。
>
> ⚠️ **hfq 的基准与 baostock 不同**：新浪 `raw × hfq` 与 baostock 后复权价差一个**恒定倍数**
> （实测 1.1582，2015 与 2026 两点一致）。后复权序列整体缩放不影响收益率与形态，
> 但**不要把新浪后复权价与其它源的后复权价直接比数值**。

> ⚠️ **北交所无复权因子**：实测 `bj920982` 返回 **404**（新浪未提供北交所的 qfq/hfq 文件），
> 本函数会抛 `HTTPError`。北交所标的请改用 §1.3 通达信盘后包的不复权日线，并自行按分红送转推导。
>
> **自检口径（实测 2026-08-19 校准）：**
> - `qfq` 序列**最新**一条因子恒为 `1.0`；`hfq` 序列**最早**一条恒为 `1.0`。
> - 同一日期上 **`qfq(d) × hfq(d)` 恒等于一个常数**（该标的全期总复权系数，茅台实测 `8.882513`）。
>   ⚠️ 两者**不是倒数**（乘积不为 1），比值 `hfq/qfq` 也**不恒定**（茅台 33 个日期有 32 种取值）——
>   两个基准不同的归一化序列，只有乘积守恒。
> 不满足以上任一条，说明响应被截断或标的代码写错。

### 1.7 mootdx — K线 + 五档盘口 + 逐笔成交（⚠️ 2026-09 起行情命令失效，留档）

TCP 二进制协议，连通达信服务器(7709)，无需注册，不封IP。

> **⚠️ 2026-09 起本节普遍取不到数（#52）：** 通达信公开服务器 TCP 仍可达，但 `bars` / `quotes` / `transaction`
> 返回 0 行（2026-09-20 逐台实测内置 10 台，全部如此）；`tdx_client()` 会在约 1 分钟测速后抛出带指引的 RuntimeError。
> 替代：**K 线 → §1.2 `tencent_kline()`**（沪深日周月前/后复权 + 1~60 分钟）或 **§1.3 `tdx_daily_package()`**（沪深北全市场某日含成交额，北交所日线只能走这里）；
> **实时价 / 五档 → §1.1 腾讯**；**逐笔 → §1.4 `tencent_ticks()`**（只有当日）。财务与 F10（§6.1 / §6.2 / §7.2）不受影响。以下代码保留，服务器恢复后可照常使用。

```python
from mootdx.quotes import Quotes

client = tdx_client()  # 见 Prerequisites 的 tdx_client() helper（规避 0.11.x BESTIP bug；等价 Quotes.factory(market='std')）

# === K线数据 ===
# ⚠️ 参数名是 frequency（不是 category！传 category 会被 **kwargs 静默吞掉，
#    永远退化成默认 frequency=9 日线，拿不到分钟数据）。
# mootdx 0.11.7 实测频率值表：
#   0=5分钟  1=15分钟  2=30分钟  3=60分钟(1小时)  4=日线  5=周线  6=月线
#   8=1分钟  9=日线(默认)  10=季线  11=年线        （7=1分钟除权口径,少用）
klines = client.bars(symbol='688017', frequency=9, offset=10)    # 日线
min1   = client.bars(symbol='688017', frequency=8, offset=240)   # 1分钟（一个交易日≈240根）
min5   = client.bars(symbol='688017', frequency=0, offset=48)    # 5分钟
# 返回: open, close, high, low, vol, amount, datetime
# ⚠️ 复权：bars 返回【不复权】原始价（通达信原始数据，无 adjust 参数）。
#    跨除权除息日做估值/回测前需自行复权，或改用带前复权的日K数据源（腾讯财经）。

# === 实时报价 ===
quotes = client.quotes(symbol=['688017', '300476'])
# 返回 46 个字段:
#   price(现价), open, high, low, last_close(昨收)
#   bid1~bid5, ask1~ask5, bid_vol1~bid_vol5, ask_vol1~ask_vol5
#   vol(成交量), amount(成交额), servertime

# === 逐笔成交（非交易时间返回空）===
trades = client.transaction(symbol='688017', date='20260502')
# 返回: time, price, vol, num, buyorsell(0买/1卖/2中性)
```

**mootdx 不提供 PE / PB / 市值 / 换手率 / 涨跌停价** — 这些走腾讯财经。

---
