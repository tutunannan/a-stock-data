> 本文件 = 单文件版 SKILL.md 的 Prerequisites 章节：依赖安装 + 全部共用 helper（`tdx_client` / `get_prefix` / `norm_ticker` / `to_joinquant` / `em_get` / `V39_RETRY_SESSION` 等）。
> 执行任何东财端点或 V3.9.0+ 新端点前，先执行本文件的对应代码块。

## Prerequisites

```bash
pip install mootdx requests pandas stockstats numpy baostock xlrd openpyxl
```

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| mootdx | >= 0.10 | TCP 财务快照+F10（非 HTTP 依赖之一；K 线/盘口/逐笔 2026-09 起返回空，#52）；0.11.x 用 `tdx_client()` 规避 BESTIP bug，见下节 |
| requests | any | 所有HTTP API直连 |
| pandas | any | 数据处理+HTML表格解析 |
| stockstats | any | 技术指标计算（RSI/MACD/BOLL等） |
| numpy | any | §4.6 筹码分布的网格计算 |
| baostock | >= 0.8 | §6.5/§6.6 估值历史·换手率·停牌·ST·退市日，§6.8 ST 名单兜底（TCP，免注册免 key；**不支持北交所**） |
| xlrd | >= 2.0 | 读 `.xls`（§6.7 申万行业分类、§12 中证） |
| openpyxl | any | 读 `.xlsx`（§11.1 社融、§12 国证、深交所两融） |

> **架构：** 除 mootdx 与 baostock（均为 TCP 客户端库）外，所有数据源均为直连 HTTP API，不经第三方数据封装。每个 HTTP 端点的底层 URL/参数完全暴露，方便调试和定制。

### iwencai API Key（仅语义搜索需要）

```bash
# 环境变量方式
export IWENCAI_API_KEY="your_key_here"
export IWENCAI_BASE_URL="https://openapi.iwencai.com"

# 申请地址: https://www.iwencai.com/skillhub
# 注册后安装 SkillHub CLI，再安装 report-search 技能即可获得 Key
```

其他数据源（腾讯 / 东财 / 同花顺 / 百度股市通 / 新浪 / 巨潮 / 财联社 / mootdx / baostock / 申万 / 人民银行 / 国家统计局 / 沪深北交易所 / 中证 / 国证 / 通达信官网 / 华尔街见闻 / 央视网 / 中债 / 中国货币网 / 五家期货交易所 / 上金所）全部免费，无需 key。

### mootdx 客户端（必读，规避 0.11.x BESTIP 空串 bug）

> **已知 bug（mootdx 0.11.x）：** 全新安装后 `Quotes.factory(market='std')` 裸调用可能抛 `ValueError: not enough values to unpack (expected 2, got 0)`。
> 根因：`~/.mootdx/config.json` 的 `BESTIP.HQ` 初始是空字符串 `""`（不是缺失键），mootdx 用 `dict.get(key, default)` 取不到 default，拆包失败。**老用户（config 曾填充过 IP）不会触发，所以容易漏测。**
> **不要靠锁版本解决：** 锁 `mootdx==0.10.12` 在部分环境（如干净的 Python 3.9）下 `import mootdx` 会因 numpy/pandas 二进制不兼容直接崩。正确做法是用下面的 `tdx_client()`——显式传 server 绕过 BESTIP，对 0.10 / 0.11 都适用。

**统一用以下 helper 创建客户端（所有 mootdx 调用都走它）：**

```python
import socket
from mootdx.quotes import Quotes

# 实测可用的备选服务器（按延迟排序，2026-06 验证）
_TDX_SERVERS = [
    ('119.97.185.59', 7709), ('124.70.133.119', 7709), ('116.205.183.150', 7709),
    ('123.60.73.44', 7709),  ('116.205.163.254', 7709), ('121.36.225.169', 7709),
    ('123.60.70.228', 7709), ('124.71.9.153', 7709),    ('110.41.147.114', 7709),
    ('124.71.187.122', 7709),
]

def _probe(ip, port, timeout=2.0):
    """TCP 握手探测（快速粗筛）。注意：握手成功 ≠ 能取数，必须再经 _validate 验活。"""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def _validate(client, market: str = 'std', check: str = 'bars') -> bool:
    """真实取数验活：坏服务器可 TCP 握手通过却回 2 字节空 body → 静默空表。用一次真实请求兜底。

    check='bars'   ：用 K 线请求验活（§1.7 行情类调用）；
    check='finance'：财务快照、F10 类别表里的「最新提示」及其正文都要取到才算活（§6.1 财务 / §6.2、§7.2 F10 调用），
                     只验财务会选中「财务正常、F10 为空」的服务器，F10 随后静默给空文本；
                     只看类别表非空，又会放过只回别的类别或畸形对象的服务器。
    两者要分开：2026-09 起通达信公开服务器的行情类命令（bars / quotes / transaction）普遍返回空表，
    而 finance / F10「最新提示」/ 除权除息仍正常（#52）。财务类调用若仍用 K 线验活，会被误判成「全部不可达」。
    验活样本 '000001' 是 A 股代码，只对 market='std' 有意义。其它市场（如扩展行情 'ext'）
    用它必然取不到数，会把所有正常服务器都判死、误报「全部不可达」，故非 std 时跳过验活。
    """
    if market != 'std':
        return True
    try:
        if check == 'finance':
            cats = client.F10C(symbol='000001')
            if not any(isinstance(c, dict) and c.get('name') == '最新提示' for c in cats):
                return False
            text = client.F10(symbol='000001', name='最新提示')
            if not isinstance(text, str) or not text.strip():
                return False
            df = client.finance(symbol='000001')
        else:
            df = client.bars(symbol='000001', frequency=9, offset=1)
        return df is not None and not df.empty
    except Exception:
        return False

def tdx_client(market='std', check='bars'):
    """
    创建 mootdx 客户端，规避 0.11.x BESTIP.HQ 空串 bug + 坏服务器静默空表（#43）。
    check: 'bars'（默认，K 线 / 盘口 / 逐笔）或 'finance'（财务快照 / F10），决定用哪类请求验活（#52）。
    每个候选都必须「真实取数验活」通过才采用（_probe TCP 握手是假阳性来源）：
      1) 顺序探测 _TDX_SERVERS，对 probe 通过者再 _validate 真实取数，取第一个验活成功的；
      2) 全部失败 → 回退 mootdx 自带 bestip 测速选优（同样验活）；
      3) 再回退裸 factory（老用户 config 已有可用 BESTIP 时成立）；
      4) 仍失败 → 抛 RuntimeError，明确报错而非静默返回空表 / 崩溃。
    """
    if check not in ('bars', 'finance'):
        raise ValueError("check 只能是 'bars' 或 'finance'")
    for ip, port in _TDX_SERVERS:
        if not _probe(ip, port):
            continue
        try:
            c = Quotes.factory(market=market, server=(ip, port))
            if _validate(c, market, check):
                return c
        except Exception:
            continue                                        # 握手过但取数崩 → 跳过下一台
    for kwargs in ({'bestip': True}, {}):                   # fallback: bestip 测速 / 裸 factory
        try:
            c = Quotes.factory(market=market, **kwargs)
            if _validate(c, market, check):
                return c
        except Exception:
            continue
    hint = ("海外网络通常全部超时（TCP 7709），请走国内代理或更新 _TDX_SERVERS 列表。")
    if check == 'bars':
        hint += ("若国内网络也如此：2026-09 起通达信公开服务器的 K 线 / 盘口 / 逐笔命令普遍返回空（#52），"
                 "K 线改用 §1.2 tencent_kline()（日周月 + 1~60 分钟）或 §1.3 tdx_daily_package()"
                 "（全市场当日日线含成交额），逐笔改用 §1.4 tencent_ticks()（当日）；"
                 "财务与 F10 用 tdx_client(check='finance') 仍可取。")
    raise RuntimeError("所有 mootdx 服务器均无法取到数据（TCP 可达但返回空 / 被 reset）。" + hint)

# 用法：client = tdx_client()                  # K 线 / 盘口 / 逐笔（#52：目前普遍取不到，见 §1.7 警告）
#       client = tdx_client(check='finance')   # 财务快照 / F10（正常）
```

> **海外 IP 用户：** mootdx 走通达信 TCP 7709，海外环境通常全部超时。`tdx_client()` 会快速失败给出明确报错，而非死等。
>
> **⚠️ 行情命令失效（#52，2026-09-20 实测）：** 内置 10 台服务器逐台测试，TCP 均可达，`finance` / `xdxr` 正常、
> `F10` 只剩「最新提示」一类（见 §6.2），但 `bars` / `quotes` / `transaction` 全部返回 0 行。财务与 F10 调用请传 `check='finance'`；
> K 线改走 §1.2 腾讯 / §1.3 通达信盘后包，实时价与五档走 §1.1 腾讯，当日逐笔走 §1.4 腾讯。

### 市场前缀规则（全局通用）

```python
# 沪市指数白名单：与深市 000xxx 个股同段，需白名单区分（沪深300/上证50/中证500/科创50/中证1000/上证180）
SH_INDEX = {"000300", "000905", "000016", "000688", "000852", "000010"}

def get_prefix(code: str) -> str:
    """6位代码 → 市场前缀（sh/sz/bj）。支持显式前缀/后缀（sh000016 / 000016.SH）透传以解决歧义。"""
    c = code.lower().strip()
    if c.endswith((".sh", ".sz", ".bj")):    # 后缀写法与前缀等价：000016.SH ≡ sh000016。
        return c[-2:]                        # 不认后缀会让 000016.SH 落到默认深市 → 静默查成深康佳A
    if c.endswith((".xshg", ".xshe")):       # 聚宽写法（#55）：.XSHG=上交所 / .XSHE=深交所，000001.XSHG=上证指数
        return "sh" if c.endswith(".xshg") else "sz"
    if c.startswith(("sh", "sz", "bj")):     # 显式前缀透传（如 sh000001=上证指数 vs sz000001=平安银行）
        return c[:2]
    if c.startswith("92"):                   # 北交所 2024-10 起的新股号段，必须先于下面的 9x 判断
        return "bj"
    if c.startswith(("5", "6", "9")):        # 5x=沪 ETF/LOF，6/9=沪个股（900xxx=沪 B 股）
        return "sh"
    if c.startswith(("4", "8")):             # 4x/8x=北交所【老号段，多数已迁 920，见下方警告】
        return "bj"
    if c in SH_INDEX:                         # 沪深300/上证50 等沪指数（000xxx）
        return "sh"
    return "sz"                              # 深市个股/ETF（00/30/15x/16x/159 等），深指数 399xxx 亦走 sz

```

> **歧义说明：** `000001` 默认按个股→`sz000001`（平安银行）；要上证指数请显式传 `sh000001`。`000016` 默认按沪指数→上证50；要深康佳A 请传 `sz000016`。

> ### ⚠️ 北交所老号段（43/83/87）已基本作废 — 会拿到僵尸数据且不报错
>
> **2026-07-31 实测：** 东财北交所在市 342 只中 **336 只已是 `920xxx` 号段**，仅剩 3 只老码且全部停牌。存量公司代码已整体迁移（如 锦波生物 `832982`→`920982`、贝特瑞 `835185`→`920185`）。
>
> **危险在于老码不会报错，而是返回看似正常的脏数据：**
>
> | 接口 | 传老码 `832982` | 传新码 `920982` |
> |------|----------------|----------------|
> | 腾讯行情 | 返回 **112.60、成交量 0**（定格在迁移日） | 131.74，正常成交 ✅ |
> | 腾讯行情（贝特瑞） | `835185` → 45.91、成交量 0 | `920185` → 21.05 ✅ |
> | 东财研报 | **0 篇**（静默空） | 79 篇 ✅ |
>
> 老码行情价与真实价可差 17%~100%+，直接拿去算估值会得出完全错误的结论。
>
> **判定僵尸报价：** `成交量 == 0 且 最新价 == 昨收` → 极可能是已迁移的废码（真停牌股同样满足，两者都不该用于估值）。`tencent_quote()` 已内置该检测并置 `is_stale` 标志，见 §1.1。
>
> **拿新码：** 用 `push2` 北交所全量清单 `fs=m:0+t:81+s:2048` 按名称反查现行代码。

### Ticker 格式归一化

`norm_ticker()` 把下列写法统一成纯 6 位数字：

> ⚠️ **不是所有端点都自动归一化**（V3.6.0 前这里写的是「所有接口统一支持」，与实现不符，已改正）。
> - **已内置归一化**：§2.1 `eastmoney_reports()`、§2.2 `ths_eps_forecast()`。
> - **只认纯 6 位或显式 `sh`/`sz`/`bj` 前缀**（其余端点）：`tencent_quote()` 等走 `get_prefix()` 路由的函数
>   支持 `600519` 和 `sh600519`，但**不认后缀式** `600519.SH`——实测会拼成 `sh600519.SH` 并返回空载荷（静默失败）。
> - **结论**：拿到用户输入的代码，**先过一遍 `norm_ticker()` 再传给任何端点**，最省事也最安全。
>   例外：输入本身带市场信息且落在 000 歧义段（`000001.SH` / `000001.XSHG` = 上证指数）时，`norm_ticker()` 会丢掉市场，
>   应改用 `get_prefix(c) + norm_ticker(c)` 得到 `sh000001` 再传。聚宽代码互转见下方 `to_joinquant()`（#55）。

| 输入 | 归一化结果 |
|------|-----------|
| `688017` | `688017` |
| `SH688017` / `sh688017` | `688017` |
| `688017.SH` / `688017.sh` | `688017` |
| `SZ000001` | `000001` |
| `BJ920982` | `920982` |
| `600519.XSHG` / `000001.XSHE`（聚宽写法，#55） | `600519` / `000001` |

```python
import re

# 整串锚定匹配，只认下表列出的写法；市场标识前缀、后缀**二选一，不能同时出现**。
# ⚠️ 两个坑都会造成「静默拿到另一只股票的数据」，比报错危险得多：
#   ① 别用 re.search(r"\d{6}") 从任意串里"捞"6 位："6005190"/"foo600519bar" 会被截成 600519。
#   ② 别让前后缀同时可选：`SH000001.SZ` 这种自相矛盾的写法会被照单全收，
#      而 000001 恰是歧义码（sh000001=上证指数 / sz000001=平安银行），静默丢掉市场信息＝选错标的。
# 捕获组：1=前缀市场 2=前缀式代码 | 3=后缀式代码 4=后缀市场
# 市场标识要**同时**从前缀和后缀取——只认 startswith("sh") 会漏掉 `000001.SH` 这种后缀写法。
_TICKER_RE = re.compile(
    r"^(?:(sh|sz|bj)(\d{6})|(\d{6})(?:\.(sh|sz|bj|xshg|xshe))?)$", re.IGNORECASE)
_JQ_SUFFIX = {"xshg": "sh", "xshe": "sz"}    # 聚宽后缀 → 市场（#55）；聚宽未公开北交所后缀，不猜

def _natural_market(digits: str) -> str:
    """6 位码的自然归属市场。仅用于校验显式前缀是否自相矛盾。
    注意 000xxx 是沪指数/深个股共用的歧义段，由调用处单独处理，不走这里。"""
    if digits.startswith(("4", "8", "92")):
        return "bj"                      # 北交所：与 get_prefix() 同一套号段规则（92x 现行 / 4x·8x 老号段，#51）
    if digits[0] in ("5", "6", "9"):
        return "sh"                      # 5x 沪 ETF/LOF，6xx 沪个股，9xx 沪 B 股
    return "sz"                          # 00x/30x/15x/16x/39x 等

def norm_ticker(code: str, stock_only: bool = False) -> str:
    """任意受支持写法 → 纯 6 位数字代码。

    支持 600519 / SH600519 / sh600519 / 600519.SH / BJ920982 等。
    stock_only=True：个股专用接口（研报、一致预期等）传这个，会拒绝显式指数写法。
    ⚠️ 不匹配时**抛 ValueError，绝不静默返回空串或猜一个代码**——
    否则调用方会把「代码格式写错」误读成「这只票没有数据」，
    或者更糟：拿到另一只股票的数据还以为是对的。
    """
    raw = str(code).strip()
    m = _TICKER_RE.match(raw)
    if not m:
        raise ValueError(
            f"无法把 {code!r} 解析为 6 位股票代码；"
            f"支持格式：600519 / SH600519 / sh600519 / 600519.SH / 600519.XSHG（聚宽）"
            f"（前缀与后缀二选一，不能同时写）"
        )
    digits = m.group(2) or m.group(3)
    market = (m.group(1) or m.group(4) or "").lower()      # 前缀式与后缀式都要认
    market = _JQ_SUFFIX.get(market, market)                  # 600519.XSHG ≡ 600519.SH
    # 归一化会丢掉市场标识，若标识与号段矛盾就会静默落到另一只票上，必须在这里拦。
    if market:
        if digits.startswith("000"):
            # 000xxx 是**沪市指数 / 深市个股共用**的歧义段，显式标识在这里是「消歧」不是「矛盾」：
            #   sh000001=上证指数 vs sz000001=平安银行；sh000016=上证50 vs sz000016=深康佳A。
            if market == "bj":
                raise ValueError(f"{code!r} 市场标识与号段矛盾：000xxx 不属北交所。")
            # 沪市个股只有 600/601/603/605/688/689（B 股 900），**不存在 000xxx 沪市个股**，
            # 所以「显式 sh + 000 段」必然是指数。实测不拦的话：sh000001→平安银行研报 100 篇、
            # sh000016→深康佳A、sh000039→中集集团 84 篇，全是别人的数据。
            if stock_only and market == "sh":
                raise ValueError(
                    f"{code!r} 指向沪市指数而非个股（沪市无 000xxx 个股），本接口只服务个股。"
                    f"要查同号段的深市个股请显式传 sz{digits}。"
                )
        else:
            nat = _natural_market(digits)
            if market != nat:
                raise ValueError(
                    f"{code!r} 的市场标识与号段矛盾：{digits} 属 {nat} 市，而不是 {market} 市。"
                    f"（改用 {nat}{digits} 或去掉市场标识）"
                )
    return digits

# 用法
norm_ticker("SH600519")      # '600519'
norm_ticker("600519.SH")     # '600519'
norm_ticker("bj920982")      # '920982'
norm_ticker("6005190")       # ValueError（7 位，不会被截成 600519）
norm_ticker("茅台")           # ValueError
norm_ticker("SH000001.SZ")   # ValueError（前后缀矛盾，不猜市场）
norm_ticker("SH000001", stock_only=True)     # ValueError（上证指数，不是平安银行）
norm_ticker("000001.SH", stock_only=True)    # ValueError（后缀写法同样拦下）
norm_ticker("SZ600519")                      # ValueError（600519 是沪市，标识矛盾）
norm_ticker("sz000016")                      # '000016'（深康佳A，000 段的显式消歧，合法）
norm_ticker("600519.XSHG")                   # '600519'（聚宽写法，#55）
norm_ticker("600519.XSHE")                   # ValueError（600519 是沪市，聚宽后缀同样校验）


def em_market_code(code: str) -> int:
    """东财 secid 的市场号：**沪=1，深/北=0**（V3.7.0 新增 · #46）。

    ⚠️ 绝不要用 `code.startswith("6")` 判市场 —— 那会把**沪市 ETF（51x）**、
    **科创板 ETF（588x）**、**沪 B 股（900x）** 全部错判成深市，接口返回 `data: null`。
    2026-08-19 实测：510300 / 588000 / 600519 / 688112 / 900901 → m=1；
    300750 / 159915 / 920982 / 832982 → m=0（北交所与深市共用 m=0）。
    """
    return 1 if get_prefix(code) == "sh" else 0


def em_secid(code: str) -> str:
    """东财 push2/push2his 的 secid，如 `1.600519` / `0.300750`。"""
    return f"{em_market_code(code)}.{norm_ticker(code)}"


def to_joinquant(code: str) -> str:
    """任意受支持写法 → 聚宽代码，如 `600519.XSHG` / `000001.XSHE`（#55）。

    000 段歧义码按 get_prefix() 的规则走：`to_joinquant("sh000001")` → `000001.XSHG`（上证指数），
    `to_joinquant("000001")` → `000001.XSHE`（平安银行）。反方向（聚宽 → 本 Skill）用
    `get_prefix(c) + norm_ticker(c)` 得到 `sh000001` 这类显式前缀写法，再传给各端点。
    北交所：聚宽公开文档与 jqdatasdk 源码（2026-09-20 查）只有 .XSHG / .XSHE，没查到北交所后缀，抛 ValueError 不猜。
    """
    digits, market = norm_ticker(code), get_prefix(code)
    if market == "bj":
        raise ValueError(f"{code!r} 是北交所证券；聚宽公开文档未给出北交所后缀，不做转换")
    return f"{digits}.{'XSHG' if market == 'sh' else 'XSHE'}"
```

### 东财数据中心统一查询（共用 helper）

龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用同一 base URL：

```python
import time
import random
import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── 东财防封：全局节流 + 会话复用 ────────────────────────────────────
# 东财系 HTTP 接口（push2 / datacenter / reportapi / search / np-weblist）有风控：
#   每秒 >5 次 / 单 IP 并发 ≥10 / 1 分钟 ≥200 次  →  临时封 IP。
# 所有 eastmoney.com 请求一律走 em_get()：串行限流（最小间隔 + 随机抖动）+ 复用
# Keep-Alive 会话，批量调用时自动降速，避免被封。详见「数据源优先级 & 东财防封」章节。
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
# 连接级自动重试：瞬态连接错误 / 429 / 5xx 指数退避重试（住宅IP偶发风控更稳）。
# 注意：403 不重试（东财风控信号，重试无益反而加重；按下方 EM_MIN_INTERVAL 降频应对）。
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _em_adapter = HTTPAdapter(max_retries=Retry(
        total=3, connect=3, backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    EM_SESSION.mount("https://", _em_adapter)
    EM_SESSION.mount("http://", _em_adapter)
except Exception:
    pass  # 老版本 urllib3 缺 allowed_methods 等参数时降级为无重试，不影响主流程
from typing import Optional     # 3.9 兼容：不能写 `dict | None`（那是 3.10+ 语法）

EM_MIN_INTERVAL = 1.0          # 两次东财请求最小间隔(秒)；批量筛选建议调大到 1.5~2
_em_last_call = [0.0]          # 模块级上次请求时间戳

def em_get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None,
           timeout: int = 15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session + 默认 UA。
    所有 eastmoney.com 接口都应通过它请求，避免高频被封 IP。"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return EM_SESSION.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()

def eastmoney_datacenter(report_name: str, columns: str = "ALL",
                          filter_str: str = "", page_size: int = 50,
                          sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用（已内置限流）"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    r = em_get(DATACENTER_URL, params=params, timeout=15)
    d = r.json()
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []
```

### V3.9.0 共用 helper（§1.2 腾讯 K 线起的所有 V3.9.0 / V3.10.0 新端点都依赖它）

先执行上面的 `get_prefix` / `norm_ticker` / 东财 `em_get` 代码块，再执行本块。V3.9.0 新端点统一返回 DataFrame，
末尾附 `source` / `source_url` / `fetched_at` 三列。**「确实没有数据」与「接口坏了」分开处理**：前者返回空表或抛
`ValueError`（非交易日、日期太早），后者抛 `RuntimeError`（结构改变、重复行、全市场 0 行），不把错误页当空结果。
东财请求一律经 `em_get()` 限流；`_em_datacenter_strict()` 与旧 `eastmoney_datacenter()` 的区别是会翻页、并把错误码抛出来。

<!-- v39-helpers:start -->
```python
import functools
import math
import re
from datetime import date as _date_cls, datetime, timezone

import pandas as pd
import requests

V39_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 一次要翻几十页（§1.4 腾讯逐笔）或偶尔握手卡住（§13.7 新浪期货日 K）的请求走这个会话：复用连接，
# 连接失败、握手或等响应头超时、429 / 5xx 指数退避重试（写法同 EM_SESSION）；读响应体中途超时不重试，
# 也不按服务端给的 Retry-After 等待。
V39_RETRY_SESSION = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _v39_retry_adapter = HTTPAdapter(max_retries=Retry(
        total=3, connect=3, backoff_factor=0.6, respect_retry_after_header=False,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]))
    V39_RETRY_SESSION.mount("https://", _v39_retry_adapter)
    V39_RETRY_SESSION.mount("http://", _v39_retry_adapter)
except Exception:
    # 老版本 urllib3（< 1.26）缺 allowed_methods：不重试，也不复用连接（复用的连接被服务端断开时没有重试兜底），同 v3.10.0
    V39_RETRY_SESSION = None


def _v39_http(url, params=None, data=None, headers=None, method="GET", timeout=(10, 40),
              allow_status=(), allow_redirects=True, session=None):
    """非东财的 HTTP 请求：带浏览器 UA。网络错误、非 2xx 一律抛 RuntimeError（不把错误页当数据）；
    allow_status 里的状态码（源用 404 表示「当天没发布」时）原样返回，由调用方判断。
    session：传 V39_RETRY_SESSION 复用连接并自动重试（哪些情况重试见它的定义）；不传每次新建连接、不重试。"""
    merged = {"User-Agent": V39_UA}
    merged.update(headers or {})
    try:
        response = (session or requests).request(method, url, params=params, data=data, headers=merged,
                                                 timeout=timeout, allow_redirects=allow_redirects)
        if response.status_code not in allow_status:
            response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"请求 {url} 失败: {type(exc).__name__}: {exc}") from exc
    return response


def _v39_json(response):
    """解析 JSON；不是 JSON 抛 RuntimeError。json 的解析错误是 ValueError 的子类，
    不转换会被调用方当成「确实没有数据」。"""
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{getattr(response, 'url', '')} 返回的不是 JSON，可能是错误页") from exc


def _v39_date(value):
    """'2026-09-18' / '20260918' / date 对象 → '2026-09-18'；其他写法抛 ValueError。"""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, _date_cls):
        return value.isoformat()
    text = str(value).strip()
    fmt = "%Y%m%d" if re.fullmatch(r"[0-9]{8}", text) else "%Y-%m-%d"
    return datetime.strptime(text, fmt).date().isoformat()


def _v39_src_date(value):
    """来源返回的日期 → 'YYYY-MM-DD'；认不出抛 RuntimeError（源格式变了，不是参数写错）。"""
    try:
        return _v39_date(value)
    except ValueError as exc:
        raise RuntimeError(f"来源返回了无法识别的日期 {value!r}") from exc


def _v39_num(value):
    """'1,234.50' → 1234.5；空串 / '-' / '--' / None → None；其他非数字抛 RuntimeError
    （来源给了认不出的值是「源的格式变了」，不能和参数错误的 ValueError 混在一起）。
    JSON 布尔值同样抛错：float(True)=1.0 会把格式错误静默写成价格 / 成交量。"""
    if value is None:
        return None
    if isinstance(value, bool):
        raise RuntimeError(f"来源在数值字段给了布尔值 {value!r}")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return float(value)
    text = str(value).replace(",", "").strip()
    if text in ("", "-", "--", "None", "null"):
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise RuntimeError(f"来源返回了无法识别的数值 {value!r}") from exc
    return number if math.isfinite(number) else None


def _v39_rows(value, what):
    """来源里可能整段缺失的行列表：字段没有（None）按空处理，其余必须是对象列表。
    写成 `value or []` 会把 {} / '' / 0 这类结构改变也当成空表，静默丢掉整段数据。"""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise RuntimeError(f"{what} 应为对象列表，实际是 {type(value).__name__}: {str(value)[:120]}")
    return value


def _v39_labels(value, what):
    """来源的标签数组（频道名之类）：None 按空处理，其余必须是字符串列表。
    直接 `value or []` 再 join，来源把数组改成字符串时会被拆成单字（'ab' → 'a,b'）。"""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise RuntimeError(f"{what} 应为字符串列表，实际是 {type(value).__name__}: {str(value)[:120]}")
    return value


def _v39_req_num(value, what):
    """必填数值（价格、成交量）：在 _v39_num 之上，空值 / NaN / inf 也抛 RuntimeError，不能当缺失放过。"""
    number = _v39_num(value)
    if number is None:
        raise RuntimeError(f"来源的 {what} 为空或不是有限数值: {value!r}")
    return number


def _v39_contract(func):
    """统一异常契约：来源行缺字段时 row["X"] 会漏出 KeyError，调用方按「参数错 / 没数据」处理就会
    把「来源格式变了」当成正常情况。这里把它转成带函数名和字段名的 RuntimeError。
    （函数内所有按用户参数取字典的地方都先校验过参数，不会走到这里。）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as exc:
            raise RuntimeError(f"{func.__name__}: 来源数据缺少字段 {exc}，格式可能已变") from exc
    return wrapper


def _v39_count(value, what):
    """来源自报的页数 / 条数 → 非负 int。只认 int 或纯数字串；bool 抛错（int(True)=1 会让
    「只返回 1 条」通过完整性核对），其他写法也抛 RuntimeError。"""
    text = str(value).strip() if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    if not re.fullmatch(r"[0-9]+", text):
        raise RuntimeError(f"{what} 不是非负整数: {value!r}")
    return int(text)


def _v39_frame(rows, source, url, columns=None):
    """统一出表：附 source / source_url / fetched_at。rows 为空时返回带列名的空表，
    是否允许为空由调用方判断（「确实没有」与「接口坏了」要分开处理）。"""
    frame = pd.DataFrame(rows, columns=columns)
    frame["source"] = source
    frame["source_url"] = url
    frame["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return frame


def _em_datacenter_strict(report_name, filter_str="", sort_columns="", sort_types="",
                          page_size=500, max_rows=5000, columns="ALL", extra=None):
    """东财 datacenter 严格版：code=0 取数据；第 1 页就 9201(返回数据为空) → []；其他错误码直接抛。

    与旧 eastmoney_datacenter() 的区别：后者把任何失败都变成 []，调用方分不清
    「这只票确实没有」和「参数写错/被风控」。sortTypes 个数必须与 sortColumns 一致，
    否则东财返回 9501「排序字段和顺序数量不一致」。
    翻页中途失败（第 2 页起 9201、空页、非末页不满页、缺 pages / count、总页数或总条数变了、
    最终条数与 count 不符）抛 RuntimeError，不把部分结果当完整结果返回。
    payload / result 不是对象、data 不是由对象组成的列表，同样抛 RuntimeError。
    只有「第 1 页、pages=1、data 为空」才算确实没有数据。
    max_rows 只在来源自报总数 count > max_rows 时提前截断；count 不超过上限的，一律走完分页并核对总数。
    """
    n_cols = len([c for c in sort_columns.split(",") if c]) if sort_columns else 0
    n_types = len([t for t in sort_types.split(",") if t]) if sort_types else 0
    if n_cols != n_types:
        raise ValueError(f"sortColumns({n_cols}) 与 sortTypes({n_types}) 个数不一致")
    rows, page, first = [], 1, None
    while True:
        params = {"reportName": report_name, "columns": columns, "filter": filter_str,
                  "pageNumber": str(page), "pageSize": str(page_size),
                  "sortColumns": sort_columns, "sortTypes": sort_types,
                  "source": "WEB", "client": "WEB"}
        params.update(extra or {})
        try:
            response = em_get(DATACENTER_URL, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"东财 {report_name} 请求失败: {type(exc).__name__}: {exc}") from exc
        payload = _v39_json(response)
        if not isinstance(payload, dict):
            raise RuntimeError(f"东财 {report_name} 返回的不是 JSON 对象: {str(payload)[:100]}")
        if payload.get("code") == 9201:
            if page == 1:
                return []
            raise RuntimeError(f"东财 {report_name} 第 {page} 页返回「数据为空」，"
                               f"前面已取 {len(rows)} 条，结果不完整")
        if payload.get("code") != 0 or not payload.get("result"):
            raise RuntimeError(f"东财 {report_name} 返回错误: "
                               f"{payload.get('code')} {payload.get('message')}")
        result = payload["result"]
        if not isinstance(result, dict):
            raise RuntimeError(f"东财 {report_name} 的 result 不是对象: {str(result)[:100]}")
        pages, count, data = result.get("pages"), result.get("count"), result.get("data")
        if data is None:
            data = []
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise RuntimeError(f"东财 {report_name} 第 {page} 页的 data 不是由对象组成的列表，格式可能已变")
        if (any(isinstance(v, bool) or not isinstance(v, int) for v in (pages, count))
                or pages < 1 or count < 0):
            raise RuntimeError(f"东财 {report_name} 缺少分页信息（pages={pages!r}, count={count!r}）")
        if first is None:
            first = (pages, count)
        elif (pages, count) != first:
            raise RuntimeError(f"东财 {report_name} 翻页时总页数 / 总条数从 {first} 变成 {(pages, count)}，"
                               "结果可能错位，请重试")
        if not data and (page > 1 or pages > 1):
            raise RuntimeError(f"东财 {report_name} 第 {page}/{pages} 页是空的，结果不完整")
        if page < pages and len(data) != int(page_size):
            raise RuntimeError(f"东财 {report_name} 第 {page}/{pages} 页只有 {len(data)} 条"
                               f"（非末页应为 {page_size} 条），结果不完整")
        rows.extend(data)
        # 只有来源自报的总数确实超过上限才提前截断；否则（count <= max_rows 却已拿到更多行）
        # 必须走完分页并核对总数，不然「data 比 count 还多」这种格式异常会被当成正常截断放过
        if len(rows) >= max_rows and count > max_rows:
            return rows[:max_rows]
        if page >= pages:
            if len(rows) != count:
                raise RuntimeError(f"东财 {report_name} 翻页后 {len(rows)} 条，与总数 {count} 不符")
            return rows
        page += 1


def _em_day(value):
    """东财日期串 '2026-09-18 00:00:00' → '2026-09-18'；空值 → None；认不出的写法抛 RuntimeError
    （只截前 10 个字符会把 '2026/09/18' 原样放行，再拿去和日期串比较就会比错）。"""
    return _v39_src_date(str(value)[:10]) if value else None
```
<!-- v39-helpers:end -->

---
