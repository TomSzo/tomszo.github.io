/*
 * OniAnime közvetítő - Cloudflare Worker (ingyenes csomag elég).
 *
 * A TV böngészőjét az onianime.hu Cloudflare-védelme nem engedi át (végtelen „Nem
 * vagyok robot”). Ez a Worker kérdezi le helyette az onianime.hu /api/ JSON-válaszait,
 * és CORS-fejléccel adja tovább a TV-s appnak. Csak az onianime.hu /api/ címeit kéri
 * le, csak GET-tel (nem nyílt proxy). A videók nem ezen mennek.
 *
 * Telepítés: dash.cloudflare.com -> Workers & Pages -> Create -> Worker („Hello World”)
 * -> Deploy -> Edit code: ennek a fájlnak a teljes tartalmát illeszd be -> Deploy.
 * A kapott cím (pl. https://onianime-relay.<neved>.workers.dev) kell az appba.
 *
 * Opcionális jelszó: Settings -> Variables -> KEY = valami. Ilyenkor az appba a
 * https://onianime-relay.<neved>.workers.dev/<jelszó> címet írd.
 */
const ORIGIN = 'https://onianime.hu';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
	'Chrome/124.0.0.0 Safari/537.36';
const API = /^\/api\/[\w\-\/]+$/;
const CORS = {
	'access-control-allow-origin': '*',
	'access-control-allow-methods': 'GET, OPTIONS',
	'access-control-max-age': '86400'
};

function reply(body, status, extra) {
	return new Response(body, {status: status, headers: Object.assign({}, CORS, extra || {})});
}

export default {
	async fetch(request, env) {
		if (request.method === 'OPTIONS') return reply(null, 204);
		if (request.method !== 'GET') return reply('Csak GET', 405);
		const url = new URL(request.url);
		let path = url.pathname;
		if (env.KEY) {
			const prefix = '/' + env.KEY;
			if (path !== prefix && path.indexOf(prefix + '/') !== 0) return reply('Hibás jelszó', 403);
			path = path.slice(prefix.length) || '/';
		}
		if (path === '/') return reply('OniAnime közvetítő: OK (v2)', 200, {'content-type': 'text/plain; charset=utf-8'});
		if (!API.test(path) || path.indexOf('..') >= 0) return reply('Nem engedélyezett cím', 400);

		// a rész videócímei (parts) tokenesek - azokat nem tároljuk el
		const ttl = path.indexOf('/parts') >= 0 ? 0 : 120;
		const upstream = await fetch(ORIGIN + path + url.search, {
			headers: {
				'user-agent': UA,
				'accept': 'application/json, text/plain, */*',
				'accept-language': 'hu-HU,hu;q=0.9,en;q=0.8',
				'referer': ORIGIN + '/home'
			},
			// csak a sikeres választ tároljuk el (egy átmeneti 403 ne ragadjon be)
			cf: ttl ? {cacheTtlByStatus: {'200-299': ttl, '300-599': 0}, cacheEverything: true} : {cacheTtl: 0}
		});
		const body = await upstream.text();
		return reply(body, upstream.status, {
			'content-type': upstream.headers.get('content-type') || 'application/json',
			'cache-control': ttl && upstream.ok ? 'public, max-age=' + ttl : 'no-store'
		});
	}
};
