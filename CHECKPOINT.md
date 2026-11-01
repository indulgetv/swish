# SWISH — checkpoint (short)

_Last updated: 2026-11-01 05:40 UK by Claude._ Full detail of every past session: `HISTORY.md` (read only when needed).
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
- Results so far (4 nights, 28–31 Oct, 31 games): 1,044 graded; strong 12–17 −£51.60; leans 400–360 −£164.88.
  Pick check (`python3 lab/check_picks.py`, 1 Nov): SWISH ≈ market (Brier .2470 vs .2467), raw model worse (.2556).
  Model slightly right when it disagrees by <5 pts, badly wrong when >10 pts — and strong picks come from big gaps.
  Best-fit model share ~5% (range −15..+25%). Overs hit 46.6% vs market's 49.7%. PTS worst market, REB ≈ market.
  Minutes: 34+ exp min over-estimated +1.8, <20 under-estimated −4.4 (needs shrink to mean). Lines moved toward model 13/42.

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
- Game moments (`gameMoment`): tip, End Q1, half, End Q3, End Q4 only if level, full-time. Desktop: sidebar "Tonight" row;
  phones/tablets: Games-page header `.ana-h[data-gh]`. Team-colour halves, frosted score card, winner blinks gold +
  confetti, loser half drains. `pollScores` every 10 s. Hidden test page: site + `#moments` (`viewMoments`).
  On refresh (`MO_BOOT`): replays only the pause you land in (quarter end/half), full-time for 20 min (`moEnd.<id>` in
  localStorage), tip-off in the first 5 min of Q1; nothing once play restarts.
- Home "Tonight's games" rows: amber pill END OF Q1 / HALF-TIME / END OF Q3 / END OF Q4 during breaks, grey FULL-TIME (· OT).
- Game jumps (`gotoGame`, all [data-goto]): un-lazies `#sections` (`.cv-all`) so content-visibility can't shift the
  target, lands under header + filter bar (`stickyTop()`), long trips jump then glide, card glows once (`.goto-hi`).
- Phones: no accidental zoom; opened items scroll into view (`revealOpened`).

## How updates run
- cron-job.org (user's account, Europe/London) POSTs to GitHub with a fine-grained token (indulgetv/swish only; may expire
  27 Jan 2027 — renew + paste into all 4 jobs). Jobs: 07:05 `update-data.yml` {"ref":"main","inputs":{"mode":"full"}};
  13:50, 19:50, 01:30 `live-loop.yml` {"ref":"main"} (5-min rounds for ~5.8 h; loops queue, never clash).
  Header X-GitHub-Api-Version 2022-11-28 sunsets 10 Mar 2028.
- GitHub's own timers in update-data.yml fire only ~1 in 5 slots, often late — best-effort backup, not our bug.
- Odds: free plan 500 credits/month, no rollover. Early prices 14:30–16:00 (games before 21:30), main 21:00–22:30,
  late re-price of ONE game when a 25+ min player is newly Out/Doubtful (max 4/night). Only PTS/REB/AST bought.
  Times in update.py are UTC — shift them when UK clocks go forward in March.
- Injuries: ESPN note beats ESPN status when it names tonight (`apply_notes`); "confirmed" after note agrees or 3 checks;
  non-injury notes (contracts, G League…) hidden from news.

## Working rules (from the user)
- Free only. Never invent odds/injuries/lineups/stats/results; label missing or stale data. No "guaranteed".
- Model change → BOTH index.html and scripts/model.py, bump MODEL_VERSION, `python3 scripts/test_model_parity.py`
  = 0 mismatches (use snapshot b8d724b, clock 2026-10-30T22:30Z — morning live.json has no props), backtest on saved
  picks (+ lab replay on both seasons), ask before shipping.
- Test phone + tablet + desktop + ultra-wide, light + dark (playwright over `python3 -m http.server`; fetch fails on file://).
  To test an old slate, set the browser clock to that slate (`page.clock.install`).
- Releases: afternoon/evening → push to branch **`pending`** (built on origin/pending); the next loop start or GitHub timer
  merges and publishes it. User may say "publish now" → merge origin/pending into main (fetch `--depth=300` first, shallow
  clones can't merge; check origin/pending really moved) and reset pending to main. Pushes to main touching `scripts/**`
  or workflows start a full update. Pushing needs the repo attached with push access (add_repo).
- Never print or store keys. Ask before spending credits, changing cron-job.org jobs or using the GitHub key.
- After each session: update CHECKPOINT.md (short!) + append details to HISTORY.md, copy CHECKPOINT.md to the project doc
  `claude/swish-checkpoint.md`, keep the guide "SWISH — how it works" (https://claude.ai/artifact/MFN3uQH3Va3qxL8Tpc5kGE,
  a Claude Doc — edit with the Docs tools) current.

## Latest (31 Oct evening, all published)
- Moments on refresh, Home break pills, 10-s live scores, lineup-due hold no longer returns after tip (both model copies,
  parity 0, no version bump — pre-tip unchanged), sidebar/game jump fix. Guide updated 1 Nov. Details in HISTORY.md.

## Next steps (in order)
1. **Model honesty (user's call, ask before shipping):** (a) big model-vs-market gap = warning, not strong pick;
   (b) shrink expected minutes toward the mean — test in lab replay on both seasons (independent of 4 nights);
   (c) show "overs hit 46.6% vs market 49.7%" on Results. Real edges = speed on news + bet365 lagging, not the model.
0. User saw moments live ("working great"). Ask if any tweaks, then remove the hidden #moments page (archived in git; ask first).
4. (Done 31 Oct: UK player props CONFIRMED not on The Odds API. Two checks, regions=uk, player_points: POR@UTA at 15:00 and
   PHI@CHA at 21:31 (40 min before tip) → no UK bookmaker returned any; 0 credits each (383 left after the night's buys).
   US prices stay the reference; site keeps telling the user to check the bet365 line. `uk-props-test.yml` kept, hand-run only.)
5. **Model lab privacy** (user wants it private): option = remove from site + `data/lab.js`, show as a private claude.ai
   page; optional private repo `swish-lab` for `lab/`. Ask which.
8. Later lab tests: is "big gap" worth holding? usage boost, usual starter benched, bench AST, back-to-backs, blowouts.
9. Later: STL/BLK/TOV columns; closing-line check only on a paid plan; after ~2 weeks review calibration vs market.
