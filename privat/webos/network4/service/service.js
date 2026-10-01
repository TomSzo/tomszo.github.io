/*
 * Network4 (webOS) - háttérszolgáltatás.
 *
 * A böngészős rész nem tud tetszőleges fejlécet (User-Agent, Authorization) küldeni és
 * a CORS is korlátozza, ezért a Network4 felé menő kéréseket ez a szolgáltatás
 * (Node.js) végzi. Csak a Network4 címeit engedi (nem nyílt proxy).
 *
 * Hívás: luna://hu.tomszo.network4.service/get  {url, headers}
 *   -> {returnValue, status, contentType, cfMitigated, body}
 */
var https = require('https');
var zlib = require('zlib');
var Service = require('webos-service');
var pkgInfo = require('./package.json');

var service = new Service(pkgInfo.name);

var ALLOWED_HOSTS = ['net4plus.network4.hu', 'www.network4.hu'];
var TIMEOUT = 25000;
var MAX_REDIRECTS = 3;
var MAX_BODY = 8 * 1024 * 1024;

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

function get(url, headers, redirects, done) {
	if (!allowed(url)) return done(new Error('Nem engedélyezett cím: ' + url));
	var h = {};
	Object.keys(headers || {}).forEach(function (k) { h[k] = headers[k]; });
	h['Accept-Encoding'] = 'gzip, deflate, br';
	var req = https.get(url, {headers: h, timeout: TIMEOUT}, function (res) {
		if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location &&
				redirects < MAX_REDIRECTS) {
			res.resume();
			return get(new URL(res.headers.location, url).toString(), headers, redirects + 1, done);
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
					cfMitigated: res.headers['cf-mitigated'] || '',
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
	get(p.url, p.headers, 0, function (err, result) {
		if (err) {
			message.respond({returnValue: false, errorText: String(err.message || err)});
			return;
		}
		result.returnValue = true;
		message.respond(result);
	});
});
