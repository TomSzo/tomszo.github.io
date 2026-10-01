/*
 * A háttérszolgáltatás hívása (luna://hu.tomszo.magyaranime.service/...).
 * TV-n a PalmServiceBridge-et használjuk (ezt csomagolja a webOSTV.js is).
 * Asztali böngészőben (fejlesztés / teszt) a window.MA_HTTP és a window.MA_SUB
 * helyettesítők hívódnak.
 */
(function (global) {
	'use strict';

	var BASE = 'luna://hu.tomszo.magyaranime.service/';
	var pending = [];   // a hívás objektuma a válaszig / lemondásig élve marad

	function onTV() {
		return typeof global.PalmServiceBridge === 'function';
	}

	function open(method, params, onMessage) {
		var bridge = new global.PalmServiceBridge();
		pending.push(bridge);
		bridge.onservicecallback = function (msg) {
			var res;
			try {
				res = JSON.parse(msg);
			} catch (e) {
				res = {returnValue: false, errorText: 'Hibás szolgáltatás-válasz'};
			}
			onMessage(res, bridge);
		};
		bridge.call(BASE + method, JSON.stringify(params || {}));
		return bridge;
	}

	function release(bridge) {
		var i = pending.indexOf(bridge);
		if (i >= 0) pending.splice(i, 1);
	}

	function request(opts) {
		if (!onTV()) {
			if (typeof global.MA_HTTP === 'function') return Promise.resolve(global.MA_HTTP(opts));
			return Promise.reject(new Error('Csak TV-n működik (nincs háttérszolgáltatás)'));
		}
		return new Promise(function (resolve, reject) {
			open('request', opts, function (res, bridge) {
				release(bridge);
				if (res.returnValue === false) reject(new Error(res.errorText || 'Szolgáltatáshiba'));
				else resolve(res);
			});
		});
	}

	// feliratkozás (pair, proxy): onMessage minden üzenetnél; a visszaadott függvény lemond
	function subscribe(method, params, onMessage) {
		if (!onTV()) {
			if (typeof global.MA_SUB === 'function') return global.MA_SUB(method, params, onMessage);
			onMessage({returnValue: false, errorText: 'Csak TV-n működik'});
			return function () {};
		}
		var p = {};
		Object.keys(params || {}).forEach(function (k) { p[k] = params[k]; });
		p.subscribe = true;
		var bridge = open(method, p, function (res) { onMessage(res); });
		return function () {
			try {
				bridge.cancel();
			} catch (e) { /* már lezárult */ }
			release(bridge);
		};
	}

	global.MABridge = {request: request, subscribe: subscribe, onTV: onTV()};
})(window);
