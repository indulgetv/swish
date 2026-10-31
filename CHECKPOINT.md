# SWISH — checkpoint (short)

_Last updated: 2026-10-31 09:50 UK by Claude._ Full detail of every past session: `HISTORY.md` (read only when needed).
Keep this file SHORT (aim < 9,000 characters): put session details in HISTORY.md, keep here only what the next chat needs.

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
  absences share the gap below 240 min; NBA.com new starter pulled ⅓ of the way to starter minutes; >28 min trimmed 10%);
  sd × 1.15; normal curve for PTS, negative binomial for REB/AST. SWISH chance = 0.3·model + 0.7·no-vig market
  (`MODEL_WEIGHT` 0.3 — don't change until ~1,000 graded props). Strong value = edge ≥ 6 pts, EV > 0, no flags.
  v1.7: missed his team's last game → expected minutes × 0.925 (`BACK_TRIM`).
  v1.8: model's own chance → sigmoid(0.70·logit p) (`MODEL_STRETCH`, function `stretch()` in both files) before the blend.
  Flags ("On hold · reason"): back from injury (overs; missed last game + on today's report), injury doubt, lineup due (25+ min teammate newly out, until NBA.com confirms), few games (<5),
  big gap (line far from projection), new role, old price, injury news newer than the line. Players < 22 exp. min: no AST.
- Projection lab: `lab/replay.py` replays a season night by night (`--lineups`, `--dump`, `--model`); data in `lab/data/`;
  tests listed in `lab/experiments.json` → `python3 lab/build_page_data.py` → `data/lab.js` (Results → Model lab).
- Results so far (3 nights, 28–30 Oct): 798 graded; strong 11–17, −£60.53 at £10. Tiny sample.
  30 Oct: all 173–166, won £1,474 / lost £1,660 = −£186; strong 3–5 = −£18.82; overs 64–74 −£177, unders 109–92 −£9.
  3 Naji Marshall props pending (not in box score; void ~10:00 if still missing).

## How updates run
- cron-job.org (user's account, Europe/London) POSTs to GitHub with a fine-grained token (indulgetv/swish only; may expire
  27 Jan 2027 — renew + paste into all 4 jobs). Jobs: 07:05 `update-data.yml` {"ref":"main","inputs":{"mode":"full"}};
  13:50, 19:50, 01:30 `live-loop.yml` {"ref":"main"} (5-min rounds for ~5.8 h; loops queue, never clash).
  Header X-GitHub-Api-Version 2022-11-28 sunsets 10 Mar 2028.
- GitHub's own timers in update-data.yml are unreliable (none fired 20:09–22:20 on 30 Oct) — backups only.
- Odds: free plan 500 credits/month, no rollover. Early prices 14:30–16:00 (games before 21:30), main 21:00–22:30,
  late re-price of ONE game when a 25+ min player is newly Out/Doubtful (max 4/night). Only PTS/REB/AST bought.
  Times in update.py are UTC — shift them when UK clocks go forward in March.
- Injuries: ESPN note beats ESPN status when it names tonight (`apply_notes`); "confirmed" after note agrees or 3 checks;
  non-injury notes (contracts, G League…) hidden from news.

## Working rules (from the user)
- Free only. Never invent odds/injuries/lineups/stats/results; label missing or stale data. No "guaranteed".
- Model change → BOTH index.html and scripts/model.py, bump MODEL_VERSION, `python3 scripts/test_model_parity.py`
  = 0 mismatches, backtest on saved picks (+ lab replay on both seasons), ask before shipping.
- Test phone + tablet + desktop + ultra-wide, light + dark (playwright over `python3 -m http.server`; fetch fails on file://).
  To test an old slate, set the browser clock to that slate (`page.clock.install`).
- Releases: afternoon/evening → push to branch **`pending`** (built on origin/pending); the next loop start or GitHub timer
  merges and publishes it. User may say "publish now" → merge origin/pending into main (fetch `--depth=300` first, shallow
  clones can't merge) and reset pending to main. Pushes to main touching `scripts/**` or workflows start a full update.
- Never print or store keys. Ask before spending credits, changing cron-job.org jobs or using the GitHub key.
- After each session: update CHECKPOINT.md (short!) + append details to HISTORY.md, copy CHECKPOINT.md to the project doc
  `claude/swish-checkpoint.md`, keep the guide "SWISH — how it works" (https://claude.ai/artifact/MFN3uQH3Va3qxL8Tpc5kGE) current.

## Latest (31 Oct 09:50) — v1.8 published (user: "ship it now")
- Confidence stretch 0.70. Lab: Brier better in all 9 runs (PTS/REB/AST × 2025-26, 2024-25, 2025-26 no lineups); projections
  unchanged. 70%+ calls: said 76% won 69% → said 75% won 75%, ~70% fewer. Parity 0 (344, snapshot b8d724b, clock 22:30Z).
  Saved-picks backtest (each game re-run on last live.json before tip, both versions same way): strong 9 (5–4 +£6.00) →
  3 (1–2 −£6.50); all 398–399 −£567 → 402–395 −£395. 30 Oct slate: strong 9→3, some 62→31, ~1 in 8 leans flip.
  Expect ~1–3 strong picks a night. Keep the 6-pt bar for now (don't retune on 3 nights).
## Earlier (31 Oct 09:40) — v1.7 published
- Minutes lab (old step 3), both seasons. a) 240-gap fixes (6 versions): all worse → rejected. b) "new" absence for 2–3 games:
  unclear → rejected. c) Missed team's last game → expected minutes × 0.925 (`BACK_TRIM`; lab bias −2 → ~0, Brier better on
  all 4 runs) + flag `back_injury` "On hold · back from injury" on OVERS when also on today's injury report.
  Parity 0 (344 props, snapshot b8d724b, clock 2026-10-30T22:30Z — live.json has no props in the morning). UI 4 sizes × 2 themes OK.
  Saved picks 28–30 Oct: strong 7–8 −£14.49 → 7–7 −£4.49 (Tre Johnson no longer strong); all picks ≈ same.
  Guide: needs "On hold · back from injury" + the −7.5% minutes note.
## Earlier (31 Oct morning)
- Review of 30 Oct + declutter (see Next steps 1 and 3). Guide already says 3PM = projection only, PRA removed (checked 10:00).

## Earlier (30 Oct evening)
- Best picks (Home + Props tab) split into top 5 Overs + top 5 Unders. Published.
- Warnings now a small amber dot + "On hold · reason" label (was ⚠ + "Check status"). "Hide on-hold" tick-box. Published.
- Lab on the under-lean (both seasons): REB lean mostly real; AST slightly under-biased; PTS overs over-rated; main issue
  is overconfidence everywhere. Shrinking the model's own chance (logit × 0.70) helped out-of-sample in all 6 tests.
- bet365 is NOT on The Odds API; UK region has Sky Bet, Paddy Power, William Hill, Coral, Ladbrokes, Betfair… Unknown if they
  have NBA player props → 1-credit test approved: `uk-props-test.yml` (by hand) → `data/uk-props-test.json`.
  Reminder set in the 30 Oct chat for 31 Oct 15:00 UK to run it.
- User's instructions now: UK-based, bet365 UK; use UK odds wherever possible, US prices = backup.

## Next steps (in order)
1. (Done 31 Oct, on `pending`: PRA removed from the site (still computed in background `EXTRA`); 3PM kept as a column with
   SWISH projection only, never a line (`PROJ_ONLY`); chips = All/Points/Rebounds/Assists; Props count = PTS/REB/AST only.)
2. (Done 31 Oct 09:40: v1.7 published; guide updated.)
3. (Done 31 Oct 09:50: v1.8 confidence stretch published.)
4. **UK props test result (15:00)** → if UK books have good PTS/REB/AST coverage, propose UK as main prices, US as backup.
5. **Model lab privacy** (user wants it private): option = remove from site + `data/lab.js`, show as a private claude.ai page;
   optional private repo `swish-lab` for `lab/`. Ask which.
6. (Done 30 Oct 22:35: guide updated for Overs/Unders split + "On hold"; heading now v1.6.)
7. (Checked 31 Oct 10:00: GitHub timers fire only ~1 in 5 of 33 daily slots, often 1–2 h late — GitHub drops/delays scheduled runs; not our bug. 20:09 run failed at "Save if changed" (push clash with the live loop, logs expired). cron-job.org + loops are the real system; timers = best-effort backup. No change made.)
8. Later lab tests: is "big gap" worth holding? usage boost, usual starter benched, bench AST, back-to-backs, blowouts.
9. Later: STL/BLK/TOV columns; closing-line check only on a paid plan; after ~2 weeks review calibration vs market.
