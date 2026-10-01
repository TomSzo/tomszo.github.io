/*
 * Network4 / Arena4+ - a hivatalos mobilalkalmazás API-ja (net4plus.network4.hu/api).
 * A Kodi-kiegészítő (plugin.video.network4, resources/lib/net4api.py) JavaScript-változata;
 * az API feltérképezése a plugin.video.arena4plus (heg, vargalex; GPL-3.0) alapján.
 *
 *   GET /api/login?email=..&password=..      -> {"access_token": "..."}   (Bearer)
 *   GET /api/collections                       -> [{title, slug, photo_thumbnail}, ...]
 *   GET /api/collectionitems/<slug>/11         -> [{vodsavail: [...], series: {...}}]
 *   GET /api/collectionitemslive/live/0        -> [{liveeventsavail: [...]}]
 *   GET /api/watch/<slug>/live                 -> {src, replaysrc}
 *   GET /api/search/<szó>                      -> [{title, short_desc, verizon_id, ...}]
 *
 * Kímélet (mint a Kodi-ban): 1 mp szünet a kérések között, gyorsítótár (6 óra),
 * a token tárolva, 401-nél egyszeri újrabelépés, sikertelen belépés után 10 perc szünet.
 */
(function (global) {
	'use strict';

	var Store = global.N4Store;
	var API = 'https://net4plus.network4.hu/api';
	var STORAGE = 'https://net4plus.network4.hu/storage/';
	var SPORT_PAGE = 'https://www.network4.hu/sport/collections';
	var FIREFOX_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0';
	var APP_UA = 'Dart/3.6 (dart:io)';
	var MIN_GAP = 1000;
	var LOGIN_COOLDOWN = 600 * 1000;
	var LIST_TTL = 6 * 3600 * 1000;
	var SPORT_TTL = 24 * 3600 * 1000;
	var SPORT_RETRY = 3600 * 1000;   // a weboldal hibája után ennyi ideig a beépített lista
	var CF_RETRIES = 2;
	var UPLYNK_HLS = 'https://content.uplynk.com/%s.m3u8';
	var ASSET_RE = /^[0-9a-f]{32}$/;
	var EXCLUDED = ['Élő közvetítések', 'Előzmények', 'Kedvenceim', 'Leading Articles',
		'Opinion Articles', 'Podcasts'];

	function ApiError(message, kind) {
		this.name = 'ApiError';
		this.message = message;
		this.kind = kind || 'api';
	}
	ApiError.prototype = Object.create(Error.prototype);

	function sleep(ms) {
		return new Promise(function (r) { setTimeout(r, ms); });
	}

	// --- napi kérésszámláló --------------------------------------------------
	function today() {
		var d = new Date();
		return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
	}

	function bump() {
		var c = Store.get('requests', {}) || {};
		if (c.date !== today()) c = {date: today(), count: 0};
		c.count = (c.count || 0) + 1;
		Store.set('requests', c);
	}

	function todayRequests() {
		var c = Store.get('requests', {}) || {};
		return c.date === today() ? (c.count || 0) : 0;
	}

	// --- HTTP (sorban, szünettel) ----------------------------------------------
	var queue = Promise.resolve();
	var last = 0;

	function isChallenge(resp) {
		if (!resp) return false;
		if ((resp.cfMitigated || '').toLowerCase() === 'challenge') return true;
		if ((resp.status === 403 || resp.status === 503) &&
				(resp.contentType || '').indexOf('text/html') >= 0) {
			var body = (resp.body || '').slice(0, 4000);
			return body.indexOf('_cf_chl_opt') >= 0 || body.indexOf('Just a moment') >= 0 ||
				body.indexOf('challenge-platform') >= 0;
		}
		return false;
	}

	function once(url, headers) {
		var wait = Math.max(0, MIN_GAP - (Date.now() - last));
		return sleep(wait).then(function () {
			last = Date.now();
			bump();
			return global.N4Bridge.httpGet(url, headers);
		});
	}

	function http(url, headers, retries) {
		var maxRetries = retries === undefined ? CF_RETRIES : retries;
		var run = function () {
			var attempt = 0;
			var tryOnce = function () {
				return once(url, headers).then(function (resp) {
					if (!isChallenge(resp)) return resp;
					if (attempt++ < maxRetries) return sleep(5000).then(tryOnce);
					throw new ApiError('A Network4 szervere (Cloudflare) elutasította a kérést. ' +
						'Próbáld újra később.', 'challenge');
				}, function (err) {
					throw new ApiError('Hálózati hiba: ' + err.message, 'network');
				});
			};
			return tryOnce();
		};
		var p = queue.then(run, run);
		queue = p.then(function () {}, function () {});
		return p;
	}

	function apiHeaders(tok) {
		var h = {'User-Agent': Store.setting('apiUa') === 'firefox' ? FIREFOX_UA : APP_UA,
			'Accept': 'application/json, text/plain, */*'};
		if (tok) h.Authorization = 'Bearer ' + tok;
		return h;
	}

	// --- belépés / token -------------------------------------------------------
	function haveCredentials() {
		return !!(String(Store.setting('email')).trim() && Store.setting('password'));
	}

	function clearToken() {
		Store.remove('token');
	}

	function login() {
		var email = String(Store.setting('email')).trim();
		var password = Store.setting('password');
		if (!email || !password) {
			return Promise.reject(new ApiError('Add meg az email címet és a jelszót a ' +
				'Beállításokban', 'login'));
		}
		var t = Store.get('token', {}) || {};
		if (t.failed && Date.now() - t.failed < LOGIN_COOLDOWN) {
			return Promise.reject(new ApiError('Az előző belépés nem sikerült - 10 perc múlva ' +
				'próbálkozom újra (vagy: Beállítások → Munkamenet törlése)', 'login'));
		}
		var url = API + '/login?email=' + encodeURIComponent(email) +
			'&password=' + encodeURIComponent(password);
		return http(url, apiHeaders()).then(function (resp) {
			var tok = null;
			try {
				tok = JSON.parse(resp.body).access_token;
			} catch (e) { /* nem JSON */ }
			if (resp.status === 200 && tok) {
				Store.set('token', {token: tok, ts: Date.now()});
				return tok;
			}
			Store.set('token', {failed: Date.now()});
			throw new ApiError('Sikertelen belépés (HTTP ' + resp.status + ') - ellenőrizd az ' +
				'email címet és a jelszót', 'login');
		});
	}

	function token() {
		var t = Store.get('token', {}) || {};
		return t.token ? Promise.resolve(t.token) : login();
	}

	function parseJson(resp, path) {
		if (resp.status !== 200) throw new ApiError('HTTP ' + resp.status + ': ' + path);
		try {
			return JSON.parse(resp.body);
		} catch (e) {
			throw new ApiError('Nem JSON válasz: ' + path);
		}
	}

	function apiGet(path, auth) {
		var url = API + path;
		if (!auth) return http(url, apiHeaders()).then(function (r) { return parseJson(r, path); });
		return token().then(function (tok) {
			return http(url, apiHeaders(tok));
		}).then(function (resp) {
			if (resp.status !== 401 && resp.status !== 403) return parseJson(resp, path);
			clearToken();
			return login().then(function (tok) {
				return http(url, apiHeaders(tok));
			}).then(function (r) { return parseJson(r, path); });
		});
	}

	function cached(key, ttl, fetch) {
		var c = Store.get('cache.' + key);
		if (c && Date.now() - c.ts < ttl) return Promise.resolve(c.data);
		return fetch().then(function (fresh) {
			if (fresh) Store.set('cache.' + key, {ts: Date.now(), data: fresh});
			return fresh;
		}, function (err) {
			if (c) return c.data;   // hálózati hiba: a korábbi adat marad
			throw err;
		});
	}

	function clearCache() {
		var n = 0;
		Store.keys().forEach(function (k) {
			if (k.indexOf('cache.') === 0) {
				Store.remove(k);
				n++;
			}
		});
		return n;
	}

	// --- tartalom --------------------------------------------------------------
	function s(value) {
		// a szerver néha null-t, "null"-t, számot vagy listát ad
		if (value === null || value === undefined || typeof value === 'object') return '';
		value = String(value).trim();
		return value.toLowerCase() === 'null' ? '' : value;
	}

	function first(data) {
		if (Array.isArray(data)) data = data.length ? data[0] : {};
		return data && typeof data === 'object' && !Array.isArray(data) ? data : {};
	}

	function dicts(value) {
		return Array.isArray(value) ? value.filter(function (i) {
			return i && typeof i === 'object' && !Array.isArray(i);
		}) : [];
	}

	function image(item) {
		if (s(item.poster_remote)) return s(item.poster_remote);
		if (s(item.thumbnail_remote)) return s(item.thumbnail_remote);
		if (s(item.photo_thumbnail)) return STORAGE + s(item.photo_thumbnail);
		return '';
	}

	function collections() {
		return cached('collections', LIST_TTL, function () {
			return apiGet('/collections', true);
		}).then(function (data) {
			return dicts(data).map(function (c) {
				return {title: s(c.title), slug: s(c.slug), thumb: image(c)};
			}).filter(function (c) {
				return c.title && c.slug && EXCLUDED.indexOf(c.title) < 0;
			});
		});
	}

	function vod(item) {
		var viewer = s(item.vodviewer);
		var asset = s(item.verizon_id).toLowerCase();
		var url = viewer || (ASSET_RE.test(asset) ? UPLYNK_HLS.replace('%s', asset) : '');
		var tok = s(item.token);
		return {title: s(item.title), desc: s(item.short_desc), thumb: image(item), url: url,
			locked: !viewer && tok !== '' && tok !== '0',
			plot: s(item.long_desc) || s(item.description) || s(item.short_desc)};
	}

	function vods(items) {
		var out = [];
		dicts(items).forEach(function (i) {
			out.push(vod(i));
			dicts(i.subvods).forEach(function (sub) { out.push(vod(sub)); });
		});
		return out.filter(function (v) { return v.url; });
	}

	function seriesVods(series) {
		var out = [];
		var seen = {};
		if (!series || typeof series !== 'object' || Array.isArray(series)) return out;
		Object.keys(series).forEach(function (season) {
			if (!season || !Array.isArray(series[season])) return;
			vods(series[season]).forEach(function (v) {
				if (!seen[v.url]) {
					seen[v.url] = true;
					out.push(v);
				}
			});
		});
		return out;
	}

	function collectionItems(slug) {
		return cached('items_' + slug, LIST_TTL, function () {
			return apiGet('/collectionitems/' + encodeURIComponent(slug) + '/11', false);
		}).then(function (raw) {
			var data = first(raw);
			var list = vods(data.vodsavail);
			return list.length ? list : seriesVods(data.series);
		});
	}

	function search(term) {
		return apiGet('/search/' + encodeURIComponent(term), false).then(vods);
	}

	function liveEvents() {
		return apiGet('/collectionitemslive/live/0', true).then(function (raw) {
			return dicts(first(raw).liveeventsavail).filter(function (e) {
				return s(e.slug);
			}).map(function (e) {
				return {title: s(e.title), desc: s(e.short_desc), slug: s(e.slug),
					status: s(e.status), start: s(e.expected_start), stop: s(e.expected_stop),
					thumb: image(e)};
			});
		});
	}

	function liveSources(slug) {
		return apiGet('/watch/' + encodeURIComponent(slug) + '/live', true).then(function (raw) {
			var d = first(raw);
			return {live: s(d.src), replay: s(d.replaysrc)};
		});
	}

	function isDirect(url) {
		return url.indexOf('https://content.uplynk.com/') === 0 && /\.m3u8$/.test(url);
	}

	var PLAYBACK_RE = /playbackUrl[\s\S]{0,40}?(https:[^"'\s<>]*uplynk[^"'\s<>]*)/;

	function vodStream(viewerUrl) {
		if (isDirect(viewerUrl)) return Promise.resolve(viewerUrl);
		return http(viewerUrl, {'User-Agent': FIREFOX_UA,
			'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'}).then(function (resp) {
			var m = PLAYBACK_RE.exec(resp.body || '');
			if (!m) throw new ApiError('Nem található lejátszási cím');
			return m[1].replace(/\\\//g, '/');
		});
	}

	// --- Sportok (www.network4.hu/sport/collections) --------------------------
	function txt(html) {
		var el = document.createElement('textarea');
		el.innerHTML = String(html || '').replace(/<[^>]+>/g, ' ');
		return el.value.replace(/\s+/g, ' ').trim();
	}

	function cards(chunk) {
		var re = /href="\/sport\/collection\/details\/([^"\/?#]+)"([\s\S]*?)<div class="league-card__name">([\s\S]*?)<\/div>/g;
		var out = [];
		var seen = {};
		var m;
		while ((m = re.exec(chunk))) {
			if (seen[m[1]]) continue;
			seen[m[1]] = true;
			var im = /<img src="([^"]+)"/.exec(m[2]);
			out.push({slug: m[1], name: txt(m[3]) || m[1], img: im ? im[1] : ''});
		}
		return out;
	}

	function parseSports(html) {
		html = html || '';
		var cats = [];
		var start = html.indexOf('aria-label="Kiemelt sportok"');
		var end = html.indexOf('aria-label="Összes sport"');
		if (start >= 0) {
			var items = cards(html.slice(start, end > start ? end : html.length));
			if (items.length) cats.push({title: 'Kiemelt sportok', items: items});
		}
		html.split('<div class="sport-cat" aria-label="').slice(1).forEach(function (part) {
			var title = txt(part.split('"')[0]);
			var its = cards(part);
			if (title && its.length) cats.push({title: title, items: its});
		});
		return cats;
	}

	function snapshot() {
		return fetch('data/sports.json').then(function (r) { return r.json(); })
			.catch(function () { return []; });
	}

	function sportCategories() {
		if (!Store.setting('sportWeb')) return snapshot();
		var failed = Store.get('sport_failed', 0);
		var c = Store.get('cache.sport_collections');
		if (Date.now() - failed < SPORT_RETRY && !(c && Date.now() - c.ts < SPORT_TTL)) {
			return c ? Promise.resolve(c.data) : snapshot();
		}
		return cached('sport_collections', SPORT_TTL, function () {
			// a menü nem létfontosságú: egy próbálkozás, hiba esetén a beépített lista
			return http(SPORT_PAGE, {'User-Agent': FIREFOX_UA,
				'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
				'Accept-Language': 'hu-HU,hu;q=0.9'}, 0).then(function (resp) {
				if (resp.status !== 200) throw new ApiError('HTTP ' + resp.status + ': sport-oldal');
				var cats = parseSports(resp.body);
				if (!cats.length) throw new ApiError('A sport-oldal szerkezete megváltozott');
				return cats;
			});
		}).then(function (cats) {
			return cats && cats.length ? cats : snapshot();
		}, function () {
			Store.set('sport_failed', Date.now());
			return snapshot();
		});
	}

	global.N4Api = {
		ApiError: ApiError, haveCredentials: haveCredentials, login: login,
		clearToken: clearToken, clearCache: clearCache, todayRequests: todayRequests,
		collections: collections, collectionItems: collectionItems, search: search,
		liveEvents: liveEvents, liveSources: liveSources, vodStream: vodStream,
		sportCategories: sportCategories, parseSports: parseSports, isDirect: isDirect,
		FIREFOX_UA: FIREFOX_UA
	};
})(window);
