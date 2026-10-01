/*
 * Beállítások, token és gyorsítótár a TV helyi tárolójában (localStorage).
 * A tároló kivételt dobhat vagy üres lehet - ilyenkor csak memóriában dolgozunk.
 */
(function (global) {
	'use strict';

	var PREFIX = 'n4.';
	var memory = {};

	function get(key, def) {
		var raw;
		try {
			raw = global.localStorage.getItem(PREFIX + key);
		} catch (e) {
			raw = memory[key];
		}
		if (raw === null || raw === undefined) return def;
		try {
			return JSON.parse(raw);
		} catch (e) {
			return def;
		}
	}

	function set(key, value) {
		var raw = JSON.stringify(value);
		memory[key] = raw;
		try {
			global.localStorage.setItem(PREFIX + key, raw);
		} catch (e) { /* csak memóriában */ }
	}

	function remove(key) {
		delete memory[key];
		try {
			global.localStorage.removeItem(PREFIX + key);
		} catch (e) { /* nincs mit tenni */ }
	}

	function keys() {
		var out = Object.keys(memory);
		try {
			for (var i = 0; i < global.localStorage.length; i++) {
				var k = global.localStorage.key(i);
				if (k && k.indexOf(PREFIX) === 0) out.push(k.slice(PREFIX.length));
			}
		} catch (e) { /* csak a memória */ }
		return out.filter(function (k, i) { return out.indexOf(k) === i; });
	}

	var DEFAULTS = {email: '', password: '', apiUa: 'app', quality: '1080', askReplay: true,
		sportWeb: true, licenseUrl: '', engine: 'shaka',
		connection: 'auto'};

	function setting(name) {
		var s = get('settings', {}) || {};
		return s[name] === undefined ? DEFAULTS[name] : s[name];
	}

	function saveSettings(values) {
		var s = get('settings', {}) || {};
		Object.keys(values).forEach(function (k) { s[k] = values[k]; });
		set('settings', s);
	}

	global.N4Store = {get: get, set: set, remove: remove, keys: keys, setting: setting,
		saveSettings: saveSettings};
})(window);
