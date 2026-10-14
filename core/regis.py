"""regis.py — flow pendaftaran akun LinkAja (input manual, OTP via SMS).

Tahap:
  1. onboard/check → cek nomor
  2. /otp (onboarding) → SMS OTP ke nomor user; refId disimpan
  3. validate-check (OTP dari user)
  4. register (nama + email + PIN) — harus ≤60 dtk setelah validate
  5. state disimpan (identity + session keys + JWT)
"""
import hashlib
import json
import time

import devicefree as df
import pin_crypto
from session import (api_post, decrypt_resp, key_agreement, load_state,
                     save_state, state_path, STATES)

TNC = "17 Februari 2025"
ENC_KEY = "DN$F#hwNk7TJWhu+ptF#f8bNTCASH"


class RegisError(Exception):
    """Error user-friendly (message-nya langsung bisa ditampilkan)."""


def normalize_msisdn(raw: str) -> str:
    """62812xxxx / 0812xxxx / +62812xxxx → 62812xxxx."""
    m = (raw or "").strip().lstrip("+").replace(" ", "").replace("-", "")
    if m.startswith("0"):
        m = "62" + m[1:]
    if not (m.startswith("62") and m[8:].isdigit() and 10 <= len(m) <= 15):
        raise RegisError("Nomor HP gak valid. Contoh: 08123456789")
    return m


def step_check(msisdn):
    """Cek nomor di server. Return (sudah_terdaftar: bool, pesan)."""
    st = load_state(msisdn, max_age=365 * 86400)
    if not st:
        st = _new_state(msisdn)
    r = api_post(_sess(st), "/onboard/check", {"msisdn": msisdn})
    j = decrypt_resp(r, st) if r.status_code == 200 else {}
    status = j.get("status", "")
    msg = j.get("message", "")
    # BUGFIX 9 Okt: "terdaftar" itu substring dari "BELUM terdaftar" —
    # nomor fresh (10010005 "Anda belum terdaftar") dianggap udah terdaftar
    # → alur daftar mati di step 1 buat SEMUA nomor baru.
    low = (msg or "").lower()
    registered = (status == "10010004"
                  or ("terdaftar" in low and "belum" not in low))
    return registered, f"{status} | {msg}"


def step_send_otp(msisdn):
    """Kirim SMS OTP ke nomor user. Return refId (disimpan di state)."""
    st = load_state(msisdn, max_age=365 * 86400)
    sess = key_agreement()          # OTP selalu session fresh
    st = _ensure_state(msisdn, sess)
    r = api_post(sess, "/onboard/check", {"msisdn": msisdn})
    r = api_post(sess, "/otp", {"msisdn": msisdn, "type": "onboarding"})
    if r.status_code != 200:
        raise RegisError(f"Server nolak kirim OTP (HTTP {r.status_code})")
    j = decrypt_resp(r, _st_of(sess))
    refid = j.get("refId") or j.get("data", {}).get("refId")
    if not refid:
        raise RegisError("Server gak kasih refId — coba lagi")
    save_state(msisdn, sess, refid=refid)
    return refid


def step_validate(msisdn, otp: str) -> dict:
    """Validasi OTP user → state SIGNUP. Raise RegisError kalau salah."""
    st = load_state(msisdn, max_age=365 * 86400)
    if not st or not st.get("refId"):
        raise RegisError("Ga ada sesi OTP aktif — mulai daftar lagi")
    r = api_post(_sess(st), "/onboard/validate-check",
                 {"msisdn": msisdn, "otp": otp, "refId": st["refId"]})
    j = decrypt_resp(r, st) if r.status_code == 200 else {}
    if j.get("data", {}).get("state") != "SIGNUP":
        raise RegisError(f"OTP ditolak: {j.get('message') or j.get('status')}")
    return j


def step_register(msisdn, pin, fullname, email) -> dict:
    """Setor nama+email+PIN → akun jadi. Wajib ≤60 dtk setelah validate."""
    st = load_state(msisdn, max_age=365 * 86400)
    if not st or not st.get("refId"):
        raise RegisError("Ga ada sesi validate aktif — mulai daftar lagi")
    sess = _sess(st)
    ts = str(int(time.time() * 1000))
    key32 = hashlib.sha256(ENC_KEY.encode()).hexdigest()[:32]
    pin_enc = pin_crypto.encrypt_plain_text(pin, key32, ts)
    body = {"email": email, "fullName": fullname, "msisdn": msisdn,
            "pushId": "", "pin": pin_enc, "sharia": False, "tncVersion": TNC}
    r = api_post(sess, "/onboard/register", body,
                 extra_headers={"x-koya-geheim": ts})
    j = decrypt_resp(r, st) if r.status_code == 200 else {}
    if j.get("status") not in ("00", "10010201"):
        raise RegisError(f"Register gagal: {j.get('message') or j.get('status')}")
    d = j.get("data", {})
    save_state(msisdn, sess, jwt=d.get("auth"),
               refreshToken=d.get("refreshToken"))
    # metadata akun (nama/email/pin/customerId) nempel di file state
    p = state_path(msisdn)
    cur = json.loads(p.read_text())
    cur.update({"fullname": fullname, "email": email, "pin": pin,
                "customerId": d.get("customerId"), "msisdn": msisdn})
    p.write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    return d


# ── helpers ──────────────────────────────────────────────────────────────
def _sess(st):
    return (st["ident"], st["shared"])


def _st_of(sess):
    return {"ident": sess[0], "shared": sess[1]}


def _new_state(msisdn):
    sess = key_agreement()
    save_state(msisdn, sess)
    return load_state(msisdn, max_age=365 * 86400)


def _ensure_state(msisdn, sess):
    save_state(msisdn, sess)
    return _st_of(sess)