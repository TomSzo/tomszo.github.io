# signde PPI (tinyppi) – TomSzo-változat

Alap: **script.signde.tinyppi** (jamal2362, signde; MIT) a signde tárolóból.
A TomSzo-változat verziója az eredetié + `.1` (pl. 17.2.7.5 → **17.2.7.5.1**), így a Kodi ezt választja.

## Mi változott?

| Újdonság | Hol kapcsolható? | Alapértelmezés |
|---|---|---|
| **Színes logók** – Dolby (Atmos, TrueHD, DD+), DTS, Dolby Vision, HDR10+, IMAX… saját színeikben | Beállítások → Kodek logók → Logók stílusa → *Színes logók* | be |
| **Felbontás jelvény** – 4K / 1080p / 720p / SD | … → *Felbontás jelvény* | ki |
| **Videókodek jelvény** – HEVC / AVC / AV1 / VP9 / MPEG-2 / VC-1 | … → *Videókodek jelvény* | ki |
| **Teljes magyar fordítás** – a hiányzó 148 szöveg (színnevek, Player Process Info sorai) | – | – |

A logók sorrendje a panelen: HDR/videó → felbontás → videókodek → hang, mindegyik között elválasztó vonallal.
Színes módban a logószín-beállítások nem érvényesek (a háttér- és elválasztószín igen); kikapcsolva minden az eredeti módon, egyszínűen festve jelenik meg.

## Építés

```
python3 privat/tinyppi-hu/_tools/build.py
```

- `_tools/colorize.py <codecs mappa> <kimenet>` – a tinyppi fehér logóiból színeseket készít (→ `media/codecs_color`)
- `_tools/make_badges.py <Inter-Bold.ttf> <kimenet> [--white]` – felbontás- és kodekjelvények (→ `media/badges`, `media/badges_white`)
- `forditas/script.signde.tinyppi.tsv` – a hiányzó magyar szövegek
