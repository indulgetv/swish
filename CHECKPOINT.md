# SWISH — progress checkpoint

_Last updated: 2026-10-28 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

## Done
- `index.html` — the full SWISH dashboard, now **wired to live data** (`data/live.js`).
  Falls back to the sample slate if the file is missing, has no games, or is >36h old.
  - Players and props built from real ESPN game logs (55% season / 45% last 10, small H2H blend).
  - US prop lines are labelled **"US reference"** and can never be "Strong value" (shown as "Check your price").
  - **Your-price form** in every prop panel and on "+ line" cells: line + over/under in decimal, fractional
    or American. Saved in the browser per slate. "Strong value" only against your own price.
  - Games & Analysis uses live records, conference rank, games back, streak and real H2H.
  - Injuries filtered to tonight's teams; ESPN "Day-To-Day" shown as Questionable.
- `scripts/update.py` — free data pipeline (ESPN feeds for schedule, standings, injuries, rosters,
  player game logs incl. STL/BLK/TOV, head-to-head; The Odds API for US prop reference lines + UK game lines,
  with a monthly credit budget). Writes `data/live.json` and `data/live.js`.
- `.github/workflows/update-data.yml` — runs automatically (UTC times):
  full 07:17 & 14:17, odds 16:37, light (scores + injuries) hourly 15:47–03:47, and on every
  push to `scripts/` or the workflow. Each run saves its output to `data/last-run.log`.
- First automated run (2026-10-28 20:05 UTC) checked: 12 games, 394 players, 0 errors.
- User has: GitHub repo `indulgetv/swish` (public), Actions write permission, secret `ODDS_API_KEY`.
- `dev/live-adapter.js` is now merged into `index.html` (kept only for reference).

## Next steps (in order)
1. After the next 16:37 UTC odds run, check `data/last-run.log` for the odds line (credits used, props found)
   and confirm reference lines appear on the Player Props page.
2. User turns on GitHub Pages: Settings → Pages → Deploy from branch → main / (root).
3. Add STL / BLK / TOV markets to the dashboard (data is now collected; needs CV/SD settings + UI columns).
4. Minutes/role model: adjust projections when a teammate is confirmed out (fill-ins are not automated yet).
5. Later: confirmed starting lineups near tip-off; results tracking (Results page) — log your saved prices
   and settle them against box scores.

## How to resume
> "Continue SWISH from CHECKPOINT.md in indulgetv/swish — start at the first unfinished next step."
