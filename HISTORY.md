# SWISH — full session history (moved out of CHECKPOINT.md on 30 Oct 2026)

Read only when you need the detail behind something in CHECKPOINT.md. Newer entries are near the end of "Done".

_Last updated: 2026-10-30 21:55 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

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

- **29–30 Oct (23:20–00:10), all tested phone/tablet/desktop, light+dark:**
  - Home game rows (≤960px): "N value" on its own line (was running off the edge).
  - 23:30 top-up ran: 11 credits (443 left); +12 lines, −3 (Dejounte Murray), 29 moved. Name alias fix
    `PLAYER_ALIASES` in update.py ("Herb Jones" → "Herbert Jones"), applied to saved props every run.
  - Line changes: update.py writes `lineMoves` ({"player|market": {open, at}} from the ledger's openLine/firstSaved);
    Props cells get corner marks ▲/▼ (moved since the main fetch) or New (added after it); panel "Line change" row.
  - Lineups: "Lineups confirmed" = pastel drifting gradient + gentle breathe (`.tag.lu-go`); green starter chips get a
    soft sheen; both off with reduced motion / calm. Badge lives in the live-score slots (`SLOT.lu`, `SLOT.luM`), so it
    disappears when a game goes live; shown on Props headers (desktop row + `.lu-mob` under the count ≤1180px) and
    Games & Analysis tiles. Injury tags use initials when surnames clash (`injNames`); injuries always on their own row
    in desktop game headers (`.gbreak`).
  - Live scores already work on phones/tablets (simulated); nothing to build.
  - Tip-off times: SWISH shows the official listed time (ESPN); bet365 shows ~10 min later. User: leave as is for now.

- **30 Oct (00:20–01:15) — live-game polish, all tested phone/tablet/desktop, light+dark:**
  - Live: flashing red dot (`.ldot`) in the sidebar + LIVE score tags; LIVE tag restyled as a neutral card with a red glow
    travelling round its edge (`@property --lvang`, `.tag.score.live::before`). Final: one gold pop (`flashFinal`) then still.
  - Light mode injury tags: stronger red tab (border) so they don't clash with LIVE.
  - (Other session, 00:50) phones/tablets: Props headers show green "Game started" / "Game over" (`SLOT.luM`); Games &
    Analysis: once live the header keeps only the score + button, tip-off/total/spread/injuries move to a "Tonight's game"
    row in the H2H card (`anaBadges`, `SLOT.anaInfo` / `anaInfoB`). Keep to ONE chat at a time to avoid clashing pushes.
  - Starter chips go still once their game starts (`.gsec:has(.gsec-h .tag.score) .lu-chip`).
  - Sidebar halftime (clock matches /half/): score dims, amber "HT" tag with a sweep + letter ripple, fixed 22×14 box.
- **Night 2 result (29 Oct):** 51–58 (−£126.96 at £10), 1 pending (DeAndre Jordan REB). Only strong pick after the top-up:
  Herbert Jones UNDER 7.5 pts → scored 16 (lost) — minutes from Dejounte Murray's absence; same issue as A1 below.
  Running total (2 nights): 233–226, −£230.30; strong 8–12; Top overs Medium tier 21–14 (+£19.27) — tiny sample.
  TOPUP_DATES={"2026-10-29"} is date-gated, so it no longer runs; remove it when A4 (conditional re-price) ships.

- **30 Oct (morning) — model v1.3 (A1 done + starter rule), both files, parity 0 on 28 & 29 Oct snapshots:**
  - New absence (player OUT who played in his team's last game, `FRESH_GAMES = 1`) frees his share of a 240-min game:
    freed = his min × 240 / (available + absent min). Long-term absences still use only the gap below 240.
    Tested 2–3 game windows: worse. Same sharing as before (room below 36, ×2 same position, +6 max, cap 40).
  - Starting tonight: NBA.com expected/confirmed starter who is NOT in his team's top-5 expected minutes gets
    ≥ 90% (`STARTER_SHARE`) of the other starters' average minutes. Names compared with accents stripped
    (NBA.com "Matković" vs ESPN "Matkovic"). Picks store `starterTonight`. Chip "▲ +N min · new starter".
  - Backtest (458 graded props, 28+29 Oct pre-tip snapshots d5512b5 / 579b0fd): minutes miss 4.01→3.96, model-only Brier
    0.2640→0.2629, SWISH 0.2513→0.2511 (market 0.2496). Re-run picks: all 230–228 → 232–226 (−£278→−£237);
    strong 8–12 → 6–11 (−£45→−£54). Herbert Jones PTS flips under→over (he started for Murray, played 32, scored 16).
    Night 1 had no saved lineups, so the starter rule is tested on ONE night (3 games) only. Small gain, not proof.
  - Rolechips in squad names now ellipsis-truncate (no longer run under the Last 6 button on desktop).
- **30 Oct (late morning) — model v1.4 "Minutes unclear" flag** (user doesn't want SWISH guessing who gains minutes):
  a player with 25+ expected minutes (`KEY_MIN`) newly OUT (played in team's last game) → every prop on his team gets
  flag `min_unclear` ("Minutes unclear — X out; waiting for the confirmed lineup") until NBA.com marks that team's lineup
  "confirmed" (~30 min pre-tip). Any flag = verdict "check", not strong, not in Top overs. Shared minutes still in the
  projection (estimate). Both files (`key_absences` / `keyAbsences` + `KEY_OUT`), parity 0 on 3 slates.
  Backtest (tiny): 28 Oct (no lineups saved that night) 82/366 props flagged on 5 teams — strong removed 1–2 (−£8.60),
  Top overs removed 6–2 (+£22.62); 29 Oct without lineups: 15 NOP props, Top overs removed 1–1. It's a safety rule.
  Parity tip: the page falls back to the sample slate when live data is >36h old, so test old snapshots with the
  browser clock set to the slate time (playwright `page.clock.install`).
  Agreed order after this: C0 → B → projection lab (with-vs-without = its first test) → A4 late re-price (ask first).
- **30 Oct (midday) — PROJECTION LAB part 2 + model v1.5:** `lab/replay.py` replays a season night by night with
  scripts/model.py (or `--model <file>`), using only earlier games; rosters from that night's box score; "Out" = ESPN
  DNP with an injury-type reason; `--lineups` gives that night's starters as confirmed; pretend line = floor(last-20 avg)+.5
  at even odds (for calibration only). ~10 s per season. Results JSON in `lab/results/`. `lab/model_v1_2.py` = frozen v1.2.
  Findings (2025-26, 61,361 common projections; 2024-25 check 51,277):
  - v1.3's "freed share" for new absences made minutes WORSE on both seasons (over-projects ~2 min where it fires) → removed.
  - New-starter rule at full strength overshot (bias +2.7 → −2.6 min) → v1.5 moves a third of the way (`STARTER_PULL`).
    Minutes miss 5.278 (v1.2) / 5.290 (v1.4) / 5.236 (v1.5); 2024-25: 5.227 / 5.262 / 5.181. Brier (pretend lines) best for v1.5.
  - Every version over-projects minutes by ~1.2–1.4 on average (expected minutes ignore DNPs) → next lab test.
  - SWISH's own chance is overconfident: says 75% → happens 61%; 59% → 51% (pretend lines). Matches live 60–65% bucket.
  - "Minutes unclear" flag (v1.4) kept; it doesn't change projections.
  Saved-picks backtest v1.5 vs v1.2: minutes 4.01→4.00, all picks unchanged 230–228, strong 8–12 → 6–9.
  Herbert Jones 29 Oct: v1.5 moves him only ~22.5 → ~24.6 min, so he stays an under — the lab says, on average, that's right.
- **30 Oct (midday) — model v1.6 (lab-tested, both seasons):** `trim_minutes()` / `trimMinutes()`: expected minutes above
  28 lose 10% of the excess (`HIGH_MIN_TRIM`, `HIGH_MIN_FROM`); final sd × `SD_SCALE = 1.15`. Lab, players who played:
  Brier 0.24282→0.24215 (2025-26), 0.24401→0.24348 (2024-25); PTS miss 4.912→4.905. sd ×1.3/×1.45 worse; trim 0.2 ≈ 0.1.
  Half of the "1.2 min too many" was players who didn't play at all (void bets). Real-line saved picks: model-only Brier
  0.2640→0.2622, minutes 4.01→3.98; strong picks 20→5 (intended: fewer overconfident edges). Parity 0 on 3 slates.
  Still overconfident at the top on pretend lines (72%→66%) — pretend lines aren't market lines; watch live calibration.
- **Model lab on the website:** Results page → "Model lab" (`labPanel()`), data from `data/lab.js` built by
  `python3 lab/build_page_data.py` from `lab/experiments.json` (hand-kept list of tests with their numbers) + the latest
  `lab/results/v1.6-lineups.json` calibration (played rows only). After any new lab test: add it to experiments.json,
  re-run build_page_data.py, push. Also loaded by refreshInPlace(). Tested phone dark + desktop light.
  Next lab tests: with-vs-without, usage boost, usual starter benched, bench AST, back-to-backs, blowouts.
- **30 Oct (afternoon) — A4 late re-price DONE (user approved credits):** update.py `reprice_candidates()` +
  auto window "reprice": after the early/late odds run, if a player with 25+ expected min (`REPRICE_MIN`) who still had
  lines when the game was priced is listed Out/Doubtful with an ESPN `updated` time newer than that game's lines, re-buy
  that ONE game's PTS/REB/AST (no UK game lines; inside the daily budget; max `REPRICE_MAX_PER_NIGHT` = 4; one trigger
  per player). Runs log {"window":"reprice","game","for"} in sections.odds.runs. Dry run on 29 Oct 22:30 data → SAC@NOP for
  Murray only. TOPUP_DATES removed from update.py and index.html; Home timeline shows "Late price update" rows.
- **30 Oct — with-vs-without TESTED AND REJECTED:** `with_without()` in model.py (switched off: `WW_MODE = 0`). 9 variants
  (shrink K 3/10/25, need 2/3/6 games without, replace vs add to the 240-gap rule) — all worse than v1.6 on both seasons
  (e.g. 2025-26 Brier 0.24215 → 0.24222–0.24266). Reason: past "without" games are few and confounded. Logged on the Model
  lab page. User wants "who replaces him" from real info, not guesses: best free signals = NBA.com confirmed lineups (used)
  + ESPN injury comments (they quote beat reporters). X/Twitter API and RotoWire-type feeds are paid → not used (free rule).
  Possible next: show the ESPN injury/news text inside the prop panel; ESPN news API (free) feed on the Injuries page.
- **30 Oct 19:15 — injury note beats status (user spotted Cameron Johnson "OUT" while the note said "expected to play"):**
  update.py `status_from_note()` / `apply_notes()` run after every injuries fetch: if the ESPN comment names tonight's
  weekday or "tonight", its status (first match: Out › Doubtful › Questionable › Probable/expected to play) replaces the
  status field; ESPN's kept in `espnStatus`, `statusFrom: "report"`. Both model files read the corrected status, so parity
  is unaffected. Page shows a small blue blip on the status pill (`injPill`, `.st.upd`; tap/hover explains). 10 corrected that night.
- **30 Oct 19:40 — refresh polish + phone header (user tested in-place refresh on Safari: no white flash, but entrance
  animations replayed):** cause = removing `html.noanim` restarts every one-off animation. Now `settleAnimations()` removes
  noanim and `finish()`es every non-infinite animation (document.getAnimations), on in-place refresh and quiet reload.
  `flashUpdated()`: green pill gets `.justupd` for 3.6 s → "↻ Updated" (phones hide the time meanwhile; icon spins twice;
  off with Reduce motion). Fires only when new data arrives. Phones (≤960px): `.qbtn` "?" in the header left of Home
  (black, white outline; red on tap and while help is open, `syncHelpBtn()`); top-bar help button hidden; theme button
  42×42 beside Dec/US on the far right. Desktop unchanged. Tested phone dark/light + desktop.
- **30 Oct 19:50 — header polish (user feedback):** "?" on phones = liquid-glass button (blurred tint, bright rim, top
  highlight), NO colour change on tap/open. Side panels (help, prop details) on phones = `min(560px, 100vw − 40px)` with
  rounded left corners, a strip of the page stays visible (was full screen). Update moment (`flashUpdated` → `.justupd` on
  the green pill + `html.updflash`, 3.6 s): pill glows bright green with a light sweep, "↻ Updated" springs open, the time
  slides up; on phones the red Injuries pill folds to an icon (`.nsc`) then reopens. Gap updates: update-data.yml cron
  `20-50/5 19 * * *` (afternoon loop ends ~19:20, evening starts 19:50; GitHub schedules can be late). 19:12 push run
  failed only at "Save" (push collisions) — data fine on later runs.
- **30 Oct 20:05 — injury NEWS filter + confirmation (user: feed showed contract/G League notes as injuries):**
  update.py `note_kind()` → `news`: "status" (STRONG_RE availability wording about tonight; a note naming another
  weekday's game = not news), "injury" (INJURY_RE: surgery, torn, re-evaluated, weeks…) or null (NOT_NEWS_RE: team option,
  contract, G League, practice, drills, progressing… or nothing relevant). Site `isNewNews` requires news ≠ null (feed,
  NEW counters, "New tonight", red pill's last change). `confirm_injuries()`: `checks` = consecutive updates with the same
  status (entries from before the rule count as settled), `confirmed` = note agrees (tonight's status, or long-term wording
  for Out) OR checks ≥ 3. Unconfirmed → outline pill (`.st.unconf`, tap explains). Late re-price needs confirmed.
  Model untouched (still uses status) → parity unaffected. 30 Oct: 28 of 95 entries hidden as not-news.
- **30 Oct 20:10 — no clashing updates:** gap cron now `25-45/5 19` (evening loop starts 19:50). update.py: a `schedule`
  (GitHub timer) run in light mode exits without writing if data was saved < 3.5 min ago (`GITHUB_EVENT_NAME`), so the
  backup timers (21:27, 21:47, 22:07… which overlap the cron-job.org loops) no longer duplicate loop updates.
  update-data.yml Save: ignores log-only changes; retries pull --rebase + push 5× instead of failing (19:12 and 19:43 runs
  failed at Save on collisions). Note: every push touching scripts/ or workflows triggers a full update (~4–6 min) —
  that's what caused the extra 19:59 update; expected after code changes only.
- **30 Oct 20:30 — GitHub was slow (Actions/Pages incident earlier that evening; publishes took 4–8 min, a 19:45 timer
  started 20:09). Fixes pushed:** page checks stamp.json every 20 s (was 60) + on focus/pageshow; swap waits for a 1.5 s
  pause in scrolling but never more than 20 s. Save step: `git pull --rebase -X theirs` (this run's data wins a real file
  clash; plain retries can't). Backup GitHub timers stand down if data < 6 min old (was 3.5).
  Desktop (>960px) update moment: badge text/size fixed, dot cross-fades to the spinning arrow (.ms absolute), glow +
  sweep + time slide only; `setHTML()` rebuilds the badge only when its HTML changes (no mid-animation restarts).
- **30 Oct 20:50 — WAITING CHANGES RIDE WITH THE NEXT UPDATE (user's rule):** during the afternoon/evening, push site or
  model changes to branch **`pending`**, NOT main (`git push origin HEAD:refs/heads/pending`, built on top of
  origin/pending). The live loop (from its next start — the 30 Oct evening loop started before this) and update-data.yml
  (every GitHub timer) merge origin/pending at the start of their run and publish it with that update; a timer that has no
  data change still pushes the release. Bot pushes don't trigger other workflows → no extra full update. Tell the user
  which update it will go out with. Pushing straight to main is for real breakages only.
- **30 Oct 20:55 — nothing pre-render ever shows:** `html:not(.ready) .app{visibility:hidden}`, `.ready` added right after
  the first render() (3 s safety timer in the head script); global `[hidden]{display:none!important}` (the empty newsPill
  was showing its amber "›" on load). index.html is the only page.
- **Night 2 final:** DeAndre Jordan REB still pending at 10:00 30 Oct (next full run grades or voids it).

- **30 Oct 21:45 — Best picks split (on `pending`, commit "Best picks: show top 5 overs and top 5 unders"):** Home
  "Best picks tonight" and the Props "Best picks" tab now show two groups — Overs then Unders, top 5 each
  (`BEST_PER_SIDE`, `sidesHTML()`), own ranking per side, "top 5 of 8" / "2 tonight" / "none tonight" counts. User asked
  because 8 of 10 strong picks were unders. Tested phone dark, tablet light, desktop light, ultra-wide dark; no errors.
  NOTE: GitHub timers haven't fired since 20:09, and the 19:50 loop predates the pending rule → `pending` (this + the
  20:55 "nothing pre-render" fix) goes live when the 01:30 loop starts (~01:40 UK, queued behind the 19:50 loop).
- **30 Oct 21:50 — LAB: is the under-lean real? (both seasons, ~117k played projections, pretend lines):**
  REB: SWISH avg over chance 47% vs actual 46–47% → no overall bias. When projection > line but SWISH says under
  (about a third of REB, 39–42% of AST), those went over only 47–51% → the skew logic is roughly right; the lean is mostly
  real, not a bug. AST: slight under-bias (says 45% overs, actual 46.5–48%; says 30% → happens 35–39%).
  PTS: the opposite — overs over-rated (says 59% → 52%). Main problem = OVERCONFIDENCE on every market.
  Calibration test (fit one season, test the other, logit recalibration per market): "stretch" ≈ 0.70 (shrink the model's
  own chance toward 50% on the logit scale) improved Brier out-of-sample in all 6 cases (PTS 0.2457→0.2437 / 0.2428→0.2404,
  REB 0.2426→0.2417 / 0.2414→0.2404, AST 0.2467→0.2451 / 0.2422→0.2420). The "shift" part depends on how pretend lines are
  made → don't ship it; ship only the stretch. Scripts: scratch only (lean.py / cal.py logic = per-market avg pO vs actual,
  buckets, logistic fit y ~ a + b·logit(pO) on `replay.py --lineups --dump` rows).

- **30 Oct 22:05 — warnings made quiet + clear (published to main at user's request):** flagged prop cells no longer
  show ⚠ + amber box; a small amber dot top-left (`.cell .hold`), projection in neutral grey. Verdict "Check status" →
  "On hold · <reason>" (`holdReason()`: injury doubt / teammate doubt / old price / new injury news / lineup due / new role /
  few games / big gap), styled as plain amber text with a dot (not button-like). "Hide flagged" → "Hide on-hold".
  Rules unchanged (on-hold props still never picks). Tonight: 43/344 on hold (few_games 17, min_unclear 17, status 9, big_gap 8).
  Idea for the lab: is `big_gap` worth keeping? (does the market beat SWISH on those props?)

- **30 Oct 22:20 — UK prices question:** The Odds API UK region has ~20 books incl. Sky Bet, Paddy Power, William Hill,
  Coral, Ladbrokes, Betfair — NOT bet365 (only bet365_au, paid, AFL/NRL). Unknown whether UK books return NBA player props.
  User approved a 1-credit test: `.github/workflows/uk-props-test.yml` (workflow_dispatch only) runs `tools/uk_props_test.py`
  (next game not started, regions=uk, markets=player_points) → `data/uk-props-test.json`. Scheduled in-chat reminder for
  31 Oct 15:00 UK to run it. User updated project instructions: UK-based, bet365 UK; use UK odds wherever possible, US = backup.
  Model lab privacy: parked to 31 Oct (option: remove from site + private claude.ai page; optional private `swish-lab` repo).

## Next steps (in order)

**FIRST on 31 Oct (user asked 30 Oct 21:21 — remind them): declutter 3PM + PRA.** They have no prices (only PTS/REB/AST
are bought; adding them ≈ 60 credits/night ≈ 1,800/month, too much for the free plan), so they can never be picks.
1. Remove the 3PM and PRA columns and filter chips from the Props page.
2. Count only PTS/REB/AST props in "props" totals (Home said "870 props" when ~344 were priced).
3. Keep computing them in the background (free) so they can be switched back on with a paid plan.
4. Optional (user to choose): one info line with the PRA / threes projection inside a player's prop panel.
No model/picks/results change (those only ever used PTS/REB/AST). Release via the `pending` branch.

**SECOND on 31 Oct: model v1.7 = confidence stretch** (lab result above, user asked for this test 30 Oct 21:40).
`MODEL_STRETCH = 0.70`: pure model over chance → sigmoid(0.70 · logit(p)) before the 30/70 market blend. Both files,
bump MODEL_VERSION, parity 0, re-run replay on both seasons (log in lab/experiments.json + build_page_data.py), backtest saved
picks (expect fewer strong picks both sides, esp. big-gap REB/AST unders and confident PTS overs). Ask user before shipping.
Also check why the pending branch waited (GitHub timers silent after 20:09).

**Order agreed 29 Oct 22:47; A1 DONE 30 Oct (v1.3). Continue with A2:**
A. **Minutes fix — injured players (esp. big ones).** Found 29 Oct: Dejounte Murray (NOP, ~31 min) ruled out 22:22 but
   teammates gained only ~1 min each, because available NOP players' expected minutes already summed to ~278 (>240),
   so the shortfall logic saw no room. Plan (all model changes: BOTH files, bump MODEL_VERSION, parity 0, backtest):
   1. ~~Share the absent player's minutes~~ DONE v1.3 (+ starter rule). It did NOT pick WHO gains (gave Murray's minutes
      to Mathurin/Queen, not Jones); the confirmed-starter rule fixed that case. Step 2 should decide who gains.
      Watch: v1.3 results by night on the Results page ("by version"); starter rule needs more nights.
   2. "With vs without" history: teammate minutes/stats in games the absent player played vs missed (this + last
      season, ≥2–3 games), fall back to step 1.
   3. Usage boost: higher per-minute PTS/AST rate when a high-usage player sits (from with/without, else small capped).
   4. Conditional re-price: after 21:00, if a 25+ min player is ruled out, re-fetch odds for that game only (~3
      credits). Replaces nightly top-ups. Tonight's one-off top-up uses TOPUP_DATES={"2026-10-29"} — remove after.
   5. Steps 2–3 tested inside the projection lab (step 0) before shipping.
B. ~~Update the page in place~~ DONE 30 Oct: `refreshInPlace()` — on a newer data/stamp.json it injects data/live.js +
   results.js, re-runs `applyLive()` (was the top-level `if (IS_LIVE){…}` block), `indexGames()`, GAMES, PLAYERS,
   PLAYER_BY_NAME, `buildAllProps()`, STARTERS, then `render()`; keeps scroll, view, open prop panel (ids are stable
   hashes), filters, and browser live scores if ahead of the file. `LIVE` is now `let`. Falls back to the old quiet reload
   only on a new slate date or an error. Tested over http (fetch doesn't work on file://) on all 5 pages, phone dark +
   desktop light, no page errors. Also: edge now shown as "+5.5%" (was "+5.5 pts").
C0. ~~Missing top-up picks~~ DONE 30 Oct: not a bug. Players expected under 22 min get only PTS/REB/PRA modelled
   (`mins >= 22` rule in model.py + index.html), so Flemings/Landale/Tyson AST lines were skipped by design (Tyson AST
   is modelled under v1.3+ because the new-absence rule takes him to 22). Only 3–8 lines a night are skipped (mostly AST).
   Whether low-minute AST is predictable → test in the projection lab, don't change now. Aliases: PLAYER_ALIASES in update.py.
C. Parked, user's call: closing-line check (step 3) — only on a paid plan or tiny budget.
0. **Projection lab — part 1 DONE 30 Oct (11:19–11:34 UTC, free):** `lab/download.py` + `.github/workflows/lab-download.yml`
   (runs on push to those files or by hand; resumable). Saved `lab/data/season-2025.json.gz` (2024-25: 1,234 games, 26,275
   player-games, 580 players, no ESPN game lines) and `season-2026.json.gz` (2025-26: 1,235 games, 26,628 player-games, 592
   players, 980 games with ESPN spread/total). Per player per game: starter, DNP + reason, min, PTS/REB/AST/3PM/STL/BLK/TOV,
   FGM/FGA/FTM/FTA, OREB/DREB, PF, +/-. Checks: 10 starters + box score = final score in every game except 7 (2025-26).
   NEXT (part 2): replay 2025-26 night by night with only earlier games (2024-25 as "last season"), port the v1.4
   projection, measure minutes/projection error; then test with-vs-without, usage boost, starter demotion, bench AST,
   rest/back-to-backs, blowouts (ESPN lines), recent-form weighting. Ship only proven changes.
   Original idea notes: **Idea saved for later (user's call, 29 Oct): projection testing lab.** Replay last season day by day from ESPN game logs
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


## 31 Oct 2026 (morning) — review of 30 Oct + declutter
- 30 Oct results (£10/pick): all 173–166, won £1,474.06, lost £1,660 → −£185.94; strong 3–5 → −£18.82;
  overs 64–74 −£176.77, unders 109–92 −£9.17. Running strong total (3 nights) 11–17, −£60.53. 3 Naji Marshall props pending.
- Minutes review: avg minutes error 3.8. Absence shares worked for ORL (Banchero/Suggs → Jase Richardson 20→33) and TOR.
  Failed for HOU (Sengun Out; available total 243) and PHI (Jaylen Brown Out 22:05; total 254): the 240-gap rule did not fire
  because players with 1–2 games this season carry last-season minutes. Capela 17→30, Simons 24→31, Amen 33→39.
  Sengun had already missed 29 Oct so not "new" (FRESH_GAMES=1). Tre Johnson (back from Achilles, Q until 22:20) strong over,
  played 13 of 23 expected. Fix ideas logged as Next step 3 (lab first).
- Declutter (user: "keep 3PM but no bookmaker line"): SHOW_MARKETS = PTS/REB/AST/3PM, PROJ_ONLY = 3PM (forced noLine),
  PRA → EXTRA (computed, not shown/counted). Filter chips without Threes/PRA (chips filter priced props). Props nav count
  excludes 3PM. Tested 4 sizes × light/dark on today's slate and 30 Oct 22:40 priced snapshot: no errors, no overflow.
  No model change (picks/ledger unaffected). Pushed to `pending`.
- 09:20: 3PM cells show the SWISH projection as the main number in blue + small "proj" label (no dash). Published to main.
- 09:25: 3PM projection number now same colour as a normal line (user asked).
