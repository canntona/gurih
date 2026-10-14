"""inject.py — pasang akun hasil daftar ke HP Android (root) via adb.

Menulis shared_prefs LinkAja (Core.xml + Security.xml):
  Core.xml    : deviceId, IMSI, adsId, nomor HP, token login (JWT + refresh)
  Security.xml: keyX1-X3 (session keys)

Syarat:
  • HP rooted (perintah `su` tersedia) + USB debugging aktif
  • App LinkAja ter-install dan PERNAH login sekali
    (entry prefs harus sudah ada — script hanya menimpa nilai, bukan
    membuat struktur; kalau entry gak ketemu, inject di-cancel &
    XML tidak diubah)
  • `adb` tersedia (Windows: platform-tools di PATH atau di folder script)

Backup otomatis:
  • per inject : backup/inject/<msisdn>/{Core,Security}.xml.orig
  • per device : /data/local/tmp/{Core,Security}.xml.bak (sekali aja)

Rollback: restore file .orig / .bak via menu Inject → Pulihkan.
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prefscrypto import pref_name_hash, pref_value_encrypt, read_pref  # noqa

PREF_DIR = "/data/data/com.telkom.mwallet/shared_prefs"
PACKAGE = "com.telkom.mwallet"


class InjectError(Exception):
    """Error user-friendly (pesan langsung bisa ditampilkan)."""


def find_adb() -> str:
    """Cari adb: folder script dulu, baru PATH (Windows: adb.exe)."""
    here = Path(__file__).resolve().parent
    root = here.parent
    for cand in (here / "adb.exe", here / "adb", root / "adb.exe",
                 root / "adb", root / "platform-tools" / "adb.exe",
                 root / "platform-tools" / "adb"):
        if cand.exists():
            return str(cand)
    # fallback ke PATH
    import shutil
    exe = shutil.which("adb")
    if not exe:
        raise InjectError(
            "adb gak ketemu. Windows: extract platform-tools, taruh folder "
            "'platform-tools' di dalam folder script ini (atau tambahin ke "
            "PATH). Android/Termux: pkg install adb")
    return exe


def adb(adb_bin, serial, *args, binary=False, check=True, input_text=None):
    cmd = [adb_bin]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    r = subprocess.run(cmd, input=(input_text.encode() if input_text else None),
                       capture_output=True, timeout=90)
    out = r.stdout if binary else r.stdout.decode(errors="replace").strip()
    if check and r.returncode != 0 and r.stderr.strip():
        raise InjectError(f"adb {' '.join(args[:3])}: {r.stderr.decode()[:200]}")
    return out


def list_devices(adb_bin):
    out = adb(adb_bin, None, "devices")
    return [ln.split("\t")[0] for ln in out.splitlines()[1:]
            if "\tdevice" in ln]


def _device_backup(adb_bin, serial):
    """Backup XML asli device sekali menggunakan cat agar aman dari Permission denied."""
    out = adb(adb_bin, serial, "shell", "su", "-c",
              "ls /data/local/tmp/Core.xml.bak 2>/dev/null")
    if "Core.xml.bak" in out:
        return
    adb(adb_bin, serial, "shell", "su", "-c",
        f"cat {PREF_DIR}/Core.xml > /data/local/tmp/Core.xml.bak && "
        f"cat {PREF_DIR}/Security.xml > /data/local/tmp/Security.xml.bak && "
        "chmod 666 /data/local/tmp/*.bak")


def _pull(adb_bin, serial, name):
    return adb(adb_bin, serial, "shell", "su", "-c", f"cat {PREF_DIR}/{name}")


def _push_and_install(adb_bin, serial, name, xml_text):
    """Timpa isi file XML existing via `su -c 'cat > file'` — owner/perm/
    SELinux context tetap. Paling robust."""
    p = subprocess.run(
        [adb_bin] + (["-s", serial] if serial else []) +
        ["shell", f"su -c 'cat > {PREF_DIR}/{name}'"],
        input=xml_text.encode(), capture_output=True, timeout=90)
    if p.returncode != 0 or b"Permission denied" in p.stderr + p.stdout:
        raise InjectError(f"install {name}: {p.stderr.decode()[:200]}")


def inject_account(state_file, adb_serial=None, progress=None) -> dict:
    """Pasang akun ke HP. state_file = data/states/state_<msisdn>.json.

    progress(msg) dipanggil tiap tahap (untuk TUI). Return info hasil.
    """
    say = progress or (lambda m: None)
    t0 = time.time()
    st = json.loads(Path(state_file).read_text())
    msisdn = st.get("msisdn") or Path(state_file).stem.replace("state_", "")
    ident, shared = st["ident"], st["shared"]
    jwt, rt = st.get("jwt"), st.get("refreshToken")
    if not (jwt and rt):
        raise InjectError(
            f"state {msisdn} ga punya token login — akun belum selesai daftar")

    adb_bin = find_adb()
    say("🔍 Cari device adb…")
    devs = list_devices(adb_bin)
    if not devs:
        raise InjectError("Gak ada device adb yang terhubung — cek USB "
                          "debugging / kabel / otorisasi")
    serial = adb_serial or devs[0]
    if adb_serial and adb_serial not in devs:
        raise InjectError(f"Serial {adb_serial} gak ada di daftar: {devs}")

    # 1. backup device (sekali) + snapshot lokal
    say(f"💾 Backup XML device ({serial})…")
    _device_backup(adb_bin, serial)
    bdir = ROOT / "backup" / "inject" / msisdn
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    core_xml = _pull(adb_bin, serial, "Core.xml")
    sec_xml = _pull(adb_bin, serial, "Security.xml")
    (bdir / f"Core.xml.{stamp}.orig").write_text(core_xml)
    (bdir / f"Security.xml.{stamp}.orig").write_text(sec_xml)

    # 2. parse & timpa nilai prefs
    say("🔐 Tulis identitas + kunci session ke XML…")
    core = load_prefs_xml_from_text(core_xml)
    sec = load_prefs_xml_from_text(sec_xml)
    reps_core = {
        "DEVICE_ID": ident["deviceId"],
        "IMSI": ident["imsi"],
        "ADS_ID": ident.get("adsId", ""),
        "USER_PHONE_NUMBER": msisdn,
        "AUTHORIZATION_TOKEN": json.dumps(
            {"token": jwt, "refreshToken": rt}, separators=(',', ':')),
    }
    reps_sec = {"keyX1": shared["key1"], "keyX2": shared["key2"],
                "keyX3": shared["key3"]}
    for store, reps in ((core, reps_core), (sec, reps_sec)):
        for name, val in reps.items():
            h = pref_name_hash(name)
            if h not in store:
                raise InjectError(
                    f"entry '{name}' gak ketemu di XML device — app belum "
                    "pernah login/versi beda. Inject dibatalkan, XML aman.")
            store[h] = pref_value_encrypt(name, val.encode())

    # 3. tulis XML baru (urutan entry dipertahankan)
    core_new = dump_xml(core, core_xml)
    sec_new = dump_xml(sec, sec_xml)

    # 4. force-stop app → push
    say("🚀 Pasang ke HP (app di-force-stop dulu)…")
    adb(adb_bin, serial, "shell", "am", "force-stop", PACKAGE)
    _push_and_install(adb_bin, serial, "Core.xml", core_new)
    _push_and_install(adb_bin, serial, "Security.xml", sec_new)

    # 5. verify pull-back
    say("✅ Verify hasil tulis…")
    vcore = load_prefs_xml_from_text(_pull(adb_bin, serial, "Core.xml"))
    vsec = load_prefs_xml_from_text(_pull(adb_bin, serial, "Security.xml"))
    verified = []
    for store, reps in ((vcore, reps_core), (vsec, reps_sec)):
        for name, want in reps.items():
            got = read_pref(store, name).decode()
            if got != want:
                raise InjectError(f"verify FAIL {name} — restore backup "
                                  f"di {bdir}")
            verified.append(name)

    # 6. Arsipkan file state yang sukses di-inject ke folder data/injected/
    try:
        state_file_path = Path(state_file)
        if state_file_path.exists():
            injected_dir = ROOT / "data" / "injected"
            injected_dir.mkdir(parents=True, exist_ok=True)
            target_path = injected_dir / state_file_path.name
            state_file_path.rename(target_path)
            say(f"📦 Arsip state -> injected/{state_file_path.name}")
    except Exception as e:
        say(f"⚠ Gagal memindah file state: {e}")

    say(f"🎉 Selesai {round(time.time() - t0, 1)}s")
    return {"ok": True, "msisdn": msisdn, "serial": serial,
            "verified": verified, "backup_dir": str(bdir),
            "elapsed": round(time.time() - t0, 1)}


def rollback(state_msisdn_or_dir, adb_serial=None, progress=None):
    """Pulihkan XML terakhir yang dibackup sebelum inject."""
    say = progress or (lambda m: None)
    bdir = Path(state_msisdn_or_dir)
    if bdir.is_dir():
        cores = sorted(bdir.glob("Core.xml.*.orig"))
        secs = sorted(bdir.glob("Security.xml.*.orig"))
        if not cores or not secs:
            raise InjectError(f"gak ada backup di {bdir}")
        adb_bin = find_adb()
        serial = adb_serial or (list_devices(adb_bin) or [None])[0]
        say("⏪ Restore XML backup…")
        adb(adb_bin, serial, "shell", "am", "force-stop", PACKAGE)
        _push_and_install(adb_bin, serial, "Core.xml", cores[-1].read_text())
        _push_and_install(adb_bin, serial, "Security.xml", secs[-1].read_text())
        return {"ok": True, "restored": str(cores[-1].parent)}


# ---------- XML helpers (raw text → dict, dump preserving order) ----------
def load_prefs_xml_from_text(text):
    """Parse XML pref ke {name_hash: value}."""
    import re
    entries = re.findall(r'<string name="([0-9a-f]+)">([^<]*)</string>', text)
    return dict(entries)


def dump_xml(store, orig_text):
    """Dump XML baru preserve urutan entry asli."""
    import re
    def repl(m):
        h = m.group(1)
        if h in store:
            return f'<string name="{h}">{store[h]}</string>'
        return m.group(0)
    return re.sub(r'<string name="([0-9a-f]+)">[^<]*</string>', repl, orig_text)