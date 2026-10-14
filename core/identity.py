#!/usr/bin/env python3
"""
identity.py — generator identitas device acak per request.
deviceId = 16 hex, imsi = 16 hex, imei = 15 digit, adsId = uuid, jid = base64 20.
"""
from __future__ import annotations
import os
import base64
import uuid


def rand_hex16() -> str:
    return os.urandom(8).hex()


def rand_imei() -> str:
    # 15 digit (TAC 8 + serial 6 + luhn 1)
    import random
    base = "".join(str(random.randint(0, 9)) for _ in range(14))
    # luhn checksum
    def luhn(s):
        tot = 0
        for i, c in enumerate(reversed(s)):
            d = int(c)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            tot += d
        return (10 - tot % 10) % 10
    return base + str(luhn(base))


def rand_jid() -> str:
    return base64.b64encode(os.urandom(15)).decode()


def new_identity() -> dict:
    return {
        "deviceId": rand_hex16(),
        "imsi": rand_hex16(),
        "imei": rand_imei(),
        "adsId": str(uuid.uuid4()),
        "jid": rand_jid(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(new_identity(), indent=2))