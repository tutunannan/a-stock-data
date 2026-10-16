---
name: a-stock-data
description: 当任务需要写代码实际获取A股及相关市场数据时使用——行情/K线/逐笔（腾讯日周月前后复权+分钟线+当日逐笔、通达信官网盘后包）、研报（东财+新浪+同花顺+iwencai）、信号（热点/北向/龙虎榜/解禁/行业/板块资金流）、资金面（融资融券/大宗/股东户数/分红/资金流/ETF份额/筹码分布）、新闻（财联社/东财/华尔街见闻/新闻联播）、财务三表/F10/估值历史/ST名单、公告（巨潮）、打板（涨停池/连板/炸板率/监控池/异动）、ETF期权、舆情互动（互动易/上证e互动/热榜）、复权因子、申万行业变迁、宏观与利率（社融/PMI/中债收益率曲线/回购定盘利率/LPR/全球宏观日历）、指数成分/权重/估值/交易日历、期货与大宗商品（五家期货交易所日行情/商品与股指期权/持仓排名/期货日K/实时期货/A50/上海金）、事件驱动（业绩预告/机构调研/增减持/回购/股权质押/新股申购）、可转债等真实数据。87端点·34来源，内嵌全部可运行代码；优先腾讯/交易所官方等不封IP源，东财内置限流防封，主源被封可查备用源降级。A股概念解释、投资观点讨论等无需取数的话题不要加载本skill。
origin: custom
version: 3.10.2
---

> 📦 项目主页：https://github.com/simonlin1212/a-stock-data — 更新、反馈、支持作者
> 
> 作者：Simon 林 · X [@linsizhen](https://x.com/linsizhen) · 邮箱：simonlin0423@gmail.com

# A股全栈数据工具包 V3.10.2

十五层数据架构，87 个能力端点（82 主端点 + 5 备胎）、34 个来源。V3.10 新增的 2 个入口于 2026-09-22 实测，V3.9 新增的 25 个入口于 2026-09-20 实测；旧端点的验证日期见各章节。覆盖主板/创业板/科创板/ST，北交所覆盖依端点而异；已有备胎的数据可按「备用源速查」降级。

> 版本历史与历次实测记录见仓库 [CHANGELOG.md](https://github.com/simonlin1212/a-stock-data/blob/main/CHANGELOG.md)；本目录与仓库根部单文件 SKILL.md 内容同源（本目录为渐进披露拆分形态）。

## 使用方式与文件结构

将本目录整体放入 `~/.claude/skills/a-stock-data/`（含 `references/`），Claude Code 自动识别。

| 文件 | 内容 | 何时读 |
|---|---|---|
| `SKILL.md`（本文件） | 能力树、端点路由、数据源优先级与防封铁律 | 激活即载 |
| `references/common.md` | 依赖安装 + 全部共用 helper（`norm_ticker`/`em_get`/`V39_RETRY_SESSION`/`tdx_client`…） | 用任何东财端点或 V3.9.0+ 端点前 |
| `references/layer-01…15-*.md` | 十五个数据层，§ 编号与单文件版一致 | 按路由表选层后 |
| `references/backups.md` | 官方两融/北交所备胎、封禁案例、34 源详表、备用源速查 | 主源被封/降级/交叉验证时 |
| `references/valuation.md` | 估值公式 + 完整调研流程 | 做估值/深度调研时 |
| `references/faq.md` | FAQ + 安装说明 | 疑难时 |

```
行情层（实时，不封IP）
├── 腾讯财经 API   → PE/PB/市值/换手率/涨跌停/指数/ETF (HTTP)
├── 腾讯 K 线      → 沪深日/周/月前后复权 + 1~60 分钟，三入口轮换 (V3.9 新增)
├── 通达信盘后包   → 某交易日沪深北全市场日线含成交额 (tdx.com.cn HTTP，V3.9 新增)
├── 腾讯逐笔       → 最近一个交易日的分笔成交明细，沪深个股 + ETF (HTTP，V3.10 新增)
├── 百度股市通     → K线带MA5/10/20 (V3.0 新增，HTTP)
├── 新浪复权因子   → qfq/hfq 因子序列 + 套用到不复权K线 (V3.7 新增)
└── mootdx        → K线 + 五档盘口 + 逐笔成交 (TCP 7709；⚠️ 2026-09 起行情命令返回空，#52，留档)

研报层
├── 东财 reportapi → 个股研报 + 行业研报 + PDF下载 + 评级 + 三年EPS
├── 同花顺 THS     → 一致预期EPS (直连 basic.10jqka.com.cn)
├── iwencai        → NL语义搜索研报 (唯一能力，需X-Claw)
└── 新浪研报列表   → 标题/机构/研究员/日期，研报第二来源 (V3.9 新增)

信号层
├── 同花顺热点     → 当日强势股 + 题材归因 reason tags (零鉴权 73ms)
├── 同花顺北向     → hgt/sgt 分钟资金流向 + 本地自缓存历史
├── 东财 slist     → 个股所属板块/概念归属 (V3.2.2 替换百度PAE)
├── 东财 push2     → 个股资金流向 分钟级 (V3.1 替换百度PAE)
├── 龙虎榜席位     → 上榜记录 + 买卖席位 TOP5 + 机构动向 (datacenter-web)
├── 全市场龙虎榜   → 每日全市场上榜股票 + 净买额排名 (datacenter-web)
├── 限售解禁日历   → 历史解禁 + 未来90天待解禁 (datacenter-web)
├── 行业板块排名   → 东财行业涨跌/上涨下跌家数 (V3.0 替换同花顺)
└── 板块资金流向   → 行业/概念/地域 × 今日/5日/10日 主力+超大/大/中/小四档 (push2, V3.5)

资金面 / 筹码层
├── 融资融券明细   → 日级融资余额/买入/偿还 + 融券 (datacenter-web)
├── 大宗交易       → 成交价/量 + 买卖方营业部 (datacenter-web)
├── 股东户数变化   → 季度股东户数 + 环比变化 (datacenter-web)
├── 分红送转       → 历史每股派息/送股/转增 (datacenter-web)
├── 个股资金流120日 → 主力/大单/中单/小单 日级净流入 (push2his)
├── 筹码分布 CYQ   → 获利比例/平均成本/90-70成本区间/筹码峰 (本地计算，V3.7 新增)
└── ETF 份额       → 上交所按日归档 / 深交所当前快照，万份 (V3.9 新增)

新闻层
├── 东财个股新闻   → 个股相关新闻 (search-api-web JSONP)
├── 财联社快讯     → 全市场实时电报 (v1 API+本地签名零key，✅V3.4 复活)
├── 东财全球资讯   → 7×24 财经快讯 (np-weblist，与财联社互备)
├── 华尔街见闻     → 7×24 快讯，按频道 + 翻页游标 (V3.9 新增)
└── 新闻联播       → 当日条目标题 + 文字稿 (央视网，V3.9 新增)

基础数据层
├── mootdx finance → 季报快照 (37字段, EPS/ROE/净利)
├── mootdx F10     → 最新提示 (公告/报道/大宗/两融/风险提示摘要；2026-09 起只剩这一类)
├── 东财个股信息   → 行业/总股本/流通股/市值/上市日期 (push2)
├── 新浪财报三表   → 资产负债表/利润表/现金流量表 (quotes.sina.cn)
├── baostock 估值历史 → 日频 PE/PB/PS/PCF + 换手率 + 停牌 + ST (不支持北交所，V3.7 新增)
├── baostock 标的信息 → 上市日/退市日/状态 (V3.7 新增)
├── 申万行业分类   → 行业归属变迁史，消除前视偏差 (仅代码无中文名，V3.7 新增)
└── ST 名单        → 沪深京 ST / *ST 当日快照 (东财，baostock 兜底，V3.9 新增)

公告层
├── 巨潮 cninfo    → 公告全文检索+下载 (cninfo.com.cn)
└── mootdx F10     → 最新公告摘要

打板层 (V3.3 新增)
├── 东财涨停池     → 连板数/几天几板/封板资金/炸板次数/行业 (push2ex)
├── 东财炸板池     → 涨停后开板 + 振幅/涨速 (push2ex)
├── 东财跌停池     → 封单资金/连续跌停/开板次数 (push2ex)
├── 东财昨涨停池   → 昨涨停今表现，算晋级率/赚钱效应 (push2ex)
└── 同花顺涨停揭秘 → 涨停原因题材/封板成功率/板型 (10jqka)

ETF期权层 (V3.3 新增)
├── 合约清单       → 50ETF/300ETF/科创50/500ETF 各月认购认沽 (新浪)
├── T型报价        → 买卖五档/持仓量/行权价/最新价 (新浪)
└── 希腊字母+IV    → Delta/Gamma/Theta/Vega/隐含波动率 (新浪)

舆情互动层 (V3.3 新增)
├── 互动易问答     → 投资者提问+公司回复 (巨潮，深市)
├── 上证e互动      → 沪市投资者提问+公司回复 (上交所运营的独立平台，V3.9 新增)
├── 同花顺热榜     → 人气值/概念标签/排名变化 (10jqka)
├── 东财人气榜     → 排名+排名变化+名称价格 (emappdata)
└── 东财概念命中   → 个股被归到哪些概念在炒+热度 (emappdata)

宏观与利率层 (V3.7 新增，V3.9 扩展)
├── 人民银行社融   → 社会融资规模增量 月度12列 (pbc.gov.cn，三级跳取 xls 附件)
├── 国家统计局PMI  → 制造业/非制造业/综合 + 大中小型企业分档 (stats.gov.cn)
├── 中债收益率曲线 → 国债 / 商业银行 AAA / 中短票 AAA，3月~30年 (V3.9 新增)
├── 回购定盘利率   → FR001/007/014 + FDR (中国货币网，V3.9 新增)
├── LPR            → 1 年 / 5 年全历史 (东财，V3.9 新增)
└── 全球宏观日历   → 公布值/预期/前值 + 重要事件 (华尔街见闻，V3.9 新增)

指数与交易日历层 (V3.8 新增)
├── 中证指数       → 当前成分 / 月末权重 / 近期 PE 与股息率
├── 国证指数       → 最近公布的成分与权重（月末快照）
└── 深交所日历     → 官方整月交易标志（完整性校验）

期货与大宗商品层 (V3.9 新增，#49)
├── 期货日行情     → 上期所/上期能源/郑商所/中金所/广期所 官方收盘数据
├── 期权日行情     → 商品期权 + 股指期权，Delta / 隐含波动率（中金所不公布这两项）
├── 持仓排名       → 会员成交量 / 持买 / 持卖前 20 名
├── 实时期货       → 新浪实时价（含大商所品种）
├── 期货日 K       → 新浪单合约 / 主力连续逐日 K 线（含大商所，V3.10 新增）
├── A50 期指       → 富时中国 A50 连续合约报价
└── 上海金现货     → 上金所 Au99.99 / Au(T+D) / Ag(T+D) 日线

事件驱动层 (V3.9 新增)
├── 业绩预告 · 机构调研 · 股东增减持 · 股票回购
└── 股权质押（中国结算周度） · 新股申购日历   (均为东财 datacenter)

可转债层 (V3.9 新增)
└── 可转债全表     → 条款 + 转股价 / 债价 / 转股价值 / 溢价率 (东财)

官方备胎扩展 (V3.8 新增)
├── 上交所/深交所  → 两融明细（分交易所调用，金额元、余量股/份）
└── 北交所         → 当前行情与五档快照（必须核对交易日）
```

## 端点路由速查（按需定位，不必通读全文）

只需一类数据时，按下表定位章节（§）局部读取。除 iwencai 需 API Key 外全部零 key。

| § | 函数 | 拿什么 | 源 / 文件 |
|---|------|--------|----|------|
| 前置 | `norm_ticker(code)` | 任意写法→纯6位（`SH600519`/`600519.SH`/`600519.XSHG` 皆可；解析失败抛错不返空） | 本地 | common.md |
| 前置 | `to_joinquant(code)` | 转聚宽代码 `600519.XSHG` / `000001.XSHE`（北交所不转换） | 本地 | common.md |
| 1.1 | `tencent_quote(codes)` | 实时价/PE/PB/市值/换手/涨跌停/指数/ETF（带 `is_stale` 僵尸报价标志） | 腾讯 | layer-01-quotes.md |
| 1.2 | `tencent_kline(code, period, adjust, start, end, count)` | 日/周/月前后复权 + 1~60 分钟 K 线（沪深，不含北交所） | 腾讯 | layer-01-quotes.md |
| 1.3 | `tdx_daily_package(date)` | 某交易日沪深北全部证券日线（含成交额） | 通达信官网 | layer-01-quotes.md |
| 1.4 | `tencent_ticks(code)` | 最近一个交易日的分笔成交（价/手/元/主动买卖；沪深个股+ETF，不含北交所） | 腾讯 | layer-01-quotes.md |
| 1.5 | `baidu_kline_with_ma(code)` | 日K线带 MA5/10/20 | 百度 | layer-01-quotes.md |
| 1.6 | `sina_adjust_factor(code, kind)` / `apply_adjust(bars, factors)` | 复权因子 qfq/hfq + 套用到不复权K线 | 新浪 | layer-01-quotes.md |
| 1.7 | `tdx_client()` → `.bars()` / `.quotes()` / `.transaction()` | K线(多周期,不复权) / 五档盘口 / 逐笔成交（⚠️ 2026-09 起返回空，#52，留档） | 通达信 | layer-01-quotes.md |
| 2.1 | `eastmoney_reports(code)` / `download_pdf(rec)` | 个股研报+评级+三年EPS / 研报PDF | 东财 | layer-02-reports.md |
| 2.1 | `eastmoney_industry_reports(industry_code)` | 行业研报 | 东财 | layer-02-reports.md |
| 2.2 | `ths_eps_forecast(code)` | 机构一致预期 EPS | 同花顺 | layer-02-reports.md |
| 2.3 | `iwencai_search(query)` / `iwencai_query(query)` | NL 语义搜研报/选股（需 Key） | iwencai | layer-02-reports.md |
| 2.4 | `sina_research_reports(code=None, page=1)` | 研报列表：标题/类型/机构/研究员（无评级） | 新浪 | layer-02-reports.md |
| 3.1 | `ths_hot_reason()` | 当日强势股+题材归因 | 同花顺 | layer-03-signals.md |
| 3.2 | `hsgt_realtime()` | 北向分钟流向（hgt 可用 / sgt 仅参考） | 同花顺 | layer-03-signals.md |
| 3.3 | `eastmoney_concept_blocks(code)` | 个股所属板块/概念归属 | 东财 | layer-03-signals.md |
| 3.4 | `eastmoney_fund_flow_minute(code)` | 个股资金流（分钟级） | 东财 | layer-03-signals.md |
| 3.5 | `dragon_tiger_board(code, date)` | 个股龙虎榜+买卖席位 TOP5 | 东财 | layer-03-signals.md |
| 3.6 | `lockup_expiry(code, date)` | 解禁历史+未来90天待解禁 | 东财 | layer-03-signals.md |
| 3.7 | `industry_comparison()` | 行业板块涨跌排名 | 东财 | layer-03-signals.md |
| 3.8 | `board_fund_flow(board_type, period)` | 板块资金流向（行业/概念/地域 × 今日/5日/10日，主力+四档） | 东财 | layer-03-signals.md |
| 3.9 | `daily_dragon_tiger(date)` | 全市场龙虎榜+净买额排名 | 东财 | layer-03-signals.md |
| 4.1 | `margin_trading(code)` | 融资融券明细 | 东财 | layer-04-funds-chips.md |
| 4.2 | `block_trade(code)` | 大宗交易+营业部 | 东财 | layer-04-funds-chips.md |
| 4.3 | `holder_num_change(code)` | 股东户数变化 | 东财 | layer-04-funds-chips.md |
| 4.4 | `dividend_history(code)` | 分红送转历史 | 东财 | layer-04-funds-chips.md |
| 4.5 | `stock_fund_flow_120d(code)` | 个股资金流（120日，日级） | 东财 | layer-04-funds-chips.md |
| 4.6 | `chip_distribution(df)` | 筹码分布（获利比例/平均成本/90-70成本区间/筹码峰） | 本地计算 | layer-04-funds-chips.md |
| 4.7 | `etf_shares(date, exchange)` | ETF 份额（万份）：上交所历史日期 / 深交所当前快照 | 上交所/深交所 | layer-04-funds-chips.md |
| 5.1 | `eastmoney_stock_news(code)` | 个股新闻 | 东财 | layer-05-news.md |
| 5.2 | `cls_telegraph()` | 财联社电报（7×24，本地签名零key） | 财联社 | layer-05-news.md |
| 5.3 | `eastmoney_global_news()` | 全球资讯（7×24） | 东财 | layer-05-news.md |
| 5.4 | `wallstreetcn_lives(channel, limit, cursor)` | 7×24 快讯（按频道，可翻页） | 华尔街见闻 | layer-05-news.md |
| 5.5 | `cctv_news(date, with_content=True)` | 新闻联播条目 + 文字稿（政策信号研究用） | 央视网 | layer-05-news.md |
| 6.1 | `tdx_client(check='finance').finance(symbol)` | 季报快照 37 字段 | 通达信 | layer-06-basics.md |
| 6.2 | `tdx_client(check='finance').F10(symbol, name)` | F10 文本（2026-09 起服务端只剩「最新提示」一类） | 通达信 | layer-06-basics.md |
| 6.3 | `eastmoney_stock_info(code)` | 行业/股本/市值/上市日期 | 东财 | layer-06-basics.md |
| 6.4 | `sina_financial_report(code, type)` | 财报三表 | 新浪 | layer-06-basics.md |
| 6.5 | `baostock_valuation_history(code, s, e)` | 估值历史 PE/PB/PS/PCF + 换手率 + 停牌 + ST（**不支持北交所**） | baostock | layer-06-basics.md |
| 6.6 | `baostock_stock_basic(code)` | 上市日 / **退市日** / 状态 | baostock | layer-06-basics.md |
| 6.7 | `sw_industry_history()` / `sw_industry_as_of(df, code, d)` | 申万行业**变迁史**（消除前视偏差，仅代码无中文名） | 申万 | layer-06-basics.md |
| 6.8 | `st_stock_list()` | 沪深京 ST / *ST 当日名单 | 东财（baostock 兜底） | layer-06-basics.md |
| 7.1 | `cninfo_announcements(code)` | 公告检索+PDF 下载 | 巨潮 | layer-07-announcements.md |
| 7.2 | `tdx_client(check='finance').F10(symbol, name='最新提示')` | 最新公告摘要 | 通达信 | layer-07-announcements.md |
| 8.1 | `em_zt_pool` / `em_zb_pool` / `em_dt_pool` / `em_yzt_pool` | 涨停/炸板/跌停/昨涨停四池 | 东财 | layer-08-limit-up.md |
| 8.2 | `ths_limit_up_pool(date)` | 涨停原因题材+封板成功率+板型 | 同花顺 | layer-08-limit-up.md |
| 8.3 | `limit_up_sentiment(date)` | 炸板率/连板高度/连板梯队 | 东财(四池组合) | layer-08-limit-up.md |
| 8.4 | `em_stock_monitor()` | 重点监控池（风险警示名单+生效时间窗） | 东财 | layer-08-limit-up.md |
| 8.5 | `em_price_anomaly()` / `em_price_anomaly_count()` | 日内异动明细 / 按标的聚合异动统计（严重异常波动） | 东财 | layer-08-limit-up.md |
| 9.1 | `sina_option_codes` / `sina_option_tquote` / `sina_option_greeks` | ETF期权合约清单 / T型报价 / 希腊字母+IV | 新浪 | layer-09-options.md |
| 10.1 | `cninfo_irm(code)` | 互动易问答（提问+公司回复，深市） | 巨潮 | layer-10-sentiment.md |
| 10.2 | `ths_hot_list()` / `em_hot_rank()` / `em_hot_concept(code)` | 热榜/人气榜/概念命中 | 同花顺+东财 | layer-10-sentiment.md |
| 10.3 | `sse_e_interaction(code=None, kind='answered')` | 上证e互动问答（沪市） | 上证e互动（上交所运营） | layer-10-sentiment.md |
| 11.1 | `pboc_social_financing(year)` | 社会融资规模增量（月度12列） | 人民银行 | layer-11-macro.md |
| 11.2 | `nbs_pmi()` | 制造业/非制造业/综合 PMI + 大中小型企业 | 国家统计局 | layer-11-macro.md |
| 11.3 | `chinabond_yield_curve(start, end, curve)` | 国债 / 银行 AAA / 中短票 AAA 收益率曲线 3月~30年 | 中债 | layer-11-macro.md |
| 11.4 | `repo_fixing_rates(kind)` | 回购定盘利率 FR / FDR 001·007·014 | 中国货币网 | layer-11-macro.md |
| 11.5 | `lpr_history()` | LPR 1 年 / 5 年全历史 | 东财 | layer-11-macro.md |
| 11.6 | `macro_calendar(start, end, country, min_importance)` | 全球宏观日历（公布值/预期/前值） | 华尔街见闻 | layer-11-macro.md |
| 12.1 | `index_constituents(index_code, provider)` | 最近公布的沪深北指数成分；csi/cni 显式选源 | 中证/国证 | layer-12-index.md |
| 12.2 | `index_weights(index_code, provider)` | 最近公布的指数权重（百分数），保留真实日期 | 中证/国证 | layer-12-index.md |
| 12.3 | `index_valuation(index_code)` | 两种口径 PE、股息率；不含 PB | 中证 | layer-12-index.md |
| 12.4 | `trading_calendar(year, month)` | 官方整月交易日历 | 深交所 | layer-12-index.md |
| 13.1 | `futures_daily(date, exchange)` | 期货日行情（SHFE/INE/CZCE/CFFEX/GFEX） | 五家期货交易所 | layer-13-futures.md |
| 13.2 | `options_daily(date, exchange)` | 商品期权 / 股指期权日行情 + Delta / IV（中金所不公布这两项） | 五家期货交易所 | layer-13-futures.md |
| 13.3 | `futures_position_rank(date, exchange, symbol)` | 会员成交 / 持买 / 持卖前 20 名 | 上期所/能源/郑商所/中金所 | layer-13-futures.md |
| 13.4 | `futures_realtime(symbols)` | 实时期货（含大商所品种） | 新浪 | layer-13-futures.md |
| 13.5 | `a50_futures()` | 富时中国 A50 期指 | 新浪 | layer-13-futures.md |
| 13.6 | `sge_spot(instrument)` | 上海金交所现货日线（黄金/白银/铂金） | 上金所 | layer-13-futures.md |
| 13.7 | `futures_kline(symbol, start, end)` | 期货日 K：单个合约 / 主力连续的逐日序列（含大商所） | 新浪 | layer-13-futures.md |
| 14.1 | `earnings_forecast(code, report_date, limit)` | 业绩预告 | 东财 | layer-14-events.md |
| 14.2 | `institution_survey(code, start, end, detail, limit)` | 机构调研（汇总 / 逐机构） | 东财 | layer-14-events.md |
| 14.3 | `holder_trades(code, direction, start, end, limit)` | 股东增减持 | 东财 | layer-14-events.md |
| 14.4 | `share_buyback(code, progress, limit)` | 股票回购方案与进度 | 东财 | layer-14-events.md |
| 14.5 | `equity_pledge(code, date, limit)` | 股权质押比例（中国结算周度，仅沪深） | 东财 | layer-14-events.md |
| 14.6 | `ipo_calendar(limit)` | 新股申购日历 | 东财 | layer-14-events.md |
| 15.1 | `convertible_bonds(include_delisted=False)` | 可转债条款 + 转股价值 / 溢价率 | 东财 | layer-15-convertible.md |
| 官方备胎扩展 | `margin_trading_backup(date, exchange, code=None)` | 单所两融明细（先执行 §12 helper） | 上交所/深交所 | backups.md |
| 官方备胎扩展 | `bse_quote_backup(date, code=None)` | 北交所全板/单票当前快照（先执行 §12 helper） | 北交所 | backups.md |
| 备用源速查 | `dragon_tiger_backup` / `fund_flow_backup` / `announcements_backup` | 龙虎榜/资金流/公告官方备胎（主源被封时降级） | 交易所官方+新浪+东财(沪市公告) | backups.md |
| 估值公式 | `forward_pe` / `pe_digestion` / `calc_peg` / `full_valuation(code)` | 前向PE / PE消化时间 / PEG / 单票估值全景 | 本地计算 | valuation.md |


## 数据源优先级 & 东财防封（重要，先读）

### 优先级原则：能用腾讯 / 交易所官方，就别用东财

| 优先级 | 数据源 | 协议 | 封 IP 风险 | 覆盖 |
|--------|--------|------|-----------|------|
| **1（首选）** | **腾讯财经** | HTTP | **不封 IP**（K 线单入口约 600 次后限流，§1.2 三入口轮换） | 实时价、PE/PB/市值/换手率/涨跌停、指数、ETF、日周月/分钟 K 线、当日逐笔 |
| **2** | **交易所 / 官方机构** | HTTP | 极低（避免高频） | 通达信盘后包、沪深北交易所、五家期货交易所、上金所、中债、货币网、中证/国证 |
| **3** | 新浪 / 巨潮 / 同花顺 / 华尔街见闻 | HTTP | 低 | 财报三表、复权因子、公告、一致预期/热点、研报列表、快讯 |
| **4** | **mootdx（通达信）** | TCP 7709 二进制 | 不封 IP | 财务快照、F10 正常；**K 线 / 盘口 / 逐笔 2026-09 起返回空（#52）** |
| **5（仅独有数据才用）** | **东财 eastmoney** | HTTP | **有风控，会封 IP** | 见下 |

**凡是行情 / K线 / 实时价 / 市值 / 财务三表能从腾讯、交易所官方或新浪拿到的，一律走它们**——实测不封 IP，可放心使用（仍应控制频率）。

### 东财只用于它「独有、别处拿不到」的数据

下列能力默认走东财（须限流）；已有交易所备胎的龙虎榜、两融可按文末速查表切换，不应视为东财独占：

> 龙虎榜席位 · 全市场龙虎榜 · 限售解禁日历 · 融资融券 · 大宗交易 · 股东户数 · 分红送转 · 个股资金流向（分钟/日级）· 行业板块排名 · 研报列表/PDF · 个股新闻 · 全球资讯 · ST 名单 · LPR · 事件驱动（业绩预告/机构调研/增减持/回购/质押/新股）· 可转债

### 东财风控阈值（社区实测，2026-05）

| 行为 | 触发封禁的阈值 | 风险 |
|------|---------------|------|
| 每秒请求数 | > 5 次/秒 | 高 |
| 单 IP 并发连接 | ≥ 10 | 高 |
| 1 分钟请求总数 | ≥ 200 次 | 中高 |
| 5 分钟请求总数 | ≥ 300 次 | 触发封禁 |
| User-Agent | 空 UA / 无浏览器特征 | 中 |

被封表现：连续请求后 `403` / `429` / 连接超时 / 返回空数据。临时封禁通常几分钟到几小时。

### 防封铁律（调用东财时必须遵守）

1. **串行，不并发**——绝不对东财开多线程/协程并发请求
2. **每次间隔 ≥ 1 秒 + 随机抖动**（QPS ≤ 2），批量筛选时调大到 1.5~2 秒
3. **复用 HTTP 会话**（Keep-Alive），不要每次新建连接
4. **带正常 UA + Referer**（本 SKILL 各端点已配好）
5. **批量场景每只股票之间 sleep**——AI 跑批量循环（如筛选 100 只股逐个拉龙虎榜/资金流）是被封的头号元凶


> ⚠️ 实测有 **IP 级 20+ 小时封禁**的真实案例（10 线程并发、1 小时 45000+ 请求、不走 `em_get()`），完整记录与东财各端点的降级路径见 `references/backups.md`。

### 已内置限流：所有东财请求走 `em_get()`

本 SKILL 提供统一的节流入口 `em_get()`（定义见下方「东财数据中心统一查询（共用 helper）」），它自动做到：串行限流（最小间隔 `EM_MIN_INTERVAL=1.0s` + 随机抖动）+ 复用 `EM_SESSION`（Keep-Alive）+ 默认 UA。**所有 `eastmoney.com` 端点的代码块都已改用 `em_get` 而非裸 `requests.get`**，AI 直接抄代码即自带防封。批量任务把 `EM_MIN_INTERVAL` 调大即可进一步降速。

> 注：`em_get` / `EM_SESSION` / `EM_MIN_INTERVAL` 是所有东财代码块共用的前置定义，使用任一东财端点前需先执行「共用 helper」代码块（`references/common.md`）。

---

## When to Activate

- 用户需要**指数成分、指数权重、指数 PE / 股息率、官方交易日历、沪深官方两融或北交所行情备份**（V3.8）。
- 用户要看**商品期货 / 期权 / 持仓排名 / A50 / 黄金现货**，或**业绩预告 / 机构调研 / 增减持 / 回购 / 股权质押 / 新股申购 / 可转债**，
  或**国债收益率曲线 / 回购利率 / LPR / 全球宏观日历**、**ETF 份额**、**ST 名单**、**新闻联播**、**沪市互动问答**、**全市场当日日线**（V3.9）。
- 用户要把代码转成**聚宽格式**（`600519.XSHG`）或问**能否回测**（V3.9，见 FAQ）。

- 用户要查 A 股个股估值（一致预期 / PE / PEG / PE消化）
- 用户要拉实时行情（价格 / 五档盘口 / K线 / 涨跌停价）
- 用户要搜研报（按主题 / 按标的 / 按行业 / 下载PDF）
- 用户要看**当日强势股 / 题材归因 / 概念热点**
- 用户要看**北向资金动向**（沪股通/深股通分钟流向）
- 用户要看**概念板块归属**（行业/概念/地域）
- 用户要看**个股资金流向**（主力/散户/超大单/大单分钟级）
- 用户要看**龙虎榜席位**（营业部 + 机构买卖）
- 用户要看**全市场龙虎榜**（当日所有上榜股票 + 净买额排名）
- 用户要看**限售解禁日历**（历史解禁 + 未来待解禁）
- 用户要做**行业横向对比**（涨跌排名 / 资金流入 / 领涨股）
- 用户要看**融资融券 / 两融数据**（融资余额 + 融券余额）
- 用户要看**大宗交易**（成交价/量 + 买卖方营业部）
- 用户要看**股东户数变化**（筹码集中度）
- 用户要看**分红送转历史**（每股派息 + 送股 + 转增）
- 用户要看**指数/ETF行情**（上证指数 / 沪深300 / 创业板指 / ETF）
- 用户要看**涨停 / 打板情绪**（涨停池 / 连板梯队 / 炸板率 / 跌停 / 涨停原因题材）
- 用户要看**ETF 期权**（T型报价 / 希腊字母 Delta·Gamma·Theta·Vega / 隐含波动率 IV）
- 用户要看**投资者互动问答**（公司如何回应某传闻/利好 · 互动易）
- 用户要看**市场热度 / 人气榜**（同花顺热榜 / 东财人气榜 / 个股概念命中）
- 用户要看新闻资讯（个股新闻 / 财联社快讯 / 全球资讯）
- 用户要查公告（巨潮公告全文）
- 用户要做产业链调研 / 批量横向对比
- 关键词：估值、一致预期、机构预测、市盈率、PEG、市值、研报、产业链、行业研究、K线、盘口、公告、新闻、**强势股、题材、热点、概念归因、北向资金、沪股通、深股通、概念板块、资金流向、主力、龙虎榜、席位、营业部、全市场龙虎榜、净买入、解禁、限售、行业对比、行业轮动、融资融券、两融、大宗交易、股东户数、筹码集中、分红、派息、送股、指数、ETF、涨停、打板、连板、炸板、跌停、涨停原因、封板、晋级率、ETF期权、希腊字母、隐含波动率、互动易、投资者关系、热榜、人气榜、市场热度、期货、商品期权、股指期权、持仓排名、A50、黄金、上海金、业绩预告、机构调研、增减持、回购、股权质押、新股申购、打新、可转债、转股溢价率、国债收益率、收益率曲线、回购利率、FR007、LPR、宏观日历、ETF份额、ST、新闻联播、上证e互动、聚宽、回测**

