/*
 * MagyarAnime - privát, sütialapú kliens. A Kodi-kiegészítő (plugin.video.magyaranime,
 * resources/lib/magyaranime.py) JavaScript-változata; a kérések a háttérszolgáltatáson
 * át mennek (süti + fejlécek).
 *
 * Lejátszás:
 *   GET  /resz/{vid}/                       -> CSRF (meta magyaranime) + data-server
 *   POST data/lejatszo/data_player.php      {server, vid, csrf_token}
 *     -> JSON: output (player HTML), servers[], hls, hls_url (base64), ...
 * A data_player.php hívásokat az oldal napi limitbe számolja: ezért helyi számláló,
 * 10 perces gyorsítótár, és a szerverlistához egyetlen hívás (mint a Kodi-ban).
 */
(function (global) {
	'use strict';

	var Store = global.MAStore;
	var DEFAULT_BASE = 'https://magyaranime.eu/';
	var UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0';
	var MIN_GAP = 300;
	var INDEX_TTL = 6 * 3600 * 1000;
	var INFO_TTL = 24 * 3600 * 1000;
	var EPS_TTL = 30 * 60 * 1000;
	var PD_TTL = 10 * 60 * 1000;
	var DAILY_MAX = 200;

	function ApiError(message, kind) {
		this.name = 'ApiError';
		this.message = message;
		this.kind = kind || 'api';
	}
	ApiError.prototype = Object.create(Error.prototype);

	function sleep(ms) {
		return new Promise(function (r) { setTimeout(r, ms); });
	}

	function base() {
		var url = String(Store.setting('baseUrl') || DEFAULT_BASE).trim() || DEFAULT_BASE;
		if (!/^https?:/.test(url)) url = 'https://' + url;
		if (url.charAt(url.length - 1) !== '/') url += '/';
		return url;
	}

	function abs(path) {
		return new URL(path, base()).toString();
	}

	// --- süti ----------------------------------------------------------------------
	function parseCookieText(text) {
		text = String(text || '').trim();
		var jar = {};
		if (!text) return jar;
		if (text.charAt(0) === '[' || text.charAt(0) === '{') {
			try {
				var data = JSON.parse(text);
				if (!Array.isArray(data)) {
					data = data.cookies || data.data || Object.keys(data).map(function (k) { return data[k]; });
				}
				(data || []).forEach(function (c) {
					if (c && typeof c === 'object' && c.name) jar[c.name] = c.value || '';
				});
				if (Object.keys(jar).length) return jar;
			} catch (e) { /* nem JSON */ }
		}
		if (text.indexOf('\t') >= 0) {
			text.split(/\r?\n/).forEach(function (line) {
				if (!line.trim() || line.charAt(0) === '#') return;
				var p = line.split('\t');
				if (p.length >= 7 && p[5]) jar[p[5]] = p[6];
			});
			if (Object.keys(jar).length) return jar;
		}
		text.replace(/\n/g, ';').split(';').forEach(function (part) {
			var i = part.indexOf('=');
			if (i > 0) jar[part.slice(0, i).trim()] = part.slice(i + 1).trim();
		});
		return jar;
	}

	function cookies() {
		return Store.get('cookies', {}) || {};
	}

	function setCookieText(text) {
		var jar = parseCookieText(text);
		Store.set('cookies', jar);
		return Object.keys(jar);
	}

	function clearCookies() {
		Store.remove('cookies');
	}

	function cookieNames() {
		return Object.keys(cookies());
	}

	function cookieHeader() {
		var jar = cookies();
		return Object.keys(jar).map(function (k) { return k + '=' + jar[k]; }).join('; ');
	}

	function mergeCookies(set) {
		if (!set || !Object.keys(set).length) return;
		var jar = cookies();
		if (!Object.keys(jar).length) return;   // belépés nélkül nem gyűjtünk sütit
		Object.keys(set).forEach(function (k) { jar[k] = set[k]; });
		Store.set('cookies', jar);
	}

	// --- HTTP (sorban, kis szünettel) -----------------------------------------------
	var queue = Promise.resolve();
	var last = 0;

	function headers(referer, ajax) {
		var h = {'User-Agent': UA, 'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5'};
		if (ajax) {
			h['X-Requested-With'] = 'XMLHttpRequest';
			h.Accept = 'application/json, text/javascript, */*; q=0.01';
		} else {
			h.Accept = 'text/html,application/xhtml+xml,*/*;q=0.8';
		}
		if (referer) h.Referer = referer;
		return h;
	}

	function send(opts) {
		var run = function () {
			var wait = Math.max(0, MIN_GAP - (Date.now() - last));
			return sleep(wait).then(function () {
				last = Date.now();
				opts.cookie = cookieHeader();
				return global.MABridge.request(opts);
			}).then(function (resp) {
				mergeCookies(resp.setCookies);
				if ((resp.cfMitigated || '').toLowerCase() === 'challenge') {
					throw new ApiError('Az oldal (Cloudflare) elutasította a kérést - próbáld később', 'challenge');
				}
				return resp;
			}, function (err) {
				throw new ApiError('Hálózati hiba: ' + err.message, 'network');
			});
		};
		var p = queue.then(run, run);
		queue = p.then(function () {}, function () {});
		return p;
	}

	function get(path, referer, ajax) {
		return send({url: abs(path), headers: headers(referer || base(), ajax)})
			.then(function (r) { return r.body || ''; });
	}

	function post(path, form, referer, ajax) {
		return send({url: abs(path), method: 'POST', form: form,
			headers: headers(referer || base(), ajax !== false)})
			.then(function (r) { return r.body || ''; });
	}

	function loggedIn(html) {
		var low = String(html || '').toLowerCase();
		return low.indexOf('kijelentkezes') >= 0 || low.indexOf('logout') >= 0 ||
			low.indexOf('felhasznalo/adatok') >= 0;
	}

	function checkLogin() {
		return get('', base()).then(function (html) {
			return {ok: loggedIn(html), length: html.length};
		});
	}

	// --- segédek --------------------------------------------------------------------------
	var decoder = document.createElement('textarea');

	function clean(t) {
		decoder.innerHTML = String(t || '').replace(/<[^>]+>/g, ' ');
		return decoder.value.replace(/\s+/g, ' ').trim();
	}

	function plotText(fragment) {
		var t = String(fragment || '').replace(/<\s*br\s*\/?>/gi, '\n')
			.replace(/<b>\s*Ismertető:\s*<\/b>\s*/i, '').replace(/<[^>]+>/g, '');
		decoder.innerHTML = t;
		return decoder.value.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
	}

	function poster(aid) {
		return abs('_public/images_v2/boritokepek/' + aid + '.webp');
	}

	function cached(key, ttl, fetch) {
		var c = Store.get('cache.' + key);
		if (c && Date.now() - c.ts < ttl) return Promise.resolve(c.data);
		return fetch().then(function (fresh) {
			if (fresh) {
				try {
					Store.set('cache.' + key, {ts: Date.now(), data: fresh});
				} catch (e) { /* megtelt a tároló - csak nem mentjük */ }
			}
			return fresh;
		}, function (err) {
			if (c) return c.data;
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

	// --- keresés (a teljes anime-index, 6 óráig tárolva) --------------------------------
	function searchIndex() {
		return cached('index', INDEX_TTL, function () {
			return get('data/search/data_search.php', base() + 'web/kereso/', true).then(function (txt) {
				var data;
				try {
					data = JSON.parse(txt);
				} catch (e) {
					throw new ApiError('A keresőindex nem tölthető be (be vagy jelentkezve?)');
				}
				if (!Array.isArray(data)) {
					data = data.data || data.aaData || Object.keys(data).map(function (k) { return data[k]; });
				}
				// csak a kereséshez kellő mezők (kisebb tárolás)
				return (data || []).filter(function (it) { return it && it.id; }).map(function (it) {
					return [String(it.id), it.name || '', it.name_jap || '', it.name_syn || '',
						it.name_other || ''];
				});
			});
		});
	}

	function search(term) {
		term = String(term || '').trim().toLowerCase();
		if (!term) return Promise.resolve([]);
		return searchIndex().then(function (idx) {
			var out = [];
			var seen = {};
			idx.forEach(function (it) {
				if (seen[it[0]]) return;
				for (var i = 1; i < it.length; i++) {
					if (it[i] && String(it[i]).toLowerCase().indexOf(term) >= 0) {
						seen[it[0]] = true;
						out.push({aid: it[0], title: clean(it[1] || it[2] || 'anime ' + it[0]),
							art: poster(it[0])});
						break;
					}
				}
			});
			return out.slice(0, 300);
		});
	}

	// --- adatlapok (katalógus) -------------------------------------------------------------
	var CATALOG_DEFAULTS = {allapot: '1', szezon: '1', besorolas: '1', rendezes: '1', kezdo: 'az'};
	var CAT_CARD_RE = /window\.open\('leiras\/(\d+)\/[^)]*\)[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>[\s\S]*?<div class="movie-title">\s*([\s\S]*?)\s*<\/div>/gi;

	function catalog(page, filters) {
		page = Math.max(1, parseInt(page, 10) || 1);
		var data = {};
		Object.keys(CATALOG_DEFAULTS).forEach(function (k) { data[k] = CATALOG_DEFAULTS[k]; });
		Object.keys(filters || {}).forEach(function (k) { data[k] = filters[k]; });
		var key = 'cat_' + page + '_' + JSON.stringify(data);
		return cached(key, 30 * 60 * 1000, function () {
			var req;
			if (page <= 1 && !filters) {
				req = get('anime/adatlapok/', base());
			} else {
				data.page = String(page);
				req = post('anime/adatlapok/', data, base() + 'anime/adatlapok/', false);
			}
			return req.then(function (html) {
				var items = [];
				var seen = {};
				var m;
				CAT_CARD_RE.lastIndex = 0;
				while ((m = CAT_CARD_RE.exec(html))) {
					if (seen[m[1]]) continue;
					seen[m[1]] = true;
					items.push({aid: m[1], title: clean(m[3]), art: abs(m[2])});
				}
				var pm = /Jelenlegi oldal:\s*<\/b>\s*(\d+)\s*\/\s*(\d+)/i.exec(html);
				return {items: items, page: page, pages: pm ? parseInt(pm[2], 10) : 1};
			});
		});
	}

	function catalogFilters() {
		return cached('catfilters', INFO_TTL, function () {
			return get('anime/adatlapok/', base()).then(function (html) {
				var out = {};
				var re = /<select name="(allapot|szezon|besorolas|rendezes|kezdo)"[^>]*>([\s\S]*?)<\/select>/gi;
				var m;
				while ((m = re.exec(html))) {
					var opts = [];
					var ore = /<option value="([^"]*)"[^>]*>\s*([\s\S]*?)\s*<\/option>/gi;
					var o;
					while ((o = ore.exec(m[2]))) {
						var label = clean(o[2]);
						if (o[1] !== '' && label) opts.push([o[1], label]);
					}
					if (opts.length) out[m[1]] = opts;
				}
				return out;
			});
		});
	}

	// --- anime adatlap és részek ----------------------------------------------------------
	var META_CSRF_RE = /<meta\s+name="magyaranime"\s+content="([^"]+)"/i;
	var DESC_RE = /<div class="leiras_text"[^>]*>([\s\S]*?)<\/div>/i;

	function headerInfo(html) {
		var tm = /<h2 class="gen-title[^"]*">([^<]+)<\/h2>/.exec(html);
		var dm = DESC_RE.exec(html);
		var meta = [];
		var em = /Epizódok:\s*([0-9]+\s*\/\s*[0-9]+)/.exec(html);
		if (em) meta.push(em[1].replace(/\s+/g, '') + ' rész');
		var sm = />\s*(\d{4}\s+(?:Tavasz|Nyár|Ősz|Tél))\s*</.exec(html);
		if (sm) meta.push(sm[1]);
		var pg = /<span>\s*((?:PG-\d+|R\+?|G|NC-17|R-17\+?|PG)\b[^<]*)<\/span>/.exec(html);
		if (pg) meta.push(clean(pg[1]));
		var mal = /MAL:\s*<span>([^<]+)<\/span>/.exec(html);
		if (mal) meta.push('MAL ' + clean(mal[1]));
		return {title: tm ? clean(tm[1]) : '', plot: dm ? plotText(dm[1]) : '', meta: meta};
	}

	function animeInfo(aid) {
		return cached('info_' + aid, INFO_TTL, function () {
			return get('leiras/' + aid + '/', base()).then(headerInfo);
		});
	}

	function collectEpWindow(html) {
		var thumbs = {};
		var re1 = /window\.location='resz\/(\d+)\/';"[^>]*>\s*<img[^>]*?\bdata-src="([^"]+)"/gi;
		var re2 = /window\.location='resz\/(\d+)\/';"[^>]*>\s*<img(?![^>]*\bdata-src)[^>]*?\bsrc="([^"]+)"/gi;
		var m;
		while ((m = re1.exec(html))) if (!thumbs[m[1]]) thumbs[m[1]] = m[2];
		while ((m = re2.exec(html))) if (!thumbs[m[1]]) thumbs[m[1]] = m[2];
		var fillers = {};
		var rf = /<a href="resz\/(\d+)\/"\s+oncontextmenu="return false;">[^<]*<\/a>([\s\S]*?)<\/h3>/gi;
		while ((m = rf.exec(html))) {
			var bm = /badge bg-\w+">([^<]+)<\/span>/.exec(m[2]);
			if (bm) {
				var b = clean(bm[1]);
				if (/filler|canon/i.test(b) && !fillers[m[1]]) fillers[m[1]] = b;
			}
		}
		var out = [];
		var rt = /<a href="resz\/(\d+)\/"\s+oncontextmenu="return false;">([^<]+)<\/a>/gi;
		while ((m = rt.exec(html))) {
			var t = clean(m[2]);
			var num = /(\d+)/.exec(t);
			if (!num) continue;
			out.push({vid: m[1], num: parseInt(num[1], 10), thumb: thumbs[m[1]] || '', title: t,
				filler: fillers[m[1]] || ''});
		}
		return out;
	}

	function episodesOfAnime(aid) {
		return cached('eps_' + aid, EPS_TTL, function () {
			return get('leiras/' + aid + '/', base()).then(function (html) {
				var info = headerInfo(html);
				var mx = /id="epizod_szam"[^>]*data-max="(\d+)"/.exec(html);
				var maxEp = mx ? parseInt(mx[1], 10) : 0;
				var cm = META_CSRF_RE.exec(html);
				var csrf = cm ? cm[1] : '';
				var referer = base() + 'leiras/' + aid + '/';
				var acc = {};
				var add = function (list) {
					list.forEach(function (e) {
						if (acc[e.num]) return;
						acc[e.num] = {vid: e.vid, num: e.num, title: e.title || e.num + '. rész',
							thumb: e.thumb ? abs(e.thumb) : '', filler: e.filler};
					});
				};
				var windowAt = function (center) {
					return post('leiras/' + aid + '/', {epizod_szam: String(center), csrf_token: csrf},
						referer, false).then(function (h) { add(collectEpWindow(h)); });
				};
				// az ablak: epizod_szam=N -> [N-9 .. N+16]; 26-os lépéssel hézagmentesen
				var top = maxEp || 100000;
				var need = 1;
				var guard = 0;
				var step = function () {
					if (need > top || guard >= 80) return Promise.resolve();
					guard++;
					var before = Object.keys(acc).length;
					return windowAt(need + 9).then(function () {
						if (!maxEp && Object.keys(acc).length === before) return null;
						need += 26;
						return step();
					});
				};
				return step().then(function () {
					if (!maxEp || !Object.keys(acc).length) return null;
					var missing = [];
					for (var n = 1; n <= maxEp && missing.length < 15; n++) if (!acc[n]) missing.push(n);
					return missing.reduce(function (p, n) {
						return p.then(function () { if (!acc[n]) return windowAt(n + 9); });
					}, Promise.resolve());
				}).then(function () {
					if (!Object.keys(acc).length) add(collectEpWindow(html));
					var eps = Object.keys(acc).map(Number).sort(function (a, b) { return a - b; })
						.filter(function (n) { return !maxEp || n <= maxEp; })
						.map(function (n) { return acc[n]; });
					return {title: info.title, plot: info.plot, meta: info.meta, episodes: eps};
				});
			});
		});
	}

	// --- napi számláló és data_player gyorsítótár ---------------------------------------
	function today() {
		var d = new Date();
		return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
	}

	function todayCount() {
		var d = Store.get('daily', {}) || {};
		return d.date === today() ? (d.count || 0) : 0;
	}

	function bump() {
		var d = Store.get('daily', {}) || {};
		if (d.date !== today()) d = {date: today(), count: 0};
		d.count = (d.count || 0) + 1;
		Store.set('daily', d);
	}

	function playerData(server, vid, csrf, referer) {
		var key = 'pd_' + vid + '_' + server;
		var c = Store.get(key);
		if (c && Date.now() - c.ts < PD_TTL) return Promise.resolve(c.data);
		return post('data/lejatszo/data_player.php', {server: server, vid: vid, csrf_token: csrf},
			referer, true).then(function (txt) {
			if (!txt) return null;
			bump();   // a kérés elérte a szervert -> a napi limitbe számít
			var data;
			try {
				data = JSON.parse(txt);
			} catch (e) {
				return null;
			}
			if (data && typeof data === 'object' && !data.error) {
				Store.set(key, {ts: Date.now(), data: data});
				pruneDataCache();
			}
			return data;
		});
	}

	function pruneDataCache() {
		Store.keys().forEach(function (k) {
			if (k.indexOf('pd_') !== 0) return;
			var c = Store.get(k);
			if (!c || Date.now() - c.ts > PD_TTL) Store.remove(k);
		});
	}

	function reszPage(vid) {
		return get('resz/' + vid + '/', base()).then(function (page) {
			var cm = META_CSRF_RE.exec(page);
			var dv = /id="VideoPlayer"[^>]*data-server="([^"]*)"/.exec(page);
			return {csrf: cm ? cm[1] : '', server: dv ? dv[1] : 's1',
				referer: base() + 'resz/' + vid + '/', html: page};
		});
	}

	function unescapeUrl(u) {
		return String(u || '').replace(/\\\//g, '/').replace(/&amp;/g, '&');
	}

	function extract(output) {
		var urls = [];
		var m;
		var src = /<source[^>]+src=["']([^"']+)["']/gi;
		while ((m = src.exec(output))) urls.push(unescapeUrl(m[1]));
		var mp4 = /https?:\\?\/\\?\/[^"'\s<>]+?\.mp4[^"'\s<>]*/gi;
		while ((m = mp4.exec(output))) urls.push(unescapeUrl(m[0]));
		var frames = [];
		var fr = /<iframe[^>]+src=["']([^"']+)["']/gi;
		while ((m = fr.exec(output))) frames.push(unescapeUrl(m[1]));
		return {urls: urls.filter(function (u, i) { return u && urls.indexOf(u) === i; }), iframes: frames};
	}

	function b64decode(s) {
		try {
			return decodeURIComponent(escape(atob(s)));
		} catch (e) {
			return '';
		}
	}

	function hostOf(url) {
		var hosts = ['indavideo', 'videa', 'mega', 'dailymotion', 'streamtape', 'dood', 'mp4upload',
			'rumble', 'ok.ru', 'vk.com', 'sibnet', 'youtube', 'filemoon', 'vidoza', 'voe'];
		var u = String(url || '').toLowerCase();
		for (var i = 0; i < hosts.length; i++) if (u.indexOf(hosts[i]) >= 0) return hosts[i];
		try {
			return new URL(url).hostname;
		} catch (e) {
			return 'ismeretlen';
		}
	}

	function quality(text) {
		var m = /(?:^|[^\d])(\d{3,4})\s*[pP](?![a-z])/.exec(text || '');
		if (m && +m[1] >= 144 && +m[1] <= 4320) return m[1] + 'p';
		m = /\.(\d{3,4})\.(?:mp4|mkv|webm|m3u8)/i.exec(text || '');
		if (m && +m[1] >= 144 && +m[1] <= 4320) return m[1] + 'p';
		return '';
	}

	function classify(data) {
		if (data.hls && data.hls_url) return {kind: 'hls', host: 'Közvetlen (HLS)', quality: ''};
		var ex = extract(data.output || '');
		var mp4 = ex.urls.filter(function (u) { return /\.mp4/i.test(u); });
		if (mp4.length) return {kind: 'mp4', host: 'Közvetlen (MP4)', quality: quality(mp4[0])};
		if (ex.iframes.length) return {kind: 'embed', host: hostOf(ex.iframes[0]), quality: quality(ex.iframes[0])};
		return null;
	}

	// szerverlista: EGYETLEN data_player hívás (a többi szerver a válasz "servers" tömbjéből)
	function listServers(vid) {
		return reszPage(vid).then(function (rp) {
			return playerData(rp.server, vid, rp.csrf, rp.referer).then(function (data) {
				if (!data) return [];
				if (data.error) throw limitOr(data.error);
				var out = [];
				var seen = {};
				var def = classify(data);
				if (def) {
					out.push({server: rp.server, host: def.host, kind: def.kind, quality: def.quality});
					seen[rp.server] = true;
				}
				(Array.isArray(data.servers) ? data.servers : []).forEach(function (s) {
					if (!s || !s.server || seen[s.server]) return;
					seen[s.server] = true;
					var hq = /(\d{3,4})/.exec(s.hq || '');
					out.push({server: s.server, host: clean(s.title || '') || 'Szerver ' + s.server,
						kind: 'server', quality: hq ? hq[1] + 'p' : ''});
				});
				return out;
			});
		});
	}

	function limitOr(err) {
		var msg = String(err);
		if (/limit/i.test(msg)) {
			return new ApiError('MagyarAnime napi videó-limit elérve (a fiókodon). Naponta ' +
				'nullázódik - próbáld később / holnap.', 'limit');
		}
		return new ApiError('Az oldal hibát adott: ' + msg);
	}

	function streamHeaders(referer) {
		return {'User-Agent': UA, Referer: referer, Origin: base().replace(/\/$/, '')};
	}

	function indavideo(embed) {
		var m = /\/(?:player\/video|video)\/([0-9a-zA-Z-]+)/.exec(embed);
		var id = m ? m[1] : embed.replace(/\/$/, '').split('/').pop();
		return send({url: 'https://amfphp.indavideo.hu/SYm0json.php/player.getVideoData/' + id,
			headers: {'User-Agent': UA, Referer: embed}}).then(function (resp) {
			var data = JSON.parse(resp.body);
			var d = data.data || data;
			var files = d.video_files || [];
			if (!Array.isArray(files)) files = Object.keys(files).map(function (k) { return files[k]; });
			var tokens = d.filesh || {};
			var best = null;
			var bestH = -1;
			files.forEach(function (f) {
				var hm = /\.(\d{3,4})\.mp4/.exec(f);
				var h = hm ? parseInt(hm[1], 10) : 0;
				var url = f;
				var tok = tokens[String(h)] || tokens[Object.keys(tokens)[0]];
				if (tok) url = f + (f.indexOf('?') >= 0 ? '&' : '?') + 'token=' + tok;
				if (h >= bestH) {
					bestH = h;
					best = url;
				}
			});
			return best;
		}).catch(function () { return null; });
	}

	// a megadott (vagy az alapértelmezett, majd s1..s5) szerverről lejátszható cím
	function resolve(vid, prefer) {
		return reszPage(vid).then(function (rp) {
			var order = [];
			[prefer, rp.server, 's1', 's2', 's3', 's4', 's5'].forEach(function (s) {
				if (s && order.indexOf(s) < 0) order.push(s);
			});
			var mega = false;
			var next = function (i) {
				if (i >= order.length) {
					throw new ApiError(mega ? 'Ez a rész mega.nz-en van, ami nem támogatott - ' +
						'próbálj másik szervert.' : 'Nem sikerült lejátszható forrást találni.');
				}
				return playerData(order[i], vid, rp.csrf, rp.referer).then(function (data) {
					if (!data) return next(i + 1);
					if (data.error) {
						if (/limit/i.test(String(data.error))) throw limitOr(data.error);
						return next(i + 1);
					}
					var hdr = streamHeaders(rp.referer);
					if (data.hls && data.hls_url) {
						var hls = b64decode(data.hls_url);
						if (hls) return {url: hls, hls: true, headers: hdr};
					}
					var output = data.output || '';
					var ex = extract(output);
					var mp4 = ex.urls.filter(function (u) { return /\.mp4/i.test(u); });
					if (mp4.length) return {url: mp4[0], hls: false, headers: hdr};
					var frames = ex.iframes.slice();
					var tryFrame = function () {
						var fr = frames.shift();
						if (!fr) {
							var m3 = /https?:\/\/[^"'\s]+?\.m3u8[^"'\s]*/.exec(output);
							if (m3) return {url: m3[0], hls: true, headers: hdr};
							return next(i + 1);
						}
						if (/mega\.(nz|co\.nz)/i.test(fr)) mega = true;
						if (/indavideo/i.test(fr)) {
							return indavideo(fr).then(function (media) {
								return media ? {url: media, hls: false, headers: {'User-Agent': UA,
									Referer: fr}} : tryFrame();
							});
						}
						return tryFrame();
					};
					return tryFrame();
				});
			};
			return next(0);
		});
	}

	global.MAApi = {
		ApiError: ApiError, base: base, UA: UA, DAILY_MAX: DAILY_MAX,
		parseCookieText: parseCookieText, setCookieText: setCookieText, clearCookies: clearCookies,
		cookieNames: cookieNames, checkLogin: checkLogin, clearCache: clearCache,
		search: search, catalog: catalog, catalogFilters: catalogFilters, poster: poster,
		animeInfo: animeInfo, episodesOfAnime: episodesOfAnime, listServers: listServers,
		resolve: resolve, todayCount: todayCount, collectEpWindow: collectEpWindow,
		headerInfo: headerInfo
	};
})(window);
