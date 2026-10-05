/*
 * OniAnime (webOS) - háttérszolgáltatás.
 *
 * Az onianime.hu API-ja nem küld CORS-fejlécet, ezért az app a JSON-válaszokat ezen a
 * szolgáltatáson (Node.js) át kéri le. Csak az onianime.hu /api/ címeit engedi
 * (nem nyílt proxy), csak GET-tel, belépés / süti nélkül.
 *
 * Hívás: luna://hu.tomszo.onianime.service/get  {path: '/api/animes/popular'}
 *   -> {returnValue, status, contentType, body}
 *
 * A videók (indavideo MP4) közvetlenül, a <video> elemből mennek - azokhoz nem kell.
 */
var https = require('https');
var zlib = require('zlib');
var Service = require('webos-service');
var pkgInfo = require('./package.json');

var service = new Service(pkgInfo.name);

var BASE = 'https://onianime.hu';
var UA = 'Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) ' +
	'Chrome/108.0.0.0 Safari/537.36';
var TIMEOUT = 25000;
var MAX_BODY = 8 * 1024 * 1024;

function allowed(path) {
	return typeof path === 'string' && /^\/api\/[\w\-\/]+(\?[\w\-.,%=&+'()!*~]*)?$/.test(path) &&
		path.indexOf('..') < 0;
}

function decode(res, buf, cb) {
	var enc = (res.headers['content-encoding'] || '').toLowerCase();
	if (enc === 'gzip') return zlib.gunzip(buf, cb);
	if (enc === 'deflate') return zlib.inflate(buf, cb);
	if (enc === 'br' && zlib.brotliDecompress) return zlib.brotliDecompress(buf, cb);
	cb(null, buf);
}

function get(path, done) {
	if (!allowed(path)) return done(new Error('Nem engedélyezett cím: ' + path));
	var finished = false;
	function finish(err, res) {
		if (finished) return;
		finished = true;
		done(err, res);
	}
	var req = https.get(BASE + path, {
		headers: {
			'User-Agent': UA,
			'Accept': 'application/json',
			'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.8',
			'Accept-Encoding': 'gzip, deflate' + (zlib.brotliDecompress ? ', br' : ''),
			'Referer': BASE + '/home'
		},
		timeout: TIMEOUT
	}, function (res) {
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
				if (err) return finish(err);
				finish(null, {
					status: res.statusCode,
					contentType: res.headers['content-type'] || '',
					body: body.toString('utf8')
				});
			});
		});
		res.on('error', finish);
	});
	req.on('timeout', function () { req.destroy(new Error('Időtúllépés')); });
	req.on('error', finish);
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
