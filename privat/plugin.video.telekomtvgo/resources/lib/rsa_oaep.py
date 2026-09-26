# -*- coding: utf-8 -*-
"""RSA-OAEP (SHA-1, MGF1-SHA-1) titkosítás tiszta Pythonban.

A Telekom TV GO webes kliense a jelszót a CMS-konfigurációban kapott nyilvános kulccsal
(modules.auth.rsaPublicKey) így titkosítja (node-forge: RSA-OAEP, md=sha1, mgf1=sha1),
és base64-ben küldi. Kodi alatt nincs garantáltan kriptográfiai modul, ezért saját kód.
"""
import base64
import hashlib
import os


def _der_len(b, i):
    n = b[i]
    i += 1
    if n & 0x80:
        cnt = n & 0x7f
        n = int.from_bytes(b[i:i + cnt], 'big')
        i += cnt
    return n, i


def _der_item(b, i):
    """(tag, tartalom-kezdet, hossz) - egy DER elem fejléce."""
    tag = b[i]
    ln, i = _der_len(b, i + 1)
    return tag, i, ln


def public_key_from_b64(spki_b64):
    """SubjectPublicKeyInfo (base64, PEM fejléc nélkül) -> (n, e)."""
    der = base64.b64decode(''.join(spki_b64.split()))
    _, i, _ = _der_item(der, 0)            # SEQUENCE
    _, j, ln = _der_item(der, i)           # AlgorithmIdentifier
    i = j + ln
    tag, i, ln = _der_item(der, i)         # BIT STRING
    if tag != 0x03:
        raise ValueError('hibás nyilvános kulcs')
    i += 1                                 # "unused bits" bájt
    _, i, _ = _der_item(der, i)            # RSAPublicKey SEQUENCE
    _, i, ln = _der_item(der, i)           # modulus
    n = int.from_bytes(der[i:i + ln], 'big')
    i += ln
    _, i, ln = _der_item(der, i)           # exponens
    e = int.from_bytes(der[i:i + ln], 'big')
    return n, e


def _mgf1(seed, length):
    out = b''
    counter = 0
    while len(out) < length:
        out += hashlib.sha1(seed + counter.to_bytes(4, 'big')).digest()
        counter += 1
    return out[:length]


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def encrypt(message, spki_b64):
    """message (str/bytes) -> base64 RSA-OAEP rejtjel."""
    if not isinstance(message, bytes):
        message = message.encode('utf-8')
    n, e = public_key_from_b64(spki_b64)
    k = (n.bit_length() + 7) // 8
    hlen = 20
    if len(message) > k - 2 * hlen - 2:
        raise ValueError('túl hosszú jelszó')
    lhash = hashlib.sha1(b'').digest()
    ps = b'\x00' * (k - len(message) - 2 * hlen - 2)
    db = lhash + ps + b'\x01' + message
    seed = os.urandom(hlen)
    masked_db = _xor(db, _mgf1(seed, k - hlen - 1))
    masked_seed = _xor(seed, _mgf1(masked_db, hlen))
    em = b'\x00' + masked_seed + masked_db
    c = pow(int.from_bytes(em, 'big'), e, n)
    return base64.b64encode(c.to_bytes(k, 'big')).decode('ascii')
