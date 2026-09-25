# Időjárás (Időkép + Open-Meteo) – `weather.tomszo`

Kodi időjárás-szolgáltató (Kodi 19+), magyar nyelvű.

| Honnan? | Mit ad? |
|---|---|
| **Időkép** (idokep.hu, magyar településeknél) | jelenlegi idő és hőmérséklet, 3 órás előrejelzés, 15 napos min/max + leírás, figyelmeztetések (pl. *Szeles nap*), napkelte/-nyugta, vízhőmérsékletek |
| **Open-Meteo** (open-meteo.com, bárhol, API-kulcs nélkül) | hőérzet, harmatpont, páratartalom, szél + széllökés, UV, légnyomás, csapadék + valószínűsége, látótávolság, óránkénti 48 órás előrejelzés; külföldi helyeknél minden adat |

Ha az Időkép nem elérhető, automatikusan csak az Open-Meteo adatai látszanak (és fordítva).

## Beállítás
1. Telepítés a TomSzo tárolóból: *Kiegészítők → Telepítés tárolóból → TomSzo Repository → Időjárás-szolgáltatók*.
2. *Beállítások → Szolgáltatások → Időjárás → Időjárás-szolgáltató*: **Időjárás (Időkép + Open-Meteo)**.
3. *Beállítások* gomb → **Helyek**: 1–5. hely; kattints rá, írd be a település nevét (vagy `47.5, 19.04` koordinátát), és válassz a listából. Alapból: Budapest. Üresen hagyott kereséssel a hely törölhető (az 1. kivételével).

## Kímélet
- helyenként és forrásonként legfeljebb 20 percenként 1 letöltés (állítható, min. 15 perc), lemez-gyorsítótárral;
- 1 mp szünet a kérések között, fix Firefox (Android 16) User-Agent;
- hálózati hibánál a legfeljebb 6 órás adat marad kint;
- *Adatok → Gyorsítótár törlése* a mai lekérések számát is megmutatja.

## Skin-tulajdonságok
A szokásos `Current.*`, `Day0-6.*`, `Daily.1-16.*`, `Hourly.1-48.*`, `Today.*` tulajdonságok (Estuary és a legtöbb skin kezeli), plusz: `Current.Headline`, `Current.Description`, `Forecast.Summary` (Időkép szövegek), `Daily.N.Alert`, `Water.N.Name/Temperature`.

Nem hivatalos, nincs kapcsolatban az Időképpel. Időjárási adatok: [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).
