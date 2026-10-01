/*
 * MagyarAnime felület (streaming-stílus, a Network4 webOS-app motorjával): bal oldali
 * menüsáv, hero a kijelölt anime borítójával, vízszintes sorok, anime-adatlap a részekkel,
 * szerverválasztó a napi számlálóval. Távirányítós navigáció, mint a Network4-ben.
 */
(function (global) {
	'use strict';

	var Api = global.MAApi;
	var Store = global.MAStore;
	var Player = global.MAPlayer;
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27, BACKSPACE: 8};
	var DIRS = {37: 'left', 38: 'up', 39: 'right', 40: 'down'};
	var ICONS = {
		search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
		home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
		browse: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5"/>',
		heart: '<path d="M12 20s-7-4.4-9.2-8.7C1.3 8.2 3.2 4.5 6.7 4.5c2 0 3.3 1.1 4.3 2.5 1-1.4 2.3-2.5 4.3-2.5 3.5 0 5.4 3.7 3.9 6.8C19 15.6 12 20 12 20z"/>',
		history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
		live: '<circle cx="12" cy="12" r="2.5"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2"/>',
		sports: '<circle cx="12" cy="12" r="9"/><path d="M12 7l4.3 3.1-1.6 5H9.3l-1.6-5z"/><path d="M12 3v4M21 10l-4.7.1M17.5 19.5l-2.8-4.4M6.5 19.5l2.8-4.4M3 10l4.7.1"/>',
		library: '<rect x="3" y="4" width="7" height="7" rx="1.5"/><rect x="14" y="4" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
		settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
		play: '<path d="M7 4v16l13-8z"/>',
		lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'
	};
	var TABS = [
		{key: 'search', label: 'Keresés', icon: 'search'},
		{key: 'home', label: 'Főoldal', icon: 'home'},
		{key: 'browse', label: 'Böngészés', icon: 'browse'},
		{key: 'favorites', label: 'Kedvencek', icon: 'heart'},
		{key: 'history', label: 'Előzmények', icon: 'history'},
		{key: 'settings', label: 'Beállítások', icon: 'settings'}
	];

	var rail, content, modal, toastEl;
	var stack = [];
	var tab = 'home';
	var modalClose = null;
	var toastTimer = null;
	var heroTimer = null;

	// --- segédek ---------------------------------------------------------------
	function el(tag, cls, text) {
		var e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null && text !== '') e.textContent = text;
		return e;
	}

	function icon(name, cls) {
		var span = el('span', cls || '');
		span.innerHTML = '<svg viewBox="0 0 24 24">' + ICONS[name] + '</svg>';
		return span.firstChild;
	}

	function img(src) {
		var i = new Image();
		i.decoding = 'async';
		i.loading = 'lazy';
		i.alt = '';
		i.src = src;
		return i;
	}

	function toast(msg, ms) {
		toastEl.textContent = msg;
		toastEl.classList.add('show');
		clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { toastEl.classList.remove('show'); }, ms || 4000);
	}

	function errMsg(err) {
		return (err && err.message) || String(err);
	}

	// --- fókusz -------------------------------------------------------------------
	function modalOpen() {
		return modal.classList.contains('open');
	}

	function visible(e) {
		return e.offsetParent !== null || e.getClientRects().length > 0;
	}

	function focusables(root) {
		return Array.prototype.slice.call(root.querySelectorAll('.focusable')).filter(visible);
	}

	function current() {
		return document.querySelector('.focused');
	}

	function top() {
		return stack[stack.length - 1];
	}

	function scrollFor(target) {
		var row = target.closest('.row');
		if (row) {
			// a sor a kijelölt kártyával balra igazodik (mint a streaming-appokban)
			var track = row.querySelector('.row-track');
			var cards = Array.prototype.slice.call(track.children);
			var idx = cards.indexOf(target);
			track._idx = idx;
			var shift = Math.max(0, target.offsetLeft - track.firstChild.offsetLeft);
			var max = Math.max(0, track.scrollWidth - 1920 + 120);
			track.style.transform = 'translateX(' + (-Math.min(shift, max)) + 'px)';
			var rows = row.parentNode;
			rows.style.transform = 'translateY(' + (-row.offsetTop) + 'px)';
			return;
		}
		var page = target.closest('.page');
		if (page) {
			// csak akkor görgetünk, ha a kijelölt elem kilógna a képernyőről
			var anchor = parseInt(page.getAttribute('data-anchor') || '340', 10);
			var t = 0;
			for (var n = target; n && n !== page; n = n.offsetParent) t += n.offsetTop;
			var y = page._y || 0;
			var vis = t - y;
			if (vis + target.offsetHeight > 1080 - 70 || vis < 70) y = Math.max(0, t - anchor);
			page._y = y;
			page.style.transform = 'translateY(' + (-y) + 'px)';
		}
	}

	function focus(target) {
		if (!target) return;
		var prev = current();
		if (prev) prev.classList.remove('focused');
		target.classList.add('focused');
		var inRail = rail.contains(target);
		rail.classList.toggle('open', inRail);
		content.classList.toggle('dim', inRail);
		if (!inRail && !modalOpen()) {
			scrollFor(target);
			if (top() && target.getAttribute('data-key')) top().lastKey = target.getAttribute('data-key');
		}
		if (target._hero) showHero(target._hero);
	}

	function focusContent() {
		var t = top();
		var key = t && t.lastKey;
		var e = key ? content.querySelector('[data-key="' + key + '"]') : null;
		focus(e || focusables(content)[0]);
	}

	function spatial(cur, dir, items) {
		var a = cur.getBoundingClientRect();
		var ax = a.left + a.width / 2;
		var ay = a.top + a.height / 2;
		var best = null;
		var bestScore = Infinity;
		items.forEach(function (e) {
			if (e === cur) return;
			var b = e.getBoundingClientRect();
			var horizontal = dir === 'left' || dir === 'right';
			var main = horizontal ? (b.left + b.width / 2) - ax : (b.top + b.height / 2) - ay;
			if (dir === 'left' || dir === 'up') main = -main;
			if (main <= 1) return;
			var gap = horizontal ? Math.max(b.top - a.bottom, a.top - b.bottom, 0) :
				Math.max(b.left - a.right, a.left - b.right, 0);
			var edge = horizontal ? Math.abs(b.top - a.top) : Math.abs(b.left - a.left);
			var score = main + gap * 3 + edge * 0.1;
			if (score < bestScore) {
				bestScore = score;
				best = e;
			}
		});
		return best;
	}

	function move(dir) {
		var cur = current();
		if (modalOpen()) {
			var m = focusables(modal);
			return focus(cur && modal.contains(cur) ? spatial(cur, dir, m) || cur : m[0]);
		}
		if (!cur) return focusContent();
		if (rail.contains(cur)) {
			if (dir === 'right') return focusContent();
			if (dir === 'up' || dir === 'down') return focus(spatial(cur, dir, focusables(rail)));
			return;
		}
		var row = cur.closest('.row');
		if (row && (dir === 'left' || dir === 'right')) {
			var sib = dir === 'left' ? cur.previousElementSibling : cur.nextElementSibling;
			if (sib) return focus(sib);
			if (dir === 'left') return focus(rail.querySelector('.rail-item.active'));
			return;
		}
		if (row && (dir === 'up' || dir === 'down')) {
			var next = dir === 'up' ? row.previousElementSibling : row.nextElementSibling;
			while (next && !next.classList.contains('row')) {
				next = dir === 'up' ? next.previousElementSibling : next.nextElementSibling;
			}
			if (next) {
				var track = next.querySelector('.row-track');
				return focus(track.children[Math.min(track._idx || 0, track.children.length - 1)]);
			}
			return;
		}
		var target = spatial(cur, dir, focusables(content));
		if (target) return focus(target);
		if (dir === 'left') focus(rail.querySelector('.rail-item.active'));
	}

	// --- hero ---------------------------------------------------------------------
	function heroBox(parent) {
		var h = el('div', 'hero');
		h.appendChild(el('div', 'hero-bg'));
		h.appendChild(el('div', 'hero-bg'));
		var info = el('div', 'hero-info');
		h.appendChild(info);
		parent.appendChild(h);
		h._layer = 0;
		return h;
	}

	function fillHeroInfo(info, d) {
		info.innerHTML = '';
		if (d.logo) {
			var lg = img(d.logo);
			lg.className = 'hero-logo';
			lg.loading = 'eager';
			lg.onerror = function () {
				lg.replaceWith(el('div', 'hero-title', d.title));
			};
			info.appendChild(lg);
		} else {
			info.appendChild(el('div', 'hero-title', d.title));
		}
		var meta = el('div', 'hero-meta');
		(d.meta || []).forEach(function (m) {
			if (!m) return;
			if (typeof m === 'string') meta.appendChild(el('span', '', m));
			else meta.appendChild(el('span', 'pill' + (m.cls ? ' ' + m.cls : ''), m.text));
		});
		info.appendChild(meta);
		if (d.desc) info.appendChild(el('div', 'hero-desc' + (d.longDesc ? ' long' : ''), d.desc));
		if (d.extra) info.appendChild(d.extra);
		// álló borító a jobb oldalon (a háttér ugyanez, elmosva)
		var h = info.parentNode;
		var old = h.querySelector('.hero-poster');
		if (old) old.remove();
		if (d.poster) {
			var pi = img(d.poster);
			pi.className = 'hero-poster';
			pi.loading = 'eager';
			pi.onerror = function () { pi.remove(); };
			h.appendChild(pi);
		}
	}

	function setHero(h, d, immediate) {
		if (!h || !d || h._current === d) return;
		h._current = d;
		var layers = h.querySelectorAll('.hero-bg');
		var next = layers[h._layer ^ 1];
		var old = layers[h._layer];
		var bg = d.backdrop || d.poster || d.logo || '';
		next.classList.toggle('logo-only', !d.backdrop && !d.poster && !!d.logo);
		next.classList.toggle('blurred', !d.backdrop && !!d.poster);
		var apply = function () {
			next.style.backgroundImage = bg ? 'url("' + bg + '")' : 'none';
			next.classList.add('show');
			old.classList.remove('show');
			h._layer ^= 1;
		};
		if (bg) {
			var pre = new Image();
			pre.onload = pre.onerror = function () { if (h._current === d) apply(); };
			pre.src = bg;
		} else {
			apply();
		}
		var info = h.querySelector('.hero-info');
		if (immediate) {
			fillHeroInfo(info, d);
			return;
		}
		info.classList.add('fade');
		setTimeout(function () {
			if (h._current !== d) return;
			fillHeroInfo(info, d);
			info.classList.remove('fade');
		}, 180);
	}

	function showHero(d) {
		var h = content.querySelector('.hero.dynamic');
		if (!h) return;
		clearTimeout(heroTimer);
		heroTimer = setTimeout(function () {
			setHero(h, d);
			heroInfoLater(d);
		}, 220);
	}

	// --- kártyák, sorok, rácsok ------------------------------------------------------
	function card(opts) {
		var c = el('div', 'card focusable' + (opts.locked ? ' locked' : ''));
		c.setAttribute('data-key', opts.key);
		var art = el('div', 'card-art');
		if (opts.image) {
			var i = img(opts.image);
			i.onerror = function () {
				art.classList.add('tile');
				art.innerHTML = '';
				art.appendChild(el('div', 'tile-title', opts.title));
			};
			art.appendChild(i);
		} else if (opts.logo) {
			art.classList.add('tile');
			var lg = img(opts.logo);
			lg.onerror = function () { lg.replaceWith(el('div', 'tile-title', opts.title)); };
			art.appendChild(lg);
		} else {
			art.classList.add('tile');
			art.appendChild(el('div', 'tile-title', opts.title));
		}
		if (opts.pill) art.appendChild(el('span', 'pill' + (opts.pillCls ? ' ' + opts.pillCls : ''), opts.pill));
		if (opts.locked) {
			var lk = el('span', 'lock pill');
			lk.appendChild(icon('lock'));
			lk.firstChild.style.cssText = 'width:22px;height:22px;fill:none;stroke:#fff;stroke-width:2';
			art.appendChild(lk);
		}
		c.appendChild(art);
		if (opts.caption) {
			var cap = el('div', 'card-caption');
			cap.appendChild(el('div', 'card-title', opts.title));
			if (opts.sub) cap.appendChild(el('div', 'card-sub', opts.sub));
			c.appendChild(cap);
		}
		c._action = opts.action;
		c._hero = opts.hero;
		return c;
	}

	function rowEl(parent, title, cards, cls) {
		if (!cards.length) return;
		var r = el('section', 'row' + (cls ? ' ' + cls : ''));
		r.appendChild(el('div', 'row-title', title));
		var track = el('div', 'row-track');
		cards.forEach(function (c) { track.appendChild(c); });
		r.appendChild(track);
		parent.appendChild(r);
	}

	function grid(parent, cards, cls) {
		var g = el('div', 'grid' + (cls ? ' ' + cls : ''));
		cards.forEach(function (c) { g.appendChild(c); });
		parent.appendChild(g);
		return g;
	}

	// --- képernyők kezelése ------------------------------------------------------------
	function skeleton(box) {
		var w = el('div', 'skel-wrap');
		for (var r = 0; r < 2; r++) {
			w.appendChild(el('div', 'skel-line skeleton'));
			var row = el('div', 'skel-row');
			for (var i = 0; i < 5; i++) row.appendChild(el('div', 'skel-card skeleton'));
			w.appendChild(row);
		}
		box.appendChild(w);
	}

	function message(box, text, retry) {
		var m = el('div', 'message');
		m.appendChild(el('div', '', text));
		if (retry) m.appendChild(button('Újra', retry, 'primary', 'retry'));
		box.appendChild(m);
	}

	function render() {
		var t = top();
		clearTimeout(heroTimer);
		content.innerHTML = '';
		t.build(content, t);
		if (current() && rail.contains(current())) return;
		var key = t.lastKey;
		var target = (key && content.querySelector('[data-key="' + key + '"]')) ||
			focusables(content)[0];
		if (target) {
			focus(target);
		} else if (current()) {
			current().classList.remove('focused');   // a tartalom még töltődik
		}
	}

	function push(title, build) {
		stack.push({title: title, build: build, lastKey: null});
		render();
	}

	function setTab(key) {
		tab = key;
		Array.prototype.forEach.call(rail.querySelectorAll('.rail-item'), function (r) {
			r.classList.toggle('active', r.getAttribute('data-tab') === key);
		});
		var t = TABS.filter(function (x) { return x.key === key; })[0];
		stack = [{title: t.label, build: SCREENS[key], lastKey: null}];
		var cur = current();
		if (cur) cur.classList.remove('focused');
		render();
	}

	function back() {
		if (stack.length > 1) {
			stack.pop();
			render();
		} else if (tab !== 'home') {
			setTab('home');
		} else if (global.PalmSystem && global.PalmSystem.platformBack) {
			global.PalmSystem.platformBack();
		} else {
			global.close();
		}
	}

	// async tartalom: csontváz, majd kitöltés; ha közben elnavigáltunk, eldobjuk
	function load(box, promise, fill) {
		var holder = el('div', '');
		box.appendChild(holder);
		skeleton(holder);
		var owner = top();
		return promise.then(function (data) {
			if (top() !== owner || !holder.parentNode) return;
			holder.innerHTML = '';
			fill(holder, data);
			var key = owner.lastKey;
			var t = key ? holder.querySelector('[data-key="' + key + '"]') : null;
			if (!current() || !rail.contains(current())) focus(t || focusables(content)[0]);
		}, function (err) {
			if (top() !== owner || !holder.parentNode) return;
			holder.innerHTML = '';
			message(holder, errMsg(err), function () { render(); });
			if (!current() || !rail.contains(current())) focus(focusables(content)[0]);
		});
	}

	function button(label, action, cls, key, iconName) {
		var b = el('div', 'button focusable' + (cls ? ' ' + cls : ''));
		if (iconName) b.appendChild(icon(iconName));
		b.appendChild(el('span', '', label));
		if (key) b.setAttribute('data-key', key);
		b._action = action;
		return b;
	}

	function page(box, title, sub, anchor) {
		var p = el('div', 'page');
		p.setAttribute('data-anchor', String(anchor || 340));
		if (title) {
			var head = el('div', 'page-head');
			head.appendChild(el('div', 'page-title', title));
			if (sub) head.appendChild(el('div', 'page-sub', sub));
			p.appendChild(head);
		}
		box.appendChild(p);
		return p;
	}

	// --- keresés -------------------------------------------------------------------------
	function textField(label, value, type, onDone, cls) {
		var wrap = el('div', 'field focusable' + (cls ? ' ' + cls : ''));
		wrap.setAttribute('data-key', 'f:' + label);
		if (label) wrap.appendChild(el('div', 'field-label', label));
		var input = el('input', 'field-input');
		input.type = type || 'text';
		input.value = value || '';
		input.setAttribute('autocomplete', 'off');
		wrap.appendChild(input);
		wrap._input = input;
		wrap._action = function () { input.focus(); };
		input.addEventListener('keydown', function (e) {
			if (e.keyCode === KEY.OK || e.keyCode === KEY.BACK || e.keyCode === KEY.ESC) {
				e.preventDefault();
				e.stopPropagation();
				input.blur();
				if (e.keyCode === KEY.OK && onDone) onDone(input.value);
			}
			if (e.keyCode === KEY.UP || e.keyCode === KEY.DOWN) {
				e.preventDefault();
				e.stopPropagation();
				input.blur();
				move(DIRS[e.keyCode]);
			}
		});
		return wrap;
	}

	// --- beállítások ---------------------------------------------------------------------
	function choice(label, key, options) {
		var wrap = el('div', 'field focusable');
		wrap.setAttribute('data-key', 'set:' + key);
		wrap.appendChild(el('div', 'field-label', label));
		var val = el('div', 'field-value');
		wrap.appendChild(val);
		var idx = function () {
			var v = Store.setting(key);
			for (var i = 0; i < options.length; i++) if (options[i][0] === v) return i;
			return 0;
		};
		var show = function () { val.textContent = options[idx()][1] + '  ›'; };
		show();
		wrap._action = function () {
			var o = {};
			o[key] = options[(idx() + 1) % options.length][0];
			Store.saveSettings(o);
			show();
		};
		return wrap;
	}

	// --- helyi könyvtár: kedvencek, előzmények, megnézett részek -------------------------
	function favorites() {
		return Store.get('favs', []) || [];
	}

	function isFavorite(aid) {
		return favorites().some(function (f) { return f.aid === aid; });
	}

	function toggleFavorite(a) {
		var list = favorites();
		var had = list.some(function (f) { return f.aid === a.aid; });
		list = list.filter(function (f) { return f.aid !== a.aid; });
		if (!had) list.unshift({aid: a.aid, title: a.title, art: a.art});
		Store.set('favs', list);
		return !had;
	}

	function history() {
		return Store.get('history', []) || [];
	}

	function addHistory(a, ep) {
		var list = history().filter(function (h) { return h.aid !== a.aid; });
		var prev = history().filter(function (h) { return h.aid === a.aid; })[0] || {};
		list.unshift({aid: a.aid, title: a.title, art: a.art, ts: Date.now(),
			last: ep ? ep.title : prev.last, lastVid: ep ? ep.vid : prev.lastVid});
		Store.set('history', list.slice(0, 60));
	}

	function watched() {
		return Store.get('watched', {}) || {};
	}

	function markWatched(vid) {
		var w = watched();
		w[vid] = Date.now();
		var keys = Object.keys(w);
		if (keys.length > 3000) {
			keys.sort(function (a, b) { return w[a] - w[b]; }).slice(0, keys.length - 3000)
				.forEach(function (k) { delete w[k]; });
		}
		Store.set('watched', w);
	}

	// --- kártyák -----------------------------------------------------------------------------
	function animeHero(a) {
		return {aid: a.aid, title: a.title, poster: a.art, desc: '', meta: a.sub ? [a.sub] : []};
	}

	function animeCard(a, key, caption) {
		var c = card({key: key, title: a.title, sub: a.sub, caption: caption, image: a.art,
			hero: animeHero(a), action: function () { openAnime(a); }});
		c.classList.add('portrait');
		return c;
	}

	function episodeCard(anime, ep, key, seen) {
		var c = card({key: key, title: ep.title, sub: ep.filler || '', caption: true,
			image: ep.thumb, pill: ep.filler ? ep.filler : '', pillCls: 'filler',
			action: function () { playEpisode(anime, ep); }});
		if (seen) {
			c.classList.add('seen');
			c.querySelector('.card-art').appendChild(el('span', 'watched', '✓'));
		}
		return c;
	}

	// a hero kiegészítése az anime ismertetőjével, ha a kártyán időzünk (oldal-lekérés,
	// nem számít a napi videó-limitbe; 1 napig tárolva)
	var infoTimer = null;

	function heroInfoLater(d) {
		clearTimeout(infoTimer);
		if (!d.aid || d.desc) return;
		infoTimer = setTimeout(function () {
			Api.animeInfo(d.aid).then(function (info) {
				var h = content.querySelector('.hero.dynamic');
				if (!h || !h._current || h._current.aid !== d.aid) return;
				var nd = {aid: d.aid, title: d.title, poster: d.poster, desc: info.plot,
					meta: info.meta && info.meta.length ? info.meta : d.meta};
				h._current = null;
				setHero(h, nd, true);
			}, function () {});
		}, 1200);
	}

	// --- főoldal --------------------------------------------------------------------------------
	function noCookie(box) {
		var p = page(box, 'Üdv a MagyarAnime-ben!', 'A böngészéshez és a lejátszáshoz add meg a ' +
			'saját MagyarAnime-munkamenetedet (sütit).');
		var acts = el('div', 'actions');
		acts.appendChild(button('Süti megadása telefonról', pairCookie, 'primary', 'pair'));
		acts.appendChild(button('Beállítások', function () { setTab('settings'); }, '', 'settings'));
		p.appendChild(acts);
	}

	function homeScreen(box) {
		if (!Api.cookieNames().length) return noCookie(box);
		var hero = heroBox(box);
		hero.classList.add('dynamic');
		var vp = el('div', 'rows-viewport');
		box.appendChild(vp);
		var cur = Api.catalog(1, {allapot: '1'}).catch(function () { return {items: []}; });
		var newest = Api.catalog(1, {allapot: '-1', rendezes: '4'}).catch(function () {
			return {items: []};
		});
		load(vp, Promise.all([cur, newest]), function (holder, res) {
			var rows = el('div', 'rows');
			holder.appendChild(rows);
			var hist = history().filter(function (h) { return h.lastVid; }).slice(0, 20);
			rowEl(rows, 'Folytatás', hist.map(function (h, i) {
				return animeCard({aid: h.aid, title: h.title, art: h.art || Api.poster(h.aid),
					sub: h.last ? 'utoljára: ' + h.last : ''}, 'h:' + i);
			}), 'portrait-row');
			rowEl(rows, 'Kedvencek', favorites().map(function (f, i) {
				return animeCard({aid: f.aid, title: f.title, art: f.art || Api.poster(f.aid)}, 'f:' + i);
			}), 'portrait-row');
			rowEl(rows, 'Aktuális szezon', (res[0].items || []).map(function (a, i) {
				return animeCard(a, 'c:' + i);
			}), 'portrait-row');
			rowEl(rows, 'Legújabb animék', (res[1].items || []).map(function (a, i) {
				return animeCard(a, 'n:' + i);
			}), 'portrait-row');
			if (!rows.children.length) {
				message(holder, 'Nem jött adat az oldalról - be vagy jelentkezve? ' +
					'(Beállítások → Kapcsolat teszt)', function () { render(); });
				return;
			}
			var first = rows.querySelector('.card');
			if (first && first._hero) setHero(hero, first._hero);
		});
	}

	// --- böngészés (adatlapok) -------------------------------------------------------------
	var FILTER_TITLES = {szezon: 'Szezon szerint', besorolas: 'Besorolás szerint',
		allapot: 'Állapot szerint', rendezes: 'Rendezés szerint', kezdo: 'Kezdőbetű szerint'};

	function tile(title, sub, key, action) {
		return card({key: key, title: title, sub: sub, caption: false, action: action});
	}

	function browseScreen(box) {
		var p = page(box, 'Böngészés', 'Az oldal adatlapjai, szűrőkkel');
		var presets = [
			['Aktuális szezon', {allapot: '1'}],
			['Összes anime (A–Z)', {allapot: '-1', rendezes: '1'}],
			['Legújabbak', {allapot: '-1', rendezes: '4'}]
		];
		var cards = presets.map(function (pr, i) {
			return tile(pr[0], '', 'pre:' + i, function () { openCatalog(pr[0], pr[1]); });
		});
		Object.keys(FILTER_TITLES).forEach(function (which) {
			cards.push(tile(FILTER_TITLES[which], '', 'flt:' + which, function () {
				openFilter(which);
			}));
		});
		grid(p, cards);
	}

	function openFilter(which) {
		push(FILTER_TITLES[which], function (box) {
			var p = page(box, FILTER_TITLES[which], '');
			load(p, Api.catalogFilters(), function (holder, filters) {
				var opts = filters[which] || [];
				if (!opts.length) {
					message(holder, 'Nem sikerült betölteni a szűrőt.', function () { render(); });
					return;
				}
				grid(holder, opts.map(function (o, i) {
					var f = {};
					f[which] = o[0];
					if (which !== 'allapot') f.allapot = '-1';
					return tile(o[1], '', 'o:' + i, function () { openCatalog(o[1], f); });
				}));
			});
		});
	}

	function openCatalog(title, filters) {
		push(title, function (box, st) {
			st.pages = st.pages || 1;
			var p = page(box, title, '');
			var holder = el('div', '');
			p.appendChild(holder);
			var g = null;
			var more = null;
			var loadPage = function (n, first) {
				var promise = Api.catalog(n, filters);
				var fill = function (target, data) {
					if (!g) g = grid(target, [], 'portrait-grid');
					(data.items || []).forEach(function (a, i) {
						g.appendChild(animeCard(a, 'a:' + n + ':' + i, true));
					});
					if (more) more.remove();
					if (n < data.pages) {
						more = card({key: 'more:' + n, title: 'Következő oldal (' + (n + 1) + '/' +
							data.pages + ')', action: function () {
								st.pages = n + 1;
								more.remove();
								more = null;
								loadPage(n + 1, false);
							}});
						more.classList.add('portrait');
						g.appendChild(more);
					}
					if (!g.children.length) message(target, 'Nincs találat (be vagy jelentkezve?)');
				};
				if (first) return load(holder, promise, fill);
				return promise.then(function (data) {
					fill(holder, data);
					if (restoring) return;
					var t = holder.querySelector('[data-key="a:' + n + ':0"]');
					if (t) focus(t);
				}, function (err) { toast(errMsg(err), 6000); });
			};
			// visszalépéskor az addig betöltött oldalak újra, majd a fókusz a megjegyzett helyre
			var restoring = st.pages > 1;
			var wanted = st.lastKey;   // a betöltés közbeni fókuszálás felülírná
			var chain = Promise.resolve();
			for (var n = 1; n <= st.pages; n++) {
				(function (k) {
					chain = chain.then(function () { return loadPage(k, k === 1); });
				})(n);
			}
			chain.then(function () {
				var t = restoring && wanted && holder.querySelector('[data-key="' + wanted + '"]');
				restoring = false;
				if (t && top() === st && !rail.contains(current())) focus(t);
			});
		});
	}

	// --- kedvencek, előzmények ---------------------------------------------------------------
	function favoritesScreen(box) {
		var p = page(box, 'Kedvencek', 'Helyben tárolva, nem fogyaszt napi limitet');
		var list = favorites();
		if (!list.length) {
			message(p, 'Még nincs kedvenc - egy anime adatlapján: ★ Kedvencekhez.');
			return;
		}
		grid(p, list.map(function (f, i) {
			return animeCard({aid: f.aid, title: f.title, art: f.art || Api.poster(f.aid)}, 'f:' + i, true);
		}), 'portrait-grid');
	}

	function historyScreen(box) {
		var p = page(box, 'Előzmények', 'Legutóbb nézett animék');
		var list = history();
		if (!list.length) {
			message(p, 'Még nincs előzmény.');
			return;
		}
		grid(p, list.map(function (h, i) {
			return animeCard({aid: h.aid, title: h.title, art: h.art || Api.poster(h.aid),
				sub: h.last ? 'utoljára: ' + h.last : ''}, 'h:' + i, true);
		}), 'portrait-grid');
		var acts = el('div', 'actions');
		acts.appendChild(button('Előzmények törlése', function () {
			Store.remove('history');
			toast('Előzmények törölve');
			render();
		}, '', 'clear'));
		p.appendChild(acts);
	}

	// --- anime adatlap ---------------------------------------------------------------------
	function openAnime(a) {
		push(a.title, function (box) {
			var p = page(box, '', '', 300);
			load(p, Api.episodesOfAnime(a.aid), function (holder, d) {
				var anime = {aid: a.aid, title: d.title || a.title, art: a.art || Api.poster(a.aid)};
				var eps = d.episodes || [];
				var w = watched();
				var dh = el('div', 'detail-hero');
				holder.appendChild(dh);
				var hero = heroBox(dh);
				var actions = el('div', 'actions');
				var hist = history().filter(function (h) { return h.aid === a.aid; })[0];
				var nextEp = eps.filter(function (e) { return !w[e.vid]; })[0] || eps[0];
				if (hist && hist.lastVid) {
					var idx = eps.map(function (e) { return e.vid; }).indexOf(hist.lastVid);
					if (idx >= 0) nextEp = w[eps[idx].vid] && eps[idx + 1] ? eps[idx + 1] : eps[idx];
				}
				if (nextEp) {
					var label = hist ? 'Folytatás: ' + nextEp.title : 'Lejátszás: ' + nextEp.title;
					actions.appendChild(button(label, function () { playEpisode(anime, nextEp); },
						'primary', 'play', 'play'));
				}
				var favBtn = button(isFavorite(a.aid) ? '★ Kedvenc' : '☆ Kedvencekhez', function () {
					var on = toggleFavorite(anime);
					favBtn.querySelector('span').textContent = on ? '★ Kedvenc' : '☆ Kedvencekhez';
					toast(on ? 'Hozzáadva a kedvencekhez' : 'Törölve a kedvencekből', 2500);
				}, '', 'fav');
				actions.appendChild(favBtn);
				setHero(hero, {title: anime.title, poster: anime.art, desc: d.plot,
					meta: (d.meta || []).concat(eps.length ? [eps.length + ' rész elérhető'] : []),
					extra: actions, longDesc: true}, true);
				if (!eps.length) {
					message(holder, 'Nincs elérhető rész (vagy nincs bejelentkezve).');
					return;
				}
				holder.appendChild(el('div', 'section-title', 'Részek'));
				grid(holder, eps.map(function (e, i) {
					return episodeCard(anime, e, 'e:' + i, !!w[e.vid]);
				}));
			});
		});
	}

	// --- lejátszás --------------------------------------------------------------------------
	function playEpisode(anime, ep) {
		if (Store.setting('epClick') === 'instant') {
			resolveAndPlay(anime, ep, null);
			return;
		}
		toast('Szerverek lekérése…', 2000);
		Api.listServers(ep.vid).then(function (servers) {
			if (!servers.length) {
				toast('Nincs elérhető szerver / forrás', 5000);
				return;
			}
			var list = el('div', 'server-list');
			servers.forEach(function (s, i) {
				var mega = /mega/i.test(s.host);
				var b = button((s.host.charAt(0).toUpperCase() + s.host.slice(1)) +
					(mega ? ' (nem támogatott)' : ''), function () {
					closeModal();
					resolveAndPlay(anime, ep, s.server);
				}, mega ? 'disabled' : (i === 0 ? 'primary' : ''), 'srv:' + i);
				if (s.quality) b.appendChild(el('span', 'pill', s.quality));
				list.appendChild(b);
			});
			openModal(ep.title, 'Ma ' + Api.todayCount() + ' / ' + Api.DAILY_MAX +
				' forrás-lekérés (helyi számláló)', [], list);
		}, function (err) { alertBox(ep.title, errMsg(err)); });
	}

	function resolveAndPlay(anime, ep, server) {
		toast('Forrás keresése…', 2500);
		Api.resolve(ep.vid, server).then(function (src) {
			addHistory(anime, ep);
			Player.play(src, anime.title + ' – ' + ep.title, function (pos) {
				if (pos.duration && pos.time / pos.duration > 0.85) markWatched(ep.vid);
				focusContent();
			});
		}, function (err) { alertBox(ep.title, errMsg(err)); });
	}

	// --- keresés --------------------------------------------------------------------------
	function searchScreen(box) {
		var p = page(box, 'Keresés', 'Cím, japán vagy egyéb név szerint', 200);
		var results = el('div', 'results');
		var field = textField('', top().term || '', 'text', function (term) {
			term = (term || '').trim();
			if (!term) return;
			top().term = term;
			run(term);
		}, 'search-field');
		field._input.placeholder = 'Melyik animét keresed?';
		p.appendChild(field);
		p.appendChild(results);
		function run(term) {
			results.innerHTML = '';
			load(results, Api.search(term), function (holder, list) {
				if (!list.length) {
					message(holder, 'Nincs találat: ' + term);
					return;
				}
				grid(holder, list.map(function (a, i) { return animeCard(a, 's:' + i, true); }),
					'portrait-grid');
			});
		}
		if (top().term) run(top().term);
	}

	// --- süti -------------------------------------------------------------------------------
	function saveCookie(text) {
		var names = Api.setCookieText(text);
		Api.clearCache();
		if (names.length) toast('Süti elmentve (' + names.join(', ') + ')', 4000);
		else toast('Nem találtam sütit a szövegben', 5000);
		return names;
	}

	function pairCookie() {
		var info = el('div', 'pair-box');
		info.appendChild(el('div', '', 'Csatlakozás…'));
		var cancel = null;
		modalClose = function () { if (cancel) cancel(); };
		openModal('Süti telefonról', '', [button('Mégse', closeModal, '', 'pair:cancel')], info);
		cancel = global.MABridge.subscribe('pair', {}, function (res) {
			if (res.returnValue === false || res.failed) {
				info.innerHTML = '';
				info.appendChild(el('div', '', (res.errorText || 'Nem sikerült') +
					(res.failed ? '' : '. A TV nem engedi a helyi oldalt - használd a „Süti beírása” ' +
						'lehetőséget.')));
				return;
			}
			if (res.cookieText) {
				var names = saveCookie(res.cookieText);
				modalClose = null;
				cancel();
				closeModal();
				if (names.length) setTab('home');
				return;
			}
			if (res.pin) {
				info.innerHTML = '';
				info.appendChild(el('div', '', 'A telefonodon (ugyanazon a Wi-Fi-n) nyisd meg:'));
				info.appendChild(el('div', 'pair-url', res.url || ('a TV IP-címe, port ' + res.port)));
				info.appendChild(el('div', '', 'és add meg ezt a PIN-kódot:'));
				info.appendChild(el('div', 'pair-pin', res.pin));
				info.appendChild(el('div', '', 'Ott másold be a Cookie-Editor exportot - a TV ' +
					'magától átveszi.'));
			}
		});
	}

	function typeCookie() {
		var field = textField('Süti (PHPSESSID=…; loginkey=…)', '', 'text', function (v) {
			if (v.trim()) {
				closeModal();
				saveCookie(v);
			}
		});
		openModal('Süti beírása', 'Írd be a „név=érték; név=érték” formát. Kényelmesebb a ' +
			'„Süti telefonról”.', [button('Mentés', function () {
			var v = field._input.value;
			closeModal();
			if (v.trim()) saveCookie(v);
		}, 'primary', 'type:save')], field);
	}

	// --- beállítások ----------------------------------------------------------------------
	function settingsScreen(box) {
		var p = page(box, 'Beállítások', 'Ma ' + Api.todayCount() + ' / ' + Api.DAILY_MAX +
			' forrás-lekérés (helyi számláló)', 360);
		var form = el('div', 'form');
		var names = Api.cookieNames();
		var ck = el('div', 'field focusable');
		ck.setAttribute('data-key', 'set:cookie');
		ck.appendChild(el('div', 'field-label', 'Süti (munkamenet)'));
		ck.appendChild(el('div', 'field-value', names.length ? names.length + ' süti: ' +
			names.join(', ') : 'nincs megadva  ›'));
		ck._action = pairCookie;
		form.appendChild(ck);
		var row1 = el('div', 'buttons');
		row1.appendChild(button('Süti telefonról', pairCookie, 'primary', 'b:pair'));
		row1.appendChild(button('Süti beírása', typeCookie, '', 'b:type'));
		row1.appendChild(button('Kapcsolat teszt', function () {
			toast('Ellenőrzés…', 2000);
			Api.checkLogin().then(function (r) {
				alertBox('Kapcsolat teszt', 'Sütik: ' + (Api.cookieNames().join(', ') || '-') +
					'\nFőoldal: ' + r.length + ' bájt\nBejelentkezve: ' + (r.ok ? 'IGEN' :
						'NEM (lejárt süti? más IP / böngésző?)'));
			}, function (err) { alertBox('Kapcsolat teszt', errMsg(err)); });
		}, '', 'b:test'));
		row1.appendChild(button('Süti törlése', function () {
			Api.clearCookies();
			toast('Süti törölve');
			render();
		}, '', 'b:clear'));
		form.appendChild(row1);
		var baseField = textField('Alap URL (csak domainváltáskor)', Store.setting('baseUrl'), 'url',
			function (v) {
				Store.saveSettings({baseUrl: v.trim() || 'https://magyaranime.eu/'});
				Api.clearCache();
				toast('Elmentve');
			});
		form.appendChild(baseField);
		form.appendChild(choice('Részre kattintva', 'epClick',
			[['servers', 'Szerverlista (választás)'], ['instant', 'Azonnali lejátszás (kevesebb kérés)']]));
		form.appendChild(choice('Lejátszó (HLS)', 'engine',
			[['shaka', 'Shaka (ajánlott)'], ['native', 'webOS beépített (tartalék)']]));
		form.appendChild(choice('Videó-továbbító (Referer-fejléc)', 'proxy',
			[['auto', 'Automatikus'], ['off', 'Ki (közvetlen lejátszás)']]));
		var row2 = el('div', 'buttons');
		row2.appendChild(button('Gyorsítótár törlése', function () {
			toast(Api.clearCache() + ' tétel törölve');
		}, '', 'b:cache'));
		row2.appendChild(button('Előzmények törlése', function () {
			Store.remove('history');
			toast('Előzmények törölve');
		}, '', 'b:hist'));
		form.appendChild(row2);
		form.appendChild(el('div', 'note', 'Személyes, privát alkalmazás a saját MagyarAnime-' +
			'fiókodhoz. A süti csak ezen a TV-n tárolódik. A napi videó-limitet az oldal ' +
			'számolja; ez a számláló csak tájékoztató.'));
		p.appendChild(form);
	}

	var SCREENS = {search: searchScreen, home: homeScreen, browse: browseScreen,
		favorites: favoritesScreen, history: historyScreen, settings: settingsScreen};

	// --- párbeszédablakok ------------------------------------------------------------------
	function openModal(title, body, buttons, extra) {
		modal.innerHTML = '';
		var d = el('div', 'dialog');
		d.appendChild(el('div', 'dialog-title', title));
		if (body) d.appendChild(el('div', 'dialog-body', body));
		if (extra) d.appendChild(extra);
		var row = el('div', 'dialog-buttons');
		buttons.forEach(function (b) { row.appendChild(b); });
		d.appendChild(row);
		modal.appendChild(d);
		modal._return = current();
		modal.classList.add('open');
		focus(focusables(modal)[0]);
	}

	function closeModal() {
		var ret = modal._return;
		modal.classList.remove('open');
		modal.innerHTML = '';
		if (ret && document.body.contains(ret)) focus(ret); else focusContent();
		var cb = modalClose;
		modalClose = null;
		if (cb) cb();
	}

	function choose(title, options, picked) {
		openModal(title, '', options.map(function (label, i) {
			return button(label, function () {
				closeModal();
				picked(i);
			}, i === 0 ? 'primary' : '');
		}));
	}

	function alertBox(title, text) {
		openModal(title, text, [button('OK', closeModal, 'primary')]);
	}

	// --- billentyűk és mutató ----------------------------------------------------------------
	function onKey(e) {
		if (Player.handleKey(e)) {
			e.preventDefault();
			return;
		}
		if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
		var code = e.keyCode;
		if (DIRS[code]) {
			e.preventDefault();
			move(DIRS[code]);
		} else if (code === KEY.OK) {
			e.preventDefault();
			var cur = current();
			if (cur && cur._action) cur._action();
		} else if (code === KEY.BACK || code === KEY.ESC || code === KEY.BACKSPACE) {
			e.preventDefault();
			if (modalOpen()) closeModal();
			else if (current() && rail.contains(current())) focusContent();
			else back();
		}
	}

	function onPointer(e) {
		// Magic Remote: rámutatás = fókusz, kattintás = OK
		var t = e.target.closest ? e.target.closest('.focusable') : null;
		if (!t) return;
		if (modalOpen() && !modal.contains(t)) return;
		if (e.type === 'mouseover') {
			if (t !== current()) focus(t);
		} else if (t._action) {
			t._action();
		}
	}

	function buildRail() {
		var logo = img('largeIcon.png');
		logo.className = 'rail-logo';
		logo.loading = 'eager';
		rail.appendChild(logo);
		TABS.forEach(function (t) {
			var item = el('div', 'rail-item focusable');
			item.setAttribute('data-tab', t.key);
			item.appendChild(icon(t.icon));
			item.appendChild(el('span', 'rail-label', t.label));
			item._action = function () { setTab(t.key); };
			rail.appendChild(item);
		});
	}

	function init() {
		rail = document.getElementById('rail');
		content = document.getElementById('content');
		modal = document.getElementById('modal');
		toastEl = document.getElementById('toast');
		Player.init();
		buildRail();
		document.addEventListener('keydown', onKey);
		document.addEventListener('mouseover', onPointer);
		document.addEventListener('click', onPointer);
		setTab('home');
	}

	global.MAUI = {init: init};
	document.addEventListener('DOMContentLoaded', init);
})(window);
