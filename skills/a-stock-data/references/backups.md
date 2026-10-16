> 本文件汇集：官方两融与北交所行情备胎、34 个数据源详表、备用源速查 & 降级策略、东财实测封禁案例与降级路径（自原「数据源优先级 & 东财防封」节移入）。
> 官方两融 / 北交所备胎依赖 `references/layer-12-index.md` 的 §12 helper，先执行它。

## 官方两融与北交所行情备胎（V3.8.0）

先执行 Layer 12 的完整自包含代码块，再执行下列代码块。新增两个**能力入口**，按入口计数，
不将同一函数的交易所路由重复算成端点。使用 `margin_trading_backup("2026-09-03", "SH")`
或 `"SZ"` 分别取数，`code="600519"` 可在完整快照中筛选个股；未指定代码时包含源侧融资融券标的（也含 ETF）。
两所发布进度可能不同，不能将单所结果标成沪深全市场。源未发布该日数据时抛错，完整列表中
个股未命中则返回有列定义的空表。

**单位及字段：** `margin_balance` / `margin_buy` / `short_balance` 为元；
`short_volume` / `short_sell_volume` 为股或份。上交所 `short_balance` 源值为空时保留为空，
不以余量乘价格冒充官方金额。该备胎并非东财所有字段的等价替代，深交所不含两种偿还字段。

`bse_quote_backup("2026-09-04", code="920021")` 只接受沪深北中的 **北交所纯 6 位代码**；
省略 `code` 拉全板。首参是调用方期望的交易日，必须与源侧每行日期一致，返回五档盘快照
（价格元、量股）、OHLC、成交量额、`pe_source`（官网字段口径未细分，不称 PE-TTM）。
**这是当前快照，没有历史回填，也未验证盘中更新延迟；不是逐笔 Level-2。**

<!-- official-data-backups:start -->
```python
import json
import time


def _official_total(value):
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise RuntimeError("官方分页总数必须为非负整数")
    return int(value)


def _official_margin_code(value, exchange):
    code = _official_code(value)
    prefixes = ("5", "6", "900") if exchange == "SH" else ("0", "1", "2", "3")
    if not code.startswith(prefixes):
        raise ValueError("两融证券代码与请求的交易所不符")
    return code


def margin_trading_backup(trade_date, exchange, code=None):
    """一次只取一个交易所。未发布抛错；完整源中筛不到 code 才返回空表。"""
    trade_date = _official_date(trade_date)
    exchange = str(exchange).upper()
    if exchange not in ("SH", "SZ"):
        raise ValueError("exchange 必须为 SH 或 SZ；本函数不覆盖北交所两融")
    if code is not None:
        code = _official_margin_code(code, exchange)
    if exchange == "SH":
        url = "https://query.sse.com.cn/marketdata/tradedata/queryMargin.do"
        response = _official_get(url, {
            "isPagination": "true", "tabType": "mxtype", "detailsDate": trade_date.replace("-", ""),
            "pageHelp.pageSize": 5000, "pageHelp.pageNo": 1, "pageHelp.beginPage": 1,
            "pageHelp.cacheSize": 1, "pageHelp.endPage": 1,
        }, "https://www.sse.com.cn/")
        page = response.json().get("pageHelp") or {}
        data = page.get("data")
        if not isinstance(data, list) or not data or len(data) != _official_total(page.get("total")):
            raise RuntimeError("上交所该日数据未发布或分页不完整")
        fields = {"rzye": "margin_balance", "rzmre": "margin_buy", "rqylje": "short_balance",
                  "rqyl": "short_volume", "rqmcl": "short_sell_volume"}
        rows = []
        for rec in data:
            if _official_date(rec.get("opDate")) != trade_date:
                raise RuntimeError("上交所两融数据日期不符")
            if not set(fields).issubset(rec):
                raise RuntimeError("上交所两融字段发生变化")
            rows.append({"date": trade_date, "code": _official_margin_code(rec["stockCode"], exchange),
                         "name": rec.get("securityAbbr"), "exchange": exchange,
                         **{dest: _official_number(rec[src], required=(src != "rqylje"))
                            for src, dest in fields.items()}})
    else:
        url = "https://www.szse.cn/api/report/ShowReport"
        response = _official_get(url, {"SHOWTYPE": "xlsx", "CATALOGID": "1837_xxpl",
                                      "TABKEY": "tab2", "txtDate": trade_date}, "https://www.szse.cn/")
        data = _official_excel(response)
        fields = {"融资余额(元)": "margin_balance", "融资买入额(元)": "margin_buy",
                  "融券余额(元)": "short_balance", "融券余量(股/份)": "short_volume",
                  "融券卖出量(股/份)": "short_sell_volume"}
        _official_columns(data, ["证券代码", "证券简称", *fields])
        rows = [{"date": trade_date, "code": _official_margin_code(str(rec["证券代码"]).zfill(6), exchange),
                 "name": rec["证券简称"], "exchange": exchange,
                 **{dest: _official_number(rec[src], required=True) for src, dest in fields.items()}}
                for rec in data.to_dict("records")]
    frame = _official_frame(rows, ["date", "code"], "sse" if exchange == "SH" else "szse", response.url)
    return frame if code is None else frame.loc[frame.code == code].reset_index(drop=True)


def bse_quote_backup(trade_date, code=None):
    """北交所当前全板/单票快照；拒绝用当前数据回填其他交易日。"""
    trade_date = _official_date(trade_date)
    if code is not None:
        code = _official_code(code)
        if not code.startswith(("4", "8", "92")):
            raise ValueError("请输入北交所代码（4/8/92 开头）")
    page_url = "https://www.bse.cn/nq/quotation.html"
    url = "https://www.bse.cn/nqhqController/nqhq_en.do"
    raw_rows = []
    total = None
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": page_url,
                                "Accept": "application/json, text/javascript, */*; q=0.01"})
        # 官网有时设置匿名 Cookie 后 302 回自己；不跟随重定向，避免循环。
        session.get(page_url, timeout=(10, 40), allow_redirects=False).raise_for_status()
        for page_number in range(100):
            form = {"page": page_number, "type_en": '["B"]', "sortfield": "hqzqdm",
                    "sorttype": "asc", "xxfcbj_en": "[2]", "zqdm": code or ""}
            response = session.post(url, data=form, timeout=(10, 40), allow_redirects=False)
            if 300 <= response.status_code < 400:
                session.get(page_url, timeout=(10, 40), allow_redirects=False).raise_for_status()
                response = session.post(url, data=form, timeout=(10, 40), allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise RuntimeError("北交所匿名会话尚未建立")
            payload = response.text.strip()
            match = re.fullmatch(r"[A-Za-z_$][\w$]*\((.*)\);?", payload, re.S)
            data = json.loads(match.group(1) if match else payload)
            if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0].get("content"), list):
                raise RuntimeError("北交所行情响应结构异常")
            current_total = _official_total(data[0].get("totalElements"))
            if total is not None and total != current_total:
                raise RuntimeError("分页期间北交所记录总数变化，请重试")
            total = current_total
            batch = data[0]["content"]
            if total < 0 or not batch:
                raise RuntimeError("北交所未返回目标行情或分页提前结束")
            raw_rows.extend(batch)
            if len(raw_rows) >= total:
                break
            time.sleep(0.2)
        if len(raw_rows) != total:
            raise RuntimeError("北交所分页不完整，不能标记全板成功")
    fields = {"hqjrkp": "open", "hqzgcj": "high", "hqzdcj": "low", "hqzjcj": "close",
              "hqzrsp": "previous_close", "hqcjsl": "volume", "hqcjje": "amount"}
    rows = []
    for rec in raw_rows:
        if _official_date(rec.get("hqjsrq")) != trade_date:
            raise RuntimeError("北交所快照不是请求的交易日；本接口不提供历史回填")
        ticker = _official_code(rec.get("hqzqdm"))
        if not ticker.startswith(("4", "8", "92")) or (code is not None and ticker != code):
            raise RuntimeError("北交所返回了请求范围之外的标的")
        row = {"date": trade_date, "code": ticker, "name": rec.get("hqzqjc"), "exchange": "BJ",
               "quote_time": str(rec.get("hqgxsj", "")), "pe_source": _official_number(rec.get("hqsyl1")),
               **{dest: _official_number(rec.get(src), required=True) for src, dest in fields.items()}}
        for level in range(1, 6):
            for src, dest in (("hqbjw", "bid_price"), ("hqbsl", "bid_volume"),
                              ("hqsjw", "ask_price"), ("hqssl", "ask_volume")):
                row[f"{dest}_{level}"] = _official_number(rec.get(f"{src}{level}"), required=True)
        rows.append(row)
    return _official_frame(rows, ["date", "code"], "bse", url)
```
<!-- official-data-backups:end -->

```python
sh_margin = margin_trading_backup("2026-09-03", "SH", code="600519")
sz_margin = margin_trading_backup("2026-09-03", "SZ", code="000001")
bj_quote = bse_quote_backup("2026-09-04", code="920021")
```

端点与字段交叉参考 [CNEquity 两融适配](https://github.com/rootSunc/CNEquity/blob/main/src/cnequity/adapters/exchange/margin_trading.py)
及 [北交所适配](https://github.com/rootSunc/CNEquity/blob/main/src/cnequity/adapters/bse/daily_quotes.py)。
本版只参考官方端点与字段契约，数据直接来自交易所。

## 数据源优先级

| 优先级 | 数据源 | 用途 | 可靠性 | 封IP风险 |
|--------|--------|------|--------|---------|
| 1 | **腾讯财经** (HTTP) | 实时PE/PB/市值/换手率/涨跌停/指数/ETF + 日周月/分钟 K 线（§1.2）+ 当日逐笔（§1.4） | 稳定 | 低（K 线单入口约 600 次后限流，已三入口轮换） |
| 2 | **mootdx** (TCP) | 财务快照+F10；K线/五档/逐笔 2026-09 起返回空（#52） | 财务/F10 稳定，行情命令失效 | 极低 |
| 3 | **东财 datacenter** (HTTP) | 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红/个股信息 | 稳定 | 低 |
| 4 | **东财 push2/push2his** (HTTP) | 行业板块/个股资金流分钟级+120日 | 稳定 | 低 |
| 5 | **iwencai** (OpenAPI) | NL主题搜索研报(唯一能力) | 需X-Claw Header | 低 |
| 6 | **东财 reportapi/PDF** (HTTP) | 完整研报图表、评级 | 稳定 | 低 |
| 7 | **同花顺热点** (HTTP) | 当日强势股+题材归因 reason tags | 稳定 73ms | 极低（零鉴权） |
| 8 | **同花顺 hsgtApi** (HTTP) | 北向资金分钟级+自缓存历史 | 稳定 | 极低（零鉴权） |
| 9 | **百度股市通** (HTTP) | 概念板块+K线带MA | 稳定 | 极低（零鉴权） |
| 10 | **新浪财经** (HTTP) | 资产负债表/利润表/现金流量表 | 稳定 | 低 |
| 11 | **同花顺 basic** (HTTP) | 一致预期EPS | 稳定(需UA) | 低 |
| 12 | **财联社** (HTTP) | 全市场实时电报 | 稳定 | 低 |
| 13 | **巨潮 cninfo** (HTTP) | 公告全文检索+下载 | 稳定 | 低 |
| 14 | **上交所官方** (HTTP，备胎) | 龙虎榜全文/实时五档/两融明细 | 一手官方源，两融须核对日期与完整性 | 零鉴权，避免高频请求 |
| 15 | **深交所官方** (HTTP) | 龙虎榜/公告+PDF/实时五档/两融明细/交易日历 | 一手官方源，日历须完整、两融须已发布 | 零鉴权，避免高频请求 |
| 16 | **baostock** (TCP，V3.7) | 估值历史PE/PB/PS/PCF+换手率+停牌+ST+上市退市日 | 稳定（免注册） | 极低；**不支持北交所** |
| 17 | **申万研究** (HTTP，V3.7) | 行业分类变迁史（公开 XLS） | 稳定 | 极低（公开文件） |
| 18 | **人民银行** (HTTP，V3.7) | 社会融资规模增量（月度，2021 年起） | 稳定（官方站） | 极低 |
| 19 | **国家统计局** (HTTP，V3.7) | PMI 制造业/非制造业/综合+大中小型 | 稳定（官方站） | 极低 |
| 20 | **中证指数** (HTTP，V3.8) | 指数成分/权重/两种口径 PE 与股息率 | 官方文件，2026-09-05 验证 | 零鉴权，避免高频重复下载 |
| 21 | **国证指数** (HTTP，V3.8) | 最近公布的指数成分/权重 | 官方月末文件，2026-09-05 验证 | 零鉴权，避免高频重复下载 |
| 22 | **北交所官方** (HTTP，V3.8，备胎) | 当前行情/五档/成交量额 | 当前快照，须核对日期 | 匿名 Cookie 会话，分页限速 |
| 23 | **通达信官网盘后包** (HTTP，V3.9) | 某交易日沪深北全市场日线（含成交额） | 官方文件，2026-09-20 抽查 2022-01-04、2023-01-03 可取（2021-01-04 已没有），未逐日验证 | 极低（单个 zip 约 2~3 MB） |
| 24 | **华尔街见闻** (HTTP，V3.9) | 7×24 快讯 + 全球宏观日历 | 稳定 | 低 |
| 25 | **央视网** (HTTP，V3.9) | 新闻联播条目 + 文字稿 | 稳定，当天节目约 20:00 后才有 | 极低 |
| 26 | **上证e互动** (HTTP，V3.9) | 沪市投资者问答 | 官方源 | 零鉴权，避免高频请求 |
| 27 | **中债（中央结算公司）** (HTTP，V3.9) | 国债 / 银行 AAA / 中短票 AAA 收益率曲线 | 官方源，单次区间 ≤ 1 年 | 极低 |
| 28 | **中国货币网（外汇交易中心）** (HTTP，V3.9) | 回购定盘利率 FR / FDR | 官方源，FR 约近 3 年、FDR 约近 1 年 | 极低 |
| 29 | **上期所** (HTTP，V3.9) | 期货 / 期权日行情 + 会员持仓排名 | 官方源 | 零鉴权，避免高频请求 |
| 30 | **上期能源** (HTTP，V3.9) | 原油 / 国际铜等期货期权日行情 + 持仓排名 | 官方源（与上期所同格式） | 零鉴权，避免高频请求 |
| 31 | **郑商所** (HTTP，V3.9) | 期货 / 期权日行情 + 持仓排名 | 官方源 | 零鉴权，避免高频请求 |
| 32 | **中金所** (HTTP，V3.9) | 股指 / 国债期货 + 股指期权日行情 + 持仓排名 | 官方源 | 零鉴权，避免高频请求 |
| 33 | **广期所** (HTTP，V3.9) | 工业硅 / 碳酸锂等期货期权日行情 | 官方源 | 零鉴权，避免高频请求 |
| 34 | **上金所** (HTTP，V3.9) | 黄金 / 白银 / 铂金现货日线 | 官方源 | 零鉴权，避免高频请求 |

> V3.9 复用的已有来源不重复计数：腾讯（§1.2 K 线）、新浪（§2.4 研报、§13.4 实时期货、§13.5 A50）、
> 东财（§6.8 ST 名单、§11.5 LPR、Layer 14 事件驱动、Layer 15 可转债）、上交所 / 深交所（§4.7 ETF 份额）。
> 上证e互动虽由上交所运营，但域名和接口独立，单列为第 26 个来源。
> V3.10 的 §1.4 腾讯逐笔、§13.7 新浪期货日 K 同样复用已有来源，来源数不变。
> 大商所官网有反爬，未接入；大商所品种的逐日 K 线用 §13.7、实时价用 §13.4（均为新浪）。

**原则：** 行情走腾讯（§1.2 K 线、§1.4 逐笔）+ 通达信官网盘后包，mootdx 只用于财务 / F10（#52）；研报走东财+iwencai，新浪作第二来源；资金面走东财 datacenter+push2，**信号层走同花顺+百度+东财直连接口**；期货、利率、黄金走交易所与官方机构。除 mootdx / baostock 两个 TCP 客户端外全部直连 HTTP。

**降级：** 任一主源被封/失效时，先查下方「备用源速查 & 降级策略」——每类数据都备有一条**不同域名、不同风控面**的独立备胎（交易所官方/新浪/同花顺），东财被封时它们不受牵连。

---


## 附：东财实测封禁案例与降级路径（自防封节移入）

### ⚠️ 实测封禁案例（2026-06-30，一手数据，感谢 [@luodada99](https://github.com/luodada99) issue #36）

上表是社区口径；下面这条是**真实踩到 IP 级封禁**的完整记录，比阈值表更有参考价值：

- **触发方式**：选股脚本 10 线程并发、**完全不走 `em_get()` 限流**，1 小时内发出 45000+ 请求（三个版本的脚本同时跑全市场 5208 只）
- **后果**：`push2` / `push2his` **全系列** `RemoteDisconnected`，**IP 级封禁持续 20+ 小时**——不是"几分钟到几小时"那种临时限速
- **关键观察一**：`datacenter-web.eastmoney.com` **不受影响**——东财不同子域走不同 WAF，`push2` 被封不代表整个东财都不能用
- **关键观察二**：**腾讯 K 线（`web.ifzq.gtimg.cn`）连续 5000+ 次后会返回空**，但这是**限流不是封 IP**，降速或换新浪即可恢复
- **降级实测**：东财被封时，第一只股票花 10.9s 完成"检测被封 + 降级"，之后每只 0.4s 走腾讯，数据准确

**这个案例正是「限流是铁律」的实证**：`em_get()` 的默认间隔（1s + 抖动、串行）下，1 小时最多约 3000 次请求，与踩坑者的 45000 次差一个数量级。

**被封后的降级路径**（各层备胎详见「备用源速查」章节）：

| 被封端点 | 替代方案 | 差异 |
|---|---|---|
| `push2/clist/get`（股票列表） | `datacenter-web` + 腾讯行情批量 | 行业字段来自 datacenter 的 `BOARD_NAME` |
| `push2his/kline/get`（K线） | 腾讯 `fqkline/get`（前复权）→ 新浪 `getKLineData`（不复权） | 腾讯有前复权，新浪没有；量的单位新浪是股，腾讯科创板是股、其余是手（见 §1.2） |
| `push2/stock/get`（个股） | 腾讯 `qt.gtimg.cn` | 腾讯无行业/概念字段 |


## 备用源速查 & 降级策略（东财/主源被封时用）

**何时用：** 主源报错 403/连接重置（东财 IP 级风控）、返回空、或需权威一手数据交叉验证时。**东财系接口共用同一风控面，某台住宅 IP 被封会成片失联**——下表列出部分核心数据的备胎（不同域名、不同风控面；打板/期权/舆情/事件驱动/可转债暂无独立备胎）。既有备胎的验证记录为 2026-07-11；两融与北交所备胎在 2026-09-05 跑通真实数据；V3.9 的研报备胎与改过主源的 K 线行在 2026-09-20 实测。历史验证不代表今天全部接口仍然可用。

| 数据类型 | 主源(本 skill) | 独立备胎 | 备胎端点 / 说明 |
|---|---|---|---|
| 实时行情+五档 | 腾讯（mootdx 盘口 #52 失效） | 交易所官方 | 沪 `yunhq.sse.com.cn:32041/v1/sh1/snap/{code}`、深 `szse.cn/api/market/ssjjhq/getTimeData?marketId=1&code={code}`；北 `bse_quote_backup(date, code)` 是当前快照，盘中延迟未标定 |
| 融资融券 | 东财 datacenter | 上交所/深交所官方 | `margin_trading_backup(date, "SH"/"SZ", code=None)`，按交易所分别取；上交所融券余额金额可能为空 |
| K线(全历史) | 腾讯 §1.2 / 百度 | 同花顺 | `d.10jqka.com.cn/v6/line/hs_{code}/01/last.js`（01日/11周/21月/30/60分；2001至今；JSONP剥壳） |
| K线(当日全市场) | 通达信盘后包 §1.3 | 腾讯 §1.2 逐只取 | 盘后包实测 2022-01-04、2023-01-03 可取（2021-01-04 已 404），取不到的日期逐只走 §1.2 |
| K线(分钟) | 腾讯 §1.2（m1~m60，≤320根） | 同花顺 | 同上一行，只有 30 / 60 分钟；1 / 5 / 15 分钟在 mootdx 恢复前暂无独立备胎 |
| 逐笔成交 | 腾讯 §1.4（只有当日；mootdx 逐笔 #52 失效） | 暂无 | 新浪 `CN_Bill.GetBillList` 只返回大单，不是全部成交，不能当备胎 |
| 研报列表 | 东财 reportapi | 新浪 §2.4 | `sina_research_reports()`：只有标题/类型/机构/研究员/日期，无评级与目标价 |
| 龙虎榜 | 东财 datacenter | 沪深交易所官方 | `dragon_tiger_backup()`（见下，含营业部席位） |
| 个股资金流 | 东财 push2 | 新浪 | `fund_flow_backup()`（见下，日度四档单净额） |
| 公告 | 巨潮 | 深交所官方/东财 | `announcements_backup()`（见下，深市深交所+PDF，沪市东财+PDF） |
| 财务三表 | 新浪/mootdx | 同花顺 F10 | `basic.10jqka.com.cn/api/stock/finance/{code}_debt.json`（`_benefit`利润/`_cash`现金流；仅 UA，5连发不封） |
| 个股新闻 | 东财 search | 新浪7x24 | `zhibo.sina.com.cn/api/zhibo/feed?zhibo_id=152&page_size=20&dire=f`（`ext.stocks` 带个股关联可过滤） |
| 快讯 | 东财7x24(§5.3) | 财联社(§5.2) | 两条已互备；再加金十 `jin10.com/flash_newest.js` |
| 券商评级+目标价 | 同花顺一致预期 | 巨潮 webapi | `p_sysapi1089?tdate=YYYY-MM-DD`，需头 `Accept-Enckey`=base64(AES-128-CBC(unix秒, key=iv=`1234567887654321`)) |
| 北向(权威) | 同花顺 hexin | HKEX 官方 | `hkex.com.hk/chi/csm/DailyStat/data_tab_daily_{YYYYMMDD}c.js`（成交额/额度/十大活跃股） |

> ⛔ **已死透别用**（2026-07 实测）：网易财经(126.net 整站下线)、和讯、凤凰行情、腾讯资金流(ff_ 已死)、雪球免登录深度数据(需 token)。mootdx **库**已烂尾(2024 停更)；**2026-09 起通达信公开服务器的 K 线 / 盘口 / 逐笔命令返回空（#52）**，财务与 F10 照常——行情改走 §1.1–§1.4（腾讯实时 / 腾讯 K 线 / 盘后包 / 腾讯逐笔），财务用 `tdx_client(check='finance')`。
>
> ⚠️ **腾讯分钟 K 线字段坑**（§1.2 `tencent_kline()` 已按此解析，不返回成交额）：返回数组 `[时间, 开, 收, 高, 低, 量, {}, 换手率基点]`，量的单位科创板是股、其余是手（见 §1.2）——第 8 个字段（下标 7）**不是成交额，是换手率基点**（当日各根累加 ÷100 = 当日换手率%）。当成交额读会小三个数量级；成交额需自算 `成交数量 × 均价`（成交数量：科创板就是量（股）；可转债是量 × 10（张）；沪深主板、创业板、B 股、ETF、LOF、REITs 是量 × 100；指数不适用）。

```python
import json, urllib.request, ssl
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE

def dragon_tiger_backup(trade_date: str) -> dict:
    """龙虎榜官方备用源（东财被封时用）：上交所+深交所官方，零鉴权权威一手，含营业部席位。"""
    out = {"date": trade_date, "sse_raw": "", "szse": []}
    su = (f"https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON"
          f"&CATALOGID=1842_xxpl&TABKEY=tab1&txtStart={trade_date}&txtEnd={trade_date}&random=0.9")
    req = urllib.request.Request(su, headers={"User-Agent": UA,
          "Referer": "https://www.szse.cn/disclosure/supervision/dealinfo/index.html"})
    with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
        d = json.loads(r.read())
    for row in d[0].get("data", []):
        out["szse"].append({"code": row.get("zqdm"), "name": row.get("zqjc"),
                            "amount": row.get("cjje"), "reason": row.get("plyy")})
    eu = (f"https://query.sse.com.cn/infodisplay/showTradePublicFile.do?"
          f"jsonCallBack=cb&isPagination=false&dateTx={trade_date}")
    req = urllib.request.Request(eu, headers={"User-Agent": UA,
          "Referer": "https://www.sse.com.cn/disclosure/diclosure/public/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        t = r.read().decode("utf-8", "ignore")
    out["sse_raw"] = "\n".join(json.loads(t[t.index("(")+1:t.rindex(")")]).get("fileContents", []))
    return out

def fund_flow_backup(code: str, days: int = 60) -> list:
    """个股资金流备用源（东财被封时用）：新浪，日度四档单净额。"""
    # 92 先判：920xxx 是北交所，误判成 sh/sz 时新浪返回空数组（实测 bj920002 有数据、sh/sz 为 []）
    pre = ("bj" if code.startswith(("92", "8"))
           else "sh" if code.startswith(("6", "9")) else "sz") + code
    u = (f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
         f"MoneyFlow.ssl_qsfx_zjlrqs?page=1&num={days}&sort=opendate&asc=0&daima={pre}")
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        t = r.read().decode("utf-8", "ignore")
    arr = json.loads(t[t.index("["):t.rindex("]")+1])
    return [{"date": x.get("opendate"), "close": x.get("trade"),
             "net_amount": x.get("netamount"), "turnover": x.get("turnover")} for x in arr]

def announcements_backup(code: str, page_size: int = 20) -> list:
    """公告备用源（巨潮被封时用）：深市走深交所官方，沪市走东财，均带 PDF 直链。"""
    if code.startswith(("0", "3")):
        body = json.dumps({"channelCode": ["listedNotice_disc"], "pageSize": page_size,
                           "pageNum": 1, "stock": [code]}).encode()
        req = urllib.request.Request("https://www.szse.cn/api/disc/announcement/annList", data=body,
              headers={"User-Agent": UA, "Content-Type": "application/json",
                       "Referer": "https://www.szse.cn/disclosure/listed/notice/index.html"})
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            d = json.loads(r.read())
        return [{"title": a.get("title"), "time": a.get("publishTime", "")[:10],
                 "pdf": "https://disc.static.szse.cn/download" + a.get("attachPath", "")}
                for a in d.get("data", [])]
    u = (f"https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size={page_size}"
         f"&page_index=1&ann_type=A&client_source=web&stock_list={code}&f_node=0&s_node=0")
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return [{"title": a.get("title"), "time": a.get("notice_date", "")[:10],
             "pdf": f"https://pdf.dfcfw.com/pdf/H2_{a.get('art_code','')}_1.pdf"}
            for a in (d.get("data") or {}).get("list") or []]     # #46 同因

# 用法（主源失败时降级）
lhb = dragon_tiger_backup("2026-07-10")   # 深市结构化 + 沪市全文(含营业部)
flow = fund_flow_backup("600519", 60)     # 近60日资金流
anns = announcements_backup("000858")     # 深市走深交所, 沪市走东财
```

---
