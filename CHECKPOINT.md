# SWISH — checkpoint (short)

_Last updated: 2026-10-30 22:30 UK by Claude._ Full detail of every past session: `HISTORY.md` (read only when needed).
Keep this file SHORT (aim < 9,000 characters): put session details in HISTORY.md, keep here only what the next chat needs.

## What SWISH is now
- Site: https://indulgetv.github.io/swish/ — one page, `index.html` (Home, Props, Games & Analysis, Injuries, Results).
  Loads `data/live.js` + `data/results.js` (+ `data/lab.js`); shows the sample slate if live data is missing or >36h old.
  Checks `data/stamp.json` every 20 s and refreshes in place (`refreshInPlace()`), keeping scroll/panels/filters.
- Pipeline: `scripts/update.py` (ESPN: schedule, standings, injuries, rosters, game logs, H2H; NBA.com lineups;
  The Odds API: **US** player props PTS/REB/AST + UK game lines) → `data/live.json/.js`. `--mode auto` picks the job by time.
- Picks ledger: `scripts/ledger.py` saves picks for games not started into `data/picks/<date>.json` (locked at tip),
  grades from ESPN box scores (void if absent 10 h after tip) → `data/results.json/.js` (Results page).
- Model: `scripts/model.py` = Python copy of the browser model in index.html. **MODEL_VERSION v1.6**.
  Projection = per-minute rate × expected minutes (this season 0.5·last3 + 0.5·last10, last season early on;
  absences share the gap below 240 min; NBA.com new starter pulled ⅓ of the way to starter minutes; >28 min trimmed 10%);
  sd × 1.15; normal curve for PTS, negative binomial for REB/AST. SWISH chance = 0.3·model + 0.7·no-vig market
  (`MODEL_WEIGHT` 0.3 — don't change until ~1,000 graded props). Strong value = edge ≥ 6 pts, EV > 0, no flags.
  Flags ("On hold · reason"): injury doubt, lineup due (25+ min teammate newly out, until NBA.com confirms), few games (<5),
  big gap (line far from projection), new role, old price, injury news newer than the line. Players < 22 exp. min: no AST.
- Projection lab: `lab/replay.py` replays a season night by night (`--lineups`, `--dump`, `--model`); data in `lab/data/`;
  tests listed in `lab/experiments.json` → `python3 lab/build_page_data.py` → `data/lab.js` (Results → Model lab).
- Results so far (2 nights, 28–29 Oct): all picks ~233–226, about −£230 at £10; strong ~8–12. Tiny sample.

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

## Latest (30 Oct evening)
- Best picks (Home + Props tab) split into top 5 Overs + top 5 Unders. Published.
- Warnings now a small amber dot + "On hold · reason" label (was ⚠ + "Check status"). "Hide on-hold" tick-box. Published.
- Lab on the under-lean (both seasons): REB lean mostly real; AST slightly under-biased; PTS overs over-rated; main issue
  is overconfidence everywhere. Shrinking the model's own chance (logit × 0.70) helped out-of-sample in all 6 tests.
- bet365 is NOT on The Odds API; UK region has Sky Bet, Paddy Power, William Hill, Coral, Ladbrokes, Betfair… Unknown if they
  have NBA player props → 1-credit test approved: `uk-props-test.yml` (by hand) → `data/uk-props-test.json`.
  Reminder set in the 30 Oct chat for 31 Oct 15:00 UK to run it.
- User's instructions now: UK-based, bet365 UK; use UK odds wherever possible, US prices = backup.

- **30 Oct 22:05 — warnings made quiet + clear (published to main at user's request):** flagged prop cells no longer
  show ⚠ + amber box; a small amber dot top-left (`.cell .hold`), projection in neutral grey. Verdict "Check status" →
  "On hold · <reason>" (`holdReason()`: injury doubt / teammate doubt / old price / new injury news / lineup due / new role /
  few games / big gap), styled as plain amber text with a dot (not button-like). "Hide flagged" → "Hide on-hold".
  Rules unchanged (on-hold props still never picks). Tonight: 43/344 on hold (few_games 17, min_unclear 17, status 9, big_gap 8).
  Idea for the lab: is `big_gap` worth keeping? (does the market beat SWISH on those props?)

## Next steps (in order)
1. **Declutter 3PM + PRA** (user asked; remind them): remove those columns + filter chips from Props; count only PTS/REB/AST
   in "props" totals; keep computing them in the background; optional info line in the prop panel (ask). No model change.
2. **Model v1.7 = confidence stretch** `MODEL_STRETCH = 0.70` (pure model chance → sigmoid(0.70·logit p) before the blend).
   Full model process; log in lab/experiments.json; expect fewer strong picks on both sides. Ask before shipping.
3. **UK props test result (15:00)** → if UK books have good PTS/REB/AST coverage, propose UK as main prices, US as backup.
4. **Model lab privacy** (user wants it private): option = remove from site + `data/lab.js`, show as a private claude.ai page;
   optional private repo `swish-lab` for `lab/`. Ask which.
5. (Done 30 Oct 22:35: guide updated for Overs/Unders split + "On hold"; heading now v1.6.)
6. Why GitHub timers went silent after 20:09 on 30 Oct.
7. Later lab tests: is "big gap" worth holding? usage boost, usual starter benched, bench AST, back-to-backs, blowouts.
8. Later: STL/BLK/TOV columns; closing-line check only on a paid plan; after ~2 weeks review calibration vs market.
