/*
 * WatchSports (webOS) - háttérszolgáltatás.
 *
 * A watchsports.su nem küld CORS-fejlécet, ezért az app a műsor- és meccsoldalak HTML-jét
 * ezen a szolgáltatáson (Node.js) át kéri le. Csak a watchsports.su címeit engedi
 * (nem nyílt proxy).
 *
 * Hívás: luna://hu.tomszo.watchsports.service/get  {url}
 *   -> {returnValue, status, contentType, body}
 *
 * Elérhetőség-ellenőrzés (adásoldalak, bármely nyilvános cím):
 *        luna://hu.tomszo.watchsports.service/probe  {url}
 *   -> {returnValue, ok, status, code, finalUrl}
 * Csak a válasz fejlécéig megy (törzset nem ad vissza). Ha a szolgáltató / DNS tiltja az
 * oldalt, a TV böngészője -102 / -105 / -107 hibaoldalt mutatna - ezt előre kiszűrjük.
 * Belső hálózati címet nem kér le.
 */
var http = require('http');
var https = require('https');
var dns = require('dns');
var net = require('net');
var zlib = require('zlib');
var Service = require('webos-service');
var pkgInfo = require('./package.json');

var service = new Service(pkgInfo.name);

var ALLOWED_HOSTS = ['watchsports.su'];
var UA = 'Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) ' +
	'Chrome/108.0.0.0 Safari/537.36';
var TIMEOUT = 25000;
var MAX_REDIRECTS = 3;
var MAX_BODY = 4 * 1024 * 1024;

function allowed(url) {
	try {
		var u = new URL(url);
		return u.protocol === 'https:' && ALLOWED_HOSTS.indexOf(u.hostname) >= 0;
	} catch (e) {
		return false;
	}
}

function decode(res, buf, cb) {
	var enc = (res.headers['content-encoding'] || '').toLowerCase();
	if (enc === 'gzip') return zlib.gunzip(buf, cb);
	if (enc === 'deflate') return zlib.inflate(buf, cb);
	if (enc === 'br') return zlib.brotliDecompress(buf, cb);
	cb(null, buf);
}

function get(url, redirects, done) {
	if (!allowed(url)) return done(new Error('Nem engedélyezett cím: ' + url));
	var headers = {
		'User-Agent': UA,
		'Accept': 'text/html,application/xhtml+xml',
		'Accept-Language': 'en-US,en;q=0.9',
		'Accept-Encoding': 'gzip, deflate, br'
	};
	var req = https.get(url, {headers: headers, timeout: TIMEOUT}, function (res) {
		if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location &&
				redirects < MAX_REDIRECTS) {
			res.resume();
			return get(new URL(res.headers.location, url).toString(), redirects + 1, done);
		}
		var chunks = [];
		var size = 0;
		res.on('data', function (c) {
			size += c.length;
			if (size > MAX_BODY) {
				req.destroy(new Error('Túl nagy válasz'));
				return;
			}
			chunks.push(c);
		});
		res.on('end', function () {
			decode(res, Buffer.concat(chunks), function (err, body) {
				if (err) return done(err);
				done(null, {
					status: res.statusCode,
					contentType: res.headers['content-type'] || '',
					body: body.toString('utf8')
				});
			});
		});
		res.on('error', done);
	});
	req.on('timeout', function () { req.destroy(new Error('Időtúllépés')); });
	req.on('error', done);
}

var PROBE_TIMEOUT = 8000;

function privateIP(ip) {
	if (net.isIPv6(ip)) {
		var v = ip.toLowerCase();
		if (v.indexOf('::ffff:') === 0) return privateIP(v.slice(7));
		return v === '::1' || v === '::' || /^f[cd]/.test(v) || /^fe[89ab]/.test(v);
	}
	var p = ip.split('.').map(Number);
	return p[0] === 10 || p[0] === 127 || p[0] === 0 || (p[0] === 169 && p[1] === 254) ||
		(p[0] === 172 && p[1] >= 16 && p[1] <= 31) || (p[0] === 192 && p[1] === 168) ||
		(p[0] === 100 && p[1] >= 64 && p[1] <= 127) || p[0] >= 224;
}

// DNS-feloldás, de belső címre nem enged
function safeLookup(host, opts, cb) {
	if (typeof opts === 'function') { cb = opts; opts = {}; }
	opts = opts || {};
	// az újabb Node {all: true}-val hív (címlistát vár), a régebbi egyetlen címet
	dns.lookup(host, {family: opts.family || 0, all: true}, function (err, list) {
		if (err) return cb(err);
		if (!list.length || list.some(function (a) { return privateIP(a.address); })) {
			var e = new Error('Belső hálózati cím');
			e.code = 'EPRIVATE';
			return cb(e);
		}
		if (opts.all) return cb(null, list);
		cb(null, list[0].address, list[0].family);
	});
}

function probe(url, redirects, done) {
	var u;
	try { u = new URL(url); } catch (e) { return done(null, {ok: false, code: 'EBADURL'}); }
	if (u.protocol !== 'https:' && u.protocol !== 'http:') return done(null, {ok: false, code: 'EBADURL'});
	if (net.isIP(u.hostname.replace(/^\[|\]$/g, '')) || /^localhost$/i.test(u.hostname)) {
		return done(null, {ok: false, code: 'EPRIVATE'});
	}
	var finished = false;
	function finish(r) {
		if (finished) return;
		finished = true;
		r.finalUrl = r.finalUrl || url;
		done(null, r);
	}
	var mod = u.protocol === 'https:' ? https : http;
	var req = mod.get(url, {
		headers: {'User-Agent': UA, 'Accept': 'text/html,*/*', 'Accept-Language': 'en-US,en;q=0.9'},
		timeout: PROBE_TIMEOUT,
		lookup: safeLookup
	}, function (res) {
		res.resume();
		req.destroy();
		var loc = res.headers.location;
		if (res.statusCode >= 300 && res.statusCode < 400 && loc && redirects < MAX_REDIRECTS + 2) {
			finished = true;
			return probe(new URL(loc, url).toString(), redirects + 1, done);
		}
		// bármilyen HTTP-válasz (a Cloudflare 403-as kihívása is) azt jelenti, hogy az oldal
		// elérhető - a böngésző a kihívást meg tudja oldani
		finish({ok: true, status: res.statusCode, finalUrl: url});
	});
	req.on('timeout', function () {
		var e = new Error('Időtúllépés');
		e.code = 'ETIMEDOUT';
		req.destroy(e);
	});
	req.on('error', function (err) {
		finish({ok: false, code: err.code || 'ERROR', error: String(err.message || err), finalUrl: url});
	});
}

service.register('probe', function (message) {
	var p = message.payload || {};
	probe(p.url, 0, function (err, result) {
		result.returnValue = true;
		message.respond(result);
	});
});

service.register('get', function (message) {
	var p = message.payload || {};
	get(p.url, 0, function (err, result) {
		if (err) {
			message.respond({returnValue: false, errorText: String(err.message || err)});
			return;
		}
		result.returnValue = true;
		message.respond(result);
	});
});
