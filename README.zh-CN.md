# cfpctl

> 会议截稿日期，尽在终端之中。

面向科研人员的终端会议截稿追踪工具。查截稿、搜会议、比 venue、管关注列表、规划投稿、接收提醒 —— 全部在命令行完成。

**327 个会议 · 10 个 CCF 领域 · 238 个接受率 · 多 Track 截稿时间**

[English](./README.md) | **中文**

## 快速开始

```bash
$ cfpctl upcoming --ccf A --field ai

📅 即将到来的截稿日期

NAME                            CCF  DEADLINE   LEFT
──────────────────────────────────────────────────────
ICLR 2027                       A    Sep 25     0d      ⚡
CVPR 2027 [Main]                A    Nov 16     48d
SIGMOD Round 4 [Research]       A    Oct 17     18d
WWW 2027 [Full Paper]           A    Oct 25     26d
STOC 2027                       A    Nov 02     34d
```

### 交互式 TUI

直接运行 `cfpctl`（不带参数）启动交互式浏览器：

```
┌─────────────────────────────────────────────────────┐
│ 📋 cfpctl — 会议浏览器                               │
│ [/] 搜索  [Enter] 详情  [w] 关注  [Tab] 视图切换     │
│ [s] 排序  [f] 领域过滤                               │
│                                                     │
│ ▸ ICLR                   A    3d    👁              │
│   CVPR                   A    48d                   │
│   SIGMOD                 A    18d                   │
│   NeurIPS                A    -                     │
│   USENIX Security        A    44d                   │
│                                                     │
│ 327/327 个会议  │  排序: 截稿日期                     │
└─────────────────────────────────────────────────────┘
```

## 安装

### Homebrew (macOS/Linux)

```bash
brew install yuranqiu/tap/cfpctl
```

### Scoop (Windows)

```bash
scoop bucket add yuranqiu https://github.com/yuranqiu/scoop-bucket
scoop install cfpctl
```

### 从 Release 下载

从 [GitHub Releases](https://github.com/yuranqiu/cfpctl/releases) 下载预编译二进制文件。

### 从源码构建（需要 Go 1.21+）

```bash
git clone https://github.com/yuranqiu/cfpctl.git
cd cfpctl
make build
./bin/cfpctl version
```

### 使用 Docker

```bash
docker run --rm -v $(pwd):/app -w /app golang:alpine \
  sh -c "go mod tidy && go build -o bin/cfpctl ."
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `cfpctl` | 启动交互式 TUI |
| `cfpctl list` | 列出所有会议 |
| `cfpctl search <关键词>` | 按名称、slug 或领域搜索 |
| `cfpctl show <会议>` | 显示详细信息（含多 Track） |
| `cfpctl upcoming` | 显示即将到来的截稿日期 |
| `cfpctl timeline` | ASCII 可视化时间线 |
| `cfpctl plan` | 投稿规划助手 |
| `cfpctl compare <c1> <c2>...` | 多会议并排对比 |
| `cfpctl stats` | 数据库统计概览 |
| `cfpctl diff` | 检测截稿日期变更 |
| `cfpctl watch <会议>` | 添加到关注列表 |
| `cfpctl unwatch <会议>` | 取消关注 |
| `cfpctl watchlist` | 查看关注列表 |
| `cfpctl calendar export` | 导出 .ics 日历文件 |
| `cfpctl remind set/list/check` | 管理截稿提醒 |
| `cfpctl notify setup/test/status` | 配置 Telegram/Webhook 通知 |
| `cfpctl update` | 从 [cfpctl-data](https://github.com/yuranqiu/cfpctl-data) 同步数据 |
| `cfpctl validate` | 校验数据文件 |
| `cfpctl version` | 打印版本信息 |

**快捷别名：** `up`=upcoming, `tl`=timeline, `s`=search, `w`=watch, `wl`=watchlist

## 功能亮点

### 多 Track 截稿时间

很多会议的不同论文类型有不同的截稿日期，cfpctl 全部展示：

```bash
$ cfpctl show sigmod

SIGMOD 2027
──────────────────────────────────────────────────
  接受率:     24.8%(250/1008 25')
  状态:       ✓ 已对照官方 CFP 验证

投稿周期

  ▸ Research Round 4
    └─ Research Paper ← 最近
      摘要截止       2026-10-10
      全文截止       2026-10-17  (18天 08时 25分)
      通知日期       2027-01-19

  ▸ Industrial & Demo
    └─ Industrial Track
      全文截止       2026-11-24
    └─ Demonstration
      全文截止       2027-01-11

  ▸ PODS Cycle 2
    └─ PODS Paper
      摘要截止       2026-12-03
      全文截止       2026-12-10
```

### ARR 滚动审稿

针对使用 ACL Rolling Review 的 NLP 会议：

```bash
$ cfpctl show acl

ACL 2027
──────────────────────────────────────────────────
  接受率:     18.9%(2296/12148 26')
  投稿方式:   🔄 ACL Rolling Review (ARR)
               https://openreview.net/group?id=aclweb.org/ACL/ARR
  Commit 截止: 2026-10-15, 2026-11-15, 2026-12-15
               通过 ARR 每月提交；ACL 主会需在 2月15日前 commit
```

### 会议对比

```bash
$ cfpctl compare iclr neurips cvpr

📊 会议对比

                  ICLR                      NeurIPS                   CVPR
──────────────────────────────────────────────────────────────────────────────
CCF:              A                         A                         A
接受率:           27.4%(5355/19525 26')     24.5%(5290/21575 25')     25.4%(4089/16092 26')
已验证:           ✓ 是                      ⚠ 否                      ✓ 是
下次截稿:         2026-09-25 (0天)          -                         2026-11-16 (48天)
通知日期:         2026-12-16                -                         2027-02-25
```

### 历史数据查询

查看任意年份的历史截稿日期：

```bash
cfpctl show neurips --year 2025      # NeurIPS 2025 的截稿信息
cfpctl upcoming --year 2025 --field ai  # 2025 年所有 AI 会议截稿
```

### 数据统计

```bash
$ cfpctl stats

📊 cfpctl 数据库统计

概览
  会议总数:       327
  已验证:         ✓ 12 (4%)
  接受率数据:     238
  滚动审稿:       3

CCF 分布
  A: 58   B: 130   C: 139

即将到来的截稿
  未来 30 天:  41 个 (14 个 CCF-A)
  未来 90 天:  85 个

热门研究领域
  systems             57  ████████████████████████████
  software            48  ████████████████████████
  security            47  ███████████████████████
  ai                  42  █████████████████████
```

### 筛选过滤

```bash
# 按 CCF 等级
cfpctl upcoming --ccf A

# 按研究领域
cfpctl upcoming --field ai,security

# 组合筛选 + 时间窗口
cfpctl upcoming --ccf A --field ai --within 90d

# 时间格式: 30d, 90d, 6m, 1y
cfpctl upcoming --within 60d
```

### 日历导出

```bash
# 导出关注列表的截稿日期
cfpctl calendar export

# 导出所有 AI 会议，自定义提醒
cfpctl calendar export --all --field ai --remind 30d,14d,7d,1d -o ai-deadlines.ics
```

生成标准 `.ics` 文件，兼容 Apple Calendar、Google Calendar、Outlook 等。

### 通知推送

```bash
# Telegram 机器人
cfpctl notify setup telegram --token <BOT_TOKEN> --chat-id <CHAT_ID>

# Webhook（Slack、Discord、自定义）
cfpctl notify setup webhook --url https://hooks.slack.com/services/...

# 测试 & 查看状态
cfpctl notify test
cfpctl notify status
```

### 截稿提醒

```bash
cfpctl remind set iclr --before 30d,14d,7d,1d
cfpctl remind list
cfpctl remind check
```

### 截稿变更检测

```bash
# 首次运行保存基线
cfpctl diff
# ✓ 基线已保存 (76 个截稿日期)

# 更新后查看变更
cfpctl update && cfpctl diff
# ⚠ 变更  neurips (2027)
#     2027-05-15 → 2027-05-12
```

## 数据

会议数据维护在独立仓库：[cfpctl-data](https://github.com/yuranqiu/cfpctl-data)

- **327 个会议**，覆盖 CCF 全部 10 个学科领域
- **238 个接受率**，来源于官方数据
- **多 Track 截稿**，12+ 个会议有细分论文类型截止时间
- **历史数据**，保留所有年份的截稿记录
- **ARR 滚动审稿**，ACL/EMNLP/NAACL 支持月度 commitment window

数据嵌入在二进制文件中，支持离线使用。运行 `cfpctl update` 可从远程仓库同步最新数据。

### 数据格式

```yaml
- name: USENIX Security
  slug: usenix-security
  rank:
    ccf: A
    core: A*
  fields: [security]
  homepage: https://www.usenix.org/conference/usenixsecurity27/call-for-papers
  verified: true
  accept_rate: "12.0%(362/3028 26')"
  cycles:
    - name: Cycle 1
      tracks:
        - name: Paper (incl. SoK)
          abstract: "2026-08-18T23:59:59-12:00"
          deadline: "2026-08-25T23:59:59-12:00"
          notification: "2026-12-03"
```

未指定时区时默认使用 **AoE (UTC-12)**。

### 每日数据更新（维护者）

日期精度处理：摘要和全文截止时间仅有同一分钟内 `:00` / `:59` 差异时保留原值，除非官网明确公布秒数；真实日期或时区变化仍会更新。新通知记录若所在原文没有明确时刻，只保存日历日期，不用 AoE 或全局截止时间声明推定通知时刻。官网只重复相同日期时，已有人工维护的通知时刻会保留。

`cfpctl-data` 是唯一维护的数据基准。`Daily Official Data Update` 每天北京时间 **08:00（00:00 UTC）**读取该仓库，从各会议现有 `cfp`（优先）或 `homepage` 官方页面检查截止日期。日更不读取、下载或同步 ccfddl；它仅作为最初建库时的参考。

官网解析结果必须明确对应会议年份、投稿轮次、Track，投稿截止时间还须有明确时间/时区证据，才能修改现有记录。通知日期允许保留官网仅公布的日历日期。无法匹配、网页不可访问或日期有歧义时保留原值并在报告中标注；不删会议、历史、人工 Track、接受率和 ARR 信息。新届次或未知 Track 留待人工核对。部分站点失败不会丢失其他会议的可靠结果，全部抓取失败则任务失败。`verified` 不阻止有明确官网证据的日期修正。

解析器支持日期列表、表格、明确适用于全部截止时间的时区声明，以及同站主会 CFP / Important Dates 链接发现；另有 ICLR、AISTATS、ECCV 表格和 ASPLOS、NDSS、OSDI、NSDI 特定届次适配。多轮投稿必须唯一匹配现有轮次，NSDI 中重名的 `2027` 轮次仍需人工消歧。划线旧日期、延期箭头、冲突日期和无法区分主会的 Track 不会自动写入。仅通知日期不确定而投稿截止日期可靠时，报告保留待核查状态，并允许采用可靠字段。

任务校验数据后在 **yuranqiu/cfpctl-data** 创建或更新 `auto/official-update` PR，包含日期前后对照和官网证据。合并 PR 后才能成为正式更新。JSON 详细报告和 Markdown 摘要作为 Actions 附件保留。程序仓库的内嵌数据不会被日更覆盖。

首次启用需在本程序仓库配置 Actions secret **`CFPCTL_DATA_TOKEN`**，使用对 `yuranqiu/cfpctl-data` 有 **Contents: read/write** 和 **Pull requests: read/write** 权限的细粒度令牌；默认 `GITHUB_TOKEN` 不能写另一个仓库。不要把令牌写入代码。

本地复现（Python 3.12+，Go 版本见 `go.mod`）：

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s scripts/tests
# 先克隆你维护的 cfpctl-data，以下默认只生成报告、不修改数据
python scripts/update_official.py --data-dir /path/to/cfpctl-data \
  --report /tmp/official-report.json --summary /tmp/official-report.md
# 加 --apply 才写入有明确官网证据且能匹配的修改；--slug 可限定会议
# python scripts/update_official.py ... --apply --slug usenix-security
go run . validate --data-dir /path/to/cfpctl-data
```

`full_refresh.py` 使用同一官网更新入口。旧 `convert_ccfddl.py` 仅保留离线首次导入用途，必须明确提供本地 `--source-dir` 和 `--output-dir`，不会访问网络。

## 参与贡献

欢迎贡献！特别是：
- **会议数据**：向 [cfpctl-data](https://github.com/yuranqiu/cfpctl-data) 提交 PR
- **验证截稿日期**：帮助对照官方 CFP 验证会议截稿时间
- **Bug 修复与新功能**：向本仓库提交 PR
- **文档改进**

## 许可证

MIT
