/*
 * MagyarAnime (webOS) - háttérszolgáltatás.
 *
 * 1) request: HTTP-kérés a sütivel és a megadott fejlécekkel (a böngészős rész sütit nem
 *    küldhet, és a CORS is tiltaná). Helyi / belső hálózati címet nem kér le.
 * 2) pair (feliratkozás): helyi weboldal a TV-n, ahol a telefonról PIN-kóddal bemásolható
 *    a süti (Cookie-Editor export / cookies.txt / "név=érték; ..."). A süti a feliratkozó
 *    appnak megy vissza; a szolgáltatás nem tárolja.
 * 3) proxy (feliratkozás): helyi továbbító a lejátszónak, amely a videót a kért fejlécekkel
 *    (Referer, Origin, User-Agent) kéri le; a HLS-listák címeit is átírja.
 */
var http = require('http');
var https = require('https');
var os = require('os');
var zlib = require('zlib');
var crypto = require('crypto');
var querystring = require('querystring');
var Service = require('webos-service');
var pkgInfo = require('./package.json');

var service = new Service(pkgInfo.name);

var TIMEOUT = 30000;
var MAX_REDIRECTS = 5;
var MAX_BODY = 16 * 1024 * 1024;
var PORTS = [9711, 9712, 9713, 9714, 9715];
var PAIR_TTL = 10 * 60 * 1000;

// --- 1) kérés ---------------------------------------------------------------
function privateHost(host) {
	host = (host || '').toLowerCase();
	return host === 'localhost' || /^127\./.test(host) || /^10\./.test(host) ||
		/^192\.168\./.test(host) || /^172\.(1[6-9]|2\d|3[01])\./.test(host) ||
		/^169\.254\./.test(host) || host === '::1' || host === '0.0.0.0';
}

function checkUrl(url) {
	var u;
	try {
		u = new URL(url);
	} catch (e) {
		return null;
	}
	if ((u.protocol !== 'https:' && u.protocol !== 'http:') || privateHost(u.hostname)) return null;
	return u;
}

function decode(res, buf, cb) {
	var enc = (res.headers['content-encoding'] || '').toLowerCase();
	if (enc === 'gzip') return zlib.gunzip(buf, cb);
	if (enc === 'deflate') return zlib.inflate(buf, cb);
	if (enc === 'br') return zlib.brotliDecompress(buf, cb);
	cb(null, buf);
}

function cookiesFrom(res) {
	var out = {};
	(res.headers['set-cookie'] || []).forEach(function (line) {
		var first = String(line).split(';')[0];
		var i = first.indexOf('=');
		if (i > 0) out[first.slice(0, i).trim()] = first.slice(i + 1).trim();
	});
	return out;
}

function doRequest(opts, redirects, done) {
	var u = checkUrl(opts.url);
	if (!u) return done(new Error('Nem engedélyezett cím: ' + opts.url));
	var h = {};
	Object.keys(opts.headers || {}).forEach(function (k) { h[k] = opts.headers[k]; });
	h['Accept-Encoding'] = 'gzip, deflate, br';
	if (opts.cookie) h.Cookie = opts.cookie;
	var body = null;
	var method = (opts.method || 'GET').toUpperCase();
	if (method === 'POST') {
		body = Buffer.from(querystring.stringify(opts.form || {}), 'utf8');
		h['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
		h['Content-Length'] = body.length;
	}
	var lib = u.protocol === 'https:' ? https : http;
	var req = lib.request(u, {method: method, headers: h, timeout: TIMEOUT}, function (res) {
		var setCookies = cookiesFrom(res);
		if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location &&
				redirects < MAX_REDIRECTS) {
			res.resume();
			var next = {url: new URL(res.headers.location, u).toString(), headers: opts.headers,
				cookie: opts.cookie, method: res.statusCode === 307 || res.statusCode === 308 ?
					method : 'GET', form: opts.form};
			return doRequest(next, redirects + 1, function (err, r) {
				if (r) Object.keys(setCookies).forEach(function (k) {
					if (!(k in r.setCookies)) r.setCookies[k] = setCookies[k];
				});
				done(err, r);
			});
		}
		var chunks = [];
		var size = 0;
		res.on('data', function (c) {
			size += c.length;
			if (size > MAX_BODY) return req.destroy(new Error('Túl nagy válasz'));
			chunks.push(c);
		});
		res.on('end', function () {
			decode(res, Buffer.concat(chunks), function (err, buf) {
				if (err) return done(err);
				done(null, {status: res.statusCode, contentType: res.headers['content-type'] || '',
					cfMitigated: res.headers['cf-mitigated'] || '', url: u.toString(),
					setCookies: setCookies, body: buf.toString('utf8')});
			});
		});
		res.on('error', done);
	});
	req.on('timeout', function () { req.destroy(new Error('Időtúllépés')); });
	req.on('error', done);
	if (body) req.write(body);
	req.end();
}

service.register('request', function (message) {
	doRequest(message.payload || {}, 0, function (err, result) {
		if (err) {
			message.respond({returnValue: false, errorText: String(err.message || err)});
			return;
		}
		result.returnValue = true;
		message.respond(result);
	});
});

// --- helyi webszerver (párosítás + továbbító) ---------------------------------
var server = null;
var port = 0;
var pairing = null;           // {pin, message, until}
var proxies = {};             // id -> {headers}
var proxyOf = {};             // feliratkozás azonosítója -> továbbító id

function subKey(message) {
	return message && (message.uniqueToken || message.token || '');
}

function lanIp() {
	var nets = os.networkInterfaces();
	var names = Object.keys(nets);
	for (var i = 0; i < names.length; i++) {
		var list = nets[names[i]] || [];
		for (var j = 0; j < list.length; j++) {
			var a = list[j];
			if ((a.family === 'IPv4' || a.family === 4) && !a.internal) return a.address;
		}
	}
	return '';
}

function ensureServer(cb) {
	if (server) return cb(null);
	var i = 0;
	var tryPort = function () {
		if (i >= PORTS.length) return cb(new Error('Nem nyitható port a TV-n'));
		var s = http.createServer(handle);
		s.once('error', function () {
			i++;
			tryPort();
		});
		s.listen(PORTS[i], '0.0.0.0', function () {
			server = s;
			port = PORTS[i];
			cb(null);
		});
	};
	tryPort();
}

function maybeStop() {
	if (server && !pairing && !Object.keys(proxies).length) {
		server.close();
		server = null;
		port = 0;
	}
}

function esc(s) {
	return String(s).replace(/[&<>"]/g, function (c) {
		return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c];
	});
}

function page(res, title, inner) {
	res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'});
	res.end('<!doctype html><html lang="hu"><head><meta charset="utf-8">' +
		'<meta name="viewport" content="width=device-width,initial-scale=1">' +
		'<title>' + esc(title) + '</title><style>' +
		'body{font-family:system-ui,sans-serif;background:#0b0b10;color:#f2f2f5;margin:0;padding:24px;max-width:640px}' +
		'h1{font-size:22px}p{color:#a9a9b6;line-height:1.5}' +
		'input,textarea{width:100%;box-sizing:border-box;font:inherit;padding:12px;border-radius:10px;' +
		'border:1px solid #33333d;background:#16161d;color:#fff;margin:6px 0 16px}' +
		'textarea{height:220px;font-family:monospace;font-size:13px}' +
		'button{font:inherit;font-weight:700;padding:14px 22px;border:0;border-radius:10px;' +
		'background:#ff4f8b;color:#fff;width:100%}.ok{color:#5be08a}.err{color:#ff7a7a}' +
		'</style></head><body>' + inner + '</body></html>');
}

function pairForm(res, note) {
	page(res, 'MagyarAnime – süti', '<h1>MagyarAnime – süti a TV-nek</h1>' +
		(note || '') +
		'<p>Másold be a Cookie-Editor exportot (JSON), egy cookies.txt tartalmát vagy ' +
		'a „PHPSESSID=…; loginkey=…” szöveget. A PIN-kódot a TV mutatja.</p>' +
		'<form method="post"><label>PIN-kód</label>' +
		'<input name="pin" inputmode="numeric" autocomplete="off" maxlength="4" required>' +
		'<label>Süti</label><textarea name="cookie" required></textarea>' +
		'<button type="submit">Küldés a TV-nek</button></form>');
}

function handlePair(req, res) {
	if (!pairing || Date.now() > pairing.until) {
		return page(res, 'MagyarAnime', '<h1>Nincs aktív párosítás</h1>' +
			'<p>A TV-n: MagyarAnime → Beállítások → Süti telefonról.</p>');
	}
	if (req.method !== 'POST') return pairForm(res);
	var chunks = [];
	var size = 0;
	req.on('data', function (c) {
		size += c.length;
		if (size < 256 * 1024) chunks.push(c);
	});
	req.on('end', function () {
		var form = querystring.parse(Buffer.concat(chunks).toString('utf8'));
		if (!pairing) return pairForm(res);
		if (String(form.pin || '').trim() !== pairing.pin) {
			pairing.tries = (pairing.tries || 0) + 1;
			if (pairing.tries >= 5) {
				pairing.message.respond({returnValue: true, failed: true,
					errorText: 'Túl sok hibás PIN - kezdd újra'});
				pairing = null;
				maybeStop();
				return page(res, 'MagyarAnime', '<h1 class="err">Túl sok hibás PIN</h1>');
			}
			return pairForm(res, '<p class="err">Hibás PIN-kód.</p>');
		}
		var text = String(form.cookie || '').trim();
		if (!text) return pairForm(res, '<p class="err">Üres süti.</p>');
		pairing.message.respond({returnValue: true, cookieText: text});
		pairing = null;
		page(res, 'MagyarAnime', '<h1 class="ok">Elküldve a TV-nek ✓</h1>' +
			'<p>Most már bezárhatod ezt az oldalt.</p>');
		setTimeout(maybeStop, 1000);
	});
}

service.register('pair', function (message) {
	ensureServer(function (err) {
		if (err) {
			message.respond({returnValue: false, errorText: err.message});
			return;
		}
		var pin = String(1000 + crypto.randomInt(9000));
		pairing = {pin: pin, message: message, until: Date.now() + PAIR_TTL};
		var ip = lanIp();
		message.respond({returnValue: true, subscribed: true, pin: pin, port: port,
			url: ip ? 'http://' + ip + ':' + port + '/' : ''});
	});
}, function () {
	pairing = null;
	maybeStop();
});

// --- 3) továbbító ---------------------------------------------------------------------
function b64(s) {
	return Buffer.from(s, 'utf8').toString('base64').replace(/\+/g, '-').replace(/\//g, '_')
		.replace(/=+$/, '');
}

function unb64(s) {
	return Buffer.from(s.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8');
}

function proxied(id, url) {
	return 'http://127.0.0.1:' + port + '/p/' + id + '/' + b64(url);
}

function rewritePlaylist(id, text, base) {
	return text.split(/\r?\n/).map(function (line) {
		var t = line.trim();
		if (!t) return line;
		if (t.charAt(0) === '#') {
			// URI="..." attribútumok (kulcs, alternatív hang / felirat, térkép)
			return line.replace(/URI="([^"]+)"/g, function (m, uri) {
				return 'URI="' + proxied(id, new URL(uri, base).toString()) + '"';
			});
		}
		return proxied(id, new URL(t, base).toString());
	}).join('\n');
}

function handleProxy(req, res, id, encoded) {
	var p = proxies[id];
	var target;
	try {
		target = unb64(encoded);
	} catch (e) {
		target = '';
	}
	var u = p && checkUrl(target);
	if (!u) {
		res.writeHead(404);
		return res.end();
	}
	var h = {};
	Object.keys(p.headers || {}).forEach(function (k) { h[k] = p.headers[k]; });
	if (req.headers.range) h.Range = req.headers.range;
	var lib = u.protocol === 'https:' ? https : http;
	var up = lib.get(u, {headers: h, timeout: TIMEOUT}, function (ur) {
		if (ur.statusCode >= 300 && ur.statusCode < 400 && ur.headers.location) {
			ur.resume();
			res.writeHead(302, {Location: proxied(id, new URL(ur.headers.location, u).toString()),
				'Access-Control-Allow-Origin': '*'});
			return res.end();
		}
		var ct = ur.headers['content-type'] || '';
		var isList = /mpegurl/i.test(ct) || /\.m3u8(\?|$)/i.test(u.pathname + u.search);
		if (isList) {
			var chunks = [];
			ur.on('data', function (c) { chunks.push(c); });
			ur.on('end', function () {
				var text = rewritePlaylist(id, Buffer.concat(chunks).toString('utf8'), u.toString());
				res.writeHead(ur.statusCode, {'Content-Type': 'application/vnd.apple.mpegurl',
					'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store'});
				res.end(text);
			});
			return;
		}
		var out = {'Access-Control-Allow-Origin': '*'};
		['content-type', 'content-length', 'content-range', 'accept-ranges'].forEach(function (k) {
			if (ur.headers[k]) out[k] = ur.headers[k];
		});
		res.writeHead(ur.statusCode, out);
		ur.pipe(res);
	});
	up.on('timeout', function () { up.destroy(new Error('Időtúllépés')); });
	up.on('error', function () {
		if (!res.headersSent) res.writeHead(502);
		res.end();
	});
	req.on('close', function () { up.destroy(); });
}

function handle(req, res) {
	var m = /^\/p\/([a-f0-9]+)\/([A-Za-z0-9_-]+)$/.exec(req.url.split('?')[0]);
	if (m) return handleProxy(req, res, m[1], m[2]);
	if (req.url === '/' || req.url.indexOf('/?') === 0) return handlePair(req, res);
	res.writeHead(404);
	res.end();
}

service.register('proxy', function (message) {
	var p = message.payload || {};
	if (!checkUrl(p.url)) {
		message.respond({returnValue: false, errorText: 'Hibás cím'});
		return;
	}
	ensureServer(function (err) {
		if (err) {
			message.respond({returnValue: false, errorText: err.message});
			return;
		}
		var id = crypto.randomBytes(8).toString('hex');
		proxies[id] = {headers: p.headers || {}};
		proxyOf[subKey(message)] = id;
		message.respond({returnValue: true, subscribed: true, url: proxied(id, p.url)});
	});
}, function (message) {
	var key = subKey(message);
	if (proxyOf[key]) {
		delete proxies[proxyOf[key]];
		delete proxyOf[key];
	}
	maybeStop();
});
