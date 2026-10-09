# cfpctl

> Conference deadlines, without leaving your terminal.

A terminal-first conference deadline tracker for researchers. Track deadlines, search conferences, compare venues, manage your watchlist, plan submissions, and get notified — all from the command line.

**327 conferences · 10 CCF fields · 238 acceptance rates · Multi-track deadlines**

**English** | [中文](./README.zh-CN.md)

## Quick Start

```bash
$ cfpctl upcoming --ccf A --field ai

📅 Upcoming Deadlines

NAME                            CCF  DEADLINE   LEFT
──────────────────────────────────────────────────────
ICLR 2027                       A    Sep 25     0d      ⚡
CVPR 2027 [Main]                A    Nov 16     48d
SIGMOD Round 4 [Research]       A    Oct 17     18d
WWW 2027 [Full Paper]           A    Oct 25     26d
STOC 2027                       A    Nov 02     34d
```

### Interactive TUI

Run `cfpctl` without arguments to launch the interactive explorer:

```
┌─────────────────────────────────────────────────────┐
│ 📋 cfpctl — Conference Explorer                     │
│ [/] Search  [Enter] Detail  [w] Watch  [Tab] View   │
│ [s] Sort    [f] Field Filter                        │
│                                                     │
│ ▸ ICLR                   A    3d    👁              │
│   CVPR                   A    48d                   │
│   SIGMOD                 A    18d                   │
│   NeurIPS                A    -                     │
│   USENIX Security        A    44d                   │
│                                                     │
│ 327/327 conferences  │  Sorted by: Deadline         │
└─────────────────────────────────────────────────────┘
```

## Installation

### Homebrew (macOS/Linux)

```bash
brew install yuranqiu/tap/cfpctl
```

### Scoop (Windows)

```bash
scoop bucket add yuranqiu https://github.com/yuranqiu/scoop-bucket
scoop install cfpctl
```

### From Release

Download pre-built binaries from [GitHub Releases](https://github.com/yuranqiu/cfpctl/releases).

### From Source (requires Go 1.21+)

```bash
git clone https://github.com/yuranqiu/cfpctl.git
cd cfpctl
make build
./bin/cfpctl version
```

### Using Docker

```bash
docker run --rm -v $(pwd):/app -w /app golang:alpine \
  sh -c "go mod tidy && go build -o bin/cfpctl ."
```

## Commands

| Command | Description |
|---------|-------------|
| `cfpctl` | Launch interactive TUI |
| `cfpctl list` | List all conferences |
| `cfpctl search <keyword>` | Search by name, slug, or field |
| `cfpctl show <conf>` | Show detailed info with tracks |
| `cfpctl upcoming` | Show upcoming deadlines |
| `cfpctl timeline` | Visual ASCII deadline timeline |
| `cfpctl plan` | Submission planning assistant |
| `cfpctl compare <c1> <c2>...` | Side-by-side conference comparison |
| `cfpctl stats` | Database statistics overview |
| `cfpctl diff` | Detect deadline changes since last check |
| `cfpctl watch <conf>` | Add to watchlist |
| `cfpctl unwatch <conf>` | Remove from watchlist |
| `cfpctl watchlist` | Show watched conferences |
| `cfpctl calendar export` | Export to .ics calendar file |
| `cfpctl remind set/list/check` | Manage deadline reminders |
| `cfpctl notify setup/test/status` | Configure Telegram/Webhook notifications |
| `cfpctl update` | Sync data from [cfpctl-data](https://github.com/yuranqiu/cfpctl-data) |
| `cfpctl validate` | Validate data files |
| `cfpctl version` | Print version info |

**Aliases:** `up`=upcoming, `tl`=timeline, `s`=search, `w`=watch, `wl`=watchlist

## Feature Highlights

### Multi-Track Deadlines

Many conferences have different deadlines per paper type. cfpctl shows them all:

```bash
$ cfpctl show sigmod

SIGMOD 2027
──────────────────────────────────────────────────
  Acceptance:  24.8%(250/1008 25')
  Status:      ✓ Verified against official CFP

Submission Cycles

  ▸ Research Round 4
    └─ Research Paper ← NEXT
      Abstract       2026-10-10
      Submission     2026-10-17  (18d 08h 25m)
      Notification   2027-01-19

  ▸ Industrial & Demo
    └─ Industrial Track
      Submission     2026-11-24
    └─ Demonstration
      Submission     2027-01-11

  ▸ PODS Cycle 2
    └─ PODS Paper
      Abstract       2026-12-03
      Submission     2026-12-10
```

### ARR Rolling Review

For NLP conferences using ACL Rolling Review:

```bash
$ cfpctl show acl

ACL 2027
──────────────────────────────────────────────────
  Acceptance:  18.9%(2296/12148 26')
  Submission:  🔄 ACL Rolling Review (ARR)
               https://openreview.net/group?id=aclweb.org/ACL/ARR
  Commit by:   2026-10-15, 2026-11-15, 2026-12-15
               Submit via ARR monthly; commit to ACL by Feb 15
```

### Conference Comparison

```bash
$ cfpctl compare iclr neurips cvpr

📊 Conference Comparison

                  ICLR                      NeurIPS                   CVPR
──────────────────────────────────────────────────────────────────────────────
CCF:              A                         A                         A
Acceptance:       27.4%(5355/19525 26')     24.5%(5290/21575 25')     25.4%(4089/16092 26')
Verified:         ✓ Yes                     ⚠ No                      ✓ Yes
Next Deadline:    2026-09-25 (0d)           -                         2026-11-16 (48d)
Notification:     2026-12-16                -                         2027-02-25
```

### Historical Data

Look up past deadlines for any year:

```bash
cfpctl show neurips --year 2025
cfpctl upcoming --year 2025 --field ai
```

### Statistics

```bash
$ cfpctl stats

📊 cfpctl Database Statistics

Overview
  Total conferences:  327
  Verified:           ✓ 12 (4%)
  Acceptance rates:   238
  Rolling review:     3

CCF Distribution
  A: 58   B: 130   C: 139

Upcoming Deadlines
  Next 30 days:  41 (14 CCF-A)
  Next 90 days:  85

Top Research Fields
  systems             57  ████████████████████████████
  software            48  ████████████████████████
  security            47  ███████████████████████
  ai                  42  █████████████████████
```

### Filtering

```bash
# By CCF rank
cfpctl upcoming --ccf A

# By research field
cfpctl upcoming --field ai,security

# Combined with time window
cfpctl upcoming --ccf A --field ai --within 90d

# Duration format: 30d, 90d, 6m, 1y
cfpctl upcoming --within 60d
```

### Calendar Export

```bash
# Export watchlist deadlines
cfpctl calendar export

# Export all AI conferences with custom reminders
cfpctl calendar export --all --field ai --remind 30d,14d,7d,1d -o ai-deadlines.ics
```

Generates standard `.ics` files compatible with Apple Calendar, Google Calendar, Outlook, etc.

### Notifications

```bash
# Telegram
cfpctl notify setup telegram --token <BOT_TOKEN> --chat-id <CHAT_ID>

# Webhook (Slack, Discord, custom)
cfpctl notify setup webhook --url https://hooks.slack.com/services/...

# Test & status
cfpctl notify test
cfpctl notify status
```

### Reminders

```bash
cfpctl remind set iclr --before 30d,14d,7d,1d
cfpctl remind list
cfpctl remind check
```

### Deadline Change Detection

```bash
# First run saves baseline
cfpctl diff
# ✓ Baseline saved (76 deadlines)

# After update, see what changed
cfpctl update && cfpctl diff
# ⚠ CHANGED  neurips (2027)
#     2027-05-15 → 2027-05-12
```

## Data

Conference data is maintained in a separate repository: [cfpctl-data](https://github.com/yuranqiu/cfpctl-data)

- **327 conferences** across all 10 CCF categories
- **238 acceptance rates** from official sources
- **Multi-track deadlines** for 12+ conferences
- **Historical data** preserved for all years
- **ARR rolling review** modeling for ACL/EMNLP/NAACL

Data is embedded in the binary for offline use. Run `cfpctl update` to sync the latest data from the remote repository.

### Data Format

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

All deadlines default to **AoE (UTC-12)** when no timezone is specified.

## Contributing

### Daily data updates (maintainers)

Date precision is preserved: an end-of-minute `:00`/`:59` difference alone does not rewrite an abstract or paper deadline unless the source explicitly states seconds. Real date/timezone changes still apply. New notifications without a clock in their own source row are stored as calendar dates; AoE or a global deadline policy does not invent a notification time. Existing curated notification clocks are retained when the source only repeats the same date.

`cfpctl-data` is the maintained source of truth. At **00:00 UTC / 08:00 Asia/Shanghai**, `Daily Official Data Update` checks conferences' existing official `cfp` URLs (preferred) or `homepage` URLs. It never downloads or synchronizes ccfddl; that repository was only an initial bootstrap reference.

Only official dates with explicit edition, round and track evidence that uniquely match existing records can change data. Submission deadlines require explicit time/zone evidence; notifications may retain an explicitly published calendar date. Ambiguous dates, unavailable pages, new editions and unknown tracks are reported for review without overwriting existing records. Metadata, acceptance rates, ARR information, manual tracks and history are preserved. Reliable evidence can correct verified records. Partial site failures remain visible; a run where every fetch fails exits unsuccessfully.

The parser supports date lists, tables, explicitly global deadline timezone statements, and discovery of main-conference CFP / Important Dates links on the same host. Dedicated adapters cover ICLR, AISTATS and ECCV tables and inspected editions of ASPLOS, NDSS, OSDI and NSDI. Multiple submission rounds must uniquely match existing records; NSDI's duplicate `2027` cycle names still require manual disambiguation. Deleted dates, extension arrows, conflicting dates and ambiguous tracks cannot update data automatically. If only notification evidence is uncertain, reliable submission fields may be applied while the result remains marked for review.

After validation, the workflow maintains an `auto/official-update` PR in **yuranqiu/cfpctl-data**, with before/after dates and source evidence. Changes become canonical after review and merge. Detailed JSON and Markdown reports are uploaded as artifacts. Daily updates do not overwrite this application's embedded data.

Configure the app repository's Actions secret **`CFPCTL_DATA_TOKEN`** with a fine-grained token granting **Contents: read/write** and **Pull requests: read/write** on `yuranqiu/cfpctl-data`. The default `GITHUB_TOKEN` cannot write to another repository. Keep credentials out of source files.

Local usage (Python 3.12+ and the Go version in `go.mod`):

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s scripts/tests
# Use your existing cfpctl-data checkout. Default: report only.
python scripts/update_official.py --data-dir /path/to/cfpctl-data \
  --report /tmp/official-report.json --summary /tmp/official-report.md
# Add --apply to write eligible changes; --slug limits conference selection.
go run . validate --data-dir /path/to/cfpctl-data
```

`full_refresh.py` uses the same official-site updater. `convert_ccfddl.py` is an offline historical bootstrap tool requiring explicit local `--source-dir` and `--output-dir`; it performs no network access.

Contributions welcome! Especially:
- **Conference data**: PR to [cfpctl-data](https://github.com/yuranqiu/cfpctl-data)
- **Verified deadlines**: Help verify conference deadlines against official CFPs
- **Bug fixes & features**: PR to this repository
- **Documentation improvements**

## License

MIT
