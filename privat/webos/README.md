# TomSzo LG webOS-alkalmazások – Network4, MagyarAnime és Streamed Sport (BÉTA, privát)

> **Személyes, privát alkalmazás** – a tulajdonos saját TV-jére és saját Network4 /
> Arena4+ előfizetésére készült; nincs a nyilvános tárolóban hirdetve.

A [Network4 Kodi-kiegészítő](../../plugin.video.network4) webOS-változata LG TV-kre
(fejlesztve LG C4-re, webOS 24). Nem hivatalos alkalmazás, nincs kapcsolatban a
Network4-gyel; a **saját Network4 / Arena4+ előfizetéseddel** működik.

- **Alap:** `plugin.video.arena4plus` – szerzők: **heg** és **vargalex** (GPL-3.0).
- **Lejátszó:** [shaka-player](https://github.com/shaka-project/shaka-player) (Apache-2.0).
- **Betűtípus:** [Inter](https://rsms.me/inter/) (SIL Open Font License 1.1).
- Licenc: **GPL-3.0-or-later**.

## Funkciók

- Streaming-stílusú felület (0.2.0-tól): bal oldali menüsáv, nagy hero-kép a kijelölt
  elem háttérképével és logójával, vízszintes sorok, gyűjtemény-adatlap „Lejátszás”
  gombbal
- Élő közvetítések (élőben vagy az elejétől)
- Sportok: Kiemelt sportok + sportágak → gyűjtemények → videók
- Videótár (összes gyűjtemény), keresés
- Beállítások: belépés, minőség (1080p / 720p / automatikus), lejátszó, kapcsolat teszt
- Távirányító: nyilak + OK + Vissza; a Magic Remote mutatója is működik
- Lejátszás közben: OK = szünet, ◀ / ▶ = tekerés (−10 / +30 mp), Vissza = kilépés

## Telepítés fejlesztői módban

### 1. Fejlesztői mód a TV-n (egyszer)

1. Regisztrálj egy ingyenes fiókot: <https://webostv.developer.lge.com> (LG Developer).
2. A TV-n: **LG Content Store** → keresd meg és telepítsd a **Developer Mode** alkalmazást.
3. Nyisd meg, lépj be az LG Developer fiókkal, kapcsold be a **Dev Mode Status**-t → a TV
   újraindul.
4. Nyisd meg újra a Developer Mode alkalmazást, és kapcsold be a **Key Server**-t. Itt látod
   a TV **IP-címét** és a **Passphrase**-t – ezek kellenek a következő lépéshez.

### 2. Az alkalmazás telepítése a gépedről

A legegyszerűbb a **webOS Dev Manager** (Windows / macOS / Linux):
<https://github.com/webosbrew/dev-manager-desktop/releases>

1. Töltsd le az IPK-t: **[hu.tomszo.network4_0.2.0_all.ipk](hu.tomszo.network4_0.2.0_all.ipk)**
2. Dev Manager → **Add device** → add meg a TV IP-címét és a Passphrase-t.
3. **Apps** → **Install** → válaszd ki a letöltött IPK-t.
4. A TV alkalmazáslistájában megjelenik a **Network4**.

Parancssorból (ha a webOS CLI telepítve van: `npm install -g @webos-tools/cli`):

```sh
ares-setup-device            # TV hozzáadása (IP, port 9922, felhasználó: prisoner)
ares-novacom --device tv --getkey    # a Passphrase-t kéri
ares-install --device tv hu.tomszo.network4_0.2.0_all.ipk
```

### 3. Első indítás

**Beállítások** → add meg a Network4 / Arena4+ email címed és jelszavad → **Kapcsolat teszt**
→ **Mentés**. A belépési adat csak a TV-n tárolódik.

## Fontos: a fejlesztői mód lejár

A fejlesztői mód kb. **50 óránként lejár**, és lejáratkor a TV **törli** a fejlesztői módban
telepített alkalmazásokat. A Developer Mode alkalmazásban az **Extend** gombbal
meghosszabbítható (a Dev Manager is mutatja a hátralévő időt). Ha mégis lejárt: kapcsold
vissza, és telepítsd újra az IPK-t.

## Frissítés (opcionális): Homebrew Channel-tároló

A Homebrew Channel fejlesztői módban is telepíthető (Dev Manager → Apps → Homebrew Channel).
A beállításaiban add hozzá ezt a tárolót, és onnan frissítheted a Network4-et:

```
https://tomszo.github.io/privat/webos/apps.json
```

## Ismert korlátok

- **Cloudflare:** a Network4 API Cloudflare mögött van. Az app (0.1.1-től) közvetlenül a TV
  böngészőmotorjából kérdez (az API ezt engedi), és csak ha ezt elutasítják, vált a
  háttérszolgáltatásra. Ha mégis „elutasította a kérést” hibát kapsz: **Beállítások →
  Kapcsolat** – próbáld a másik módot; a **Kapcsolat teszt** kiírja, melyik út működött.
- **Zárolt videók:** a „token” jelzésű videókhoz aláírt lejátszás kellene, ezeket az API nem
  adja meg – „zárolt”-ként jelennek meg (a Kodi-ban is).
- **DRM:** ha egy élő adás Widevine-védett DASH-ként jön, a lejátszás a TV DRM-támogatásán
  múlik.
- Ha a lejátszás nem indul: **Beállítások → Lejátszó → webOS beépített (tartalék)**.

## MagyarAnime (0.1.0, BÉTA)

A [MagyarAnime Kodi-kiegészítő](../plugin.video.magyaranime) TV-s változata, ugyanazzal a
streaming-stílusú felülettel. **Személyes, privát** – a saját MagyarAnime-fiókod
munkamenet-sütijével működik, belépési adatot nem tartalmaz.

- Telepítés: ugyanúgy, mint a Network4 –
  **[hu.tomszo.magyaranime_0.1.0_all.ipk](hu.tomszo.magyaranime_0.1.0_all.ipk)**
- Menük: Keresés, Főoldal (Folytatás, Kedvencek, Aktuális szezon, Legújabbak), Böngészés
  (adatlapok szűrőkkel), Kedvencek, Előzmények, Beállítások
- Anime-adatlap: borító, ismertető, részek (filler-jelölés, ✓ megnézve), Lejátszás /
  Folytatás, ★ Kedvenc
- Szerverválasztó a napi számlálóval (egyetlen forrás-lekérés a listához, mint a Kodi-ban);
  közvetlen HLS / MP4 és indavideo (mega.nz nem támogatott)

### A süti megadása

1. A gépeden / telefonodon a böngészőben lépj be a MagyarAnime-re, és a **Cookie-Editor**
   bővítménnyel exportáld a sütiket (Export → JSON).
2. A TV-n: **Beállítások → Süti telefonról**. A TV kiír egy címet (pl.
   `http://192.168.1.50:9711/`) és egy **PIN-kódot**.
3. A telefonodon (ugyanazon a Wi-Fi-n) nyisd meg a címet, add meg a PIN-t, és másold be
   az exportot → a TV magától átveszi.
4. **Kapcsolat teszt** – „Bejelentkezve: IGEN”.

Ha a TV nem engedi a helyi oldalt (fejlesztői módban ez TV-függő), használd a
**Süti beírása** lehetőséget (`PHPSESSID=…; loginkey=…`).

### Lejátszás és a Referer-fejléc

A videószerverek Referer / Origin fejlécet várhatnak, amit a TV böngészője nem küld. Ezért
a lejátszás alapból a háttérszolgáltatás **helyi videó-továbbítóján** megy (a fejlécekkel).
Ha valami nem indul: **Beállítások → Videó-továbbító: Ki**, illetve **Lejátszó: webOS
beépített**.

## Streamed Sport (0.1.4, BÉTA)

A [streamed-tui](https://github.com/Salastil/streamed-tui) (Salastil, GPL-3.0) TV-s
változata: a **streamed.pk** sportműsora három oszlopban – kategóriák | meccsek | adások.
Belépés nem kell.

- Telepítés: ugyanúgy, mint a Network4 –
  **[hu.tomszo.streamed_0.1.4_all.ipk](hu.tomszo.streamed_0.1.4_all.ipk)**
- Kategóriák: **Élő most**, **Népszerű**, **Mai műsor**, és sportáganként (magyar
  nevekkel). Az élő meccsek elöl, piros **ÉLŐ** jelzéssel; a lista percenként frissül.
- **Élő állás és befejezett meccsek:** a **Sofascore** (élő meccsek, állás, játékrész –
  szinte minden sportág) és az **ESPN** (foci, NFL, NBA/WNBA, NHL, MLB, UFC) eredményei
  alapján. Az élő meccseknél az ÉLŐ jelzés alatt az állás, mellette pl. „67. perc” /
  „2. negyed”. A **Befejezett meccsek elrejtése** (alapból BE) kiszedi a már véget ért
  meccseket, amiket a streamed.pk még élőként mutat; amit egyik forrás sem ismer (pl.
  darts-napok), annál a sportág szokásos meccshossza dönt.
- Adások: nyelv, HD-jelzés, forrás, nézőszám – nézőszám szerint, a legnézettebb elöl.
- **Csak működő (admin) adások** (a kategóriák alján, alapból BE): a TV-n az **ADMIN**
  forrású adások indulnak, a többi forrás hálózati hibát (-102 / -107) adhat. Bekapcsolva
  csak az admin adású meccsek és adások látszanak (a meccsnél „✓ indítható”).
- **OK** egy adáson: az adás lejátszóoldala teljes képernyőn nyílik meg az appban. Indítás:
  mutass a **Magic Remote-tal** a kép közepén lévő ▶ gombra, és kattints.
  **Vissza:** kilépés a lejátszásból (kattintás után is működik).
- **Piros gomb** egy adáson: megnyitás a TV saját böngészőjében (tartalék, ha az appban
  nem indul).
- **Reklámszűrő** (a kategóriák alján, alapból BE): letiltja a felugró ablakokat és az
  átirányítást. Ha egy adás nem indul el, kapcsold KI, és próbáld újra.

Eltérés a streamed-tui-tól: az eredeti egy rejtett Chrome-mal (puppeteer) kibányássza a
közvetlen videócímet, és az mpv-nek adja – ilyen a TV-n nincs, ezért itt az adás saját
lejátszóoldala fut (ugyanúgy, mint böngészőben). Az **ADMIN** jelzésű adások a leírás
szerint csak böngészőben mennek – a TV-n az appban viszont éppen ezek indulnak (a többi
forrás lejátszója nálunk hálózati hibát ad), ezért ezek vannak elöl.

## Fejlesztőknek

- `network4/app` – webes alkalmazás (HTML/JS), `network4/service` – Node.js szolgáltatás
  (a Network4 felé menő kérések; csak a Network4 címeit engedi).
- `magyaranime/app` – webes alkalmazás, `magyaranime/service` – Node.js szolgáltatás
  (sütis kérések, telefonos süti-párosítás PIN-nel, helyi videó-továbbító; belső hálózati
  címet nem kér le).
- `streamed/app` – webes alkalmazás, szolgáltatás nélkül (a streamed.pk API CORS-t enged).
- Építés: `sh privat/webos/build.sh` (vagy `… build.sh magyaranime`) → IPK-k + `apps.json`
  + manifestek.
