# Telekom TV GO (Kodi) – privát, BÉTA

Nem hivatalos Kodi-kiegészítő a Magyar Telekom **TV GO** szolgáltatásához
(`player.telekomtvgo.hu`), a **saját Telekom-fiókoddal / TV-előfizetéseddel**.

## Mit tud?

- **Élő TV** – csatornalista a most futó műsorral
- **Műsorújság és visszanézés** – 3 nap vissza / 3 nap előre; a lement műsorok visszanézhetők
- **Kapcsolat teszt** – belépés, fiókadatok, csatornák ellenőrzése

## Beállítás

1. Telepítés a TomSzo Privát tárolóból.
2. Beállítások → **Belépés**: a Telekom-fiókod email címe és jelszava
   (ugyanaz, mint a player.telekomtvgo.hu-n).
3. Ha az automatikus belépés nem sikerül: jelentkezz be a böngészőben a
   player.telekomtvgo.hu-n, és a `refreshToken` nevű süti értékét (vagy a belépés utáni
   visszairányítási URL-t, amiben `refresh_token=` van) illeszd be a
   **Belépés → Refresh token** mezőbe.
4. Kell hozzá az **InputStream Adaptive** és a **Widevine** (ha az InputStream Helper
   telepítve van, az addon szükség esetén felajánlja a Widevine telepítését).

## Hogyan működik?

A webes lejátszó (W02.0.1470) működése alapján, új kóddal:

| Lépés | Végpont |
|---|---|
| Belépés | `bifrost/tenant/config` → MediaKind STS → Telekom belépőoldal (email + jelszó) → token |
| Tokenfrissítés | `bifrost/oauth/token` (`grant_type=refresh_token`) |
| Fiók, csatornák, műsorújság, lejátszási adatok | `tv-hu-prod.yo-digital.com/bifrost/…` (`bff_token` fejléc) |
| Stream | MediaKind: `/v1/client/registrations`, `/v1/client/roll` → DASH (`livetv.cdn.telekomtvgo.hu`) |
| Licenc | MediaKind: `/v1/client/get-widevine-license` |
| Életjel | MediaKind: `/v1/client/beacons` (lejátszás közben) |

A kiegészítő **eszközként regisztrál** a Telekom-fiókodban (állandó azonosítóval,
nem hoz létre újat minden indításkor).

## Ha valami nem megy

A hibás válaszok mindig mentődnek (`error_*.json`, belépésnél `login_steps.json` és
`login_page.html`). Részletesebb mentéshez: Beállítások → **Hibakeresés → Nyers
API-válaszok mentése**, majd próbáld újra. A fájlok a Kodi profil-mappájában
(`userdata/addon_data/plugin.video.telekomtvgo/`) lesznek – ezekből a hiba javítható.
A token-mezők a mentésben ki vannak takarva.

## Jogi megjegyzés

Nem hivatalos, nincs kapcsolatban a Magyar Telekommal. Belépési adatot nem tartalmaz,
DRM-et nem kerül meg (a licenc a Telekom saját licencszerveréről jön, a saját
előfizetésed alapján). Saját felelősségre.
