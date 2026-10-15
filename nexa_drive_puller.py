"""
Google Drive otonom çekici: public bir Drive klasör linkinden dosyaları
otomatik listeler, projeler/ klasör yapısına indirir ve watchdog zincirini
tetikler. Böylece "tek Drive linki -> dosyalar -> DB -> site -> ALYA" tam
otonom senkron sağlanır.

Klasör linki örnek: https://drive.google.com/drive/folders/1AbCdEfGhIjKlmNo
(Klasör 'linki olan herkes görüntüleyebilir' olarak paylaşılmalı.)
"""
import os
import re
import sys
import json
import time
import shutil
import logging
import urllib.request
import urllib.parse
from pathlib import Path

logger = logging.getLogger("nexa.drive")

SITE_DIR = Path(__file__).resolve().parent
PROJELER_DIR = SITE_DIR / "projeler"
CONFIG_FILE = SITE_DIR / "config.json"
STATE_FILE = SITE_DIR / "drive_state.json"
DEFAULT_INTERVAL = 600  # 10 dakika

FOLDER_URL_KEY = "drive_folder_url"
LAST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def folder_id_from_url(url):
    m = re.search(r"(?:/folders/|/drive/u/\d+/folders/|id=)([\w-]{15,})", url or "")
    return m.group(1) if m else None


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=LAST_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def download_file(fid, dst, timeout=180):
    """drive.usercontent endpoint'i ile indirir (206/uyarli, HTML virus-scan
    sayfasi dondurmez, buyuk dosyalar icin guvenilir)."""
    url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
    tmp = str(dst) + ".part"
    with urllib.request.urlopen(urllib.request.Request(url, headers=LAST_HEADERS), timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            logger.warning("drive %s HTML sayfasi dondurdu (public degil mi?)", fid)
            return 0
        with open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    size = os.path.getsize(tmp)
    if size < 512 and tmp.lower().endswith((".mp4", ".pdf")):
        os.unlink(tmp)
        logger.warning("drive %s cok kucuk/bos dosya", fid)
        return 0
    if dst.exists():
        dst.unlink()
    shutil.move(tmp, dst)
    return size


def list_folder(fid, depth=0, seen=None):
    """Embedded folderview HTML'inden dosya + alt klasör listesi çıkarır."""
    if depth > 3 or not fid:
        return []
    seen = seen or set()
    if fid in seen:
        return []
    seen.add(fid)
    try:
        html = fetch(f"https://drive.google.com/embeddedfolderview?id={fid}")
    except Exception as e:
        logger.warning("drive listeleme hatasi %s: %s", fid, e)
        return []
    files = []
    for block in re.split(r'<div class="flip-entry"', html)[1:]:
        m_id = re.search(r'id="entry-([\w-]{15,})"', block)
        m_title = re.search(r'<div class="flip-entry-title">\s*([^<]+?)\s*</div>', block)
        if not m_id or not m_title:
            continue
        kind = "folder" if 'aria-label="Folder"' in block or "drive-sprite-folder" in block else "file"
        files.append({"name": m_title.group(1).strip(), "id": m_id.group(1), "kind": kind})
    if not files:
        for m in re.finditer(r'href="https://drive\.google\.com/file/d/([\w-]{15,})/view[^"]*"[^>]*>\s*<span[^>]*>\s*([^<]+?)\s*</span>', html):
            files.append({"name": m.group(2), "id": m.group(1), "kind": "file"})
    for f in list(files):
        if f["kind"] == "folder":
            f["children"] = list_folder(f["id"], depth + 1, seen)
    return files


def pull_once():
    """Drive klasöründeki dosyaları projeler/'e indirir; değişen varsa True."""
    cfg = get_config()
    url = cfg.get(FOLDER_URL_KEY, "") or os.environ.get("DRIVE_FOLDER_URL", "") or "https://drive.google.com/drive/folders/1wl6IORLksewhrWqpCOfjFNgjlC_rAhZT"
    fid = folder_id_from_url(url)
    if not fid:
        logger.info("drive_folder_url tanimli degil - Drive cekimi atlandi")
        return 0
    entries = list_folder(fid)
    if not entries:
        logger.warning("Drive klasoru bos veya erisilemiyor (public mi?): %s", fid)
        return 0
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    downloaded = 0
    for top in entries:
        if top["kind"] != "folder":
            continue
        local_dir = PROJELER_DIR / top["name"]
        local_dir.mkdir(parents=True, exist_ok=True)
        items = top.get("children", [])
        for it in items:
            if it["kind"] == "folder":
                # Alt klasörlerden (örn. DIŞ CEPHE GÖRSELLERİ, PLANLAR) görselleri ve ek belgeleri çek
                sub_items = it.get("children", [])
                for sub_it in sub_items:
                    if sub_it.get("kind") != "file":
                        continue
                    sname = sub_it["name"]
                    if not sname.lower().endswith((".pdf", ".mp4", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp")):
                        continue
                    skey = f"{top['name']}/{sname}"
                    dst = local_dir / sname
                    if state.get(skey) == sub_it["id"] and dst.exists():
                        continue
                    try:
                        size = download_file(sub_it["id"], dst)
                        if size > 0:
                            state[skey] = sub_it["id"]
                            downloaded += 1
                            logger.info("Drive alt klasör -> %s (%s KB)", skey, size // 1024)
                            STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
                    except Exception as e:
                        logger.warning("alt klasör indirme hatasi %s: %s", sname, e)
                continue

            if it["kind"] != "file":
                continue
            name = it["name"]
            if not name.lower().endswith((".pdf", ".mp4", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp")):
                continue
            key = f"{top['name']}/{name}"
            if state.get(key) == it["id"] and (local_dir / name).exists():
                continue
            dst = local_dir / name
            try:
                size = download_file(it["id"], dst)
                if size > 0:
                    state[key] = it["id"]
                    downloaded += 1
                    logger.info("Drive -> %s (%s KB)", key, size // 1024)
                    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as e:
                logger.warning("indirme hatasi %s: %s", name, e)
    if downloaded:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        _trigger_ingest()
        _refresh_drive_previews()
    return downloaded


def _trigger_ingest():
    try:
        import subprocess
        import sys as _sys
        kwargs = {}
        if _sys.platform == 'win32':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen([sys.executable, str(SITE_DIR / "nexa_watchdog.py")],
                         cwd=str(SITE_DIR), **kwargs)
    except Exception:
        pass


def _refresh_drive_previews():
    """Drive'da bulunan video/pdf ID'lerini kartlara isler (dogrudan /preview
    URL'leri yazar). Boylece Drive'a yeni dosya eklendiginde site otomatik
    Drive onizlemesi kullanmaya baslar — hosting icin sifir depolama."""
    try:
        import json as _json
        map_path = SITE_DIR / "static" / "data" / "projects_map.json" if (SITE_DIR / "static" / "data" / "projects_map.json").exists() else SITE_DIR / "projects_map.json"
        cards = _json.loads(map_path.read_text(encoding="utf-8"))
        state = _json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
        vid_pri = ['tanitim', 'lansman', 'animasyon', 'render', 'muteahhit', 'kisa', 'promo']
        pdf_pri = ['sunum', 'tanitim', 'proje', 'fiyat', 'odeme']

        def fold(s):
            for a, b in (('İ','i'),('I','i'),('ı','i'),('Ş','s'),('ş','s'),('Ğ','g'),('ğ','g'),
                         ('Ç','c'),('ç','c'),('Ö','o'),('ö','o'),('Ü','u'),('ü','u')):
                s = s.replace(a, b)
            return s.lower()

        groups = {}
        for key, fid in state.items():
            folder, name = key.split('/', 1)
            if name.lower().endswith(('.pdf', '.mp4')):
                groups.setdefault(folder, {'pdf': [], 'mp4': []})
                groups[folder]['pdf' if name.lower().endswith('.pdf') else 'mp4'].append((name, fid))

        def pick(items, pri):
            items = sorted(items, key=lambda x: next((i for i, k in enumerate(pri) if k in fold(x[0])), len(pri)))
            return items[0][1] if items else ''

        changed = 0
        for c in cards:
            m = groups.get(c.get('folder_name'))
            if not m:
                continue
            vid = pick(m['mp4'], vid_pri)
            pdf = pick(m['pdf'], pdf_pri)
            if vid and c.get('drive_video_preview') != f"https://drive.google.com/file/d/{vid}/preview":
                c['drive_video_preview'] = f"https://drive.google.com/file/d/{vid}/preview"
                changed += 1
            if pdf and c.get('drive_pdf_preview') != f"https://drive.google.com/file/d/{pdf}/preview":
                c['drive_pdf_preview'] = f"https://drive.google.com/file/d/{pdf}/preview"
                changed += 1
        if changed:
            content_str = _json.dumps(cards, ensure_ascii=False, indent=1)
            map_path.write_text(content_str, encoding="utf-8")
            alt_path = SITE_DIR / "projects_map.json"
            if alt_path != map_path:
                alt_path.write_text(content_str, encoding="utf-8")
            logger.info("kart Drive onizlemeleri guncellendi: %s alan", changed)
    except Exception as e:
        logger.warning("drive preview yenileme hatasi: %s", e)


def drive_loop(interval=DEFAULT_INTERVAL):
    logger.info("Drive cekici basladi (10 dk aralik)")
    while True:
        try:
            pull_once()
        except Exception as e:
            logger.warning("drive_loop: %s", e)
        time.sleep(interval)


def set_folder_url(url):
    cfg = get_config()
    cfg[FOLDER_URL_KEY] = url
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    n = pull_once()
    print(f"indirilen dosya: {n}")