/*
 * Lejátszó (shaka-player): Uplynk HLS (videótár) és élő HLS / DASH.
 * DASH esetén Widevine-licenc (alapból az Uplynk licencszervere, mint a Kodi-ban).
 * Minőség: a Kodi 0.5.3 mintájára rögzített felső határ (mikroszaggatás ellen).
 */
(function (global) {
	'use strict';

	var Store = global.N4Store;
	var DEFAULT_LICENSE = 'https://content.uplynk.com/wv';
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27,
		BACKSPACE: 8, PLAY: 415, PAUSE: 19, STOP: 413, FF: 417, RW: 412};

	var root, video, title, fill, timeEl, statusEl;
	var player = null;
	var onClose = null;
	var hideTimer = null;
	var isLive = false;

	function fmt(sec) {
		if (!isFinite(sec) || sec < 0) return '--:--';
		sec = Math.floor(sec);
		var h = Math.floor(sec / 3600);
		var m = Math.floor(sec % 3600 / 60);
		var s2 = sec % 60;
		var mm = (h && m < 10 ? '0' : '') + m;
		return (h ? h + ':' : '') + mm + ':' + (s2 < 10 ? '0' : '') + s2;
	}

	function showOsd() {
		root.classList.add('osd');
		clearTimeout(hideTimer);
		hideTimer = setTimeout(function () {
			if (!video.paused) root.classList.remove('osd');
		}, 4000);
	}

	function update() {
		if (isLive) {
			timeEl.textContent = 'ÉLŐ';
			fill.style.width = '100%';
			return;
		}
		var d = video.duration;
		fill.style.width = isFinite(d) && d > 0 ? (video.currentTime / d * 100) + '%' : '0%';
		timeEl.textContent = fmt(video.currentTime) + ' / ' + fmt(d);
	}

	function status(msg) {
		statusEl.textContent = msg || '';
		statusEl.style.display = msg ? 'block' : 'none';
	}

	function maxHeight() {
		var q = Store.setting('quality');
		return q === '720' ? 720 : q === 'auto' ? Infinity : 1080;
	}

	function errorText(err) {
		var code = err && err.code;
		if (code === 6001 || code === 6002 || code === 6007) {
			return 'A DRM-védett adás nem játszható le (Widevine-hiba ' + code + ')';
		}
		if (code >= 1000 && code < 2000) return 'Hálózati hiba a lejátszásnál (' + code + ')';
		return 'Lejátszási hiba' + (code ? ' (' + code + ')' : '');
	}

	function close() {
		clearTimeout(hideTimer);
		root.classList.remove('open', 'osd');
		var p = player;
		player = null;
		var done = p ? p.destroy() : Promise.resolve();
		done.catch(function () {}).then(function () {
			video.removeAttribute('src');
			try {
				video.load();
			} catch (e) { /* nincs mit tenni */ }
		});
		var cb = onClose;
		onClose = null;
		if (cb) cb();
	}

	function play(url, label, live, closed) {
		onClose = closed;
		isLive = !!live;
		title.textContent = label || '';
		root.classList.add('open');
		status('Betöltés…');
		showOsd();
		update();

		var mpd = /\.mpd(\?|$)/i.test(url);
		if (!mpd && Store.setting('engine') === 'native') {
			// a webOS beépített HLS-lejátszója (tartalék; minőségkorlát nélkül)
			video.src = url;
			video.play().then(function () { status(''); }, function () {
				status('Lejátszási hiba (beépített lejátszó)');
			});
			return;
		}
		global.shaka.polyfill.installAll();
		if (!global.shaka.Player.isBrowserSupported()) {
			status('Ez a TV nem támogatja a lejátszót');
			return;
		}
		player = new global.shaka.Player();
		var config = {
			abr: {restrictions: {maxHeight: maxHeight()}},
			streaming: {bufferingGoal: 30, rebufferingGoal: 4, retryParameters: {maxAttempts: 4}}
		};
		if (mpd) {
			config.drm = {servers: {'com.widevine.alpha': Store.setting('licenseUrl') ||
				DEFAULT_LICENSE}};
		}
		player.configure(config);
		player.addEventListener('error', function (ev) { status(errorText(ev.detail)); });
		player.addEventListener('buffering', function (ev) {
			status(ev.buffering ? 'Pufferelés…' : '');
		});
		player.attach(video).then(function () {
			return player.load(url);
		}).then(function () {
			status('');
			return video.play();
		}).catch(function (err) {
			if (player) status(errorText(err));
		});
	}

	function seek(delta) {
		if (isLive || !isFinite(video.duration)) return;
		video.currentTime = Math.max(0, Math.min(video.duration - 1, video.currentTime + delta));
		showOsd();
	}

	function toggle() {
		if (video.paused) video.play(); else video.pause();
		showOsd();
	}

	function handleKey(e) {
		if (!root.classList.contains('open')) return false;
		switch (e.keyCode) {
		case KEY.BACK: case KEY.ESC: case KEY.BACKSPACE: case KEY.STOP:
			close();
			break;
		case KEY.OK: case KEY.PLAY: case KEY.PAUSE:
			toggle();
			break;
		case KEY.LEFT: case KEY.RW:
			seek(-10);
			break;
		case KEY.RIGHT: case KEY.FF:
			seek(30);
			break;
		default:
			showOsd();
		}
		return true;
	}

	function init() {
		root = document.getElementById('player');
		video = root.querySelector('video');
		title = root.querySelector('.p-title');
		fill = root.querySelector('.p-fill');
		timeEl = root.querySelector('.p-time');
		statusEl = root.querySelector('.p-status');
		video.addEventListener('timeupdate', update);
		video.addEventListener('pause', showOsd);
		video.addEventListener('ended', close);
		video.addEventListener('playing', function () { status(''); });
		video.addEventListener('waiting', function () { if (!player) status('Pufferelés…'); });
		video.addEventListener('error', function () {
			if (!player && root.classList.contains('open')) status('Lejátszási hiba (beépített lejátszó)');
		});
	}

	global.N4Player = {init: init, play: play, handleKey: handleKey,
		isOpen: function () { return root && root.classList.contains('open'); }};
})(window);
