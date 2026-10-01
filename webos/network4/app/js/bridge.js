/*
 * HTTP-kérés a háttérszolgáltatáson át (luna://hu.tomszo.network4.service/get).
 * TV-n a PalmServiceBridge-et használjuk (ezt csomagolja a webOSTV.js is).
 * Asztali böngészőben (fejlesztés / teszt) a window.N4_HTTP helyettesítő hívódik.
 */
(function (global) {
	'use strict';

	var SERVICE = 'luna://hu.tomszo.network4.service/get';
	var pending = [];   // a hívás objektuma a válaszig élve marad (különben eltakarítható)

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

	function httpGet(url, headers) {
		if (typeof global.PalmServiceBridge === 'function') {
			return luna(SERVICE, {url: url, headers: headers || {}});
		}
		if (typeof global.N4_HTTP === 'function') {
			return Promise.resolve(global.N4_HTTP(url, headers || {}));
		}
		return Promise.reject(new Error('Csak TV-n működik (nincs háttérszolgáltatás)'));
	}

	global.N4Bridge = {httpGet: httpGet, onTV: typeof global.PalmServiceBridge === 'function'};
})(window);
