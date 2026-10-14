#!/usr/bin/env python3.12
"""
pin_crypto.py — Replikasi Python encryptPlainText() LinkAja (com.telkom.mwallet).
Model final, teruji luas.

ALGORITMA FINAL:
  salt_str = to_string(rand() % 9000 + 1000)   # 4 digit ASCII "1000".."9999"
  S        = salt_str + pin + arg3             # arg3 = timestamp (epoch ms string)
  body[k]  = ord(S[k]) ^ ord(S[k+10])   jika k < 12 DAN k+10 < len(S)
             ord(S[k])                  selain itu
  data     = body + PKCS#7 pad ke kelipatan 16
  ct       = AES-256-CBC(key=ascii(key)[:32].ljust(32, b'\\0'), IV=b'\\0'*16, data)
  ret      = base64(ct)

CATATAN PENTING:
  - 4 byte pertama plaintext hasil decrypt BUKAN salt mentah — itu
    salt_str XOR arg3[0:4]. Kembalikan dgn recover_salt_str().
  - XOR-nya full-ASCII (bukan digit-value); utk pasangan digit hasilnya sama
    dgn XOR nibble, tapi utk arg3 hex (self-call path) wajib ASCII.
  - Window XOR: partner = posisi+10, aktif utk k <= 15 (16 posisi pertama) dan
    hanya jika partner masih ada di dalam S.
  -"3B mystery 01 07 05" pada ts 13 digit = XOR ts[0],ts[1] dgn ts[10],ts[11]:
    '1'^'0'=0x01, '7'^'7'=0x00, '5'^'5'=0x00 ... (pasangan digit-sama -> 0).
"""

from __future__ import annotations

import base64
import random

from Crypto.Cipher import AES

BLOCK = 16


def _transform(S: str) -> bytes:
    """body[k] = ord(S[k]) ^ ord(S[k+10]) utk k<=15 & k+10<len(S); else ord(S[k]).

    Window k<=15 terverifikasi: self-call (len 42) -> XOR aktif k=0..15,
    tslen13 (len 23) -> aktif k=0..12 (partner OOB mulai k=13)."""
    n = len(S)
    out = bytearray()
    for k in range(n):
        if k < 16 and k + 10 < n:
            out.append((ord(S[k]) ^ ord(S[k + 10])) & 0xFF)
        else:
            out.append(ord(S[k]))
    return bytes(out)


def encrypt_plain_text(pin: str, key: str, ts: str, salt_str: str | None = None) -> str:
    """Replikasi native module.libraries.coresec.ExternalFun.encryptPlainText.
    salt_str bisa di-inject utk determinism test."""
    s = salt_str if salt_str is not None else str(random.randint(1000, 9999))
    assert len(s) == 4 and s.isdigit(), "salt_str harus 4 digit"
    data = _transform(s + pin + ts)
    pad = BLOCK - (len(data) % BLOCK)
    data += bytes([pad]) * pad
    key32 = key.encode("utf-8")[:32].ljust(32, b"\x00")
    ct = AES.new(key32, AES.MODE_CBC, b"\x00" * BLOCK).encrypt(data)
    return base64.b64encode(ct).decode()


def decrypt_cipher_text(b64: str, key: str) -> bytes:
    """Decrypt output (body + PKCS7) -> unpad. Return full pt (salt-masked)."""
    key32 = key.encode("utf-8")[:32].ljust(32, b"\x00")
    pt = AES.new(key32, AES.MODE_CBC, b"\x00" * BLOCK).decrypt(base64.b64decode(b64))
    pad = pt[-1]
    if 1 <= pad <= BLOCK and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    return pt


def recover_salt_str(pt: bytes, arg3: str) -> str:
    """salt_str[k] = chr(pt[k] ^ ord(arg3[k])). Harus 4 digit '1000'-'9999'."""
    raw = bytes((pt[k] ^ ord(arg3[k])) & 0xFF for k in range(4))
    return raw.decode("latin1")


def extract_pin(pt: bytes, arg3: str, pin_len: int = 6) -> str:
    """Ekstrak pin dari pt (model S = salt4+pin+arg3).
    Region pin: k=4..9; partner S[k+10] = arg3[k] (karena S[10+m]=arg3[m])."""
    out = []
    for k in range(4, 4 + pin_len):
        p = k + 10
        if p < 4 + 6 + len(arg3):
            a = arg3[k]  # S[k+10] = arg3[(k+10)-10] = arg3[k]
            out.append(chr(0x30 + ((pt[k] ^ ord(a)) & 0x0F)))
        else:
            out.append(chr(pt[k]))
    return "".join(out)


if __name__ == "__main__":
    # smoke test: determinism + struktur
    key = "0123456789abcdef0123456789abcdef"
    b1 = encrypt_plain_text("123456", key, "1758000000000", salt_str="1234")
    b2 = encrypt_plain_text("123456", key, "1758000000000", salt_str="1234")
    print("deterministic (salt fixed):", b1 == b2)
    pt = decrypt_cipher_text(b1, key)
    print("pt:", pt.hex())
    print("salt_str recovered:", repr(recover_salt_str(pt, "1758000000000")))
    print("pin recovered:", extract_pin(pt, "1758000000000"))