/*
 * OniAnime (webOS) - háttérszolgáltatás.
 *
 * Az onianime.hu API-ja nem küld CORS-fejlécet, ezért az app a JSON-válaszokat ezen a
 * szolgáltatáson (Node.js) át kéri le. Csak az onianime.hu /api/ címeit engedi
 * (nem nyílt proxy), csak GET-tel, belépés / süti nélkül.
 *
 * Hívás: luna://hu.tomszo.onianime.service/get  {path: '/api/animes/popular'}
 *   -> {returnValue, status, contentType, body, mode, cloudflare, tried}
 *
 * A videók (indavideo MP4) közvetlenül, a <video> elemből mennek - azokhoz nem kell.
 */
var https = require('https');
var zlib = require('zlib');
var http2 = null;
try { http2 = require('http2'); } catch (e) {}
var Service = require('webos-service');
var pkgInfo = require('./package.json');

var service = new Service(pkgInfo.name);

var BASE = 'https://onianime.hu';
var HOST = 'onianime.hu';
var UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
	'Chrome/124.0.0.0 Safari/537.36';
var TIMEOUT = 20000;
var MAX_BODY = 8 * 1024 * 1024;

// A Cloudflare a nem böngészőből jövő kéréseket (a TV régebbi Node.js-ének TLS-
// ujjlenyomatát) 403-mal elutasíthatja. Ezért böngészőszerűen kérdezünk: Chrome-
// sorrendű titkosítás, HTTP/2, böngészőfejlécek - és ha egy mód 403-at kap, a
// következővel próbáljuk.
var CHROME_CIPHERS = [
	'TLS_AES_128_GCM_SHA256', 'TLS_AES_256_GCM_SHA384', 'TLS_CHACHA20_POLY1305_SHA256',
	'ECDHE-ECDSA-AES128-GCM-SHA256', 'ECDHE-RSA-AES128-GCM-SHA256', 'ECDHE-ECDSA-AES256-GCM-SHA384',
	'ECDHE-RSA-AES256-GCM-SHA384', 'ECDHE-ECDSA-CHACHA20-POLY1305', 'ECDHE-RSA-CHACHA20-POLY1305',
	'ECDHE-RSA-AES128-SHA', 'ECDHE-RSA-AES256-SHA', 'AES128-GCM-SHA256', 'AES256-GCM-SHA384',
	'AES128-SHA', 'AES256-SHA'
].join(':');
var CHROME_SIGALGS = 'ecdsa_secp256r1_sha256:rsa_pss_rsae_sha256:rsa_pkcs1_sha256:' +
	'ecdsa_secp384r1_sha384:rsa_pss_rsae_sha384:rsa_pkcs1_sha384:rsa_pss_rsae_sha512:rsa_pkcs1_sha512';

var lastGood = 0;   // az utoljára működött mód indexe

function allowed(path) {
	return typeof path === 'string' && /^\/api\/[\w\-\/]+(\?[\w\-.,%=&+'()!*~]*)?$/.test(path) &&
		path.split('?')[0].indexOf('..') < 0;
}

function browserHeaders(path) {
	return {
		'user-agent': UA,
		'accept': 'application/json, text/plain, */*',
		'accept-language': 'hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7',
		'accept-encoding': 'gzip, deflate' + (zlib.brotliDecompress ? ', br' : ''),
		'referer': BASE + (path.indexOf('/api/anime/') === 0 ? '/info/' + path.split('/')[3] : '/home'),
		'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
		'sec-ch-ua-mobile': '?0',
		'sec-ch-ua-platform': '"Windows"',
		'sec-fetch-dest': 'empty',
		'sec-fetch-mode': 'cors',
		'sec-fetch-site': 'same-origin'
	};
}

function tlsOpts(chrome) {
	var o = {servername: HOST};
	if (chrome) {
		o.ciphers = CHROME_CIPHERS;
		o.ecdhCurve = 'X25519:prime256v1:secp384r1';
		o.sigalgs = CHROME_SIGALGS;
		o.honorCipherOrder = false;
	}
	return o;
}

function decode(enc, buf, cb) {
	enc = (enc || '').toLowerCase();
	if (enc === 'gzip') return zlib.gunzip(buf, cb);
	if (enc === 'deflate') return zlib.inflate(buf, cb);
	if (enc === 'br' && zlib.brotliDecompress) return zlib.brotliDecompress(buf, cb);
	cb(null, buf);
}

function finishBody(headers, status, chunks, done) {
	decode(headers['content-encoding'], Buffer.concat(chunks), function (err, body) {
		if (err) return done(err);
		done(null, {
			status: status,
			contentType: headers['content-type'] || '',
			cloudflare: status === 403 && (!!headers['cf-mitigated'] ||
				/cloudflare|cf-chl|just a moment/i.test(body.toString('utf8', 0, 4000))),
			body: body.toString('utf8')
		});
	});
}

// HTTP/1.1 (https modul)
function getH1(path, chrome, done) {
	var finished = false;
	function finish(err, res) { if (!finished) { finished = true; done(err, res); } }
	var opts = tlsOpts(chrome);
	var h = browserHeaders(path);
	delete h['sec-ch-ua']; delete h['sec-ch-ua-mobile']; delete h['sec-ch-ua-platform'];
	opts.headers = h;
	opts.timeout = TIMEOUT;
	opts.agent = false;
	var req;
	try {
		req = https.get(BASE + path, opts, function (res) {
			var chunks = [], size = 0;
			res.on('data', function (c) {
				size += c.length;
				if (size > MAX_BODY) { req.destroy(new Error('Túl nagy válasz')); return; }
				chunks.push(c);
			});
			res.on('end', function () { finishBody(res.headers, res.statusCode, chunks, finish); });
			res.on('error', finish);
		});
	} catch (e) {
		return finish(e);   // pl. a régi Node nem ismeri a sigalgs opciót
	}
	req.on('timeout', function () { req.destroy(new Error('Időtúllépés')); });
	req.on('error', finish);
}

// HTTP/2 (mint a böngésző)
function getH2(path, done) {
	if (!http2) return done(new Error('nincs http2'));
	var finished = false;
	var client;
	function finish(err, res) {
		if (finished) return;
		finished = true;
		try { client.close(); } catch (e) {}
		done(err, res);
	}
	var opts = tlsOpts(true);
	opts.settings = {headerTableSize: 65536, enablePush: false, initialWindowSize: 6291456, maxHeaderListSize: 262144};
	try {
		client = http2.connect(BASE, opts);
	} catch (e) {
		return done(e);
	}
	client.on('error', finish);
	client.setTimeout(TIMEOUT, function () { finish(new Error('Időtúllépés')); });
	var h = browserHeaders(path);
	h[':method'] = 'GET';
	h[':authority'] = HOST;
	h[':scheme'] = 'https';
	h[':path'] = path;
	var req = client.request(h);
	var status = 0, headers = {}, chunks = [], size = 0;
	req.on('response', function (hd) { headers = hd; status = hd[':status']; });
	req.on('data', function (c) {
		size += c.length;
		if (size > MAX_BODY) { finish(new Error('Túl nagy válasz')); return; }
		chunks.push(c);
	});
	req.on('end', function () { finishBody(headers, status, chunks, finish); });
	req.on('error', finish);
	req.end();
}

var MODES = [
	{name: 'h2', run: function (p, cb) { getH2(p, cb); }},
	{name: 'h1-chrome', run: function (p, cb) { getH1(p, true, cb); }},
	{name: 'h1', run: function (p, cb) { getH1(p, false, cb); }}
];

function get(path, done) {
	if (!allowed(path)) return done(new Error('Nem engedélyezett cím: ' + path));
	var order = [lastGood];
	for (var i = 0; i < MODES.length; i++) if (i !== lastGood) order.push(i);
	var tried = [];
	var lastRes = null, lastErr = null;
	(function next(k) {
		if (k >= order.length) {
			if (lastRes) { lastRes.tried = tried.join(', '); return done(null, lastRes); }
			return done(lastErr || new Error('Sikertelen kérés'));
		}
		var m = MODES[order[k]];
		m.run(path, function (err, res) {
			if (!err && res.status >= 200 && res.status < 400) {
				lastGood = order[k];
				res.mode = m.name;
				return done(null, res);
			}
			tried.push(m.name + ': ' + (err ? String(err.message || err) : res.status));
			if (res) lastRes = res;
			else lastErr = err;
			next(k + 1);
		});
	})(0);
}

service.register('get', function (message) {
	var p = message.payload || {};
	get(p.path, function (err, result) {
		if (err) {
			message.respond({returnValue: false, errorText: String(err.message || err)});
			return;
		}
		result.returnValue = true;
		message.respond(result);
	});
});
