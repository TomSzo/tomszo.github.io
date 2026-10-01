#!/bin/sh
# Network4 (webOS) - IPK építése és a Homebrew Channel-tároló frissítése.
#
# Kell hozzá: Node.js és a webOS CLI (npm install -g @webos-tools/cli), python3.
# Használat:  sh webos/build.sh
#
# Eredmény (a GitHub Pages kiszolgálja):
#   webos/hu.tomszo.network4_<verzió>_all.ipk          - telepíthető csomag
#   webos/hu.tomszo.network4.manifest.json             - Homebrew Channel manifest
#   webos/apps.json                                    - Homebrew Channel tároló
set -eu

cd "$(dirname "$0")"
APP=network4/app
SVC=network4/service
ID=$(python3 -c "import json;print(json.load(open('$APP/appinfo.json'))['id'])")
VERSION=$(python3 -c "import json;print(json.load(open('$APP/appinfo.json'))['version'])")
SVC_VERSION=$(python3 -c "import json;print(json.load(open('$SVC/package.json'))['version'])")
if [ "$VERSION" != "$SVC_VERSION" ]; then
	echo "Eltérő verzió: appinfo.json $VERSION, service/package.json $SVC_VERSION" >&2
	exit 1
fi

rm -f "${ID}"_*.ipk
ares-package "$APP" "$SVC" -o . >/dev/null
IPK="${ID}_${VERSION}_all.ipk"
test -f "$IPK"

python3 - "$ID" "$VERSION" "$IPK" <<'EOF'
import hashlib, json, os, sys

app_id, version, ipk = sys.argv[1:]
base = 'https://tomszo.github.io/webos/'
data = open(ipk, 'rb').read()
manifest = {
    'id': app_id,
    'version': version,
    'type': 'web',
    'title': 'Network4',
    'appDescription': 'Network4 / Arena4+ - sport és élő közvetítések a saját előfizetéseddel '
                      '(nem hivatalos; alap: Arena4Plus - heg, vargalex)',
    'iconUri': base + 'network4/app/largeIcon.png',
    'sourceUrl': 'https://github.com/TomSzo/tomszo.github.io/tree/main/webos/network4',
    'rootRequired': False,
    'ipkUrl': base + ipk,
    'ipkHash': {'sha256': hashlib.sha256(data).hexdigest()},
    'ipkSize': len(data),
}
with open(app_id + '.manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write('\n')
repo = {
    'paging': {'page': 1, 'count': 1, 'maxPage': 1, 'itemsTotal': 1,
               'prevUrl': None, 'nextUrl': None},
    'packages': [{
        'id': app_id,
        'title': 'Network4',
        'iconUri': manifest['iconUri'],
        'manifestUrl': base + app_id + '.manifest.json',
        'manifest': manifest,
        'pool': 'main',
        'shortDescription': 'Sport és élő közvetítések a saját Network4 / Arena4+ előfizetéseddel',
    }],
}
with open('apps.json', 'w', encoding='utf-8') as f:
    json.dump(repo, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('Kész: %s (%d bájt, sha256 %s)' % (ipk, len(data), manifest['ipkHash']['sha256']))
EOF
