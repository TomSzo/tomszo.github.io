# MagyarAnime (privát) – Kodi videó addon

> 🔒 **Privát, magánhasználatú addon.** Kizárólag a tulajdonos saját,
> böngészőből kinyert munkamenet-sütijével működik. Mások számára
> használhatatlan (a login Cloudflare Turnstile-lal védett).

## Belépés (cookie)

1. Böngészőben (pl. Firefox + **Cookie-Editor**) lépj be a **magyaranime.eu**-ra.
2. Másold ki a **`PHPSESSID`** és **`loginkey`** cookie-kat.
3. Kodi → az addon **Beállítások → Belépés → Cookie** mezőjébe illeszd be így:
   ```
   PHPSESSID=ertek; loginkey=ertek
   ```
4. Ha lejár (kijelentkeztet), lépj be újra a böngészőben, és frissítsd a cookie-t.

## Funkciók (v0.1.0)

- **Keresés** anime címre
- **Epizódlista** (`/resz/{vid}/` alapján), „rész megnyitása azonosítóval"
- **Lejátszás:** `data_player.php` → közvetlen `mp4` / **HLS** / **indavideo** feloldás
- Hibakereséshez a `data_player.php` nyers válaszát naplózza

## Megjegyzés

Béta – a videa-forrás és a katalógus-böngészés a tesztelés visszajelzései alapján
finomodik. A `kodi.log`-ban a `plugin.video.magyaranime` sorok (főleg a
`resolve(...)` és a `data_player.php` válasz) segítenek a pontosításban.
