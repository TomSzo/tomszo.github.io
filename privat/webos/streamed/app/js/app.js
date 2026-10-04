/*
 * Streamed Sport (webOS) - a streamed-tui (Salastil, GPL-3.0) TV-s változata.
 *
 * A streamed.pk nyilvános API-jából (CORS: *) olvassa a sportágakat, meccseket és
 * adásokat, három oszlopban: kategóriák | meccsek | adások. Egy adás kiválasztásakor az
 * adás beágyazott lejátszóoldalát (embedUrl) teljes képernyős iframe-ben nyitja meg -
 * ugyanazt, amit a böngésző is mutatna; a piros gombbal a TV böngészőjében is
 * megnyitható.
 *
 * Vissza gomb: keyCode 461 (disableBackHistoryAPI: true). Lejátszás közben a fókusz
 * mindig visszakerül az appra (egy kattintás után is), különben a gombnyomások a
 * lejátszó iframe-jébe mennének, és a Vissza nem működne.
 */
(function () {
	'use strict';

	var BASE = 'https://streamed.pk';
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27, BACKSPACE: 8, RED: 403};
	var REFRESH_MS = 60000;
	var MONTHS = ['jan.', 'febr.', 'márc.', 'ápr.', 'máj.', 'jún.', 'júl.', 'aug.', 'szept.',
		'okt.', 'nov.', 'dec.'];
	var SPORT_HU = {
		'basketball': ['Kosárlabda', '🏀'], 'football': ['Labdarúgás', '⚽'],
		'american-football': ['Amerikai foci', '🏈'], 'hockey': ['Jégkorong', '🏒'],
		'baseball': ['Baseball', '⚾'], 'motor-sports': ['Motorsport', '🏎️'],
		'fight': ['Küzdősport (UFC, box)', '🥊'], 'tennis': ['Tenisz', '🎾'],
		'rugby': ['Rögbi', '🏉'], 'golf': ['Golf', '⛳'], 'billiards': ['Biliárd', '🎱'],
		'afl': ['Ausztrál futball', '🏉'], 'darts': ['Darts', '🎯'], 'cricket': ['Krikett', '🏏'],
		'other': ['Egyéb', '🏅']
	};
	var FIXED = [
		{id: 'live', name: 'Élő most', ico: '🔴', url: '/api/matches/live'},
		{id: 'popular', name: 'Népszerű', ico: '⭐', url: '/api/matches/all/popular'},
		{id: 'today', name: 'Mai műsor', ico: '📅', url: '/api/matches/all-today'}
	];

	// beállítások (a kategóriák alján): kulcs, ikon, felirat, magyarázat
	var SETTINGS = [
		{setting: 'adminOnly', ico: '✅', name: 'Csak működő (admin) adások',
			help: 'a többi forrás hálózati hibát adhat'},
		{setting: 'hideEnded', ico: '🏁', name: 'Befejezett meccsek elrejtése',
			help: 'Sofascore és ESPN eredményei alapján'},
		{setting: 'sitePage', ico: '🌐', name: 'Lejátszás a streamed.pk oldalán',
			help: 'mint telefonon – ha a beágyazott lejátszó hibát ad (-102)'},
		{setting: 'adblock', ico: '🛡', name: 'Reklámszűrő',
			help: 'felugró ablakok és átirányítás tiltása'}
	];
	var cols = [];          // [{el, inner, items, sel, render}]
	var active = 0;
	var categories = FIXED.slice();
	var matches = [];
	var streams = [];
	var liveIds = {};
	var curCat = null;
	var curMatch = null;
	var matchReq = 0;
	var streamReq = 0;
	var liveFailed = false;
	var opts = {adminOnly: true, hideEnded: true, sitePage: false, adblock: true};
	var playing = false;
	var toastTimer = null;
	var hintTimer = null;
	var focusTimer = null;

	// --- segédek -------------------------------------------------------------
	function $(sel) { return document.querySelector(sel); }

	function el(tag, cls, text) {
		var e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null && text !== '') e.textContent = text;
		return e;
	}

	function pad(n) { return (n < 10 ? '0' : '') + n; }

	function sameDay(a, b) {
		return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() &&
			a.getDate() === b.getDate();
	}

	function whenText(ms) {
		if (!ms) return ['', ''];
		var d = new Date(ms);
		var now = new Date();
		var tomorrow = new Date(now.getTime() + 86400000);
		var day = sameDay(d, now) ? 'ma' : sameDay(d, tomorrow) ? 'holnap' :
			MONTHS[d.getMonth()] + ' ' + d.getDate() + '.';
		return [day, pad(d.getHours()) + ':' + pad(d.getMinutes())];
	}

	// a streamed.pk szerint élő-e (ez a befejezett meccseket is sokáig élőnek mutatja)
	function listedLive(m) {
		if (liveIds[m.id]) return true;
		// ha az élő lista nem jött le: elkezdődött, és még 3 órán belül van
		return liveFailed && m.date && m.date <= Date.now() && Date.now() - m.date < 3 * 3600000;
	}

	// valódi állapot: ESPN-eredmény, ha van; különben a sportág szokásos meccshossza
	function matchInfo(m) {
		var st = window.Scores ? window.Scores.status(m) : null;
		if (st) {
			return {live: st.state === 'in', ended: st.state === 'post', score: st.score,
				detail: st.state === 'in' ? st.detail : ''};
		}
		var ended = !!m.date && m.date <= Date.now() && window.Scores &&
			window.Scores.estimateEnded(m);
		return {live: !ended && listedLive(m), ended: !!ended, score: '', detail: ''};
	}

	function isLive(m) { return matchInfo(m).live; }

	function hasAdmin(m) {
		return (m.sources || []).some(function (s) { return s.source === 'admin'; });
	}

	function sportName(id) {
		return (SPORT_HU[id] || [id || ''])[0];
	}

	function toast(msg) {
		var t = $('#toast');
		t.textContent = msg;
		t.className = 'on';
		clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { t.className = ''; }, 3500);
	}

	function status(msg) { $('#status').textContent = msg || ''; }

	function getJSON(path) {
		var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
		var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, 20000);
		return fetch(BASE + path, {headers: {Accept: 'application/json'},
			signal: ctrl ? ctrl.signal : undefined})
			.then(function (r) {
				clearTimeout(timer);
				if (!r.ok) throw new Error('HTTP ' + r.status);
				return r.json();
			}, function (e) {
				clearTimeout(timer);
				throw e;
			});
	}

	function img(src, cls) {
		var i = new Image();
		i.alt = '';
		if (cls) i.className = cls;
		i.onerror = function () { i.style.visibility = 'hidden'; };
		i.src = src;
		return i;
	}

	// --- oszlopok ------------------------------------------------------------
	function makeCol(id, render) {
		var section = $('#' + id);
		var list = section.querySelector('.list');
		var inner = el('div', 'list-inner');
		list.appendChild(inner);
		var col = {el: section, list: list, inner: inner, items: [], sel: 0, render: render, nodes: []};
		cols.push(col);
		return col;
	}

	function fill(ci, items, keepSel, emptyText) {
		var col = cols[ci];
		col.items = items;
		if (!keepSel) col.sel = 0;
		col.sel = Math.max(0, Math.min(col.sel, items.length - 1));
		col.inner.innerHTML = '';
		col.nodes = [];
		if (!items.length && emptyText) col.inner.appendChild(el('div', 'empty', emptyText));
		items.forEach(function (it, i) {
			var node = it.sep ? el('div', 'item sep') : col.render(it);
			if (!it.sep) {
				node.addEventListener('click', function () {
					setActive(ci);
					select(ci, i);
					activate();
				});
				node.addEventListener('mouseenter', function () {
					if (cols[ci].sel !== i || active !== ci) { setActive(ci); select(ci, i, true); }
				});
			}
			col.inner.appendChild(node);
			col.nodes.push(node);
		});
		paint(ci);
	}

	function paint(ci) {
		var col = cols[ci];
		col.nodes.forEach(function (n, i) { n.classList.toggle('sel', i === col.sel); });
		var node = col.nodes[col.sel];
		if (!node) { col.inner.style.transform = ''; return; }
		var view = col.list.clientHeight;
		var top = node.offsetTop;
		var h = node.offsetHeight;
		var total = col.inner.scrollHeight;
		var y = Math.max(0, Math.min(top - (view - h) / 2, total - view));
		col.inner.style.transform = 'translateY(' + (-y) + 'px)';
	}

	function setActive(ci) {
		active = ci;
		cols.forEach(function (c, i) { c.el.classList.toggle('active', i === ci); });
	}

	function select(ci, i, fromPointer) {
		var col = cols[ci];
		if (!col.items.length) return;
		i = Math.max(0, Math.min(i, col.items.length - 1));
		if (col.items[i].sep) i += (i > col.sel ? 1 : -1);
		i = Math.max(0, Math.min(i, col.items.length - 1));
		col.sel = i;
		paint(ci);
		if (ci === 1) showHero(col.items[i]);
	}

	function current(ci) { return cols[ci].items[cols[ci].sel]; }

	// --- renderelők ----------------------------------------------------------
	function renderCat(c) {
		var n = el('div', 'item');
		n.appendChild(el('div', 'ico', c.ico));
		var main = el('div', 'main');
		main.appendChild(el('div', 't', c.setting ? c.name + ': ' + (opts[c.setting] ? 'BE' : 'KI') : c.name));
		if (c.setting) main.appendChild(el('div', 's', c.help));
		n.appendChild(main);
		return n;
	}

	function renderMatch(m) {
		var n = el('div', 'item');
		var when = el('div', 'when');
		var info = matchInfo(m);
		if (info.live || info.ended) {
			when.appendChild(el('span', info.live ? 'live-badge' : 'live-badge ended', info.live ? 'ÉLŐ' : 'VÉGE'));
			if (info.score) when.appendChild(el('div', 'score', info.score));
		} else if (!m.date) {
			when.appendChild(el('span', 'live-badge chan', '0–24'));
		} else {
			var w = whenText(m.date);
			when.appendChild(el('div', '', w[0]));
			when.appendChild(el('div', '', w[1]));
		}
		n.appendChild(when);
		var main = el('div', 'main');
		main.appendChild(el('div', 't', m.title));
		var sub = el('div', 's', sportName(m.category) + (info.detail ? ' · ' + info.detail : ''));
		if (hasAdmin(m)) {
			sub.appendChild(el('span', 'ok', ' · ✓ indítható'));
		} else {
			n.className += ' dim';
			sub.appendChild(document.createTextNode(' · nincs admin adás'));
		}
		main.appendChild(sub);
		n.appendChild(main);
		var t = m.teams || {};
		if ((t.home && t.home.badge) || (t.away && t.away.badge)) {
			var b = el('div', 'badges');
			[t.home, t.away].forEach(function (team) {
				if (team && team.badge) b.appendChild(img(BASE + '/api/images/badge/' + team.badge + '.webp'));
			});
			n.appendChild(b);
		}
		return n;
	}

	function renderStream(s) {
		var n = el('div', 'item');
		n.appendChild(el('div', 'ico', '▶'));
		var main = el('div', 'main');
		var t = el('div', 't', (s.language || 'Ismeretlen nyelv') + ' #' + s.streamNo);
		if (s.hd) t.appendChild(el('span', 'tag hd', 'HD'));
		if (s.source === 'admin') t.appendChild(el('span', 'tag admin', 'ADMIN'));
		main.appendChild(t);
		var sub = 'Forrás: ' + s.source;
		if (s.viewers) sub += ' · ' + s.viewers.toLocaleString('hu-HU') + ' néző';
		main.appendChild(el('div', 's', sub));
		n.appendChild(main);
		return n;
	}

	function showHero(m) {
		var hero = $('#hero');
		if (!m || m.sep) { hero.className = ''; return; }
		var im = hero.querySelector('img');
		if (m.poster) {
			im.style.visibility = '';
			im.onerror = function () { im.style.visibility = 'hidden'; };
			im.src = BASE + m.poster;
		} else {
			im.removeAttribute('src');
			im.style.visibility = 'hidden';
		}
		hero.querySelector('.hero-cat').textContent = sportName(m.category);
		hero.querySelector('.hero-title').textContent = m.title;
		var w = whenText(m.date);
		var info = matchInfo(m);
		hero.querySelector('.hero-time').textContent = info.live ?
			'● Élőben' + (info.score ? ' · ' + info.score : '') + (info.detail ? ' · ' + info.detail : '') :
			info.ended ? 'Véget ért' + (info.score ? ' · ' + info.score : '') :
			!m.date ? '0–24 órás csatorna' : (w[0] + ' ' + w[1]);
		hero.className = 'on';
	}

	// --- adatok --------------------------------------------------------------
	function loadCategories() {
		getJSON('/api/sports').then(function (list) {
			var extra = (list || []).map(function (s) {
				var hu = SPORT_HU[s.id];
				return {id: s.id, name: hu ? hu[0] : s.name, ico: hu ? hu[1] : '🏅',
					url: '/api/matches/' + encodeURIComponent(s.id)};
			});
			categories = FIXED.concat([{sep: true}], extra, [{sep: true}], SETTINGS);
			fill(0, categories, true);
		}).catch(function () {
			toast('A sportágak listája nem tölthető be');
		});
	}

	function refreshLive() {
		return getJSON('/api/matches/live').then(function (list) {
			liveIds = {};
			liveFailed = false;
			(list || []).forEach(function (m) { liveIds[m.id] = true; });
		}).catch(function () {
			liveFailed = true;
		});
	}

	function loadMatches(cat, keep) {
		if (!cat || cat.sep) return;
		curCat = cat;
		var my = ++matchReq;
		if (!keep) {
			fill(1, [], false, 'Betöltés…');
			fill(2, [], false, '');
			$('#hero').className = '';
		}
		status(cat.name + ' – betöltés…');
		Promise.all([getJSON(cat.url), refreshLive()]).then(function (res) {
			if (my !== matchReq) return;
			var all = res[0] || [];
			showMatches(cat, all, keep);
			// ESPN-állapot az elkezdett meccsekhez; ha megjött, újrarajzolás
			var cats = [];
			all.forEach(function (m) {
				if (m.date && m.date <= Date.now() + 600000 && cats.indexOf(m.category) < 0) cats.push(m.category);
			});
			if (window.Scores && cats.length) {
				window.Scores.remember(cats).then(function () {
					if (my === matchReq) showMatches(cat, all, true);
				});
			}
		}).catch(function (e) {
			if (my !== matchReq) return;
			fill(1, [], false, 'Hiba a betöltéskor: ' + e.message);
			status('');
		});
	}

	function showMatches(cat, all, keep) {
		var list = all.filter(function (m) {
			if (opts.adminOnly && !hasAdmin(m)) return false;
			if (opts.hideEnded && matchInfo(m).ended) return false;
			return true;
		});
		list.sort(function (a, b) {
			var la = isLive(a) ? 0 : 1, lb = isLive(b) ? 0 : 1;
			if (la !== lb) return la - lb;
			var aa = hasAdmin(a) ? 0 : 1, ab = hasAdmin(b) ? 0 : 1;
			if (aa !== ab) return aa - ab;
			if (cat.id === 'popular' && la === 0) return (b.viewers || 0) - (a.viewers || 0);
			return (a.date || 0) - (b.date || 0);
		});
		var prev = keep && current(1);
		matches = list;
		fill(1, list, false, all.length ? 'Itt most nincs megjeleníthető meccs (a beállításokkal – a kategóriák alján – a többi is látszik)' : 'Nincs meccs ebben a kategóriában');
		if (prev) {
			for (var i = 0; i < list.length; i++) if (list[i].id === prev.id) { select(1, i, true); break; }
		}
		var live = list.filter(isLive).length;
		status(cat.name + ' · ' + list.length + ' meccs' + (live ? ' · ' + live + ' élő' : ''));
		if (cols[1].items.length && active === 1) showHero(current(1));
	}

	function loadStreams(m) {
		if (!m) return;
		curMatch = m;
		var my = ++streamReq;
		fill(2, [], false, 'Adások keresése…');
		var sources = m.sources || [];
		Promise.all(sources.map(function (s) {
			return getJSON('/api/stream/' + encodeURIComponent(s.source) + '/' + encodeURIComponent(s.id))
				.catch(function () { return []; });
		})).then(function (lists) {
			if (my !== streamReq) return;
			var all = [];
			lists.forEach(function (l) { all = all.concat(l || []); });
			all = all.filter(function (s) { return s && s.embedUrl; });
			// az admin adások a TV-n (iframe-ben) működnek, a többi forrás hálózati hibát
			// adhat: „Csak működő adások” esetén csak az admin; sorrend: nézőszám szerint
			var total = all.length;
			if (opts.adminOnly) all = all.filter(function (x) { return x.source === 'admin'; });
			all.sort(function (a, b) {
				return (b.viewers || 0) - (a.viewers || 0) || (a.streamNo || 0) - (b.streamNo || 0);
			});
			streams = all;
			fill(2, all, false, total ? 'Nincs admin adás – a „Csak működő adások” kikapcsolásával a többi forrás is látszik' : 'Ehhez a meccshez most nincs adás (később próbáld újra)');
		});
	}

	// --- lejátszás -----------------------------------------------------------
	// a beágyazott lejátszó (embedUrl), vagy a streamed.pk saját nézőoldala - ezt nyitja
	// meg a telefon is (streamed.pk/watch/<meccs>/<forrás>/<sorszám>)
	function watchUrl(s) {
		if (!curMatch || !curMatch.id) return s.embedUrl;
		return BASE + '/watch/' + encodeURIComponent(curMatch.id) + '/' +
			encodeURIComponent(s.source) + '/' + (s.streamNo || 1);
	}

	function playUrl(s) {
		return opts.sitePage ? watchUrl(s) : s.embedUrl;
	}

	function play(s) {
		var p = $('#player');
		var old = p.querySelector('iframe');
		var frame = old.cloneNode(false);    // a sandbox csak új iframe-nél érvényes
		if (opts.adblock) {
			frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-presentation');
		} else {
			frame.removeAttribute('sandbox');
		}
		frame.src = playUrl(s);
		old.parentNode.replaceChild(frame, old);
		p.className = 'on';
		playing = true;
		var hint = p.querySelector('.p-hint');
		hint.className = 'p-hint';
		clearTimeout(hintTimer);
		hintTimer = setTimeout(function () { hint.className = 'p-hint off'; }, 10000);
		grabFocus();
		clearInterval(focusTimer);
		focusTimer = setInterval(grabFocus, 1000);
	}

	// a fókuszt az app egy rejtett elemére tesszük vissza (az iframe-ből is)
	function grabFocus() {
		if (!playing) return;
		var sink = $('#sink');
		if (document.activeElement !== sink) {
			try { sink.focus(); } catch (e) {}
		}
	}

	window.addEventListener('blur', function () {
		if (playing) setTimeout(grabFocus, 150);   // kattintás a lejátszóban: vissza a fókusz
	});

	function stop() {
		var p = $('#player');
		// új, üres iframe (az src átírása új history-bejegyzést adna)
		var old = p.querySelector('iframe');
		old.parentNode.replaceChild(old.cloneNode(false), old);
		p.querySelector('iframe').removeAttribute('src');
		p.className = '';
		playing = false;
		clearInterval(focusTimer);
		window.focus();
	}

	function openInBrowser(s) {
		if (!s || !s.embedUrl) return;
		if (typeof window.PalmServiceBridge === 'function') {
			var bridge = new window.PalmServiceBridge();
			window.__bridge = bridge;   // a válaszig életben tartjuk
			bridge.onservicecallback = function () {};
			bridge.call('luna://com.webos.applicationManager/launch', JSON.stringify({
				id: 'com.webos.app.browser', params: {target: watchUrl(s)}
			}));
			toast('Megnyitás a TV böngészőjében…');
		} else {
			window.open(watchUrl(s), '_blank');
		}
	}

	// --- vezérlés ------------------------------------------------------------
	function activate() {
		var it = current(active);
		if (!it) return;
		if (active === 0 && it.setting) {
			var k = it.setting;
			opts[k] = !opts[k];
			try { localStorage.setItem(k, opts[k] ? '1' : '0'); } catch (e) {}
			fill(0, categories, true);
			toast(it.name + (opts[k] ? ' bekapcsolva' : ' kikapcsolva'));
			if ((k === 'adminOnly' || k === 'hideEnded') && curCat) loadMatches(curCat);
			return;
		}
		if (active === 0) {
			loadMatches(it);
			setActive(1);
		} else if (active === 1) {
			loadStreams(it);
			setActive(2);
		} else {
			play(it);
		}
	}

	function back() {
		if (playing) { stop(); return; }
		if (active > 0) setActive(active - 1);
	}

	document.addEventListener('keydown', function (e) {
		var k = e.keyCode;
		if (playing) {
			if (k === KEY.BACK || k === KEY.ESC || k === KEY.BACKSPACE) { e.preventDefault(); back(); }
			return;
		}
		if (k === KEY.BACK || k === KEY.ESC || k === KEY.BACKSPACE) {
			e.preventDefault();
			back();
			return;
		}
		var col = cols[active];
		if (k === KEY.UP || k === KEY.DOWN) {
			e.preventDefault();
			select(active, col.sel + (k === KEY.UP ? -1 : 1));
		} else if (k === KEY.RIGHT || k === KEY.OK) {
			e.preventDefault();
			if (k === KEY.RIGHT && active === 2) return;
			activate();
		} else if (k === KEY.LEFT) {
			e.preventDefault();
			if (active > 0) back();
		} else if (k === KEY.RED || k === 82 /* R */) {
			if (active === 2) openInBrowser(current(2));
		} else if (k === 33 || k === 34) {   // lapozás (Page Up/Down, CH+/CH-)
			e.preventDefault();
			select(active, col.sel + (k === 33 ? -6 : 6));
		}
	});

	function tick() {
		var d = new Date();
		$('#clock').textContent = pad(d.getHours()) + ':' + pad(d.getMinutes());
	}

	document.addEventListener('DOMContentLoaded', function () {
		makeCol('c0', renderCat);
		makeCol('c1', renderMatch);
		makeCol('c2', renderStream);
		Object.keys(opts).forEach(function (k) {
			try {
				var v = localStorage.getItem(k);
				if (v === '0' || v === '1') opts[k] = v === '1';
			} catch (e) {}
		});
		categories = FIXED.concat([{sep: true}], SETTINGS);
		fill(0, categories);
		fill(2, [], false, 'Válassz egy meccset');
		setActive(0);
		tick();
		setInterval(tick, 10000);
		loadCategories();
		loadMatches(FIXED[0]);
		setInterval(function () {
			if (!playing && curCat) loadMatches(curCat, true);
		}, REFRESH_MS);
	});
})();
