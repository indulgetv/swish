# SWISH — progress checkpoint

_Last updated: 2026-10-29 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

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
  - Floating bottom tab bar (shadow + inner glow, red active tab, dark-mode contrast); back-to-top button
    (top-right under the header on phones, bottom-right on desktop); sidebar widened to 284px;
    standings "plays tonight" colours: East blue, West orange (`.side-sec.stand[data-stand]`).
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

- **Results tracking (2026-10-28):** `scripts/model.py` = Python port of the browser model (MODEL_VERSION
  stamped on every pick; `scripts/test_model_parity.py` must report 0 mismatches after any model change —
  change BOTH files). `scripts/ledger.py`: every run re-saves picks for games not started into
  `data/picks/<slate>.json` (locked once the game starts; `open*` fields keep the first line); the 07:17/14:17
  full runs grade them from ESPN game logs (void if not in the box score 10h after tip); summary in
  `data/results.json/.js` → Results page (records, profit at £10, Brier accuracy vs market, calibration,
  by market/night, recent picks). 28 Oct backfilled from pre-tip snapshots d5512b5/8f76016 (`scripts/backfill.py`).

- **Reliable updates (29 Oct 00:20):** GitHub's cron NEVER fired for this repo (0 scheduled runs ever).
  Fix: `update.py --mode auto` picks the job by UK/UTC time (full 07:00–09:00 & 14:00–14:30 if none in 3h; odds early
  14:30–16:00 and late 21:00–22:30 once each per day; otherwise light). `live-loop.yml` runs auto every 5 min for up
  to 5.8h (workflow_dispatch; backup cron 20:53). Picks are graded as soon as a game is final, in any mode.
  Site loads data with cache-busting, polls `data/stamp.json` every 60s and reloads itself on new data.
  Times shown in UK 24-hour format. Injury pill shows "checked HH:MM · newest news HH:MM".
- Lineups: NBA.com daily lineups file WORKS from GitHub (expected → confirmed); ESPN box-score starters once live.

- **Live scores in the browser (29 Oct):** `pollScores()` in index.html fetches ESPN's scoreboard every 30 s from
  10 min before a tip-off until final, and repaints only the score spots (`slot(g, kind)` / `SLOT` / `data-ls`) with
  a small bump animation — no reload. While it works, "light" data updates show the refresh bar instead of reloading.

## Next steps (in order)
1. **Make updates start every day without GitHub cron (most urgent).** The live loop started manually on 29 Oct
   00:18 runs until ~06:00 only. Set up a free external pinger (e.g. cron-job.org) that calls the GitHub API
   `POST /repos/indulgetv/swish/actions/workflows/live-loop.yml/dispatches` with body {"ref":"main"}
   at ~13:50 and ~19:50 UK daily (each loop runs 5.8h), plus ~07:05 for the morning full run. Needs a fine-grained
   GitHub token (this repo only, Actions: read & write) stored in the pinger. Walk the user through it step by step.
2. ~~Check the 28 Oct picks were graded~~ DONE 29 Oct: 350/356 graded (6 pending = Gui Santos & Markkanen, not in
   box score → void on next full run). Strong 8-11 (−£31.71), all 182-168 (−£103 at £10). Brier: market 0.2497,
   SWISH 0.2514, model-only 0.2661 → model alone is worse than the market; 0.60–0.65 bucket predicted 62%, hit 48%.
   Strong losses were mostly minutes/role changes (Rollins 17 min, Reed 38, Kuminga, Shannon, Dosunmu).
   Model leans under on REB (79/47) & AST (50/39) but results went over 53%/51%. `scripts/review.py` prints all this.
   Today's ideas, in order: (a) projection = per-minute rate × expected minutes, current-season minutes weighted
   heavier; (b) cap SWISH chance / shrink edges until calibrated; (c) check the REB/AST under-lean (NB skew at .5
   lines); (d) no "strong" tag on players whose minutes changed a lot vs last season. One night = noise; don't
   change MODEL_WEIGHT yet.
3. Line movement (closing line value): a second, small odds fetch ~30 min before tip-off — budget the credits.
4. Minutes/role model: raise teammates' projections when a starter is confirmed out (use the lineups data).
5. Add STL / BLK / TOV columns (data already collected).
6. After ~2 weeks of results: review accuracy vs market & calibration; only then consider raising MODEL_WEIGHT.

## How to resume
> "Continue SWISH from CHECKPOINT.md in indulgetv/swish — start at the first unfinished next step."
