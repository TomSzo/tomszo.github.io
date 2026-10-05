/*
 * OniAnime (webOS) - Netflix-stílusú felület az onianime.hu-hoz.
 *
 * Az onianime.hu nyilvános JSON API-ját használja (ugyanazt, amit a weboldal):
 *   /api/animes/popular, /recommended, /latest-episodes  - a kezdőlap sorai
 *   /api/animes/search?search=…                          - keresés
 *   /api/anime/<id>, /info, /episodes                    - adatlap, részek
 *   /api/anime/<id>/parts?episode=N&type=sub|dub&server=… - a rész videói (MP4)
 * Belépés nem kell. Az API nem küld CORS-fejlécet, ezért a TV-n a kérések a
 * háttérszolgáltatáson mennek (luna://hu.tomszo.onianime.service/get); ha az nem
 * válaszol, közvetlen fetch. A videók (indavideo MP4) közvetlenül a <video> elembe
 * kerülnek, saját lejátszóval (OSD, tekerés, minőségváltás, következő rész).
 *
 * A „Folytatás” és a „Listám” csak a TV-n tárolódik (localStorage), nem az
 * onianime.hu-fiókban.
 *
 * Vissza gomb: disableBackHistoryAPI - a 461-es gombot mi kezeljük (lejátszó ->
 * adatlap -> kezdőlap -> menüsáv -> kilépés).
 */
(function () {
	'use strict';

	var BASE = 'https://onianime.hu';
	var SERVICE = 'luna://hu.tomszo.onianime.service/get';
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27, BACKSPACE: 8,
		RED: 403, GREEN: 404, YELLOW: 405, BLUE: 406, PLAY: 415, PAUSE: 19, PLAYPAUSE: 10252,
		STOP: 413, FF: 417, RW: 412, CHUP: 33, CHDOWN: 34};
	var TIMEOUT = 25000;
	var SERVERS = {sub: 'karks', dub: 'miku'};   // a weboldal alapértelmezett szerverei
	var NEW_DAYS = 3;
	var TABS = ['search', 'home', 'mylist'];

	// --- állapot ---------------------------------------------------------------
	var tab = 'home';
	var zone = 'rows';        // rows | rail | sinput | sgrid | detail | player
	var rows = [];            // [{key, title, kind, items, sel, el, track}]
	var activeRow = 0;
	var railSel = 1;
	var home = null;          // a kezdőlap nyers adatai
	var infoCache = {};       // id -> Promise(info)
	var heroTimer = null, heroInfoTimer = null, toastTimer = null;
	var pending = [];         // a luna-hívások objektumai a válaszig élve maradnak
	var search = {q: '', items: [], sel: 0, req: 0, timer: null, title: ''};
	var detail = null;        // {item, info, full, eps, sel, zone, btn, buttons, type}
	var detailReq = 0;

	// --- segédek ---------------------------------------------------------------
	function $(sel, root) { return (root || document).querySelector(sel); }
	function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

	function el(tag, cls, text) {
		var e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null && text !== '') e.textContent = text;
		return e;
	}

	function pad(n) { return (n < 10 ? '0' : '') + n; }
	function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

	function fmt(sec) {
		if (!isFinite(sec) || sec < 0) sec = 0;
		sec = Math.floor(sec);
		var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
		return (h ? h + ':' + pad(m) : m) + ':' + pad(s);
	}

	function toast(msg, ms) {
		var t = $('#toast');
		t.textContent = msg;
		t.className = 'on';
		clearTimeout(toastTimer);
		toastTimer = setTimeout(function () { t.className = ''; }, ms || 3500);
	}

	// a TMDB eredeti méretű képei 4K-sak - a TV-n kisebb is elég
	function tmdb(url, size) {
		return url ? String(url).replace('/t/p/original/', '/t/p/' + size + '/') : '';
	}

	function store(key, def) {
		try {
			var v = JSON.parse(localStorage.getItem('oni.' + key) || 'null');
			return v === null ? def : v;
		} catch (e) { return def; }
	}

	function save(key, v) {
		try { localStorage.setItem('oni.' + key, JSON.stringify(v)); } catch (e) {}
	}

	function parseDate(s) {
		if (!s) return null;
		var d = new Date(String(s).replace(' ', 'T'));
		return isNaN(d.getTime()) ? null : d;
	}

	// --- HTTP ------------------------------------------------------------------
	function onTV() { return typeof window.PalmServiceBridge === 'function'; }

	function viaService(path) {
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
				if (res.status !== 200) {
					return reject(new Error('HTTP ' + res.status + (res.cloudflare ? ' (Cloudflare)' : '') +
						(res.tried ? ' [' + res.tried + ']' : '')));
				}
				resolve(res.body || '');
			};
			bridge.call(SERVICE, JSON.stringify({path: path}));
		});
	}

	function viaFetch(path) {
		var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
		var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, TIMEOUT);
		return fetch(BASE + path, {credentials: 'omit', cache: 'no-store', signal: ctrl ? ctrl.signal : undefined})
			.then(function (r) {
				clearTimeout(timer);
				if (!r.ok) throw new Error('HTTP ' + r.status);
				return r.text();
			}, function (err) {
				clearTimeout(timer);
				throw new Error(err && err.name === 'AbortError' ? 'időtúllépés' : 'a kérés nem ment át');
			});
	}

	// A TV-n először a böngészőmotor kérdez közvetlenül (a Cloudflare ezt engedi a
	// legkevésbé gyanúsnak), ha az nem megy (pl. CORS), a háttérszolgáltatás. Amelyik
	// út működött, azzal kezdünk legközelebb.
	var route = store('route', 'direct');

	function api(path) {
		var p;
		if (!onTV()) {
			p = viaFetch(path);
		} else {
			var first = route === 'service' ? viaService : viaFetch;
			var second = route === 'service' ? viaFetch : viaService;
			var names = route === 'service' ? ['szolgáltatás', 'közvetlen'] : ['közvetlen', 'szolgáltatás'];
			p = first(path).catch(function (e1) {
				return second(path).then(function (body) {
					route = route === 'service' ? 'direct' : 'service';
					save('route', route);
					return body;
				}, function (e2) {
					throw new Error(names[0] + ': ' + e1.message + '; ' + names[1] + ': ' + e2.message);
				});
			});
		}
		return p.then(function (body) {
			try { return JSON.parse(body); } catch (e) { throw new Error('hibás JSON'); }
		});
	}

	function info(id) {
		if (!infoCache[id]) {
			infoCache[id] = api('/api/anime/' + id + '/info').catch(function (err) {
				delete infoCache[id];
				throw err;
			});
		}
		return infoCache[id];
	}

	// --- adatok egységesítése --------------------------------------------------
	// a felnőtt (Rx / Hentai) tartalom kimarad, ahogy a weboldal alapból is szűri
	function adult(a) {
		return /^Rx/i.test(a.rating || '') || (a.tags || []).indexOf('Hentai') >= 0;
	}

	function norm(a) {
		var title = a.eng_name || a.name || '';
		var eps = a.part_count || a.partCount || a.ep || 0;
		return {
			id: a.id || a.anime_id,
			title: title,
			alt: a.name && a.name !== title ? a.name : '',
			image: a.image || a.anime_image || '',
			color: a.color || '',
			type: a.type || '',
			status: a.status || a.statusText || '',
			eps: eps,
			dub: (a.dub_count || 0) > 0,
			desc: a.description || '',
			rating: a.rating || '',
			bg: a.background ? tmdb(a.background, 'w1280') : '',
			logo: a.logoEn ? tmdb(a.logoEn, 'w500') : '',
			tags: a.tags || [],
			year: a.release_year || (a.formattedDate ? parseInt(a.formattedDate, 10) : 0) || 0,
			latest: parseDate(a.latest_created_at),
			rank: a.trending_rank || 0
		};
	}

	function normList(list) {
		return (list || []).filter(function (a) { return a && !adult(a); }).map(norm);
	}

	function isNew(item) {
		return item.latest && Date.now() - item.latest.getTime() < NEW_DAYS * 86400000;
	}

	function ratingShort(r) {
		var m = /^([A-Z]+(?:-\d+)?\+?)/.exec(r || '');
		return m ? m[1] : '';
	}

	// --- Folytatás / Listám (helyben) ------------------------------------------
	function progressAll() { return store('progress', {}); }

	function progressOf(id) { return progressAll()[id] || null; }

	function saveProgress(rec) {
		var all = progressAll();
		all[rec.id] = rec;
		var ids = Object.keys(all).sort(function (a, b) { return (all[b].ts || 0) - (all[a].ts || 0); });
		ids.slice(80).forEach(function (k) { delete all[k]; });
		save('progress', all);
	}

	function continueItems() {
		var all = progressAll();
		return Object.keys(all).map(function (k) { return all[k]; })
			.filter(function (p) { return !p.done; })
			.sort(function (a, b) { return (b.ts || 0) - (a.ts || 0); })
			.map(function (p) {
				return {id: p.id, title: p.title, image: p.image, bg: p.bg, color: p.color, ep: p.ep,
					t: p.t, d: p.d, thumb: p.thumb, cont: true, type: p.atype || '', status: '',
					eps: p.eps || 0, desc: p.desc || '', tags: [], alt: '', logo: p.logo || ''};
			});
	}

	function myList() { return store('list', []); }

	function inList(id) { return myList().some(function (x) { return x.id === id; }); }

	function toggleList(item) {
		var list = myList();
		var i = -1;
		list.forEach(function (x, j) { if (x.id === item.id) i = j; });
		if (i >= 0) {
			list.splice(i, 1);
			toast('Eltávolítva a listádról');
		} else {
			list.unshift({id: item.id, eng_name: item.title, name: item.alt || item.title, image: item.image,
				color: item.color, type: item.type, status: item.status, part_count: item.eps,
				description: item.desc, tags: item.tags});
			toast('Hozzáadva a listádhoz');
		}
		save('list', list);
	}

	// --- kártyák ---------------------------------------------------------------
	function pic(src, item) {
		var frag = document.createDocumentFragment();
		var ph = el('div', 'ph', item.title);
		if (item.color) ph.style.setProperty('--c', item.color);
		frag.appendChild(ph);
		if (src) {
			var img = el('img', 'pic');
			img.alt = '';
			img.onerror = function () { if (img.parentNode) img.parentNode.removeChild(img); };
			img.src = src;
			frag.appendChild(img);
		}
		return frag;
	}

	function posterCard(item) {
		var c = el('div', 'card poster');
		c.appendChild(pic(item.image, item));
		// a Top 5 (recommended) elemeiben nincs borító - az /info-ból pótoljuk
		if (!item.image && item.id) {
			info(item.id).then(function (inf) {
				if (!inf || !inf.image) return;
				item.image = inf.image;
				var img = el('img', 'pic');
				img.alt = '';
				img.onerror = function () { if (img.parentNode) img.parentNode.removeChild(img); };
				img.src = inf.image;
				c.insertBefore(img, c.children[1] || null);
			}, function () {});
		}
		if (isNew(item)) c.appendChild(el('div', 'badge', 'ÚJ RÉSZ'));
		return c;
	}

	function wideCard(item) {
		var c = el('div', 'card wide');
		c.appendChild(pic(item.thumb || item.bg || item.image, item));
		if (item.version) c.appendChild(el('div', 'badge' + (/dub/i.test(item.version) ? ' dub' : ''),
			/dub/i.test(item.version) ? 'SZINKRON' : 'ÚJ RÉSZ'));
		var cap = el('div', 'cap');
		cap.appendChild(el('div', 't', item.title));
		var sub = item.ep ? item.ep + '. rész' : '';
		if (item.epTitle) sub += ' · ' + item.epTitle;
		if (item.cont && item.d) sub += ' · ' + fmt(item.t) + ' / ' + fmt(item.d);
		cap.appendChild(el('div', 's', sub));
		c.appendChild(cap);
		if (item.cont && item.d) {
			var pr = el('div', 'prog');
			var i = el('i');
			i.style.width = clamp(item.t / item.d * 100, 2, 100) + '%';
			pr.appendChild(i);
			c.appendChild(pr);
		}
		return c;
	}

	function rankCard(item, n) {
		var r = el('div', 'rank');
		r.appendChild(el('div', 'num', String(n)));
		r.appendChild(posterCard(item));
		return r;
	}

	function makeCard(row, item, i) {
		if (row.kind === 'wide') return wideCard(item);
		if (row.kind === 'rank') return rankCard(item, i + 1);
		return posterCard(item);
	}

	// --- sorok -----------------------------------------------------------------
	function homeRows() {
		var out = [];
		var cont = continueItems();
		if (cont.length) out.push({key: 'continue', title: 'Folytatás', kind: 'wide', items: cont});
		if (!home) return out;
		var rec = normList(home.recommended);
		if (rec.length) out.push({key: 'top', title: 'Top ' + rec.length + ' ma az OniAnime-on', kind: 'rank', items: rec});
		var latest = (home.latest || []).filter(function (e) { return e && e.anime_id; }).map(function (e) {
			return {id: e.anime_id, title: e.eng_name || e.name, alt: e.eng_name && e.name !== e.eng_name ? e.name : '',
				image: e.anime_image, thumb: e.picture_thumbnail, ep: e.part, epTitle: e.ep_title || '',
				version: e.version || '', desc: e.ep_description || '', color: '', type: '', status: '',
				eps: 0, tags: [], latest: parseDate(e.created_at)};
		});
		if (latest.length) out.push({key: 'latest', title: 'Legújabb részek', kind: 'wide', items: latest});
		var p = home.popular || {};
		[['currentSeason', p.currentSeasonLabel ? 'Szezon: ' + p.currentSeasonLabel : 'Aktuális szezon'],
			['sliderTwo', 'Ma népszerű'],
			['newEpisodes', 'Friss feltöltések'],
			['sliderOne', 'Legnézettebb'],
			['oniTranslations', 'OniAnime fordítások'],
			['sliderMovies', 'Legnézettebb filmek'],
			['previousSeason', p.previousSeasonLabel ? 'Előző szezon: ' + p.previousSeasonLabel : 'Előző szezon']
		].forEach(function (d) {
			var items = normList(p[d[0]]);
			if (items.length) out.push({key: d[0], title: d[1], kind: 'poster', items: items});
		});
		return out;
	}

	function listRows() {
		var out = [];
		var cont = continueItems();
		if (cont.length) out.push({key: 'continue', title: 'Folytatás', kind: 'wide', items: cont});
		var list = normList(myList());
		if (list.length) out.push({key: 'list', title: 'Listám', kind: 'poster', items: list});
		return out;
	}

	function buildRows() {
		var prev = {};
		rows.forEach(function (r) { prev[r.key] = r.sel; });
		var prevKey = rows[activeRow] ? rows[activeRow].key : null;
		rows = tab === 'mylist' ? listRows() : homeRows();
		activeRow = 0;
		rows.forEach(function (r, i) {
			r.sel = Math.min(prev[r.key] || 0, r.items.length - 1);
			if (r.key === prevKey) activeRow = i;
		});
		render();
	}

	function render() {
		var inner = $('#rows .rows-inner');
		inner.innerHTML = '';
		if (!rows.length) {
			inner.appendChild(el('div', 'empty', tab === 'mylist' ?
				'A listád még üres. Egy anime adatlapján a „+ Listám” gombbal adhatsz hozzá, a megkezdett részek pedig maguktól ide kerülnek.' :
				'Nem sikerült betölteni a kínálatot. OK: újrapróbálás.'));
			showHero(true);
			return;
		}
		rows.forEach(function (r, ri) {
			var row = el('section', 'row');
			var h = el('h2', null, r.title);
			row.appendChild(h);
			var track = el('div', 'track');
			var ti = el('div', 'track-inner');
			r.items.forEach(function (item, i) {
				var c = makeCard(r, item, i);
				c.addEventListener('mouseenter', function () { if (zone === 'rows') focusCard(ri, i); });
				c.addEventListener('click', function () { setZone('rows'); focusCard(ri, i); openItem(item); });
				ti.appendChild(c);
			});
			track.appendChild(ti);
			row.appendChild(track);
			inner.appendChild(row);
			r.el = row;
			r.track = ti;
		});
		if (activeRow >= rows.length) activeRow = 0;
		rows.forEach(function (r, i) { paintRow(i); });
		layout();
		showHero(true);
	}

	function paintRow(ri) {
		var r = rows[ri];
		if (!r || !r.track) return;
		var cards = r.track.children;
		var on = ri === activeRow && zone === 'rows';
		for (var i = 0; i < cards.length; i++) {
			var cls = r.kind === 'rank' ? 'rank' : cards[i].className.replace(/ sel\b/g, '');
			if (r.kind === 'rank') {
				cards[i].className = 'rank' + (on && i === r.sel ? ' sel' : '');
				cards[i].lastChild.className = 'card poster' + (on && i === r.sel ? ' sel' : '');
			} else {
				cards[i].className = cls + (on && i === r.sel ? ' sel' : '');
			}
		}
		r.el.className = 'row' + (ri === activeRow ? ' active' : '');
		// vízszintes görgetés: a kijelölt kártya előtt egy kártyányi marad látszani
		var target = cards[r.sel];
		var x = 0;
		if (target && r.sel > 0) x = target.offsetLeft - cards[r.sel - 1].offsetWidth - 20;
		var last = cards[cards.length - 1];
		var maxX = last ? Math.max(0, last.offsetLeft + last.offsetWidth - (1920 - 170 - 80)) : 0;
		r.track.style.transform = 'translateX(' + (-clamp(x, 0, maxX)) + 'px)';
	}

	function layout() {
		var r = rows[activeRow];
		var y = r && r.el ? r.el.offsetTop : 0;
		$('#rows .rows-inner').style.transform = 'translateY(' + (-y) + 'px)';
	}

	function current() {
		var r = rows[activeRow];
		return r ? r.items[r.sel] : null;
	}

	function focusCard(ri, i) {
		if (!rows[ri]) return;
		var prev = activeRow;
		activeRow = ri;
		rows[ri].sel = clamp(i, 0, rows[ri].items.length - 1);
		if (prev !== ri) paintRow(prev);
		paintRow(ri);
		layout();
		showHero(false);
	}

	// --- hero ------------------------------------------------------------------
	function setAccent(color) {
		document.documentElement.style.setProperty('--accent', color || '#e50914');
	}

	function metaInto(box, item, extra) {
		box.innerHTML = '';
		var parts = [];
		if (isNew(item)) parts.push(['m-new', 'Új rész']);
		if (extra && extra.year) parts.push([null, String(extra.year)]);
		else if (item.year) parts.push([null, String(item.year)]);
		if (item.type) parts.push([null, item.type]);
		if (item.status) parts.push([null, item.status]);
		var eps = (extra && extra.eps) || item.eps;
		if (eps) parts.push([null, eps + ' rész']);
		if (item.dub || (extra && extra.dub)) parts.push([null, 'Szinkronnal']);
		var rs = ratingShort((extra && extra.rating) || item.rating);
		parts.forEach(function (p, i) {
			if (i) box.appendChild(el('span', 'dot', '•'));
			box.appendChild(el('span', p[0], p[1]));
		});
		if (rs) box.appendChild(el('span', 'm-box', rs));
	}

	function setBackdrop(src, poster) {
		var img = $('.bd-img'), ps = $('.bd-poster');
		if (src) {
			if (img.getAttribute('src') !== src) {
				img.className = 'bd-img';
				img.onload = function () { if (img.getAttribute('src') === src) img.className = 'bd-img on'; };
				img.src = src;
			} else {
				img.className = 'bd-img on';
			}
			ps.className = 'bd-poster';
		} else {
			img.className = 'bd-img';
			if (poster) {
				if (ps.getAttribute('src') !== poster) ps.src = poster;
				ps.className = 'bd-poster on';
			} else {
				ps.className = 'bd-poster';
			}
		}
	}

	function showHero(now) {
		clearTimeout(heroTimer);
		clearTimeout(heroInfoTimer);
		var hero = $('#hero');
		var apply = function () {
			hero.className = '';
			var item = current();
			if (!item) {
				$('.h-title').textContent = tab === 'mylist' ? 'Listám' : '';
				$('.h-title').className = 'h-title';
				$('.h-logo-wrap').className = 'h-logo-wrap';
				$('.h-meta').innerHTML = '';
				$('.h-desc').textContent = '';
				$('.h-actions').style.display = 'none';
				setBackdrop('', '');
				return;
			}
			$('.h-actions').style.display = '';
			$('.btn-play').innerHTML = '▶&nbsp; ' + (item.cont ? 'Folytatás: ' + item.ep + '. rész' :
				item.ep ? 'Lejátszás: ' + item.ep + '. rész' : 'Lejátszás');
			fillHero(item, null);
			setAccent(item.color);
			var cached = item.bg && item.logo;
			setBackdrop(item.bg, item.image);
			if (cached) return;
			// a háttérkép és a logó az /info-ból jön (a sorok adatai nem tartalmazzák)
			heroInfoTimer = setTimeout(function () {
				info(item.id).then(function (inf) {
					if (current() !== item) return;
					fillHero(item, inf);
				}, function () {});
			}, 350);
		};
		if (now) return apply();
		hero.className = 'fade';
		heroTimer = setTimeout(apply, 160);
	}

	function fillHero(item, inf) {
		var logo = item.logo || (inf && inf.logoEn ? tmdb(inf.logoEn, 'w500') : '');
		var lw = $('.h-logo-wrap'), lg = $('.h-logo'), t = $('.h-title');
		t.textContent = item.title;
		if (logo) {
			lg.onerror = function () { lw.className = 'h-logo-wrap'; t.className = 'h-title'; };
			lg.onload = function () { if (lg.getAttribute('src') === logo) { lw.className = 'h-logo-wrap on'; t.className = 'h-title off'; } };
			if (lg.getAttribute('src') !== logo) {
				lw.className = 'h-logo-wrap';
				t.className = 'h-title';
				lg.src = logo;
			}
		} else {
			lw.className = 'h-logo-wrap';
			t.className = 'h-title';
			lg.removeAttribute('src');
		}
		metaInto($('.h-meta'), item, inf ? {eps: 0} : null);
		var desc = item.desc || (inf && inf.description) || '';
		if (item.epTitle && item.ep) desc = item.ep + '. rész: ' + item.epTitle + (item.desc ? ' – ' + item.desc : '');
		$('.h-desc').textContent = desc.replace(/\s+/g, ' ');
		if (inf) {
			if (!item.color && inf.color) setAccent(inf.color);
			var bg = inf.background ? tmdb(inf.background, 'w1280') : '';
			if (bg) setBackdrop(bg, item.image);
		}
	}

	// --- menüsáv és fülek ------------------------------------------------------
	function setZone(z) {
		var prev = zone;
		zone = z;
		$('#rail').className = z === 'rail' ? 'open' : '';
		paintRail();
		if ((prev === 'rows') !== (z === 'rows')) paintRow(activeRow);
		if ((prev === 'sgrid') !== (z === 'sgrid')) paintGrid();
		$('.s-bar').className = 's-bar' + (z === 'sinput' ? ' sel' : '');
	}

	function paintRail() {
		$$('#rail .r-item').forEach(function (it, i) {
			it.className = 'r-item' + (TABS[i] === tab ? ' cur' : '') + (zone === 'rail' && i === railSel ? ' sel' : '');
		});
	}

	function openRail() {
		railSel = TABS.indexOf(tab);
		var q = $('#q');
		if (document.activeElement === q) q.blur();
		setZone('rail');
	}

	function setTab(t) {
		tab = t;
		document.body.className = t === 'search' ? 'search' : '';
		if (t === 'search') {
			setZone('sinput');
			if (!search.items.length && !search.q) suggest();
			focusInput();
		} else {
			rows = [];
			buildRows();
			setZone('rows');
			paintRow(activeRow);
		}
		paintRail();
	}

	function exitApp() {
		if (window.PalmSystem && window.PalmSystem.platformBack) window.PalmSystem.platformBack();
		else window.close();
	}

	// --- keresés ---------------------------------------------------------------
	function focusInput() {
		var q = $('#q');
		setTimeout(function () { q.focus(); }, 30);
	}

	function suggest() {
		var p = home && home.popular ? home.popular : {};
		search.items = normList(p.sliderTwo || p.sliderOne || []);
		search.title = 'Népszerű most';
		search.sel = 0;
		renderGrid();
	}

	function runSearch(q) {
		q = q.trim();
		search.q = q;
		if (q.length < 2) { suggest(); return; }
		var my = ++search.req;
		$('.s-info').textContent = 'Keresés: „' + q + '”…';
		api('/api/animes/search?search=' + encodeURIComponent(q)).then(function (res) {
			if (my !== search.req) return;
			search.items = normList(res && res.animes);
			search.title = search.items.length ? 'Találatok: „' + q + '” (' + search.items.length + ')' :
				'Nincs találat erre: „' + q + '”';
			search.sel = 0;
			renderGrid();
		}, function (err) {
			if (my !== search.req) return;
			$('.s-info').textContent = 'A keresés nem sikerült (' + err.message + ')';
		});
	}

	var COLS = 7;

	function renderGrid() {
		$('.s-info').textContent = search.title;
		var inner = $('.s-grid-inner');
		inner.innerHTML = '';
		search.items.forEach(function (item, i) {
			var c = posterCard(item);
			c.addEventListener('mouseenter', function () { if (zone === 'sgrid') { search.sel = i; paintGrid(); } });
			c.addEventListener('click', function () { search.sel = i; setZone('sgrid'); openItem(item); });
			inner.appendChild(c);
		});
		paintGrid();
	}

	function paintGrid() {
		var cards = $('.s-grid-inner').children;
		for (var i = 0; i < cards.length; i++) {
			cards[i].className = 'card poster' + (zone === 'sgrid' && i === search.sel ? ' sel' : '') +
				(i % COLS === 0 ? ' c0' : '');
		}
		var r = Math.floor(search.sel / COLS);
		$('.s-grid-inner').style.transform = 'translateY(' + (-Math.max(0, r - 1) * 342) + 'px)';
	}

	function gridKey(k) {
		var n = search.items.length;
		var s = search.sel;
		if (k === KEY.LEFT) {
			if (s % COLS === 0) return openRail();
			s--;
		} else if (k === KEY.RIGHT) {
			if (s % COLS < COLS - 1 && s + 1 < n) s++;
		} else if (k === KEY.UP) {
			if (s < COLS) { setZone('sinput'); focusInput(); return; }
			s -= COLS;
		} else if (k === KEY.DOWN) {
			if (s + COLS < n) s += COLS;
			else if (Math.floor(s / COLS) < Math.floor((n - 1) / COLS)) s = n - 1;
		} else if (k === KEY.OK) {
			return openItem(search.items[s]);
		}
		search.sel = clamp(s, 0, Math.max(0, n - 1));
		paintGrid();
	}

	// --- adatlap ---------------------------------------------------------------
	function openItem(item) {
		if (!item) return;
		openDetail(item, item.ep || 0);
	}

	function openDetail(item, focusEp) {
		var my = ++detailReq;
		var prog = progressOf(item.id);
		detail = {item: item, info: null, full: null, eps: [], sel: 0, zone: 'actions', btn: 0, buttons: [],
			type: (prog && prog.type) || store('lang', 'sub'), from: zone, focusEp: focusEp || 0, loading: true};
		var q = $('#q');
		if (document.activeElement === q) q.blur();
		zone = 'detail';
		$('#rail').className = '';
		document.body.className = 'detail';
		setAccent(item.color);
		fillDetail();
		$('.d-track-inner').innerHTML = '';
		$('.d-eps .cnt').textContent = '';
		$('.d-track-inner').appendChild(el('div', 'd-loading', 'Részek betöltése…'));
		Promise.all([
			info(item.id).catch(function () { return null; }),
			api('/api/anime/' + item.id).catch(function () { return null; }),
			api('/api/anime/' + item.id + '/episodes').catch(function () { return null; })
		]).then(function (res) {
			if (my !== detailReq || !detail) return;
			detail.info = res[0];
			detail.full = res[1] && res[1].id ? res[1] : null;
			detail.eps = res[2] && res[2].episodes ? res[2].episodes : [];
			detail.loading = false;
			if (!detail.eps.length && detail.full && detail.full.ep) {
				for (var i = 1; i <= detail.full.ep; i++) detail.eps.push({ep: i, hasSub: true, hasDub: false});
			}
			// a mentett nyelv csak akkor marad, ha van ilyen rész
			var anyDub = detail.eps.some(function (e) { return e.hasDub; });
			var anySub = detail.eps.some(function (e) { return e.hasSub; });
			if (detail.type === 'dub' && !anyDub) detail.type = 'sub';
			if (detail.type === 'sub' && !anySub && anyDub) detail.type = 'dub';
			var target = detail.focusEp || (progressOf(item.id) || {}).ep || 0;
			detail.sel = 0;
			detail.eps.forEach(function (e, i) { if (+e.ep === +target) detail.sel = i; });
			fillDetail();
			renderEps();
		});
	}

	function detailItem() {
		var d = detail, it = d.item, inf = d.info || {}, f = d.full || {};
		return {
			title: it.title || inf.eng_name || inf.name, alt: it.alt,
			desc: inf.description || f.description || it.desc || '',
			bg: inf.background ? tmdb(inf.background, 'w1280') : (it.bg || f.background || ''),
			logo: inf.logoEn ? tmdb(inf.logoEn, 'w500') : (it.logo || ''),
			image: it.image || inf.image || f.image || '',
			color: it.color || inf.color || f.color || '',
			type: f.type || inf.type || it.type, status: f.status || inf.status || it.status,
			rating: f.rating || it.rating || '',
			tags: inf.tags || f.tags || it.tags || [],
			year: f.created_at ? new Date(f.created_at).getFullYear() : it.year,
			studio: f.studio || '',
			translators: (inf.translators || []).map(function (t) { return t.name; }).filter(Boolean),
			eps: d.eps.length || f.part_count || f.ep || it.eps
		};
	}

	function fillDetail() {
		var di = detailItem();
		setAccent(di.color);
		var img = $('.d-bg img');
		var src = di.bg;
		if (img.getAttribute('src') !== src) {
			img.className = '';
			if (src) {
				img.onload = function () { if (img.getAttribute('src') === src) img.className = 'on'; };
				img.src = src;
			} else {
				img.removeAttribute('src');
			}
		}
		var lw = $('.d-logo-wrap'), lg = $('.d-logo'), t = $('.d-title');
		t.textContent = di.title;
		if (di.logo) {
			if (lg.getAttribute('src') !== di.logo) {
				lw.className = 'd-logo-wrap';
				t.className = 'd-title';
				lg.onload = function () { lw.className = 'd-logo-wrap on'; t.className = 'd-title off'; };
				lg.onerror = function () { lw.className = 'd-logo-wrap'; t.className = 'd-title'; };
				lg.src = di.logo;
			}
		} else {
			lw.className = 'd-logo-wrap';
			t.className = 'd-title';
			lg.removeAttribute('src');
		}
		var anyDub = detail.eps.some(function (e) { return e.hasDub; });
		metaInto($('.d-meta'), {type: di.type, status: di.status, eps: di.eps, rating: di.rating, year: di.year,
			latest: detail.item.latest}, {dub: anyDub});
		var tags = di.tags.slice(0, 5).join(', ');
		if (di.studio) tags += (tags ? '   ·   ' : '') + di.studio;
		if (di.translators.length) tags += (tags ? '   ·   ' : '') + 'Fordító: ' + di.translators.join(', ');
		$('.d-tags').textContent = tags;
		$('.d-desc').textContent = di.desc.replace(/\s+/g, ' ');
		renderButtons();
	}

	function renderButtons() {
		var d = detail;
		var box = $('.d-actions');
		box.innerHTML = '';
		d.buttons = [];
		var prog = progressOf(d.item.id);
		var ep = d.eps[d.sel];
		if (d.loading) {
			box.appendChild(el('span', 'btn primary', 'Betöltés…'));
			return;
		}
		if (d.eps.length) {
			if (prog && !prog.done && hasEp(prog.ep)) {
				d.buttons.push({cls: 'primary', html: '▶&nbsp; Folytatás: ' + prog.ep + '. rész' +
					(prog.t > 5 ? ' (' + fmt(prog.t) + ')' : ''), act: function () { playEp(prog.ep, true); }});
				d.buttons.push({html: '↺&nbsp; ' + epNo(0) + '. résztől', act: function () { playEp(epNo(0), false); }});
			} else {
				d.buttons.push({cls: 'primary', html: '▶&nbsp; Lejátszás: ' + epNo(0) + '. rész',
					act: function () { playEp(epNo(0), false); }});
			}
		}
		var anyDub = d.eps.some(function (e) { return e.hasDub; });
		var anySub = d.eps.some(function (e) { return e.hasSub; });
		if (anyDub && anySub) {
			d.buttons.push({html: 'Nyelv: <span class="on">' + (d.type === 'dub' ? 'Szinkron' : 'Felirat') + '</span>',
				act: function () {
					d.type = d.type === 'dub' ? 'sub' : 'dub';
					save('lang', d.type);
					renderButtons();
					renderEps();
				}});
		}
		var listed = inList(d.item.id);
		d.buttons.push({html: listed ? '<span class="on">✓</span>&nbsp; Listám' : '+&nbsp; Listám', act: function () {
			toggleList(detailItemForList());
			renderButtons();
		}});
		if (ep === undefined && !d.eps.length) {
			box.appendChild(el('span', 'd-loading', 'Ehhez az animéhez még nincs feltöltött rész.'));
		}
		d.btn = clamp(d.btn, 0, d.buttons.length - 1);
		d.buttons.forEach(function (b, i) {
			var e = el('span', 'btn' + (b.cls ? ' ' + b.cls : '') + (d.zone === 'actions' && i === d.btn ? ' sel' : ''));
			e.innerHTML = b.html;
			e.addEventListener('mouseenter', function () { d.zone = 'actions'; d.btn = i; paintDetail(); });
			e.addEventListener('click', function () { b.act(); });
			box.appendChild(e);
		});
	}

	function detailItemForList() {
		var di = detailItem();
		return {id: detail.item.id, title: di.title, alt: di.alt, image: di.image, color: di.color, type: di.type,
			status: di.status, eps: di.eps, desc: di.desc, tags: di.tags};
	}

	function epNo(i) { return detail.eps[i] ? +detail.eps[i].ep : 1; }
	function hasEp(n) { return detail.eps.some(function (e) { return +e.ep === +n; }); }

	function renderEps() {
		var d = detail;
		var inner = $('.d-track-inner');
		inner.innerHTML = '';
		$('.d-eps .cnt').textContent = d.eps.length ? d.eps.length + ' rész' : '';
		var prog = progressOf(d.item.id) || {};
		var seen = prog.seen || {};
		var di = detailItem();
		d.eps.forEach(function (e, i) {
			var w = el('div', 'ep');
			var c = el('div', 'card');
			var ph = el('div', 'ph', '');
			ph.style.setProperty('--c', di.color || '#444');
			c.appendChild(ph);
			var img = el('img', 'pic');
			img.alt = '';
			img.setAttribute('data-src', e.thumbnail || di.bg || di.image || '');
			img.onerror = function () { if (img.parentNode) img.parentNode.removeChild(img); };
			c.appendChild(img);
			c.appendChild(el('div', 'shade'));
			c.appendChild(el('div', 'no', String(e.ep)));
			var avail = d.type === 'dub' ? e.hasDub : e.hasSub;
			if (seen[e.ep]) c.appendChild(el('div', 'seen', '✓ MEGNÉZVE'));
			else if (!avail) c.appendChild(el('div', 'seen', d.type === 'dub' ? 'CSAK FELIRAT' : 'CSAK SZINKRON'));
			if (+prog.ep === +e.ep && prog.d && !prog.done) {
				var pr = el('div', 'prog');
				var bar = el('i');
				bar.style.width = clamp(prog.t / prog.d * 100, 2, 100) + '%';
				pr.appendChild(bar);
				c.appendChild(pr);
			}
			w.appendChild(c);
			w.appendChild(el('div', 'et', e.title || e.ep + '. rész'));
			w.appendChild(el('div', 'ed', e.description || ''));
			w.addEventListener('mouseenter', function () { d.zone = 'eps'; d.sel = i; paintDetail(); });
			w.addEventListener('click', function () { d.sel = i; playEp(+e.ep, true); });
			inner.appendChild(w);
		});
		paintDetail();
	}

	function paintDetail() {
		var d = detail;
		if (!d) return;
		$$('.d-actions .btn').forEach(function (b, i) {
			b.className = b.className.replace(/ sel\b/g, '') + (d.zone === 'actions' && i === d.btn ? ' sel' : '');
		});
		$('.d-eps').className = 'd-eps' + (d.zone === 'eps' ? '' : ' idle');
		var eps = $('.d-track-inner').children;
		for (var i = 0; i < eps.length; i++) {
			eps[i].className = 'ep' + (i === d.sel ? ' sel' : '');
			// képek csak a látható környéken (170+ rész esetén sem tölt be mindent)
			if (i >= d.sel - 3 && i <= d.sel + 8) {
				var img = eps[i].querySelector('img[data-src]');
				if (img) {
					var s = img.getAttribute('data-src');
					img.removeAttribute('data-src');
					if (s) img.src = s; else img.parentNode.removeChild(img);
				}
			}
		}
		var w = 380 + 22;
		var x = Math.max(0, d.sel - 1) * w;
		var maxX = Math.max(0, eps.length * w - (1920 - 110 - 60));
		$('.d-track-inner').style.transform = 'translateX(' + (-clamp(x, 0, maxX)) + 'px)';
	}

	function closeDetail() {
		detail = null;
		detailReq++;
		document.body.className = tab === 'search' ? 'search' : '';
		if (tab === 'search') {
			setZone('sgrid');
			paintGrid();
		} else {
			// a Folytatás sor frissülhetett
			buildRows();
			setZone('rows');
		}
	}

	function detailKey(k) {
		var d = detail;
		if (d.zone === 'actions') {
			if (k === KEY.LEFT) d.btn = Math.max(0, d.btn - 1);
			else if (k === KEY.RIGHT) d.btn = Math.min(d.buttons.length - 1, d.btn + 1);
			else if (k === KEY.DOWN) { if (d.eps.length) d.zone = 'eps'; }
			else if (k === KEY.OK) { var b = d.buttons[d.btn]; if (b) b.act(); return; }
		} else {
			if (k === KEY.LEFT) d.sel = Math.max(0, d.sel - 1);
			else if (k === KEY.RIGHT) d.sel = Math.min(d.eps.length - 1, d.sel + 1);
			else if (k === KEY.RW || k === KEY.CHDOWN) d.sel = Math.max(0, d.sel - 10);
			else if (k === KEY.FF || k === KEY.CHUP) d.sel = Math.min(d.eps.length - 1, d.sel + 10);
			else if (k === KEY.UP) d.zone = 'actions';
			else if (k === KEY.OK) { if (d.eps[d.sel]) playEp(+d.eps[d.sel].ep, true); return; }
		}
		paintDetail();
	}

	// --- lejátszó --------------------------------------------------------------
	var P = {root: null, video: null, ctx: null, sources: [], qi: 0, hideTimer: null, saveAt: 0,
		nextTimer: null, nextLeft: 0, req: 0, resumeAt: 0};

	function playEp(n, resume) {
		var d = detail;
		if (!d) return;
		var e = null;
		d.eps.forEach(function (x) { if (+x.ep === +n) e = x; });
		if (!e) return toast('Nincs ilyen rész: ' + n);
		var type = d.type;
		if (type === 'dub' && !e.hasDub && e.hasSub) { type = 'sub'; toast('Ez a rész csak feliratosan érhető el'); }
		else if (type === 'sub' && !e.hasSub && e.hasDub) { type = 'dub'; toast('Ez a rész csak szinkronosan érhető el'); }
		var prog = progressOf(d.item.id);
		var resumeAt = resume && prog && +prog.ep === +n && !prog.done && prog.t > 10 &&
			(!prog.d || prog.t < prog.d - 30) ? prog.t : 0;
		var di = detailItem();
		P.ctx = {id: d.item.id, title: di.title, image: di.image, bg: di.bg, logo: di.logo, color: di.color,
			atype: di.type, desc: di.desc, eps: d.eps, ep: +n, epInfo: e, type: type};
		openPlayer(resumeAt);
	}

	function openPlayer(resumeAt) {
		var c = P.ctx;
		var my = ++P.req;
		zone = 'player';
		P.root.className = 'open osd';
		hideNext();
		$('.p-anime').textContent = c.title;
		$('.p-ep').textContent = c.ep + '. rész' + (c.epInfo && c.epInfo.title ? ': ' + c.epInfo.title : '') +
			(c.type === 'dub' ? '  ·  szinkron' : '');
		pstatus('Betöltés…');
		P.video.removeAttribute('src');
		P.video.load();
		P.resumeAt = resumeAt || 0;
		updateBar();
		api('/api/anime/' + c.id + '/parts?episode=' + c.ep + '&type=' + c.type + '&server=' + SERVERS[c.type])
			.then(function (res) {
				if (my !== P.req || zone !== 'player') return;
				var src = (res && res.sources || []).filter(function (s) { return s && s.src; });
				src.sort(function (a, b) { return (parseInt(b.label, 10) || 0) - (parseInt(a.label, 10) || 0); });
				P.sources = src;
				c.hasNext = res && res.nextEpisode === 'yes';
				if (!src.length) {
					pstatus('Ehhez a részhez most nincs elérhető videó.\nVissza: kilépés');
					return;
				}
				var pref = store('quality', '');
				P.qi = 0;
				src.forEach(function (s, i) { if (s.label === pref) P.qi = i; });
				startSource(P.resumeAt);
			}, function (err) {
				if (my !== P.req) return;
				pstatus('Nem sikerült lekérni a videót (' + err.message + ').\nVissza: kilépés');
			});
		showOsd();
	}

	function startSource(at) {
		var s = P.sources[P.qi];
		if (!s) return;
		$('.p-q').textContent = s.label || '';
		pstatus('Betöltés…');
		var v = P.video;
		var seekTo = at || 0;
		v.src = s.src;
		v.onloadedmetadata = function () {
			if (seekTo > 0 && isFinite(v.duration) && seekTo < v.duration - 5) {
				v.currentTime = seekTo;
				if (P.resumeAt) toast('Folytatás innen: ' + fmt(seekTo), 2500);
			}
			P.resumeAt = 0;
		};
		var p = v.play();
		if (p && p.catch) p.catch(function () {});
	}

	function pstatus(t) {
		var s = $('.p-status');
		s.textContent = '';
		String(t || '').split('\n').forEach(function (line, i) {
			if (i) s.appendChild(el('br'));
			s.appendChild(document.createTextNode(line));
		});
	}

	function showOsd() {
		P.root.classList.add('osd');
		clearTimeout(P.hideTimer);
		P.hideTimer = setTimeout(function () {
			if (!P.video.paused) P.root.classList.remove('osd');
		}, 4000);
	}

	function updateBar() {
		var v = P.video;
		var d = isFinite(v.duration) ? v.duration : 0;
		var t = v.currentTime || 0;
		var pct = d ? t / d * 100 : 0;
		$('.p-fill').style.width = pct + '%';
		$('.p-knob').style.left = pct + '%';
		if (d && v.buffered && v.buffered.length) {
			$('.p-buf').style.width = clamp(v.buffered.end(v.buffered.length - 1) / d * 100, 0, 100) + '%';
		} else {
			$('.p-buf').style.width = '0';
		}
		$('.p-time').textContent = fmt(t);
		$('.p-left').textContent = d ? '-' + fmt(d - t) : '';
	}

	function nextEpOf(c) {
		var next = null;
		c.eps.forEach(function (x) { if (!next && +x.ep > c.ep) next = x; });
		return next;
	}

	function recordProgress(force) {
		var c = P.ctx, v = P.video;
		if (!c || !isFinite(v.duration) || !v.duration) return;
		var now = Date.now();
		if (!force && now - P.saveAt < 5000) return;
		P.saveAt = now;
		var prev = progressOf(c.id) || {};
		var seen = prev.seen || {};
		var rec = {id: c.id, title: c.title, image: c.image, bg: c.bg, logo: c.logo, color: c.color, atype: c.atype,
			desc: c.desc, eps: c.eps.length, type: c.type, ep: c.ep, t: v.currentTime, d: v.duration,
			thumb: c.epInfo && c.epInfo.thumbnail || '', ts: now, seen: seen, done: false};
		if (v.currentTime > v.duration * 0.92) {
			seen[c.ep] = 1;
			var next = nextEpOf(c);
			if (next) {
				rec.ep = +next.ep;
				rec.t = 0;
				rec.d = 0;
				rec.thumb = next.thumbnail || '';
			} else {
				rec.done = true;
			}
		}
		saveProgress(rec);
	}

	function seek(delta) {
		var v = P.video;
		if (!isFinite(v.duration)) return;
		v.currentTime = clamp(v.currentTime + delta, 0, v.duration - 1);
		updateBar();
		showOsd();
	}

	function togglePlay() {
		var v = P.video;
		if (!v.src) return;
		if (v.paused) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
		else v.pause();
		showOsd();
	}

	function switchQuality() {
		if (P.sources.length < 2) { toast(P.sources.length ? 'Csak egy minőség érhető el' : 'Nincs videó'); return; }
		P.qi = (P.qi + 1) % P.sources.length;
		save('quality', P.sources[P.qi].label);
		toast('Minőség: ' + P.sources[P.qi].label, 2000);
		startSource(P.video.currentTime || 0);
	}

	function playNext() {
		hideNext();
		var next = nextEpOf(P.ctx);
		if (!next) { toast('Ez volt az utolsó rész'); return; }
		recordProgress(true);
		var c = P.ctx;
		var type = c.type;
		if (type === 'dub' && !next.hasDub && next.hasSub) type = 'sub';
		else if (type === 'sub' && !next.hasSub && next.hasDub) type = 'dub';
		c.ep = +next.ep;
		c.epInfo = next;
		c.type = type;
		openPlayer(0);
	}

	function showNext() {
		var next = nextEpOf(P.ctx);
		if (!next) return closePlayer();
		$('.p-next-title').textContent = next.ep + '. rész' + (next.title ? ': ' + next.title : '');
		P.nextLeft = 8;
		var box = $('.p-next');
		box.className = 'p-next on';
		var tick = function () {
			$('.p-next-cd').textContent = 'Indul ' + P.nextLeft + ' másodperc múlva…';
			if (P.nextLeft-- <= 0) return playNext();
			P.nextTimer = setTimeout(tick, 1000);
		};
		tick();
	}

	function hideNext() {
		clearTimeout(P.nextTimer);
		P.nextTimer = null;
		$('.p-next').className = 'p-next';
	}

	function closePlayer() {
		recordProgress(true);
		hideNext();
		P.req++;
		P.video.pause();
		P.video.removeAttribute('src');
		P.video.load();
		P.root.className = '';
		zone = 'detail';
		if (detail) {
			// a lejátszott részre áll, és frissíti a Folytatás gombot / jelöléseket
			detail.eps.forEach(function (e, i) { if (P.ctx && +e.ep === +P.ctx.ep) detail.sel = i; });
			renderButtons();
			renderEps();
		}
	}

	function playerKey(k, e) {
		if (P.nextTimer) {
			if (k === KEY.OK) playNext();
			else if (k === KEY.BACK || k === KEY.ESC || k === KEY.BACKSPACE) { hideNext(); closePlayer(); }
			return;
		}
		switch (k) {
		case KEY.BACK: case KEY.ESC: case KEY.BACKSPACE: case KEY.STOP:
			closePlayer();
			break;
		case KEY.OK: case KEY.PLAY: case KEY.PAUSE: case KEY.PLAYPAUSE:
			if (k === KEY.PLAY && !P.video.paused) break;
			if (k === KEY.PAUSE && P.video.paused) break;
			togglePlay();
			break;
		case KEY.LEFT: seek(e.repeat ? -30 : -10); break;
		case KEY.RIGHT: seek(e.repeat ? 30 : 10); break;
		case KEY.RW: seek(-60); break;
		case KEY.FF: seek(60); break;
		case KEY.UP: switchQuality(); showOsd(); break;
		case KEY.DOWN: case KEY.CHUP: playNext(); break;
		default: showOsd();
		}
	}

	function initPlayer() {
		P.root = $('#player');
		var v = P.video = $('#player video');
		v.addEventListener('timeupdate', function () {
			updateBar();
			recordProgress(false);
		});
		v.addEventListener('progress', updateBar);
		v.addEventListener('playing', function () { pstatus(''); P.root.classList.remove('paused'); });
		v.addEventListener('pause', function () {
			if (zone === 'player') { P.root.classList.add('paused'); showOsd(); }
		});
		v.addEventListener('waiting', function () { pstatus('Pufferelés…'); });
		v.addEventListener('ended', function () {
			recordProgress(true);
			if (P.ctx && nextEpOf(P.ctx)) showNext();
			else closePlayer();
		});
		v.addEventListener('error', function () {
			if (zone !== 'player' || !v.getAttribute('src')) return;
			// tartalék: a következő (kisebb) minőség
			if (P.qi < P.sources.length - 1) {
				P.qi++;
				toast('Hiba a lejátszásban – próbálom: ' + P.sources[P.qi].label);
				startSource(v.currentTime || 0);
			} else {
				pstatus('A videót nem sikerült lejátszani.\nVissza: kilépés');
			}
		});
		P.root.addEventListener('click', function () { if (!P.nextTimer) togglePlay(); });
		P.root.addEventListener('mousemove', showOsd);
	}

	// --- betöltés --------------------------------------------------------------
	function load() {
		$('#loading').className = '';
		return Promise.all([
			api('/api/animes/popular').catch(function (e) { return {error: e}; }),
			api('/api/animes/recommended').catch(function () { return []; }),
			api('/api/animes/latest-episodes').catch(function () { return []; })
		]).then(function (res) {
			if (res[0] && res[0].error && !res[1].length && !res[2].length) {
				toast('Nem sikerült elérni az onianime.hu-t (' + res[0].error.message + ')', 6000);
				home = null;
			} else {
				home = {popular: res[0] && !res[0].error ? res[0] : {},
					recommended: Array.isArray(res[1]) ? res[1] : [],
					latest: Array.isArray(res[2]) ? res[2] : []};
			}
			$('#loading').className = 'off';
			if (tab !== 'search' && !detail) {
				buildRows();
				setZone('rows');
			}
		});
	}

	function tick() {
		var d = new Date();
		$('#clock').textContent = pad(d.getHours()) + ':' + pad(d.getMinutes());
	}

	// --- vezérlés --------------------------------------------------------------
	function isBack(k) { return k === KEY.BACK || k === KEY.ESC || k === KEY.BACKSPACE; }

	function rowsKey(k) {
		if (!rows.length) {
			if (k === KEY.OK && tab === 'home') load();
			else if (k === KEY.LEFT) openRail();
			return;
		}
		var r = rows[activeRow];
		if (k === KEY.LEFT) {
			if (r.sel === 0) return openRail();
			focusCard(activeRow, r.sel - 1);
		} else if (k === KEY.RIGHT) focusCard(activeRow, r.sel + 1);
		else if (k === KEY.UP) { if (activeRow > 0) focusCard(activeRow - 1, rows[activeRow - 1].sel); }
		else if (k === KEY.DOWN) { if (activeRow < rows.length - 1) focusCard(activeRow + 1, rows[activeRow + 1].sel); }
		else if (k === KEY.OK || k === KEY.PLAY) openItem(current());
	}

	function railKey(k) {
		if (k === KEY.UP) railSel = Math.max(0, railSel - 1);
		else if (k === KEY.DOWN) railSel = Math.min(TABS.length - 1, railSel + 1);
		else if (k === KEY.OK) { setTab(TABS[railSel]); return; }
		else if (k === KEY.RIGHT) {
			if (tab === 'search') { setZone(search.items.length ? 'sgrid' : 'sinput'); if (zone === 'sinput') focusInput(); }
			else setZone('rows');
			return;
		}
		paintRail();
	}

	function onKey(e) {
		var k = e.keyCode;
		var q = $('#q');
		// gépelés a keresőmezőben: a betűket, törlést és a kurzormozgást a mező kapja
		if (zone === 'sinput' && document.activeElement === q) {
			if (k === KEY.DOWN || k === KEY.OK) {
				e.preventDefault();
				q.blur();
				clearTimeout(search.timer);
				if (q.value.trim() !== search.q) runSearch(q.value);
				if (search.items.length) setZone('sgrid');
				return;
			}
			if (k === KEY.BACK || k === KEY.ESC) { e.preventDefault(); openRail(); return; }
			if (k === KEY.UP) { e.preventDefault(); return; }
			if (k === KEY.LEFT && q.selectionStart === 0 && q.selectionEnd === 0) { e.preventDefault(); openRail(); }
			return;
		}
		if (zone === 'player') { e.preventDefault(); playerKey(k, e); return; }
		if (zone === 'detail') {
			e.preventDefault();
			if (isBack(k)) closeDetail();
			else if (k === KEY.YELLOW && detail) { toggleList(detailItemForList()); renderButtons(); }
			else if (detail) detailKey(k);
			return;
		}
		if (zone === 'rail') {
			e.preventDefault();
			if (isBack(k)) {
				if (tab !== 'home') setTab('home');
				else exitApp();
				return;
			}
			railKey(k);
			return;
		}
		if (zone === 'sinput') {
			e.preventDefault();
			if (k === KEY.OK) focusInput();
			else if (k === KEY.DOWN && search.items.length) setZone('sgrid');
			else if (k === KEY.LEFT || isBack(k)) openRail();
			return;
		}
		if (zone === 'sgrid') {
			e.preventDefault();
			if (isBack(k)) { setZone('sinput'); focusInput(); }
			else gridKey(k);
			return;
		}
		if (zone === 'rows') {
			e.preventDefault();
			if (isBack(k)) {
				// Vissza: először a sorok elejére, aztán a menüsávra (onnan kilépés)
				if (activeRow > 0 || (rows[0] && rows[0].sel > 0)) {
					if (rows[0]) rows[0].sel = 0;
					var prev = activeRow;
					activeRow = 0;
					paintRow(prev);
					focusCard(0, 0);
				} else {
					openRail();
				}
				return;
			}
			rowsKey(k);
		}
	}

	window.addEventListener('load', function () {
		tick();
		setInterval(tick, 10000);
		initPlayer();
		document.addEventListener('keydown', onKey);

		var q = $('#q');
		q.addEventListener('input', function () {
			clearTimeout(search.timer);
			search.timer = setTimeout(function () { runSearch(q.value); }, 700);
		});
		q.addEventListener('focus', function () { if (zone !== 'sinput') setZone('sinput'); });

		$$('#rail .r-item').forEach(function (it, i) {
			it.addEventListener('mouseenter', function () { railSel = i; if (zone !== 'rail') setZone('rail'); else paintRail(); });
			it.addEventListener('click', function () { setTab(TABS[i]); });
		});
		$('#rail').addEventListener('mouseleave', function () {
			if (zone === 'rail') {
				if (tab === 'search') setZone('sinput');
				else setZone('rows');
			}
		});
		$('.btn-play').addEventListener('click', function () { openItem(current()); });
		$('.btn-info').addEventListener('click', function () { openItem(current()); });

		// a görgő függőlegesen a sorok között lép
		var wheelLock = 0;
		document.addEventListener('wheel', function (e) {
			if (Date.now() - wheelLock < 250) return;
			wheelLock = Date.now();
			var down = e.deltaY > 0;
			if (zone === 'rows' && rows.length) {
				var to = activeRow + (down ? 1 : -1);
				if (to >= 0 && to < rows.length) focusCard(to, rows[to].sel);
			} else if (zone === 'detail' && detail) {
				detailKey(down ? KEY.RIGHT : KEY.LEFT);
			} else if (zone === 'sgrid') {
				gridKey(down ? KEY.DOWN : KEY.UP);
			}
		});
		document.addEventListener('visibilitychange', function () {
			if (document.hidden && zone === 'player') {
				recordProgress(true);
				P.video.pause();
			}
		});
		window.addEventListener('beforeunload', function () { if (zone === 'player') recordProgress(true); });

		paintRail();
		load();
	});
})();
