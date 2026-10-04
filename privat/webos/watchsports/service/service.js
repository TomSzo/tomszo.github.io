/*
 * WatchSports (webOS) - háttérszolgáltatás.
 *
 * A watchsports.su nem küld CORS-fejlécet, ezért az app a műsor- és meccsoldalak HTML-jét
 * ezen a szolgáltatáson (Node.js) át kéri le. Csak a watchsports.su címeit engedi
 * (nem nyílt proxy).
 *
 * Hívás: luna://hu.tomszo.watchsports.service/get  {url}
 *   -> {returnValue, status, contentType, body}
 */
var https = require('https');
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
