> 本文件 = 单文件版 SKILL.md 的 Layer 6 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。
> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。

## Layer 6: 基础数据层

### 6.1 mootdx 财务快照（37字段季报数据）

```python
from mootdx.quotes import Quotes

client = tdx_client(check='finance')  # 见 Prerequisites 的 tdx_client()；财务/F10 按 finance 验活（#52：K 线命令失效不影响这里）

# market: 0=深圳, 1=上海
fin = client.finance(symbol='688017')
# 返回 37 个字段的季报快照:
#   liutongguben(流通股本), zongguben(总股本)
#   eps(每股收益), bvps(每股净资产), roe(净资产收益率%)
#   profit(净利润), income(主营收入)
#   meigujingzichan(每股净资产), meigugongjijin(每股公积金)
#   meiguweifeipeili(每股未分配利润)
#   等37个季报财务字段
```

### 6.2 mootdx F10（公司文本资料）

```python
from mootdx.quotes import Quotes

client = tdx_client(check='finance')  # 见 Prerequisites 的 tdx_client()；财务/F10 按 finance 验活（#52：K 线命令失效不影响这里）

# 先用 F10C 列出服务器实际提供的类别，不要写死类别名：
# 请求不存在的类别时 mootdx 不报错，而是返回 {类别: 文本} 的 dict，按字符串切片会抛 TypeError。
for cat in client.F10C(symbol='688017'):
    text = client.F10(symbol='688017', name=cat['name'])
    print(f"=== {cat['name']} ===")
    print(text[:200] if text else "(空)")
```

> **⚠️ 2026-09 起 F10 只剩「最新提示」一类（#52 同一次服务端变化）：** 内置 10 台服务器 2026-09-20 逐台实测，
> `F10C` 只返回「最新提示」（内含 最新提示 / 互动问答 / 最新公告 / 最新报道 / 最新异动 / 大宗交易 / 融资融券 / 风险提示 8 个小节，
> 约 1.2 万字）；原来的公司概况、财务分析、股东研究、股本结构、资本运作、业内点评、行业分析、公司大事 8 类不再返回。
> 替代：行业 / 股本 / 市值 → §6.3；财务 → §6.1、§6.4；股东户数 → §4.3；增减持 → §14.3；回购 → §14.4；质押 → §14.5；
> 公司公告与大事 → §7.1 巨潮。

### 6.3 东财个股基本面（直连 push2 API）

```python
import requests

def eastmoney_stock_info(code: str) -> dict:
    """
    东财个股基本面信息。
    返回: {code, name, industry, total_shares, float_shares, mcap, float_mcap, list_date}
    """
    market_code = em_market_code(code)      # #46
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
        "secid": f"{market_code}.{code}",
    }
    headers = {"User-Agent": UA}
    r = em_get(url, params=params, headers=headers, timeout=10)
    d = r.json().get("data", {})
    return {
        "code": d.get("f57", ""),
        "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": d.get("f84", 0),     # 总股本(股)
        "float_shares": d.get("f85", 0),     # 流通股(股)
        "mcap": d.get("f116", 0),            # 总市值(元)
        "float_mcap": d.get("f117", 0),      # 流通市值(元)
        "list_date": str(d.get("f189", "")), # 上市日期 YYYYMMDD
        "price": d.get("f43", 0),
    }

# 用法
info = eastmoney_stock_info("688017")
print(f"{info['name']}({info['code']}): 行业={info['industry']} 总市值={info['mcap']/1e8:.0f}亿 上市={info['list_date']}")
```

### 6.4 新浪财报三表（资产负债表/利润表/现金流量表）

```python
import requests

def sina_financial_report(code: str, report_type: str = "lrb", num: int = 8) -> list[dict]:
    """
    新浪财报三表。
    code: 6位代码
    report_type: "fzb"(资产负债表) / "lrb"(利润表) / "llb"(现金流量表)
    num: 取最近 N 期（默认 8 期）
    返回: 按报告期倒序的记录列表，每期一条 dict：
          {"报告期": "2026-03-31", "<科目>": "<值>", "<科目>_同比": <同比>, ...}
          （item_value 为新浪原始字符串数值，仅在有同比时附 "_同比" 键）
    """
    prefix = get_prefix(code)               # #46：51x/588x/900x 也是沪市
    paper_code = f"{prefix}{code}"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {
        "paperCode": paper_code,
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    headers = {"User-Agent": UA}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    # 新浪实际结构: result.data.report_list 是「按报告期(如 '20260331')为键」的 dict,
    # 每期对象的 data 字段才是行项列表 [{item_title, item_value, item_tongbi}]。
    # #46 同因：任一层为 null 时 `.get(k, {})` 返回 None，链式 .get 会 AttributeError
    _j = r.json() or {}
    report_list = ((_j.get("result") or {}).get("data") or {}).get("report_list") or {}

    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        rows.append(rec)
    return rows

# 用法: 利润表
lrb = sina_financial_report("600519", "lrb")
for item in lrb[:3]:
    print(f"报告期: {item.get('报告期', '')} 净利润: {item.get('净利润', '')}")

# 用法: 资产负债表
fzb = sina_financial_report("600519", "fzb")

# 用法: 现金流量表
llb = sina_financial_report("600519", "llb")
```

---

### 6.5 baostock 估值历史 — PE/PB/PS/PCF + 换手率 + 停牌 + ST（V3.7.0 新增）

**核心价值：** §1.1 腾讯只给**当日**估值快照，本端点给**日频历史序列**（可回溯至 2016），
一次调用同时拿到四个我们此前完全没有的字段：**换手率**（筹码分布的必需输入）、
**停牌状态**、**ST 标记**、**历史估值**。

🔴 **北交所不支持**：baostock 服务端直接拒绝 4/8/92/920 号段，报
`10004011 股票代码未标识sh或sz`（2026-08-19 实测）。本实现在**登录前**就拦掉并抛 `ValueError`，
不浪费一次会话，也不会静默返回空表。

```python
from contextlib import contextmanager

import baostock as bs
import pandas as pd


@contextmanager
def bs_session():
    """baostock 登录会话 — 必须用上下文管理器，异常路径也保证 logout"""
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {lg.error_code} {lg.error_msg}")
    try:
        yield
    finally:
        bs.logout()


def _rs_to_df(rs) -> pd.DataFrame:
    """baostock ResultData → DataFrame；错误码转异常，绝不静默返回空表"""
    if rs.error_code != "0":
        raise RuntimeError(f"baostock 查询失败: {rs.error_code} {rs.error_msg}")
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    return pd.DataFrame(rows, columns=rs.fields)


def _bs_code(code: str) -> str:
    """6位代码 → baostock 格式；北交所在登录前就拦掉"""
    code = str(code).zfill(6)
    if code[:2] in ("60", "68", "90"):
        return f"sh.{code}"
    if code[:2] in ("00", "30", "20"):
        return f"sz.{code}"
    raise ValueError(
        f"baostock 不支持该代码: {code}（北交所 4/8/92/920 号段会被服务端拒绝，"
        f"报 10004011 股票代码未标识sh或sz）。北交所估值请改用 §1.1 腾讯当日快照。"
    )


def baostock_valuation_history(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """估值历史序列 — PE/PB/PS/PCF + 换手率 + 停牌 + ST，日频"""
    bs_code = _bs_code(code)          # 先校验，失败就不必登录
    fields = "date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM,turn,tradestatus,isST"
    with bs_session():
        rs = bs.query_history_k_data_plus(
            bs_code, fields, start_date=start_date, end_date=end_date,
            frequency="d", adjustflag="3",     # 3=不复权，与 §1.2 tencent_kline(adjust='') 口径一致
        )
        df = _rs_to_df(rs)
    for c in ("close", "peTTM", "pbMRQ", "psTTM", "pcfNcfTTM", "turn"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# 用法
df = baostock_valuation_history("600519", "2016-01-04", "2026-08-18")
print(len(df), "行", df.iloc[0]["date"], "→", df.iloc[-1]["date"])
print(df.tail(2)[["date", "close", "peTTM", "pbMRQ", "psTTM", "turn", "isST"]].to_string(index=False))
# 实测 2026-08-19：2581 行；2026-08-18 peTTM=19.93 pbMRQ=6.46 psTTM=9.37 turn=0.3098

# ST 标记实测有效：000004 在 2024-01 至今的 610 个交易日里有 276 天 isST=1
st = baostock_valuation_history("000004", "2024-01-01", "2026-08-18")
print("isST 分布:", st["isST"].value_counts().to_dict())     # {'0': 334, '1': 276}

# 停牌：tradestatus == "0"
print("停牌天数:", (df["tradestatus"] == "0").sum())
```

**字段说明**

| 字段 | 含义 | 备注 |
|------|------|------|
| `peTTM` `pbMRQ` `psTTM` `pcfNcfTTM` | 市盈率TTM / 市净率MRQ / 市销率TTM / 市现率TTM | 负值代表亏损，不要直接排序 |
| `turn` | 换手率（**百分数**，0.31 = 0.31%） | §4.6 筹码分布的必需输入 |
| `tradestatus` | `1`=正常交易 `0`=停牌 | 算指标前应过滤掉停牌日 |
| `isST` | `1`=ST/*ST `0`=正常 | 历史逐日标记，可还原「当时是不是 ST」 |

---

### 6.6 baostock 标的基本信息 — 上市日 / 退市日 / 状态（V3.7.0 新增）

**核心价值：** 唯一能拿到**退市日期**的零鉴权源。配合 §1.1 的 `is_stale` 僵尸报价标志，
可以在回测/筛选阶段直接剔除已退市标的。

```python
def baostock_stock_basic(code: str) -> dict:
    """标的基本信息 — ipoDate(上市日) / outDate(退市日，在市为空) / status(1=上市 0=退市)"""
    bs_code = _bs_code(code)
    with bs_session():
        df = _rs_to_df(bs.query_stock_basic(code=bs_code))
    return df.iloc[0].to_dict() if not df.empty else {}


# 用法
print(baostock_stock_basic("600519"))
# 实测：{'code': 'sh.600519', 'code_name': '贵州茅台', 'ipoDate': '2001-08-27',
#        'outDate': '', 'type': '1', 'status': '1'}   ← outDate 为空 = 仍在市
```

> 🔴 **已退市标的的除权除息，三个源全缺**（2026-08 交叉验证）：通达信 `xdxr()` 即使传对
> `market=2` 也返回 0 条、东财历史快照同样没有、baostock 直接拒绝北交所代码。
> 已退市标的（尤其北交所）**做复权必然对不上**，不是本工具包的缺陷，是源侧的保留策略。

---

### 6.7 申万行业分类历史 — 消除行业前视偏差（V3.7.0 新增）

**核心价值：** §3.7 `industry_comparison()` 用东财，**只有当前归属**。做历史研究时用今天的
行业分类去套过去，是典型的**前视偏差**。本端点给出每只股票的**行业变迁史**。

⚠️ 申万官方只发布**代码**不发布中文名（名称表是另一份未公开发布）。
东财/通达信的行业名**不能**直接套——分类体系不同，代码不通用。

```python
import io

from typing import Optional

import pandas as pd
import requests

SW_URL = "https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls"


def sw_industry_history() -> pd.DataFrame:
    """申万行业归属变迁史 — 每只股票每次行业调整一行"""
    try:
        r = requests.get(SW_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
    except requests.exceptions.SSLError as e:
        # 2026-08-19 实测：纯 certifi 环境握手正常，证书链完整，无需手动补中间证书。
        # 保留此分支是为了在站点证书回归时给出可操作的提示，而不是吞掉异常。
        raise RuntimeError(
            "申万站点 SSL 握手失败。2026-08 实测其证书链正常，若你遇到此错误，"
            "多半是本机 CA 包过旧或中间人代理：先试 `pip install -U certifi`。"
            f"原始错误: {e}"
        ) from e
    df = pd.read_excel(io.BytesIO(r.content))
    df = df.rename(columns={"股票代码": "code", "计入日期": "start_date",
                            "行业代码": "industry_code", "更新日期": "update_date"})
    missing = {"code", "start_date", "industry_code"} - set(df.columns)
    if missing:
        raise RuntimeError(f"申万表结构变了，缺列 {sorted(missing)}；实际列={list(df.columns)}")
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["industry_code"] = df["industry_code"].astype(str).str.zfill(6)
    # 层级码要补成规范的 6 位（申万官方一级是 480000、二级是 480300），
    # 直接截断成 "48"/"4803" 无法与官方指数/名称表 join。
    df["l1_code"] = df["industry_code"].str[:2] + "0000"    # 一级，如 480000
    df["l2_code"] = df["industry_code"].str[:4] + "00"      # 二级，如 480300
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    return df.sort_values(["code", "start_date"]).reset_index(drop=True)


def sw_industry_as_of(df: pd.DataFrame, code: str, as_of: str) -> Optional[dict]:
    """某只股票在 as_of 日所属的申万行业（取不晚于该日的最后一次调整）"""
    code = str(code).zfill(6)
    sub = df[(df["code"] == code) & (df["start_date"] <= pd.Timestamp(as_of))]
    if sub.empty:
        return None                  # 该日尚未上市 / 无归属记录
    row = sub.iloc[-1]
    return {"code": code, "as_of": as_of,
            "industry_code": row["industry_code"],
            "l1_code": row["l1_code"], "l2_code": row["l2_code"],
            "since": row["start_date"].strftime("%Y-%m-%d")}


# 用法
sw = sw_industry_history()
print(len(sw), "行 |", sw["code"].nunique(), "只标的 |",
      sw["l1_code"].nunique(), "个一级行业")
# 实测 2026-08-19：12893 行 | 5905 只 | 38 个一级 / 194 个二级 / 553 个三级

# 前视偏差验证：平安银行在不同时点属于不同行业
for d in ("2013-01-01", "2016-01-01", "2026-08-18"):
    print(d, sw_industry_as_of(sw, "000001", d))
# 2013-01-01 → 440101（一级 440000，自 1991-04-03）
# 2016-01-01 → 480101（一级 480000，自 2014-02-21）
# 2026-08-18 → 480301（一级 480000 / 二级 480300，自 2021-07-30）
```

> **典型用法：** 做行业轮动回测时，每个调仓日调用 `sw_industry_as_of()` 取**当时**的归属，
> 而不是用一张当前分类表贯穿全程。实测有标的历史上变更过 **10 次**行业。

### 6.8 ST / *ST 名单 — 全市场风险警示快照（V3.9.0 新增）

沪深走东财「风险警示板」过滤（含 B 股）；北交所不在这个过滤里，改为拉北交所全表按名称筛。
东财 push2 与 push2delay 都连不上时，退到 §6.5 baostock 证券列表按名称筛——**只有沪深、没有价格**，
`attrs['coverage']` 与 `attrs['fallback_reason']` 会写明。走 push2delay 时价格约有 15 分钟延迟（`source_url` 可看出走的哪个域）。
需要回测用的**历史** ST 状态，用 §6.5 `baostock_valuation_history()` 的 `isST` 列。

<!-- v39-st-list:start -->
```python
import requests

EM_CLIST_HOSTS = ["https://push2.eastmoney.com", "https://push2delay.eastmoney.com"]


def _em_clist_all(fs, fields, page_size=100):
    """东财 clist 全量翻页。主域网络失败时换 push2delay（同一接口，行情延迟约 15 分钟）。
    网络层全部失败抛 requests.ConnectionError；服务端返回异常内容（含非 JSON 的错误页）抛 RuntimeError，
    不换域重试，也不会让 st_stock_list 退到只有沪深的备胎。"""
    errors = []
    for host in EM_CLIST_HOSTS:
        url = host + "/api/qt/clist/get"
        rows, page, total = [], 1, None
        try:
            while True:
                response = em_get(url, params={"pn": page, "pz": page_size, "po": 1, "np": 1,
                                               "fltt": 2, "invt": 2, "fid": "f12",
                                               "fs": fs, "fields": fields}, timeout=15)
                response.raise_for_status()
                payload = _v39_json(response)
                data = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(data, dict) or payload.get("rc") != 0 or not data:
                    raise RuntimeError(f"东财 clist 返回异常或无数据（fs={fs}）: {str(payload)[:100]}")
                page_total = _v39_count(data.get("total"), f"东财 clist total（fs={fs}）")
                diff = _v39_rows(data.get("diff"), f"东财 clist 的 diff（fs={fs}）")
                if total is None:
                    total = page_total
                elif page_total != total:   # 翻页途中名单变了：拼出来的是两份名单的混合
                    raise RuntimeError(f"东财 clist 翻页时 total 从 {total} 变成 {page_total}，请重试")
                rows.extend(diff)
                if not diff or len(rows) >= total:
                    break
                page += 1
        except requests.RequestException as exc:
            errors.append(f"{host}: {type(exc).__name__}")
            continue
        if len(rows) != total:
            raise RuntimeError(f"东财 clist 翻页后 {len(rows)} 条，与 total={total} 不符")
        return rows, url
    raise requests.ConnectionError("东财 push2 / push2delay 均不可达: " + "; ".join(errors))


@_v39_contract
def st_stock_list():
    """全市场 ST / *ST 名单（风险警示）— 当日快照。

    沪深：东财「风险警示板」过滤（含 B 股）；北交所：东财不纳入该过滤，改为拉北交所全表按名称筛。
    东财两个域名都连不上时退到 baostock 证券列表按名称筛（**只有沪深、没有价格**，attrs 里注明）。
    price / pct_change 在走 push2delay 时约有 15 分钟延迟（source_url 可看出走的是哪个域）。
    """
    fields = "f12,f13,f14,f2,f3"
    try:
        shsz, url = _em_clist_all("m:0+f:4,m:1+f:4", fields)
        bj, bj_url = _em_clist_all("m:0+t:81+s:2048", fields)
    except requests.ConnectionError as exc:
        return _st_list_baostock(str(exc))
    # 两边原始集合都不该为空：北交所全表空了还标「沪深京」，会把缺失说成「北交所没有 ST」
    if not shsz or not bj:
        raise RuntimeError(f"东财风险警示板 {len(shsz)} 条、北交所全表 {len(bj)} 条，"
                           "有一边为空，不能当成沪深京完整名单")
    if bj_url != url:
        url = url + " | " + bj_url      # 两次调用可能落在不同域名（push2 / push2delay）
    rows = []
    for rec, is_bj in [(r, False) for r in shsz] + [(r, True) for r in bj]:
        # 代码 / 市场号 / 名称都是身份字段：f13 缺失或变样按「深市」处理会给出错误市场，
        # 名称为空则北交所那半边会被静默筛掉，结果却仍标「沪深京」。
        # 2026-09-20 实测两张表共 562 行：f12 全是 6 位、f13 只有 int 0/1、f14 无空值。
        code, market_id, name = rec["f12"], rec["f13"], str(rec["f14"]).strip()
        if (not re.fullmatch(r"[0-9]{6}", str(code)) or isinstance(market_id, bool)
                or market_id not in (0, 1)):
            raise RuntimeError(f"东财 clist 返回了认不出的代码 / 市场号: f12={code!r} f13={market_id!r}")
        if not name:
            raise RuntimeError(f"东财 clist 里 {code} 没有名称，ST 判定要靠名称，不能当成完整名单")
        if is_bj and "ST" not in name.upper():
            continue
        rows.append({"code": code,
                     "market": "bj" if is_bj else ("sh" if market_id == 1 else "sz"),
                     "name": name, "st_type": "*ST" if name.startswith("*") else "ST",
                     "price": _v39_num(rec.get("f2")), "pct_change": _v39_num(rec.get("f3"))})
    frame = _v39_frame(rows, "eastmoney", url)
    if frame.empty or frame.duplicated(["code"]).any():
        raise RuntimeError("ST 名单为空或代码重复，不能当成完整快照")
    frame.attrs["coverage"] = "沪深京"
    return frame


def _st_list_baostock(reason):
    import baostock as bs
    # 用名称模糊查询（约 300 条、2 秒）；不带参数的全量查询实测会在服务端卡住
    with bs_session():
        basic = _rs_to_df(bs.query_stock_basic(code_name="ST"))
    # type 1 = 股票，status 1 = 上市
    picked = basic[(basic["type"] == "1") & (basic["status"] == "1")
                   & basic["code_name"].str.upper().str.contains("ST")]
    rows = [{"code": c.split(".")[1], "market": c.split(".")[0], "name": n,
             "st_type": "*ST" if n.startswith("*") else "ST", "price": None, "pct_change": None}
            for c, n in zip(picked["code"], picked["code_name"])]
    frame = _v39_frame(rows, "baostock", "baostock.query_stock_basic")
    if frame.empty:
        raise RuntimeError("baostock 证券列表里没有筛出 ST，结果不可信")
    frame.attrs["coverage"] = "沪深（东财不可达，baostock 不含北交所）"
    frame.attrs["fallback_reason"] = reason
    return frame
```
<!-- v39-st-list:end -->

```python
st = st_stock_list()
print(st.attrs["coverage"], len(st), st.st_type.value_counts().to_dict())
```

---
