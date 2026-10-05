/*
 * OniAnime közvetítő - Cloudflare Worker (ingyenes csomag elég).
 *
 * A TV böngészőjét az onianime.hu Cloudflare-védelme nem engedi át (végtelen „Nem
 * vagyok robot”). Ez a Worker kérdezi le helyette az onianime.hu /api/ JSON-válaszait,
 * és CORS-fejléccel adja tovább a TV-s appnak. Csak az onianime.hu /api/ címeit kéri
 * le (nem nyílt proxy): GET-tel bármelyiket, POST / DELETE-tel csak a bejelentkezést,
 * a Folytatás mentését / törlését és a menetrend elérhetőség-ellenőrzését. A videók
 * nem ezen mennek.
 *
 * Fiók: a TV-s app a munkamenet-sütit az `x-oni-session` fejlécben küldi (a Worker ezt
 * Cookie-ként adja tovább), az onianime.hu által beállított sütiket pedig az
 * `x-oni-set-cookie` fejlécben kapja vissza. A Worker semmit nem tárol; a személyes
 * válaszok nem kerülnek a gyorsítótárba.
 *
 * Telepítés: a README szerint (GitHubról, Workers Builds-szel, vagy a kódszerkesztőbe
 * beillesztve). Opcionális jelszó: Settings -> Variables -> KEY; ilyenkor az appba a
 * https://onianime-relay.<neved>.workers.dev/<jelszó> címet kell írni.
 */
const ORIGIN = 'https://onianime.hu';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
	'Chrome/124.0.0.0 Safari/537.36';
const API = /^\/api\/[\w\-\/]+$/;
// GET-en kívül csak ezek
const WRITE = {
	POST: [/^\/api\/users\/login$/, /^\/api\/users\/logout$/, /^\/api\/continue$/,
		/^\/api\/animes\/check-relations$/],
	DELETE: [/^\/api\/continue$/]
};
// személyes adatok - soha nem kerülnek a gyorsítótárba
const PRIVATE = /^\/api\/(continue|users|calendar|playlists|anime\/animelist)/;
const CORS = {
	'access-control-allow-origin': '*',
	'access-control-allow-methods': 'GET, POST, DELETE, OPTIONS',
	'access-control-allow-headers': 'content-type, x-oni-session',
	'access-control-expose-headers': 'x-oni-set-cookie',
	'access-control-max-age': '86400'
};
const MAX_BODY = 64 * 1024;

function reply(body, status, extra) {
	return new Response(body, {status: status, headers: Object.assign({}, CORS, extra || {})});
}

// a Set-Cookie fejlécekből csak a név=érték párok (a TV-s app tárolja őket)
function cookiePairs(headers) {
	let list = [];
	if (typeof headers.getSetCookie === 'function') list = headers.getSetCookie();
	else if (headers.get('set-cookie')) list = headers.get('set-cookie').split(/,(?=\s*[^;,\s]+=)/);
	return list.map(c => c.split(';')[0].trim()).filter(c => c.indexOf('=') > 0).join('; ');
}

export default {
	async fetch(request, env) {
		if (request.method === 'OPTIONS') return reply(null, 204);
		const url = new URL(request.url);
		let path = url.pathname;
		if (env.KEY) {
			const prefix = '/' + env.KEY;
			if (path !== prefix && path.indexOf(prefix + '/') !== 0) return reply('Hibás jelszó', 403);
			path = path.slice(prefix.length) || '/';
		}
		if (path === '/') return reply('OniAnime közvetítő: OK (v3)', 200, {'content-type': 'text/plain; charset=utf-8'});
		if (!API.test(path) || path.indexOf('..') >= 0) return reply('Nem engedélyezett cím', 400);
		const method = request.method;
		if (method !== 'GET' && !(WRITE[method] || []).some(re => re.test(path))) {
			return reply('Nem engedélyezett kérés', 405);
		}

		const session = request.headers.get('x-oni-session') || '';
		const headers = {
			'user-agent': UA,
			'accept': 'application/json, text/plain, */*',
			'accept-language': 'hu-HU,hu;q=0.9,en;q=0.8',
			'referer': ORIGIN + '/home'
		};
		if (session) headers.cookie = session;
		let body;
		if (method !== 'GET') {
			body = await request.text();
			if (body.length > MAX_BODY) return reply('Túl nagy kérés', 413);
			headers['content-type'] = 'application/json';
			headers.origin = ORIGIN;
		}

		// a rész videócímei (parts) tokenesek, a személyes adatok egyéniek - ezeket nem
		// tároljuk; a többit 2 percig (csak a sikeres választ)
		const ttl = method !== 'GET' || session || PRIVATE.test(path) || path.indexOf('/parts') >= 0 ? 0 : 120;
		const upstream = await fetch(ORIGIN + path + url.search, {
			method: method,
			headers: headers,
			body: body,
			redirect: 'manual',
			cf: ttl ? {cacheTtlByStatus: {'200-299': ttl, '300-599': 0}, cacheEverything: true} : {cacheTtl: 0}
		});
		const text = await upstream.text();
		const extra = {
			'content-type': upstream.headers.get('content-type') || 'application/json',
			'cache-control': ttl && upstream.ok ? 'public, max-age=' + ttl : 'no-store'
		};
		const set = cookiePairs(upstream.headers);
		if (set) extra['x-oni-set-cookie'] = set;
		return reply(text, upstream.status, extra);
	}
};
