# NFL Fantasy Draft Assistant

Local ESPN fantasy-football draft assistant for Windows. It builds an initial
consensus board before a league exists, updates recommendations after every live
pick, and writes one self-contained Markdown file for discussing the draft with
an AI agent.

## What it does

- downloads the public ESPN fantasy player pool without requiring an ESPN login;
- uses ESPN ADP as the preseason consensus signal and full-season projections
  when ESPN publishes enough of them for a reliable pool;
- ranks players by value over positional replacement, roster need, ADP, and injury status;
- records every selection locally and recalculates after each pick;
- supports an unknown draft order now; set `draft_position` later;
- sends the current draft report by email only when explicitly requested;
- writes `%LOCALAPPDATA%\NFLFantasyDraftAssistant\draft-room-context.md`.

It does not automate or submit ESPN draft picks. During the draft, record picks
as ESPN announces them and keep the ESPN draft room open separately.

## Setup on another Windows computer

Download or clone this repository, open its folder, and double-click
`SETUP.cmd`. Answer the prompts; pressing Enter accepts the recommended values.
The setup installs Python 3.13 when needed, creates the private local
configuration, downloads ESPN's public player data, and validates the result.

After setup, double-click `RUN.cmd`. Its numbered menu handles refreshes, draft
recommendations, recording picks, building the post-draft roster, expected-point
lineups, and manual email reports. No command-line knowledge is required.

Application data and mail credentials stay under
`%LOCALAPPDATA%\NFLFantasyDraftAssistant` and are never stored in this repository.

## Developer setup

```powershell
Set-Location "Fantasy NFL"
uv python install 3.13
uv venv --python 3.13 .venv
uv pip install --python .\.venv\Scripts\python.exe -e .
.\.venv\Scripts\python.exe -m nflfantasy setup
.\.venv\Scripts\python.exe -m nflfantasy doctor
```

Runtime data is private and stored under:

```text
%LOCALAPPDATA%\NFLFantasyDraftAssistant
```

Edit `config.toml` there when the ESPN league settings are known. The current
defaults are the confirmed 14-team, head-to-head PPR snake draft with ESPN's
standard roster: QB, two RB, two WR, TE, FLEX, D/ST, K, and seven bench spots.
The draft position remains unknown until ESPN assigns it. ESPN league or account
credentials are neither requested nor stored; picks and roster ownership remain
manual.

The current model understands `ppr`, `half`, and `standard` as labels for the
league context. ESPN ADP remains the primary signal until complete projections
for the configured season are available. Before the draft, verify the exact
ESPN scoring rules because bonuses, superflex, keepers, and custom scoring can
materially change rankings.

## Post-draft recommendations

During the draft, mark your own selections when prompted. After the draft, choose
menu option 5 to build the roster from those picks and option 6 to recommend the
starting lineup by ESPN full-season expected points. Players without trustworthy
projections are listed explicitly instead of receiving invented estimates.

ESPN is not publishing usable 2026 weekly projections yet. Scheduled lineup
emails are therefore disabled. Once weekly projection coverage is available, the
intended schedule is Thursday evening before the first game and Sunday morning
before the main slate; there is no useful reason to send recurring preseason
alerts.

## Before the draft

Refresh ESPN and inspect the initial board:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy refresh
.\.venv\Scripts\python.exe -m nflfantasy board --limit 30
.\.venv\Scripts\python.exe -m nflfantasy dossier
```

Open the generated `draft-room-context.md` or attach it to another agent. It
contains league settings, source freshness, tiers, current recommendations,
recorded picks, roster construction, risks, and a ready-made discussion prompt.

## On-demand email

There is no recurring alert schedule. To email the current report manually, set
`smtp_host`, `sender`, and `recipient` under `[email]` in `config.toml`, then set
the mail account credentials only in the current environment:

```powershell
$env:NFLFANTASY_SMTP_USERNAME = "your-mail-account"
$env:NFLFANTASY_SMTP_PASSWORD = "your-app-password"
.\.venv\Scripts\python.exe -m nflfantasy email
```

The command regenerates the dossier and sends it as a Markdown attachment. SMTP
credentials are unrelated to ESPN and are never written to the application data.

## During the live draft

Find and record picks as they happen:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy search "Justin Jefferson"
.\.venv\Scripts\python.exe -m nflfantasy pick "Justin Jefferson"
.\.venv\Scripts\python.exe -m nflfantasy pick "Jahmyr Gibbs" --mine
```

Each `pick` prints the next ten recommendations and rewrites the dossier. Player
IDs from `search` can be used instead of names when names are ambiguous.

If `my_team` is configured, this also marks your selection automatically:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy pick "Jahmyr Gibbs" --team 4
```

Corrections:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy undo
.\.venv\Scripts\python.exe -m nflfantasy reset --yes
```

## Data limitations

The public ESPN endpoint is unofficial and may change. `refresh --input FILE`
can parse a saved ESPN player JSON response if live access changes. ADP is a
market estimate, not a forecast; late injuries, depth-chart changes, suspensions,
rookie roles, keeper rules, and your league's scoring must be checked near draft time.

## Developer validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src tests
```