/*
 * WatchSports (webOS) - Netflix-stílusú felület a watchsports.su műsorához.
 *
 * A watchsports.su főoldalának HTML-jéből olvassa ki a sportágakat és meccseket (élő
 * állapot, kezdési idő, csapatok, adásszám), és vízszintes sorokban mutatja: elöl az
 * „Élő most” sor, utána sportáganként. A kijelölt meccs a nagy hero-részben látszik.
 * OK egy meccsen: adatlap a meccsoldal adásaival; OK egy adáson: az adás oldala az app
 * ablakában nyílik meg (az adásoldalak nem engedik a beágyazást), a piros gombbal a TV
 * böngészőjében.
 *
 * Az oldal nem küld CORS-fejlécet, ezért a TV-n a lekérés a háttérszolgáltatáson megy
 * (luna://hu.tomszo.watchsports.service/get); ha az nem válaszol, közvetlen fetch.
 * A csapatlogók az ESPN képszerveréről jönnek (a watchsports.su képei is onnan valók,
 * de a saját szerverük a TV-s appnak nem adja ki őket - Cross-Origin-Resource-Policy).
 *
 * Vissza gomb: nincs disableBackHistoryAPI, így a webOS a history-ban lép vissza. Az
 * adatlap a címben (#g=…) él: az adatlap Vissza gombra bezárul, egy adásoldalról
 * visszalépve pedig az app ugyanott nyílik újra. A kezdőoldalon a Vissza kilép.
 */
(function () {
	'use strict';

	var BASE = 'https://watchsports.su';
	var SERVICE = 'luna://hu.tomszo.watchsports.service/get';
	var LOGO = 'https://a.espncdn.com/combiner/i?img=';
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, ESC: 27, BACKSPACE: 8, RED: 403};
	var REFRESH_MS = 60000;
	var TIMEOUT = 25000;
	var MONTHS = ['jan.', 'febr.', 'márc.', 'ápr.', 'máj.', 'jún.', 'júl.', 'aug.', 'szept.',
		'okt.', 'nov.', 'dec.'];

	// sportág: magyar név, kártyaszínek (c1 -> c2)
	var SPORTS = {
		'football': ['Labdarúgás', '#1f6b3a', '#0e2a18'], 'soccer': ['Labdarúgás', '#1f6b3a', '#0e2a18'],
		'tennis': ['Tenisz', '#5d7a1f', '#1f2a0c'], 'nfl': ['NFL', '#7a3b1f', '#2a140b'],
		'cfb': ['Egyetemi amerikai foci', '#7a3b1f', '#2a140b'], 'ufl': ['UFL', '#7a3b1f', '#2a140b'],
		'nba': ['NBA', '#b4531a', '#3a1a08'], 'wnba': ['WNBA', '#b4531a', '#3a1a08'],
		'college-basketball': ['Egyetemi kosárlabda', '#b4531a', '#3a1a08'],
		'fiba': ['FIBA kosárlabda', '#b4531a', '#3a1a08'],
		'nhl': ['NHL', '#2b6c99', '#0c2233'], 'mlb': ['MLB', '#2a3f8f', '#0d1430'],
		'llws': ['Little League', '#2a3f8f', '#0d1430'],
		'cricket': ['Krikett', '#1f7a6e', '#0b2a26'], 'golf': ['Golf', '#3d8a3d', '#112a11'],
		'racing': ['Motorsport', '#9a1f1f', '#2e0b0b'], 'f1': ['Formula 1', '#9a1f1f', '#2e0b0b'],
		'nascar': ['NASCAR', '#9a1f1f', '#2e0b0b'], 'indycar': ['IndyCar', '#9a1f1f', '#2e0b0b'],
		'nhra': ['NHRA', '#9a1f1f', '#2e0b0b'],
		'mma': ['MMA', '#6b1f2e', '#22090f'], 'boxing': ['Boksz', '#6b1f2e', '#22090f'],
		'ufc': ['UFC', '#6b1f2e', '#22090f'], 'wwe': ['WWE', '#5a2a7a', '#1c0d26'],
		'aew': ['AEW', '#5a2a7a', '#1c0d26'], 'rugby': ['Rögbi', '#5a5a1f', '#1e1e0a'],
		'afl': ['Ausztrál futball', '#5a5a1f', '#1e1e0a'],
		'volleyball': ['Röplabda', '#1f5a7a', '#0a1e2a'], 'olympics': ['Olimpia', '#2a5a9a', '#0c1c33']
	};
	var LIVE_COLORS = ['#8a1015', '#2a0507'];

	var rows = [];          // [{key, name, games, sel, el, track}]
	var activeRow = 0;
	var loaded = false;
	var detail = null;      // {game, streams, sel, el}
	var detailReq = 0;
	var heroTimer = null;
	var toastTimer = null;
	var pending = [];       // a luna-hívások objektumai a válaszig élve maradnak

	// --- segédek -------------------------------------------------------------
	function $(sel, root) { return (root || document).querySelector(sel); }
	function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

	function el(tag, cls, text) {
		var e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null && text !== '') e.textContent = text;
		return e;
	}

	function txt(node) { return node ? node.textContent.replace(/\s+/g, ' ').trim() : ''; }
	function pad(n) { return (n < 10 ? '0' : '') + n; }

	function sameDay(a, b) {
		return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() &&
			a.getDate() === b.getDate();
	}

	function whenText(d) {
		if (!d || isNaN(d.getTime())) return '';
		var now = new Date();
		var tom = new Date(now.getTime() + 86400000);
		var hm = pad(d.getHours()) + ':' + pad(d.getMinutes());
		if (sameDay(d, now)) return 'ma ' + hm;
		if (sameDay(d, tom)) return 'holnap ' + hm;
		return MONTHS[d.getMonth()] + ' ' + d.getDate() + '. ' + hm;
	}

	// a site saját szövegei (55', Halftime, Round 4 - In Progress …) magyarítva
	function liveText(s) {
		if (!s) return 'Élőben';
		var m = /^(\d+)(?:\+(\d+))?'$/.exec(s);
		if (m) return m[1] + (m[2] ? '+' + m[2] : '') + '. perc';
		return s.replace(/^Live$/i, 'Élőben').replace(/Halftime/i, 'Félidő')
			.replace(/In Progress/i, 'folyamatban').replace(/^Round (\d+)/i, '$1. kör')
			.replace(/^(\d+:\d+) - (\d+)(st|nd|rd|th)$/i, '$2. játékrész · $1')
			.replace(/^(\d)(st|nd|rd|th) (Period|Quarter|Half)/i, '$1. játékrész')
			.replace(/^(Top|Bot|Bottom|Mid|End) (\d+)(st|nd|rd|th)/i, '$2. inning')
			.replace(/^Lap (\d+) \/ (\d+)/i, '$1. / $2 kör')
			.replace(/^Final/i, 'Vége');
	}

	function sportInfo(key) {
		return SPORTS[key] || [key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Sport',
			'#3a4a6b', '#141a26'];
	}

	// /img/i?p=%2Fi%2Fteamlogos%2Fnfl%2F500%2Fkc.png&w=32  ->  ESPN-kép
	function logoUrl(src, size) {
		if (!src) return '';
		var m = /[?&]p=([^&]+)/.exec(src);
		if (!m) return '';
		var path;
		try { path = decodeURIComponent(m[1]); } catch (e) { return ''; }
		if (!/^\/i\//.test(path)) return '';
		return LOGO + path + '&w=' + size + '&h=' + size;
	}

	function initials(name) {
		var p = (name || '?').replace(/[^\wÀ-ž ]/g, ' ').trim().split(/\s+/);
		return ((p[0] || '?').charAt(0) + (p.length > 1 ? p[p.length - 1].charAt(0) : '')).toUpperCase();
	}

	function toast(msg, ms) {
		var t = $('#toast');
		t.textContent = msg;
		t.className = 'on';
		clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { t.className = ''; }, ms || 3500);
	}

	function status(s) { $('#status').textContent = s || ''; }

	// --- HTTP ----------------------------------------------------------------
	function onTV() { return typeof window.PalmServiceBridge === 'function'; }

	function viaService(url) {
		return new Promise(function (resolve, reject) {
			var bridge = new window.PalmServiceBridge();
			var done = false;
			pending.push(bridge);
			var timer = setTimeout(function () {
				if (!done) { done = true; reject(new Error('a szolgáltatás nem válaszol')); }
			}, TIMEOUT + 5000);
			bridge.onservicecallback = function (msg) {
				var i = pending.indexOf(bridge);
				if (i >= 0) pending.splice(i, 1);
				if (done) return;
				done = true;
				clearTimeout(timer);
				var res;
				try { res = JSON.parse(msg); } catch (e) { return reject(new Error('hibás válasz')); }
				if (res.returnValue === false) return reject(new Error(res.errorText || 'szolgáltatáshiba'));
				if (res.status !== 200) return reject(new Error('HTTP ' + res.status));
				resolve(res.body || '');
			};
			bridge.call(SERVICE, JSON.stringify({url: url}));
		});
	}

	function viaFetch(url) {
		var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
		var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, TIMEOUT);
		return fetch(url, {credentials: 'omit', cache: 'no-store', signal: ctrl ? ctrl.signal : undefined})
			.then(function (r) {
				clearTimeout(timer);
				if (!r.ok) throw new Error('HTTP ' + r.status);
				return r.text();
			}, function (err) {
				clearTimeout(timer);
				throw new Error(err && err.name === 'AbortError' ? 'időtúllépés' : 'a kérés nem ment át');
			});
	}

	function getPage(path) {
		var url = BASE + path;
		if (!onTV()) return viaFetch(url);
		return viaService(url).catch(function (err) {
			return viaFetch(url).catch(function () { throw err; });
		});
	}

	function parseHTML(html) {
		return new DOMParser().parseFromString(html, 'text/html');
	}

	// --- főoldal feldolgozása ------------------------------------------------
	function parseGame(a, sportKey) {
		var href = a.getAttribute('href') || '';
		var live = /\bis-live\b/.test(a.className) || !!$('.status-live', a);
		var timeEl = $('time[datetime]', a);
		var start = timeEl ? new Date(timeEl.getAttribute('datetime')) : null;
		var teams = $$('.team-line', a).map(function (t) {
			var img = $('img', t);
			return {name: txt($('.team-name', t)), logo: img ? img.getAttribute('src') : ''};
		}).filter(function (t) { return t.name; });
		var streams = parseInt(txt($('.game-streams', a)), 10) || 0;
		return {
			href: href,
			sport: sportKey || (href.split('/')[1] || ''),
			live: live,
			liveText: live ? txt($('.status-live', a)) : '',
			statusText: txt($('.game-status', a)),
			start: start && !isNaN(start.getTime()) ? start : null,
			teams: teams,
			event: txt($('.event-name', a)),
			detail: txt($('.game-detail', a)),
			streams: streams
		};
	}

	function gameTitle(g) {
		if (g.teams.length >= 2) return g.teams[0].name + ' – ' + g.teams[1].name;
		return g.event || (g.teams[0] && g.teams[0].name) || g.detail || 'Esemény';
	}

	function gameWhen(g) {
		if (g.live) return liveText(g.liveText);
		return whenText(g.start) || g.statusText;
	}

	function parseHome(html) {
		var doc = parseHTML(html);
		var sections = [];
		var all = [];
		$$('#sports .sport-section', doc).forEach(function (sec) {
			var btn = $('.sport-header', sec);
			var ctrl = btn ? (btn.getAttribute('aria-controls') || '') : '';
			var key = ctrl.replace(/-games$/, '');
			var games = $$('a.game-row', sec).map(function (a) { return parseGame(a, key); })
				.filter(function (g) { return g.href; });
			if (!games.length) return;
			// élők elöl, utána kezdési idő szerint (a site sorrendjét megtartva)
			games.forEach(function (g, i) { g.order = i; });
			games.sort(function (a, b) {
				if (a.live !== b.live) return a.live ? -1 : 1;
				return a.order - b.order;
			});
			var info = sportInfo(key);
			sections.push({key: key, name: info[0], siteName: txt($('.sport-name', sec)), games: games});
			all = all.concat(games);
		});
		var live = all.filter(function (g) { return g.live; });
		live.sort(function (a, b) { return b.streams - a.streams; });
		var out = [];
		if (live.length) out.push({key: '_live', name: 'Élő most', games: live});
		var soon = all.filter(function (g) {
			return !g.live && g.start && g.start.getTime() - Date.now() < 3 * 3600000;
		}).sort(function (a, b) { return a.start - b.start; });
		if (soon.length) out.push({key: '_soon', name: 'Hamarosan kezdődik', games: soon.slice(0, 30)});
		return out.concat(sections);
	}

	// --- kártyák és sorok ----------------------------------------------------
	function logoImg(src, size, fallbackName) {
		var url = logoUrl(src, size);
		if (!url) return el('div', 'ini', initials(fallbackName));
		var img = el('img');
		img.alt = '';
		img.onerror = function () {
			if (!img.parentNode) return;
			// név nélkül (adatlap) a hibás logó egyszerűen eltűnik
			if (fallbackName) img.parentNode.replaceChild(el('div', 'ini', initials(fallbackName)), img);
			else img.parentNode.removeChild(img);
		};
		img.src = url;
		return img;
	}

	function makeCard(g, rowKey) {
		var c = el('div', 'card');
		var info = g.live && rowKey === '_live' ? null : sportInfo(g.sport);
		var colors = info ? [info[1], info[2]] : sportInfo(g.sport).slice(1);
		c.style.setProperty('--c1', colors[0]);
		c.style.setProperty('--c2', colors[1]);
		if (g.teams.length >= 2 && (g.teams[0].logo || g.teams[1].logo)) {
			var lg = el('div', 'logos');
			lg.appendChild(logoImg(g.teams[0].logo, 160, g.teams[0].name));
			lg.appendChild(el('div', 'vs', 'VS'));
			lg.appendChild(logoImg(g.teams[1].logo, 160, g.teams[1].name));
			c.appendChild(lg);
		} else {
			c.appendChild(el('div', 'ev', g.event || gameTitle(g)));
		}
		if (g.live) c.appendChild(el('div', 'live', 'ÉLŐ'));
		if (g.streams) c.appendChild(el('div', 'badge-n', g.streams + ' adás'));
		var names = el('div', 'names');
		names.appendChild(el('div', 't', g.teams.length >= 2 ? gameTitle(g) : (g.detail || gameTitle(g))));
		var sub = gameWhen(g);
		if (rowKey && rowKey.charAt(0) === '_') sub = sportInfo(g.sport)[0] + ' · ' + sub;
		else if (g.teams.length >= 2 && g.detail) sub += ' · ' + g.detail;
		names.appendChild(el('div', 's', sub));
		c.appendChild(names);
		return c;
	}

	function render(prevHref) {
		var inner = $('#rows .rows-inner');
		inner.innerHTML = '';
		if (!rows.length) {
			inner.appendChild(el('div', 'empty', 'Most nincs meccs a műsorban – később próbáld újra.'));
			return;
		}
		rows.forEach(function (r, ri) {
			var row = el('section', 'row');
			var h = el('h2', null, r.name);
			h.appendChild(el('span', 'cnt', r.games.length + ''));
			row.appendChild(h);
			var track = el('div', 'track');
			var ti = el('div', 'track-inner');
			r.games.forEach(function (g, gi) {
				var c = makeCard(g, r.key);
				c.addEventListener('mouseenter', function () { focusCard(ri, gi); });
				c.addEventListener('click', function () { focusCard(ri, gi); openGame(g); });
				ti.appendChild(c);
			});
			track.appendChild(ti);
			row.appendChild(track);
			inner.appendChild(row);
			r.el = row;
			r.track = ti;
			r.sel = Math.min(r.sel || 0, r.games.length - 1);
		});
		// a korábban kijelölt meccs megtartása (frissítés / visszatérés után)
		// (elsőként az aktív sorban keressük, hogy az „Élő most” sorból ne ugorjon el)
		if (activeRow >= rows.length) activeRow = 0;
		if (prevHref) {
			var order = [activeRow];
			for (var i = 0; i < rows.length; i++) if (i !== activeRow) order.push(i);
			order.some(function (ri) {
				for (var j = 0; j < rows[ri].games.length; j++) {
					if (rows[ri].games[j].href === prevHref) { activeRow = ri; rows[ri].sel = j; return true; }
				}
				return false;
			});
		}
		rows.forEach(function (r, i) { paintRow(i); });
		layout();
		showHero(true);
	}

	function paintRow(ri) {
		var r = rows[ri];
		if (!r || !r.track) return;
		var cards = r.track.children;
		for (var i = 0; i < cards.length; i++) {
			cards[i].className = 'card' + (i === r.sel && ri === activeRow ? ' sel' : '');
		}
		r.el.className = 'row' + (ri === activeRow ? ' active' : '');
		// vízszintes görgetés: a kijelölt kártya a sor elejéhez közel (1 kártyányi előre)
		var w = 352 + 16;
		var visible = 4;
		var first = Math.max(0, Math.min(r.sel - 1, r.games.length - visible));
		if (r.sel === 0) first = 0;
		r.track.style.transform = 'translateX(' + (-first * w) + 'px)';
	}

	function layout() {
		$('#rows .rows-inner').style.transform = 'translateY(' + (-activeRow * 300) + 'px)';
	}

	function current() {
		var r = rows[activeRow];
		return r ? r.games[r.sel] : null;
	}

	function focusCard(ri, gi) {
		if (!rows[ri]) return;
		var prev = activeRow;
		activeRow = ri;
		rows[ri].sel = Math.max(0, Math.min(gi, rows[ri].games.length - 1));
		if (prev !== ri) paintRow(prev);
		paintRow(ri);
		layout();
		showHero(false);
	}

	// --- hero ----------------------------------------------------------------
	function setSportColor(target, g) {
		var c = g.live ? LIVE_COLORS[0] : sportInfo(g.sport)[1];
		target.style.setProperty('--sport', c);
	}

	function showHero(now) {
		clearTimeout(heroTimer);
		var bd = $('#backdrop .bd-logos');
		var apply = function () {
			var g = current();
			if (!g) return;
			$('.h-live').className = 'h-live' + (g.live ? ' on' : '');
			$('.h-sport').textContent = sportInfo(g.sport)[0];
			$('.h-time').textContent = gameWhen(g);
			$('.h-title').textContent = g.teams.length >= 2 ? g.teams[0].name + ' vs ' + g.teams[1].name : gameTitle(g);
			$('.h-detail').textContent = g.teams.length >= 2 ? g.detail : (g.event ? g.detail : '');
			$('.h-teams').textContent = '';
			$('.h-streams').textContent = g.streams ? g.streams + ' adás' : 'Részletek';
			setSportColor(document.documentElement, g);
			var a = $('.bd-a'), b = $('.bd-b');
			var la = g.teams[0] ? logoUrl(g.teams[0].logo, 500) : '';
			var lb = g.teams[1] ? logoUrl(g.teams[1].logo, 500) : '';
			if (la) a.src = la; else a.removeAttribute('src');
			if (lb) b.src = lb; else b.removeAttribute('src');
			bd.className = 'bd-logos' + ((la && !lb) || (!la && lb) ? ' single' : '');
		};
		if (now) return apply();
		bd.className += ' fade';
		heroTimer = setTimeout(apply, 180);
	}

	// --- adatlap -------------------------------------------------------------
	function openGame(g) {
		if (!g) return;
		try {
			sessionStorage.setItem('ws.game', JSON.stringify(g));
		} catch (e) {}
		location.hash = 'g=' + encodeURIComponent(g.href);
	}

	function hashGame() {
		var m = /^#g=(.+)$/.exec(location.hash);
		if (!m) return null;
		try { return decodeURIComponent(m[1]); } catch (e) { return null; }
	}

	function findGame(href) {
		for (var i = 0; i < rows.length; i++) {
			for (var j = 0; j < rows[i].games.length; j++) {
				if (rows[i].games[j].href === href) return rows[i].games[j];
			}
		}
		try {
			var s = JSON.parse(sessionStorage.getItem('ws.game') || 'null');
			if (s && s.href === href) {
				if (s.start) s.start = new Date(s.start);
				return s;
			}
		} catch (e) {}
		return {href: href, sport: href.split('/')[1] || '', teams: [], live: false, event: '', detail: '', streams: 0};
	}

	function routeChanged() {
		var href = hashGame();
		if (href && /^\/[\w.\/-]+$/.test(href)) showDetail(findGame(href));
		else hideDetail();
	}

	function showDetail(g) {
		var d = $('#detail');
		var my = ++detailReq;
		detail = {game: g, items: [], sel: 0};
		setSportColor(d, g);
		fillDetailHead(g, null);
		var list = $('.d-list', d);
		list.innerHTML = '';
		list.appendChild(el('div', 'd-empty', 'Adások betöltése…'));
		d.className = 'on';
		getPage(g.href).then(function (html) {
			if (my !== detailReq || !detail) return;
			var page = parseGamePage(html);
			fillDetailHead(g, page);
			fillStreams(page.streams);
		}, function (err) {
			if (my !== detailReq || !detail) return;
			list.innerHTML = '';
			list.appendChild(el('div', 'd-empty', 'Nem sikerült betölteni a meccsoldalt (' + err.message + ').'));
			fillStreams([]);
		});
	}

	function parseGamePage(html) {
		var doc = parseHTML(html);
		var mu = $('.sp-matchup', doc);
		var page = {title: txt($('.breadcrumbs [aria-current]', doc)), logos: [], meta: [], live: false,
			when: '', streams: []};
		if (mu) {
			page.logos = $$('img', mu).map(function (i) { return i.getAttribute('src'); });
			// a fogadási sorok (Line, O/U - a site sr-only címkéjük alapján) kimaradnak
			[$('.sp-game-note', mu), $('.sp-round-badge', mu)].concat($$('.sp-game-meta li', mu)
				.filter(function (li) { return !$('.sr-only', li); }))
				.forEach(function (n) { var t = txt(n); if (t && page.meta.indexOf(t) < 0) page.meta.push(t); });
			var liveEl = $('[class*="status-live"], [class*="sp-live"]', mu);
			page.live = !!liveEl;
			if (liveEl) page.when = liveText(txt(liveEl));
			var t = $('time[datetime]', mu);
			if (!page.when && t) page.when = whenText(new Date(t.getAttribute('datetime')));
		}
		$$('.sp-stream-list li.stream', doc).forEach(function (li) {
			var a = $('a.stream-link', li);
			if (!a) return;
			var url = a.getAttribute('href') || '';
			if (!/^https?:\/\//.test(url)) return;
			var who = $('.streamer', a);
			var name = '';
			if (who) {
				for (var n = who.firstChild; n; n = n.nextSibling) {
					if (n.nodeType === 3) name += n.textContent;
				}
			}
			page.streams.push({
				url: url,
				name: name.trim() || txt(who) || 'Adás',
				channel: txt($('.chan', a)),
				tags: $$('.meta-tag', a).filter(function (m) { return !/compat-tag/.test(m.className); })
					.map(function (m) { return txt(m); }).filter(Boolean),
				votes: parseInt(txt($('.vote-count', li)), 10) || 0
			});
		});
		return page;
	}

	function fillDetailHead(g, page) {
		var d = $('#detail');
		var logos = $('.d-logos', d);
		logos.innerHTML = '';
		var srcs = page && page.logos.length ? page.logos : g.teams.map(function (t) { return t.logo; });
		srcs.slice(0, 2).forEach(function (s) {
			if (logoUrl(s, 300)) logos.appendChild(logoImg(s, 300, ''));
		});
		var badges = $('.d-badges', d);
		badges.innerHTML = '';
		var live = page ? page.live || g.live : g.live;
		if (live) badges.appendChild(el('span', 'live', 'ÉLŐ'));
		badges.appendChild(el('span', null, sportInfo(g.sport)[0]));
		var when = page && page.when ? page.when : (g.href && (g.live || g.start) ? gameWhen(g) : '');
		if (when) badges.appendChild(el('span', null, '· ' + when));
		var title = g.teams && g.teams.length >= 2 ? g.teams[0].name + ' vs ' + g.teams[1].name :
			(g.event || (page && page.title) || 'Meccs');
		$('.d-title', d).textContent = title;
		var meta = page && page.meta.length ? page.meta.join(' · ') : (g.detail || '');
		$('.d-meta', d).textContent = meta;
	}

	function fillStreams(streams) {
		var g = detail.game;
		var items = streams.slice();
		items.push({site: true, url: BASE + g.href, name: 'Meccsoldal megnyitása',
			channel: 'watchsports.su', tags: []});
		items.forEach(function (s, i) { s.no = i + 1; });
		detail.items = items;
		detail.empty = !streams.length;
		detail.sel = 0;
		renderStreams();
		checkStreams(detail);
	}

	function renderStreams() {
		var list = $('.d-list');
		list.innerHTML = '';
		var inner = el('div', 'd-list-inner');
		if (detail.empty) {
			inner.appendChild(el('div', 'd-empty', 'Ehhez a meccshez még nincs adás – általában a ' +
				'kezdés előtt nem sokkal jelennek meg.'));
		}
		detail.items.forEach(function (s, i) {
			var row = el('div', 'st' + (s.site ? ' site' : ''));
			row.appendChild(el('div', 'no', s.site ? '↗' : String(s.no)));
			var main = el('div', 'main');
			var nm = el('div', 'nm', s.name);
			if (s.channel) nm.appendChild(el('span', null, s.channel));
			main.appendChild(nm);
			var tags = el('div', 'tags');
			s.tags.forEach(function (t) {
				var cls = /1080|720|4k|hd/i.test(t) ? ' hd' : (/\bads?\b/i.test(t) ? ' ads' : '');
				tags.appendChild(el('span', 'tag' + cls, t.replace(/^(\d+) ads?$/, '$1 reklám')
					.replace(/^no ads$/i, 'reklám nélkül')));
			});
			s.chip = el('span', 'tag chk');
			tags.appendChild(s.chip);
			main.appendChild(tags);
			row.appendChild(main);
			row.appendChild(el('div', 'go', '▶'));
			row.addEventListener('mouseenter', function () { selectStream(i); });
			row.addEventListener('click', function () { selectStream(i); playStream(s); });
			s.row = row;
			paintCheck(s);
			inner.appendChild(row);
		});
		list.appendChild(inner);
		selectStream(detail.sel);
	}

	// --- elérhetőség-ellenőrzés -----------------------------------------------
	// A szolgáltató / DNS által tiltott adásoldalakon a TV -102 / -105 / -107 hibaoldalt
	// mutatna (és kidobna az appból). A háttérszolgáltatás előre megnézi, hogy az oldal
	// válaszol-e; a nem elérhetőket jelöljük, a lista végére tesszük, és nem nyitjuk meg.
	var probeCache = {};    // url -> {at, promise, result}
	var PROBE_TTL = 5 * 60000;

	function probe(url) {
		var c = probeCache[url];
		if (c && Date.now() - c.at < PROBE_TTL) return c.promise;
		c = probeCache[url] = {at: Date.now(), result: null};
		if (!onTV()) {
			// asztali böngészőben nincs szolgáltatás - nem ellenőrizhető
			c.result = {ok: true, unknown: true};
			c.promise = Promise.resolve(c.result);
			return c.promise;
		}
		c.promise = new Promise(function (resolve) {
			var bridge = new window.PalmServiceBridge();
			var done = false;
			pending.push(bridge);
			var timer = setTimeout(function () {
				if (done) return;
				done = true;
				resolve({ok: true, unknown: true});   // a szolgáltatás nem válaszol: nem tudjuk
			}, 15000);
			bridge.onservicecallback = function (msg) {
				var i = pending.indexOf(bridge);
				if (i >= 0) pending.splice(i, 1);
				if (done) return;
				done = true;
				clearTimeout(timer);
				var r;
				try { r = JSON.parse(msg); } catch (e) { r = null; }
				resolve(r && r.returnValue !== false && typeof r.ok === 'boolean' ? r : {ok: true, unknown: true});
			};
			bridge.call('luna://hu.tomszo.watchsports.service/probe', JSON.stringify({url: url}));
		}).then(function (r) {
			c.result = r;
			if (r.unknown) c.at = 0;   // legközelebb újra próbáljuk
			return r;
		});
		return c.promise;
	}

	function probeError(r) {
		var code = String(r.code || '');
		if (code === 'ECONNREFUSED') return 'a kapcsolatot elutasították (-102)';
		if (code === 'ENOTFOUND' || code === 'EAI_AGAIN') return 'a cím nem található (-105, DNS-tiltás?)';
		if (code === 'ETIMEDOUT' || code === 'ESOCKETTIMEDOUT') return 'nem válaszol (időtúllépés)';
		if (code === 'ECONNRESET' || code === 'EPIPE' || code === 'EPROTO' || /SSL|TLS|CERT/i.test(code)) {
			return 'a kapcsolatot megszakították (-107) – valószínűleg szolgáltatói tiltás';
		}
		if (code === 'EPRIVATE') return 'belső hálózati cím';
		return 'nem érhető el' + (code ? ' (' + code + ')' : '');
	}

	function paintCheck(s) {
		if (!s.chip) return;
		var c = probeCache[s.url];
		var r = c && c.result;
		var bad = r && !r.ok;
		s.chip.className = 'tag chk' + (!r ? ' wait' : bad ? ' bad' : r.unknown ? ' hide' : ' ok');
		s.chip.textContent = !r ? 'ellenőrzés…' : bad ? '✗ ' + probeError(r) : '✓ elérhető';
		if (s.row) s.row.className = s.row.className.replace(/ off\b/, '') + (bad ? ' off' : '');
	}

	function checkStreams(d) {
		var queue = d.items.slice();
		var running = 0;
		function next() {
			if (d !== detail) return;
			if (!queue.length) {
				if (!running) reorder(d);
				return;
			}
			while (running < 4 && queue.length) {
				var s = queue.shift();
				running++;
				probe(s.url).then(function (s) {
					return function () {
						running--;
						if (d !== detail) return;
						paintCheck(s);
						next();
					};
				}(s));
			}
		}
		next();
	}

	// a végén: az elérhető adások elöl (az eredeti sorrendben), a nem elérhetők hátul
	function reorder(d) {
		var bad = function (s) {
			var c = probeCache[s.url];
			return c && c.result && !c.result.ok ? 1 : 0;
		};
		var cur = d.items[d.sel];
		var sorted = d.items.slice().sort(function (a, b) {
			return bad(a) - bad(b) || (a.site ? 1 : 0) - (b.site ? 1 : 0) || a.no - b.no;
		});
		var same = sorted.every(function (s, i) { return s === d.items[i]; });
		if (same) return;
		d.items = sorted;
		d.sel = d.sel === 0 ? 0 : Math.max(0, sorted.indexOf(cur));
		renderStreams();
	}

	function selectStream(i) {
		if (!detail || !detail.items.length) return;
		detail.sel = Math.max(0, Math.min(i, detail.items.length - 1));
		var rowsEl = $$('.d-list .st');
		rowsEl.forEach(function (r, j) { r.className = r.className.replace(/ sel\b/, '') + (j === detail.sel ? ' sel' : ''); });
		var inner = $('.d-list-inner');
		var row = rowsEl[detail.sel];
		var listH = $('.d-list').clientHeight || 500;
		var off = row ? Math.max(0, row.offsetTop + row.offsetHeight + 16 - listH) : 0;
		if (inner) inner.style.transform = 'translateY(' + (-off) + 'px)';
	}

	function hideDetail() {
		detailReq++;
		detail = null;
		$('#detail').className = '';
	}

	function playStream(s) {
		if (!s || !s.url) return;
		var d = detail;
		var c = probeCache[s.url];
		if (!(c && c.result)) toast('Elérhetőség ellenőrzése…', 15000);
		probe(s.url).then(function (r) {
			if (d !== detail) return;
			paintCheck(s);
			if (!r.ok) {
				toast('Ez az adás a hálózatodról nem érhető el: ' + probeError(r) + '. Válassz másikat.', 6000);
				return;
			}
			go(s.url);
		});
	}

	function go(url) {
		try {
			sessionStorage.setItem('ws.focus', JSON.stringify({href: detail ? detail.game.href : '', row: activeRow}));
		} catch (e) {}
		toast('Megnyitás… (Vissza gomb: vissza az apphoz)', 6000);
		// az adásoldalak nem engedik a beágyazást - az app ablaka navigál oda
		setTimeout(function () { location.href = url; }, 150);
	}

	function openInBrowser(url) {
		if (!url) return;
		if (onTV()) {
			var bridge = new window.PalmServiceBridge();
			pending.push(bridge);
			bridge.onservicecallback = function () {
				var i = pending.indexOf(bridge);
				if (i >= 0) pending.splice(i, 1);
			};
			bridge.call('luna://com.webos.applicationManager/launch', JSON.stringify({
				id: 'com.webos.app.browser', params: {target: url}
			}));
			toast('Megnyitás a TV böngészőjében…');
		} else {
			window.open(url, '_blank');
		}
	}

	// --- betöltés ------------------------------------------------------------
	function load(quiet) {
		if (!quiet) status('Műsor betöltése…');
		var keep = current();
		var keepHref = keep ? keep.href : restoredHref();
		return getPage('/').then(function (html) {
			var prevRows = {};
			rows.forEach(function (r) { prevRows[r.key] = r.sel; });
			rows = parseHome(html);
			rows.forEach(function (r) { r.sel = prevRows[r.key] || 0; });
			loaded = true;
			render(keepHref);
			var n = 0, live = 0;
			rows.forEach(function (r) {
				if (r.key.charAt(0) === '_') return;
				n += r.games.length;
				live += r.games.filter(function (g) { return g.live; }).length;
			});
			status(n + ' esemény' + (live ? ' · ' + live + ' élő' : '') + ' · frissítve ' + clockText());
			$('#loading').className = 'off';
		}, function (err) {
			$('#loading').className = 'off';
			status('Hiba: ' + err.message);
			if (!loaded) {
				var inner = $('#rows .rows-inner');
				inner.innerHTML = '';
				inner.appendChild(el('div', 'empty', 'Nem sikerült betölteni a watchsports.su műsorát (' +
					err.message + '). OK: újrapróbálás.'));
			}
		});
	}

	function restoredHref() {
		try {
			var f = JSON.parse(sessionStorage.getItem('ws.focus') || 'null');
			if (f) {
				if (typeof f.row === 'number') activeRow = f.row;
				return f.href;
			}
		} catch (e) {}
		return hashGame();
	}

	function clockText() {
		var d = new Date();
		return pad(d.getHours()) + ':' + pad(d.getMinutes());
	}

	// --- vezérlés ------------------------------------------------------------
	function back() {
		if (detail) history.back();
	}

	function onKey(e) {
		var k = e.keyCode;
		if (detail) {
			if (k === KEY.UP) selectStream(detail.sel - 1);
			else if (k === KEY.DOWN) selectStream(detail.sel + 1);
			else if (k === KEY.OK) playStream(detail.items[detail.sel]);
			else if (k === KEY.RED) openInBrowser((detail.items[detail.sel] || {}).url);
			else if (k === KEY.ESC || k === KEY.BACKSPACE) back();
			else return;
			e.preventDefault();
			return;
		}
		if (!rows.length) {
			if (k === KEY.OK) { load(); e.preventDefault(); }
			return;
		}
		var r = rows[activeRow];
		if (k === KEY.LEFT) focusCard(activeRow, r.sel - 1);
		else if (k === KEY.RIGHT) focusCard(activeRow, r.sel + 1);
		else if (k === KEY.UP) { if (activeRow > 0) focusCard(activeRow - 1, rows[activeRow - 1].sel); }
		else if (k === KEY.DOWN) { if (activeRow < rows.length - 1) focusCard(activeRow + 1, rows[activeRow + 1].sel); }
		else if (k === KEY.OK) openGame(current());
		else if (k === KEY.RED) { var g = current(); if (g) openInBrowser(BASE + g.href); }
		else return;
		e.preventDefault();
	}

	function tick() { $('#clock').textContent = clockText(); }

	window.addEventListener('load', function () {
		tick();
		setInterval(tick, 10000);
		document.addEventListener('keydown', onKey);
		window.addEventListener('hashchange', routeChanged);
		// a görgő függőlegesen a sorok között lép
		var wheelLock = 0;
		document.addEventListener('wheel', function (e) {
			if (detail || Date.now() - wheelLock < 250 || !rows.length) return;
			wheelLock = Date.now();
			var to = activeRow + (e.deltaY > 0 ? 1 : -1);
			if (to >= 0 && to < rows.length) focusCard(to, rows[to].sel);
		});
		document.addEventListener('visibilitychange', function () {
			if (!document.hidden && loaded) load(true);
		});
		load().then(function () {
			routeChanged();
			try { sessionStorage.removeItem('ws.focus'); } catch (e) {}
		});
		setInterval(function () { if (!document.hidden && !detail) load(true); }, REFRESH_MS);
	});
})();
