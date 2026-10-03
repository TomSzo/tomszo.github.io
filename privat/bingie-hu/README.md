# Bingie – magyar változat (privát)

A [matke-84/repository.bingie](https://github.com/matke-84/repository.bingie) Kodi 21-es (Omega)
Bingie skinjének és kiegészítőinek **teljes magyar fordítása, magyar súgóval**.

## Mi van benne?

- **Teljes magyar fordítás** (kb. 1300 szöveg): a skin, a TMDb Bingie Helper, a Bingie Widgets /
  Helper / Toolbox, a képernyővédő, a színválasztó, a skinmentés és az automatikus kiegészítés.
- **Súgó-infódoboz**:
  - a skinbeállításoknál alul mindig látszik, mit csinál a kijelölt beállítás (145 beállítás +
    általános súgó a 109 színgombhoz);
  - a kiegészítők beállítás-ablakában (pl. TMDb Bingie Helper) is van leírásmező, és
    **minden beállításnak van magyar súgója** (kb. 120 új súgószöveg).
- **Magyar alapértékek**: a TMDb Bingie Helper alapból magyarul kéri le a címeket és
  leírásokat; az alap-színtéma színnevei magyarok.
- A kódba égetett néhány angol felirat is magyar.

A verziószámok az eredeti után egy `.1`-et kapnak (pl. `skin.bingie` 2.0.2 → **2.0.2.1**),
így ha mindkét tároló telepítve van, a Kodi a magyar változatot választja.

## Telepítés (AVDV / Kodi 21)

1. Telepítsd a **matke-tárolót** is (a nem fordított függőségek, pl. a stúdiólogók onnan jönnek):
   Fájlkezelő → Forrás hozzáadása: `https://matke-84.github.io/repository.bingie/repository.bingie/`
   → Kiegészítők → Telepítés ZIP fájlból → `repository.bingie-1.0.0.zip`.
2. Legyen fent a **TomSzo Privát Tároló** (lásd a [fő README-t](../README.md)).
3. Kiegészítők → Telepítés tárolóból → **TomSzo Privát Tároló** → Skin → **Bingie**
   (2.0.2.1). A függőségeket a Kodi magától felteszi, a magyar változatokat ebből a tárolóból.
4. Ha a Bingie már fent volt: Kiegészítők → Saját kiegészítők → ... → **Frissítés**, és válaszd a
   2.0.2.1 / 1.0.3.1 stb. verziót a TomSzo tárolóból.
5. A Kodi nyelve legyen magyar (Beállítások → Felület → Régió → Nyelv).

Megjegyzés: ha a matke-tároló később újabb verziót ad ki (pl. 2.0.3), a Kodi arra frissít, és a
fordítás eltűnik, amíg itt is el nem készül az új magyar változat.

## Újraépítés

```sh
python3 privat/bingie-hu/_tools/build.py
```

A szkript letölti az eredeti csomagokat, beteszi a `forditas/` mappa fájljait (`<id>.tsv`:
fordítás, `<id>.sugo.tsv`: beállítás-súgók), elvégzi a skin-módosításokat, és kiírja a
zipeket a privát tárolóba (`privat/<id>/`), majd frissíti a `privat/addons.xml`-t.
