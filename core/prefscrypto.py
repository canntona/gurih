"""prefscrypto.py — crypto SecuredPreference LinkAja (pure Python).

Format penyimpanan prefs LinkAja (v4.46.1):
  preferenceKey(name)   = HMAC-SHA512(b"HEY TAYOh3y T4y0", name).hexdigest()
  decryptPrefValue(keyname, value):
      ct  = unhex(value)                       # stored value (uppercase hex)
      key = keyname ASCII NUL-padded to 32      # AES-256 key
      iv  = b"HEY TAYOh3y T4y0"                 # constant
      pt  = AES-256-CBC-decrypt(key, iv, ct)
      out = strip PKCS7                         # plaintext / JSON
  preferenceValueEncrypt mirrors exactly:
      stored = ascii2hex(AES-256-CBC-encrypt(key, iv, PKCS7pad(pt))).upper()
"""
import re
import hmac
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

PREF_HMAC_KEY = b"HEY TAYOh3y T4y0"   # 16B — HMAC key & AES IV
AES_IV = b"HEY TAYOh3y T4y0"          # 16B


def pref_name_hash(name: str) -> str:
    """XML <string name="..."> for a preference key name."""
    return hmac.new(PREF_HMAC_KEY, name.encode(), hashlib.sha512).hexdigest()


def _pref_value_key(keyname: str) -> bytes:
    return keyname.encode().ljust(32, b"\x00")[:32]


def pref_value_decrypt(keyname: str, value_hex: str) -> bytes:
    ct = bytes.fromhex(value_hex)
    c = AES.new(_pref_value_key(keyname), AES.MODE_CBC, AES_IV)
    pt = c.decrypt(ct)
    return unpad(pt, 16)


def pref_value_encrypt(keyname: str, plaintext: bytes) -> str:
    c = AES.new(_pref_value_key(keyname), AES.MODE_CBC, AES_IV)
    ct = c.encrypt(pad(plaintext, 16))
    return ct.hex().upper()


def load_prefs_xml(path: str) -> dict:
    return dict(re.findall(r'<string name="([0-9a-f]+)">(.*?)</string>', open(path).read()))


def read_pref(store: dict, name: str):
    h = pref_name_hash(name)
    if h not in store:
        return None
    return pref_value_decrypt(name, store[h])


def write_pref(store: dict, name: str, value: bytes) -> dict:
    store[pref_name_hash(name)] = pref_value_encrypt(name, value)
    return store


def store_to_xml(store: dict) -> str:
    out = ["<?xml version='1.0' encoding='utf-8' standalone='yes' ?>", "<map>"]
    for k, v in store.items():
        out.append(f'    <string name="{k}">{v}</string>')
    out.append("</map>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    # round-trip sanity
    demo = b'{"token":"abc","refreshToken":"xyz"}'
    enc = pref_value_encrypt("AUTHORIZATION_TOKEN", demo)
    assert pref_value_decrypt("AUTHORIZATION_TOKEN", enc) == demo
    print("round-trip encrypt/decrypt: OK")
