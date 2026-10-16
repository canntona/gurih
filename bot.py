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

# Coba import library kriptografi
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich import box

from core import regis
from core.regis import RegisError
from core.session import list_states, state_path, api_get, api_post, decrypt_resp

console = Console()

# ==========================================
# KONFIGURASI AUTO-UPDATE SENYAP
# ==========================================
# Dikosongkan agar tidak melakukan auto-update
GITHUB_RAW_URL = "https://raw.githubusercontent.com/canntona/gurih/refs/heads/main/bot.py"

def auto_update():
    if not GITHUB_RAW_URL.strip():
        return
    try:
        req = urllib.request.Request(GITHUB_RAW_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            remote_code = response.read().decode('utf-8')

        with open(__file__, "r", encoding="utf-8") as f:
            local_code = f.read()

        if remote_code.strip() != local_code.strip():
            console.print("\n[bold bright_yellow][!] Memperbarui sistem ke versi terbaru...[/bold bright_yellow]")
            with open(__file__, "w", encoding="utf-8") as f:
                f.write(remote_code)
            os.execv(sys.executable, ['python'] + sys.argv)
    except Exception:
        # Senyap jika gagal atau offline
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
            return d.get("otp_code", d.get("otp", d.get("sms")))
    except Exception:
        pass
    return None

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
    try:
        msisdn = regis.normalize_msisdn(Prompt.ask("[bold cyan]>> Nomor HP[/] [dim](mis. 08123456789)[/]"))
        console.print(f"[green][OK] Nomor tervalidasi:[/] [bold]{msisdn}[/]")
    except RegisError as e:
        console.print(f"[bold red][X] {e}[/]")
        return

# State terpusat untuk Live Dashboard Multi-Worker
WORKER_STATUS = {}
WORKER_LOCK = threading.Lock()

def update_worker_ui(worker_id, **kwargs):
    with WORKER_LOCK:
        if worker_id not in WORKER_STATUS:
            WORKER_STATUS[worker_id] = {
                "msisdn": "-",
                "attempt": "0/3",
                "otp": "-",
                "identity": "-",
                "status": "[dim]Menunggu...[/]",
                "state": "idle",  # idle, running, success, failed
            }
        WORKER_STATUS[worker_id].update(kwargs)

def build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim):
    table = Table(
        box=box.SIMPLE_HEAD,
        header_style="bold bright_cyan",
        border_style="bright_black",
        expand=True,
    )
    table.add_column("Worker", justify="center", style="bold cyan", width=8)
    table.add_column("Coba", justify="center", width=8)
    table.add_column("Nomor HP", style="bright_white", width=16)
    table.add_column("Kode OTP", justify="center", style="bold yellow", width=10)
    table.add_column("Identitas", style="dim", overflow="ellipsis")
    table.add_column("Status Real-Time", justify="left")

    sukses = 0
    gagal = 0
    berjalan = 0

    with WORKER_LOCK:
        for wid in sorted(WORKER_STATUS.keys()):
            info = WORKER_STATUS[wid]
            st = info.get("state", "running")
            if st == "success":
                sukses += 1
            elif st == "failed":
                gagal += 1
            else:
                berjalan += 1

            table.add_row(
                f"W-{wid:02d}",
                info["attempt"],
                info["msisdn"],
                info["otp"],
                info["identity"],
                info["status"],
            )

    info_jadwal = (
        f"[bold white]Server:[/] [cyan]S{pilihan_server}[/] (Rp {harga_info})  |  "
        f"[bold white]Start:[/] [yellow]{target_mulai or 'Instan'}[/]  |  "
        f"[bold white]Cut-off:[/] [yellow]{target_kirim or 'Langsung'}[/]  |  "
        f"[bold green][OK] Sukses: {sukses}[/]  "
        f"[bold cyan][..] Jalan: {berjalan}[/]  "
        f"[bold red][X] Gagal: {gagal}[/]"
    )

    return Panel(
        Group(
            Panel(info_jadwal, box=box.MINIMAL, style="on grey11"),
            table
        ),
        title="[bold bright_yellow][*] LIVE MONITOR BULK REGISTER[/]",
        border_style="bright_cyan",
        box=box.ROUNDED,
    )

def worker_register_scheduled(worker_id, target_mulai, target_kirim_data, pilihan_server, config_api):
    sekarang = datetime.now()
    dt_mulai = None
    dt_kirim = None
    batas_aman = None

    base_url = "https://otpinstan.com/api/reseller"
    base_s = f"{base_url}/s1" if pilihan_server == "1" else base_url

    if target_mulai.strip():
        jam_mulai = datetime.strptime(target_mulai.strip(), "%H:%M:%S").time()
        dt_mulai = datetime.combine(sekarang.date(), jam_mulai)
        if dt_mulai < sekarang:
            dt_mulai += timedelta(days=1)

    if target_kirim_data.strip():
        jam_kirim = datetime.strptime(target_kirim_data.strip(), "%H:%M:%S").time()
        patokan_hari = dt_mulai.date() if dt_mulai else sekarang.date()
        dt_kirim = datetime.combine(patokan_hari, jam_kirim)
        if dt_kirim < (dt_mulai if dt_mulai else sekarang):
            dt_kirim += timedelta(days=1)
        batas_aman = dt_kirim - timedelta(seconds=40)

    if dt_mulai:
        update_worker_ui(worker_id, status=f"[dim][..] Standby ({dt_mulai.strftime('%H:%M:%S')})[/]", state="running")
        while datetime.now() < dt_mulai:
            time.sleep(1)

    service_id = config_api["service_id"]
    country_id = config_api["country_id"]
    provider_id = config_api["provider_id"]

    maksimal_ganti_nomor = 3
    otp_code = None
    msisdn = None

    # --- SISTEM 3 STRIKES ---
    for attempt in range(1, maksimal_ganti_nomor + 1):
        if batas_aman and datetime.now() >= batas_aman and attempt == 1:
            update_worker_ui(worker_id, status="[red][X] Zona Merah (Batal)[/]", state="failed")
            return

        update_worker_ui(
            worker_id,
            attempt=f"{attempt}/3",
            msisdn="-",
            otp="-",
            status="[cyan][..] Meminta nomor baru...[/]",
            state="running"
        )
        order_id = None
        raw_number = None

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
                        update_worker_ui(worker_id, status="[bold red][X] Saldo OTP Habis![/]", state="failed")
                        return
                    else:
                        update_worker_ui(worker_id, status=f"[dim yellow][..] Antre stok ({tarik_attempt+1}/20)...[/]")
                        for _ in range(15):
                            time.sleep(0.1)
                        continue

                data_order = res_o.get('data', res_o)
                order_id = data_order.get('order_id', data_order.get('id'))
                raw_number = data_order.get('phone', data_order.get('number'))
                update_worker_ui(worker_id, msisdn=str(raw_number), status="[green][+] Nomor didapat[/]")
                break
            except Exception:
                time.sleep(2)
                continue

        if not order_id:
            update_worker_ui(worker_id, status="[red][X] Nomor Zonk[/]")
            continue

        try:
            msisdn = regis.normalize_msisdn(raw_number)
            update_worker_ui(worker_id, msisdn=msisdn, status="[cyan][..] Cek nomor...[/]")
            registered, info = regis.step_check(msisdn)
            if registered:
                update_worker_ui(worker_id, status="[yellow][!] Nomor sudah terdaftar[/]")
                try:
                    state_path(msisdn).unlink(missing_ok=True)
                except Exception:
                    pass
                continue
        except RegisError:
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

        update_worker_ui(worker_id, status="[yellow][>>] Meminta SMS OTP...[/]")
        try:
            regis.step_send_otp(msisdn)
        except RegisError:
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

        # --- ARGOMETER 55 DETIK ---
        total_cek = 55 // 5
        for i in range(total_cek):
            sisa_detik = 55 - (i * 5)
            update_worker_ui(worker_id, status=f"[bright_yellow][..] Tunggu OTP ({sisa_detik}s)...[/]")
            time.sleep(5)
            otp_code = cek_status_otp(base_s, order_id)
            if otp_code:
                update_worker_ui(worker_id, otp=str(otp_code), status="[bold green][OK] OTP Diterima![/]")
                break

        if otp_code:
            break
        else:
            update_worker_ui(worker_id, status="[red][X] Timeout (Ghosting)[/]")
            try:
                state_path(msisdn).unlink(missing_ok=True)
            except Exception:
                pass
            continue

    if not otp_code:
        update_worker_ui(worker_id, status="[bold red][X] Gagal Total (3x)[/]", state="failed")
        return

    # --- FASE EKSEKUSI ---
    fullname, email = generate_random_identity()
    pin = PIN_KUNCI
    update_worker_ui(worker_id, identity=fullname, status="[cyan][..] Validasi OTP...[/]")

    try:
        regis.step_validate(msisdn, otp_code)
        update_worker_ui(worker_id, status="[green][OK] Validasi OK[/]")
    except RegisError:
        update_worker_ui(worker_id, status="[bold red][X] Validasi Gagal[/]", state="failed")
        try:
            state_path(msisdn).unlink(missing_ok=True)
        except Exception:
            pass
        return

    if dt_kirim:
        if datetime.now() < dt_kirim:
            update_worker_ui(worker_id, status=f"[bold cyan][!] Siaga Cut-off ({dt_kirim.strftime('%H:%M:%S')})[/]")
            while True:
                sisa = (dt_kirim - datetime.now()).total_seconds()
                if sisa <= 0:
                    break
                elif sisa > 0.5:
                    time.sleep(0.1)
                elif sisa > 0.05:
                    time.sleep(0.01)
        else:
            update_worker_ui(worker_id, status="[bold yellow][>>] Terjang![/]")

    for r in range(3):
        try:
            # Langsung tembak POST Register tanpa menyentuh UI Lock terlebih dahulu
            regis.step_register(msisdn, pin, fullname, email)
            waktu_sukses = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            update_worker_ui(
                worker_id,
                status=f"[bold bright_green][OK] SUKSES [{waktu_sukses}][/]",
                state="success"
            )
            return
        except Exception:
            if r < 2:
                time.sleep(1)
            else:
                update_worker_ui(worker_id, status="[bold red][X] Final Gagal[/]", state="failed")
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
    pilihan_server = Prompt.ask("[bold cyan]>> Pilih Server API OTPInstan[/]", choices=["1", "2"], default="1")
    jumlah_akun = int(Prompt.ask("[bold cyan]>> Masukkan jumlah akun (1 - 20)[/]", default="1"))
    target_mulai = Prompt.ask("[bold cyan]>> Jam mulai pendaftaran (HH:MM:SS, kosong = instan)[/]", default="")
    target_kirim_data = Prompt.ask("[bold cyan]>> Jam kirim data diri (HH:MM:SS, kosong = langsung)[/]", default="")

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

    WORKER_STATUS.clear()
    for i in range(1, jumlah_akun + 1):
        update_worker_ui(i, status="[dim]Menyiapkan thread...[/]", state="running")

    # Bersihkan layar sebelum masuk ke Live Dashboard agar tidak tumpang tindih di py.exe
    clear_once()
    threads = []
    with Live(
        build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim_data),
        console=console,
        refresh_per_second=1
    ) as live:
        for i in range(1, jumlah_akun + 1):
            t = threading.Thread(
                target=worker_register_scheduled,
                args=(i, target_mulai, target_kirim_data, pilihan_server, config_api)
            )
            threads.append(t)
            t.start()
            for _ in range(8):
                time.sleep(0.1)
                live.update(build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim_data))

        while any(t.is_alive() for t in threads):
            live.update(build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim_data))
            time.sleep(0.25)

        live.update(build_bulk_dashboard(harga_info, pilihan_server, target_mulai, target_kirim_data))

    console.print("\n[bold green][OK] Bulk Register Selesai![/]")


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
    print_section_header(
        "[*] Cek Bonus Massal",
        "Memeriksa saldo utama dan bonus poin seluruh akun di dalam folder data/states.",
        style="bright_green"
    )
    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] Library pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] Folder states kosong.[/]")
        return

    table = Table(
        box=box.ROUNDED,
        header_style="bold bright_white on dark_blue",
        border_style="bright_cyan",
        expand=False,
    )
    table.add_column("No", style="bright_cyan", justify="center", width=5)
    table.add_column("Nomor", style="bright_green", width=16)
    table.add_column("Saldo", justify="right", style="bright_yellow", width=14)
    table.add_column("Bonus", justify="right", style="bright_magenta", width=14)
    table.add_column("Status", justify="center", width=14)

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
            time.sleep(0.3)

    console.print(
        Panel(
            f"[bold white]Total Diperiksa:[/] {len(states)}   |   "
            f"[bold bright_green][+] Bonus Masuk:[/] {jml_masuk}   |   "
            f"[bold yellow]Zonk:[/] {jml_zonk}   |   "
            f"[bold red]Error:[/] {jml_err}",
            border_style="bright_cyan",
            box=box.ROUNDED,
            expand=False,
        )
    )


# ==========================================
# MENU 5: RESTORE / INJECT TERMUX
# ==========================================
def menu_injeck_termux():
    print_section_header(
        "[*] Restore Termux (Root)",
        "Inject akun pertama dari data/states langsung ke HP ini via Superuser.",
        style="bright_magenta"
    )

    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] Library pycryptodome belum diinstall di Termux.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] Folder data/states kosong. Tidak ada akun matang untuk di-inject.[/]")
        return

    akun_target = states[0]["file"]
    nomor = states[0].get("msisdn", "?")

    console.print(
        Panel(
            f"[bold white]Nomor Target :[/] [bold bright_green]{nomor}[/]\n"
            f"[bold white]Lokasi File  :[/] [dim]{akun_target}[/]\n"
            f"[bold white]Sisa Antrean :[/] [cyan]{len(states)} akun di data/states[/]",
            title="[bold magenta]Target Restore[/]",
            border_style="magenta",
            box=box.ROUNDED,
            expand=False,
        )
    )

    if not Confirm.ask("[bold magenta]>> Inject akun ini ke perangkat sekarang?[/]", default=True):
        return

    console.print()
    try:
        inject_termux_account(akun_target)
    except InjectError as e:
        console.print(f"\n[bold red][X] Gagal Inject: {e}[/]")
    except Exception as e:
        console.print(f"\n[bold red][X] Error Sistem: {e}[/]")


# ==========================================
# MENU 6: SORTIR AKUN
# ==========================================
def menu_sortir():
    print_section_header(
        "[*] Sortir Akun Berdasarkan Bonus",
        "Membuang otomatis file akun zonk (0) dan mempertahankan akun bonus 5000.",
        style="bright_yellow"
    )

    if not CRYPTO_AVAILABLE:
        console.print("[bold red][X] Library pycryptodome belum diinstall.[/red]")
        return

    states = list_states()
    if not states:
        console.print("[yellow][!] Tidak ada akun di folder data/states untuk disortir.[/]")
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
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Memulai cek dan sortir akun...", total=len(states))

        for akun in states:
            file_path = Path(akun["file"])
            if not file_path.exists():
                progress.advance(task)
                continue

            msisdn = akun.get("msisdn", "?")
            progress.update(task, description=f"[cyan]Memeriksa {msisdn}...[/]")

            saldo_utama, bonus_poin, status_msg = proses_cek_satu_akun(akun)

            if bonus_poin == "-" or "Error" in status_msg or "Sesi Mati" in status_msg:
                progress.console.print(f"  [red][X] {msisdn}[/] - Error/Sesi Mati saat cek saldo. Dilewati.")
                count_error += 1
                progress.advance(task)
                continue

            poin_int = int(bonus_poin) if str(bonus_poin).isdigit() else 0

            try:
                if poin_int >= 5000:
                    progress.console.print(f"  [green][OK] {msisdn}[/] -> [bold green]AMAN ({poin_int} pts, dipertahankan di data/states/)[/]")
                    count_bonus += 1
                else:
                    shutil.move(str(file_path), str(dir_zonk / file_path.name))
                    progress.console.print(f"  [yellow][!] {msisdn}[/] -> [dim yellow]DIBUANG ke folder ZONK ({poin_int} pts)[/]")
                    count_zonk += 1
            except Exception as e:
                progress.console.print(f"  [red][X] Gagal memindahkan file {msisdn}: {e}[/]")

            progress.advance(task)
            time.sleep(0.3)

    rekap = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    rekap.add_column("Kategori", style="bold")
    rekap.add_column("Jumlah", justify="right")
    rekap.add_column("Keterangan", style="dim")
    rekap.add_row("[bright_green][+] Bonus (>= 5000)[/]", f"[bold green]{count_bonus} akun[/]", "Siap di-inject via Menu 3 di data/states/")
    rekap.add_row("[bright_yellow][-] Zonk (< 5000)[/]", f"[bold yellow]{count_zonk} akun[/]", "Dipindah ke data/states_zonk/")
    if count_error > 0:
        rekap.add_row("[bright_red][!] Error Check[/]", f"[bold red]{count_error} akun[/]", "Tetap berada di folder data/states/")

    console.print()
    console.print(Panel(rekap, title="[bold bright_green][OK] Sortir Selesai![/]", border_style="bright_green", expand=False))


# ==========================================
# MENU 7 & 8: FITUR DALAM PENGEMBANGAN
# ==========================================
def menu_fitur_segera(nama_fitur: str):
    print_section_header(
        f"[*] {nama_fitur}",
        "Modul tambahan untuk Command Center.",
        style="bright_yellow"
    )
    console.print(
        Panel(
            f"[bold yellow][!] Mohon maaf, fitur [cyan]{nama_fitur}[/] saat ini sedang dalam tahap pengembangan.[/]\n"
            "[dim]Fitur ini akan segera hadir pada pembaruan versi berikutnya.[/]",
            title="[bold bright_yellow]Informasi Pengembangan[/]",
            border_style="bright_yellow",
            box=box.ROUNDED,
            expand=False,
        )
    )
    console.print()
    Prompt.ask("[dim cyan]Tekan [bold white]Enter[/bold white] untuk kembali ke menu utama...[/]")


# ==========================================
# MASTER UI / MENU UTAMA
# ==========================================
def render_dashboard_header():
    void_art = (
        "[bold bright_yellow]"
        "888     888  .d88888b.  8888888 8888888b.\n"
        "888     888 d88P\" \"Y88b   888   888  \"Y88b\n"
        "888     888 888     888   888   888    888\n"
        "Y88b   d88P 888     888   888   888    888\n"
        " Y88b d88P  888     888   888   888    888\n"
        "  Y88o88P   888     888   888   888    888\n"
        "   Y888P    Y88b. .d88P   888   888  .d88P\n"
        "    Y8P      \"Y88888P\"  8888888 8888888P\""
        "[/bold bright_yellow]"
    )

    try:
        jml_state = len(list_states())
    except Exception:
        jml_state = 0

    crypto_badge = "[bold green]Aktif[/]" if CRYPTO_AVAILABLE else "[bold red]Nonaktif[/]"
    status_line = (
        f"[bold white]Akun Ready:[/] [bright_cyan]{jml_state} file[/]   |   "
        f"[bold white]Crypto AES:[/] {crypto_badge}   |   "
        f"[bold white]PIN Default:[/] [bright_yellow]{PIN_KUNCI}[/]   |   "
        f"[bold white]Versi App:[/] [dim]v{APP_VERSION}[/]"
    )

    console.print(void_art)
    console.print(Panel(status_line, border_style="bright_black", box=box.ROUNDED, expand=False, padding=(0, 2)))

def main():
    while True:
        clear_once()
        render_dashboard_header()

        menu_table = Table(show_header=True, header_style="bold bright_cyan", box=box.SIMPLE_HEAD, padding=(0, 2))
        menu_table.add_column("Kode", style="bold bright_yellow", justify="center", width=6)
        menu_table.add_column("Menu Fitur", style="bold bright_white", width=24)
        menu_table.add_column("Deskripsi Singkat", style="dim white")

        menu_table.add_row("[1]", "Daftar Manual", "Registrasi akun tunggal dengan OTP SMS manual")
        menu_table.add_row("[2]", "Daftar Otomatis (Bulk)", "Registrasi massal terjadwal dengan Live Monitor")
        menu_table.add_row("[3]", "ADB Push (Khusus PC)", "Inject sesi akun ke banyak HP sekaligus via ADB")
        menu_table.add_row("[4]", "Cek Bonus", "Tampilkan tabel saldo & poin secara real-time")
        menu_table.add_row("[5]", "Restore Termux (Root)", "Pasang sesi akun langsung ke HP ini via Superuser")
        menu_table.add_row("[6]", "Sortir Akun", "Pisahkan otomatis akun bonus >= 5.000 & akun zonk")
        menu_table.add_row("[7]", "Verifikasi Email", "[dim yellow]Verifikasi email akun (Segera Hadir)[/]")
        menu_table.add_row("[8]", "Scan BONUS", "[dim yellow]Pindai bonus otomatis (Segera Hadir)[/]")
        menu_table.add_row("[9]", "[bright_red]Keluar[/]", "[dim red]Tutup sesi Command Center[/]")

        console.print(
            Panel(
                menu_table,
                title="[bold bright_yellow][*] VOID COMMAND CENTER[/]",
                subtitle="[dim]Gunakan angka 1-9 untuk memilih menu[/]",
                border_style="bright_cyan",
                box=box.ROUNDED,
                expand=False,
            )
        )

        c = Prompt.ask(
            "\n[bold bright_cyan]>> Pilih Menu[/]",
            choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"],
            default="9"
        )

        if c == "9":
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
                menu_cek_saldo()
            elif c == "5":
                menu_injeck_termux()
            elif c == "6":
                menu_sortir()
            elif c == "7":
                menu_fitur_segera("Verifikasi Email")
            elif c == "8":
                menu_fitur_segera("Scan BONUS")

            if c in ["1", "2", "3", "4", "5", "6"]:
                console.print()
                console.print(Rule(style="bright_black"))
                Prompt.ask("[dim cyan]Tekan [bold white]Enter[/bold white] untuk kembali ke menu...[/]")

        except KeyboardInterrupt:
            console.print("\n[dim]Batal (Ctrl+C).[/]")
            time.sleep(1)

if __name__ == "__main__":
    try:
        auto_update()
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Stop (Ctrl+C).[/]")
