#!/usr/bin/env python3
"""devicefree.py — crypto stack LinkAja 4.46.1, pure python.

LAYERS:
  getKey(kX, ver)   : gk = kX[off:off+16], off dari simpleEncrypt hex2ascii(
                      kX[atoi(digits(ver))%len : +4], "a5ff") u16be % len
  body (putu/tayo/thomas): AES-256-CBC, key=mask(XOR(imsi+gk_body, did+ts)),
                      iv=mask(XOR(ts, gk_body)), gk_body = getKey(k3)
                      putu   = E(salt4 + json)
                      tayo   = E(json + SECRET)
                      thomas = E(json)
  raw header        : HMAC-SHA512(key=(XOR(imsi+gk_raw, did+ts))>>2, msg)
                      gk_raw = getKey(k1)
                      msg    = encrypted body (POST) | ts + "tw4ll3tn30" (GET)
"""
from __future__ import annotations

import base64
import hmac as _hmac
import hashlib
import secrets

from Crypto.Cipher import AES

SECRET = "DN$F#hwNk7TJWhu+ptF#f8bNTCASH"
UID_MAC = "tw4ll3tn30"     # hashMacUID constant (libBaseKey.so)
GK_FALLBACK = "XT6PRpRuehFsyMa2"  # native const @0x169c0 — gk saat keys blank (echo/key-exchange)


# ---------- getKey (native libHappyBus @0x30858) ----------
def _simple_encrypt(a: bytes, b: bytes) -> bytes:
    return bytes(a[i] ^ b[i % len(b)] for i in range(len(a)))


def get_key(kx: str, ver: str = "4.46.1") -> str:
    """gk 16-char dari kX (768 hex) — offset deterministik."""
    digits = "".join(c for c in ver if c.isdigit())
    start = int(digits) if digits else 0
    n = len(kx)
    s4 = "".join(kx[(start + i) % n] for i in range(4))
    enc = _simple_encrypt(bytes.fromhex(s4), bytes.fromhex("a5ff"))
    off = ((enc[0] << 8) | enc[1]) % n
    return "".join(kx[(off + i) % n] for i in range(16))


# ---------- helpers ----------
def _xr(d: bytes, k: bytes) -> bytes:
    return bytes(d[i] ^ k[i % len(k)] for i in range(len(d)))


def _mask(b: bytes) -> bytes:
    return bytes((((x & 0x3F) << 2) & 0xFF) for x in b)


def _pad16(data: bytes) -> bytes:
    pad = 16 - (len(data) % 16)
    return data + bytes([pad]) * pad


# ---------- body encryption ----------
def encrypt_body(ts: str, did: str, imsi: str, msg: str, k3: str,
                ver: str = "4.46.1", gk: str = None) -> str:
    gk = gk or get_key(k3, ver)
    se2 = _xr(imsi.encode() + gk.encode(), (did + ts).encode())
    key32 = _mask(se2)
    se3 = _xr(ts.encode(), gk.encode())
    iv = (_mask(se3) + b"\x00" * 16)[:16]
    return base64.b64encode(
        AES.new(key32, AES.MODE_CBC, iv).encrypt(_pad16(msg.encode()))
    ).decode()


def encrypt_request_payload(ts: str, did: str, imsi: str, payload_json: str,
                            k3: str, ver: str = "4.46.1") -> dict:
    """Return {putu, tayo, thomas} — encrypted request body."""
    salt4 = f"{secrets.randbelow(0xFFFF):04x}"
    putu = encrypt_body(ts, did, imsi, salt4 + payload_json, k3, ver)
    tayo = encrypt_body(ts, did, imsi, payload_json + SECRET, k3, ver)
    thomas = encrypt_body(ts, did, imsi, payload_json, k3, ver)
    return {"putu": putu, "tayo": tayo, "thomas": thomas}


# ---------- raw header ----------
# v5 = body + ts + UID_MAC (POST) | ts + UID_MAC (GET)
# raw = HMAC-SHA512(key=(XOR(imsi+gk, did+ts))>>2, v5), gk = getKey(k1)
def calc_raw(ts: str, did: str, imsi: str, msg: str, k1: str,
             ver: str = "4.46.1", gk: str = None) -> str:
    gk = gk or get_key(k1, ver)
    se2 = _xr(imsi.encode() + gk.encode(), (did + ts).encode())
    hkey = bytes(b >> 2 for b in se2)
    return _hmac.new(hkey, msg.encode("latin-1"), hashlib.sha512).hexdigest()


def raw_for_get(ts: str, did: str, imsi: str, k1: str, ver: str = "4.46.1",
                gk: str = None) -> str:
    return calc_raw(ts, did, imsi, ts + UID_MAC, k1, ver, gk)


def raw_for_post(ts: str, did: str, imsi: str, encrypted_body: str,
                 k1: str, ver: str = "4.46.1", gk: str = None) -> str:
    v5 = encrypted_body + ts + UID_MAC
    return calc_raw(ts, did, imsi, v5, k1, ver, gk)


# ---------- response decryption ----------
def decrypt_body(ts: str, did: str, imsi: str, b64_ct: str, k3: str,
                 ver: str = "4.46.1") -> str:
    gk = get_key(k3, ver)
    se2 = _xr(imsi.encode() + gk.encode(), (did + ts).encode())
    key32 = _mask(se2)
    se3 = _xr(ts.encode(), gk.encode())
    iv = (_mask(se3) + b"\x00" * 16)[:16]
    pt = AES.new(key32, AES.MODE_CBC, iv).decrypt(base64.b64decode(b64_ct))
    pt = pt[: -pt[-1]]  # strip PKCS7
    return pt.decode()


if __name__ == "__main__":
    print("devicefree: modul siap (getKey/body/raw/decrypt).")