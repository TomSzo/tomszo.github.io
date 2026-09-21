# SubVito – Kodi videó addon

Nem hivatalos Kodi videó addon a **[subvito.eu](https://subvito.eu/)** oldalhoz –
**South Park magyarul**, feliratokkal és online részekkel.

> ⚠️ **BÉTA / Nem hivatalos.** Az addon semmilyen tartalmat nem tárol, csak a
> subvito.eu nyilvánosan elérhető hivatkozásait listázza. Csak saját felelősségre
> használd. Az addon nincs kapcsolatban a subvito.eu üzemeltetőivel.

## Funkciók

- **Évadok** böngészése
- **Részek** listázása évadonként
- **Legfrissebb részek** a főoldalról
- **Keresés** a South Park részek között
- Robusztus lejátszó:
  - közvetlen `mp4` / `m3u8` linkek kinyerése
  - `iframe` beágyazások egy szintű követése
  - HLS (`m3u8`) lejátszás **InputStream Adaptive** segítségével
  - magyar felirat (`srt` / `vtt`) automatikus csatolása, ha az oldal kínálja

## Hogyan működik

Az addon **URL-minta alapú**, nem függ az oldal CSS-osztályaitól. A subvito.eu
linkjei így épülnek fel:

```
https://subvito.eu/<évad>-evad/<rész-slug>/
```

Az addon a főoldalról olvassa ki az évadokat, az évad-oldalakról a részeket, a
rész-oldalról pedig a lejátszható forrást.

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
