# cfpctl

> Conference deadlines, without leaving your terminal.

A terminal-first conference deadline tracker for researchers. Track deadlines, search conferences, manage your watchlist, and plan your submission strategy — all from the command line.

## Quick Start

```bash
$ cfpctl upcoming --ccf A --field ai

NAME          CCF  DEADLINE  LEFT
ICLR 2027     A    Oct 01    3d
CVPR 2027     A    Nov 10    43d
ICML 2027     A    Jan 28    122d
ACL 2027      A    Feb 15    140d
AAAI 2027     A    Aug 15    322d
NeurIPS 2026  A    May 15    passed
```

## Installation

### From source (requires Go 1.21+)

```bash
git clone https://github.com/cfpctl/cfpctl.git
cd cfpctl
make build
./bin/cfpctl version
```

### Using Docker (no Go needed)

```bash
docker run --rm -v $(pwd):/app -w /app golang:alpine \
  sh -c "go mod tidy && go build -o bin/cfpctl ."
```

## Commands

| Command | Description |
|---------|-------------|
| `cfpctl list` | List all conferences in the database |
| `cfpctl search <keyword>` | Search by name, slug, or field |
| `cfpctl show <conference>` | Show detailed conference info |
| `cfpctl upcoming` | Show upcoming deadlines |
| `cfpctl timeline` | Visual ASCII deadline timeline |
| `cfpctl plan` | Submission planning assistant |
| `cfpctl watch <conference>` | Add to your watchlist |
| `cfpctl unwatch <conference>` | Remove from watchlist |
| `cfpctl watchlist` | Show watched conferences & deadlines |
| `cfpctl calendar export` | Export deadlines to .ics calendar file |
| `cfpctl remind set/list/check` | Manage deadline reminders |
| `cfpctl validate` | Validate conference data files |
| `cfpctl update` | Update local conference database |
| `cfpctl version` | Print version info |

### Filtering

```bash
# By CCF rank
cfpctl upcoming --ccf A
cfpctl list --ccf B

# By research field
cfpctl upcoming --field ai
cfpctl upcoming --field security,software

# Combined
cfpctl upcoming --ccf A --field ai --within 90d

# Duration format: 30d, 90d, 6m, 1y
cfpctl upcoming --within 60d
```

### Conference Detail

```bash
$ cfpctl show usenix-security

USENIX SECURITY 2027
──────────────────────────────────────────────────

CCF:        A
CORE:       A*
Field:      security
Location:   TBD

Submission Cycles

  Summer 2027
    Abstract      2026-05-27
    Submission    2026-06-03
    Notification  2026-09-15

  Winter 2027
    Abstract      2026-11-05
    Submission    2026-11-12
    Notification  2027-02-15

Next Deadline:  2026-06-03 (64d 07h 21m)

Links:
  Homepage:  https://www.usenix.org/conferences/byname/108
```

### Watchlist

```bash
$ cfpctl watch iclr
✓ Watching ICLR (iclr)

$ cfpctl watchlist

CONFERENCE  EVENT            DEADLINE  LEFT
ICLR        2027 abstract    Sep 25    0d
ICLR        2027 submission  Oct 01    3d
```

## Data Format

Conference data is stored as YAML files embedded in the binary:

```yaml
- name: USENIX Security
  slug: usenix-security
  rank:
    ccf: A
    core: A*
  fields:
    - security
  homepage: https://www.usenix.org/conferences/byname/108
  cycles:
    - name: Summer
      abstract: "2026-05-27T23:59:59-12:00"
      deadline: "2026-06-03T23:59:59-12:00"
      notification: "2026-09-15"
```

All deadlines default to **AoE (UTC-12)** when no timezone is specified.

### Calendar Export

```bash
# Export watchlist deadlines
cfpctl calendar export

# Export all AI conferences with custom reminders
cfpctl calendar export --all --field ai --remind 30d,14d,7d,1d -o ai-deadlines.ics

# Export security CCF-A deadlines
cfpctl calendar export --all --ccf A --field security
```

Generates standard `.ics` files compatible with Apple Calendar, Google Calendar, Outlook, etc.

### Submission Planning

```bash
$ cfpctl plan --field ai --next 6m

📋 Submission Plan
   Filters: field=ai, next=180d

  Oct 2026
  ─────────────────────────────────────
  ◇ B    AAMAS 2027                   abstract     3d
  ○ A    ICLR 2027                    submission   3d
  ○ B    AAMAS 2027                   submission   10d

  Nov 2026
  ─────────────────────────────────────
  ◇ A    CVPR 2027                    abstract     36d
  ○ A    CVPR 2027                    submission   43d

  Jan 2027
  ─────────────────────────────────────
  ○ A    ICML 2027                    submission   122d
  ○ A    ACL 2027                     submission   140d
```

### Reminders

```bash
# Set reminders for a conference
cfpctl remind set iclr --before 30d,14d,7d,1d

# List all configured reminders
cfpctl remind list

# Check which reminders are due soon
cfpctl remind check

# Remove reminders
cfpctl remind remove iclr
```

### Data Validation

```bash
# Validate all embedded data files
cfpctl validate

# Useful in CI pipelines
cfpctl validate || exit 1
```

## Roadmap

### Next
- `cfpctl sync` — Remote data repository sync (`cfpctl-data`)
- `cfpctl recommend` — AI-powered venue recommendations
- TUI mode (Bubble Tea interactive explorer)
- goreleaser + automated releases (brew/scoop/choco)

## Contributing

Contributions welcome! Especially:
- New conference data (add YAML files to `data/`)
- Bug fixes and feature implementations
- Documentation improvements

## License

MIT
