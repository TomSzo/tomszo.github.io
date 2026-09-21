# SubVito – Kodi videó addon

Nem hivatalos Kodi videó addon a **[subvito.eu](https://subvito.eu/)** oldalhoz –
**South Park magyarul**, feliratokkal és online részekkel.

> ⚠️ **BÉTA / Nem hivatalos.** Az addon semmilyen tartalmat nem tárol, csak a
> subvito.eu nyilvánosan elérhető hivatkozásait listázza. Csak saját felelősségre
> használd. Az addon nincs kapcsolatban a subvito.eu üzemeltetőivel.

## Funkciók

- **Évadok** (1-29), **Filmek** és **P+ (Paramount+)** böngészése
- **Részek** listázása kategóriánként, címmel
- **Legfrissebb részek** (a legújabb évad)
- **Keresés** a részek címei között (ékezet- és kis/nagybetű-független)
- Lejátszás:
  - közvetlen `mp4` forrás kinyerése az epizód-oldalról
  - magyar (és angol) **felirat** (`vtt` / `srt`) automatikus csatolása, magyar előre sorolva
  - tartalék: `iframe` egy szintű követés és HLS (`m3u8`) lejátszás **InputStream Adaptive** segítségével

## Hogyan működik

A subvito.eu minden oldalának fejlécében ott a teljes menü (évadok + részek,
címmel). Az addon ezt **egyetlen kéréssel** kiolvassa, és ebből építi a
katalógust – így nem függ az oldal CSS-osztályaitól, és a keresés is helyben,
hálózat nélkül fut.

A kategória-URL-ek felépítése:

```
https://subvito.eu/<N>-evad/        (2–29. évad)
https://subvito.eu/1-evad-2/        (1. évad – eltérő cím)
https://subvito.eu/filmek/          (Filmek)
https://subvito.eu/paramount-plus/  (P+)
```

Egy rész oldalán a videó közvetlen MP4-ként van beágyazva
(`<video><source src="…mp4">`), a felirat pedig `<track src="…hun.vtt">`-ként –
ezeket nyeri ki és adja át a Kodi lejátszójának.

## Telepítés

A TomSzo Kodi tárolóból:

1. **Kiegészítők → Telepítés repository-ból → TomSzo Repository → Videó kiegészítők → SubVito**

vagy közvetlenül ZIP-ből:

1. **Kiegészítők → Telepítés ZIP fájlból →** `plugin.video.subvito-1.0.0.zip`

## Beállítások

- **Alap URL** – a subvito.eu címe (csak domainváltozáskor kell módosítani)
- **Hibakeresési naplózás** – részletes napló a hibakereséshez

## Hibajelentés

Ha egy rész nem játszódik le, kapcsold be a **hibakeresési naplózást**, próbáld
újra, majd a Kodi naplójában (`kodi.log`) keress rá a `plugin.video.subvito`
sorokra. A `resolve(...) -> media=... iframes=...` sor megmutatja, milyen
forrásokat talált az addon – ezt elküldve pontosítható a lejátszó.

## Követelmények

- Kodi 19 (Matrix) vagy újabb
- `script.module.requests`
- `inputstream.adaptive` (opcionális, HLS lejátszáshoz)

## Licenc

GPL-3.0-or-later
