#!/usr/bin/env python3
"""ljreg — pendaftaran akun LinkAja device-free + pasang ke HP."""

import sys
import os
import time
import json
import random
import base64
import hashlib
import hmac
import requests
import threading
import shutil
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# 1. AUTO-CREATE FIS.JSON (HARUS PALING ATAS)
# ==========================================
def setup_fis_json():
    # Menentukan path folder data dan file fis.json
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    fis_path = data_dir / "fis.json"
    
    # Membuat file beserta isinya jika belum ada
    if not fis_path.exists():
        fis_content = {
            "name": "projects/891651208293/installations/cP3nmU9n-zSU-5PAJtD5AH", 
            "fid": "cP3nmU9n-zSU-5PAJtD5AH", 
            "refreshToken": "3_AS3qfwL3HVGML5Hb2ae-XWv31gcYcBjXjO1qTE9fqvrGdRShdVQkkAy3nImbRMckB0r-kOaOfgUYjhBbD-hAb2bEs5IugkAQhqdtBXIBRwdoUb4", 
            "authToken": {
                "token": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjE6ODkxNjUxMjA4MjkzOmFuZHJvaWQ6ZDYyZjgyY2Y3NTllYjRmNCIsImV4cCI6MTc5MTgyOTk0MywiZmlkIjoiY1Azbm1VOW4telNVLTVQQUp0RDVBSCIsInByb2plY3ROdW1iZXIiOjg5MTY1MTIwODI5M30.AB2LPV8wRQIhAK3dEEtmGuRW5il_751LCfalD4--CbsamMIedF2dfUX1AiALJ-uPLjTox79Kzkh0L4s1c8Peh666YixMPWBB7FYrkA", 
                "expiresIn": "604800s"
            }
        }
        with open(fis_path, "w", encoding="utf-8") as f:
            json.dump(fis_content, f, indent=4)

# Eksekusi pembuatan fis.json SEBELUM import modul core
setup_fis_json()

# ==========================================
# 2. IMPORT CORE & RICH 
# ==========================================
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box 

from core import regis
from core.regis import RegisError
from core.session import list_states, state_path, api_get, api_post, decrypt_resp

console = Console()

# ==========================================
# 3. KONFIGURASI AUTO-UPDATE SENYAP
# ==========================================
GITHUB_RAW_URL = "https://raw.githubusercontent.com/canntona/gurih/refs/heads/main/bot.py"

def auto_update():
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            remote_code = response.read().decode('utf-8')

        with open(__file__, "r", encoding="utf-8") as f:
            local_code = f.read()

        if remote_code.strip() != local_code.strip():
            console.print("\n[bold bright_yellow]⚡ Memperbarui sistem ke versi terbaru...[/bold bright_yellow]")
            with open(__file__, "w", encoding="utf-8") as f:
                f.write(remote_code)
            os.execv(sys.executable, ['python'] + sys.argv)
            
    except Exception:
        # Senyap jika gagal atau offline
        pass


# ==========================================
# 4. FUNGSI LOAD API KEY
# ==========================================
def load_api_key():
    api_file = "api.txt"
    if os.path.exists(api_file):
        with open(api_file, "r") as f:
            key = f.read().strip()
            if key:
                return key
                
    console.print(Panel("[bold yellow]API Key belum dikonfigurasi![/]", width=50))
    new_key = Prompt.ask("[bold cyan]Masukkan API Key OTPInstan kamu[/]").strip()
    
    with open(api_file, "w") as f:
        f.write(new_key)
        
    console.print("[green]✅ API Key berhasil disimpan ke [bold]api.txt[/][/]\n")
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
# =======================

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

def clear_once():
    os.system("cls" if os.name == "nt" else "clear")

# ==========================================
# FUNGSI HELPER OTP MULTI-SERVER
# ==========================================
def batalkan_pesanan(base_s, srv, order_id):
    if not order_id: return
    h = {"X-Api-Key": API_KEY_OTP}
    try:
        if srv == "1":
            h["Content-Type"] = "application/json"
            requests.post(f"{base_s}/cancel.php", headers=h, json={"order_id": order_id}, timeout=5)
        else:
            requests.post(f"{base_s}/cancel.php", headers=h, data={"order_id": order_id}, timeout=5)
    except: pass

def cek_status_otp(base_s, order_id):
    try:
        res = requests.get(f"{base_s}/check.php", params={"order_id": order_id}, headers={"X-Api-Key": API_KEY_OTP}, timeout=8).json()
        d = res.get("data", res)
        if isinstance(d, list) and len(d) > 0: d = d[0]
        if isinstance(d, dict): return d.get("otp_code", d.get("otp", d.get("sms")))
    except: pass
    return None

# ==========================================
# ENGINE TERMUX ROOT INJECT (MODUL 5)
# ==========================================
class InjectError(Exception): pass

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
        if out.strip() != "0": raise InjectError(f"su jalan tapi uid={out} — bukan root")
    except FileNotFoundError: raise InjectError("`su` gak ada — HP belum rooted / KernelSU gak kasih grant")
    except subprocess.TimeoutExpired: raise InjectError("su timeout — prompt grant mungkin belum di-approve")

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
        if h in store: return f'<string name="{h}">{store[h]}</string>'
        return m.group(0)
    return re.sub(r'<string name="([0-9a-f]+)">[^<]*</string>', repl, orig_text)

def _pull_xml_la(name: str) -> str: return termux_su(f"cat {PREF_DIR_LA}/{name}")
def _install_xml_la(name: str, xml_text: str): termux_su(f"cat > {PREF_DIR_LA}/{name}", input_bytes=xml_text.encode())

def _device_backup_once_la():
    out = termux_su(f"ls /data/local/tmp/Core.xml.bak 2>/dev/null || echo NOPE")
    if "Core.xml.bak" in out: return
    termux_su(f"cp {PREF_DIR_LA}/Core.xml /data/local/tmp/Core.xml.bak && cp {PREF_DIR_LA}/Security.xml /data/local/tmp/Security.xml.bak")
    console.print("  [dim]💾 backup device pertama → /data/local/tmp/*.bak[/]")

def inject_termux_account(state_path: str):
    t0 = time.time()
    try:
        st = json.load(open(state_path))
        m, ident, shared = st.get("msisdn"), st.get("ident"), st.get("shared")
        jwt, rt = st.get("jwt"), st.get("refreshToken")
        if not (jwt and rt and ident and shared):
            raise InjectError("State rusak atau belum selesai daftar (tidak ada token)")
    except Exception as e:
        raise InjectError(f"Gagal baca JSON: {e}")

    console.print(f"🔍 [dim]Root check...[/]")
    check_root_termux()

    console.print(f"📖 [dim]Baca prefs XML device...[/]")
    try:
        core_xml = _pull_xml_la("Core.xml"); sec_xml = _pull_xml_la("Security.xml")
    except InjectError as e:
        raise InjectError(f"Gagal baca prefs app LinkAja (pastikan sudah pernah login sekali): {e}")
        
    core, sec = load_prefs_xml_la(core_xml), load_prefs_xml_la(sec_xml)

    token_json = json.dumps({"token": jwt, "refreshToken": rt}, separators=(",", ":"))
    reps_core = {
        "DEVICE_ID": ident["deviceId"], "IMSI": ident["imsi"],
        "ADS_ID": ident.get("adsId", ""), "USER_PHONE_NUMBER": m,
        "AUTHORIZATION_TOKEN": token_json,
    }
    reps_sec = {"keyX1": shared["key1"], "keyX2": shared["key2"], "keyX3": shared["key3"]}

    for store, reps, fname in ((core, reps_core, "Core.xml"), (sec, reps_sec, "Security.xml")):
        for name in reps:
            if pref_name_hash_la(name) not in store:
                raise InjectError(f"Entry XML '{name}' tidak ketemu di {fname} — app LinkAja HP ini belum pernah login. Batal.")

    console.print("💾 [dim]Backup XML asli...[/]")
    _device_backup_once_la()
    bdir = os.path.join(BACKUP_ROOT_LA, m)
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    open(os.path.join(bdir, f"Core.xml.{stamp}.orig"), "w").write(core_xml)
    open(os.path.join(bdir, f"Security.xml.{stamp}.orig"), "w").write(sec_xml)

    console.print("🔐 [dim]Encrypt + susun XML baru...[/]")
    for store, reps in ((core, reps_core), (sec, reps_sec)):
        for name, val in reps.items():
            store[pref_name_hash_la(name)] = pref_value_encrypt_la(name, val.encode())
            
    core_new = dump_xml_la(core, core_xml); sec_new = dump_xml_la(sec, sec_xml)

    console.print("🚀 [dim]Force-stop app + timpa prefs...[/]")
    termux_su(f"am force-stop {PACKAGE_LA}")
    _install_xml_la("Core.xml", core_new); _install_xml_la("Security.xml", sec_new)

    console.print("📁 [dim]Pindah state ke backup...[/]")
    os.makedirs(STATE_BACKUP_DIR, exist_ok=True)
    dest = os.path.join(STATE_BACKUP_DIR, os.path.basename(state_path))
    if os.path.exists(dest):
        base, ext = os.path.splitext(os.path.basename(state_path))
        dest = os.path.join(STATE_BACKUP_DIR, f"{base}_{stamp}{ext}")
    shutil.move(state_path, dest)

    el = round(time.time() - t0, 1)
    console.print(f"[bold green]🎉 {m} sukses terpasang ({el}s)![/]")
    console.print("[green]Silakan buka app LinkAja sekarang, akun otomatis masuk![/]")

# ==========================================
# MENU 1 & 2: PENDAFTARAN & AUTO BULK 
# ==========================================
def menu_daftar_manual():
    console.print(Panel("[bold]Daftar Akun Manual[/]\nOTP masuk ke SMS HP lo sendiri.", style="bright_yellow"))
    try:
        msisdn = regis.normalize_msisdn(Prompt.ask("[bold]Nomor HP[/] (mis. 08123456789)"))
    except RegisError as e:
        console.print(f"[red]❌ {e}[/]")
        return

def worker_register_scheduled(worker_id, target_mulai, target_kirim_data, pilihan_server, config_api):
    w_log = f"[W-{worker_id}]"
    sekarang = datetime.now()
    dt_mulai = None
    dt_kirim = None
    batas_aman = None
    
    base_url = "https://otpinstan.com/api/reseller"
    base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url

    if target_mulai.strip():
        jam_mulai = datetime.strptime(target_mulai.strip(), "%H:%M:%S").time()
        dt_mulai = datetime.combine(sekarang.date(), jam_mulai)
        if dt_mulai < sekarang: dt_mulai += timedelta(days=1)
            
    if target_kirim_data.strip():
        jam_kirim = datetime.strptime(target_kirim_data.strip(), "%H:%M:%S").time()
        patokan_hari = dt_mulai.date() if dt_mulai else sekarang.date()
        dt_kirim = datetime.combine(patokan_hari, jam_kirim)
        if dt_kirim < (dt_mulai if dt_mulai else sekarang): dt_kirim += timedelta(days=1)
        batas_aman = dt_kirim - timedelta(seconds=40)

    if dt_mulai:
        console.print(f"[dim]{w_log} ⏳ Standby {dt_mulai.strftime('%H:%M:%S')}...[/]")
        while datetime.now() < dt_mulai: time.sleep(1)

    service_id = config_api["service_id"]
    country_id = config_api["country_id"]
    provider_id = config_api["provider_id"]
    
    maksimal_ganti_nomor = 3
    otp_code = None
    msisdn = None
    
    # --- SISTEM 3 STRIKES ---
    for attempt in range(1, maksimal_ganti_nomor + 1):
        if batas_aman and datetime.now() >= batas_aman and attempt == 1:
            console.print(f"[red]{w_log} ❌ Zona Merah (Batal)[/]")
            return

        console.print(f"[cyan]{w_log} 🔄 Req No ({attempt}/3)...[/]")
        order_id = None; raw_number = None
        
        for tarik_attempt in range(20):
            try:
                if pilihan_server == "1":
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
                        console.print(f"[red]{w_log} ❌ Saldo Habis![/]")
                        return
                    else:
                        for _ in range(15): time.sleep(0.1)
                        continue

                data_order = res_o.get('data', res_o)
                order_id = data_order.get('order_id', data_order.get('id'))
                raw_number = data_order.get('phone', data_order.get('number'))
                console.print(f"[green]{w_log} 📱 {raw_number}[/]")
                break 
            except:
                time.sleep(2)
                continue
        
        if not order_id:
            console.print(f"[red]{w_log} ❌ No Zonk[/]")
            continue

        try:
            msisdn = regis.normalize_msisdn(raw_number)
            registered, info = regis.step_check(msisdn)
            if registered:
                console.print(f"[yellow]{w_log} ⚠ Terdaftar[/]")
                try: state_path(msisdn).unlink(missing_ok=True)
                except: pass
                continue
        except RegisError:
            try: state_path(msisdn).unlink(missing_ok=True)
            except: pass
            continue

        console.print(f"[yellow]{w_log} 🚀 Req OTP[/]")
        try: 
            regis.step_send_otp(msisdn)
        except RegisError:
            try: state_path(msisdn).unlink(missing_ok=True)
            except: pass
            continue

        # --- ARGOMETER 55 DETIK ---
        total_cek = 55 // 5
        for i in range(total_cek):
            time.sleep(5)
            otp_code = cek_status_otp(base_s, order_id)
            if otp_code:
                console.print(f"[green]{w_log} ✅ OTP: {otp_code}[/]")
                break
                
        if otp_code:
            break 
        else:
            console.print(f"[red]{w_log} ❌ Timeout (Ghosting)[/]")
            try: state_path(msisdn).unlink(missing_ok=True)
            except: pass
            continue

    if not otp_code:
        console.print(f"[red]{w_log} ❌ Gagal Total (3x)[/]")
        return

    # --- FASE EKSEKUSI ---
    fullname, email = generate_random_identity()
    pin = PIN_KUNCI
    
    try:
        regis.step_validate(msisdn, otp_code)
        console.print(f"[green]{w_log} ✅ Valid OK[/]")
    except RegisError:
        console.print(f"[red]{w_log} ❌ Valid Gagal[/]")
        try: state_path(msisdn).unlink(missing_ok=True)
        except: pass
        return

    if dt_kirim:
        if datetime.now() < dt_kirim:
            console.print(f"[cyan]{w_log} 🎯 Siaga Cut-off {dt_kirim.strftime('%H:%M:%S')}[/]")
            while True:
                sisa = (dt_kirim - datetime.now()).total_seconds()
                if sisa <= 0: break 
                elif sisa > 0.5: time.sleep(0.1)   
                elif sisa > 0.05: time.sleep(0.01)  
        else:
            console.print(f"[yellow]{w_log} ⚡ Terjang![/]")

    for r in range(3):
        try:
            # POST Register meluncur...
            regis.step_register(msisdn, pin, fullname, email)
            
            # Menangkap waktu presisi (Jam:Menit:Detik.Milidetik) tepat setelah server membalas SUKSES
            waktu_sukses = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            
            console.print(f"[bold green]🎉 {w_log} SUKSES [{waktu_sukses}] | {msisdn} | {fullname}[/]")
            return 
        except:
            if r < 2:
                time.sleep(1) 
            else:
                console.print(f"[red]{w_log} ❌ Final Gagal[/]")
                try: state_path(msisdn).unlink(missing_ok=True)
                except: pass
                return

def menu_daftar_auto_bulk():
    console.print(Panel("[bold bright_yellow]Daftar Akun Massal Berjadwal (Scheduled Bulk)[/]", style="bright_yellow"))
    pilihan_server = Prompt.ask("[bold]Pilih Server API OTPInstan[/] (1 atau 2)", choices=["1", "2"], default="1")
    jumlah_akun = int(Prompt.ask("[bold]Masukkan jumlah akun (1 - 20)[/]", default="1"))
    target_mulai = Prompt.ask("[bold]Jam mulai pendaftaran[/] (HH:MM:SS, kosongkan jika instan)", default="")
    target_kirim_data = Prompt.ask("[bold]Jam kirim data diri[/] (HH:MM:SS, kosongkan jika langsung setelah validasi)", default="")

    console.print("[dim]🔄 Init API...[/]")
    
    base_url = "https://otpinstan.com/api/reseller"
    base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url
    headers_get = {"X-Api-Key": API_KEY_OTP}

    try:
        res_c = requests.get(f"{base_s}/countries.php", headers=headers_get, timeout=10).json()
        countries = res_c.get("data", res_c) if isinstance(res_c, dict) else res_c
        if isinstance(countries, dict): countries = [{"id": k, **v} if isinstance(v, dict) else v for k, v in countries.items()]
        country_id = next((c.get("id", c.get("country_id")) for c in (countries if isinstance(countries, list) else []) 
                           if "indonesia" in str(c.get("name", c.get("country_name", "Unknown"))).lower()), None)

        res_s = requests.get(f"{base_s}/services.php", params={"country_id": country_id} if pilihan_server=="1" else None, headers=headers_get, timeout=10).json()
        services = res_s.get("data", res_s) if isinstance(res_s, dict) else res_s
        if isinstance(services, dict): services = [{"platform_id": k, **v} if isinstance(v, dict) else v for k, v in services.items()]
        valid_services = [s for s in (services if isinstance(services, list) else [])
                          if "linkaja" in str(s.get("name", s.get("service_name", ""))).lower()
                          and int(s.get("stock", s.get("count", s.get("qty", 0)))) > 0]
        
        if not valid_services:
            console.print("[red]❌ Stok Kosong![/]")
            return
            
        valid_services.sort(key=lambda x: float(x.get("price", 0)))
        service_id = valid_services[0].get("platform_id", valid_services[0].get("id", valid_services[0].get("service")))
        
        provider_id = "any"
        harga_info = valid_services[0].get("price", "?")

        if pilihan_server == "2":
            res_op = requests.get(f"{base_url}/operators.php", params={"service": service_id, "country": country_id}, headers=headers_get, timeout=10).json()
            operators = res_op.get("data", res_op) if isinstance(res_op, dict) else res_op
            valid_operators = [o for o in (operators if isinstance(operators, list) else []) if int(o.get("stock", o.get("count", o.get("qty", 0)))) > 0]
            if valid_operators:
                valid_operators.sort(key=lambda x: float(x.get("price", 0)))
                provider_id = valid_operators[0].get("value", valid_operators[0].get("provider_id", valid_operators[0].get("id")))
                harga_info = valid_operators[0].get('price', '?')

        config_api = {
            "country_id": country_id,
            "service_id": service_id,
            "provider_id": provider_id
        }
        
    except:
        console.print("[red]❌ API Down![/]")
        return

    console.print(f"[green]✅ Layanan OK (Rp {harga_info}). Start {jumlah_akun} worker...[/]\n")
    
    threads = []
    for i in range(1, jumlah_akun + 1):
        t = threading.Thread(target=worker_register_scheduled, args=(i, target_mulai, target_kirim_data, pilihan_server, config_api))
        threads.append(t)
        t.start()
        time.sleep(0.8) 
        
    for t in threads: t.join()
    console.print("\n[bold green]✨ Bulk Register Selesai![/]")


# ==========================================
# MENU 3: ADB PUSH (INJECT)
# ==========================================
def menu_inject():
    console.print(Panel("[bold bright_yellow]ADB Push Akun (Inject)[/]", style="bright_yellow"))
    states = list_states()
    if not states:
        console.print("[yellow]⚠ Tidak ada akun baru di folder data/states.[/]")
        return
    from core import inject
    try:
        adb_bin = inject.find_adb()
        devs = inject.list_devices(adb_bin)
    except:
        console.print("[red]❌ Error ADB[/]"); return

    if not devs:
        console.print("[red]❌ Device tidak ditemukan.[/]"); return

    total_inject = min(len(states), len(devs))
    if Prompt.ask("[bold]Mulai push otomatis?[/] (y/n)", default="y").lower() != 'y': return
    
    for i in range(total_inject):
        akun = states[i]; serial_hp = devs[i]
        console.print(f"[cyan]📲 HP {serial_hp} ← {akun['msisdn']}[/]")
        try:
            inject.inject_account(akun["file"], adb_serial=serial_hp, progress=lambda m: None)
            console.print("[green]  ✅ Sukses[/]")
        except:
            console.print("[red]  ❌ Gagal[/]")


# ==========================================
# MENU 4: CEK BONUS
# ==========================================
def proses_cek_satu_akun(akun):
    try:
        with open(akun["file"], "r") as f: st = json.load(f)
        jwt = st.get("jwt"); rt = st.get("refreshToken")
        if not jwt: return "0", "0", "[red]No Token[/]"
            
        sess = (st["ident"], st["shared"])
        token_auth = f"Bearer {jwt}"
        
        res_bal = api_get(sess, "/user/balance", token=token_auth)
        data_bal = decrypt_resp(res_bal, st) if res_bal.status_code == 200 else {}
        
        if res_bal.status_code == 401 or data_bal.get("status") != "00":
            if not rt: return "0", "0", "[red]Sesi Mati[/]"
            res_ref = api_post(sess, "/auth/session/refresh", {"token": jwt, "refreshToken": rt})
            data_ref = decrypt_resp(res_ref, st) if res_ref.status_code == 200 else {}
            
            if data_ref.get("status") == "00":
                jwt = data_ref["data"]["token"]; rt = data_ref["data"]["refreshToken"]
                st["jwt"] = jwt; st["refreshToken"] = rt
                with open(akun["file"], "w") as f: json.dump(st, f, ensure_ascii=False, indent=2)
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

        status_msg = "[bold bright_green]Masuk![/]" if int(bonus_poin) >= 5000 else "[bright_yellow]Zonk[/]"
        return saldo_utama, bonus_poin, status_msg

    except: return "-", "-", "[red]Error[/]"

def menu_cek_saldo():
    console.print(Panel("[bold bright_yellow]Cek Bonus Massal[/]", style="bright_yellow"))
    if not CRYPTO_AVAILABLE:
        console.print("[red]❌ Library pycryptodome belum diinstall.[/red]"); return

    states = list_states()
    if not states:
        console.print("[yellow]⚠ Folder states kosong.[/]"); return
        
    table = Table(
        box=box.SIMPLE, 
        header_style="bold bright_white on blue",
        border_style="bright_cyan"
    )
    table.add_column("No", style="bright_cyan", justify="center")
    table.add_column("Nomor", style="bright_green")
    table.add_column("Saldo", justify="right", style="bright_yellow")
    table.add_column("Bonus", justify="right", style="bright_magenta")
    table.add_column("Status", justify="center")

    console.print(f"[dim]🔄 Cek {len(states)} akun...[/]")
    for idx, akun in enumerate(states, start=1):
        saldo_utama, bonus_poin, status_msg = proses_cek_satu_akun(akun)
        table.add_row(str(idx), akun.get("msisdn", "?"), f"Rp {saldo_utama}", f"{bonus_poin} pts", status_msg)
        time.sleep(0.3) 
    console.print(table)


# ==========================================
# MENU 5: INJECK TERMUX
# ==========================================
def menu_injeck_termux():
    console.print(Panel("[bold magenta]Injeck Termux (Root)[/]\nInject akun pertama dari data/states langsung ke HP ini via Superuser.", style="magenta"))
    
    if not CRYPTO_AVAILABLE:
        console.print("[red]❌ Library pycryptodome belum diinstall di Termux.[/red]")
        return
        
    states = list_states()
    if not states:
        console.print("[yellow]⚠ Folder data/states kosong. Tidak ada akun matang untuk di-inject.[/]")
        return
        
    akun_target = states[0]["file"]
    nomor = states[0].get("msisdn", "?")
    
    console.print(f"[cyan]Satu akun ditemukan siap inject: {nomor}[/]")
    if Prompt.ask(f"[bold]Inject akun ini ke perangkat sekarang?[/] (y/n)", default="y").lower() != 'y': 
        return
        
    try:
        inject_termux_account(akun_target)
    except InjectError as e:
        console.print(f"[red]❌ Gagal Inject: {e}[/]")
    except Exception as e:
        console.print(f"[red]❌ Error Sistem: {e}[/]")


# ==========================================
# MENU 6: SORTIR
# ==========================================
def menu_sortir():
    console.print(Panel("[bold bright_yellow]Sortir Akun Berdasarkan Bonus[/]\nMembuang otomatis file akun zonk (0) dan mempertahankan akun bonus 5000.", style="bright_yellow"))
    
    if not CRYPTO_AVAILABLE:
        console.print("[red]❌ Library pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow]⚠ Tidak ada akun di folder data/states untuk disortir.[/]")
        return

    # Siapkan folder tujuan HANYA untuk yang zonk (buangan)
    dir_base = Path(__file__).resolve().parent / "data"
    dir_zonk = dir_base / "states_zonk"
    
    # Buat folder zonk jika belum ada
    dir_zonk.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]🔄 Memulai cek dan sortir {len(states)} akun...[/]")
    
    count_bonus = 0
    count_zonk = 0
    count_error = 0

    for idx, akun in enumerate(states, start=1):
        file_path = Path(akun["file"])
        if not file_path.exists():
            continue
            
        msisdn = akun.get("msisdn", "?")
        
        # Cek saldo & bonus
        saldo_utama, bonus_poin, status_msg = proses_cek_satu_akun(akun)
        
        if bonus_poin == "-" or "Error" in status_msg or "Sesi Mati" in status_msg:
            console.print(f"[red]❌ {msisdn} - Error/Sesi Mati saat cek saldo. Dilewati.[/]")
            count_error += 1
            continue
            
        poin_int = int(bonus_poin) if str(bonus_poin).isdigit() else 0
        
        try:
            if poin_int >= 5000:
                # DIBIARKAN DI FOLDER ASLI
                console.print(f"[green]✅ {msisdn} -> AMAN ({poin_int} pts, dipertahankan di data/states/)[/]")
                count_bonus += 1
            else:
                # DIPINDAHKAN (DIBUANG) KE FOLDER ZONK
                shutil.move(str(file_path), str(dir_zonk / file_path.name))
                console.print(f"[yellow]⚠ {msisdn} -> DIBUANG ke folder ZONK ({poin_int} pts)[/]")
                count_zonk += 1
        except Exception as e:
            console.print(f"[red]❌ Gagal memindahkan file {msisdn}: {e}[/]")
            
        time.sleep(0.3) 

    # Rekapitulasi Akhir
    console.print(f"\n[bold green]✨ Sortir Selesai![/]")
    console.print(f"📁 Bonus (>= 5000) : {count_bonus} akun (Siap di-inject via Menu 3 di [cyan]data/states/[/])")
    console.print(f"🗑️ Zonk (< 5000)   : {count_zonk} akun dipindah ke [yellow]data/states_zonk/[/]")
    
    if count_error > 0:
        console.print(f"📁 Error Check     : {count_error} akun (tetap berada di folder data/states/)")


# ==========================================
# MASTER UI
# ==========================================
def main():
    clear_once()
    
    # --- ASCII ART RAVE of VOID ---
    void_art = """[bold bright_yellow]
8888888b.         d8888 888     888 8888888888         d8b 
888   Y88b       d88888 888     888 888                Y8P 
888    888      d88P888 888     888 888                    
888   d88P     d88P 888 Y88b   d88P 8888888    .d88b.  8888888 
8888888P"     d88P  888  Y88b d88P  888       d88""88b 888 
888 T88b     d88P   888   Y88o88P   888       888  888 8888888 
888  T88b   d8888888888    Y888P    888       Y88..88P 888 
888   T88b d88P     888     Y8P     8888888888 "Y88P"  888 

888     888  .d88888b.  8888888 8888888b.  
888     888 d88P" "Y88b   888   888  "Y88b 
888     888 888     888   888   888    888 
Y88b   d88P 888     888   888   888    888 
 Y88b d88P  888     888   888   888    888 
  Y88o88P   888     888   888   888    888 
   Y888P    Y88b. .d88P   888   888  .d88P 
    Y8P      "Y88888P"  8888888 8888888P"  
[/bold bright_yellow]"""
    
    while True:
        console.print(void_art)
        console.print("[bold yellow]⚡ COMMAND CENTER[/bold yellow]\n")
        
        # --- MENU TANPA BORDER & FULL KUNING ---
        menu_ui = (
            "[bold bright_yellow]1.[/] [bright_yellow]DAFTAR Manual[/]\n"
            "[bold bright_yellow]2.[/] [bright_yellow]DAFTAR OTOMATIS[/]\n"
            "[bold bright_yellow]3.[/] [bright_yellow]ADB PUSH KHUSUS PC [/]\n"
            "[bold bright_yellow]4.[/] [bright_yellow]CEK BONUS[/]\n"
            "[bold bright_yellow]5.[/] [bright_yellow]RESTORE TERMUX[/]\n"
            "[bold bright_yellow]6.[/] [bright_yellow]SORTIR[/]\n"
            "[bold bright_yellow]7.[/] [dim yellow]Keluar[/]"
        )
        
        console.print(menu_ui)
        
        c = Prompt.ask("\n[bold yellow]Pilih[/]", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")
        
        if c == "7":
            console.print("[dim]Keluar.[/]")
            break
        try:
            if c == "1": menu_daftar_manual()
            elif c == "2": console.print("\n"); menu_daftar_auto_bulk()
            elif c == "3": console.print("\n"); menu_inject()
            elif c == "4": console.print("\n"); menu_cek_saldo()
            elif c == "5": console.print("\n"); menu_injeck_termux()
            elif c == "6": console.print("\n"); menu_sortir()
            
            Prompt.ask("\n[dim]Tekan Enter untuk kembali ke menu...[/]")
            clear_once()
            
        except KeyboardInterrupt:
            console.print("\n[dim]Batal.[/]")
            clear_once()

if __name__ == "__main__":
    try:
        auto_update()  
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Stop (Ctrl+C).[/]")
