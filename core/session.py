#!/usr/bin/env python3
"""session.py — LinkAja API session: key agreement + request signing.

Flow: identity → DH key exchange → session keys (k1/k2/k3) → API call.
"""
import json, time, warnings, sys, os, pathlib
warnings.filterwarnings("ignore")
import httpx

import devicefree as df

BASE = "https://avengers.linkaja.com/v2/api"
VER = "4.46.1"

# data dir portable (Windows/Linux/Termux): <root>/data/ sejajar core/
_HERE = pathlib.Path(__file__).resolve().parent
ROOT = _HERE.parent
DATA = ROOT / "data"
STATES = DATA / "states"
DATA.mkdir(parents=True, exist_ok=True)
STATES.mkdir(parents=True, exist_ok=True)

_FIS_FILE = DATA / "fis.json"
if not _FIS_FILE.exists():
    sys.exit("❌ data/fis.json gak ketemu — seed installation token harus ada "
             "di data/fis.json (lihat README)")
fis = json.loads(_FIS_FILE.read_text())
FID_TOKEN = fis["authToken"]["token"]

from keyagreement import get_key as dh_privkeys, get_public_key, generate_shared_key
from identity import new_identity

_CLIENT = httpx.Client(verify=False, timeout=30)


def state_path(msisdn) -> pathlib.Path:
    return STATES / f"state_{msisdn}.json"


def save_state(msisdn, sess, refid=None, jwt=None, refreshToken=None):
    """Simpan/perbarui state akun (identity + session keys + refId + JWT)."""
    ident, shared = sess
    p = state_path(msisdn)
    old = {}
    if p.exists():
        try:
            old = json.loads(p.read_text())
            if not isinstance(old, dict):
                old = {}
        except Exception:
            old = {}
    old.update({"ident": ident, "shared": shared, "created": time.time()})
    if refid:
        old["refId"] = refid
    if jwt:
        old["jwt"] = jwt
    if refreshToken:
        old["refreshToken"] = refreshToken
    p.write_text(json.dumps(old, ensure_ascii=False, indent=2))
    return old


def load_state(msisdn, max_age=7 * 86400) -> dict | None:
    p = state_path(msisdn)
    if p.exists():
        try:
            st = json.loads(p.read_text())
        except Exception:
            return None
        if time.time() - st.get("created", 0) > max_age:
            return None
        return st
    return None


def list_states() -> list[dict]:
    out = []
    for p in sorted(STATES.glob("state_*.json")):
        try:
            st = json.loads(p.read_text())
            ms = p.stem.replace("state_", "")
            out.append({"msisdn": ms, "fullname": st.get("fullname", ""),
                        "jwt": st.get("jwt", ""),
                        "file": str(p)})
        except Exception:
            pass
    return out


def key_agreement():
    ident = new_identity()
    did, imsi = ident["deviceId"], ident["imsi"]
    priv = dh_privkeys()
    pub = get_public_key(priv)
    payload = json.dumps({"Krisna": pub["key1"], "Endhy": pub["key2"],
                          "Rilvi": pub["key3"]}, separators=(',', ':'))
    ts = str(int(time.time() * 1000))
    enc = lambda m: df.encrypt_body(ts, did, imsi, m, k3="", gk=df.GK_FALLBACK)
    send = json.dumps({"putu": enc(payload), "tayo": enc(payload + df.SECRET),
                       "thomas": enc("7744" + payload + ts)}, separators=(',', ':'))
    raw = df.calc_raw(ts, did, imsi, send + ts + df.UID_MAC, k1="", gk=df.GK_FALLBACK)
    H = {"accept-language": "ID", "pushid": "", "jid": ident["jid"],
         "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
         "fid": FID_TOKEN, "osname": "Android", "osversion": "13",
         "appversion": VER, "devicemodel": "XIAOMI Redmi Note 5",
         "accept": "application/json", "deviceid": did, "imsi": imsi,
         "content-type": "application/json; charset=UTF-8",
         "timestamp": ts, "raw": raw, "errorcode": "",
         "authorization": "Bearer", "user-agent": "okhttp/4.11.0",
         "accept-encoding": "gzip"}
    r = _CLIENT.post(f"{BASE}/echo", content=send, headers=H)
    assert r.status_code == 200, f"echo {r.status_code}: {r.text[:120]}"
    resp = json.loads(r.text)
    shared = {"key1": generate_shared_key(priv["key1"], resp["data"]["x1"]),
              "key2": generate_shared_key(priv["key2"], resp["data"]["x2"]),
              "key3": generate_shared_key(priv["key3"], resp["data"]["x3"])}
    return ident, shared


def decrypt_resp(r, st):
    """Response decrypt: gk=getKey(k1), ts = response header timestamp."""
    import base64
    from Crypto.Cipher import AES
    body = r.text.strip()
    if body.startswith("{"):
        return json.loads(body)
    ident, shared = st["ident"], st["shared"]
    did, imsi = ident["deviceId"], ident["imsi"]
    rts = r.headers.get("timestamp", "")
    gk = df.get_key(shared["key1"], VER)
    _xr = lambda d, k: bytes(d[i] ^ k[i % len(k)] for i in range(len(d)))
    _mask = lambda b: bytes(((x & 0x3f) << 2) & 0xff for x in b)
    se2 = _xr(imsi.encode() + gk.encode(), (did + rts).encode())
    key32 = _mask(se2)
    se3 = _xr(rts.encode(), gk.encode())
    iv = (_mask(se3) + b"\x00" * 16)[:16]
    pt = AES.new(key32, AES.MODE_CBC, iv).decrypt(base64.b64decode(body))
    n = pt[-1] if pt[-1] <= 16 else 0
    return json.loads(pt[:len(pt) - n].decode())


def api_post(sess, path, payload_dict, token="Bearer", ts=None, extra_headers=None):
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    payload = json.dumps(payload_dict, separators=(',', ':'))
    ts = ts or str(int(time.time() * 1000))
    enc = lambda m: df.encrypt_body(ts, did, imsi, m, k3=shared["key3"])
    send = json.dumps({"putu": enc(payload), "tayo": enc(payload + df.SECRET),
                       "thomas": enc("7744" + payload + ts)}, separators=(',', ':'))
    raw = df.calc_raw(ts, did, imsi, send + ts + df.UID_MAC, k1=shared["key1"])
    H = {"accept-language": "ID", "pushid": "", "jid": ident["jid"],
         "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
         "fid": FID_TOKEN, "osname": "Android", "osversion": "13",
         "appversion": VER, "devicemodel": "XIAOMI Redmi Note 5",
         "accept": "application/json", "deviceid": did, "imsi": imsi,
         "content-type": "application/json; charset=UTF-8",
         "timestamp": ts, "raw": raw, "errorcode": "",
         "authorization": token, "user-agent": "okhttp/4.11.0",
         "accept-encoding": "gzip"}
    if extra_headers:
        H.update(extra_headers)
    return _CLIENT.post(BASE + path, content=send, headers=H)


def api_get(sess, path, token="Bearer"):
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    ts = str(int(time.time() * 1000))
    raw = df.calc_raw(ts, did, imsi, ts + df.UID_MAC, k1=shared["key1"])
    H = {"accept-language": "ID", "pushid": "", "jid": ident["jid"],
         "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
         "fid": FID_TOKEN, "osname": "Android", "osversion": "13",
         "appversion": VER, "devicemodel": "XIAOMI Redmi Note 5",
         "accept": "application/json", "deviceid": did, "imsi": imsi,
         "timestamp": ts, "raw": raw, "errorcode": "",
         "authorization": token, "user-agent": "okhttp/4.11.0",
         "accept-encoding": "gzip"}
    return _CLIENT.get(BASE + path, headers=H)