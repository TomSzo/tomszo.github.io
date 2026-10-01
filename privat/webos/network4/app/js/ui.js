/*
 * Felület (streaming-stílus): bal oldali menüsáv, nagy hero-kép a kijelölt elemmel,
 * vízszintes sorok, gyűjtemény-adatlap, rácsok. Távirányítós navigáció: sorokon belül
 * balra / jobbra, sorok között fel / le (a sor megjegyzi, hol jártunk), balra a menü.
 */
(function (global) {
	'use strict';

	var Api = global.N4Api;
	var Store = global.N4Store;
	var Player = global.N4Player;
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27, BACKSPACE: 8};
	var DIRS = {37: 'left', 38: 'up', 39: 'right', 40: 'down'};
	var MONTHS = ['jan.', 'febr.', 'márc.', 'ápr.', 'máj.', 'jún.', 'júl.', 'aug.', 'szept.',
		'okt.', 'nov.', 'dec.'];
	var ICONS = {
		search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
		home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
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
		{key: 'live', label: 'Élő', icon: 'live'},
		{key: 'sports', label: 'Sportok', icon: 'sports'},
		{key: 'library', label: 'Videótár', icon: 'library'},
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

	// "2026-09-25T18:00:00.000000Z" (UTC) vagy "2026-09-23 21:00:39" (helyi idő)
	function parseTime(iso) {
		iso = String(iso || '');
		var utc = /(Z|[+-]\d\d:?\d\d)$/.test(iso);
		return new Date(iso.slice(0, 19).replace(' ', 'T') + (utc ? 'Z' : ''));
	}

	function localTime(iso) {
		if (!iso) return '';
		var d = parseTime(iso);
		if (isNaN(d.getTime())) return '';
		var p = function (n) { return (n < 10 ? '0' : '') + n; };
		return MONTHS[d.getMonth()] + ' ' + d.getDate() + '. ' + p(d.getHours()) + ':' +
			p(d.getMinutes());
	}

	function localDate(iso) {
		if (!iso) return '';
		var d = parseTime(iso);
		if (isNaN(d.getTime())) return '';
		return d.getFullYear() + '. ' + MONTHS[d.getMonth()] + ' ' + d.getDate() + '.';
	}

	function duration(sec) {
		if (!sec) return '';
		var h = Math.floor(sec / 3600);
		var m = Math.round(sec % 3600 / 60);
		return h ? h + ' ó ' + m + ' p' : m + ' perc';
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
		if (d.desc) info.appendChild(el('div', 'hero-desc', d.desc));
		if (d.extra) info.appendChild(d.extra);
	}

	function setHero(h, d, immediate) {
		if (!h || !d || h._current === d) return;
		h._current = d;
		var layers = h.querySelectorAll('.hero-bg');
		var next = layers[h._layer ^ 1];
		var old = layers[h._layer];
		var bg = d.backdrop || d.logo || '';
		next.classList.toggle('logo-only', !d.backdrop && !!d.logo);
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
		heroTimer = setTimeout(function () { setHero(h, d); }, 220);
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

	function rowEl(parent, title, cards) {
		if (!cards.length) return;
		var r = el('section', 'row');
		r.appendChild(el('div', 'row-title', title));
		var track = el('div', 'row-track');
		cards.forEach(function (c) { track.appendChild(c); });
		r.appendChild(track);
		parent.appendChild(r);
	}

	function collectionCard(c, key) {
		return card({key: key, title: c.title, image: c.art.card, logo: c.art.logo,
			hero: {title: c.title, backdrop: c.art.backdrop, logo: c.art.logo, desc: c.desc, meta: []},
			action: function () { openCollection(c.slug, c.title); }});
	}

	function sportCard(it, key) {
		var logo = Api.sized(it.img, 480);
		var c = card({key: key, title: it.name || it.slug, logo: logo,
			hero: {title: it.name || it.slug, logo: Api.sized(it.img, 800), meta: []},
			action: function () { openCollection(it.slug, it.name || it.slug); }});
		c._slug = it.slug;
		return c;
	}

	// a gyűjteménylista (képek, leírás) később érkezik: a kártyák helyben frissülnek
	function upgradeCards(root, map) {
		Array.prototype.forEach.call(root.querySelectorAll('.card'), function (c) {
			var info = c._slug && map[c._slug];
			if (!info) return;
			c._hero = {title: info.title, backdrop: info.art.backdrop, logo: info.art.logo,
				desc: info.desc, meta: []};
			if (info.art.card) {
				var art = c.querySelector('.card-art');
				var i = img(info.art.card);
				i.loading = 'eager';   // még nincs a DOM-ban - lusta betöltéssel sosem töltene be
				i.onload = function () {
					art.classList.remove('tile');
					art.innerHTML = '';
					art.appendChild(i);
				};
			}
			if (c.classList.contains('focused')) showHero(c._hero);
		});
	}

	function liveMeta(e) {
		return e.status === 'live' ? {text: 'ÉLŐ', cls: 'live'} : (localTime(e.start) || 'hamarosan');
	}

	function liveCard(e, key, caption) {
		var m = liveMeta(e);
		return card({key: key, title: e.title, sub: e.desc, caption: caption,
			image: e.art.cardLarge || e.thumb, pill: typeof m === 'string' ? m : m.text,
			pillCls: typeof m === 'string' ? '' : 'live',
			hero: {title: e.title, backdrop: e.art.backdrop, logo: '', desc: e.desc, meta: [m]},
			action: function () { playLive(e); }});
	}

	function vodCard(v, key, caption) {
		var meta = [localDate(v.date), duration(v.duration)];
		return card({key: key, title: v.title, sub: v.desc || meta.filter(Boolean).join(' · '),
			caption: caption, image: v.art.cardLarge || v.thumb, locked: v.locked,
			hero: {title: v.title, backdrop: v.art.backdrop, desc: v.plot || v.desc, meta: meta},
			action: function () { playVod(v); }});
	}

	function grid(parent, cards) {
		var g = el('div', 'grid');
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
		promise.then(function (data) {
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

	// --- főoldal és Sportok: hero + sorok ---------------------------------------------
	function browse(box, withLive, withLibrary) {
		var hero = heroBox(box);
		hero.classList.add('dynamic');
		var vp = el('div', 'rows-viewport');
		box.appendChild(vp);
		var owner = top();
		var data = Promise.all([
			withLive && Api.haveCredentials() ? Api.liveEvents().catch(function () { return []; }) :
				Promise.resolve([]),
			Api.sportCategories()
		]);
		load(vp, data, function (holder, res) {
			var live = res[0];
			var cats = res[1] || [];
			var rows = el('div', 'rows');
			holder.appendChild(rows);
			if (live.length) {
				rowEl(rows, 'Élő és hamarosan', live.map(function (e, i) {
					return liveCard(e, 'live:' + i, false);
				}));
			}
			cats.forEach(function (cat, ci) {
				var items = (cat.items || []).filter(function (i) { return i && i.slug; });
				rowEl(rows, cat.title, items.map(function (it, i) {
					return sportCard(it, 'cat' + ci + ':' + i);
				}));
			});
			if (!rows.children.length) message(holder, 'Nincs megjeleníthető tartalom.');
			var first = rows.querySelector('.card');
			if (first && first._hero) setHero(hero, first._hero);
			Api.collectionMap().then(function (map) {
				if (top() !== owner) return;
				upgradeCards(rows, map);
				if (!withLibrary) return;
				var pick = Object.keys(map).map(function (k) { return map[k]; }).filter(function (c) {
					return c.art.card && c.count && Api.isListed(c);
				}).sort(function (a, b) { return a.order - b.order; }).slice(0, 30);
				rowEl(rows, 'A videótárból', pick.map(function (c, i) {
					return collectionCard(c, 'lib:' + i);
				}));
				// ha erre a sorra emlékeztünk (visszalépés), most már fókuszálható
				var key = owner.lastKey;
				var t = key && key.indexOf('lib:') === 0 && rows.querySelector('[data-key="' + key + '"]');
				if (t && !rail.contains(current())) focus(t);
			});
		});
	}

	function homeScreen(box) {
		if (!Api.haveCredentials()) {
			var p = page(box, 'Üdv a Network4-ben!', 'Az élő közvetítésekhez és a videótárhoz ' +
				'add meg a Network4 / Arena4+ belépési adataidat.');
			var acts = el('div', 'actions');
			acts.appendChild(button('Belépési adatok megadása', function () { setTab('settings'); },
				'primary', 'login'));
			acts.appendChild(button('Sportok böngészése', function () { setTab('sports'); }, '',
				'sports'));
			p.appendChild(acts);
			return;
		}
		browse(box, true, true);
	}

	function sportsScreen(box) {
		browse(box, false, false);
	}

	// --- élő ----------------------------------------------------------------------------
	function liveScreen(box) {
		var p = page(box, 'Élő közvetítések', 'Élőben vagy az elejétől');
		load(p, Api.liveEvents(), function (holder, events) {
			if (!events.length) {
				message(holder, 'Most nincs élő vagy közelgő közvetítés.');
				return;
			}
			grid(holder, events.map(function (e, i) { return liveCard(e, 'l:' + i, true); }));
		});
	}

	function playLive(e) {
		toast('Adás betöltése…', 2000);
		Api.liveSources(e.slug).then(function (src) {
			if (!src.live && !src.replay) {
				toast('Ez a közvetítés még nem indult el');
				return;
			}
			if (src.live && src.replay && Store.setting('askReplay')) {
				choose(e.title, ['Élő (most)', 'Kezdés az elejéről'], function (i) {
					startPlayer(i === 1 ? src.replay : src.live, e.title, i !== 1);
				});
				return;
			}
			startPlayer(src.live || src.replay, e.title, !!src.live);
		}, function (err) { toast(errMsg(err), 6000); });
	}

	// --- videótár és gyűjtemény-adatlap --------------------------------------------------
	function libraryScreen(box) {
		var p = page(box, 'Videótár', 'Minden gyűjtemény');
		load(p, Api.collections(), function (holder, cols) {
			grid(holder, cols.map(function (c, i) {
				var cd = collectionCard(c, 'c:' + i);
				var cap = el('div', 'card-caption');
				cap.appendChild(el('div', 'card-title', c.title));
				if (c.count) cap.appendChild(el('div', 'card-sub', c.count + ' videó'));
				cd.appendChild(cap);
				return cd;
			}));
		});
	}

	function openCollection(slug, title) {
		push(title, function (box) {
			var p = page(box, '', '', 300);
			load(p, Api.collectionDetail(slug), function (holder, d) {
				var dh = el('div', 'detail-hero');
				holder.appendChild(dh);
				var hero = heroBox(dh);
				var firstPlayable = d.vods.filter(function (v) { return !v.locked; })[0];
				var actions = el('div', 'actions');
				if (firstPlayable) {
					actions.appendChild(button('Lejátszás', function () { playVod(firstPlayable); },
						'primary', 'play', 'play'));
				}
				setHero(hero, {title: d.title || title, backdrop: d.art.backdrop, logo: d.art.logo,
					desc: d.desc, meta: [d.vods.length ? d.vods.length + ' videó' : ''],
					extra: actions}, true);
				if (!d.vods.length) {
					message(holder, 'Nincs lejátszható videó ebben a gyűjteményben.');
					return;
				}
				holder.appendChild(el('div', 'section-title', 'Videók'));
				grid(holder, d.vods.map(function (v, i) { return vodCard(v, 'v:' + i, true); }));
			});
		});
	}

	function playVod(v) {
		if (v.locked) {
			alertBox(v.title, 'Ez a videó aláírt lejátszást igényel (token), amit a Network4 ' +
				'API most nem ad meg - egyelőre nem játszható.');
			return;
		}
		Api.vodStream(v.url).then(function (url) {
			startPlayer(url, v.title, false);
		}, function (err) { toast(errMsg(err), 6000); });
	}

	function startPlayer(url, title, live) {
		Player.play(url, title, live, function () { focusContent(); });
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

	function searchScreen(box) {
		var p = page(box, 'Keresés', 'Meccsek, összefoglalók, műsorok', 200);
		var results = el('div', 'results');
		var field = textField('', top().term || '', 'text', function (term) {
			term = (term || '').trim();
			if (!term) return;
			top().term = term;
			run(term);
		}, 'search-field');
		field._input.placeholder = 'Mit keresel?';
		p.appendChild(field);
		p.appendChild(results);
		function run(term) {
			results.innerHTML = '';
			load(results, Api.search(term), function (holder, vods) {
				if (!vods.length) {
					message(holder, 'Nincs találat: ' + term);
					return;
				}
				grid(holder, vods.map(function (v, i) { return vodCard(v, 's:' + i, true); }));
			});
		}
		if (top().term) run(top().term);
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

	function settingsScreen(box) {
		var p = page(box, 'Beállítások', 'Ma ' + Api.todayRequests() + ' kérés a Network4 felé', 360);
		var form = el('div', 'form');
		var email = textField('Email cím (Network4 / Arena4+ fiók)', Store.setting('email'), 'email');
		var pass = textField('Jelszó', Store.setting('password'), 'password');
		form.appendChild(email);
		form.appendChild(pass);
		form.appendChild(choice('Minőség (felső határ)', 'quality',
			[['1080', '1080p'], ['720', '720p'], ['auto', 'Automatikus']]));
		form.appendChild(choice('Lejátszó', 'engine',
			[['shaka', 'Shaka (ajánlott)'], ['native', 'webOS beépített (tartalék)']]));
		form.appendChild(choice('Élő adásnál kérdezze meg: élő vagy elejétől', 'askReplay',
			[[true, 'Igen'], [false, 'Nem (mindig élő)']]));
		form.appendChild(choice('Sportok frissítése a weboldalról (naponta 1x)', 'sportWeb',
			[[true, 'Igen'], [false, 'Nem (beépített lista)']]));
		form.appendChild(choice('Kapcsolat a Network4 felé', 'connection',
			[['auto', 'Automatikus (TV böngésző, ha kell: szolgáltatás)'],
				['browser', 'Csak TV böngésző'], ['service', 'Csak háttérszolgáltatás']]));
		form.appendChild(choice('API User-Agent (csak szolgáltatásnál)', 'apiUa',
			[['app', 'Network4 mobilalkalmazás (Dart)'], ['firefox', 'Firefox (Android)']]));

		var save = function () {
			var changed = email._input.value.trim() !== Store.setting('email') ||
				pass._input.value !== Store.setting('password');
			Store.saveSettings({email: email._input.value.trim(), password: pass._input.value});
			if (changed) Api.clearToken();
		};
		var row = el('div', 'buttons');
		row.appendChild(button('Mentés', function () {
			save();
			toast('Elmentve');
			setTab('home');
		}, 'primary', 'b:save'));
		row.appendChild(button('Kapcsolat teszt', function () {
			save();
			Api.clearToken();
			toast('Belépés…', 2000);
			Api.login().then(function () {
				alertBox('Kapcsolat teszt', 'Sikeres belépés (út: ' + global.N4Bridge.state.lastVia +
					'). Ma ' + Api.todayRequests() + ' kérés.');
			}, function (err) {
				alertBox('Kapcsolat teszt', errMsg(err) + ' (utolsó út: ' +
					(global.N4Bridge.state.lastVia || '-') + ')');
			});
		}, '', 'b:test'));
		row.appendChild(button('Munkamenet törlése', function () {
			Api.clearToken();
			toast('Munkamenet törölve - a következő kérésnél újra belép');
		}, '', 'b:session'));
		row.appendChild(button('Gyorsítótár törlése', function () {
			toast(Api.clearCache() + ' tétel törölve');
		}, '', 'b:cache'));
		form.appendChild(row);
		form.appendChild(el('div', 'note', 'Nem hivatalos alkalmazás, nincs kapcsolatban a ' +
			'Network4-gyel. Saját, érvényes előfizetés kell hozzá. A belépési adat csak ezen a ' +
			'TV-n tárolódik. Alap: Arena4Plus (heg, vargalex).'));
		p.appendChild(form);
	}

	var SCREENS = {search: searchScreen, home: homeScreen, live: liveScreen,
		sports: sportsScreen, library: libraryScreen, settings: settingsScreen};

	// --- párbeszédablakok ------------------------------------------------------------------
	function openModal(title, body, buttons) {
		modal.innerHTML = '';
		var d = el('div', 'dialog');
		d.appendChild(el('div', 'dialog-title', title));
		if (body) d.appendChild(el('div', 'dialog-body', body));
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

	global.N4UI = {init: init, localTime: localTime};
	document.addEventListener('DOMContentLoaded', init);
})(window);
