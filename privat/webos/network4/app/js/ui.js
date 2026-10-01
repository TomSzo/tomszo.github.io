/*
 * Felület: képernyő-verem (Főmenü → lista → ...), távirányítós térbeli navigáció,
 * párbeszédablakok, beállítások. A Kodi-kiegészítő menüszerkezetét követi.
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

	var app, header, crumbs, content, modal, toastEl;
	var stack = [];
	var modalClose = null;
	var toastTimer = null;

	// --- segédek ---------------------------------------------------------------
	function el(tag, cls, text) {
		var e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null) e.textContent = text;
		return e;
	}

	function localTime(iso) {
		if (!iso) return '';
		var d = new Date(iso.slice(0, 19) + 'Z');
		if (isNaN(d.getTime())) return '';
		var p = function (n) { return (n < 10 ? '0' : '') + n; };
		return MONTHS[d.getMonth()] + ' ' + d.getDate() + '. ' + p(d.getHours()) + ':' +
			p(d.getMinutes());
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

	// --- fókusz és térbeli navigáció -------------------------------------------
	function scope() {
		return modal.classList.contains('open') ? modal : content;
	}

	function focusables() {
		return Array.prototype.slice.call(scope().querySelectorAll('.focusable'))
			.filter(function (e) { return e.offsetParent !== null; });
	}

	function focus(target) {
		if (!target) return;
		var prev = document.querySelector('.focused');
		if (prev) prev.classList.remove('focused');
		target.classList.add('focused');
		if (target.scrollIntoView) target.scrollIntoView({block: 'nearest', inline: 'nearest'});
		if (!modal.classList.contains('open') && stack.length) {
			stack[stack.length - 1].focusIndex = focusables().indexOf(target);
		}
	}

	function current() {
		var f = scope().querySelector('.focused');
		return f || null;
	}

	function move(dir) {
		var cur = current();
		var items = focusables();
		if (!cur) return focus(items[0]);
		var a = cur.getBoundingClientRect();
		var ax = a.left + a.width / 2;
		var ay = a.top + a.height / 2;
		var best = null;
		var bestScore = Infinity;
		items.forEach(function (e) {
			if (e === cur) return;
			var b = e.getBoundingClientRect();
			var bx = b.left + b.width / 2;
			var by = b.top + b.height / 2;
			var horizontal = dir === 'left' || dir === 'right';
			var main = horizontal ? bx - ax : by - ay;
			if (dir === 'left' || dir === 'up') main = -main;
			if (main <= 1) return;
			// keresztirányú távolság: átfedő sávnál 0 (ilyenkor a sor eleje nyer), különben a rés
			var gap = horizontal ? Math.max(b.top - a.bottom, a.top - b.bottom, 0) :
				Math.max(b.left - a.right, a.left - b.right, 0);
			var edge = horizontal ? Math.abs(b.top - a.top) : Math.abs(b.left - a.left);
			var score = main + gap * 3 + edge * 0.1;
			if (score < bestScore) {
				bestScore = score;
				best = e;
			}
		});
		if (best) focus(best);
	}

	function activate(e) {
		if (e && e._action) e._action();
	}

	// --- képernyők ---------------------------------------------------------------
	function render() {
		var top = stack[stack.length - 1];
		crumbs.textContent = stack.map(function (s) { return s.title; }).join('  ›  ');
		content.innerHTML = '';
		content.scrollTop = 0;
		top.build(content);
		var items = focusables();
		focus(items[Math.min(top.focusIndex || 0, items.length - 1)] || items[0]);
	}

	function push(title, build) {
		stack.push({title: title, build: build, focusIndex: 0});
		render();
	}

	function back() {
		if (stack.length > 1) {
			stack.pop();
			render();
			return;
		}
		if (global.PalmSystem && global.PalmSystem.platformBack) {
			global.PalmSystem.platformBack();
		} else {
			global.close();
		}
	}

	function loading(box, text) {
		box.innerHTML = '';
		box.appendChild(el('div', 'loading', text || 'Betöltés…'));
	}

	function message(box, text, retry) {
		box.innerHTML = '';
		var m = el('div', 'message');
		m.appendChild(el('div', '', text));
		if (retry) {
			var b = button('Újra', retry);
			m.appendChild(b);
		}
		box.appendChild(m);
		var items = focusables();
		if (items.length) focus(items[0]);
	}

	function async(box, promise, fill) {
		loading(box);
		var token = {};
		box._token = token;
		promise.then(function (data) {
			if (box._token !== token) return;
			box.innerHTML = '';
			fill(data);
			var top = stack[stack.length - 1];
			var items = focusables();
			focus(items[Math.min(top.focusIndex || 0, items.length - 1)] || items[0]);
		}, function (err) {
			if (box._token !== token) return;
			message(box, errMsg(err), function () { render(); });
		});
	}

	function button(label, action, cls) {
		var b = el('div', 'button focusable' + (cls ? ' ' + cls : ''), label);
		b._action = action;
		return b;
	}

	function menuItem(label, sub, action) {
		var m = el('div', 'menu-item focusable');
		m.appendChild(el('div', 'menu-label', label));
		if (sub) m.appendChild(el('div', 'menu-sub', sub));
		m._action = action;
		return m;
	}

	function card(opts) {
		var c = el('div', 'card focusable' + (opts.locked ? ' locked' : ''));
		var img = el('div', 'card-img');
		if (opts.thumb) {
			var i = new Image();
			i.loading = 'lazy';
			i.src = opts.thumb;
			i.alt = '';
			img.appendChild(i);
		}
		if (opts.badge) img.appendChild(el('div', 'badge ' + (opts.badgeCls || ''), opts.badge));
		c.appendChild(img);
		c.appendChild(el('div', 'card-title', opts.title));
		if (opts.sub) c.appendChild(el('div', 'card-sub', opts.sub));
		c._action = opts.action;
		return c;
	}

	function grid(box) {
		var g = el('div', 'grid');
		box.appendChild(g);
		return g;
	}

	// --- főmenü -----------------------------------------------------------------
	function home(box) {
		var m = el('div', 'menu');
		if (!Api.haveCredentials()) {
			m.appendChild(menuItem('Belépési adatok megadása', 'Email cím és jelszó (Network4 / ' +
				'Arena4+ fiók)', function () { push('Beállítások', settings); }));
		}
		m.appendChild(menuItem('Élő közvetítések', 'Élőben vagy az elejétől', function () {
			push('Élő közvetítések', live);
		}));
		m.appendChild(menuItem('Sportok', 'Sportágak és bajnokságok', function () {
			push('Sportok', sports);
		}));
		m.appendChild(menuItem('Videótár', 'Összes gyűjtemény', function () {
			push('Videótár', collections);
		}));
		m.appendChild(menuItem('Keresés', null, function () { push('Keresés', searchScreen); }));
		m.appendChild(menuItem('Beállítások', 'Ma ' + Api.todayRequests() + ' kérés',
			function () { push('Beállítások', settings); }));
		box.appendChild(m);
	}

	// --- élő ----------------------------------------------------------------------
	function live(box) {
		async(box, Api.liveEvents(), function (events) {
			if (!events.length) {
				message(box, 'Most nincs élő vagy közelgő közvetítés.');
				return;
			}
			var g = grid(box);
			events.forEach(function (e) {
				var on = e.status === 'live';
				g.appendChild(card({title: e.title, sub: e.desc, thumb: e.thumb,
					badge: on ? '● ÉLŐ' : (localTime(e.start) || 'hamarosan'),
					badgeCls: on ? 'live' : '',
					action: function () { playLive(e); }}));
			});
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

	// --- sportok / gyűjtemények ----------------------------------------------------
	function sports(box) {
		async(box, Api.sportCategories(), function (cats) {
			var g = grid(box);
			cats.forEach(function (cat) {
				var items = (cat.items || []).filter(function (i) { return i && i.slug; });
				if (!items.length) return;
				g.appendChild(card({title: cat.title, sub: items.length + ' gyűjtemény',
					thumb: items[0].img, action: function () {
						push(cat.title, function (b) {
							var g2 = grid(b);
							items.forEach(function (it) {
								g2.appendChild(card({title: it.name || it.slug, thumb: it.img,
									action: function () { openCollection(it.name || it.slug, it.slug); }}));
							});
						});
					}}));
			});
		});
	}

	function collections(box) {
		async(box, Api.collections(), function (cols) {
			var g = grid(box);
			cols.forEach(function (c) {
				g.appendChild(card({title: c.title, thumb: c.thumb,
					action: function () { openCollection(c.title, c.slug); }}));
			});
		});
	}

	function openCollection(title, slug) {
		push(title, function (box) {
			async(box, Api.collectionItems(slug), function (vods) {
				if (!vods.length) {
					message(box, 'Nincs lejátszható videó ebben a gyűjteményben.');
					return;
				}
				vodGrid(box, vods);
			});
		});
	}

	function vodGrid(box, vods) {
		var g = grid(box);
		vods.forEach(function (v) {
			g.appendChild(card({title: v.title, sub: v.desc, thumb: v.thumb, locked: v.locked,
				badge: v.locked ? 'zárolt' : '', action: function () { playVod(v); }}));
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
		Player.play(url, title, live, function () {
			var items = focusables();
			var top = stack[stack.length - 1];
			focus(items[top.focusIndex] || items[0]);
		});
	}

	// --- keresés --------------------------------------------------------------------
	function textField(label, value, type, onDone) {
		var wrap = el('div', 'field focusable');
		wrap.appendChild(el('div', 'field-label', label));
		var input = el('input', 'field-input');
		input.type = type || 'text';
		input.value = value || '';
		input.setAttribute('autocomplete', 'off');
		wrap.appendChild(input);
		wrap._input = input;
		wrap._action = function () {
			input.focus();
		};
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
		var results = el('div', 'results');
		var run = function (term) {
			term = (term || '').trim();
			if (!term) return;
			async(results, Api.search(term), function (vods) {
				if (!vods.length) {
					message(results, 'Nincs találat: ' + term);
					return;
				}
				vodGrid(results, vods);
			});
		};
		var field = textField('Keresett szó (Network4)', '', 'text', run);
		box.appendChild(field);
		box.appendChild(results);
	}

	// --- beállítások ----------------------------------------------------------------
	function choice(label, key, options) {
		var wrap = el('div', 'field focusable');
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
			var next = options[(idx() + 1) % options.length][0];
			var o = {};
			o[key] = next;
			Store.saveSettings(o);
			show();
		};
		return wrap;
	}

	function settings(box) {
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
		form.appendChild(choice('Sportok menü frissítése a weboldalról (naponta 1x)', 'sportWeb',
			[[true, 'Igen'], [false, 'Nem (beépített lista)']]));
		form.appendChild(choice('Kapcsolat a Network4 felé', 'connection',
			[['auto', 'Automatikus (TV böngésző, ha kell: szolgáltatás)'],
				['browser', 'Csak TV böngésző'], ['service', 'Csak háttérszolgáltatás']]));
		form.appendChild(choice('API User-Agent (csak szolgáltatásnál)', 'apiUa',
			[['app', 'Network4 mobilalkalmazás (Dart)'], ['firefox', 'Firefox (Android)']]));

		var row = el('div', 'buttons');
		row.appendChild(button('Mentés', function () {
			var changed = email._input.value.trim() !== Store.setting('email') ||
				pass._input.value !== Store.setting('password');
			Store.saveSettings({email: email._input.value.trim(), password: pass._input.value});
			if (changed) Api.clearToken();
			toast('Elmentve');
			back();
		}, 'primary'));
		row.appendChild(button('Kapcsolat teszt', function () {
			Store.saveSettings({email: email._input.value.trim(), password: pass._input.value});
			Api.clearToken();
			toast('Belépés…', 2000);
			Api.login().then(function () {
				alertBox('Kapcsolat teszt', 'Sikeres belépés (út: ' + global.N4Bridge.state.lastVia +
					'). Ma ' + Api.todayRequests() + ' kérés.');
			}, function (err) {
				alertBox('Kapcsolat teszt', errMsg(err) + ' (utolsó út: ' +
					(global.N4Bridge.state.lastVia || '-') + ')');
			});
		}));
		row.appendChild(button('Munkamenet törlése', function () {
			Api.clearToken();
			Store.remove('token');
			toast('Munkamenet törölve - a következő kérésnél újra belép');
		}));
		row.appendChild(button('Gyorsítótár törlése', function () {
			toast(Api.clearCache() + ' tétel törölve');
		}));
		form.appendChild(row);
		form.appendChild(el('div', 'note', 'Nem hivatalos alkalmazás, nincs kapcsolatban a ' +
			'Network4-gyel. Saját, érvényes előfizetés kell hozzá. A belépési adat csak ezen a ' +
			'TV-n tárolódik. Alap: Arena4Plus (heg, vargalex).'));
		box.appendChild(form);
	}

	// --- párbeszédablakok -------------------------------------------------------------
	function openModal(title, body, buttons) {
		modal.innerHTML = '';
		var d = el('div', 'dialog');
		d.appendChild(el('div', 'dialog-title', title));
		if (body) d.appendChild(el('div', 'dialog-body', body));
		var row = el('div', 'dialog-buttons');
		buttons.forEach(function (b) { row.appendChild(b); });
		d.appendChild(row);
		modal.appendChild(d);
		modal.classList.add('open');
		focus(focusables()[0]);
	}

	function closeModal() {
		modal.classList.remove('open');
		modal.innerHTML = '';
		var items = focusables();
		var top = stack[stack.length - 1];
		focus(items[top.focusIndex] || items[0]);
		var cb = modalClose;
		modalClose = null;
		if (cb) cb();
	}

	function choose(title, options, picked) {
		openModal(title, '', options.map(function (label, i) {
			return button(label, function () {
				closeModal();
				picked(i);
			});
		}));
	}

	function alertBox(title, text) {
		openModal(title, text, [button('OK', closeModal)]);
	}

	// --- billentyűk -------------------------------------------------------------------
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
			activate(current());
		} else if (code === KEY.BACK || code === KEY.ESC || code === KEY.BACKSPACE) {
			e.preventDefault();
			if (modal.classList.contains('open')) closeModal(); else back();
		}
	}

	function onPointer(e) {
		// a Magic Remote mutatója: rámutatás = fókusz, kattintás = OK
		var t = e.target.closest ? e.target.closest('.focusable') : null;
		if (!t || !scope().contains(t)) return;
		if (e.type === 'mouseover') focus(t); else activate(t);
	}

	function init() {
		app = document.getElementById('app');
		header = app.querySelector('header');
		crumbs = header.querySelector('.crumbs');
		content = document.getElementById('content');
		modal = document.getElementById('modal');
		toastEl = document.getElementById('toast');
		Player.init();
		document.addEventListener('keydown', onKey);
		document.addEventListener('mouseover', onPointer);
		document.addEventListener('click', onPointer);
		push('Network4', home);
	}

	global.N4UI = {init: init, localTime: localTime};
	document.addEventListener('DOMContentLoaded', init);
})(window);
