/*
 * HTTP-kérés a Network4 felé - két úton:
 *   1) közvetlenül a TV böngészőmotorjából (fetch): a net4plus API CORS-t enged
 *      (Access-Control-Allow-Origin: *, az Authorization fejléc is), és a Cloudflare a
 *      valódi böngészőt szívesebben engedi át, mint a Node.js-t;
 *   2) a háttérszolgáltatáson át (luna://hu.tomszo.network4.service/get) - ez tetszőleges
 *      fejlécet küldhet, és CORS nélküli oldalakat (pl. www.network4.hu) is elér.
 * "Automatikus" módban előbb az 1), hiba vagy Cloudflare-kihívás esetén a 2).
 * Asztali böngészőben (fejlesztés / teszt) a window.N4_HTTP helyettesítő hívódik.
 */
(function (global) {
	'use strict';

	var SERVICE = 'luna://hu.tomszo.network4.service/get';
	var DIRECT_HOSTS = ['net4plus.network4.hu'];
	var TIMEOUT = 25000;
	var pending = [];   // a hívás objektuma a válaszig élve marad (különben eltakarítható)
	var state = {lastVia: ''};

	function onTV() {
		return typeof global.PalmServiceBridge === 'function';
	}

	function mode() {
		var store = global.N4Store;
		return store ? store.setting('connection') : 'auto';
	}

	function luna(uri, params) {
		return new Promise(function (resolve, reject) {
			var bridge = new global.PalmServiceBridge();
			pending.push(bridge);
			bridge.onservicecallback = function (msg) {
				var i = pending.indexOf(bridge);
				if (i >= 0) pending.splice(i, 1);
				var res;
				try {
					res = JSON.parse(msg);
				} catch (e) {
					reject(new Error('Hibás szolgáltatás-válasz'));
					return;
				}
				if (res.returnValue === false) {
					reject(new Error(res.errorText || 'Szolgáltatáshiba'));
				} else {
					resolve(res);
				}
			};
			bridge.call(uri, JSON.stringify(params || {}));
		});
	}

	function viaService(url, headers) {
		if (onTV()) return luna(SERVICE, {url: url, headers: headers || {}});
		if (typeof global.N4_HTTP === 'function') {
			return Promise.resolve(global.N4_HTTP(url, headers || {}));
		}
		return Promise.reject(new Error('Nincs háttérszolgáltatás (csak TV-n működik)'));
	}

	function viaBrowser(url, headers) {
		// a böngésző a User-Agent-et nem engedi felülírni - a sajátját küldi
		var h = {};
		Object.keys(headers || {}).forEach(function (k) {
			if (k.toLowerCase() !== 'user-agent') h[k] = headers[k];
		});
		var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
		var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, TIMEOUT);
		return fetch(url, {headers: h, credentials: 'omit', cache: 'no-store',
			signal: ctrl ? ctrl.signal : undefined}).then(function (resp) {
			return resp.text().then(function (body) {
				clearTimeout(timer);
				return {status: resp.status, contentType: resp.headers.get('content-type') || '',
					cfMitigated: resp.headers.get('cf-mitigated') || '', body: body};
			});
		}, function (err) {
			clearTimeout(timer);
			// CORS nélküli hibaválasz (pl. Cloudflare-kihívás) is ide fut: TypeError
			throw new Error('böngésző: ' + (err && err.name === 'AbortError' ? 'időtúllépés' :
				'a kérés nem ment át'));
		});
	}

	function blocked(resp) {
		// a JSON-os 401/403 (lejárt token) nem tiltás - azt az API-réteg kezeli
		var html = (resp.contentType || '').indexOf('text/html') >= 0;
		return resp.status === 429 || (resp.cfMitigated || '').toLowerCase() === 'challenge' ||
			((resp.status === 403 || resp.status === 503) && html);
	}

	function direct(url) {
		try {
			return DIRECT_HOSTS.indexOf(new URL(url).hostname) >= 0;
		} catch (e) {
			return false;
		}
	}

	function httpGet(url, headers) {
		var m = mode();
		var canBrowser = direct(url) && m !== 'service' && (onTV() || global.N4_DIRECT);
		if (!canBrowser) {
			state.lastVia = 'szolgáltatás';
			return viaService(url, headers);
		}
		return viaBrowser(url, headers).then(function (resp) {
			if (m === 'browser' || !blocked(resp)) {
				state.lastVia = 'böngésző';
				return resp;
			}
			state.lastVia = 'szolgáltatás (a böngészőt elutasította: HTTP ' + resp.status + ')';
			return viaService(url, headers).catch(function () { return resp; });
		}, function (err) {
			if (m === 'browser') throw err;
			state.lastVia = 'szolgáltatás (' + err.message + ')';
			return viaService(url, headers);
		});
	}

	global.N4Bridge = {httpGet: httpGet, onTV: onTV(), state: state};
})(window);
