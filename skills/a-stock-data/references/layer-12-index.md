> 本文件 = 单文件版 SKILL.md 的 Layer 12 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。
> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。

## Layer 12: 指数与交易日历（V3.8.0）

补齐指数成分、权重、指数估值与官方交易日历。以下完整代码块可独立执行，仅使用已有的
`requests pandas xlrd openpyxl`；不依赖前面章节的股票代码推断规则。指数代码必须是 **6 位纯数字**，
`provider="csi"` 表示中证，`provider="cni"` 表示国证，不能把股票代码直接当指数查询。

| 函数 | 契约 |
|---|---|
| `index_constituents(index_code, provider="csi")` | 官方最近发布的成分快照；中证日度文件、国证月末文件，真实日期在 `date` 列 |
| `index_weights(index_code, provider="csi")` | 最近公布的权重；`weight_percent=0.433` 表示 **0.433%**，不是 43.3% |
| `index_valuation(index_code)` | 仅中证公开估值文件：两种股本口径 PE、两种股息率；**不提供 PB、不承诺全历史** |
| `trading_calendar(year, month)` | 深交所整月日历；逐日返回 `is_open`，不靠工作日推断，也不把未发布月份当休市 |

**日期边界：** 当前成分与权重可能不同日，不能按行号拼接或将月末权重标成今天。
这些快照不提供历史时点成分；国证的 `download-history` 名字虽带 history，本次接口实际返回
单个月末快照。历史调样另有接口，暂不纳入本版。调用方应先检查 `date`，做历史回测时不能拿
当前成分代替当时成分。网络失败、结构变化、重复记录或不完整日历均抛异常，不伪装为空结果。

### 12.1–12.4 自包含实现

<!-- official-data-core:start -->
```python
import calendar
import math
import re
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import requests


def _official_code(value):
    value = str(value).strip()
    if not re.fullmatch(r"[0-9]{6}", value):
        raise ValueError("代码必须是 6 位纯数字；指数 provider 与证券交易所不是同一概念")
    return value


def _official_date(value):
    value = str(value).strip()
    fmt = "%Y%m%d" if re.fullmatch(r"[0-9]{8}", value) else "%Y-%m-%d"
    return datetime.strptime(value, fmt).date().isoformat()


def _official_number(value, required=False):
    if pd.isna(value) or str(value).strip() in ("", "-", "--"):
        if required:
            raise RuntimeError("官方源缺少必需数值")
        return None
    number = float(str(value).replace(",", ""))
    if not math.isfinite(number):
        raise RuntimeError("官方源返回非有限数值")
    return number


def _official_get(url, params=None, referer=None):
    response = requests.get(
        url, params=params,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer or url},
        timeout=(10, 40),
    )
    response.raise_for_status()
    return response


def _official_excel(response):
    try:
        frame = pd.read_excel(BytesIO(response.content), dtype=str)
    except (ValueError, OSError) as exc:
        raise RuntimeError("官方源未返回可解析的 Excel；可能未发布或响应结构改变") from exc
    # 两种中证文件的表头空格略有差异，按完整列名去空白后匹配。
    frame.columns = [re.sub(r"\s+", "", str(c)) for c in frame.columns]
    return frame


def _official_columns(frame, names):
    missing = set(names) - set(frame.columns)
    if missing:
        raise RuntimeError("官方数据列缺失: " + ", ".join(sorted(missing)))


def _official_frame(rows, keys, source, url):
    frame = pd.DataFrame(rows)
    if frame.empty or frame.duplicated(keys).any():
        raise RuntimeError("官方数据为空或主键重复，不能当成完整快照")
    frame["source"] = source
    frame["source_url"] = url
    frame["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return frame.sort_values(keys).reset_index(drop=True)


def _official_index_members(index_code, provider, weights):
    index_code = _official_code(index_code)
    if provider not in ("csi", "cni"):
        raise ValueError("provider 必须是 csi（中证）或 cni（国证）")
    if provider == "csi":
        kind = "closeweight" if weights else "cons"
        url = ("https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/"
               f"autofile/{kind}/{index_code}{kind}.xls")
        response = _official_get(url)
        data = _official_excel(response)
        cols = ["日期Date", "指数代码IndexCode", "成份券代码ConstituentCode",
                "成份券名称ConstituentName", "交易所Exchange"]
        if weights:
            cols.append("权重(%)weight")
    else:
        url = "https://www.cnindex.com.cn/sample-detail/download-history"
        response = _official_get(url, {"indexcode": index_code})
        data = _official_excel(response)
        cols = ["日期", "样本代码", "样本简称", "权重（%）"]
    _official_columns(data, cols)
    rows = []
    for rec in data.to_dict("records"):
        if provider == "csi":
            if str(rec["指数代码IndexCode"]).zfill(6) != index_code:
                raise RuntimeError("中证返回了不同指数的数据")
            code = str(rec["成份券代码ConstituentCode"]).zfill(6)
            exchanges = {"上海证券交易所": "SH", "深圳证券交易所": "SZ", "北京证券交易所": "BJ"}
            exchange = exchanges.get(rec["交易所Exchange"])
            if exchange is None:
                raise ValueError("本端点仅支持沪深北成分，请使用相应市场的数据工具")
            row = {"date": _official_date(rec["日期Date"]), "index_code": index_code,
                   "code": _official_code(code), "name": rec["成份券名称ConstituentName"],
                   "exchange": exchange}
            weight = rec.get("权重(%)weight")
        else:
            # 国证没有交易所列；A 股文件保留六位文本。港股 00700 不能补成 000700/SZ。
            code = _official_code(rec["样本代码"])
            exchange = ("SH" if code.startswith("6") else "SZ" if code.startswith(("0", "3"))
                        else "BJ" if code.startswith(("4", "8", "92")) else None)
            if exchange is None:
                raise ValueError("国证该指数包含本端点不支持的证券类型")
            row = {"date": _official_date(rec["日期"]), "index_code": index_code,
                   "code": code, "name": rec["样本简称"], "exchange": exchange}
            weight = rec["权重（%）"]
        if weights:
            row["weight_percent"] = _official_number(weight, required=True)
        rows.append(row)
    frame = _official_frame(rows, ["date", "code", "exchange"], provider, response.url)
    if frame["date"].nunique() != 1:
        raise RuntimeError("成分文件混有多个日期，不能当作单日快照")
    if weights and (not frame.weight_percent.between(0, 100).all()
                    or not 99 <= frame.weight_percent.sum() <= 101):
        raise RuntimeError("权重范围或合计异常；可能文件残缺或不是百分数口径")
    return frame


def index_constituents(index_code, provider="csi"):
    """最近公布的沪深北成分；date 是源文件日期，不是抓取日。"""
    return _official_index_members(index_code, provider, weights=False)


def index_weights(index_code, provider="csi"):
    """最近公布的指数权重，weight_percent 单位为百分数。"""
    return _official_index_members(index_code, provider, weights=True)


def index_valuation(index_code):
    """中证近期 PE/股息率文件；不含 PB，两种股本口径不混用。"""
    index_code = _official_code(index_code)
    url = ("https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/"
           f"autofile/indicator/{index_code}indicator.xls")
    response = _official_get(url)
    data = _official_excel(response)
    mapping = {"市盈率1（总股本）P/E1": "pe_total",
               "市盈率2（计算用股本）P/E2": "pe_calculation",
               "股息率1（总股本）D/P1": "dividend_yield_total_percent",
               "股息率2（计算用股本）D/P2": "dividend_yield_calculation_percent"}
    _official_columns(data, ["日期Date", "指数代码IndexCode", *mapping])
    rows = []
    for rec in data.to_dict("records"):
        if str(rec["指数代码IndexCode"]).zfill(6) != index_code:
            raise RuntimeError("中证估值文件返回了不同指数")
        rows.append({"date": _official_date(rec["日期Date"]), "index_code": index_code,
                     **{dest: _official_number(rec[src]) for src, dest in mapping.items()}})
    return _official_frame(rows, ["date", "index_code"], "csi", response.url)


def trading_calendar(year, month):
    """深交所完整自然月日历。未发布或缺日抛错，周末调休不视为交易日。"""
    if type(year) is not int or type(month) is not int or not 1 <= month <= 12:
        raise ValueError("year/month 必须为整数，month 在 1–12 之间")
    last = calendar.monthrange(year, month)[1]
    expected = {datetime(year, month, day).date().isoformat() for day in range(1, last + 1)}
    url = "https://www.szse.cn/api/report/exchange/onepersistenthour/monthList"
    response = _official_get(url, {"month": f"{year}-{month}"})
    data = response.json().get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("深交所尚未返回该月日历；不能推断全月休市")
    rows = []
    for rec in data:
        if str(rec.get("jybz")) not in ("0", "1") or not rec.get("jyrq"):
            raise RuntimeError("深交所日历字段异常")
        rows.append({"date": _official_date(rec["jyrq"]), "is_open": str(rec["jybz"]) == "1"})
    frame = _official_frame(rows, ["date"], "szse", response.url)
    if set(frame.date) != expected:
        raise RuntimeError("日历月份错位或日期不完整，不能继续调度")
    return frame
```
<!-- official-data-core:end -->

```python
members = index_constituents("000300")
weights = index_weights("399006", provider="cni")
valuation = index_valuation("000300")
days = trading_calendar(2026, 9)
print(members[["date", "code", "name"]].head())
print(weights[["date", "code", "weight_percent"]].head())
print(valuation.tail(1))
print(days.loc[days.is_open, "date"].tolist())
```

原始端点的发现与交叉核对参考：
[AKShare 中证成分](https://github.com/akfamily/akshare/blob/main/akshare/index/index_cons.py)、
[AKShare 中证估值](https://github.com/akfamily/akshare/blob/main/akshare/index/index_stock_zh_csindex.py)、
[AKShare 国证](https://github.com/akfamily/akshare/blob/main/akshare/index/index_cni.py)、
[Qlib 交易日历](https://github.com/microsoft/qlib/blob/main/scripts/data_collector/utils.py)。
本实现直接读取官方文件/API，不调用上述项目的包装库。
