/*
 * Meccsállapot két nyilvános eredményforrásból (mindkettő CORS: *):
 *   - Sofascore (www.sofascore.com/api/v1/sport/<sport>/events/live): az éppen zajló
 *     meccsek sportáganként, állással és játékrésszel - szinte minden sportágra;
 *   - ESPN (site.api.espn.com): a mai meccsek pre / in / post állapottal - foci, NFL,
 *     NBA/WNBA, NHL, MLB, UFC; ebből látszik biztosan, ha egy meccs véget ért.
 * A streamed.pk „élő” listája a befejezett meccseket is sokáig benne hagyja - ezzel
 * szűrhetők ki. Párosítás csapatnevek alapján (ékezet-, írásjel- és „FC”-független).
 */
(function (global) {
	'use strict';

	var SOFA = 'https://www.sofascore.com/api/v1/sport/';
	var ESPN = 'https://site.api.espn.com/apis/site/v2/sports/';
	var SOFA_SPORT = {
		'football': 'football', 'basketball': 'basketball', 'hockey': 'ice-hockey',
		'american-football': 'american-football', 'baseball': 'baseball', 'tennis': 'tennis',
		'darts': 'darts', 'cricket': 'cricket', 'rugby': 'rugby', 'fight': 'mma',
		'afl': 'aussie-rules', 'billiards': 'snooker'
	};
	var ESPN_LEAGUES = {
		'football': ['soccer/all'],
		'american-football': ['football/nfl', 'football/college-football'],
		'basketball': ['basketball/nba', 'basketball/wnba'],
		'hockey': ['hockey/nhl'],
		'baseball': ['baseball/mlb'],
		'fight': ['mma/ufc']
	};
	// szokásos hossz (óra) a kezdéstől, ráhagyással - ha semmi más nem segít
	var DURATION_H = {
		'football': 2.4, 'basketball': 3, 'american-football': 4, 'hockey': 3.2,
		'baseball': 4, 'tennis': 4, 'fight': 6, 'motor-sports': 3, 'rugby': 2.4,
		'golf': 10, 'billiards': 6, 'afl': 3.2, 'darts': 6, 'cricket': 9, 'other': 4
	};
	// ennyi idővel a kezdés után már a Sofascore élő listájában kellene lennie
	var SOFA_GRACE_MS = 20 * 60000;
	var CACHE_MS = 90000;
	var STOP = {fc: 1, cf: 1, sc: 1, afc: 1, the: 1, of: 1, club: 1, de: 1, republic: 1, cd: 1, ac: 1};
	var PERIOD_HU = {
		'1st half': '1. félidő', '2nd half': '2. félidő', 'halftime': 'szünet', 'pause': 'szünet',
		'1st quarter': '1. negyed', '2nd quarter': '2. negyed', '3rd quarter': '3. negyed',
		'4th quarter': '4. negyed', '1st period': '1. harmad', '2nd period': '2. harmad',
		'3rd period': '3. harmad', 'overtime': 'hosszabbítás', 'extra time': 'hosszabbítás',
		'awaiting extra time': 'hosszabbításra vár', 'penalties': 'tizenegyesek',
		'1st set': '1. szett', '2nd set': '2. szett', '3rd set': '3. szett',
		'4th set': '4. szett', '5th set': '5. szett', 'started': 'elkezdődött'
	};

	var cache = {};       // url -> {at, promise}
	var sofaLive = {};    // sport -> események (null: nem jött le)
	var espnEvents = {};  // liga -> események

	// --- nevek ------------------------------------------------------------------
	function norm(s) {
		s = String(s || '').toLowerCase();
		if (s.normalize) s = s.normalize('NFD').replace(/[̀-ͯ]/g, '');
		return s.replace(/[^a-z0-9 ]+/g, ' ').trim();
	}

	function tokens(s) {
		return norm(s).split(/\s+/).filter(function (t) { return t && !STOP[t]; });
	}

	function subset(a, b) {
		if (!a.length) return false;
		for (var i = 0; i < a.length; i++) if (b.indexOf(a[i]) < 0) return false;
		return true;
	}

	function sameTeam(name, cands) {
		var t = tokens(name);
		if (!t.length) return false;
		for (var i = 0; i < cands.length; i++) {
			var c = tokens(cands[i]);
			if (c.length && (subset(t, c) || subset(c, t))) return true;
		}
		return false;
	}

	function teamNames(m) {
		var t = m.teams || {};
		if (t.home && t.home.name && t.away && t.away.name) return [t.home.name, t.away.name];
		var parts = String(m.title || '').split(/\s+(?:vs\.?|v|@)\s+/i);
		return parts.length === 2 ? parts : null;
	}

	// a két csapat (bármilyen sorrendben) egyezik-e: null | {swapped}. Ha csak az egyik
	// név egyezik (pl. „LA Chargers” / „Los Angeles Chargers”), a kezdési időnek is
	// egyeznie kell (fél órán belül).
	function pair(names, home, away, startDiff) {
		var h0 = sameTeam(names[0], home), a1 = sameTeam(names[1], away);
		var a0 = sameTeam(names[0], away), h1 = sameTeam(names[1], home);
		var close = startDiff < 30 * 60000;
		if (h0 && a1) return {swapped: false};
		if (a0 && h1) return {swapped: true};
		if (close && (h0 || a1)) return {swapped: false};
		if (close && (a0 || h1)) return {swapped: true};
		return null;
	}

	// --- letöltés ----------------------------------------------------------------
	function getCached(url) {
		var c = cache[url];
		var now = Date.now();
		if (c && now - c.at < CACHE_MS) return c.promise;
		var p = fetch(url).then(function (r) {
			if (!r.ok) throw new Error('HTTP ' + r.status);
			return r.json();
		});
		cache[url] = {at: now, promise: p};
		p.catch(function () { delete cache[url]; });
		return p;
	}

	function ymd(d) {
		return d.getUTCFullYear() + ('0' + (d.getUTCMonth() + 1)).slice(-2) + ('0' + d.getUTCDate()).slice(-2);
	}

	function loadSofa(sport) {
		return getCached(SOFA + sport + '/events/live').then(function (d) {
			sofaLive[sport] = (d.events || []).map(function (e) {
				var h = e.homeTeam || {}, a = e.awayTeam || {};
				return {
					home: [h.name, h.shortName], away: [a.name, a.shortName],
					hs: (e.homeScore || {}).current, as: (e.awayScore || {}).current,
					status: e.status || {}, time: e.time || {}, start: (e.startTimestamp || 0) * 1000
				};
			});
		}, function () {
			sofaLive[sport] = null;
		});
	}

	function loadEspn(league) {
		var now = new Date();
		var days = [ymd(now)];
		if (now.getUTCHours() < 10) days.push(ymd(new Date(now.getTime() - 86400000)));
		return Promise.all(days.map(function (day) {
			return getCached(ESPN + league + '/scoreboard?dates=' + day + '&limit=500')
				.then(function (d) { return d.events || []; }, function () { return []; });
		})).then(function (lists) {
			var out = [];
			lists.forEach(function (events) {
				events.forEach(function (e) {
					var comp = (e.competitions || [])[0];
					if (!comp || !comp.competitors || comp.competitors.length !== 2) return;
					var type = ((comp.status || e.status || {}).type) || {};
					var home = null, away = null;
					comp.competitors.forEach(function (x) { if (x.homeAway === 'home') home = x; else away = x; });
					if (!home || !away) return;
					var ht = home.team || {}, at = away.team || {};
					out.push({
						date: Date.parse(e.date) || 0, state: type.state || '',
						home: [ht.displayName, ht.shortDisplayName, ht.location],
						away: [at.displayName, at.shortDisplayName, at.location],
						hs: home.score, as: away.score
					});
				});
			});
			espnEvents[league] = out;
		});
	}

	// Az adott sportágak adatainak frissítése (a kész ígéret után a status() válaszol).
	function remember(categories) {
		var jobs = [];
		categories.forEach(function (c) {
			if (SOFA_SPORT[c]) jobs.push(loadSofa(SOFA_SPORT[c]));
			(ESPN_LEAGUES[c] || []).forEach(function (l) { jobs.push(loadEspn(l)); });
		});
		return Promise.all(jobs);
	}

	// --- állapot -----------------------------------------------------------------
	function sofaDetail(ev, category) {
		var desc = String(ev.status.description || '');
		var hu = PERIOD_HU[desc.toLowerCase()];
		if (!hu) {   // „4th inning”, „3rd round” … -> „4. inning”, „3. menet”
			var mm = /^(\d+)(?:st|nd|rd|th)\s+(\w+)/i.exec(desc);
			var word = mm && {inning: 'inning', quarter: 'negyed', half: 'félidő', period: 'harmad',
				set: 'szett', round: 'menet', map: 'pálya', game: 'játszma', leg: 'leg'}[mm[2].toLowerCase()];
			hu = word ? mm[1] + '. ' + word : desc;
		}
		var t = ev.time || {};
		if (category === 'football' && t.currentPeriodStartTimestamp &&
				(ev.status.code === 6 || ev.status.code === 7)) {
			var min = Math.floor((Date.now() / 1000 - t.currentPeriodStartTimestamp) / 60) + 1;
			if (ev.status.code === 7) min += 45;
			if (min > 0 && min < 130) return min + '. perc';
		}
		return hu;
	}

	function score(a, b) {
		return (a !== undefined && a !== null && b !== undefined && b !== null) ? a + '–' + b : '';
	}

	// {state: 'pre'|'in'|'post', score: '2–1', detail: '67. perc'} vagy null
	function status(m) {
		var names = teamNames(m);
		var now = Date.now();
		if (names) {
			// 1) Sofascore: most zajlik
			var sport = SOFA_SPORT[m.category];
			var live = sport ? sofaLive[sport] : null;
			if (live) {
				for (var i = 0; i < live.length; i++) {
					var p = pair(names, live[i].home, live[i].away, Math.abs(live[i].start - (m.date || 0)));
					if (!p) continue;
					var ev = live[i];
					return {state: 'in', detail: sofaDetail(ev, m.category),
						score: p.swapped ? score(ev.as, ev.hs) : score(ev.hs, ev.as)};
				}
			}
			// 2) ESPN: mai meccsek pontos állapottal
			var best = null;
			(ESPN_LEAGUES[m.category] || []).forEach(function (l) {
				(espnEvents[l] || []).forEach(function (e) {
					var q = pair(names, e.home, e.away, Math.abs((e.date || 0) - (m.date || 0)));
					if (!q) return;
					var diff = Math.abs((e.date || 0) - (m.date || 0));
					if (!best || diff < best.diff) best = {e: e, diff: diff, swapped: q.swapped};
				});
			});
			if (best && best.diff < 12 * 3600000) {
				var e = best.e;
				return {state: e.state, detail: '',
					score: e.state === 'pre' ? '' : (best.swapped ? score(e.as, e.hs) : score(e.hs, e.as))};
			}
			// 3) a Sofascore ismeri a sportágat, de a meccs nincs az élők között
			if (live && m.date && now - m.date > SOFA_GRACE_MS) {
				return {state: 'post', detail: '', score: ''};
			}
		}
		return null;
	}

	// becslés ESPN / Sofascore nélkül: befejeződött-e a szokásos meccshossz alapján
	function estimateEnded(m, now) {
		if (!m.date) return false;              // 0 = 0-24 órás csatorna
		var h = DURATION_H[m.category] || DURATION_H.other;
		return (now || Date.now()) - m.date > h * 3600000;
	}

	global.Scores = {remember: remember, status: status, estimateEnded: estimateEnded};
})(window);
