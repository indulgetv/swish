# SWISH — progress checkpoint

_Last updated: 2026-10-28 by Claude._ Paste the line in **"How to resume"** into a new Claude session.

## Done
- `index.html` — the full SWISH dashboard (still on the **sample slate**).
- `scripts/update.py` — free data pipeline (ESPN feeds for schedule, standings, injuries, rosters,
  player game logs, head-to-head; The Odds API for US prop reference lines + UK game lines,
  with a monthly credit budget). Writes `data/live.json` and `data/live.js`.
- `.github/workflows/update-data.yml` — runs automatically (UTC times):
  full 07:17 & 14:17, odds 16:37, light (scores + injuries) hourly 15:47–03:47, and on every
  push to `scripts/` or the workflow. Each run saves its output to `data/last-run.log`.
- User has: GitHub repo `indulgetv/swish` (public), Actions write permission, secret `ODDS_API_KEY`.

## Next steps (in order)
1. Check `data/last-run.log` + `data/live.json` from the first automated run; fix any ESPN parsing issues.
2. Wire `index.html` to live data: load `data/live.js`, merge `dev/live-adapter.js`
   (builds players/props from real logs; sample fallback; US lines labelled "reference";
   "Strong value" only against the user's own bet365 price).
3. Add the bet365 "enter your line" form in the prop panel and on cells with no line.
4. Replace sample team stats on Games & Analysis with live records/standings.
5. User turns on GitHub Pages: Settings → Pages → Deploy from branch → main / (root).
6. Later: confirmed starting lineups near tip-off; results tracking (Results page).

## How to resume
> "Continue SWISH from CHECKPOINT.md in indulgetv/swish — start at the first unfinished next step."
