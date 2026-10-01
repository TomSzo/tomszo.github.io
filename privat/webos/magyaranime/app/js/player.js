/*
 * Lejátszó: HLS shaka-playerrel (vagy a webOS beépített lejátszójával), MP4 a beépített
 * lejátszóval. A videószerver Referer / Origin fejlécet várhat, amit a böngésző nem küld:
 * ezért (alapból) a háttérszolgáltatás helyi továbbítóján át megy, ami a fejléceket
 * hozzáadja - ha a TV ezt nem engedi, közvetlenül próbálja.
 */
(function (global) {
	'use strict';

	var Store = global.MAStore;
	var KEY = {OK: 13, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, BACK: 461, ESC: 27,
		BACKSPACE: 8, PLAY: 415, PAUSE: 19, STOP: 413, FF: 417, RW: 412};

	var root, video, title, fill, timeEl, leftEl, statusEl;
	var player = null;
	var onClose = null;
	var hideTimer = null;
	var cancelProxy = null;
	var session = 0;

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
		var d = video.duration;
		fill.style.width = isFinite(d) && d > 0 ? (video.currentTime / d * 100) + '%' : '0%';
		timeEl.textContent = fmt(video.currentTime);
		leftEl.textContent = isFinite(d) && d > 0 ? '-' + fmt(d - video.currentTime) : '';
	}

	function status(msg) {
		statusEl.textContent = msg || '';
		statusEl.style.display = msg ? 'block' : 'none';
	}

	function errorText(err) {
		var code = err && err.code;
		if (code >= 1000 && code < 2000) return 'Hálózati hiba a lejátszásnál (' + code + ')';
		return 'Lejátszási hiba' + (code ? ' (' + code + ')' : '');
	}

	function close() {
		session++;
		clearTimeout(hideTimer);
		root.classList.remove('open', 'osd', 'paused');
		var pos = {time: video.currentTime || 0, duration: video.duration || 0};
		var p = player;
		player = null;
		var done = p ? p.destroy() : Promise.resolve();
		done.catch(function () {}).then(function () {
			video.removeAttribute('src');
			try {
				video.load();
			} catch (e) { /* nincs mit tenni */ }
		});
		if (cancelProxy) {
			cancelProxy();
			cancelProxy = null;
		}
		var cb = onClose;
		onClose = null;
		if (cb) cb(pos);
	}

	function start(url, hls, my) {
		if (my !== session) return;
		if (!hls || Store.setting('engine') === 'native') {
			video.src = url;
			video.play().then(function () { status(''); }, function () {
				if (my === session) status('Lejátszási hiba (beépített lejátszó)');
			});
			return;
		}
		global.shaka.polyfill.installAll();
		if (!global.shaka.Player.isBrowserSupported()) {
			status('Ez a TV nem támogatja a lejátszót');
			return;
		}
		player = new global.shaka.Player();
		player.configure({streaming: {bufferingGoal: 30, rebufferingGoal: 4,
			retryParameters: {maxAttempts: 4}}});
		player.addEventListener('error', function (ev) { status(errorText(ev.detail)); });
		player.addEventListener('buffering', function (ev) {
			status(ev.buffering ? 'Pufferelés…' : '');
		});
		var p = player;
		p.attach(video).then(function () {
			return p.load(url);
		}).then(function () {
			status('');
			return video.play();
		}).catch(function (err) {
			if (player === p) status(errorText(err));
		});
	}

	// src: {url, hls, headers}
	function play(src, label, closed) {
		var my = ++session;
		onClose = closed;
		title.textContent = label || '';
		root.classList.add('open');
		status('Betöltés…');
		showOsd();
		update();
		if (Store.setting('proxy') === 'off' || !src.headers) {
			start(src.url, src.hls, my);
			return;
		}
		var started = false;
		cancelProxy = global.MABridge.subscribe('proxy', {url: src.url, headers: src.headers},
			function (res) {
				if (started || my !== session) return;
				started = true;
				if (res.returnValue === false || !res.url) {
					// a TV nem engedi a továbbítót: közvetlenül próbáljuk
					start(src.url, src.hls, my);
				} else {
					start(res.url, src.hls, my);
				}
			});
	}

	function seek(delta) {
		if (!isFinite(video.duration)) return;
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
		leftEl = root.querySelector('.p-left');
		statusEl = root.querySelector('.p-status');
		video.addEventListener('timeupdate', update);
		video.addEventListener('pause', function () {
			if (root.classList.contains('open')) root.classList.add('paused');
			showOsd();
		});
		video.addEventListener('play', function () { root.classList.remove('paused'); });
		video.addEventListener('ended', close);
		video.addEventListener('playing', function () { status(''); });
		video.addEventListener('waiting', function () { if (!player) status('Pufferelés…'); });
		video.addEventListener('error', function () {
			if (!player && root.classList.contains('open')) status('Lejátszási hiba (beépített lejátszó)');
		});
	}

	global.MAPlayer = {init: init, play: play, handleKey: handleKey,
		isOpen: function () { return root && root.classList.contains('open'); }};
})(window);
