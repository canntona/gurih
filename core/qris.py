#!/usr/bin/env python3
"""core/qris.py — Modul Payment & Cashout QRIS Dinamis/Statis LinkAja.

Mendukung pembayaran menggunakan saldo bonus (bonbal), saldo utama, maupun
penggabungan keduanya (split-payment).
"""
import base64
import json
import time
import hashlib
from Crypto.Cipher import AES

import devicefree as df
import pin_crypto
import session

VER = session.VER
BASE = session.BASE
ENC_KEY = "DN$F#hwNk7TJWhu+ptF#f8bNTCASH"


# -------------------------------------------------------------
# 1. EMV TLV PARSER & OFFLINE QR INSPECTION (ZERO-DEPENDENCY)
# -------------------------------------------------------------
def _crc16(data: str) -> int:
    crc = 0xFFFF
    for ch in data.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def emv_fields(raw: str) -> dict:
    """Parse EMV TLV sequential dari awal string QR."""
    out, i = {}, 0
    while i + 4 <= len(raw):
        try:
            tag, ln = raw[i:i + 2], int(raw[i + 2:i + 4])
        except ValueError:
            break
        val = raw[i + 4:i + 4 + ln]
        if len(val) < ln:
            break
        out.setdefault(tag, val)
        i += 4 + ln
    return out


def inspect_qr(raw: str) -> dict:
    """Inspeksi offline format QRIS: validitas CRC, tipe dinamis/statis, merchant, dan nominal."""
    raw = (raw or "").strip()
    info = {"raw_len": len(raw), "ok": False}
    if len(raw) < 20 or not raw.startswith("00"):
        info["err"] = "Bukan format QRIS yang valid (Tag 00 tidak ditemukan)"
        return info

    crc_tag, body = raw[-4:], raw[:-4]
    info["crc_ok"] = f"{_crc16(body):04X}".upper() == crc_tag.upper()
    f = emv_fields(raw)
    info["fields"] = f
    info["merchant"] = (f.get("59") or f.get("58") or "Merchant").strip()
    info["mcc"] = f.get("52")
    info["currency"] = f.get("53")
    info["poi_method"] = f.get("01")  # 02 = statis, 12 = dinamis
    info["reference"] = f.get("62") or ""

    amt54 = f.get("54")
    if amt54:
        try:
            info["amount_tag54"] = float(int(amt54))
        except ValueError:
            info["amount_tag54"] = None
    else:
        info["amount_tag54"] = None

    info["dynamic"] = bool(amt54)
    info["ok"] = info["crc_ok"] and bool(f.get("26"))
    return info


# -------------------------------------------------------------
# 2. SOF (SOURCE OF FUNDS) DECRYPTION (AES KEY2)
# -------------------------------------------------------------
def bonbal_pm(inq_data: dict, sess: tuple, rts: str) -> dict | None:
    """Mendekripsi Source of Funds (SOF) LinkAja menggunakan Key2."""
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    sof = None
    for sec in (inq_data.get("detail") or []):
        if sec.get("id") == 3:
            for it in (sec.get("data") or []):
                if (it.get("themes") or {}).get("style") == ["ENCRYPTED"]:
                    sof = it.get("value")
                    break
    if not sof:
        return None

    k2 = shared.get("key2", "")
    if len(k2) < 16:
        return None

    try:
        blob = base64.b64decode(sof)
    except Exception:
        return None

    if not blob or len(blob) % 16:
        return None

    n = len(k2)
    gks = [df.get_key(k2, VER)]
    gks += ["".join(k2[(off + i) % n] for i in range(16)) for off in range(n)]

    _xr = lambda d, k: bytes(d[i] ^ k[i % len(k)] for i in range(len(d)))
    _mask = lambda b: bytes(((x & 0x3f) << 2) & 0xff for x in b)

    for gk in gks:
        if not gk:
            continue
        key32 = _mask(_xr(imsi.encode() + gk.encode(), (did + rts).encode()))
        iv = (_mask(_xr(rts.encode(), gk.encode())) + b"\x00" * 16)[:16]
        try:
            first = AES.new(key32, AES.MODE_CBC, iv).decrypt(blob[:16])
        except Exception:
            continue
        if first[:1] not in (b"{", b"["):
            continue
        pt = AES.new(key32, AES.MODE_CBC, iv).decrypt(blob)
        pad = pt[-1] if pt[-1] <= 16 else 0
        try:
            pms = json.loads(pt[:len(pt) - pad].decode())
        except Exception:
            continue

        pms_list = pms if isinstance(pms, list) else [pms]
        # Prioritas 1: Split payment yang ENABLED
        for pm in pms_list:
            if isinstance(pm, dict) and pm.get("isBonbal") and pm.get("isEnable", True):
                return pm

        # Prioritas 2: Reguler LinkAja yang ENABLED (code 09110)
        for pm in pms_list:
            if isinstance(pm, dict) and pm.get("code") == "09110" and pm.get("isEnable", True):
                return pm

        # Prioritas 3: Fallback sembarang isBonbal
        for pm in pms_list:
            if isinstance(pm, dict) and pm.get("isBonbal"):
                return pm

        # Prioritas 4: Fallback sembarang code 09110
        for pm in pms_list:
            if isinstance(pm, dict) and pm.get("code") == "09110":
                return pm
    return None


# -------------------------------------------------------------
# 3. QRIS API PIPELINE
# -------------------------------------------------------------
def qr_parse(sess: tuple, msisdn: str, raw_qr: str, jwt: str) -> dict | None:
    """POST /transaction/qr/parse."""
    ts = str(int(time.time() * 1000))
    extra = {"x-koya-geheim": ts}
    payload = {"input": raw_qr, "msisdn": msisdn}
    token = f"Bearer {jwt}"
    r = session.api_post(sess, "/transaction/qr/parse", payload, token=token, ts=ts, extra_headers=extra)
    if r.status_code != 200:
        return None
    st = {"ident": sess[0], "shared": sess[1]}
    j = session.decrypt_resp(r, st)
    if j.get("status") != "00":
        return None
    return j.get("data", {})


def qr_inquiry(sess: tuple, msisdn: str, parse_id: str, amount: float, jwt: str) -> tuple[dict | None, str, str]:
    """POST /transaction/qr/inquiry. Return (inq_data, rts, err_msg)."""
    ts = str(int(time.time() * 1000))
    extra = {"x-koya-geheim": ts}
    payload = {
        "origin": msisdn,
        "parseId": parse_id,
        "tipId": None,
        "amount": float(amount),
        "isUseBonbal": True,
        "promoCodes": []
    }
    token = f"Bearer {jwt}"
    r = session.api_post(sess, "/transaction/qr/inquiry", payload, token=token, ts=ts, extra_headers=extra)
    rts = r.headers.get("timestamp", "")
    if r.status_code != 200:
        return None, rts, f"HTTP Error {r.status_code}"
    st = {"ident": sess[0], "shared": sess[1]}
    j = session.decrypt_resp(r, st)
    if j.get("status") != "00":
        return None, rts, f"{j.get('status')} | {j.get('message', 'Inquiry ditolak')}"
    return j.get("data", {}), rts, ""


def qr_confirm(sess: tuple, msisdn: str, trx_id: str, pin: str, pm: dict, jwt: str) -> dict | None:
    """POST /transaction/qr/confirm dengan PIN terenkripsi."""
    ts = str(int(time.time() * 1000))
    key32 = hashlib.sha256(ENC_KEY.encode()).hexdigest()[:32]
    pin_enc = pin_crypto.encrypt_plain_text(pin, key32, ts)
    payload = {
        "transactionId": trx_id,
        "code": pm.get("code", "09110"),
        "bankCode": pm.get("bankCode", "09110"),
        "cardId": pm.get("cardId", msisdn),
        "sid": pm.get("sid", msisdn),
        "pin": pin_enc
    }
    extra = {"x-koya-geheim": ts}
    token = f"Bearer {jwt}"
    r = session.api_post(sess, "/transaction/qr/confirm", payload, token=token, ts=ts, extra_headers=extra)
    if r.status_code != 200:
        return None
    st = {"ident": sess[0], "shared": sess[1]}
    j = session.decrypt_resp(r, st)
    status_code = j.get("status")
    if status_code in ("00", "60010011"):
        return {
            "success": True,
            "status": status_code,
            "pending": (status_code == "60010011"),
            "message": j.get("message", "Sukses"),
            "data": j.get("data", {})
        }
    return {
        "success": False,
        "status": status_code,
        "message": j.get("message", "Konfirmasi ditolak"),
        "data": j.get("data", {})
    }


# -------------------------------------------------------------
# 4. HIGH-LEVEL EXECUTOR PER AKUN
# -------------------------------------------------------------
def check_account_balance(sess: tuple, jwt: str, st: dict) -> tuple[int, int]:
    """Cek Saldo Utama dan Saldo Bonus secara live langsung dari server LinkAja."""
    token = f"Bearer {jwt}"
    saldo_utama = 0
    bonus_poin = 0
    try:
        r_bal = session.api_get(sess, "/user/balance", token=token)
        if r_bal.status_code == 200:
            d_bal = session.decrypt_resp(r_bal, st)
            raw_v = (d_bal.get("data") or {}).get("value", 0)
            saldo_utama = int("".join(filter(str.isdigit, str(raw_v))) or 0)
    except Exception:
        pass

    try:
        r_pt = session.api_get(sess, "/user/point", token=token)
        if r_pt.status_code == 200:
            d_pt = session.decrypt_resp(r_pt, st)
            raw_p = (d_pt.get("data") or {}).get("total", 0)
            bonus_poin = int("".join(filter(str.isdigit, str(raw_p))) or 0)
    except Exception:
        pass

    return saldo_utama, bonus_poin


def pay_account_qris(state_file_path: str, raw_qr: str, pin_fallback: str = "888999", custom_amount: float = None) -> tuple[bool, str, dict]:
    """Eksekusi pembayaran QRIS untuk 1 file state akun.
    
    Mendukung penggabungan Saldo Bonus + Saldo Utama secara otomatis.
    Returns: (is_success: bool, status_msg: str, detail_dict: dict)
    """
    try:
        with open(state_file_path, "r") as f:
            st = json.load(f)
    except Exception as e:
        return False, f"Gagal membaca file state: {e}", {}

    msisdn = st.get("msisdn")
    jwt = st.get("jwt")
    rt = st.get("refreshToken")
    pin = st.get("pin") or pin_fallback

    if not msisdn or not jwt:
        return False, "Data akun tidak lengkap (msisdn atau jwt tidak ada)", {}

    sess = (st["ident"], st["shared"])

    # 1. Inspeksi format lokal
    inspect = inspect_qr(raw_qr)
    if not inspect["ok"]:
        return False, f"Format QRIS tidak valid ({inspect.get('err', 'CRC Error')})", {}

    # 2. Parse ke server LinkAja (auto refresh jika token expired)
    parse_data = qr_parse(sess, msisdn, raw_qr, jwt)
    if not parse_data and rt:
        # Coba auto-refresh token
        res_ref = session.api_post(sess, "/auth/session/refresh", {"token": jwt, "refreshToken": rt})
        if res_ref.status_code == 200:
            d_ref = session.decrypt_resp(res_ref, st)
            if d_ref.get("status") == "00":
                jwt = d_ref["data"]["token"]
                rt = d_ref["data"].get("refreshToken", rt)
                st["jwt"] = jwt
                st["refreshToken"] = rt
                with open(state_file_path, "w") as f:
                    json.dump(st, f, indent=2, ensure_ascii=False)
                parse_data = qr_parse(sess, msisdn, raw_qr, jwt)

    if not parse_data or not parse_data.get("parseId"):
        return False, "Parse QRIS ke server LinkAja gagal (QR kadaluarsa atau tidak aktif)", {}

    parse_id = parse_data["parseId"]
    merchant_name = parse_data.get("merchantName") or inspect.get("merchant") or "Merchant"
    srv_amount = parse_data.get("amount")

    # Nominal yang akan dibayar: custom > server parse > tag54
    nominal = custom_amount or srv_amount or inspect.get("amount_tag54")
    if not nominal or nominal <= 0:
        return False, "Nominal transaksi tidak terdeteksi (Gunakan QR Dinamis yang ber-nominal)", {}

    nominal = float(nominal)

    # 3. Inquiry Transaksi (isUseBonbal: True)
    inq_data, rts, err = qr_inquiry(sess, msisdn, parse_id, nominal, jwt)
    if not inq_data:
        return False, f"Inquiry gagal: {err}", {"merchant": merchant_name, "nominal": nominal}

    trx_id = inq_data.get("transactionId")
    if not trx_id:
        return False, "Tidak mendapatkan transactionId dari server", {}

    # 4. Dekripsi Source of Funds (SOF)
    pm = bonbal_pm(inq_data, sess, rts)
    if not pm:
        return False, "Gagal mendekripsi metode pembayaran / SOF akun", {}

    # Validasi gabungan Saldo Bonus + Saldo Utama (LinkAja menyimpan saldo utama di 'limitAmount')
    bonbal = float(pm.get("bonbal") or 0)
    balance = float(pm.get("limitAmount") or pm.get("balance") or 0)
    total_daya_beli = bonbal + balance

    if total_daya_beli < nominal:
        return False, (
            f"Saldo tidak cukup (Butuh: Rp {int(nominal):,} | "
            f"Tersedia: Rp {int(total_daya_beli):,} [Bonus: Rp {int(bonbal):,} + Utama: Rp {int(balance):,}])"
        ), {"merchant": merchant_name, "nominal": nominal, "bonbal": bonbal, "balance": balance}

    # 5. Konfirmasi Pembayaran
    conf = qr_confirm(sess, msisdn, trx_id, pin, pm, jwt)
    if not conf or not conf.get("success"):
        msg = conf.get("message", "Konfirmasi ditolak server") if conf else "Gagal konfirmasi pembayaran"
        return False, msg, {"merchant": merchant_name, "nominal": nominal}

    # 6. Verifikasi Saldo Real-Time (Anti-Transaksi Gantung di Switch LinkAja)
    expected_bonbal_used = min(bonbal, nominal)
    expected_balance_used = max(0.0, nominal - bonbal)

    # Jeda 1.5 detik agar database core LinkAja & switch merampungkan pencatatan ledger
    time.sleep(1.5)
    saldo_after, bonus_after = check_account_balance(sess, jwt, st)

    # Jika saldo utama seharusnya berkurang tapi masih utuh, polling verifikasi hingga 2 kali lagi
    if expected_balance_used > 0 and saldo_after >= balance:
        for _ in range(2):
            time.sleep(1.5)
            saldo_after, bonus_after = check_account_balance(sess, jwt, st)
            if saldo_after < balance:
                break

    actual_balance_deducted = max(0.0, balance - saldo_after)
    actual_bonbal_deducted = max(0.0, bonbal - bonus_after)

    # DETEKSI ANOMALI: Saldo utama tidak terpotong sama sekali padahal nominal butuh saldo utama
    if expected_balance_used > 0 and actual_balance_deducted < (expected_balance_used * 0.8):
        status_code = conf.get("status", "60010011")
        err_msg = (
            f"Transaksi Gantung di Switch LinkAja ({status_code})! "
            f"Saldo Utama BELUM terpotong (masih Rp {int(saldo_after):,}) dan uang belum masuk merchant."
        )
        return False, err_msg, {
            "merchant": merchant_name,
            "nominal": nominal,
            "transactionId": trx_id,
            "gantung": True,
            "saldo_utama_sisa": saldo_after,
            "bonus_sisa": bonus_after,
            "bonbal_used": actual_bonbal_deducted,
            "balance_used": actual_balance_deducted
        }

    return True, conf.get("message", "Sukses (Terkonfirmasi)"), {
        "merchant": merchant_name,
        "nominal": nominal,
        "transactionId": trx_id,
        "pending": False,
        "bonbal_used": actual_bonbal_deducted if actual_bonbal_deducted > 0 else expected_bonbal_used,
        "balance_used": actual_balance_deducted if actual_balance_deducted > 0 else expected_balance_used
    }
