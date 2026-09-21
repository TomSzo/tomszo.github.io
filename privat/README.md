# 🔒 TomSzo Privát Kodi Tároló

> **FIGYELEM — SZEMÉLYES, PRIVÁT TÁROLÓ.** Az itt található kiegészítők
> **kizárólag a tulajdonos (TomSzo) saját fiókjával működnek.** Ha nem te vagy a
> tulajdonos, **ne telepítsd** – nem fog működni a saját fiókod és érvényes
> munkameneted nélkül.

## Miért nem működik másnál? (szakmai indoklás)

A tárolóban lévő kiegészítők olyan oldalakhoz készültek, amelyek **bejelentkezéshez
kötöttek**, és a bejelentkezés **Cloudflare Turnstile / reCAPTCHA** védelemmel van
ellátva. Ezek a védelmek **kliensoldali, böngészőben futó kihívások**, amelyek
megakadályozzák az automatizált (felhasználónév/jelszó alapú) belépést egy
Kodi-kiegészítőből.

Ezért a kiegészítők **nem jelszóval lépnek be**, hanem:

1. A tulajdonos **a saját böngészőjében** bejelentkezik (ő oldja meg a captchát),
2. onnan **kinyeri a munkamenet-sütijét** (session cookie),
3. és ezt **kizárólag a saját Kodi-példányában**, az adott kiegészítő
   beállításai közt tárolja.

A süti a tulajdonos **személyes hitelesítője**:

- **Nélküle** a cél-oldal minden kérésre **login-oldallal vagy HTTP 401/403**
  válaszol → a kiegészítő nem tud sem listázni, sem lejátszani.
- A süti a szolgáltatás **session-élettartama** szerint **lejár**; ilyenkor a
  tulajdonosnak újra be kell lépnie a böngészőben, és frissítenie a süti
  értékét a beállításokban.

**Semmilyen belépési adat nincs a tárolóban**, és semmilyen megosztott hozzáférés
nincs terjesztve. A tároló pusztán a tulajdonos **magánhasználatú** kiegészítőit
szállítja.

## Telepítés (csak a tulajdonosnak)

1. Kodi → **Beállítások → Fájlkezelő → Forrás hozzáadása**
   URL: `https://tomszo.github.io/privat/`  · Név: `TomSzo Privát`
2. **Kiegészítők → Telepítés ZIP fájlból → TomSzo Privát →**
   `repository.tomszo.private-1.0.0.zip`
3. **Kiegészítők → Telepítés repository-ból → TomSzo Privát Tároló**
4. A kiegészítő beállításaiban add meg a **saját, böngészőből kinyert
   munkamenet-sütidet**.

## Jogi / használati megjegyzés

Magánhasználat, saját felelősségre. A kiegészítők csak a tulajdonos saját,
jogszerűen elért fiókjának tartalmát teszik elérhetővé a saját eszközén; harmadik
fél számára szándékosan használhatatlanok.
