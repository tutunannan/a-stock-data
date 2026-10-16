> 本文件 = 单文件版 SKILL.md 的 FAQ + 安装说明章节。

## FAQ

### Q: 东财接口 403 / 连接重置，是被封了吗，怎么办？
A: 东财系接口（datacenter/push2/push2ex/reportapi/search/np-weblist）共用同一套风控，IP 被封会成片失联。三步处理：① 停止请求等 30-60 分钟（IP 级临时封通常自动解除），或换网络（手机热点）立刻恢复；② 长批任务确认全部走 `em_get()`，并调大 `EM_MIN_INTERVAL`；③ 数据不能等 → 用上方「备用源速查 & 降级策略」的独立备胎（交易所官方/新浪/同花顺，不同风控面，东财被封时不受牵连）。

### Q: 财联社快讯不是 V3.2 标注下线了吗？
A: 已复活（V3.4.0，见 §5.2）。2026-05 死的是旧 `nodeapi` 系接口；官方新版 `v1/roll/get_roll_list` 一直可用，只是强制 `sign` 校验——而 sign 纯本地可算（`md5(sha1(按 key 字典序拼接的 query 串))`），零 key。与 §5.3 东财 7×24 互为独立备份。

### Q: mootdx 取不到 K 线 / `tdx_client()` 报「所有 mootdx 服务器均无法取到数据」（#52）
A: 2026-09-20 逐台实测内置 10 台服务器，TCP 都能连上，财务、除权除息正常，F10 只剩「最新提示」一类，但 K 线、五档盘口、逐笔成交都返回 0 行。这是服务器端的变化，换 mootdx 版本解决不了。替代方案：
- 沪深日 / 周 / 月 K 线（前后复权）和 1~60 分钟 K 线 → §1.2 `tencent_kline()`
- 某交易日沪深北全市场日线（含成交额；北交所日线只能走这里）→ §1.3 `tdx_daily_package()`
- 实时价与五档 → §1.1 腾讯，或「备用源速查」里的交易所官方五档
- 当日逐笔成交 → §1.4 `tencent_ticks()`（只有最近一个交易日，不含北交所）
- 财务快照 / F10 → `tdx_client(check='finance')`，照常可用

`tdx_client()` 在 K 线模式下要先测速，全部失败大约需要 1 分钟才报错。

### Q: mootdx 库听说停更了，还能用吗？
A: 库确实烂尾（最后 commit 2024-07，官网下线，BESTIP bug 无官方修复）。本 skill 的 `tdx_client()` 已内置 IP 探测绕开 BESTIP bug；目前只用它取财务与 F10（见上一条）。

### Q: mootdx 和腾讯有什么区别？
A: 以前互补：mootdx 管价格 / 盘口 / K 线，腾讯管估值（PE/PB/市值/换手率/涨跌停价）。#52 之后价格与 K 线都走腾讯，mootdx 只剩财务快照和 F10。两者都不封 IP。

### Q: 能直接回测吗？能接聚宽吗？（#55）
A: 本 skill 只负责取数，**不带回测引擎**。回测要把数据交给自己的框架或聚宽。
- 代码格式：`norm_ticker()` / `get_prefix()` 认聚宽写法 `600519.XSHG` / `000001.XSHE`；`to_joinquant()` 把任意写法转成聚宽代码。聚宽公开文档没有北交所后缀，北交所代码会直接报错，不做转换。
- 复权：聚宽 `get_price` 默认前复权（`fq='pre'`）。对拍时用 §1.2 `tencent_kline(adjust='qfq')`，或用 §1.6 复权因子自己换算。
- 防未来函数：历史估值用 §6.5，历史行业归属用 §6.7，历史指数成分要注意 §12 只给当前快照。

### Q: 研报只能从东财拿吗？（#53）
A: 不是。§2.4 `sina_research_reports()` 是第二来源，可按个股或全市场翻页，东财被封时也能用。它只有标题、类型、机构、研究员和日期，没有评级和目标价。评级与目标价仍用 §2.1 东财或 §2.2 同花顺一致预期。

### Q: 有商品期货和期权吗？大商所呢？（#49）
A: 有，见 Layer 13。§13.1 / §13.2 取上期所、上期能源、郑商所、中金所、广期所官方的期货日行情和期权日行情，§13.3 取前四家的会员持仓排名（广期所未接）；§13.4 取新浪实时价，§13.5 取 A50 期指，§13.6 取上金所现货。**大商所官网有反爬，日行情没接**；大商所品种（豆粕、铁矿石等）的实时价可用 §13.4。

### Q: 沪市公司的互动易问答为什么是空的？
A: 巨潮互动易只覆盖深市公司，沪市公司实测返回 0 条。沪市请用 §10.3 `sse_e_interaction()`（上证e互动）。部分公司近一个月确实没有回复，返回空表属正常。

### Q: V3.0 为什么移除 akshare？
A: akshare 本质是对东财/同花顺/新浪等公开 API 的封装，中间层增加了故障点（版本兼容 bug、pandas 3.0 ArrowInvalid 等）。V3.0 直连底层 HTTP API，零中间依赖，更稳定可控。

### Q: iwencai 返回 401
A: 检查两点：(1) API Key 是否有效 (2) 是否携带了 X-Claw-* Headers。SkillHub 2.0 后必须带 X-Claw Headers，否则一律 401。

### Q: 同花顺一致预期 ths_eps_forecast 返回空
A: 该股票无机构覆盖。小盘/次新/ST 股常见。可 fallback 到东财 reportapi 里的 predictThisYearEps 字段。

### Q: 东财 PDF 下载 403
A: 必须带 `Referer: https://data.eastmoney.com/` header。

### Q: 腾讯 API 返回乱码
A: 编码是 GBK，必须 `decode("gbk")`。

### Q: 腾讯 API 字段 43 是 PB 吗？
A: **不是！** 43=振幅%，46=PB。网上很多教程写错了，这里是实测校准结果。

### Q: iwencai search 返回条数太少
A: `size` 参数默认 10，调到 50。隐藏参数，文档未写明但实测可用。

### Q: 哪些数据源需要 API Key？
A: 只有 iwencai 需要。其余 33 个来源（腾讯 / 东财 / 同花顺 / 新浪 / 巨潮 / 财联社 / 交易所与期货交易所 / 中债 / 货币网等）全部免费无 key。

### Q: 同花顺热点接口需要 cookie 吗？
A: **不需要**。仅 User-Agent 即可，零鉴权 73ms 拿到 ~125 只当日强势股。但**不要去打 search.10jqka.com.cn 的 iwencai NL 选股接口** —— 那个有 hexin-v cookie JS 签名鉴权，跟热点接口完全两码事。

### Q: 百度股市通 ResultCode 有时是 0 有时是 "0"？
A: 已知坑。`ResultCode` 返回类型不稳定——有时 int，有时 string。代码里必须用 `str(d.get("ResultCode", -1)) != "0"` 统一比较。

### Q: 北向资金历史数据为什么只有最近几天？
A: 本地自缓存模式。eastmoney 全系北向数据自 2024-08 起断供（净买额字段返回 NaN/0）。每次调用实时 API 后自动写入本地 CSV，历史越跑越丰富。

### Q: 行业板块为什么从同花顺换成东财？
A: 同花顺 `stock_board_industry_summary_ths` 接口 2026 年初加了反爬 401（需要登录态）。东财 push2 行业板块数据（`m:90+t:2`）是完美替代，零鉴权且字段更丰富。

### Q: 在海外服务器跑，mootdx 接口超时？
A: mootdx 走 TCP 直连通达信行情服务器，需国内 IP 才稳定。海外环境建议走代理。腾讯财经和百度股市通不受影响。

### Q: 不用 Claude Code，能用吗？
A: 能。SKILL.md 本质是 Markdown + 内嵌 Python 代码。Codex、OpenClaw 或任何 AI 编程助手都能读取。你也可以直接把 Python 代码段复制出来在自己的脚本里跑。

---

> 下面的安装说明针对**单文件版**（仓库根部 SKILL.md）；本目录形态的安装见主 SKILL.md「使用方式」。

## 安装说明

```bash
# 1. 创建 skill 目录
mkdir -p ~/.claude/skills/a-stock-data

# 2. 将本文件复制为 SKILL.md
cp SKILL.md ~/.claude/skills/a-stock-data/SKILL.md

# 3. 安装 Python 依赖
pip install mootdx requests pandas stockstats numpy baostock xlrd openpyxl

# 4. (可选) 配置 iwencai API Key
export IWENCAI_API_KEY="your_key_here"

# 5. 启动 Claude Code，说"查一下688017的估值"即可自动激活
```

---

