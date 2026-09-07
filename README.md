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
- creates a Thursday 2:00 PM local-time alert and emails it when configured;
- estimates weekly points from the ESPN season baseline, opponent strength,
  and home/away status, then uses those scores to select starters;
- optionally uses Gemini to explain recent sourced injury and opportunity news,
  estimate start likelihood, and name deterministic replacement candidates;
- writes `%LOCALAPPDATA%\NFLFantasyDraftAssistant\draft-room-context.md`.

It does not automate or submit ESPN draft picks. During the draft, record picks
as ESPN announces them and keep the ESPN draft room open separately.

## Setup on another Windows computer

Download or clone this repository, open its folder, and double-click
`SETUP.cmd`. Answer the prompts; pressing Enter accepts the recommended values.
The setup installs Python 3.13 when needed, creates and reuses a persistent
`.venv`, collects optional email and Gemini settings, downloads ESPN's public player data,
validates the result, and installs the Thursday task. Git, VS Code, uv, and an
ESPN account are not required.

After setup, double-click `DRAFT.cmd` for the continuous live draft room or
`RUN.cmd` for all other tools. The draft room accepts a displayed recommendation
number or player name, automatically marks your snake-draft selections, and
recalculates after every pick. Setup, menu, and draft failures remain visible and
are logged under `%LOCALAPPDATA%\NFLFantasyDraftAssistant\logs`.

Application data stays under `%LOCALAPPDATA%\NFLFantasyDraftAssistant`. Email is
sent through the signed-in Classic Outlook desktop app, so no mail password is
requested or stored. The Gemini key is stored in the private data folder, never
in `config.toml`.
The scheduled NFL alert makes at most one Gemini request per weekly run and the
default local guard allows no more than two requests or 20,000 estimated input
tokens per day. On Google's free tier, supported-model input and output are free;
if the project quota is exhausted, Gemini returns an error and this assistant
continues with ESPN-only advice. Charges are possible only after billing is
enabled for the Google AI project. Current project quotas should be checked in
Google AI Studio because Google changes model-specific limits over time.

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

The Windows task runs every Thursday at 2:00 PM in the computer's local time. It
refreshes ESPN, writes `%LOCALAPPDATA%\NFLFantasyDraftAssistant\latest-alert.txt`,
checks bounded Google News RSS evidence and, when enabled, makes one structured
Gemini request before sending. RSS or Gemini failure falls back to ESPN-only
advice and is shown in the alert. If the computer is asleep, Windows is
configured to wake or catch up when possible. The user must be logged in.
After ESPN reports a complete regular-season schedule with every game finished,
the next scheduled run sends no alert, makes no Gemini request, and disables its
own Thursday task. Running `SETUP.cmd` for a later season installs/enables it again.

ESPN is not publishing usable 2026 weekly projections yet. Post-draft alerts
therefore divide available full-season projections into a weekly baseline and
apply a bounded fixture multiplier based on the opponent's public scoring record
and home/away status. The alert shows the neutral baseline and fixture adjustment
separately and marks missing values as `N/A`.

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

## Thursday alert and email

`SETUP.cmd` asks whether to configure email and for its recipient. Messages are
sent through the signed-in Classic Outlook desktop app, as in the UCL assistant;
no SMTP app password is needed. Choose menu option 7 to preview exactly what
Thursday's alert will contain and option 9 to inspect the task status.

Developer equivalents are:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy alert
.\.venv\Scripts\python.exe -m nflfantasy schedule-status
.\.venv\Scripts\python.exe -m nflfantasy schedule-install
```

The watchdog uses `.venv\Scripts\python.exe`, captures stdout and stderr, rejects
nonzero exits, times out after 30 minutes, and appends monthly logs. Classic
Outlook must be installed, signed in, and available to the logged-in Windows user.

## During the live draft

Double-click `DRAFT.cmd`. The current board remains open and asks directly for
each selection, so returning to the main menu is unnecessary:

```text
Overall pick #1 - draft slot 1 [YOUR PICK]; actual player selected: 1
Overall pick #2 - draft slot 2; actual player selected: DRAKE London
Overall pick #3 - draft slot 3; actual player selected: j.jefferson
```

A number selects that row from the displayed board. `mine NAME` manually marks
your selection if the draft position was not configured. Player matching ignores
case and punctuation, so variants such as `DRAKE London` and `d.london` match
Drake London. It also accepts unambiguous surname-first forms and close typos.
The prompt shows the snake-draft slot for every selection and labels
your turns as `[YOUR PICK]`. The commands `undo`, `reset`, `refresh`, `board`,
and `quit` are available at every prompt. Picks are saved immediately, and reopening
`DRAFT.cmd` resumes the same draft.

For a mock draft, enter `reset` when finished and type `RESET` to confirm.
The same action is menu option 12 in `RUN.cmd`. Reset removes recorded picks,
the derived roster, and cached draft reviews while keeping ESPN player data,
configuration, email settings, and the Gemini key.

When Gemini is enabled, completion of each full league round triggers one
strategy review. Gemini may choose a primary and three fallbacks only from the
current deterministic recommendation board; it cannot invent players or replace
the ESPN-based ranking model. Round reviews use a separate local limit of 20
requests and 100,000 estimated input tokens per day.

Developer command equivalents are:

```powershell
.\.venv\Scripts\python.exe -m nflfantasy draft
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