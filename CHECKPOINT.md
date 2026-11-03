# SWISH — checkpoint (short)

_Last updated: 2026-11-03 10:00 UK by Claude._ Full detail of every past session: `HISTORY.md` (read only when needed).
Keep this file SHORT (under 9,000 characters): put session details in HISTORY.md, keep here only what the next chat needs.

## What SWISH is now
- Site: https://indulgetv.github.io/swish/ — one page, `index.html` (Home, Props, Games & Analysis, Injuries, Results).
  Loads `data/live.js` + `data/results.js` (+ `data/lab.js`); shows the sample slate if live data is missing or >36h old.
  Checks `data/stamp.json` every 20 s and refreshes in place (`refreshInPlace()`), keeping scroll/panels/filters.
- Pipeline: `scripts/update.py` (ESPN: schedule, standings, injuries, rosters, game logs, H2H; NBA.com lineups;
  The Odds API: **US** player props PTS/REB/AST + UK game lines) → `data/live.json/.js`. `--mode auto` picks the job by time.
- Picks ledger: `scripts/ledger.py` saves picks for games not started into `data/picks/<date>.json` (locked at tip),
  grades from ESPN box scores (void if absent 10 h after tip) → `data/results.json/.js` (Results page).
- Model: `scripts/model.py` = Python copy of the browser model in index.html. **MODEL_VERSION v1.8**.
  Projection = per-minute rate × expected minutes (this season 0.5·last3 + 0.5·last10, last season early on;
  absences share the gap below 240 min; NBA.com new starter pulled ⅓ of the way to starter minutes; >28 min trimmed 10%;
  missed his team's last game → × 0.925 `BACK_TRIM`). sd × 1.15; normal for PTS, negative binomial for REB/AST.
  Model's own chance → sigmoid(0.70·logit p) (`MODEL_STRETCH`, `stretch()` in both files), then
  SWISH chance = 0.3·model + 0.7·no-vig market (`MODEL_WEIGHT` 0.3 — don't change until ~1,000 graded props).
  Strong value = edge ≥ 6 pts, EV > 0, no flags. Expect ~1–3 strong picks a night.
  Flags ("On hold · reason"): back from injury (overs; missed last game + on today's report), injury doubt, lineup due
  (25+ min teammate newly out, until NBA.com confirms or the game starts — "started" counts as confirmed), few games (<5), big gap, new role, old price, injury news newer
  than the line. Players < 22 exp. min: no AST.
- Projection lab: `lab/replay.py` replays a season night by night (`--lineups`, `--dump`, `--model`); data in `lab/data/`;
  tests listed in `lab/experiments.json` → `python3 lab/build_page_data.py` → `data/lab.js` (Results → Model lab).
- Results (28–31 Oct): 1,044 graded; strong 12–17 −£51.60; leans 400–360 −£164.88.
  `lab/check_picks.py`: SWISH ≈ market, raw model worse; best-fit model share ~5%. Overs hit 46.6% vs market 49.7%.

## Site features (current UI)
- Props: filter bar (market chips All/Points/Rebounds/Assists, search, sort; tick-boxes Show last 6 / Value only /
  Hide on-hold; Expand/Collapse all). Desktop: floating glass card under the header. Phones: chips 4-up.
  PRA hidden (computed in `EXTRA`); 3PM = SWISH projection only (`PROJ_ONLY`, `lineable()` for counts).
  Best picks = top 5 Overs + top 5 Unders.
- Lineups: player chip Likely starter → Confirm ~HH:MM (last 90 min) → Confirming… (from tip−20) → green Starting ✓;
  game tag Likely lineups / Lineups confirm ~HH:MM / Lineups confirming… / Lineups confirmed / Game started / Game over.
  `LU_DUE_MIN` 90, `LU_CONFIRM_BEFORE` 20 (NBA.com confirms 15–25 min before tip; once after tip, 28 Oct).
- Injuries: nav badge = changes in last 6 h. Per team: Q/D + Out ≤48 h for regulars (≥12 min, `usualMin`);
  rest in "Older & long-term" drop-down.
- Game moments (`gameMoment`): tip, quarter ends, half, full-time; sidebar on desktop, Games header on phones. `pollScores` 10 s. Hidden test page: site + `#moments`. Details in HISTORY.md.
- Home "Tonight's games" rows: amber pill END OF Q1 / HALF-TIME / END OF Q3 / END OF Q4 during breaks, grey FULL-TIME (· OT).
- Game jumps (`gotoGame`, all [data-goto]): un-lazies `#sections` (`.cv-all`) so content-visibility can't shift the
  target, lands under header + filter bar (`stickyTop()`), long trips jump then glide, card glows once (`.goto-hi`).

## How updates run
- cron-job.org (user's account, Europe/London) POSTs to GitHub with a fine-grained token (indulgetv/swish only; may expire
  27 Jan 2027 — renew + paste into all 4 jobs). Jobs: 07:05 `update-data.yml` {"ref":"main","inputs":{"mode":"full"}};
  13:50, 19:50, 01:30 `live-loop.yml` {"ref":"main"} (5-min rounds for ~5.8 h; loops queue, never clash).
- GitHub's own timers in update-data.yml are unreliable — backup only.
- Odds credits (changed 3 Nov): `odds_budget` shares credits by games left in the month (ESPN count, 7/day estimate if it fails), minus 0.4 credit/game held for re-prices; `market_plan`: every game gets the same markets (order PTS, REB, AST), leftovers add one to the earliest games. About 2 markets a game right now, so AST mostly comes only from re-prices. `sections.odds.gameMarkets` = bought per game; page says "no price" per team.
- Odds: free plan 500 credits/month, no rollover. Early prices 14:30–16:00 (games before 21:30), main 21:00–22:30,
  late re-price of ONE game when a 25+ min player is newly Out/Doubtful (max 4/night). Only PTS/REB/AST bought.
  Times in update.py are UTC — shift them when UK clocks go forward in March.
- Injuries: ESPN note beats status when it names tonight (`apply_notes`); non-injury notes hidden.
- UK player props are NOT on The Odds API (checked 31 Oct); US prices stay the reference.

## Working rules (from the user)
- Free only. Never invent odds/injuries/lineups/stats/results; label missing or stale data. No "guaranteed".
- Model change → BOTH index.html and scripts/model.py, bump MODEL_VERSION, `python3 scripts/test_model_parity.py`
  = 0 mismatches (use snapshot b8d724b, clock 2026-10-30T22:30Z — morning live.json has no props), backtest on saved
  picks (+ lab replay on both seasons), ask before shipping.
- Test phone + tablet + desktop + ultra-wide, light + dark (playwright over `python3 -m http.server`; fetch fails on file://).
  To test an old slate, set the browser clock to that slate (`page.clock.install`).
- Releases: afternoon/evening → push to branch **`pending`** (built on origin/pending); the next loop start or GitHub timer
  merges and publishes it. User may say "publish now" → merge origin/pending into main (fetch `--depth=300` first;
  check origin/pending moved) and reset pending to main. Pushes to main touching `scripts/**`
  or workflows start a full update. Pushing needs the repo attached with push access (add_repo).
- Never print or store keys. Ask before spending credits, changing cron-job.org jobs or using the GitHub key.
- After each session: update CHECKPOINT.md (short!) + append details to HISTORY.md, copy CHECKPOINT.md to the project doc
  `claude/swish-checkpoint.md`, keep the guide "SWISH — how it works" (https://claude.ai/artifact/MFN3uQH3Va3qxL8Tpc5kGE,
  a Claude Doc — edit with the Docs tools) current.

## Latest
- 1 Nov: news alert + closing-price check + compact Model lab published (details HISTORY.md).

## Next steps (in order)
A000. Check `pending` route: live-loop's checkout is shallow, and origin/pending isn't an ancestor of main, so its merge may never succeed (no release merge since 30 Oct). 3 Nov no-games fix went straight to main.
A00. 3 Nov review of 2 Nov: 15 games, strong 0–1 −£10, leans 82–88 −£169.10; season 1,437 graded. Do next, in order:
   (1) **Injury hold too broad**: `injury_after_line` fires on any ESPN note edit (Thiero, out since 30 Oct, held all 12 MIA@LAL props; 128/266 held). Only fire on a status change; both files + parity + backtest, show the user first.
   (2) Weight review + Pacers-type minutes miss (10 out, priced players 14 min short) once REB/AST data is flowing. Top overs 46.3% vs 51.2% predicted.
   (3) Harmless: "lineMoves skipped" log on no-game days. Check the first run with the new credit split (Wed 4 Nov 21:00): ESPN range count not testable from Claude's sandbox; the log shows games to cover.
A0. 2 Nov (pending): **Injury alert** (renamed from News alert) — title + "what this is" text; also fires when a 25+ min
   player's status got worse since his team's last game (Questionable → Out) even if he missed it (`was` field in
   injuries, saved from 2 Nov). 1 Nov review: leans 32–47 −£175, Top overs 14–12 +£9; 1,173 graded → weight review due.
A. Done 1 Nov: closing-price check on Results (`clv_summary`, `clvPanel`). Game-line test: user agreed to WAIT (~15 Nov).
1. **Decided 1 Nov: no v1.9 now, stay v1.8.** Lab-only: `lab/model_gameline_test.py` (blowout spread>9 ×0.25, REB/AST ×
   (implied/115)^0.5) — tiny lab gain, none vs market (`lab/backtest_saved.py`); bundle into the next real model change.
   "Big gap = hold" rejected (strong needs a ≥20-pt gap; v1.8 re-run: those went 8–5). Re-check ~15 Nov with `lab/check_picks.py`.
2. Done 1 Nov: "Check your bookie" box, "worth it at", news alert (`newsAlarms`, `alarmHTML`). Details in HISTORY.md.
0. Moments "working great" — ask if tweaks, then remove hidden #moments page (ask first).
5. **Model lab privacy** (user wants it private): option = remove from site + `data/lab.js`, show as a private claude.ai
   page; optional private repo `swish-lab` for `lab/`. Ask which.
8. Later lab tests: usage boost (per-minute rate when a star sits), bench AST, back-to-backs.
9. Later: STL/BLK/TOV columns; ~15 Nov review calibration vs market.
