> 本文件 = 单文件版 SKILL.md 的 Layer 15 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。
> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。

## Layer 15: 可转债（V3.9.0 新增）

东财数据中心可转债全表：基本条款（评级、规模、转股起始日、到期日）+ 最新转股价 / 债价 / 正股价 / 转股价值 / 溢价率。
行情类字段由东财服务端按最新报价填入（盘中为实时价，停牌或未上市为 None）。
`status`：`upcoming` 已发行未上市 / `listed` 交易中 / `delisted` 已摘牌（`include_delisted=True` 才返回）/ `unknown` 判断不了（不猜）。
东财在赎回 / 到期公告后会提前填上摘牌日，摘牌日之前仍算 `listed`；上市日也可能提前填上，上市日之前算 `upcoming`（按北京时间判断）。
退市板块的转债（404001–404005，如 404005 普利退债）东财不填上市日和摘牌日，按交易市场 `STAS00` 判为 `delisted`。

### 15.1 自包含实现

<!-- v39-cb:start -->
```python
from datetime import datetime, timedelta, timezone

_CB_QUOTES = ("f2~01~CONVERT_STOCK_CODE~CONVERT_STOCK_PRICE,f235~10~SECURITY_CODE~TRANSFER_PRICE,"
              "f236~10~SECURITY_CODE~TRANSFER_VALUE,f2~10~SECURITY_CODE~CURRENT_BOND_PRICE,"
              "f237~10~SECURITY_CODE~TRANSFER_PREMIUM_RATIO")
_CB_COLUMNS = ["code", "name", "status", "stock_code", "stock_name", "rating", "issue_size_100m",
               "apply_date", "apply_code", "listing_date", "delist_date", "expire_date", "convert_start",
               "initial_convert_price", "convert_price", "bond_price", "stock_price", "convert_value",
               "premium_pct"]


@_v39_contract
def convertible_bonds(include_delisted=False):
    """可转债全表（东财数据中心）— 基本条款 + 最新转股价 / 债价 / 正股价 / 转股价值 / 溢价率。

    status: 'upcoming'（已发行未上市）/ 'listed'（交易中）/ 'delisted'（已摘牌，include_delisted=True 才返回）/
    'unknown'（交易市场不认识，或既没有上市日也没有申购日，不猜）。
    退市板块的转债（代码 404xxx、TRADE_MARKET=STAS00，如 404005 普利退债）东财不填上市日和摘牌日，按 delisted 处理。
    行情类字段由东财服务端按最新报价填入：盘中为实时价，停牌或未上市为 None。
    转股价值 = 100 / 转股价 × 正股价；premium_pct = 债价 / 转股价值 − 1（%）。issue_size_100m 单位亿元。
    """
    rows = _em_datacenter_strict("RPT_BOND_CB_LIST", "", "PUBLIC_START_DATE,SECURITY_CODE", "-1,1",
                                 page_size=500, max_rows=20000,
                                 extra={"quoteColumns": _CB_QUOTES, "quoteType": "0"})
    if not rows:
        raise RuntimeError("东财可转债列表为空，接口可能改了")
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()   # 按北京时间，不看本机时区
    out = []
    for r in rows:
        listing, delist = _em_day(r.get("LISTING_DATE")), _em_day(r.get("DELIST_DATE"))
        market = r.get("TRADE_MARKET")
        # 东财在发布赎回/到期公告后就会填上未来的摘牌日，摘牌日之前仍在交易；
        # 上市日同理可能提前填上，上市日之前算 upcoming
        if (delist and delist <= today) or market == "STAS00":     # STAS00 = 退市板块，已从沪深摘牌
            status = "delisted"
        elif market not in ("CNSESH", "CNSESZ"):
            status = "unknown"
        elif listing and listing <= today:
            status = "listed"
        elif listing or r.get("PUBLIC_START_DATE"):
            status = "upcoming"
        else:
            status = "unknown"
        if status == "delisted" and not include_delisted:
            continue
        out.append({"code": r["SECURITY_CODE"], "name": r.get("SECURITY_NAME_ABBR"), "status": status,
                    "stock_code": r.get("CONVERT_STOCK_CODE"), "stock_name": r.get("SECURITY_SHORT_NAME"),
                    "rating": r.get("RATING"), "issue_size_100m": _v39_num(r.get("ACTUAL_ISSUE_SCALE")),
                    "apply_date": _em_day(r.get("PUBLIC_START_DATE")), "apply_code": r.get("CORRECODE"),
                    "listing_date": listing, "delist_date": delist, "expire_date": _em_day(r.get("EXPIRE_DATE")),
                    "convert_start": _em_day(r.get("TRANSFER_START_DATE")),
                    "initial_convert_price": _v39_num(r.get("INITIAL_TRANSFER_PRICE")),
                    "convert_price": _v39_num(r.get("TRANSFER_PRICE")),
                    "bond_price": _v39_num(r.get("CURRENT_BOND_PRICE")),
                    "stock_price": _v39_num(r.get("CONVERT_STOCK_PRICE")),
                    "convert_value": _v39_num(r.get("TRANSFER_VALUE")),
                    "premium_pct": _v39_num(r.get("TRANSFER_PREMIUM_RATIO"))})
    frame = _v39_frame(out, "eastmoney", DATACENTER_URL + "?reportName=RPT_BOND_CB_LIST", _CB_COLUMNS)
    if frame.duplicated(["code"]).any():
        raise RuntimeError("东财可转债列表代码重复")
    return frame
```
<!-- v39-cb:end -->

```python
cb = convertible_bonds()
cheap = cb[(cb.status == "listed") & (cb.premium_pct < 10)].sort_values("premium_pct")
print(len(cb), cheap[["code", "name", "bond_price", "convert_value", "premium_pct"]].head())
```

---
