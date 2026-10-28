# SWISH — progress checkpoint

_Last updated: 2026-10-28 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

## Done
- `index.html` — the full SWISH dashboard, now **wired to live data** (`data/live.js`).
  Falls back to the sample slate if the file is missing, has no games, or is >36h old.
  - Players and props built from real ESPN game logs (55% season / 45% last 10, small H2H blend).
  - Prop prices are **US market prices** (FanDuel/DraftKings/BetMGM via The Odds API), labelled as such.
    Value is judged against them; users are told to check their own bookmaker's line matches.
  - Optional, collapsed "compare with your own bookmaker's price" form in each prop panel.
  - **Model safeguards** (2026-10-28): SWISH chance = 30% model + 70% no-vig market (`MODEL_WEIGHT`);
    negative-binomial curve for REB/AST/3PM; ±12% projection error added to the spread (`PROJ_ERR`);
    flags for lines far from the projection (>0.9 spreads or >40%) and players with <5 games.
    Result on the first real slate: 20 strong-value props out of 356 priced (was 213 before safeguards).
  - Real team logos (ESPN image server) everywhere, with coloured-badge fallback.
  - Animated team-colour game headers on Games & Analysis, Injuries and Home (not just Player Props).
  - Injury timing: "Posted HH:MM · Xm ago" chips, NEW badge (<6h), newest first, status bar (last/next
    check, news count), "Latest injury news" feed, injury-news counter pill in the top bar, and a prop flag
    when injury news in that game is newer than the line's fetch time.
  - Responsive: full width on ultra-wide; fixed bottom tab bar ≤960px; full player names (squad tables
    become name row + stat row ≤760px); lists >8 collapse with "Show all" on phones (news feed and Home
    injury watch on every screen). Logo bug fixed (class clash with the brand `.logo`; now `.haslogo`).
  - Games & Analysis uses live records, conference rank, games back, streak and real H2H.
  - Injuries filtered to tonight's teams; ESPN "Day-To-Day" shown as Questionable.
- `scripts/update.py` — free data pipeline (ESPN feeds for schedule, standings, injuries, rosters,
  player game logs incl. STL/BLK/TOV, head-to-head; The Odds API for US prop reference lines + UK game lines,
  with a monthly credit budget). Writes `data/live.json` and `data/live.js`.
- `.github/workflows/update-data.yml` — runs automatically (UTC = UK winter time):
  full 07:17 & 14:17; odds **early 14:37** (only games tipping before 21:30) and **main 21:07**
  (every game not started); light (scores + injuries) hourly 15:47–20:47, then **every 20 min 21:27–02:47**,
  last 03:47; plus every push to `scripts/` or the workflow. Odds runs MERGE into existing lines and stamp
  each line with `fetched`. Output log: `data/last-run.log`.
- First automated run (2026-10-28 20:05 UTC) checked: 12 games, 394 players, 0 errors.
- First odds run (manual, 2026-10-28 22:22 UTC): 1,042 prop lines, 11/12 games, 35 credits.
  Fixed: Clippers name mismatch (ESPN "LA Clippers" vs "Los Angeles Clippers").
  Odds markets now `auto`: covers every game first, adds markets (PTS→REB→AST→3PM→PRA) as budget allows.
- GitHub Pages is ON: https://indulgetv.github.io/swish/
- User has: GitHub repo `indulgetv/swish` (public), Actions write permission, secret `ODDS_API_KEY`.
- `dev/live-adapter.js` is now merged into `index.html` (kept only for reference).

## Next steps (in order)
1. **Results tracking (most important):** each morning, save every priced prop (line, prices, SWISH chance,
   market chance) and settle it against the box score. Show hit rate, profit at £10 flat, closing-line value
   and calibration on the Results page. This is how MODEL_WEIGHT gets raised (or not) based on evidence.
2. Minutes/role model: adjust projections when a teammate is confirmed out (fill-ins are not automated yet).
3. Add STL / BLK / TOV columns (data already collected; Odds API has fewer lines for these).
4. Later: confirmed starting lineups near tip-off; paid Odds API plan if more markets per game are wanted.

## How to resume
> "Continue SWISH from CHECKPOINT.md in indulgetv/swish — start at the first unfinished next step."
