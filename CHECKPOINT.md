# SWISH — progress checkpoint

_Last updated: 2026-10-29 19:35 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

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

- **29 Oct (late morning) — mobile fixes + model v1.1:**
  - No refresh bar: new data swaps in quietly (waits until you stop scrolling/typing, reloads with no entrance animations,
    restores page, scroll, open prop panel, filters and latest live scores via sessionStorage `swish.silent`).
  - Live scores tick up one point at a time in yellow, then back to red (`animateScore`, `.lsw.ticking`).
  - Game log fits phones: date under opponent, columns PTS/REB/AST + the market you opened (3PM/PRA hidden ≤760px);
    squad-table phone CSS no longer leaks into the nested game log (child selectors `.sqt > tbody > tr`).
  - Phones: red home button top-right of the logo bar (replaces back-to-top); logo plays once per tap (no sticky loop).
  - Clock card: logos no longer blink; flicks through every upcoming tip-off every 4s with dots.
  - Model v1.1 (both files, parity 0 mismatches on 28 Oct snapshot d5512b5): projection = per-minute rate × expected minutes;
    expected minutes = this season (0.5·last 3 + 0.5·last 10) taking over from last season after ~5 games; role change =
    this season vs last season minutes ≥5; flag `new_role` if <3 games this season. Backtest on 28 Oct: minutes error
    4.78→4.27, Brier model-only 0.2655→0.2629 (market 0.2495) — small gain, one night.
  - Props: "Expected minutes" panel + role chips; new default "Top overs" list ranked by SWISH chance of the over, with
    High (60%+) / Medium (55–60%) confidence; only overs SWISH rates ≥ the bookmaker, no warnings.

- **29 Oct (midday) — v1.2 + overs tracker + timeline:**
  - Model v1.2 (both files, parity 0): teammates OUT → minutes shortfall vs 240 among available players who've played
    this season is shared by room below 36 min (×2 same position as the absent), max +6 each, cap 40; projection scaled
    by new/old minutes; shown as the role adjustment row + "Injury boosts" list. 28 Oct backtest: boosted players' minutes
    error 3.77→3.43, overall projections ≈ unchanged (one night).
  - Results: "Top overs tracker" (ledger `overs`: High 60%+ / Medium 55–60% / Low, each graded on the over price).
  - Home: "Today's updates · UK time" timeline (07:05 / 13:50 / 14:30 early lines / 19:50 / 21:00 lines / tip-off / 01:30).
    NOTE: update.py odds windows are UTC (21:00–22:30); when UK clocks go forward in March, shift them or the cron jobs.
  - Squad tables: Min shows average (last 10) and expected tonight in blue; phone game log shows PTS/REB/AST/3PM.
  - Odds credits: UK game lines (totals/spreads) only bought when the day's budget covers 3 prop markets for every game.
    Free plan = 500/month (resets monthly, no rollover). 28 Oct run used 35, 465 left. November ≈16/day → auto picks
    PTS only on 10+ game nights, PTS+REB on ≤8. User chose PTS, REB, AST only (29 Oct) — threes/PRA no longer bought.
  - Guide doc for the user: https://claude.ai/artifact/MFN3uQH3Va3qxL8Tpc5kGE ("SWISH — how it works"); keep it updated.

- **29 Oct (afternoon) — plain-English pass:** top bar "Data updated HH:MM" + "Injury list checked · last change" (both show on
  phones in a second row); role/minutes chips explain themselves on hover/tap (`data-tip`, one floating `.tipbox`, text
  built only from the player's own logs / ESPN injury list); green "▲ +X min · teammate out" chip; Results cards redrawn
  (won/lost numbers + bar with a break-even tick, "Ahead/Behind the bookies" meter, average-miss bars); headings and
  notices rewritten in plain English across Home, Props, Games, Injuries, Results. Logo: colour sweep on tap, gentle wave
  after the ball drops, smooth ease back (no snap when the mouse leaves mid-shot).

- **29 Oct (evening) — UI session, all tested on phone/tablet/desktop, light+dark:**
  - Back-of-jersey vest avatars (team colours, official ESPN number — pipeline now saves `jersey` + team `alt` colour;
    auto mode forces a one-off full run if saved players lack jerseys). Shown in squad tables (desktop: name · Last 6
    on one line; icon-only Last 6 with a floating "Last 6" hover tag when two squads sit side by side), Last 6 panel,
    prop panel, injury cards. NO real player photos (Claude won't add them — user informed).
  - Phones: one-row top bar (↻ time pill, amber injury button, icon-only ?), home/back button, glass bottom menu with
    dividers (faint glow), page drawn edge-to-edge (viewport-fit=cover), compact squad rows, options card with lit
    Expand/Collapse buttons + state line, Best-picks tabs as a fixed grid, results tables fit, recent picks compact,
    Games cards centred (team context symmetric), headers brighten as they reach screen centre, home game list:
    city/nickname stack + HOME badge, team colours cascade down the list (3.9 s per game).
  - Injuries: one-line "New tonight" announcement; "Just in" (<2 h) glowing cards; changes list tinted by team colour;
    "ESPN: day-to-day" tag; plain tiles; next check from real schedule.
  - Tip-off clock icons; timeline shows Expected (morning) + Confirmed (~30 min pre-tip, blue) lineups.
  - Prop panel: interactive last-10 bars (oldest→latest, numbers, tap/hover tooltip; fixed reversed order bug);
    game log columns centred. Logo: tap plays once, gentle wave, smooth settle. Hoop favicon + home-screen icon.
  - Header art behind text on all pages; home court enlarged on phones/tablets; Props header = outlined tank top "10".
  - Desktop game-header gradient: softer, blurred, 19 s loop (no banding).
- Desktop home list uses the same HOME pill as mobile.
- Home header shows "(prices due 14:30/21:00 · prices coming in · no prices yet)" next to the props count while no prop has a price (`pricesDueTxt()`).
- Lineups: NBA.com projected starters were in by ~10:20 UK on 29 Oct (status "expected"); confirmed ~30 min before tip.

- **29 Oct (19:20–19:45):** Home header shows "(prices due 21:00 / 14:30)" while no prop has a line yet. Timeline status
  badges same width (100px; 92px ≤760px), text centred. Credits talk: Nov free plan ≈16/day vs ~22 needed for full
  PTS/REB/AST, so auto drops to PTS-only on busy nights. Paid 20K plan ≈ $30/mo (third-party source; check the official page).
  User decision: stay free for now; closing-line check (step 3) parked — only worth it on a paid plan or a ~3 credits/night cap.

- **29 Oct (21:40):** one-off price top-up tonight at 23:30 UK (`TOPUP_DATES` in update.py + index.html, both must match).
  Re-prices games not started (~11 credits) to catch lines posted after 21:00 (questionable players, late markets).
  Only nights listed in TOPUP_DATES get it; user to decide tomorrow whether to keep it (Nov budget ≈16 credits/day).
  Home "Props with a price" now says "with no bookmaker line tonight" once the main fetch has covered every game.

## Next steps (in order)

**TOMORROW (user agreed 29 Oct 22:47), in this order:**
A. **Minutes fix — injured players (esp. big ones).** Found 29 Oct: Dejounte Murray (NOP, ~31 min) ruled out 22:22 but
   teammates gained only ~1 min each, because available NOP players' expected minutes already summed to ~278 (>240),
   so the shortfall logic saw no room. Plan (all model changes: BOTH files, bump MODEL_VERSION, parity 0, backtest):
   1. Scale available players' expected minutes to 240 first, then share the absent player's minutes (quick; do first;
      check against tonight's graded NOP game).
   2. "With vs without" history: teammate minutes/stats in games the absent player played vs missed (this + last
      season, ≥2–3 games), fall back to step 1.
   3. Usage boost: higher per-minute PTS/AST rate when a high-usage player sits (from with/without, else small capped).
   4. Conditional re-price: after 21:00, if a 25+ min player is ruled out, re-fetch odds for that game only (~3
      credits). Replaces nightly top-ups. Tonight's one-off top-up uses TOPUP_DATES={"2026-10-29"} — remove after.
   5. Steps 2–3 tested inside the projection lab (step 0) before shipping.
B. **Update the page in place, no reload** (user asked 29 Oct 20:36): fetch new data in the background and redraw only
   what changed (times, injuries, prices, picks), like live scores. Safari currently reloads on each data update.
C. Parked, user's call: closing-line check (step 3) — only on a paid plan or tiny budget.
0. **Idea saved for later (user's call, 29 Oct): projection testing lab.** Replay last season day by day from ESPN game logs
   (project each night using only earlier games, compare with actual) to test/tune minutes, rate weighting, H2H, rest/back-
   to-backs, blowouts, recent-form decay — ~25k player-games, no Odds credits. Plan: (a) GitHub job downloads all 30 teams'
   last-season logs into the repo; (b) next session build the replay + run tests; ship only proven changes as new versions.
   Tested & NOT shipped 29 Oct: game total/spread adjustment (implied team points vs team scoring, ± blowout minutes) made
   28 Oct projections worse in all 5 variants (MAE 3.31 → 3.33–3.60). Revisit only inside the lab.
1. ~~Daily auto-start~~ DONE 29 Oct: cron-job.org (user's account, timezone Europe/London) POSTs to the GitHub API with a
   fine-grained token (indulgetv/swish only, Actions read & write; if the 90-day option was kept it expires 27 Jan 2027 —
   renew it and paste into all 4 jobs' Authorization header). Jobs: 07:05 `update-data.yml` body
   {"ref":"main","inputs":{"mode":"full"}}; 13:50, 19:50, 01:30 `live-loop.yml` body {"ref":"main"}. Tested: 204 + runs
   started. Header X-GitHub-Api-Version 2022-11-28 is deprecated, sunset 10 Mar 2028 — update the header before then.
   Loops share a concurrency group, so overlapping starts queue rather than clash.
2. ~~Check the 28 Oct picks were graded~~ DONE 29 Oct: 350/356 graded (6 pending = Gui Santos & Markkanen, not in
   box score → void on next full run). Strong 8-11 (−£31.71), all 182-168 (−£103 at £10). Brier: market 0.2497,
   SWISH 0.2514, model-only 0.2661 → model alone is worse than the market; 0.60–0.65 bucket predicted 62%, hit 48%.
   Strong losses were mostly minutes/role changes (Rollins 17 min, Reed 38, Kuminga, Shannon, Dosunmu).
   Model leans under on REB (79/47) & AST (50/39) but results went over 53%/51%. `scripts/review.py` prints all this.
   Today's ideas, in order: (a) projection = per-minute rate × expected minutes, current-season minutes weighted
   heavier; (b) cap SWISH chance / shrink edges until calibrated; (c) check the REB/AST under-lean (NB skew at .5
   lines); (d) no "strong" tag on players whose minutes changed a lot vs last season. One night = noise; don't
   change MODEL_WEIGHT yet.
3. Line movement (closing line value): a second, automatic odds fetch ~30 min before tip-off. Explained to user 29 Oct
   (credits = The Odds API free plan, 500/month, ~1 per game per market). Budget options: re-check only flagged props, or PTS only.
   Ask the user before it starts spending credits.
4. ~~Minutes/role model~~ done (v1.2, injury-based). Still to do: use NBA.com confirmed lineups (starter swaps) and usage (rate) boosts.
5. Add STL / BLK / TOV columns (data already collected).
6. After ~2 weeks of results: review accuracy vs market & calibration; only then consider raising MODEL_WEIGHT.

## How to resume
> "Continue SWISH from CHECKPOINT.md in indulgetv/swish — start at the first unfinished next step."
