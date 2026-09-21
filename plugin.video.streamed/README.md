# Streamed – Kodi videó addon

Nem hivatalos Kodi videó addon a **[streamed.pk](https://streamed.pk/)** nyilvános
API-jához – **élő sportesemények** böngészése és lejátszása.

> ⚠️ **BÉTA / Nem hivatalos.** Az addon semmilyen tartalmat nem tárol, csak a
> streamed.pk API nyilvánosan elérhető hivatkozásait listázza. Csak saját
> felelősségre használd. Az addon nincs kapcsolatban a streamed.pk üzemeltetőivel.

## Funkciók

- **Élő most** – éppen futó események
- **Népszerű** és **Ma** listák
- **Sportágak** szerinti böngészés → meccsek
- **Összes meccs**
- Meccsenként **stream-választás** (forrás, nyelv, HD/SD, stream-szám)
- Lejátszás: az embedből kinyert `m3u8` HLS lejátszása **InputStream Adaptive**-val,
  a szükséges `Referer`/`Origin` fejlécekkel

## Hogyan működik

Az addon a streamed.pk **JSON API-ját** hívja (nem HTML-t szkrébel):

```
api/sports                     – sportágak
api/matches/live               – élő most
api/matches/all-today          – mai meccsek
api/matches/all/popular        – népszerűek
api/matches/<sport>            – egy sportág meccsei
api/stream/<source>/<id>       – egy meccs streamjei
```

A meccs kiválasztása után a stream **embed-oldaláról** próbálja kinyerni a
lejátszható `m3u8` linket, és azt adja át a Kodi HLS lejátszójának.

## A lejátszásról (fontos)

A stream-lejátszó (`embed.st`) reklám-/adblock-védett, obfuszkált JS-sel tölti be
a videót, ezért az `m3u8` kinyerése **best-effort**, és időnként változhat. Ha egy
stream nem indul:

1. Kapcsold be a **Beállítások → Hibakeresési naplózás**-t
2. Próbáld újra a lejátszást
3. A `kodi.log`-ban keresd a `plugin.video.streamed` sorokat – a
   `resolve(...) -> m3u8=... origin=...` sor megmutatja, mit talált az addon

Ha az `m3u8` üres, az embed-oldal tartalmát elküldve pontosítható a kinyerés.

## Telepítés

A TomSzo Kodi tárolóból:

1. **Kiegészítők → Telepítés repository-ból → TomSzo Repository → Videó kiegészítők → Streamed**

vagy közvetlenül ZIP-ből: `plugin.video.streamed-1.0.0.zip`

## Beállítások

- **API alap URL** – a streamed.pk címe (csak domainváltozáskor kell módosítani, pl. `streamed.su`)
- **Hibakeresési naplózás**

## Követelmények

- Kodi 19 (Matrix) vagy újabb
- `script.module.requests`
- `inputstream.adaptive` (HLS lejátszáshoz)

## Licenc

GPL-3.0-or-later
