/* =================================================================
   LIVE DATA ADAPTER
   data/live.js (written by the GitHub automation) sets window.SWISH_LIVE.
   When it is present and has tonight's games, SWISH switches from the
   sample slate to real data. Nothing sample is mixed into live mode.
   ================================================================= */
const LIVE = window.SWISH_LIVE || null;
const ET_TODAY = new Date().toLocaleDateString("en-CA", {timeZone: "America/New_York"});
const LIVE_AGE_H = LIVE && LIVE.meta && LIVE.meta.writtenAt ? (Date.now() - new Date(LIVE.meta.writtenAt)) / 3.6e6 : Infinity;
const IS_LIVE = !!(LIVE && Array.isArray(LIVE.games) && LIVE.games.length && LIVE_AGE_H < 36);
const LIVE_NOTE = !LIVE ? "No live data file found — showing the sample slate."
  : !(LIVE.games || []).length ? "No NBA games on the latest live slate — showing the sample slate."
  : LIVE_AGE_H >= 36 ? "Live data is more than 36 hours old — showing the sample slate until it refreshes." : "";
const agoTxt = iso => { if (!iso) return "unknown"; const m = Math.round((Date.now() - new Date(iso)) / 60000); return m < 60 ? `${m} min ago` : m < 2880 ? `${Math.round(m/60)}h ago` : `${Math.round(m/1440)} days ago`; };
const normName = n => (n || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b\.?/g, "").replace(/[^a-z]/g, "");

/* ---- your own bookmaker prices (bet365 etc.), saved in this browser for the slate ---- */
const MYLINES_KEY = "lines." + (IS_LIVE ? LIVE.meta.slateDate : "sample");
function loadMyLines(){ try { return JSON.parse(store.get(MYLINES_KEY, "{}")) || {}; } catch(e){ return {}; } }
function saveMyLines(v){ store.set(MYLINES_KEY, JSON.stringify(v)); }
const toAmerican = dec => dec >= 2 ? Math.round((dec - 1) * 100) : Math.round(-100 / (dec - 1));
const parsePrice = (txt, fmt) => {           // accepts decimal (1.91), American (-110) or fractional (10/11)
  const t = String(txt).trim(); if (!t) return null;
  if (/^\d+\s*\/\s*\d+$/.test(t)) { const [a, b] = t.split("/").map(Number); return b ? toAmerican(1 + a / b) : null; }
  const v = Number(t); if (!isFinite(v)) return null;
  if (fmt === "am" || Math.abs(v) >= 100) return Math.abs(v) >= 100 ? Math.round(v) : null;
  return v > 1.01 ? toAmerican(v) : null;
};

if (IS_LIVE){
  /* teams: every team ESPN gave us (all 30 via standings) */
  const T = {};
  Object.entries(LIVE.teams || {}).forEach(([ab, t]) => { T[ab] = {city: t.city || "", name: t.name || ab, color: t.color && t.color.length > 3 ? t.color : "#777", record: t.record, displayName: t.displayName}; });
  /* standings → same "ABBR W-L" shape the sidebar already reads */
  const ST = {};
  ["East","West"].forEach(c => { ST[c] = ((LIVE.standings || {})[c] || []).map(r => `${r.team} ${r.w}-${r.l}`); });
  const stRow = ab => { for (const c of ["East","West"]) { const i = ((LIVE.standings || {})[c] || []).findIndex(r => r.team === ab); if (i >= 0) return {...LIVE.standings[c][i], conf:c, rank:i+1}; } return null; };

  /* UK game lines → median total + spread per game */
  const glines = LIVE.gameLines || [];
  const med = a => { const s = [...a].sort((x,y) => x - y); return s.length ? s[Math.floor(s.length / 2)] : null; };
  const injOut = ab => (LIVE.injuries || []).filter(i => i.team === ab && i.status === "Out").map(i => i.player);

  const games = (LIVE.games || []).map(g => {
    const tot = med(glines.filter(l => l.game === g.id && l.market === "totals" && /over/i.test(l.name)).map(l => l.point));
    const hs = glines.filter(l => l.game === g.id && l.market === "spreads");
    const homeName = `${(T[g.home]||{}).city} ${(T[g.home]||{}).name}`.trim();
    const hsp = med(hs.filter(l => normName(l.name) === normName(homeName)).map(l => l.point));
    const spread = hsp != null ? `${g.home} ${hsp > 0 ? "+" : "−"}${Math.abs(hsp)}` : (g.espnLine && g.espnLine.details) || "—";
    const total = tot != null ? tot : (g.espnLine && g.espnLine.overUnder) || "—";
    const h2h = (LIVE.h2h || {})[g.id] || [];
    const notes = [];
    [g.away, g.home].forEach(ab => { const o = injOut(ab); if (o.length) notes.push(`${T[ab] ? T[ab].name : ab} are without ${o.slice(0,4).join(", ")}${o.length > 4 ? ` and ${o.length - 4} more` : ""}.`); });
    const sa = stRow(g.away), sh = stRow(g.home);
    if (sa && sh) notes.push(`${T[g.away].name} are ${sa.w}-${sa.l} (${sa.conf} #${sa.rank}); ${T[g.home].name} are ${sh.w}-${sh.l} (${sh.conf} #${sh.rank}).`);
    if (h2h.length) { const w = h2h.filter(m => (m.hp > m.ap ? m.home : m.away) === g.home).length; notes.push(`${T[g.home].name} have won ${w} of the last ${h2h.length} meetings.`); }
    const status = g.state === "pre" ? "Scheduled" : g.state === "in" ? `Live · ${g.status || ""}` : (g.status || "Final");
    return {id: g.id, away: g.away, home: g.home, tipoff: g.tipoff, status, state: g.state, lineups: g.state === "pre" ? "Unconfirmed" : "Set",
            total, spread, h2h, notes: notes.length ? notes : ["No notable injuries or trends flagged yet."],
            score: g.state !== "pre" ? `${g.awayScore ?? "–"}–${g.homeScore ?? "–"}` : null};
  });

  const inj = (LIVE.injuries || []).map(i => ({team: i.team, player: i.player, pos: i.pos || "", status: i.status || "Unknown",
    detail: i.detail || i.comment || i.rawStatus || "", updated: i.updated || (LIVE.sections.injuries || {}).fetchedAt, comment: i.comment, fillIns: []}));

  Object.assign(DATA, {
    meta: {source: "LIVE", isLive: true, slateLabel: "Tonight's slate", generatedAt: LIVE.meta.writtenAt, staleAfterMinutes: 14 * 60},
    teams: T, standings: ST, games, injuries: inj, rosters: {}, staleOdds: []
  });
  DATA.liveTeamRow = stRow;
}

/* ---- build players + props from real game logs ---- */
function stdev(a){ if (a.length < 2) return 0; const m = avg(a); return Math.sqrt(a.reduce((s,v) => s + (v - m) ** 2, 0) / (a.length - 1)); }
function buildLivePlayers(){
  const out = [];
  (LIVE.players || []).forEach(p => {
    const gm = GAME_OF_TEAM[p.team]; if (!gm) return;
    const played = arr => (arr || []).filter(g => (g.min || 0) > 0);
    const cur = played(p.season), last = played(p.lastSeason);
    const recent = [...cur, ...last];                                  // newest first
    if (!recent.length) return;
    const r10 = recent.slice(0, 10);
    const mins = Math.round(avg(r10.map(g => g.min || 0)));
    const wCur = Math.min(1, cur.length / 10);                         // trust this season more as it fills up
    const seasonAvg = m => { const a = cur.length ? avg(cur.map(g => g[m])) : 0, b = last.length ? avg(last.map(g => g[m])) : a; return wCur * a + (1 - wCur) * b; };
    const avgs = {}; MARKETS.forEach(m => avgs[m] = seasonAvg(m));
    out.push({name: p.name, pos: p.pos || "", team: p.team, min: mins, projMin: mins, avgs, boost: null, scenario: null,
              status: statusOf(p.name), log: r10, recent, curGames: cur.length, ...gm});
  });
  return out;
}

function buildLiveProp(pl, market){
  const myLines = loadMyLines();
  const key = `${pl.name}|${market}`;
  const mine = myLines[key];
  const refs = (LIVE.props || []).filter(x => x.key === normName(pl.name) && x.market === market && x.game === pl.g.id);
  let src = null;
  if (mine) src = {line: mine.line, over: mine.over, under: mine.under, book: mine.book || "Your price", updated: mine.at, source: "manual"};
  else if (refs.length){
    // consensus reference: the most common line across US books, then that line's average price
    const cnt = {}; refs.forEach(r => cnt[r.line] = (cnt[r.line] || 0) + 1);
    const line = +Object.entries(cnt).sort((a,b) => b[1] - a[1] || a[0] - b[0])[0][0];
    const at = refs.filter(r => r.line === line);
    const am = xs => { const p = avg(xs.map(americanToProb)); return Math.round(probToAmericanRaw(p)); };
    src = {line, over: am(at.map(r => r.over)), under: am(at.map(r => r.under)), book: at.map(r => r.book).join(", "),
           updated: at.map(r => r.updated).sort().pop() || (LIVE.sections.odds || {}).fetchedAt, source: "ref"};
  }
  // ---- projection from real logs
  const recent = pl.recent.map(g => g[market]);
  const last10 = pl.log.map(g => g[market]);
  const seasonAvg = pl.avgs[market];
  const l10 = last10.length ? avg(last10) : seasonAvg;
  const base = Math.max(0.1, 0.55 * seasonAvg + 0.45 * l10);
  const h2hGames = pl.recent.filter(g => g.opp === pl.opp).slice(0, 4);
  const h2h = h2hGames.map(g => g[market]);
  const n = h2h.length, h2hAvg = n ? avg(h2h) : base;
  const w = n ? H2H_MAX_WEIGHT * n / (n + H2H_K) : 0;
  const projection = base * (1 - w) + h2hAvg * w;
  const sd = Math.max(SD_FLOOR[market], 0.5 * stdev(recent.slice(0, 20)) + 0.5 * CV[market] * projection);
  const p = {id: hashStr(pl.name + market) % 1e9, player: pl.name, team: pl.team, opp: pl.opp, game: pl.g.id, pos: pl.pos, market,
             base, h2h, h2hDates: h2hGames.map(g => g.d), n, h2hAvg, w, h2hAdj: projection - base, role: null, projection, sd, last10,
             minutes: pl.projMin, seasonMin: pl.projMin, status: pl.status, seasonAvg, live: true};
  if (!src) return {...p, noLine: true};
  return {...p, line: src.line, over: src.over, under: src.under, book: src.book, source: src.source, oddsUpdated: src.updated || DATA.meta.generatedAt};
}
