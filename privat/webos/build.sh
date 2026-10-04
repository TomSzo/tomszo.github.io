#!/bin/sh
# TomSzo webOS-alkalmazások (Network4, MagyarAnime, Streamed Sport, WatchSports, Acestrims, StreamSports99) - IPK-k építése és a Homebrew
# Channel-tároló frissítése.
#
# Kell hozzá: Node.js és a webOS CLI (npm install -g @webos-tools/cli), python3.
# Használat:  sh privat/webos/build.sh                (mindkét app)
#             sh privat/webos/build.sh magyaranime    (csak a megadott; a tároló mindig
#                                                      az összes meglévő IPK-ból készül)
#
# Eredmény (a GitHub Pages kiszolgálja):
#   privat/webos/<app-id>_<verzió>_all.ipk       - telepíthető csomagok
#   privat/webos/<app-id>.manifest.json          - Homebrew Channel manifestek
#   privat/webos/apps.json                       - Homebrew Channel tároló
set -eu

cd "$(dirname "$0")"
APPS="network4 magyaranime streamed watchsports acestrims"
# a streamsports99 IPK-ja nincs a tárolóban; helyi építés: sh build.sh streamsports99
BUILD=${*:-$APPS}

for name in $BUILD; do
	APP=$name/app
	SVC=$name/service
	ID=$(python3 -c "import json;print(json.load(open('$APP/appinfo.json'))['id'])")
	VERSION=$(python3 -c "import json;print(json.load(open('$APP/appinfo.json'))['version'])")
	rm -f "${ID}"_*.ipk
	if [ -d "$SVC" ]; then           # háttérszolgáltatás (nem minden appnak van)
		SVC_VERSION=$(python3 -c "import json;print(json.load(open('$SVC/package.json'))['version'])")
		if [ "$VERSION" != "$SVC_VERSION" ]; then
			echo "$name: eltérő verzió (appinfo.json $VERSION, service/package.json $SVC_VERSION)" >&2
			exit 1
		fi
		ares-package "$APP" "$SVC" -o . >/dev/null
	else
		ares-package "$APP" -o . >/dev/null
	fi
	test -f "${ID}_${VERSION}_all.ipk"
done

python3 - $APPS <<'EOF'
import hashlib, json, sys

base = 'https://tomszo.github.io/privat/webos/'
info = {
    'network4': ('Network4', 'Network4 / Arena4+ - sport és élő közvetítések a saját '
                 'előfizetéseddel (nem hivatalos; alap: Arena4Plus - heg, vargalex)',
                 'Sport és élő közvetítések a saját Network4 / Arena4+ előfizetéseddel'),
    'magyaranime': ('MagyarAnime', 'MagyarAnime - privát kliens a saját fiókodhoz '
                    '(munkamenet-süti), a Kodi-kiegészítő TV-s változata',
                    'Anime a saját MagyarAnime-fiókoddal (privát)'),
    'streamed': ('Streamed Sport', 'Streamed Sport - a streamed.pk sportműsora a TV-n '
                 '(a streamed-tui webOS-változata; alap: Salastil)',
                 'Élő sportközvetítések listája és lejátszása (streamed.pk)'),
    'watchsports': ('WatchSports', 'WatchSports - a watchsports.su webhely indítója a TV-n '
                    '(az oldalt nyitja meg az app ablakában)',
                    'A watchsports.su megnyitása a TV-n'),
    'acestrims': ('Acestrims', 'Acestrims - az acestrims.pages.dev webhely indítója a TV-n '
                  '(az oldalt nyitja meg az app ablakában)',
                  'Az acestrims.pages.dev megnyitása a TV-n'),
    'streamsports99': ('StreamSports99', 'StreamSports99 - a streamsports99.ru webhely '
                       'indítója a TV-n (az oldalt nyitja meg az app ablakában)',
                       'A streamsports99.ru megnyitása a TV-n'),
}
packages = []
for name in sys.argv[1:]:
    app = json.load(open(name + '/app/appinfo.json'))
    ipk = '%s_%s_all.ipk' % (app['id'], app['version'])
    data = open(ipk, 'rb').read()
    title, desc, short = info[name]
    manifest = {
        'id': app['id'], 'version': app['version'], 'type': 'web', 'title': title,
        'appDescription': desc,
        'iconUri': base + name + '/app/largeIcon.png',
        'sourceUrl': 'https://github.com/TomSzo/tomszo.github.io/tree/main/privat/webos/' + name,
        'rootRequired': False,
        'ipkUrl': base + ipk,
        'ipkHash': {'sha256': hashlib.sha256(data).hexdigest()},
        'ipkSize': len(data),
    }
    with open(app['id'] + '.manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write('\n')
    packages.append({'id': app['id'], 'title': title, 'iconUri': manifest['iconUri'],
                     'manifestUrl': base + app['id'] + '.manifest.json', 'manifest': manifest,
                     'pool': 'main', 'shortDescription': short})
    print('Kész: %s (%d bájt, sha256 %s)' % (ipk, len(data), manifest['ipkHash']['sha256']))
repo = {'paging': {'page': 1, 'count': len(packages), 'maxPage': 1,
                   'itemsTotal': len(packages), 'prevUrl': None, 'nextUrl': None},
        'packages': packages}
with open('apps.json', 'w', encoding='utf-8') as f:
    json.dump(repo, f, ensure_ascii=False, indent=2)
    f.write('\n')
EOF
