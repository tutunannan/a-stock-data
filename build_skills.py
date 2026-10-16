# -*- coding: utf-8 -*-
"""把根 SKILL.md（单文件版）拆分为 skills/a-stock-data/ 渐进披露形态。

按 H2 标题自动定位章节，不依赖行号，根 SKILL.md 版本更新后直接重跑本脚本即可。
代码块零改动，纯切片 + 少量标注；对账（fence / marker / 内容守恒）跑完自动输出。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "SKILL.md"
OUT = ROOT / "skills" / "a-stock-data"
REF = OUT / "references"

lines = SRC.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def sl(a, b):  # 1-based inclusive
    return lines[a - 1 : b]


def find(pred, start=0):
    """返回首个满足条件的 1-based 行号，找不到则报错。"""
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i + 1
    raise LookupError("锚点未找到: %r (from line %d)" % (pred, start))


def h2(title_prefix):
    """定位 `## <title_prefix>` 标题行。"""
    pat = re.compile(r"^## " + re.escape(title_prefix))
    return find(lambda l: pat.match(l))


def h2_all():
    """[(行号, 标题), ...] 全部 H2。"""
    return [(i + 1, l[3:]) for i, l in enumerate(lines) if l.startswith("## ")]


# ── 全局锚点 ────────────────────────────────────────────────────────
VER = re.search(r"^version: (.+)$", "\n".join(lines[0:8]), re.M).group(1)
L_HOME = h2("端点路由速查")
L_GUARD = h2("数据源优先级 & 东财防封")
L_ACT = h2("When to Activate")
L_PRE = h2("Prerequisites")
L_FAQ = h2("FAQ")
L_INSTALL = h2("安装说明")

layer_heads = {}  # n -> (标题行号, 标题)
for ln_no, title in h2_all():
    m = re.match(r"^Layer (\d+):", title)
    if m:
        layer_heads[int(m.group(1))] = (ln_no, title)
assert sorted(layer_heads) == list(range(1, 16)), layer_heads.keys()

SLUG = {1: "quotes", 2: "reports", 3: "signals", 4: "funds-chips", 5: "news",
        6: "basics", 7: "announcements", 8: "limit-up", 9: "options",
        10: "sentiment", 11: "macro", 12: "index", 13: "futures",
        14: "events", 15: "convertible"}
FILE_OF_LAYER = {n: f"layer-{n:02d}-{SLUG[n]}.md" for n in SLUG}

# 层区间 = 本层标题行 → 下一个 H2 前
h2_lines = [n for n, _ in h2_all()] + [len(lines) + 1]
def section(start_line):
    """标题行号 → [start, next H2 - 1]，去掉尾部空行。"""
    end = min(x for x in h2_lines if x > start_line) - 1
    body = sl(start_line, end)
    while body and not body[-1].strip():
        body.pop()
    return body

# ── 写 references ──────────────────────────────────────────────────
REF.mkdir(parents=True, exist_ok=True)

LAYER_HEADER = (
    "> 本文件 = 单文件版 SKILL.md 的 Layer {n} 章节，§ 编号与原文一致；跨层 § 引用与文件的对应关系见主 SKILL.md「端点路由速查」。\n"
    "> 依赖：东财端点须先执行 `references/common.md` 的共用 helper（`em_get` / `EM_SESSION` / `norm_ticker` 等）；"
    "V3.9.0 及之后新增的端点另需其中的 `V39_RETRY_SESSION`。\n\n"
)
for n, (ln_no, _t) in layer_heads.items():
    (REF / FILE_OF_LAYER[n]).write_text(
        LAYER_HEADER.format(n=n) + "\n".join(section(ln_no)) + "\n", encoding="utf-8")

# common.md = Prerequisites
(REF / "common.md").write_text(
    "> 本文件 = 单文件版 SKILL.md 的 Prerequisites 章节：依赖安装 + 全部共用 helper"
    "（`tdx_client` / `get_prefix` / `norm_ticker` / `to_joinquant` / `em_get` / `V39_RETRY_SESSION` 等）。\n"
    "> 执行任何东财端点或 V3.9.0+ 新端点前，先执行本文件的对应代码块。\n\n"
    + "\n".join(section(L_PRE)) + "\n", encoding="utf-8")

# valuation.md = 估值计算公式 + 完整调研流程（中间的「完整调研流程」是独立 H2，须跨过）
def span(a_line, b_line):
    """[a_line, b_line) 区间，去尾部空行。"""
    body = sl(a_line, b_line - 1)
    while body and not body[-1].strip():
        body.pop()
    return body

L_VAL = h2("估值计算公式")
(REF / "valuation.md").write_text(
    "> 本文件 = 单文件版 SKILL.md 的「估值计算公式」+「完整调研流程」章节。\n\n"
    + "\n".join(span(L_VAL, h2("官方两融与北交所行情备胎"))) + "\n", encoding="utf-8")

# backups.md = 官方备胎 + 34 源详表 + 备用源速查（「数据源优先级」「备用源速查」是独立 H2，须跨过）
#             + 封禁案例（自防封节移入）
A_BACKUPS = h2("官方两融与北交所行情备胎")
backups = span(A_BACKUPS, L_FAQ)                  # 含官方备胎 / 数据源优先级 / 备用源速查
L_SPEEDY = find(lambda l: l.startswith("## 备用源速查"), A_BACKUPS - 1)
idx = L_SPEEDY - A_BACKUPS                        # 区间内偏移
L_CASE = find(lambda l: l.startswith("### ⚠️ 实测封禁案例"), L_GUARD - 1)
L_RULES = find(lambda l: l.startswith("### 防封铁律"), L_GUARD - 1)
case = sl(L_CASE, L_RULES - 1)
backups = (backups[:idx] + ["", "## 附：东财实测封禁案例与降级路径（自防封节移入）", ""]
           + case + [""] + backups[idx:])
(REF / "backups.md").write_text(
    "> 本文件汇集：官方两融与北交所行情备胎、34 个数据源详表、备用源速查 & 降级策略、"
    "东财实测封禁案例与降级路径（自原「数据源优先级 & 东财防封」节移入）。\n"
    "> 官方两融 / 北交所备胎依赖 `references/layer-12-index.md` 的 §12 helper，先执行它。\n\n"
    + "\n".join(backups) + "\n", encoding="utf-8")

# faq.md = FAQ + 安装说明（剔除文末仓库链接行，主文件头部已有）
install = section(L_INSTALL)
if install and install[-1].startswith("> 📦 https://github.com"):
    install.pop()
(REF / "faq.md").write_text(
    "> 本文件 = 单文件版 SKILL.md 的 FAQ + 安装说明章节。\n\n"
    + "\n".join(section(L_FAQ)) + "\n\n"
    + "> 下面的安装说明针对**单文件版**（仓库根部 SKILL.md）；本目录形态的安装见主 SKILL.md「使用方式」。\n\n"
    + "\n".join(install) + "\n", encoding="utf-8")

# ── 主 SKILL.md ────────────────────────────────────────────────────
DESC = (
    "当任务需要写代码实际获取A股及相关市场数据时使用——行情/K线/逐笔（腾讯日周月前后复权+分钟线+当日逐笔、"
    "通达信官网盘后包）、研报（东财+新浪+同花顺+iwencai）、信号（热点/北向/龙虎榜/解禁/行业/板块资金流）、"
    "资金面（融资融券/大宗/股东户数/分红/资金流/ETF份额/筹码分布）、新闻（财联社/东财/华尔街见闻/新闻联播）、"
    "财务三表/F10/估值历史/ST名单、公告（巨潮）、打板（涨停池/连板/炸板率/监控池/异动）、ETF期权、"
    "舆情互动（互动易/上证e互动/热榜）、复权因子、申万行业变迁、宏观与利率（社融/PMI/中债收益率曲线/"
    "回购定盘利率/LPR/全球宏观日历）、指数成分/权重/估值/交易日历、期货与大宗商品（五家期货交易所日行情/"
    "商品与股指期权/持仓排名/期货日K/实时期货/A50/上海金）、事件驱动（业绩预告/机构调研/增减持/回购/"
    "股权质押/新股申购）、可转债等真实数据。87端点·34来源，内嵌全部可运行代码；优先腾讯/交易所官方等"
    "不封IP源，东财内置限流防封，主源被封可查备用源降级。A股概念解释、投资观点讨论等无需取数的话题不要加载本skill。"
)
assert len(DESC) < 1024, len(DESC)

# 头部：仓库链接 3 行 + 标题 + 简介（标题行起连续取）
L_HEAD = find(lambda l: l.startswith("> 📦 项目主页"))
L_TITLE = find(lambda l: l.startswith("# A股全栈数据工具包"))
head = sl(L_HEAD, L_HEAD + 2) + ["", lines[L_TITLE - 1], "", lines[L_TITLE + 1]]

# 能力树 = 「**使用方式：**」行后的第一个代码块
L_USAGE = find(lambda l: l.startswith("**使用方式：**"))
L_TREE = find(lambda l: l.strip() == "```", L_USAGE)
tree_depth, tree_end = 1, L_TREE
while tree_depth:
    tree_end += 1
    if lines[tree_end - 1].startswith("```"):
        tree_depth -= 1
tree = sl(L_TREE, tree_end)

# 路由表加「文件」列
def route_file(sec):
    sec = sec.strip()
    m = re.match(r"^(\d+)\.", sec)
    if m:
        return FILE_OF_LAYER[int(m.group(1))]
    return {"前置": "common.md", "官方备胎扩展": "backups.md",
            "备用源速查": "backups.md", "估值公式": "valuation.md"}.get(sec, "")

table_out = []
for ln in sl(L_HOME, L_GUARD - 1):
    if ln.startswith("| § | 函数"):
        table_out.append("| § | 函数 | 拿什么 | 源 / 文件 |")
    elif re.match(r"^\|---+", ln):
        table_out.append(ln + "------|")
    elif ln.startswith("| "):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        f = route_file(cells[0]) if cells else ""
        table_out.append(ln + f" {f} |" if f else ln)
    else:
        table_out.append(ln)

# 防封节：优先级表 / 独有清单 / 阈值表 / 铁律 / em_get 原文保留，案例移 backups.md
L_RULES = find(lambda l: l.startswith("### 防封铁律"), L_GUARD - 1)
L_EM = find(lambda l: l.startswith("### 已内置限流"), L_GUARD - 1)
guard = (sl(L_GUARD, find(lambda l: l.startswith("### ⚠️ 实测封禁案例"), L_GUARD - 1) - 1)
         + sl(L_RULES, L_EM - 1) + ["", "> ⚠️ 实测有 **IP 级 20+ 小时封禁**的真实案例"
         "（10 线程并发、1 小时 45000+ 请求、不走 `em_get()`），完整记录与东财各端点的降级路径"
         "见 `references/backups.md`。", ""]
         + [l.replace("「共用 helper」代码块", "「共用 helper」代码块（`references/common.md`）")
            for l in section(L_EM)])

act = section(L_ACT)
while act and act[-1].strip() == "---":
    act.pop()

main = "\n".join(
    ["---", "name: a-stock-data", f"description: {DESC}", "origin: custom",
     f"version: {VER}", "---", ""]
    + head + ["",
              "> 版本历史与历次实测记录见仓库 [CHANGELOG.md]"
              "(https://github.com/simonlin1212/a-stock-data/blob/main/CHANGELOG.md)；"
              "本目录与仓库根部单文件 SKILL.md 内容同源（本目录为渐进披露拆分形态）。", ""]
    + ["## 使用方式与文件结构", "",
       "将本目录整体放入 `~/.claude/skills/a-stock-data/`（含 `references/`），Claude Code 自动识别。",
       "",
       "| 文件 | 内容 | 何时读 |", "|---|---|---|",
       "| `SKILL.md`（本文件） | 能力树、端点路由、数据源优先级与防封铁律 | 激活即载 |",
       "| `references/common.md` | 依赖安装 + 全部共用 helper（`norm_ticker`/`em_get`/`V39_RETRY_SESSION`/`tdx_client`…） | 用任何东财端点或 V3.9.0+ 端点前 |",
       "| `references/layer-01…15-*.md` | 十五个数据层，§ 编号与单文件版一致 | 按路由表选层后 |",
       "| `references/backups.md` | 官方两融/北交所备胎、封禁案例、34 源详表、备用源速查 | 主源被封/降级/交叉验证时 |",
       "| `references/valuation.md` | 估值公式 + 完整调研流程 | 做估值/深度调研时 |",
       "| `references/faq.md` | FAQ + 安装说明 | 疑难时 |", ""]
    + tree + [""] + table_out + [""] + guard + [""] + act)
(OUT / "SKILL.md").write_text(main + "\n", encoding="utf-8")

# ── 对账 ───────────────────────────────────────────────────────────
def fences(path):
    return sum(1 for l in path.read_text(encoding="utf-8").split("\n") if l.startswith("```"))

MARK = re.compile(r"<!--\s*(v[0-9a-z-]+(?::start|:end)?)[^>]*-->")

out_files = [OUT / "SKILL.md"] + sorted(REF.glob("*.md"))
src_text = "\n".join(lines)
print(f"版本 {VER}；文件数 {len(out_files)} (SKILL.md + {len(out_files) - 1} references)")
for p in out_files:
    t = p.read_text(encoding="utf-8")
    print(f"  {p.relative_to(OUT)}: {len(t.splitlines())} 行, {fences(p)} fence, {len(MARK.findall(t))} marker")
print("fence: 原 %d → 拆分后 %d" % (fences(SRC), sum(fences(p) for p in out_files)))
src_m, out_m = sorted(MARK.findall(src_text)), sorted(m for p in out_files for m in MARK.findall(p.read_text(encoding="utf-8")))
print(f"marker: 原 {len(src_m)} → 拆分后 {len(out_m)}；集合一致: {src_m == out_m}")
print(f"description 长度: {len(DESC)}")
