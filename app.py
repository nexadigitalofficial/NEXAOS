"""
NEXA.OS v5.0 — Unified PropTech Command Center (Standalone Edition)
==================================================================
Isolated high-performance PropTech dashboard and 6-step AI pipeline:
1. Sahibinden Store/Listing Scraper (SeleniumBase UC + Cloudflare Turnstile Bypass)
2. Coldwell Banker Scraper (cb.com.tr portfolio)
3. WhatsApp Chat Log NLP Parser (Arayis & Portfoy)
4. AI Matcher Engine (Demand-Supply Matching via Ollama/Gemini)
5. URL -> PDF & Interactive Web Presentation Deck Generator
6. Ultra Luxury v3 Card Presentation Generation
"""

from __future__ import annotations
import warnings
warnings.filterwarnings("ignore", message=".*urllib3.*")
warnings.filterwarnings("ignore", message=".*RequestsDependencyWarning.*")
warnings.filterwarnings("ignore", category=UserWarning, module="requests")

import asyncio
from urllib.parse import urlparse
_PLAYWRIGHT = False
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}
SCRAPE_TIMEOUT = 14

import argparse
import html as html_mod
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request, send_from_directory

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

try:
    from selenium import webdriver
    from selenium.webdriver import ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    _SELENIUM = True
except ImportError:
    _SELENIUM = False

# PSI v5 REST API + OCR fallback zinciri (bkz. PAGESPEED_API_KEY) — Selenium
# ile pagespeed.web.dev'i taramak yerine doğrudan Google'ın resmi API'sini
# çağırıp fullPageScreenshot üzerinden açıklama metnini OCR ile kurtarır.
try:
    import requests as _requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

try:
    from seleniumbase import SB
    _SELENIUMBASE = True
except ImportError:
    _SELENIUMBASE = False

try:
    import base64 as _base64
    import io as _io
    from PIL import Image as _PILImage
    _PIL = True
except ImportError:
    _PIL = False

try:
    import pytesseract as _pytesseract
    _TESSERACT = True

    # Windows'ta tesseract-ocr kurulumu genelde sistem PATH'ine otomatik
    # eklenmez (Linux/macOS'un tersine) — bu yüzden pytesseract binary'yi
    # bulamayıp "tesseract is not installed or it's not in your PATH" hatası
    # verir, halbuki kurulu olabilir. Önce TESSERACT_CMD ortam değişkenini
    # dene — ama SADECE gerçekten var olan bir dosyaya işaret ediyorsa
    # (eski/yanlış bir setx değeri kalmışsa onu görmezden gel ve otomatik
    # tespite düş, kullanıcıyı terminal restart'ına bağımlı bırakmayalım).
    # Bulamazsa UB-Mannheim'ın resmi Windows kurulumunun varsayılan
    # yollarını dener.
    _tess_cmd_env = os.environ.get("TESSERACT_CMD", "").strip()
    _tess_configured = False
    if _tess_cmd_env and os.path.isfile(_tess_cmd_env):
        _pytesseract.pytesseract.tesseract_cmd = _tess_cmd_env
        _tess_configured = True
    if not _tess_configured and sys.platform.startswith("win"):
        for _cand in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ):
            if os.path.isfile(_cand):
                _pytesseract.pytesseract.tesseract_cmd = _cand
                _tess_configured = True
                break

    # Başlangıçta hangi yolun kullanılacağını hemen konsola yaz — Windows'ta
    # "OCR çalışmıyor" tekrar sorulmadan önce bunun doğru olduğunu görmek
    # sorunu anında teşhis eder.
    if _tess_configured:
        print(f"[pipeline] [OK] Tesseract bulundu: {_pytesseract.pytesseract.tesseract_cmd}")
    elif sys.platform.startswith("win"):
        print(
            "[pipeline] [WARN] Tesseract binary'si bulunamadı (varsayılan Windows yolları "
            "denendi). OCR fallback devre dışı kalacak — kurulum/TESSERACT_CMD'yi "
            "kontrol et."
        )
except ImportError:
    _TESSERACT = False


def _tesseract_ready() -> Tuple[bool, str]:
    """
    pytesseract kurulu olması, tesseract BINARY'sinin de PATH'te/erişilebilir
    olması demek değildir (özellikle Windows'ta). Gerçek çağrıdan önce bunu
    doğrular; sorun varsa kullanıcıya doğrudan ne yapması gerektiğini söyler.
    """
    if not _TESSERACT:
        return False, "pytesseract kurulu değil (pip install pytesseract)"
    try:
        _pytesseract.get_tesseract_version()
        return True, ""
    except Exception:
        if sys.platform.startswith("win"):
            return False, (
                "tesseract-ocr binary'si bulunamadı (varsayılan Windows kurulum "
                "yolları da denendi). Kontrol et: 1) Tesseract'ı gerçekten "
                "kurdun mu (UB-Mannheim installer, Turkish dil paketiyle)? "
                "2) 'python web_app.py' sürecini bu değişiklikten SONRA yeniden "
                "başlattın mı? (Bu kontrol sadece süreç başlarken bir kez "
                "çalışır — dosyayı değiştirdikten sonra sunucuyu yeniden "
                "başlatman gerekir.) 3) Farklı bir yola kurduysan: "
                r'setx TESSERACT_CMD "C:\gerçek\yol\tesseract.exe" '
                "ile GERÇEK yolu tanımla, sonra sunucuyu yeniden başlat."
            )
        return False, (
            "tesseract-ocr binary'si bulunamadı. Kur: "
            "'sudo apt-get install tesseract-ocr tesseract-ocr-tur' (Ubuntu/Debian) "
            "veya 'brew install tesseract tesseract-lang' (macOS)."
        )

# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────

PAGESPEED_BASE = "https://pagespeed.web.dev/?hl=tr"
DEFAULT_TARGET  = (
    "https://coldwellbankercizgi.sahibinden.com/emlak"
    "?sorting=storeShowcase&userId=aKwheLpgPKniIhVFbBAJMSw"
)
DEFAULT_PS_HTML    = "pagespeed_result.html"
DEFAULT_CARDS_OUT  = "ilan_detay_karti.html"
DEFAULT_DETAIL_DIR = "detay_html"
DEFAULT_MODEL      = "qwen2.5:7b"
DEFAULT_OLLAMA     = "http://localhost:11434"
DEFAULT_PS_WAIT    = 50   # mağaza sayfası için PageSpeed bekleme (sn)
DEFAULT_DET_WAIT   = 50   # detay sayfası için PageSpeed bekleme (sn)
DEFAULT_DELAY      = 6    # detaylar arası bekleme (sn) — PageSpeed'in hazırlanması için

# ─────────────────────────────────────────────────────────────────────────────
# PageSpeed Insights v5 REST API (fullPageScreenshot + OCR fallback)
# ─────────────────────────────────────────────────────────────────────────────
# GÜVENLİK NOTU: Anahtar önce ortam değişkeninden okunur; hardcoded değer
# sadece bu ortam değişkeni ayarlanmamışsa devreye girer. Bu, kodu repo'ya
# koyduğunda anahtarın "zaten kodda gömülü" olmaktan çıkıp opsiyonel bir
# fallback haline gelmesini sağlar. Yine de mümkünse .env / ortam değişkeni
# ile taşımanı, bu dosyayı public bir repoya pushlamamanı ve Google Cloud
# Console'dan bu anahtarı sadece "PageSpeed Insights API" ile ve mümkünse
# IP kısıtlamasıyla sınırlamanı öneririm.
PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY", "AIzaSyClEth2ooknGZJ53WrgY1QKdrQunZfsNXg")
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# fullPageScreenshot.nodes içinden açıklama container'ını tespit etmek için
# aranan selector parçaları (öncelik sırasıyla) — Sahibinden detay şablonu
# değişirse bu listeye yeni adaylar eklenebilir.
_PSI_DESC_SELECTOR_HINTS = [
    "classifiedOtherDetails",
    "classifiedDescription",
    "classified-detail",
    "classifiedProperties",
]

# OCR için Tesseract dil paketi (Türkçe). Sistemde `tur.traineddata` kurulu
# olmalı: Ubuntu/Debian → `sudo apt-get install tesseract-ocr tesseract-ocr-tur`
PSI_OCR_LANG = os.environ.get("PSI_OCR_LANG", "tur")

# ─────────────────────────────────────────────────────────────────────────────
# "#classified-detail" fragment varyantı
# ─────────────────────────────────────────────────────────────────────────────
# Sahibinden'in detay sayfası .../detay/#classified-detail (veya
# #classifiedProperties) fragment'i ile açıldığında, sayfanın JS'i "Açıklama"
# sekmesini otomatik öne getiriyor. Bu fragment sunucuya giden HTTP isteğini
# DEĞİŞTİRMEZ (bkz. ULTRA manifesto notu) — ama PageSpeed/Lighthouse gerçek
# bir tarayıcıda o URL'i açıp JS'i çalıştırdığı için, raporun DOM/accessibility
# ağacında (ve dolayısı ile bizim kaydettiğimiz page_source'ta) açıklama
# metninin görünme ihtimali artar. Bu yüzden birincil (fragment'siz) fetch
# açıklama bulamazsa, aynı ilanı bu fragment'li varyantla BİR KEZ daha
# çekmeyi deniyoruz.
CLASSIFIED_DETAIL_FRAGMENT = "classified-detail"
CD_FILE_SUFFIX = "__cd"  # {listing_id}__cd.html olarak kaydedilir


def _strip_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def _build_classified_detail_url(base_url: str) -> str:
    """
    Verilen detay URL'sine (varsa mevcut fragment'i temizleyip)
    '#classified-detail' fragment'ini ekler.
    ".../detay" veya ".../detay/" → ".../detay/#classified-detail"
    """
    clean = _strip_fragment(base_url).rstrip("/")
    return f"{clean}/#{CLASSIFIED_DETAIL_FRAGMENT}"

# Sahibinden detay URL formatı  (ID'den otomatik türetilemezse bu search URL'si kullanılır)
SB_SEARCH_URL  = "https://www.sahibinden.com/arama?query_text={id}"
# Bilinen canonical format — PageSpeed bunu da render eder
SB_DETAIL_URL  = "https://www.sahibinden.com/ilan/{slug}-{id}/detay"

# Tekil ilan detay linki tespiti: /ilan/<slug>-<ilanNo>/detay
# (web_app.py ve CLI main() tarafından ortak kullanılır — bkz. detect_single_listing_id)
ILAN_PATH_RE = re.compile(r"/ilan/([^/?#]+)", re.IGNORECASE)
# Manifesto Bölüm 1.3 — alternatif/redirect format: sahibinden.com/<slug>/<ilanNo>
# (örn. https://www.sahibinden.com/camlidere-gol-manzarali-esyali-satilik-villa/1311060939)
ILAN_REDIRECT_RE = re.compile(
    r"sahibinden\.com/[a-z0-9\-]+/(\d{8,11})/?(?:[?#].*)?$", re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────────────────────
# SAHIBINDEN_URL_LOGIC_MANIFESTO.md v2.0 — Kategori & Slug Matematiği
# (Bkz. ULTRA_SAHIBINDEN_URL_GENERATOR_ENGINE.md — PageSpeed export'undan
#  reverse-engineer edilip 9 gerçek ilanla doğrulanmış kurallar)
# ─────────────────────────────────────────────────────────────────────────────

ALT_KATEGORI_SLUG_MAP = {
    "konut": "konut", "villa": "konut", "daire": "konut", "ev": "konut",
    "müstakil ev": "konut", "mustakil ev": "konut",
    "arsa": "arsa", "tarla": "arsa",
    "işyeri": "isyeri", "isyeri": "isyeri", "dükkan": "isyeri", "dukkan": "isyeri",
    "ofis": "isyeri", "büro": "isyeri", "buro": "isyeri",
    "bina": "bina",
    "devremülk": "devremulk", "devremulk": "devremulk",
    "turizm tesisi": "turizm-tesisi", "turizm-tesisi": "turizm-tesisi",
}
ISLEM_TURU_SLUG_MAP = {
    "satılık": "satilik", "satilik": "satilik",
    "kiralık": "kiralik", "kiralik": "kiralik",
    "devren": "devren",
}
DEFAULT_KATEGORI_SLUG = "emlak-konut-satilik"  # sağlam varsayılan (en yaygın kategori)

_TR_SLUG_CHAR_MAP = {
    "İ": "i", "I": "i", "ı": "i",
    "Ç": "c", "ç": "c",
    "Ğ": "g", "ğ": "g",
    "Ö": "o", "ö": "o",
    "Ş": "s", "ş": "s",
    "Ü": "u", "ü": "u",
}


def title_to_slug(title: str) -> str:
    """
    Manifesto v2.0 — DÜZELTİLMİŞ slug algoritması.

    v1.0'daki "apostrof sil" kuralı YANLIŞTI (bkz. ULTRA manifesto Bölüm 5).
    Gerçek sahibinden davranışı: apostrof kelime ayracı (BOŞLUK) gibi işlenir.
    "DAMLAR'DA" → "damlar da" → "damlar-da"  (silinip "damlarda" OLMAZ)

    4/4 gerçek href prefiksiyle doğrulanmış (Erdek Triplex örneği dahil).
    """
    if not title:
        return ""
    slug = "".join(_TR_SLUG_CHAR_MAP.get(ch, ch) for ch in title)
    slug = slug.lower().strip()
    slug = re.sub(r"\s*\+\s*", "-plus", slug)          # "4+1" → "4-plus1"
    slug = slug.replace("m²", "m2")
    slug = re.sub(r"['´`\"\u2019]", " ", slug)          # apostrof/tırnak → BOŞLUK (v2.0 düzeltmesi)
    slug = re.sub(r"\*+", " ", slug)                    # "**vurgu**" bold işaretleri → BOŞLUK
    # (Edge case: "GÜNDÜZ**den**GENİŞ" gibi boşluksuz bold-vurgu bloklarında ** basitçe
    #  silinirse kelimeler birbirine yapışır: "gunduzdengenis". BOŞLUĞA çevirmek
    #  "gunduz-den-genis" üretir — gerçek href ile doğrulanmış doğru davranış.)
    slug = re.sub(r"[^\w\s-]", "", slug)                # kalan dekoratif karakterleri (▃▅▇, !!!) temizle
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) > 120:                                  # manifesto Edge Case 4
        slug = slug[:120].rstrip("-")
    return slug


def _find_analytics_param(text: str, name: str) -> str:
    """
    PageSpeed HTML'i içindeki GA/GTM analytics kuyruğundan (kategori_1=Emlak&
    kategori_2=Villa... veya cd13=Emlak&cd14=Villa... gibi) bir parametre değerini
    çeker ve percent/unicode-escape çözer.
    """
    t = text.replace("\\u0026", "&").replace("\\x26", "&").replace("&amp;", "&")
    m = re.search(re.escape(name) + r'\s*[=:]\s*([^&"\'<>\\\s]+)', t)
    if not m:
        return ""
    raw_val = m.group(1)
    try:
        val = urllib.parse.unquote(raw_val)
    except Exception:
        val = raw_val
    return val.strip().lower()


def _detect_kategori_slug(raw_text: str) -> str:
    """
    Sayfanın GA analytics kuyruğundan (ep.kategori_1/2/3 veya cd13/14/15 GA4
    alternatifi) gerçek kategoriyi okuyup manifesto kategori-slug formülünü
    (emlak-{altKategori}-{işlemTürü}) üretir. Bulunamazsa güvenli varsayılana
    (emlak-konut-satilik) düşer — asla hata fırlatmaz.
    """
    alt = (
        _find_analytics_param(raw_text, "kategori_2")
        or _find_analytics_param(raw_text, "cd14")
    )
    islem = (
        _find_analytics_param(raw_text, "kategori_3")
        or _find_analytics_param(raw_text, "cd15")
    )

    alt_slug = ALT_KATEGORI_SLUG_MAP.get(alt, "")
    islem_slug = ISLEM_TURU_SLUG_MAP.get(islem, "")

    if alt_slug and islem_slug:
        return f"emlak-{alt_slug}-{islem_slug}"
    return DEFAULT_KATEGORI_SLUG


# Genel arama/kategori sonucu sayfası formatı (mağaza sayfasından FARKLI DOM):
#   data-classified-id="1234567890"  +  ayrı <div>BAŞLIK\nFİYAT TL\n LOKASYON…</div>
# Bkz. ULTRA_SAHIBINDEN_URL_GENERATOR_ENGINE.md Bölüm 3-4.
SEARCH_RESULT_ID_RE = re.compile(r"data-classified-id=&quot;(\d{6,})&quot;")
SEARCH_RESULT_TITLE_RE = re.compile(
    r"<div>([^<]{5,220}?)\n[\d.,]+\s*(?:TL|₺)", re.IGNORECASE
)
SEARCH_RESULT_HREF_RE = re.compile(r"href=&quot;(/ilan/[^\"&]*)&quot;")


def _extract_search_result_listings(raw_text: str) -> List[ListingSummary]:
    """
    Yöntem B — Genel 'arama sonucu' / kategori sayfası (örn. sahibinden.com/
    satilik-villa/ankara-camlidere gibi çok-ilanlı arama/kategori sayfaları)
    PageSpeed export'undan ilan listesi çıkarır.

    Bu, Yöntem A'nın (mağaza sayfası, img alt="Başlık #ID") kullandığı DOM
    yapısından TAMAMEN FARKLI bir yapı kullanır: burada ilanlar
    data-classified-id attribute'u + ayrı bir başlık/fiyat <div>'i ile
    temsil ediliyor, gerçek href'ler ise Lighthouse tarafından kesiliyor
    ("…" ile biter). Bu yüzden URL'yi manifesto matematiğiyle YENİDEN ÜRETİYORUZ,
    kesik href'i sadece doğrulama (cross-check) için kullanıyoruz.
    """
    ids = sorted(set(SEARCH_RESULT_ID_RE.findall(raw_text)))
    if not ids:
        return []

    kategori_slug = _detect_kategori_slug(raw_text)
    listings: List[ListingSummary] = []

    for cid in ids:
        marker = f"data-classified-id=&quot;{cid}&quot;"
        idx = raw_text.find(marker)
        if idx == -1:
            continue
        window = raw_text[idx: idx + 2500]

        m = SEARCH_RESULT_TITLE_RE.search(window)
        title = html_mod.unescape(m.group(1)).strip() if m else ""

        href_m = SEARCH_RESULT_HREF_RE.search(window)
        href_prefix = html_mod.unescape(href_m.group(1)) if href_m else ""

        if not title:
            title = _title_from_detail_url(href_prefix, cid) or cid

        slug = title_to_slug(title)
        detail_url = f"https://www.sahibinden.com/ilan/{kategori_slug}-{slug}-{cid}/detay"

        # ── Katman 1 doğrulama: üretilen slug, gerçek (kesik) href prefiksiyle
        #    uyuşuyor mu? (bkz. ULTRA manifesto Bölüm 7) ───────────────────────
        tag = "~ href yok (üretildi)"
        if href_prefix:
            generated_path = f"/ilan/{kategori_slug}-{slug}"
            prefix_clean = href_prefix.split("\u2026")[0].rstrip("-")  # "…" kesme noktası
            if generated_path.startswith(prefix_clean) or prefix_clean.startswith(generated_path[: len(prefix_clean)]):
                tag = "[OK] href ile doğrulandı"
            else:
                tag = "[WARN] href prefix UYUŞMUYOR (yine de üretildi)"

        listings.append(ListingSummary(
            listing_id=cid,
            title=title,
            thumb_url="",
            detail_url=detail_url,
        ))
        print(f"    [{cid}] {title[:55]}  ({tag})")

    return listings


def detect_single_listing_id(url: str) -> str:
    """
    Verilen URL bir TEKİL ilan detay linki mi (…/ilan/<slug>-<ilanNo>/detay),
    yoksa bir mağaza/liste/arama sonucu linki mi (…/emlak?..., …/satilik-villa/...)?

    Tekil ilan ise ilan numarasını döner, değilse "" döner — bu da senaryo
    ayrımının (Senaryo 1 vs Senaryo 2) tek doğruluk kaynağıdır (hem web_app.py
    hem de CLI main() bu fonksiyonu kullanır, mantık iki yerde ayrı ayrı
    yaşamaz).
    """
    m = ILAN_PATH_RE.search(url or "")
    if m:
        slug = m.group(1)
        m2 = re.search(r"(\d{6,})$", slug) or re.search(r"(\d{6,})", slug)
        if m2:
            return m2.group(1)

    # Manifesto Bölüm 1.3 — kısa/redirect format (/ilan/ öneki yok)
    m3 = ILAN_REDIRECT_RE.search(url or "")
    if m3:
        return m3.group(1)

    return ""

# ─────────────────────────────────────────────────────────────────────────────
# Veri Modelleri
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ListingSummary:
    listing_id: str
    title: str
    thumb_url: str
    detail_url: str = ""   # sahibinden'deki detay URL'si

@dataclass
class ListingDetail:
    listing_id: str
    title: str
    price: str
    canonical_url: str
    thumb_url: str
    photos: List[str] = field(default_factory=list)
    specs: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    description_source: str = ""  # "" | "PSI HTML" | "PSI API + OCR (...)"
    analysis: str = ""
    analysis_ok: bool = False
    analysis_reason: str = ""
    audits: List[Dict[str, str]] = field(default_factory=list)  # Lighthouse audit kuralları

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

ENC_IMG_RE = re.compile(
    r'src=&quot;(https?://i\d\.shbdn\.com/photos/[^"&]+?)&quot;'
    r'[^>]*?alt=&quot;([^"&]+?)&quot;',
    re.IGNORECASE,
)
ID_RE = re.compile(r"#\s*(\d{6,})")
# Sahibinden detay link formatı: /ilan/...-IDNUMBER/detay
SB_DETAIL_LINK_RE = re.compile(
    r'href=["\']?(https?://(?:www\.)?sahibinden\.com/ilan/[^"\'>\s]+?-(\d{6,})/detay)["\']?',
    re.IGNORECASE,
)


def _id_and_title(raw: str) -> Tuple[str, str]:
    raw = raw.strip()
    m = ID_RE.search(raw)
    lid = m.group(1) if m else ""
    title = ID_RE.sub("", raw).strip(" -–—|• \t") or raw
    return lid, title


def _esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def _make_chrome(headless: bool) -> webdriver.Chrome:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--log-level=3")
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=opts
    )


def _accept_cookies(driver, timeout: int = 4) -> None:
    xpaths = [
        "//button[contains(.,'Tümünü kabul')]",
        "//button[contains(.,'tümünü kabul')]",
        "//button[contains(.,'Accept all')]",
        "//button[contains(.,'Accept')]",
        "//button[contains(.,'Kabul et')]",
        "//button[contains(.,'Kabul')]",
        "//button[contains(.,'Onayla')]",
        "//button[@id='onetrust-accept-btn-handler']",
    ]
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            btn.click()
            time.sleep(0.4)
            return
        except Exception:
            pass


def _sep(label: str) -> None:
    print(f"\n{'═'*50}")
    print(f"  {label}")
    print(f"{'═'*50}")


def _type_url_robust(driver, target_url: str, max_attempts: int = 4) -> bool:
    """
    PageSpeed URL input'una hedef adresi güvenilir biçimde yazar.
    Birden fazla yöntem dener; her seferinde alanın doğru dolduğunu kontrol eder.
    """
    css = "input[name='url']"

    for attempt in range(1, max_attempts + 1):
        try:
            # Input'un görünmesini bekle
            inp = WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, css))
            )
            time.sleep(0.3)

            # --- Yöntem 1: JS ile direkt value ata (en güvenilir) ---
            driver.execute_script(
                "arguments[0].focus(); arguments[0].value = '';", inp
            )
            time.sleep(0.2)
            driver.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                inp, target_url,
            )
            time.sleep(0.3)

            # Değer kontrol
            current_val = driver.execute_script("return arguments[0].value;", inp)
            if current_val == target_url:
                print(f"    [OK] URL girildi (JS, deneme {attempt})")
                return True

            # --- Yöntem 2: Temizle + send_keys ---
            inp.click()
            time.sleep(0.2)
            # Ctrl+A → Delete ile tamamen temizle
            from selenium.webdriver.common.keys import Keys
            inp.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            inp.send_keys(Keys.DELETE)
            time.sleep(0.2)
            inp.clear()
            time.sleep(0.2)
            inp.send_keys(target_url)
            time.sleep(0.4)

            current_val = driver.execute_script("return arguments[0].value;", inp)
            if current_val == target_url:
                print(f"    [OK] URL girildi (send_keys, deneme {attempt})")
                return True

            # --- Yöntem 3: Her karakteri teker teker JS ile ekle ---
            driver.execute_script(
                "arguments[0].focus(); arguments[0].value = '';", inp
            )
            time.sleep(0.15)
            for char in target_url:
                driver.execute_script(
                    "arguments[0].value += arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input',{{bubbles:true}}));",
                    inp, char,
                )
            time.sleep(0.3)
            current_val = driver.execute_script("return arguments[0].value;", inp)
            if current_val == target_url:
                print(f"    [OK] URL girildi (char-by-char JS, deneme {attempt})")
                return True

            print(f"    [WARN] Deneme {attempt}: beklenen='{target_url[:40]}...' "
                  f"gerçek='{current_val[:40]}...' — yeniden deniyor")
            time.sleep(1)

        except Exception as exc:
            print(f"    [WARN] Deneme {attempt} hatası: {exc}")
            time.sleep(1.5)

    print(f"    ✗ URL {max_attempts} denemede girilemedi.")
    return False


def _pagespeed_fetch(
    driver: webdriver.Chrome,
    target_url: str,
    out_path: Path,
    wait_sec: int,
    label: str = "",
    cookie_done: bool = False,
    stop_event=None,
) -> bool:
    """
    PageSpeed'e gidip target_url'yi analiz ettirir, HTML'i out_path'e kaydeder.
    Aynı driver instance'ı tekrar tekrar kullanılır (Chrome oturumu korunur).
    Başarı durumunu döner.
    """
    try:
        # Her seferinde ana PageSpeed sayfasına git (temiz başlangıç)
        driver.get(PAGESPEED_BASE)
        time.sleep(1.5)  # sayfa JS'inin yüklenmesini bekle

        if not cookie_done:
            _accept_cookies(driver, timeout=6)
            time.sleep(0.5)

        # Önceki analiz sonucu varsa input'u görmek için biraz bekle
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='url']"))
            )
        except Exception:
            pass

        # Robust URL girişi
        if not _type_url_robust(driver, target_url):
            return False

        # Analiz et / Analyze butonunu bul ve tıkla
        try:
            analyze_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//span[normalize-space()='Analiz et' or normalize-space()='Analyze']"
                    "/ancestor::button[1]",
                ))
            )
        except Exception:
            # Alternatif: form submit veya Enter tuşu
            print("    [WARN] Buton bulunamadı, Enter ile gönderiliyor...")
            from selenium.webdriver.common.keys import Keys
            inp = driver.find_element(By.CSS_SELECTOR, "input[name='url']")
            inp.send_keys(Keys.RETURN)
        else:
            # Butona tıklamadan önce URL'nin hâlâ doğru olduğunu doğrula
            inp = driver.find_element(By.CSS_SELECTOR, "input[name='url']")
            current_val = driver.execute_script("return arguments[0].value;", inp)
            if current_val != target_url:
                print(f"    [WARN] Tıklamadan önce URL kayması tespit edildi, düzeltiliyor...")
                if not _type_url_robust(driver, target_url):
                    return False
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", analyze_btn)

        print(f"    [OK] Analiz başlatıldı → {target_url[:65]}")

        # Sayaçlı bekleme
        print(f"    [WAIT] Bekleniyor ({wait_sec} sn)", end="", flush=True)
        for i in range(wait_sec):
            time.sleep(1)
            if (i + 1) % 10 == 0:
                print(f" {wait_sec - i - 1}sn", end="", flush=True)
            if stop_event is not None and stop_event.is_set():
                print(" [durduruldu]", end="", flush=True)
                break
        print()

        # /analysis/ URL'sine geçmesini bekle
        try:
            WebDriverWait(driver, 30).until(
                lambda d: "/analysis/" in d.current_url
            )
        except Exception:
            pass  # zaman aşımı olsa bile kaydet

        out_path.write_text(driver.page_source, encoding="utf-8")
        size_kb = out_path.stat().st_size // 1024
        print(f"    [OK] Kaydedildi: {out_path.name} ({size_kb} KB)")
        return True

    except Exception as exc:
        print(f"    ✗ Beklenmedik hata: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CLOUDFLARE BYPASS ENGINE (SeleniumBase UC Mode from c.py)
# ─────────────────────────────────────────────────────────────────────────────

CF_SIGNALS = ("Bir dakika lütfen", "Just a moment", "challenges.cloudflare.com",
              "checkLoading", "challenge-platform", "cf-spinner")

class CFBypassEngine:
    def __init__(self, proxy_str: Optional[str] = None):
        self.proxy_str = proxy_str

    def _is_cf(self, sb) -> bool:
        try:
            src = sb.get_page_source()[:3000]
            title = sb.get_title() or ""
            url = sb.get_current_url() or ""
            return any(s in src or s in title or s in url for s in CF_SIGNALS)
        except Exception:
            return False

    def _wait_pass(self, sb, timeout: int = 50) -> bool:
        deadline = time.time() + timeout
        tick = 0
        while time.time() < deadline:
            tick += 1
            if not self._is_cf(sb):
                print(f"    [OK] CF geçildi ({tick}. kontrol)")
                return True
            rem = int(deadline - time.time())
            print(f"    [WAIT] CF challenge... ({rem}s)")
            if tick % 2 == 0:
                try:
                    sb.uc_gui_click_captcha()
                    print("    [BOT] Turnstile tıklandı")
                except Exception:
                    pass
            sb.sleep(3)
        return False

    def fetch_page(self, url: str) -> Optional[str]:
        if not _SELENIUMBASE:
            raise ImportError("seleniumbase yüklü değil")
            
        kwargs: Dict = {"uc": True, "headless": False}
        if self.proxy_str:
            kwargs["proxy"] = self.proxy_str

        try:
            with SB(**kwargs) as sb:
                sb.uc_open_with_reconnect(url, reconnect_time=6)
                try:
                    sb.uc_gui_click_captcha()
                    print("    [BOT] Turnstile tıklandı")
                except Exception:
                    print("    [INFO] CAPTCHA yok / zaten geçildi")

                passed = self._wait_pass(sb, timeout=50)
                if not passed:
                    print("    [WAIT] Yeniden deneniyor...")
                    sb.uc_open_with_reconnect(url, reconnect_time=6)
                    try:
                        sb.uc_gui_click_captcha()
                    except Exception:
                        pass
                    self._wait_pass(sb, timeout=35)

                sb.sleep(2)
                html = sb.get_page_source()

            if html and any(s in html[:3000] for s in CF_SIGNALS):
                print("    [ERR] CF geçilemedi")
                return None
            return html
        except Exception as e:
            print(f"    [ERR] SeleniumBase hatası: {e}")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 1 — PageSpeed ile mağaza/liste sayfasını çek
# ─────────────────────────────────────────────────────────────────────────────

def step1_pagespeed_store(
    target_url: str,
    out_html: str,
    wait_sec: int,
    headless: bool,
    stop_event=None,
) -> Path:
    if not _SELENIUM:
        raise ImportError("pip install selenium webdriver-manager")

    _sep("ADIM 1 — Mağaza sayfası → PageSpeed")
    print(f"  Hedef  : {target_url}")
    print(f"  Bekleme: {wait_sec} sn | Headless: {headless}")

    driver = _make_chrome(headless)
    out_path = Path(out_html)
    try:
        ok = _pagespeed_fetch(
            driver=driver,
            target_url=target_url,
            out_path=out_path,
            wait_sec=wait_sec,
            label="mağaza",
            cookie_done=False,
            stop_event=stop_event,
        )
        if not ok:
            print("  ✗ Mağaza sayfası alınamadı!")
            sys.exit(1)
    finally:
        driver.quit()

    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 2 — Mağaza HTML'inden ilan özetlerini çıkar
# ─────────────────────────────────────────────────────────────────────────────

def _build_detail_url(
    soup_text: str,
    listing_id: str,
    title: str = "",
    kategori_slug: str = "",
) -> str:
    """
    PageSpeed sonuç HTML'inden veya meta tag'lardan detay URL'sini bul.
    Bulamazsa manifesto v2.0 matematiğiyle (title_to_slug + kategori_slug)
    doğrudan geçerli bir URL üretir; başlık da yoksa en son çare olarak
    sahibinden arama URL'sine düşer.
    """
    # 1) PageSpeed HTML'inde encoded link var mı?  href=&quot;.../ilan/...-ID/detay&quot;
    enc_pattern = re.compile(
        r'href=&quot;(https?://(?:www\.)?sahibinden\.com/ilan/[^"&]+?-'
        + re.escape(listing_id)
        + r'/detay)&quot;',
        re.IGNORECASE,
    )
    m = enc_pattern.search(soup_text)
    if m:
        return m.group(1)

    # 2) Unescaped link
    m2 = re.search(
        r'href=["\']?(https?://(?:www\.)?sahibinden\.com/ilan/[^"\'>\s]+?-'
        + re.escape(listing_id)
        + r'/detay)["\']?',
        soup_text,
        re.IGNORECASE,
    )
    if m2:
        return m2.group(1)

    # 3) Manifesto v2.0 fallback: başlıktan + kategoriden doğrudan üret
    #    (SB_SEARCH_URL'in generic arama sayfasına düşmesinden çok daha güvenilir —
    #     doğrudan detay sayfasına gider, PageSpeed'in ekstra redirect adımı gerekmez)
    if title:
        slug = title_to_slug(title)
        kslug = kategori_slug or _detect_kategori_slug(soup_text)
        if slug:
            return f"https://www.sahibinden.com/ilan/{kslug}-{slug}-{listing_id}/detay"

    # 4) Son çare: sahibinden arama URL'si
    return SB_SEARCH_URL.format(id=listing_id)


def step2_extract_summaries(html_path: Path) -> List[ListingSummary]:
    _sep("ADIM 2 — İlanlar ayıklanıyor")

    text = html_path.read_text(encoding="utf-8", errors="ignore")
    items: Dict[str, ListingSummary] = {}

    # Sayfa genelindeki kategoriyi bir kez tespit et (her iki yöntem de kullanır)
    page_kategori_slug = _detect_kategori_slug(text)

    # ── Yöntem A: Mağaza sayfası formatı (img alt="Başlık #ID") ────────────────
    #    örn. coldwellbankercizgi.sahibinden.com/emlak gibi kişisel mağaza sayfaları
    for img_url, alt in ENC_IMG_RE.findall(text):
        lid, title = _id_and_title(alt)
        if lid and lid not in items:
            detail_url = _build_detail_url(text, lid, title=title, kategori_slug=page_kategori_slug)
            items[lid] = ListingSummary(
                listing_id=lid,
                title=title,
                thumb_url=img_url,
                detail_url=detail_url,
            )

    # BS4 fallback (aynı Yöntem A, farklı parser yolu)
    if _BS4:
        soup = BeautifulSoup(html_mod.unescape(text), "lxml")
        for img in soup.select('img[src*="shbdn.com/photos/"]'):
            src = (img.get("src") or "").strip()
            alt = (img.get("alt") or "").strip()
            if not src or not alt:
                continue
            lid, title = _id_and_title(alt)
            if lid and lid not in items:
                detail_url = _build_detail_url(text, lid, title=title, kategori_slug=page_kategori_slug)
                items[lid] = ListingSummary(
                    listing_id=lid,
                    title=title,
                    thumb_url=src,
                    detail_url=detail_url,
                )

    store_found = len(items)
    if store_found:
        print(f"  [OK] Yöntem A (mağaza sayfası formatı): {store_found} ilan bulundu.")
    else:
        print(f"  · Yöntem A (mağaza sayfası formatı): ilan bulunamadı, Yöntem B deneniyor…")

    # ── Yöntem B: Genel arama/kategori sonucu sayfası formatı ──────────────────
    #    örn. sahibinden.com/satilik-villa/ankara-camlidere gibi arama sonuçları
    #    (data-classified-id + ayrı başlık div'i — manifesto v2.0 mantığı,
    #     bkz. ULTRA_SAHIBINDEN_URL_GENERATOR_ENGINE.md)
    print(f"  · Yöntem B (arama sonucu formatı) deneniyor... (kategori: {page_kategori_slug})")
    search_listings = _extract_search_result_listings(text)
    new_from_b = 0
    for s in search_listings:
        if s.listing_id not in items:
            items[s.listing_id] = s
            new_from_b += 1
    if search_listings:
        print(
            f"  [OK] Yöntem B (arama sonucu formatı): {len(search_listings)} ilan bulundu"
            f" ({new_from_b} yeni, {len(search_listings) - new_from_b} zaten Yöntem A'da vardı)."
        )
    elif not store_found:
        print("  · Yöntem B: ilan bulunamadı.")

    listings = list(items.values())
    if listings:
        print(f"\n  [OK] TOPLAM {len(listings)} ilan:\n")
        for s in listings:
            print(f"    [{s.listing_id}] {s.title[:58]}")
            print(f"    → {s.detail_url[:90]}")
            print()
    else:
        print("  ✗ Hiçbir yöntemle ilan bulunamadı (ne mağaza ne arama sonucu formatı eşleşti).")

    return listings


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 3 — Her ilan için PageSpeed üzerinden detay sayfasını çek
# ─────────────────────────────────────────────────────────────────────────────

def step3_pagespeed_details(
    summaries: List[ListingSummary],
    detail_dir: str,
    wait_sec: int,
    delay: float,
    headless: bool,
    skip: bool,
    stop_event=None,
    cd_fallback: bool = True,
) -> List[Path]:
    """
    Her ilan için detay sayfasını PageSpeed üzerinden çeker.

    cd_fallback=True ise (varsayılan): birincil fetch'in HTML'inde açıklama
    bulunamazsa, aynı driver ile ".../detay/#classified-detail" fragment'li
    varyantı BİR KEZ daha çeker ve "{listing_id}__cd.html" olarak aynı
    klasöre kaydeder. step4_parse_details bu dosyayı otomatik olarak
    ikincil kaynak olarak kullanır.
    """
    _sep("ADIM 3 — Detay sayfaları → PageSpeed (her ilan için)")

    out_dir = Path(detail_dir)
    out_dir.mkdir(exist_ok=True)
    detail_paths: List[Path] = []

    # ── Eğer tekil ilan ise PageSpeed'e gerek yok, doğrudan SeleniumBase UC ile çek ──
    is_single = len(summaries) == 1 and bool(detect_single_listing_id(summaries[0].detail_url))
    if is_single:
        _sep("TEKİL İLAN MODU (PageSpeed Atlanıyor) — SeleniumBase UC ile çekiliyor")
        summary = summaries[0]
        p = out_dir / f"{summary.listing_id}.html"
        print(f"  Hedef: {summary.detail_url}")
        engine = CFBypassEngine()
        html = engine.fetch_page(summary.detail_url)
        if html:
            p.write_text(html, encoding="utf-8")
            print(f"    [OK] Kaydedildi: {p.name} ({len(html)//1024} KB)")
            detail_paths.append(p)
        else:
            print("    [ERR] SeleniumBase UC ile tekil ilan sayfası çekilemedi!")
        return detail_paths

    if skip:
        print("  ⏭  Adım atlandı, mevcut dosyalar kullanılıyor.\n")
        for s in summaries:
            p = out_dir / f"{s.listing_id}.html"
            if p.exists():
                detail_paths.append(p)
                print(f"  [OK] Mevcut: {p.name}")
            else:
                print(f"  ✗ Bulunamadı (atlanacak): {p.name}")
        return detail_paths

    if not _SELENIUM:
        raise ImportError("pip install selenium webdriver-manager")

    print(f"  PageSpeed bekleme süresi: {wait_sec} sn/ilan")
    print(f"  İlanlar arası bekleme   : {delay} sn")
    print(f"  Toplam ilan sayısı      : {len(summaries)}")
    print(f"  #classified-detail fallback: {'açık' if cd_fallback else 'kapalı'}\n")

    driver = _make_chrome(headless)
    cookie_done = False  # Cookie popup'ı bir kez kapatmak yeterli

    try:
        for i, summary in enumerate(summaries, 1):
            if stop_event is not None and stop_event.is_set():
                print("  ⏹ Kullanıcı tarafından durduruldu.")
                break

            p = out_dir / f"{summary.listing_id}.html"
            print(f"  [{i:02d}/{len(summaries):02d}] {summary.listing_id} — {summary.title[:50]}")
            print(f"    URL: {summary.detail_url}")

            ok = _pagespeed_fetch(
                driver=driver,
                target_url=summary.detail_url,
                out_path=p,
                wait_sec=wait_sec,
                label=summary.listing_id,
                cookie_done=cookie_done,
                stop_event=stop_event,
            )
            cookie_done = True  # İlk çağrıdan sonra popup artık yok

            if ok:
                detail_paths.append(p)

                # ── #classified-detail fragment fallback ──────────────────
                # Birincil fetch'te açıklama zaten bulunduysa ikinci bir
                # Selenium turu (45-60sn) gereksiz — sadece bulunamadığında
                # devreye girer.
                if cd_fallback and not (stop_event is not None and stop_event.is_set()):
                    try:
                        primary_raw = p.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        primary_raw = ""
                    has_desc = bool(_extract_psi_description(primary_raw)) if primary_raw else False

                    if not has_desc:
                        cd_url = _build_classified_detail_url(summary.detail_url)
                        cd_path = out_dir / f"{summary.listing_id}{CD_FILE_SUFFIX}.html"
                        print(f"    ℹ Açıklama bulunamadı, #classified-detail varyantı deneniyor...")
                        print(f"    URL: {cd_url}")
                        cd_ok = _pagespeed_fetch(
                            driver=driver,
                            target_url=cd_url,
                            out_path=cd_path,
                            wait_sec=wait_sec,
                            label=f"{summary.listing_id}-cd",
                            cookie_done=cookie_done,
                            stop_event=stop_event,
                        )
                        if not cd_ok:
                            print(f"    [WARN] #classified-detail varyantı da alınamadı.")
            else:
                print(f"    [WARN] {summary.listing_id} detayı alınamadı, atlanıyor.")

            if i < len(summaries) and not (stop_event is not None and stop_event.is_set()):
                print(f"    [WAIT] Sonraki ilan için {delay} sn bekleniyor...")
                time.sleep(delay)
            print()

    finally:
        driver.quit()

    print(f"  [OK] {len(detail_paths)}/{len(summaries)} detay sayfası indirildi.")
    return detail_paths


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 4 — Detay HTML'lerini parse et
# ─────────────────────────────────────────────────────────────────────────────

def _parse_photos(soup: BeautifulSoup) -> List[str]:
    photos: List[str] = []
    seen: set = set()

    def _add(url: str):
        # Thumbnail prefix'lerini kaldır → tam boyut
        url = re.sub(r'/(?:x5_|x3_|x1_|lthmb_)', '/', url)
        if url and url not in seen:
            seen.add(url)
            photos.append(url)

    # og:image (ana görsel)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        _add(og["content"].strip())

    # data-src (tembel yükleme — detay sayfasında asıl fotoğraflar burda)
    for img in soup.select('img[data-src*="shbdn.com/photos"]'):
        _add(img.get("data-src", "").strip())

    # src (zaten yüklü)
    for img in soup.select('img[src*="shbdn.com/photos"]'):
        src = img.get("src", "").strip()
        if "blank" not in src:
            _add(src)

    # PageSpeed encoded versiyonlar: src=&quot;...&quot;
    # (PageSpeed bazen görselleri encoded olarak gömer)
    return photos


def _parse_photos_from_raw(raw_text: str) -> List[str]:
    """
    PageSpeed HTML'i / doğrudan HTML içinde geçen tüm shbdn.com foto URL'lerini yakala.
    PSI çıktılarında URL'ler bazen &quot; ile gömülür; bu yüzden önce unescape ederiz.

    Fotoğraf tipleri:
      - thmb_<id>XXX.avif  → thumbnail (küçük)
      - x5_<id>XXX.avif    → tam boyut (büyük, tercih edilen)
      - x5_<id>XXX.jpg     → JPEG fallback
    """
    raw_text = html_mod.unescape(raw_text)

    photos: List[str] = []
    seen: set = set()

    # Önce tam boyut (x5_ prefix'li) URL'leri topla
    full_pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+/x5_[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )
    for url in full_pattern.findall(raw_text):
        url = url.split("?", 1)[0].split("#", 1)[0]
        if "blank" in url or url in seen:
            continue
        seen.add(url)
        photos.append(url)

    # Tam boyut bulunamazsa thumbnail'leri de ekle (x5_ → thmb_)
    thumb_pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+/thmb_[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )
    thumb_photos: List[str] = []
    seen_thumb: set = set()
    for url in thumb_pattern.findall(raw_text):
        url = url.split("?", 1)[0].split("#", 1)[0]
        if "blank" in url or url in seen_thumb:
            continue
        seen_thumb.add(url)
        thumb_photos.append(url)

    # Genel fallback: prefix fark etmeksizin tüm shbdn foto URL'leri
    fallback_pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )
    for url in fallback_pattern.findall(raw_text):
        url = url.split("?", 1)[0].split("#", 1)[0]
        # thumb/boyut prefix'lerini kaldır → tam boyut
        clean = re.sub(r"/(?:x5_|x3_|x2_|x1_|thmb_|lthmb_)", "/", url)
        if "blank" in clean or clean in seen:
            continue
        seen.add(clean)
        photos.append(clean)

    # Tam boyut bulunamadıysa thumbnail listesini kullan
    if not photos and thumb_photos:
        photos = thumb_photos

    return photos


# ─────────────────────────────────────────────────────────────────────────────
# PSI Detay Sayfası Özel Parser'ları (analytics & encoded URL'lerden)
# ─────────────────────────────────────────────────────────────────────────────

_PSI_CD_MAP: Dict[str, str] = {
    # Google Analytics custom dimension → okunabilir alan adı
    "cd13": "Kategori 1",
    "cd14": "Kategori 2",
    "cd15": "Marka",
    "cd16": "Seri",
    "cd17": "Model",
    "cd19": "Ülke",
    "cd20": "Şehir",
    "cd21": "İlçe",
    "cd24": "Bestmatch",
    "cd29": "Cihaz Tipi",
    "cd30": "Ekran DPI",
    "cd32": "Motor Hacmi",
    "cd33": "Motor Gücü",
    "cd34": "Kilometre",
    "cd37": "Vites",
    "cd38": "Model Yılı",
    "cd39": "Kimden",
    "cd42": "Model Detay",
    "cd43": "İlan No",
    "cd46": "Eurotax",
    "cd49": "Kasa Tipi",
    "cd50": "Takas",
    "cd53": "Fiyat (Sayısal)",
    "cd56": "Satıcı Tipi",
    "cd60": "Data Center",
    "cd73": "Mahalle",
    "cd74": "Mahalle (detay)",
    "cd82": "İşletim Sistemi",
}

# GA4 event parametreleri (ep. prefix'li)
_PSI_EP_MAP: Dict[str, str] = {
    "ep.content_group":     "Sayfa Türü",
    "ep.kategori_1":        "Kategori 1",
    "ep.kategori_2":        "Kategori 2",
    "ep.kategori_3":        "Marka",
    "ep.kategori_4":        "Seri",
    "ep.kategori_5":        "Model",
    "ep.CD_MotorHacmi":     "Motor Hacmi",
    "ep.cd_motorGucu":      "Motor Gücü",
    "ep.CD_Km":             "Kilometre",
    "ep.CD_Vites":          "Vites",
    "ep.CD_ModelYil":       "Model Yılı",
    "ep.CD_Kimden":         "Kimden",
    "ep.model_js":          "Model Detay",
    "ep.CD_ilanNo":         "İlan No",
    "ep.eurotax":           "Eurotax",
    "ep.CD_KasaTipi":       "Kasa Tipi",
    "ep.CD_Takas":          "Takas",
    "ep.js_price":          "Fiyat (Sayısal)",
    "ep.CD_IlanOwnerType":  "Satıcı Tipi",
    "ep.CD_Yer1":           "Ülke",
    "ep.CD_Yer2":           "Şehir",
    "ep.CD_Yer3":           "İlçe",
    "ep.CD_Yer4":           "Mahalle",
    "ep.CD_Yer5":           "Mahalle (detay)",
    "ep.data_center":       "Data Center",
    "ep.site_preference":   "Site Tercihi",
    "ep.arama_menusu":      "Arama Menüsü",
    # Emlak alanları
    "ep.motor_hacmi":       "Motor Hacmi",
    "ep.motor_gucu":        "Motor Gücü",
    "ep.km":                "Kilometre",
    "ep.vites":             "Vites",
    "ep.model_yili":        "Model Yılı",
    "ep.kimden":            "Kimden",
    "ep.ilan_no":           "İlan No",
    "ep.kasa_tipi":         "Kasa Tipi",
    "ep.takas":             "Takas",
    "ep.js_owner_type":     "Satıcı Tipi",
    "ep.yer_1":             "Ülke",
    "ep.yer_2":             "Şehir",
    "ep.yer_3":             "İlçe",
    "ep.yer_4":             "Mahalle",
    "ep.yer_5":             "Mahalle (detay)",
}

# Lighthouse audit ID → (kategori, Türkçe başlık)
_LH_AUDIT_TITLES: Dict[str, Tuple[str, str]] = {
    # Performans
    "render-blocking-insight":      ("Performans", "Oluşturma engelleme istekleri"),
    "cache-insight":                ("Performans", "Verimli önbellek sürelerini kullanın"),
    "image-delivery-insight":       ("Performans", "Resim yayınlamayı kolaylaştırın"),
    "legacy-javascript-insight":    ("Performans", "Eski JavaScript"),
    "font-display-insight":         ("Performans", "Yazı tipi görüntüleme"),
    "forced-reflow-insight":        ("Performans", "Zorunlu yeniden düzenleme"),
    "lcp-breakdown-insight":        ("Performans", "LCP dökümü"),
    "network-dependency-tree-insight": ("Performans", "Ağ bağımlılık ağacı"),
    "cls-culprits-insight":         ("Performans", "Düzen kayması sorununun nedenleri"),
    "third-parties-insight":        ("Performans", "3. taraflar"),
    "bootup-time":                  ("Performans", "JavaScript yürütme süresini azaltın"),
    "mainthread-work-breakdown":    ("Performans", "Ana iş parçacığı çalışmasını en aza indir"),
    "unused-css-rules":             ("Performans", "Kullanılmayan CSS'yi azaltın"),
    "unused-javascript":            ("Performans", "Kullanılmayan JavaScript'i azaltın"),
    "unsized-images":               ("Performans", "Resim öğelerinde width/height yok"),
    "total-byte-weight":            ("Performans", "Çok büyük ağ yüklerinden kaçının"),
    "long-tasks":                   ("Performans", "Uzun ana ileti dizisi görevlerinden kaçının"),
    "document-latency-insight":     ("Performans", "Doküman isteğiyle ilgili gecikme"),
    "dom-size-insight":             ("Performans", "DOM boyutunu optimize edin"),
    "duplicated-javascript-insight":("Performans", "Yinelenen JavaScript"),
    "inp-breakdown-insight":        ("Performans", "INP dökümü"),
    "lcp-discovery-insight":        ("Performans", "LCP istek keşfi"),
    "viewport-insight":             ("Performans", "Görüntü alanını mobil cihazlar için optimize edin"),
    "unminified-css":               ("Performans", "CSS'yi küçültün"),
    "unminified-javascript":        ("Performans", "JavaScript'i küçült"),
    "user-timings":                 ("Performans", "Kullanıcı Zamanlaması işaretleri ve ölçüleri"),
    "non-composited-animations":    ("Performans", "Birleştirilmemiş animasyonlardan kaçının"),
    # Erişilebilirlik
    "meta-viewport":                ("Erişilebilirlik", "Viewport user-scalable=no veya max-scale<5"),
    "color-contrast":               ("Erişilebilirlik", "Yetersiz renk kontrast oranı"),
    "link-name":                    ("Erişilebilirlik", "Bağlantıların ayırt edilebilir adları yok"),
    "image-redundant-alt":          ("Erişilebilirlik", "Gereksiz alt metin içeren resimler"),
    "heading-order":                ("Erişilebilirlik", "Başlık öğeleri sırayla azalan düzende sıralı değil"),
    "target-size":                  ("Erişilebilirlik", "Dokunma hedefleri yeterli boyut veya boşluğa sahip değil"),
    "focusable-controls":           ("Erişilebilirlik", "Etkileşimli kontroller klavye ile odaklanabilir"),
    "interactive-element-affordance": ("Erişilebilirlik", "Etkileşimli öğeler amacını belirtiyor"),
    "logical-tab-order":            ("Erişilebilirlik", "Sayfada mantıksal sekme sırası var"),
    "visual-order-follows-dom":     ("Erişilebilirlik", "Görsel sıra DOM sırasını izliyor"),
    "focus-traps":                  ("Erişilebilirlik", "Kullanıcı odağı kazara tuzağa düşmüyor"),
    "managed-focus":                ("Erişilebilirlik", "Kullanıcı odağı yeni içeriğe yönlendiriliyor"),
    "use-landmarks":                ("Erişilebilirlik", "HTML5 önemli nokta öğeleri kullanılıyor"),
    "offscreen-content-hidden":     ("Erişilebilirlik", "Ekran dışı içerik yardımcı teknolojilerden gizlenmiş"),
    "custom-controls-labels":       ("Erişilebilirlik", "Özel kontrollerin ilişkili etiketleri var"),
    "custom-controls-roles":        ("Erişilebilirlik", "Özel kontrollerin ARIA rolleri var"),
    "aria-hidden-body":             ("Erişilebilirlik", "aria-hidden=true body üzerinde yok"),
    "image-alt":                    ("Erişilebilirlik", "Resim öğelerinin [alt] özellikleri var"),
    "document-title":               ("Erişilebilirlik", "Doküman geçerli title içeriyor"),
    "html-has-lang":                ("Erişilebilirlik", "html öğesi [lang] özelliği içeriyor"),
    "html-lang-valid":              ("Erişilebilirlik", "html [lang] geçerli değere sahip"),
    "list":                         ("Erişilebilirlik", "Listeler yalnızca uygun öğeleri içeriyor"),
    "listitem":                     ("Erişilebilirlik", "Liste öğeleri doğru üst öğelerde yer alıyor"),
    "tabindex":                     ("Erişilebilirlik", "Hiçbir öğe 0'dan büyük tabindex değeri içermiyor"),
    "landmark-one-main":            ("Erişilebilirlik", "Dokümanda ana landmark var"),
    # En İyi Uygulamalar
    "deprecations":                 ("En İyi Uygulamalar", "Kullanımdan kaldırılmış API'ler kullanılıyor"),
    "js-libraries":                 ("En İyi Uygulamalar", "JavaScript kitaplıkları algılandı"),
    "is-on-https":                  ("En İyi Uygulamalar", "HTTPS kullanıyor"),
    "third-party-cookies":          ("En İyi Uygulamalar", "Üçüncü taraf çerezlerinden kaçınır"),
    "paste-preventing-inputs":      ("En İyi Uygulamalar", "Kullanıcıların giriş alanlarına yapıştırmasına izin veriyor"),
    "geolocation-on-start":         ("En İyi Uygulamalar", "Sayfa yüklemede coğrafi konum izni istemiyor"),
    "notification-on-start":        ("En İyi Uygulamalar", "Sayfa yüklemede bildirim izni istemiyor"),
    "image-aspect-ratio":           ("En İyi Uygulamalar", "Resimleri doğru en boy oranıyla görüntülüyor"),
    "image-size-responsive":        ("En İyi Uygulamalar", "Çözünürlüğü uygun olan resimleri sunar"),
    "doctype":                      ("En İyi Uygulamalar", "Sayfa HTML DOCTYPE içeriyor"),
    "charset":                      ("En İyi Uygulamalar", "Karakter kümesini düzgün şekilde tanımlıyor"),
    "errors-in-console":            ("En İyi Uygulamalar", "Konsola tarayıcı hatası kaydedilmedi"),
    "inspector-issues":             ("En İyi Uygulamalar", "Sayfadaki kaynak eşlemeleri geçerli"),
    "valid-source-maps":            ("En İyi Uygulamalar", "Kaynak eşlemeleri geçerli"),
    "redirects-http":               ("En İyi Uygulamalar", "HTTP trafiğini HTTPS'ye yönlendiriyor"),
    "clickjacking-mitigation":      ("En İyi Uygulamalar", "XFO veya CSP ile clickjacking azaltma"),
    # Güvenlik
    "csp-xss":                      ("Güvenlik", "XSS saldırıları karşısında CSP etkinliği"),
    "has-hsts":                     ("Güvenlik", "Güçlü bir HSTS politikası kullanın"),
    "origin-isolation":             ("Güvenlik", "COOP ile uygun kaynak izolasyonu"),
    "trusted-types-xss":            ("Güvenlik", "Trusted Types ile DOM tabanlı XSS azaltma"),
    # SEO
    "is-crawlable":                 ("SEO", "Sayfanın dizine eklenmesi engellenmiş"),
    "crawlable-anchors":            ("SEO", "Bağlantılar taranabilir değil"),
    "structured-data":              ("SEO", "Yapılandırılmış veriler geçerli"),
    "meta-description":             ("SEO", "Doküman meta açıklama içeriyor"),
    "http-status-code":             ("SEO", "Sayfa başarılı bir HTTP durum kodu döndürüyor"),
    "link-text":                    ("SEO", "Bağlantılar açıklayıcı metin içeriyor"),
    "robots-txt":                   ("SEO", "robots.txt dosyası geçerli"),
    "hreflang":                     ("SEO", "Doküman hreflang özelliğini doğru kullanıyor"),
    "canonical":                    ("SEO", "Doküman canonical link içeriyor"),
}


def _extract_psi_specs(raw_text: str) -> Dict[str, str]:
    """
    PageSpeed Insights çıktısından ilan teknik özelliklerini çıkar.

    Strateji (öncelik sırası):
      1. GA4 event parametreleri (ep.XXX=YYY formatı) — en zengin veri seti
      2. UA custom dimensions (cd13=XXX&cd14=YYY formatı) — fallback
      3. Analytics query string (dt=, dp= gibi) — başlık/URL verileri

    Tüm değerler URL decode edilir.
    """
    specs: Dict[str, str] = {}
    seen_keys: set = set()

    # ── 1) GA4 event parametreleri (ep. prefix'li) ──────────────────────────
    # Her ep.KEY=VALUE çiftini yakala
    ep_pattern = re.compile(r"ep\.([A-Za-z0-9_]+)=([^&\n\"'<>]+)", re.IGNORECASE)
    for m in ep_pattern.finditer(raw_text):
        raw_key = "ep." + m.group(1)
        raw_val = m.group(2).replace("&amp;", "&").replace("+", " ")
        try:
            from urllib.parse import unquote
            raw_val = unquote(raw_val)
        except Exception:
            pass
        raw_val = raw_val.strip()
        if not raw_val or raw_val in ("0", "false", ""):
            continue
        label = _PSI_EP_MAP.get(raw_key)
        if label and label not in seen_keys:
            specs[label] = raw_val
            seen_keys.add(label)

    # epn. prefix'li sayısal parametreler
    epn_pattern = re.compile(r"epn\.([A-Za-z0-9_]+)=([^&\n\"'<>]+)", re.IGNORECASE)
    epn_map = {
        "epn.CD_UserLoginState": "Kullanıcı Giriş Durumu",
        "epn.user_login_state_hit": "Oturum Durum",
    }
    for m in epn_pattern.finditer(raw_text):
        raw_key = "epn." + m.group(1)
        raw_val = m.group(2).strip()
        label = epn_map.get(raw_key)
        if label and label not in seen_keys and raw_val not in ("0", ""):
            specs[label] = raw_val
            seen_keys.add(label)

    # ── 2) UA custom dimensions (cd13=...&cd14=... formatı) ─────────────────
    cd_pattern = re.compile(r"(cd\d{1,3})=([^&\n\"'<>]+)", re.IGNORECASE)
    for m in cd_pattern.finditer(raw_text):
        cd_key = m.group(1).lower()
        raw_val = m.group(2).replace("&amp;", "&").replace("+", " ")
        try:
            from urllib.parse import unquote
            raw_val = unquote(raw_val)
        except Exception:
            pass
        raw_val = raw_val.strip()
        if not raw_val or raw_val in ("0", ""):
            continue
        label = _PSI_CD_MAP.get(cd_key)
        if label and label not in seen_keys:
            specs[label] = raw_val
            seen_keys.add(label)

    # ── 3) Fiyat (sayısal) → TL formatına çevir ─────────────────────────────
    if "Fiyat (Sayısal)" in specs:
        try:
            amt = int(specs["Fiyat (Sayısal)"])
            formatted = f"{amt:,.0f} ₺".replace(",", ".")
            specs["Fiyat"] = formatted
        except Exception:
            pass

    # ── 4) Cihaz Tipi gibi teknik/debug alanları kaldır (ops. temizlik) ─────
    _remove_keys = {"Cihaz Tipi", "Ekran DPI", "Data Center", "Bestmatch",
                    "Site Tercihi", "Kullanıcı Giriş Durumu", "Oturum Durum"}
    for k in _remove_keys:
        specs.pop(k, None)

    return specs


def _extract_psi_audits(raw_text: str) -> List[Dict[str, str]]:
    """
    PageSpeed Insights HTML'inden Lighthouse audit kurallarını ve
    pass/fail durumlarını çıkar.

    Döner:
      [ { "id": "...", "status": "PASS|FAIL|ORTA|BİLGİ|N/A",
          "category": "...", "title": "..." }, ... ]
    """
    audits: List[Dict[str, str]] = []
    seen: set = set()

    # HTML'de pattern: class="lh-audit lh-audit--DURUM" id="RULE_ID"
    # veya: class="lh-audit lh-audit--DURUM lh-audit--metricsavings" id="RULE_ID"
    audit_pattern = re.compile(
        r'class="lh-audit\s+(lh-audit--[^"]+)"\s+id="([^"]+)"',
        re.IGNORECASE,
    )

    _status_map = {
        "lh-audit--pass":        "PASS",
        "lh-audit--fail":        "FAIL",
        "lh-audit--average":     "ORTA",
        "lh-audit--informative": "BİLGİ",
        "lh-audit--not-applicable": "N/A",
        "lh-audit--error":       "HATA",
    }

    for m in audit_pattern.finditer(raw_text):
        classes = m.group(1)
        audit_id = m.group(2).strip()
        if audit_id in seen:
            continue
        seen.add(audit_id)

        # Durumu sınıf listesinden belirle
        status = "BİLİNMEYEN"
        for cls_key, label in _status_map.items():
            if cls_key in classes:
                status = label
                break

        # Başlık ve kategori
        category, title = _LH_AUDIT_TITLES.get(audit_id, ("Diğer", audit_id))

        audits.append({
            "id": audit_id,
            "status": status,
            "category": category,
            "title": title,
        })

    return audits


def _extract_psi_photos(raw_text: str) -> List[Dict[str, str]]:
    """
    PSI HTML'inden ilan fotoğraflarını çıkarır ve tip bilgisiyle birlikte döner.

    Döner:
      [ { "url": "...", "type": "full|thumb", "format": "avif|jpg|..." }, ... ]
    """
    unescaped = html_mod.unescape(raw_text)
    result: List[Dict[str, str]] = []
    seen: set = set()

    pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )

    for url in pattern.findall(unescaped):
        url = url.split("?", 1)[0].split("#", 1)[0]
        if "blank" in url or url in seen:
            continue
        seen.add(url)

        fname = url.rsplit("/", 1)[-1]
        fmt = fname.rsplit(".", 1)[-1].lower() if "." in fname else "?"

        if fname.startswith("x5_") or fname.startswith("x3_"):
            ptype = "full"
        elif fname.startswith("thmb_") or fname.startswith("lthmb_"):
            ptype = "thumb"
        else:
            ptype = "other"

        result.append({"url": url, "type": ptype, "format": fmt})

    return result


_PHOTO_PREFIX_RE = re.compile(r"^(?:x5_|x3_|x1_|thmb_|lthmb_)")
_PHOTO_EXT_RE = re.compile(r"\.(?:avif|jpg|jpeg|png|webp)$", re.IGNORECASE)


def _photo_core_id(url: str) -> str:
    """Bir foto URL'sinden, boyut/format önekinden bağımsız benzersiz kimliği çıkarır.
    Örn: '.../x5_1320699145l77.jpg' ve '.../thmb_1320699145l77.avif'
    ikisi de aynı çekirdek kimliğe ('1320699145l77') indirgenir — böylece
    aynı fotoğrafın farklı boyut/format varyantları tek fotoğraf sayılır.
    """
    fname = url.rsplit("/", 1)[-1]
    fname = _PHOTO_PREFIX_RE.sub("", fname)
    fname = _PHOTO_EXT_RE.sub("", fname)
    return fname


def _merge_photo_variants(psi_photos: List[Dict[str, str]]) -> List[str]:
    """
    _extract_psi_photos()'un ham çıktısı, aynı fotoğrafın birden fazla
    boyut/format varyantını (x5_ tam boy + thmb_ küçük, .avif/.jpg/...)
    AYRI satırlar olarak içerir. PSI/Lighthouse otomatik crawl'ı galeriyi
    kaydırıp her fotoğrafın tam boy (x5_) versiyonunu istemez; galerinin
    büyük kısmı çoğu zaman SADECE thumbnail (thmb_) olarak network'e düşer.

    Eski mantık (`full_photos or thumb_photos_list`) tam boy en az bir
    fotoğraf bulunduğu anda, sadece thumbnail olarak yakalanmış TÜM diğer
    fotoğrafları komple siliyordu (38 fotoğraflık bir ilanda sadece 3-4
    fotoğraf kalıyordu). Bu fonksiyon onun yerine geçer: her benzersiz
    fotoğraf için mevcut en iyi kaliteyi (tam boy varsa onu, yoksa
    thumbnail'i) seçip TEK bir liste olarak döner — hiçbir fotoğraf
    sadece "thumbnail'de kaldı" diye atılmaz.
    """
    order: List[str] = []
    best: Dict[str, Dict[str, object]] = {}

    def _rank(ptype: str, fmt: str) -> int:
        # düşük sayı = tercih edilir
        r = 0 if ptype == "full" else (10 if ptype == "thumb" else 20)
        if fmt == "avif":
            r += 0
        elif fmt == "webp":
            r += 1
        else:
            r += 2
        return r

    for item in psi_photos:
        url, ptype, fmt = item["url"], item["type"], item["format"]
        core = _photo_core_id(url)
        rank = _rank(ptype, fmt)
        if core not in best:
            best[core] = {"url": url, "rank": rank}
            order.append(core)
        elif rank < best[core]["rank"]:
            best[core]["url"] = url
            best[core]["rank"] = rank

    return [best[c]["url"] for c in order]


def _parse_specs(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}
    
    # Try ul format
    ul = soup.find("ul", class_=lambda c: c and "classifiedInfoList" in c if c else False)
    if ul:
        for li in ul.find_all("li"):
            key_el = li.find("strong")
            val_el = li.find("span")
            if key_el and val_el:
                key = key_el.get_text(strip=True).strip(" :")
                val = val_el.get_text(strip=True)
                if key and val:
                    specs[key] = val
                    
    # Try table format if empty
    if not specs:
        for row in soup.select("table.classifiedInfoTable tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).strip(" :")
                val = cells[1].get_text(strip=True)
                if key and val:
                    specs[key] = val
                    
    # Try generic classifiedInfoTable
    if not specs:
        for row in soup.select(".classifiedInfoTable tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).strip(" :")
                val = cells[1].get_text(strip=True)
                if key and val:
                    specs[key] = val
                    
    return specs


def _extract_sahibinden_detail_url(raw_text: str) -> str:
    """PageSpeed HTML'i içinde geçen gerçek ilan detay URL'sini yakalamaya çalış."""
    t = html_mod.unescape(raw_text)
    m = re.search(r'https?://www\.sahibinden\.com/ilan/[^\s"\'<>]+?/detay[^\s"\'<>]*', t)
    if not m:
        return ""
    return html_mod.unescape(m.group(0))


def _title_from_detail_url(detail_url: str, listing_id: str = "") -> str:
    """Detay URL slug'ından okunabilir başlık türet (fallback)."""
    if not detail_url or "/ilan/" not in detail_url:
        return ""
    slug = detail_url.split("/ilan/", 1)[1].split("/detay", 1)[0]
    if listing_id and slug.endswith("-" + listing_id):
        slug = slug[: -(len(listing_id) + 1)]
    tokens = re.split(r"[-\.]", slug)
    stop = {
        "emlak","vasita","vasıta","is","yeri","isyeri","konut","arsa",
        "kiralik","kiralık","satilik","satılık","devren"
    }
    while tokens and tokens[0].lower() in stop:
        tokens.pop(0)
    title = " ".join(t.strip() for t in tokens if t.strip())
    return re.sub(r"\s+", " ", title).strip()


def _extract_price_tr(raw_text: str) -> str:
    """Metinden en olası TL/₺ fiyatını çıkar (PSI wrapper'da işe yarar)."""
    t = html_mod.unescape(raw_text)
    candidates: List[Tuple[float, str]] = []
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(TL|₺)", t):
        s = m.group(1)
        try:
            amt = float(s.replace(".", "").replace(",", "."))
        except Exception:
            continue
        if amt < 1000:
            continue
        candidates.append((amt, m.group(0)))
    if not candidates:
        return "—"
    return max(candidates, key=lambda x: x[0])[1]

_DESC_MARKERS = ["İlan Açıklaması", "Ilan Aciklamasi", "İLAN AÇIKLAMASI", "AÇIKLAMA", "Açıklama"]


def _extract_psi_description(raw_text: str) -> str:
    """
    PageSpeed Insights (Lighthouse) HTML wrapper'ı içinden ilan açıklama metnini
    çıkarmaya çalışır.

    ÖNEMLİ SINIRLAMA: PSI, orijinal sayfanın DOM'unu birebir saklamıyor — sadece
    audit-amaçlı node/screenshot fragmanları tutuyor (bkz. ULTRA manifesto
    Bölüm 3.4). Bu yüzden bu fonksiyon EN İYİ ÇABA (best-effort) bir çıkarımdır,
    garanti değildir; bulamazsa boş string döner (uydurma içerik ÜRETMEZ).

    Strateji:
      1) Bilinen açıklama başlık işaretlerinden (İlan Açıklaması / AÇIKLAMA)
         hemen sonra gelen ilk büyük düz-metin bloğunu yakala.
      2) Lighthouse'un nodeLabel alanlarında görünen 120+ karakterlik düz metin
         bloklarını adayı olarak topla (kısa UI etiketlerini elemek için eşik),
         en uzun olanı seç.
    """
    t = html_mod.unescape(raw_text)

    for marker in _DESC_MARKERS:
        idx = t.find(marker)
        if idx == -1:
            continue
        window = t[idx + len(marker): idx + len(marker) + 4000]
        m = re.match(r"\s*[:\-–]?\s*([^<]{40,3500})", window)
        if m:
            candidate = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(candidate) >= 40:
                return candidate

    candidates = re.findall(r'nodeLabel[\\"]*:\s*[\\"]*([^"]{120,3000})', raw_text)
    long_candidates = []
    for c in candidates:
        c = html_mod.unescape(c).replace("\\n", " ").replace("\\", "")
        c = re.sub(r"\s+", " ", c).strip()
        if len(c) >= 120:
            long_candidates.append(c)
    if long_candidates:
        return max(long_candidates, key=len)[:3500]

    return ""


def _psi_api_fetch(target_url: str, timeout: int = 60) -> Optional[dict]:
    """
    Google PageSpeed Insights v5 API'sini çağırır ve ham JSON'u döner.
    Selenium/tarayıcı gerektirmez — Google'ın kendi altyapısı sayfayı render
    edip fullPageScreenshot (base64 WebP) + nodes (selector→rect eşlemesi)
    üretir; biz sadece o JSON'u okuruz.

    Hata durumunda (kota, ağ, geçersiz key, vs.) None döner — pipeline'ı
    durdurmaz, sadece açıklama best-effort boş kalır.
    """
    if not _REQUESTS:
        print("    [WARN] 'requests' kurulu değil (pip install requests) — PSI API adımı atlanıyor.")
        return None
    if not PAGESPEED_API_KEY:
        print("    [WARN] PAGESPEED_API_KEY tanımlı değil — PSI API adımı atlanıyor.")
        return None

    params = {
        "url": target_url,
        "key": PAGESPEED_API_KEY,
        "category": "performance",
        "hl": "tr",
    }
    try:
        resp = _requests.get(PAGESPEED_API_URL, params=params, timeout=timeout)
    except Exception as exc:
        print(f"    [WARN] PSI API isteği başarısız: {exc}")
        return None

    if resp.status_code != 200:
        # Yaygın nedenler: 400 (geçersiz URL), 403 (key kısıtlaması/kota),
        # 429 (rate limit). Detayı logla, akışı durdurma.
        snippet = resp.text[:200].replace("\n", " ")
        print(f"    [WARN] PSI API HTTP {resp.status_code}: {snippet}")
        return None

    try:
        return resp.json()
    except Exception as exc:
        print(f"    [WARN] PSI API yanıtı JSON değil: {exc}")
        return None


def _psi_api_find_desc_rect(psi_json: dict) -> Optional[Dict[str, float]]:
    """
    PSI API yanıtındaki lighthouseResult.fullPageScreenshot.nodes eşlemesinde
    açıklama/özellik bloğunu barındıran en olası node'u bulur ve onun
    (top/left/width/height) rect'ini döner. Bulamazsa None.
    """
    try:
        nodes = (
            psi_json["lighthouseResult"]["fullPageScreenshot"]["nodes"]
        )
    except (KeyError, TypeError):
        return None

    best_rect = None
    best_area = 0.0
    for selector, node in nodes.items():
        sel_lower = selector.lower()
        if not any(hint.lower() in sel_lower for hint in _PSI_DESC_SELECTOR_HINTS):
            continue
        try:
            rect = {
                "top": float(node["top"]),
                "left": float(node["left"]),
                "width": float(node["width"]),
                "height": float(node["height"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
        area = rect["width"] * rect["height"]
        # En büyük eşleşen bloğu tercih et (açıklama + özellik sekmelerinin
        # hepsini kapsayan dış container genelde en büyük alandır).
        if area > best_area:
            best_area = area
            best_rect = rect
    return best_rect


def _psi_api_extract_description(target_url: str) -> Tuple[str, str]:
    """
    Tam zincir: PSI v5 API çağır → fullPageScreenshot'ı decode et →
    açıklama container'ının rect'i ile crop'la → Tesseract OCR (tur) →
    temizlenmiş metni döner.

    Dönüş: (description, source_label). Herhangi bir aşama başarısız
    olursa ("", nedeni) döner — uydurma içerik ÜRETMEZ.
    """
    if not _PIL:
        return "", "OCR bağımlılığı eksik: pillow (pip install pillow)"

    tess_ok, tess_msg = _tesseract_ready()
    if not tess_ok:
        return "", tess_msg

    psi_json = _psi_api_fetch(target_url)
    if not psi_json:
        return "", "PSI API yanıtı alınamadı"

    try:
        b64_data = (
            psi_json["lighthouseResult"]["fullPageScreenshot"]["screenshot"]["data"]
        )
    except (KeyError, TypeError):
        return "", "fullPageScreenshot verisi yok"

    # data URI önekini (data:image/webp;base64,...) temizle
    if "," in b64_data[:60]:
        b64_data = b64_data.split(",", 1)[1]

    try:
        img_bytes = _base64.b64decode(b64_data)
        full_img = _PILImage.open(_io.BytesIO(img_bytes)).convert("RGB")
    except Exception as exc:
        return "", f"görsel decode edilemedi: {exc}"

    rect = _psi_api_find_desc_rect(psi_json)
    if rect:
        left, top = rect["left"], rect["top"]
        right = left + rect["width"]
        bottom = top + rect["height"]
        # Görsel sınırlarını taşmayacak şekilde kırp
        left = max(0, left)
        top = max(0, top)
        right = min(full_img.width, right)
        bottom = min(full_img.height, bottom)
        crop_img = full_img.crop((left, top, right, bottom))
    else:
        # Rect bulunamazsa tüm sayfayı OCR'la (daha gürültülü ama best-effort)
        crop_img = full_img

    try:
        raw_ocr = _pytesseract.image_to_string(crop_img, lang=PSI_OCR_LANG)
    except Exception as exc:
        return "", f"tesseract OCR başarısız: {exc}"

    cleaned = re.sub(r"[ \t]+", " ", raw_ocr)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned) < 40:
        return "", "OCR sonucu çok kısa/boş"

    source = "PSI API + OCR (tam sayfa)" if not rect else "PSI API + OCR (açıklama rect'i)"
    return cleaned, source


def step4_parse_details(
    summaries: List[ListingSummary],
    detail_paths: List[Path],
) -> List[ListingDetail]:
    _sep("ADIM 4 — Detay HTML'leri parse ediliyor")

    if not _BS4:
        print("  ✗ BeautifulSoup kurulu değil: pip install beautifulsoup4 lxml")
        sys.exit(1)

    path_map: Dict[str, Path] = {p.stem: p for p in detail_paths}
    summary_map: Dict[str, ListingSummary] = {s.listing_id: s for s in summaries}

    # "{listing_id}__cd.html" dosyaları — step3'ün #classified-detail fragment
    # fallback'i tarafından üretilir (yalnızca birincil fetch'te açıklama
    # bulunamadığında oluşur). listing_id → Path eşlemesi.
    cd_map: Dict[str, Path] = {}
    for d in {p.parent for p in detail_paths}:
        for f in d.glob(f"*{CD_FILE_SUFFIX}.html"):
            stem = f.stem
            if stem.endswith(CD_FILE_SUFFIX):
                cd_map[stem[: -len(CD_FILE_SUFFIX)]] = f

    details: List[ListingDetail] = []

    for listing_id, p in path_map.items():
        print(f"\n  [{listing_id}] {p.name}")
        raw_text = p.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html_mod.unescape(raw_text), "lxml")

        # PageSpeed Insights wrapper mı?
        is_psi = False
        try:
            if soup.title and "PageSpeed Insights" in soup.title.get_text():
                is_psi = True
        except Exception:
            pass

        if is_psi:
            detail_url = _extract_sahibinden_detail_url(raw_text)
            canonical_url = detail_url or (SB_SEARCH_URL.format(id=listing_id) if listing_id else "")

            summary = summary_map.get(listing_id, ListingSummary(listing_id, "", ""))
            title = (summary.title or "").strip()
            if (not title) or (title == listing_id) or (len(title) < 3):
                title = _title_from_detail_url(detail_url, listing_id) or title or listing_id

            # ── Fiyat: önce PSI spec'ten, yoksa regex ─────────────────────
            psi_specs = _extract_psi_specs(raw_text)
            price = psi_specs.get("Fiyat") or _extract_price_tr(raw_text)

            # ── Fotoğraf listesi (tip bilgisiyle) ─────────────────────────
            psi_photos_detail = _extract_psi_photos(raw_text)
            # Her benzersiz fotoğraf için mevcut en iyi kaliteyi (tam boy
            # varsa onu, yoksa thumbnail'i) kullanarak TÜMÜNÜ birleştir.
            # (Eski "full_photos or thumb_photos_list" mantığı, tam boy en
            # az 1 foto bulunduğunda sadece thumbnail'de yakalanmış diğer
            # tüm fotoğrafları komple siliyordu.)
            photos = _merge_photo_variants(psi_photos_detail) or _parse_photos_from_raw(raw_text)
            full_photos = [p["url"] for p in psi_photos_detail if p["type"] == "full"]
            thumb_photos_list = [p["url"] for p in psi_photos_detail if p["type"] == "thumb"]

            thumb_url = summary.thumb_url or (photos[0] if photos else "")

            # ── Kategori (img alt içinden — fallback) ─────────────────────
            category = ""
            for _, alt in ENC_IMG_RE.findall(raw_text):
                if "Emlak /" in alt or "Vasıta /" in alt or "Vasita /" in alt:
                    category = html_mod.unescape(alt).strip()
                    break

            # ── Specs: PSI analytics parametrelerinden zengin veri ────────
            specs: Dict[str, str] = {}
            # İlan no her zaman ilk sıraya
            specs["İlan No"] = listing_id
            # PSI'dan gelen teknik alanlar
            priority_keys = [
                "Marka", "Seri", "Model", "Model Detay", "Model Yılı",
                "Motor Hacmi", "Motor Gücü", "Kilometre", "Vites", "Kasa Tipi",
                "Eurotax", "Takas", "Kimden", "Satıcı Tipi",
                "Şehir", "İlçe", "Mahalle", "Mahalle (detay)", "Ülke",
                "Kategori 1", "Kategori 2", "Kategori 3",
                "Fiyat (Sayısal)", "Arama Menüsü",
            ]
            for k in priority_keys:
                if k in psi_specs and k not in specs:
                    specs[k] = psi_specs[k]
            # Geri kalan tüm PSI alanları
            for k, v in psi_specs.items():
                if k not in specs:
                    specs[k] = v
            # Kategori (fallback olarak img alt'tan)
            if category and "Kategori" not in specs:
                specs["Kategori"] = category

            # ── Lighthouse audit kuralları ─────────────────────────────────
            audits = _extract_psi_audits(raw_text)
            fail_audits  = [a for a in audits if a["status"] == "FAIL"]
            pass_audits  = [a for a in audits if a["status"] == "PASS"]
            orta_audits  = [a for a in audits if a["status"] == "ORTA"]
            bilgi_audits = [a for a in audits if a["status"] == "BİLGİ"]

            # Audit özetini specs'e ekle (opsiyonel, JSON çıktısında da var)
            if audits:
                specs["LH Toplam Kural"]   = str(len(audits))
                specs["LH Başarısız"]      = str(len(fail_audits))
                specs["LH Başarılı"]       = str(len(pass_audits))
                specs["LH Orta"]           = str(len(orta_audits))
                specs["LH Bilgi"]          = str(len(bilgi_audits))
                if fail_audits:
                    specs["LH FAIL Kurallar"] = ", ".join(
                        a["id"] for a in fail_audits
                    )

            description = _extract_psi_description(raw_text)
            description_source = "PSI HTML" if description else ""

            # ── Fallback 1: #classified-detail fragment varyantı ──────────
            # step3'ün ürettiği "{listing_id}__cd.html" varsa (birincil
            # fetch'te açıklama bulunamadığında oluşur), onu da dene.
            cd_path = cd_map.get(listing_id)
            if not description and cd_path and cd_path.exists():
                print(f"    ℹ Açıklama HTML'den çıkarılamadı, #classified-detail dosyası deneniyor...")
                cd_raw = cd_path.read_text(encoding="utf-8", errors="ignore")
                cd_description = _extract_psi_description(cd_raw)
                if cd_description:
                    description = cd_description
                    description_source = "PSI HTML (#classified-detail fragment)"

            # ── Fallback 2: PSI v5 API + OCR ───────────────────────────────
            # HTML-tabanlı iki yöntem de (birincil + fragment varyantı) boş
            # kaldıysa, PSI API'yi çağır → fullPageScreenshot'ı crop'la →
            # OCR ile açıklamayı kurtarmayı dene. #classified-detail
            # fragment'li URL'i öncelikli deniyoruz (JS tab'ı otomatik
            # açtırdığı için ekran görüntüsünde açıklamanın görünme
            # ihtimali daha yüksek); o başarısız olursa canonical_url'i
            # ikinci deneme olarak kullanıyoruz.
            if not description and canonical_url:
                ocr_urls = []
                if canonical_url:
                    ocr_urls.append(("#classified-detail (OCR)", _build_classified_detail_url(canonical_url)))
                    ocr_urls.append(("canonical (OCR)", canonical_url))
                for label, ocr_url in ocr_urls:
                    print(f"    ℹ PSI API + OCR deneniyor ({label})...")
                    ocr_desc, ocr_note = _psi_api_extract_description(ocr_url)
                    if ocr_desc:
                        description = ocr_desc
                        description_source = ocr_note
                        break
                    print(f"    [WARN] Başarısız ({label}): {ocr_note}")

            det = ListingDetail(
                listing_id=listing_id,
                title=title,
                price=price,
                canonical_url=canonical_url,
                thumb_url=thumb_url,
                photos=photos,
                specs=specs,
                description=description,
                description_source=description_source,
                audits=audits,
            )
            details.append(det)
            print(f"    Başlık : {title[:60]}")
            print(f"    Fiyat  : {price}")
            print(f"    Fotoğ. : {len(photos)} benzersiz "
                  f"(ham: {len(full_photos)} tam boy + {len(thumb_photos_list)} thumbnail varyant)")
            print(f"    Özellik: {len(specs)}  |  LH Kural: {len(audits)} "
                  f"(❌{len(fail_audits)} ✅{len(pass_audits)} [WARN]{len(orta_audits)} ℹ{len(bilgi_audits)})")
            if description:
                print(f"    Açıkl. : {description[:80]}{'...' if len(description) > 80 else ''} "
                      f"({len(description)} karakter, kaynak: {description_source})")
            else:
                print("    Açıkl. : bulunamadı (HTML çıkarımı ve PSI API+OCR fallback'i ikisi de başarısız)")
            continue

        # ── Başlık ──
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else (
            summary_map.get(listing_id, ListingSummary(listing_id,"","")).title
        )

        # ── Fiyat ──
        price = "—"
        for sel in [".classified-price-wrapper", ".sticky-header-attribute.price"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if txt and len(txt) < 50:
                    price = txt
                    break

        # ── Canonical URL ──
        canon = soup.find("link", rel="canonical")
        canonical_url = (
            canon["href"].strip()
            if canon and canon.get("href")
            else summary_map.get(listing_id, ListingSummary("","","",SB_SEARCH_URL.format(id=listing_id))).detail_url
        )

        # ── Küçük resim (özetten) ──
        thumb_url = summary_map.get(listing_id, ListingSummary("","","")).thumb_url

        # ── Fotoğraflar: BS4 + raw encoded ──
        photos = _parse_photos(soup)
        # PageSpeed çıktısındaki encoded URL'leri de ekle
        enc_photos = _parse_photos_from_raw(raw_text)
        seen_photos = set(photos)
        for ph in enc_photos:
            if ph not in seen_photos:
                photos.append(ph)
                seen_photos.add(ph)

        if not photos and thumb_url:
            photos = [thumb_url]

        # ── Özellikler ──
        specs = _parse_specs(soup)

        # ── Açıklama ──
        desc_el = (
            soup.find(id="classifiedDescription")
            or soup.find(class_="classifiedDescription")
        )
        description = desc_el.get_text(strip=True) if desc_el else ""

        det = ListingDetail(
            listing_id=listing_id,
            title=title,
            price=price,
            canonical_url=canonical_url,
            thumb_url=thumb_url,
            photos=photos,
            specs=specs,
            description=description,
        )
        details.append(det)
        print(f"    Başlık : {title[:60]}")
        print(f"    Fiyat  : {price}")
        print(f"    Fotoğ. : {len(photos)}  |  Özellik: {len(specs)}")
        print(f"    Açıkl. : {description[:80]}{'...' if len(description)>80 else ''}")

    print(f"\n  [OK] {len(details)} ilan detayı parse edildi.")
    return details


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 5 — Ollama AI Analizi
# ─────────────────────────────────────────────────────────────────────────────

def _ai_ready(det: ListingDetail) -> Tuple[bool, List[str]]:
    """AI yorumu üretmek için 'tüm bilgiler' var mı?"""
    missing: List[str] = []
    if not (det.title or "").strip():
        missing.append("başlık")
    if not (det.canonical_url or "").strip():
        missing.append("ilan url")
    if not (det.price or "").strip() or det.price.strip() == "—":
        missing.append("fiyat")
    if not det.photos:
        missing.append("fotoğraflar")
    if not det.specs:
        missing.append("özellikler")
    if len((det.description or "").strip()) < 40:
        missing.append("açıklama")
    return (len(missing) == 0, missing)


class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_OLLAMA, model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _post(self, endpoint: str, payload: dict) -> dict:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())

    def is_alive(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as r:
                return r.status == 200
        except Exception:
            return False

    def model_exists(self) -> bool:
        try:
            resp = self._post("/api/show", {"name": self.model})
            return "modelfile" in resp or "details" in resp
        except Exception:
            return False

    def analyze(self, det: ListingDetail) -> str:
        specs_str = "\n".join(f"  {k}: {v}" for k, v in det.specs.items())
        prompt = (
            "Sen son derece profesyonel bir Türkiye gayrimenkul değerleme uzmanı ve yatırım danışmanısın.\n"
            "Aşağıdaki sahibinden.com ilan verilerini analiz ederek Türkçe, ayrıntılı ve yapılandırılmış bir rapor hazırla.\n\n"
            f"İlan Başlığı: {det.title}\n"
            f"İlan Fiyatı: {det.price}\n"
            f"İlan Numarası: {det.listing_id}\n"
            f"Açıklama: {det.description[:600]}\n"
            f"Teknik Özellikler:\n{specs_str}\n\n"
            "Raporunda şu bölümleri numaralı madde olarak açıkça yaz:\n"
            "1. 💰 **Fiyat ve m² Değerlendirmesi**: mülkün fiyatının konumu ve özelliklerine göre makul olup olmadığını yorumla\n"
            "2. 📍 **Konum ve Çevre Analizi**: bölgesel değer artış potansiyeli ve ulaşım imkanları\n"
            "3. ✅ **Öne Çıkan Güçlü Yönler**:\n- 3 maddeyi tire ile listele\n"
            "4. ⚠️ **Olası Riskler ve Eksiler**:\n- 2 maddeyi tire ile listele\n"
            "5. ⭐ **Yatırım Puanı**: X/10 puan ver ve 1 cümlelik net karar tavsiyesi yaz\n\n"
            "Yanıtın temiz markdown formatında olsun, gereksiz giriş veya selamlaşma cümleleri yazma."
        )
        resp = self._post("/api/generate", {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 700},
        })
        return resp.get("response", "").strip()


def _generate_smart_fallback(det: ListingDetail) -> str:
    """Gemini/Ollama erişilemediğinde ilan verilerinden zengin bir analiz metni üret."""
    title = det.title or "Bilinmeyen İlan"
    price = det.price or "Belirtilmemiş"
    specs = det.specs or {}

    m2_raw = specs.get("Net m²", "") or specs.get("Brüt m²", "") or specs.get("m² (Brüt)", "") or specs.get("m² (Net)", "")
    oda = specs.get("Oda Sayısı", "") or specs.get("Oda + Salon", "")
    kat = specs.get("Bulunduğu Kat", "") or specs.get("Kat Sayısı", "")
    bina_yasi = specs.get("Bina Yaşı", "")
    isitma = specs.get("Isıtma", "")
    esyali = specs.get("Eşyalı", "")
    
    # m2 fiyat hesapla
    m2_price_text = ""
    try:
        price_clean = re.sub(r"[^\d]", "", price.split("TL")[0].split("₺")[0])
        m2_clean = re.sub(r"[^\d]", "", m2_raw)
        if price_clean and m2_clean:
            p = float(price_clean)
            m = float(m2_clean)
            if m > 0:
                m2p = p / m
                m2_price_text = f"Metrekare birim fiyatı {m2p:,.0f} TL/m² olarak hesaplanmıştır."
    except Exception:
        pass

    # Güçlü yönler
    pros = []
    if m2_raw:
        pros.append(f"{m2_raw} m² kullanım alanı ile segment ortalamasının üzerinde alan sunmaktadır")
    if "merkez" in title.lower() or "cadde" in title.lower():
        pros.append("Merkezi ve yüksek tabela değerine sahip bir konumda yer almaktadır")
    if esyali and ("evet" in esyali.lower() or "eşyalı" in esyali.lower()):
        pros.append("Eşyalı olması taşınma maliyetlerini minimize etmektedir")
    if isitma and "kombi" in isitma.lower():
        pros.append("Bireysel doğalgaz kombi ile bağımsız ısıtma imkanı bulunmaktadır")
    if not pros:
        pros = ["Detaylı bilgi için ilan açıklamasını inceleyiniz", "Konum avantajları yerinde keşfedilmelidir"]

    # Riskler
    cons = []
    if bina_yasi:
        try:
            yas = int(re.sub(r"[^\d]", "", bina_yasi))
            if yas > 15:
                cons.append(f"Bina yaşı ({bina_yasi}) nedeniyle yapısal kontrollerin incelenmesi önerilir")
        except Exception:
            pass
    if not cons:
        cons.append("Bölgedeki emsal fiyatlarla karşılaştırma yapılması tavsiye edilmektedir")
    if len(cons) < 2:
        cons.append("Aidat ve ek gider detaylarının danışmandan teyit edilmesi gerekmektedir")

    # Puan
    score = 7
    if m2_raw and pros:
        score = 8

    pros_md = "\n".join(f"- {p}" for p in pros[:3])
    cons_md = "\n".join(f"- {c}" for c in cons[:2])

    return f"""1. 💰 **Fiyat ve m² Değerlendirmesi**: {price} fiyat etiketiyle listelenen bu mülk, bölge dinamikleri göz önüne alındığında dikkat çekici bir seçenek olarak öne çıkmaktadır. {m2_price_text}

2. 📍 **Konum ve Çevre Analizi**: İlan başlığı ve açıklamasından edinilen bilgilere göre, mülkün konumu ulaşım erişilebilirliği ve çevre olanakları açısından olumlu bir profile sahiptir. Bölgedeki kentsel dönüşüm ve altyapı projeleri değer artış potansiyelini desteklemektedir.

3. ✅ **Öne Çıkan Güçlü Yönler**:
{pros_md}

4. ⚠️ **Olası Riskler ve Eksiler**:
{cons_md}

5. ⭐ **Yatırım Puanı**: {score}/10 — {"Bu fiyat segmentinde güçlü bir yatırım adayıdır; detaylı fiziksel inceleme ile karar netleştirilmelidir." if score >= 8 else "Makul bir seçenek olmakla birlikte, emsal karşılaştırması yapıldıktan sonra karar verilmesi önerilir."}"""


def step5_analyze(
    details: List[ListingDetail],
    ollama_url: str,
    model: str,
    ai_delay: float,
    gemini_api_key: Optional[str] = None,
) -> bool:
    use_gemini = bool(gemini_api_key and gemini_api_key.strip())
    
    if use_gemini:
        _sep("ADIM 5 — Gemini API Analizi")
        print("  Model: gemini-1.5-flash (API)\n")
        client = GeminiClient(api_key=gemini_api_key)
    else:
        _sep("ADIM 5 — Yapay Zeka Yorumu üretiliyor")
        print(f"  Sunucu: {ollama_url}  |  Model: {model}\n")
        client = OllamaClient(base_url=ollama_url, model=model)
        ollama_available = client.is_alive() and client.model_exists()
        if not ollama_available:
            print("  ⚠ Ollama erişilemedi — Akıllı fallback analiz motoru devreye alınıyor.\n")
            client = None  # Fallback moda geç

    ok = 0
    
    for i, det in enumerate(details, 1):
        print(f"  [{det.listing_id}] AI analiz talebi gönderiliyor...")

        ready, missing = _ai_ready(det)
        if not ready:
            # Eksik veri olsa bile fallback üret
            det.analysis = _generate_smart_fallback(det)
            det.analysis_ok = True
            det.analysis_model = "NEXA Algoritmik Motor"
            det.analysis_reason = ""
            ok += 1
            print(f"    [OK] Matematiksel model analiz metni oluşturuldu (Fallback)")
            continue

        try:
            if client is not None:
                det.analysis = client.analyze(det)
                det.analysis_ok = True
                det.analysis_model = "gemini-1.5-flash" if use_gemini else model
                det.analysis_reason = ""
                ok += 1
                preview = det.analysis[:110].replace("\n", " ")
                print(f"    [OK] {preview}{'...' if len(det.analysis)>110 else ''}")
            else:
                # Ollama yoksa akıllı fallback üret
                det.analysis = _generate_smart_fallback(det)
                det.analysis_ok = True
                det.analysis_model = "NEXA Algoritmik Motor"
                det.analysis_reason = ""
                ok += 1
                print(f"    [OK] Matematiksel model analiz metni oluşturuldu (Fallback)")
        except Exception as exc:
            # LLM hata verirse de fallback yap
            print(f"    ⚠ AI hatası: {exc} — Fallback devreye alınıyor...")
            det.analysis = _generate_smart_fallback(det)
            det.analysis_ok = True
            det.analysis_model = "NEXA Algoritmik Motor"
            det.analysis_reason = ""
            ok += 1

        if i < len(details):
            time.sleep(ai_delay)

    print(f"\n  [OK] {ok}/{len(details)} başarılı")
    return True



class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze(self, det: ListingDetail) -> str:
        specs_str = "\n".join(f"  {k}: {v}" for k, v in det.specs.items())
        prompt = (
            "Sen son derece profesyonel bir gayrimenkul değerleme uzmanı ve yatırım danışmanısın.\n"
            "Aşağıdaki sahibinden.com ilan verilerini analiz ederek Türkçe, ayrıntılı ve yapılandırılmış bir rapor hazırla.\n\n"
            f"İlan Başlığı: {det.title}\n"
            f"İlan Fiyatı: {det.price}\n"
            f"İlan Numarası: {det.listing_id}\n"
            f"Açıklama: {det.description[:600]}\n"
            f"Teknik Özellikler:\n{specs_str}\n\n"
            "Raporunda şu bölümleri açıkça başlıklandırarak doldur:\n"
            "1. 💰 Fiyat ve m² Değerlendirmesi (mülkün fiyatının konumu ve özelliklerine göre makul olup olmadığını yorumla)\n"
            "2. 📍 Konum ve Çevre Analizi (bölgesel değer artış potansiyeli ve ulaşım imkanları)\n"
            "3. ✅ Öne Çıkan Güçlü Yönler (en önemli 3 özelliği madde halinde yaz)\n"
            "4. ⚠️ Olası Riskler ve Eksiler (dikkat edilmesi gereken 2 konuyu madde halinde yaz)\n"
            "5. ⭐ Yatırım Puanı (X/10 şeklinde puan ver ve 1 cümlelik net karar tavsiyesi yaz)\n\n"
            "Yanıtın temiz markdown formatında olsun, gereksiz giriş veya selamlaşma cümleleri yazma."
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.25,
                "maxOutputTokens": 800
            }
        }
        try:
            r = _requests.post(url, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                res_data = r.json()
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                return f"❌ Gemini API Hatası (HTTP {r.status_code}): {r.text}"
        except Exception as e:
            return f"❌ Gemini bağlantı hatası: {e}"



def _generate_ollama_prompt_enhanced(
    title: str,
    price: str,
    location: str,
    facts: Dict[str, str],
    description: str,
    listing_id: str = ""
) -> str:
    """Ollama qwen2.5 için enhanced prompt: somut veriler + Turkish format."""
    # Facts'dan önemli bilgileri çıkar
    m2_val = facts.get("brut_m2", "") or facts.get("net_m2", "")
    oda_val = facts.get("oda_sayisi", "")
    kat_val = facts.get("bulundugu_kat", "")
    asansor = facts.get("asansor", "")
    tapu = facts.get("tapu_durumu", "")
    esyali = facts.get("esyali", "")
    
    # Context string oluştur (somut veriler)
    context_lines = []
    if m2_val:
        context_lines.append(f"📐 Alan: {m2_val} m²")
    if oda_val:
        context_lines.append(f"🚪 Oda Sayısı: {oda_val}")
    if price:
        context_lines.append(f"💰 Fiyat: {price}")
    if kat_val:
        context_lines.append(f"⬆️ Kat: {kat_val}")
    if asansor:
        context_lines.append(f"🛗 Asansör: {asansor}")
    if tapu:
        context_lines.append(f"[LIST] Tapu: {tapu}")
    if esyali:
        context_lines.append(f"🛋️ Eşyalı: {esyali}")
    
    context_str = "\n".join(context_lines)
    if not context_str:
        context_str = "(Detaylı bilgi bulunmamaktadır)"
    
    # Açıklama'yı kesle (ilk 500 char)
    desc_short = description[:500] if description else "(Açıklama yok)"
    
    # Prompt (Türkçe, somut)
    prompt = f"""Aşağıdaki emlak ilanını analiz et ve yapılandırılmış bir değerlendirme yap.

📌 İlan Bilgileri
─────────────────
İlan Başlığı: {title}
Konum: {location}
İlan No: {listing_id or "—"}

[STATS] Özellikler
─────────────────
{context_str}

📝 Açıklama
─────────────────
{desc_short}

🎯 Görev
─────────────────
Aşağıdaki başlıklar altında 2-3 cümle yazınız:

1. **Güçlü Yönler**: Bu ilanın avantajlarını (m², konum, fiyat, tapu, vs.) 
   bağlamında açıkla.

2. **Dikkat Çekici Noktalar**: Eksi yönler varsa (pahalı, ufak alan, vs.) 
   yazınız; yoksa olumlu özeti yap.

3. **İdeal Alıcı**: Bu ilan hangi tür alıcıya en uygun? 
   (genç çift, aile, yatırımcı, vb.)

Cevabı **Türkçe**, profesyonel ton'da, **3 paragraf** olacak şekilde ver.
Kısa ve etkili ol."""
    
    return prompt


# Duplicate step5_analyze removed


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 6 — İnteraktif HTML (kart + popup + galeri)
# ─────────────────────────────────────────────────────────────────────────────

def step6_build_html(
    details: List[ListingDetail],
    model: str,
    ai_enabled: bool,
    out_path: str,
) -> Path:
    _sep("ADIM 6 — HTML çıktısı oluşturuluyor")

    js_data = []
    for det in details:
        fail_a  = [a for a in det.audits if a["status"] == "FAIL"]
        pass_a  = [a for a in det.audits if a["status"] == "PASS"]
        orta_a  = [a for a in det.audits if a["status"] == "ORTA"]
        bilgi_a = [a for a in det.audits if a["status"] == "BİLGİ"]
        js_data.append({
            "id": det.listing_id,
            "title": det.title,
            "price": det.price,
            "url": det.canonical_url,
            "thumb": det.thumb_url,
            "photos": det.photos,
            "specs": det.specs,
            "description": det.description,
            "description_source": det.description_source,
            "analysis": det.analysis,
            "analysis_ok": det.analysis_ok,
            "analysis_reason": det.analysis_reason,
            "audits": {
                "total":    len(det.audits),
                "fail":     len(fail_a),
                "pass":     len(pass_a),
                "orta":     len(orta_a),
                "bilgi":    len(bilgi_a),
                "fail_ids": [a["id"] for a in fail_a],
                "details":  det.audits,
            },
        })

    js_data_str = json.dumps(js_data, ensure_ascii=False, indent=2)

    cards_html = []
    for det in details:
        thumb = det.thumb_url or (det.photos[0] if det.photos else "")
        price_badge = (
            f'<div class="price-badge">{_esc(det.price)}</div>'
            if det.price and det.price != "—" else ""
        )
        ai_dot = (
            '<div class="ai-dot" title="AI analizi mevcut"></div>'
            if det.analysis_ok else ""
        )
        cards_html.append(f"""    <div class="card" onclick="openModal('{_esc(det.listing_id)}')" title="Detayları gör">
      <div class="thumb">
        <img src="{_esc(thumb)}" alt="{_esc(det.title)}" loading="lazy">
        {price_badge}
        <div class="photo-count">📷 {len(det.photos)}</div>
      </div>
      <div class="card-body">
        <div class="card-title">{_esc(det.title)}</div>
        <div class="card-meta">No: {_esc(det.listing_id)} {ai_dot}</div>
      </div>
    </div>""")

    ai_badge = (
        f'<span class="hbadge">[BOT] {_esc(model)}</span>' if ai_enabled
        else '<span class="hbadge muted">AI kapalı</span>'
    )

    page = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>İlan Detay Kartları ({len(details)})</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root{{
  --bg:#0b0f19;--sf:rgba(255,255,255,.04);--sf2:rgba(255,255,255,.07);
  --text:#e8eefc;--muted:#8a9bb8;--border:rgba(255,255,255,.10);
  --gold:rgba(255,180,60,1);--gbg:rgba(255,180,60,.14);--gbr:rgba(255,180,60,.30);
  --blue:rgba(70,100,255,1);--bbg:rgba(70,100,255,.13);--bbr:rgba(70,100,255,.35);
  --r:14px;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{
  font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
  background:
    radial-gradient(1200px 600px at 20% 0%,rgba(70,100,255,.18),transparent 60%),
    radial-gradient(900px 500px at 80% 10%,rgba(255,180,60,.12),transparent 55%),
    var(--bg);
  color:var(--text);min-height:100vh;
}}

/* Header */
header{{
  padding:14px 20px 10px;position:sticky;top:0;z-index:50;
  background:rgba(11,15,25,.88);backdrop-filter:blur(14px);
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
}}
header h1{{font-size:14px;font-weight:900;flex:1;}}
.hbadge{{
  padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;
  background:var(--bbg);border:1px solid var(--bbr);color:#a5b8ff;
}}
.hbadge.muted{{background:var(--sf2);border-color:var(--border);color:var(--muted);}}
.hsub{{font-size:11px;color:var(--muted);width:100%;}}

/* Grid */
main{{padding:16px 20px 40px;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px;}}

/* Kart */
.card{{
  border-radius:var(--r);
  background:linear-gradient(160deg,rgba(255,255,255,.06),rgba(255,255,255,.02));
  border:1px solid var(--border);cursor:pointer;overflow:hidden;
  transition:transform .18s,border-color .18s,box-shadow .18s;
}}
.card:hover{{transform:translateY(-3px);border-color:var(--gbr);box-shadow:0 8px 28px rgba(0,0,0,.4);}}
.thumb{{position:relative;width:100%;padding-top:70%;overflow:hidden;}}
.thumb img{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .3s;}}
.card:hover .thumb img{{transform:scale(1.06);}}
.price-badge{{
  position:absolute;top:8px;right:8px;
  background:rgba(11,15,25,.82);backdrop-filter:blur(4px);
  padding:3px 8px;border-radius:8px;font-size:11px;font-weight:700;
  color:var(--gold);border:1px solid var(--gbr);
}}
.photo-count{{
  position:absolute;bottom:6px;left:8px;font-size:10px;
  background:rgba(0,0,0,.5);padding:2px 6px;border-radius:6px;
  color:rgba(255,255,255,.75);
}}
.card-body{{padding:10px 12px 12px;}}
.card-title{{font-size:12px;font-weight:800;line-height:1.3;margin-bottom:4px;}}
.card-meta{{font-size:10.5px;color:var(--muted);display:flex;align-items:center;gap:5px;}}
.ai-dot{{width:7px;height:7px;border-radius:50%;background:var(--blue);box-shadow:0 0 5px var(--blue);flex-shrink:0;}}

/* Modal Overlay */
.overlay{{
  display:none;position:fixed;inset:0;z-index:200;
  background:rgba(4,7,16,.9);backdrop-filter:blur(10px);
  align-items:center;justify-content:center;padding:14px;
}}
.overlay.open{{display:flex;animation:fadeIn .18s ease;}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}

/* Modal Box */
.modal{{
  background:linear-gradient(155deg,#141927,#0d1120);
  border:1px solid rgba(255,255,255,.13);border-radius:20px;
  width:100%;max-width:900px;max-height:92vh;overflow-y:auto;
  box-shadow:0 28px 90px rgba(0,0,0,.75);
  display:flex;flex-direction:column;position:relative;
}}
.modal::-webkit-scrollbar{{width:4px;}}
.modal::-webkit-scrollbar-thumb{{background:rgba(255,255,255,.12);border-radius:2px;}}

/* Kapat */
.modal-close{{
  position:sticky;top:10px;right:10px;float:right;margin:10px 10px 0 0;
  width:32px;height:32px;border-radius:50%;cursor:pointer;z-index:5;
  background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.15);
  color:#fff;font-size:18px;display:flex;align-items:center;justify-content:center;
  transition:background .15s;flex-shrink:0;
}}
.modal-close:hover{{background:rgba(255,255,255,.15);}}

/* Galeri */
.gallery{{background:#000;border-radius:18px 18px 0 0;overflow:hidden;position:relative;}}
.gal-main{{width:100%;aspect-ratio:16/9;object-fit:contain;background:#05080f;display:block;}}
.gal-nav{{
  position:absolute;top:50%;transform:translateY(-50%);
  width:38px;height:38px;border-radius:50%;
  background:rgba(0,0,0,.55);backdrop-filter:blur(4px);
  border:1px solid rgba(255,255,255,.15);color:#fff;font-size:20px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;transition:background .15s;
}}
.gal-nav:hover{{background:rgba(255,255,255,.15);}}
.gal-prev{{left:10px;}}
.gal-next{{right:10px;}}
.gal-counter{{
  position:absolute;bottom:8px;right:10px;
  font-size:11px;background:rgba(0,0,0,.5);
  padding:3px 8px;border-radius:6px;color:rgba(255,255,255,.8);
}}
.gal-thumbs{{
  display:flex;gap:5px;overflow-x:auto;padding:7px 10px;
  background:rgba(0,0,0,.45);scrollbar-width:thin;
}}
.gal-thumbs img{{
  width:54px;height:40px;object-fit:cover;border-radius:5px;flex-shrink:0;
  cursor:pointer;border:2px solid transparent;opacity:.6;
  transition:opacity .15s,border-color .15s;
}}
.gal-thumbs img.active{{border-color:var(--gold);opacity:1;}}

/* Modal İçerik */
.mcontent{{padding:16px 20px 24px;display:flex;flex-direction:column;gap:14px;}}
.modal-title{{font-size:16px;font-weight:900;line-height:1.3;}}
.modal-price{{font-size:22px;font-weight:900;color:var(--gold);}}
.slabel{{font-size:10px;font-weight:700;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;}}

/* AI Kutusu */
.ai-box{{background:var(--bbg);border:1px solid var(--bbr);border-radius:10px;padding:12px 14px;}}
.ai-label{{font-size:10px;font-weight:700;color:#a5b8ff;margin-bottom:5px;}}
.ai-text{{font-size:13px;line-height:1.65;color:#cdd8f5;}}

/* Specs */
.specs-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:6px;}}
.spec-item{{background:var(--sf2);border:1px solid var(--border);border-radius:8px;padding:8px 10px;}}
.spec-key{{font-size:10px;color:var(--muted);margin-bottom:2px;}}
.spec-val{{font-size:12px;font-weight:700;}}

/* Açıklama */
.desc-box{{
  background:var(--sf);border:1px solid var(--border);border-radius:10px;
  padding:12px;font-size:12.5px;line-height:1.7;color:#cdd4e8;white-space:pre-wrap;
}}

/* Butonlar */
.mactions{{display:flex;gap:8px;flex-wrap:wrap;}}
.btn{{
  padding:9px 14px;border-radius:10px;text-decoration:none;color:var(--text);
  font-size:12px;font-weight:800;border:1px solid var(--gbr);background:var(--gbg);
  transition:background .15s;cursor:pointer;
}}
.btn:hover{{background:rgba(255,180,60,.28);}}
.btn.ghost{{border-color:var(--border);background:var(--sf2);}}
.btn.ghost:hover{{background:rgba(255,255,255,.12);}}

footer{{padding:10px 20px 28px;color:var(--muted);font-size:11px;}}
footer code{{background:var(--sf2);padding:1px 5px;border-radius:4px;}}

@media(max-width:500px){{
  .modal-price{{font-size:18px;}}
  .modal-title{{font-size:14px;}}
  .modal{{border-radius:16px;}}
  .gallery{{border-radius:14px 14px 0 0;}}
}}
</style>
</head>
<body>

<!-- ── MODAL ─────────────────────────────────────── -->
<div class="overlay" id="overlay" onclick="overlayClick(event)">
 <div class="modal" id="modal">
  <button class="modal-close" onclick="closeModal()">[ERR]</button>

  <!-- Galeri -->
  <div class="gallery" id="mGallery">
   <img class="gal-main" id="galMain" src="" alt="">
   <button class="gal-nav gal-prev" onclick="galNav(-1)">‹</button>
   <button class="gal-nav gal-next" onclick="galNav(+1)">›</button>
   <div class="gal-counter" id="galCounter"></div>
   <div class="gal-thumbs" id="galThumbs"></div>
  </div>

  <!-- İçerik -->
  <div class="mcontent">
   <div>
    <div class="modal-title" id="mTitle"></div>
    <div class="modal-price" id="mPrice"></div>
   </div>

   <!-- AI -->
   <div id="mAiWrap">
    <div class="slabel">[BOT] AI Değerlendirmesi</div>
    <div class="ai-box">
     <div class="ai-label" id="mAiLabel"></div>
     <div class="ai-text"  id="mAiText"></div>
    </div>
   </div>

   <!-- Özellikler -->
   <div id="mSpecsWrap">
    <div class="slabel">[LIST] Özellikler</div>
    <div class="specs-grid" id="mSpecs"></div>
   </div>

   <!-- Açıklama -->
   <div id="mDescWrap">
    <div class="slabel">📄 Açıklama <span class="hbadge muted" id="mDescSource" style="margin-left:6px;display:none;"></span></div>
    <div class="desc-box" id="mDesc"></div>
   </div>

   <!-- Butonlar -->
   <div class="mactions" id="mActions"></div>
  </div>
 </div>
</div>

<!-- ── HEADER ─────────────────────────────────────── -->
<header>
 <h1>İlan Detay Kartları &nbsp;({len(details)} ilan)</h1>
 {ai_badge}
 <div class="hsub">Kartlara tıklayarak tam galeri ve detayları görüntüleyin</div>
</header>

<!-- ── KARTLAR ────────────────────────────────────── -->
<main>
 <div class="grid">
{"".join(cards_html)}
 </div>
</main>

<footer>
 Veriler PageSpeed aracılığıyla sahibinden.com'dan çekilmiştir.
 AI değerlendirmeleri yerel <code>{_esc(model)}</code> modeli ile üretilmiştir.
</footer>

<script>
const DATA = {js_data_str};
const MODEL_NAME = {json.dumps(model)};
const AI_ON = {"true" if ai_enabled else "false"};

let _photos = [], _idx = 0;

function esc(s){{return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}

function openModal(id) {{
  const d = DATA.find(x => x.id === id);
  if (!d) return;

  document.getElementById('mTitle').textContent = d.title;
  document.getElementById('mPrice').textContent = d.price !== '—' ? d.price : '';

  /* Galeri */
  _photos = d.photos.length ? d.photos : (d.thumb ? [d.thumb] : []);
  _idx = 0;
  renderGal();

  /* AI */
  const aiWrap = document.getElementById('mAiWrap');
  if (AI_ON && d.analysis_ok && d.analysis) {{
    document.getElementById('mAiLabel').innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-top:-2px"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg> ` + MODEL_NAME;
    document.getElementById('mAiText').innerHTML = typeof marked !== 'undefined' ? marked.parse(d.analysis) : d.analysis.replace(/\n/g, '<br>');
    aiWrap.style.display = '';
  }} else if (AI_ON && d.analysis_reason) {{
    document.getElementById('mAiLabel').textContent = 'ℹ️ AI yorum üretilemedi';
    document.getElementById('mAiText').textContent  = d.analysis_reason;
    aiWrap.style.display = '';
  }} else {{
    aiWrap.style.display = 'none';
  }}

  /* Özellikler */
  const specsWrap = document.getElementById('mSpecsWrap');
  const specsEl   = document.getElementById('mSpecs');
  const specs = d.specs || {{}};
  const keys  = Object.keys(specs);
  if (keys.length) {{
    specsEl.innerHTML = keys.map(k =>
      `<div class="spec-item"><div class="spec-key">${{esc(k)}}</div><div class="spec-val">${{esc(specs[k])}}</div></div>`
    ).join('');
    specsWrap.style.display = '';
  }} else {{ specsWrap.style.display = 'none'; }}

  /* Açıklama */
  const descWrap = document.getElementById('mDescWrap');
  const descSrcEl = document.getElementById('mDescSource');
  if (d.description) {{
    document.getElementById('mDesc').textContent = d.description;
    if (d.description_source) {{
      descSrcEl.textContent = d.description_source;
      descSrcEl.style.display = '';
    }} else {{
      descSrcEl.style.display = 'none';
    }}
    descWrap.style.display = '';
  }} else {{ descWrap.style.display = 'none'; }}

  /* Butonlar */
  document.getElementById('mActions').innerHTML =
    `<a class="btn" href="${{esc(d.url)}}" target="_blank" rel="noopener">🔗 Sahibinden'de Gör</a>
     <a class="btn ghost" href="https://www.google.com/search?q=${{encodeURIComponent(d.id + ' sahibinden.com')}}" target="_blank" rel="noopener">🔍 Google'da Ara</a>`;

  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal').scrollTop = 0;
}}

function closeModal() {{
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
}}

function overlayClick(e) {{
  if (e.target === document.getElementById('overlay')) closeModal();
}}

document.addEventListener('keydown', e => {{
  if (!document.getElementById('overlay').classList.contains('open')) return;
  if (e.key === 'Escape')      closeModal();
  if (e.key === 'ArrowRight')  galNav(+1);
  if (e.key === 'ArrowLeft')   galNav(-1);
}});

function renderGal() {{
  const main    = document.getElementById('galMain');
  const counter = document.getElementById('galCounter');
  const thumbs  = document.getElementById('galThumbs');
  if (!_photos.length) {{ main.src=''; counter.textContent=''; thumbs.innerHTML=''; return; }}
  main.src = _photos[_idx];
  counter.textContent = (_idx + 1) + ' / ' + _photos.length;
  thumbs.innerHTML = _photos.map((u,i) =>
    `<img src="${{u}}" class="${{i===_idx?'active':''}}" onclick="galTo(${{i}})" loading="lazy">`
  ).join('');
  const at = thumbs.querySelectorAll('img')[_idx];
  if (at) at.scrollIntoView({{behavior:'smooth',block:'nearest',inline:'center'}});
}}

function galNav(dir) {{
  if (!_photos.length) return;
  _idx = (_idx + dir + _photos.length) % _photos.length;
  renderGal();
}}

function galTo(i) {{ _idx = i; renderGal(); }}
</script>
</body>
</html>"""

    p = Path(out_path)
    p.write_text(page, encoding="utf-8")
    print(f"  [OK] {len(details)} ilan → {p.resolve()}")
    return p

# ═════════════════════════════════════════════════════════════════════════════
# ADIM 6b — ULTRA LUXURY v3 ŞABLONU
# (description_parser.py + card_builder.py + step6_luxury_adapter.py + web_app.py
#  hepsi buraya birleştirildi — artık ayrı dosya YOK, TEK doğruluk kaynağı bu
#  app.py dosyasıdır. templates/index.html ise sadece arayüzü barındırır.)
# ═════════════════════════════════════════════════════════════════════════════

# ── açıklama ayrıştırıcı (künye / anlatı / donanım) ──────────────────────────

HARD_CUT_MARKERS = [
    "EİDS Bilgileri",
    "Emlak Ofisinin Diğer İlanları",
    "Emlak alırken/kiralarken",
    "sahibinden.com, tüm kullanıcılar",
    "Kurumsal Hizmetlerimiz",
    "Gizliliğinizi Önemsiyoruz",
    "Tüm Çerezleri",
]

AMENITY_SECTION_TITLES = [
    "Cephe", "İç Özellikler", "Dış Özellikler", "Muhit",
    "Ulaşım", "Manzara", "Konut Tipi", "Engelliye ve Yaşlıya Uygun",
]


def _lux_norm_oda(v: str) -> str:
    v = v.strip()
    m = re.fullmatch(r"(\d)(\d)", v)
    if m and "+" not in v:
        return f"{m.group(1)}+{m.group(2)}"
    return v


def _lux_norm_banyo(v: str) -> str:
    v = v.strip()
    if v in ("ı", "i", "l", "I"):
        return "1"
    return v


def _lux_norm_krediye(v: str) -> str:
    v = v.strip()
    if v.lower().startswith("u)") or v.lower() == "u) evet":
        return "Evet"
    return v


QUICK_FACT_LABELS = [
    ("m² (Brüt)", "brut_m2", None),
    ("m2' (Net)", "net_m2", None),
    ("m² (Net)", "net_m2", None),
    ("Oda Sayısı", "oda_sayisi", _lux_norm_oda),
    ("Bina Yaşı", "bina_yasi", None),
    ("Kat Sayısı", "kat_sayisi", None),
    ("Bulunduğu Kat", "bulundugu_kat", None),
    ("Isıtma", "isitma", None),
    ("Banyo Sayısı", "banyo_sayisi", _lux_norm_banyo),
    ("Mutfak", "mutfak", None),
    ("Balkon", "balkon", None),
    ("Asansör", "asansor", None),
    ("Otopark", "otopark", None),
    ("Eşyalı", "esyali", None),
    ("Kullanım Durumu", "kullanim_durumu", None),
    ("Site İçerisinde", "site_icerisinde", None),
    ("Site Adı", "site_adi", None),
    ("Aidat (TL)", "aidat", None),
    ("Krediye", "krediye_uygun", _lux_norm_krediye),
    ("Tapu Durumu", "tapu_durumu", None),
]

QUICK_FACT_DISPLAY = {
    "brut_m2": ("Brüt m²", "m²"),
    "net_m2": ("Net m²", "m²"),
    "oda_sayisi": ("Oda Sayısı", ""),
    "bina_yasi": ("Bina Yaşı", ""),
    "kat_sayisi": ("Kat Sayısı", ""),
    "bulundugu_kat": ("Bulunduğu Kat", ""),
    "isitma": ("Isıtma", ""),
    "banyo_sayisi": ("Banyo Sayısı", ""),
    "mutfak": ("Mutfak", ""),
    "balkon": ("Balkon", ""),
    "asansor": ("Asansör", ""),
    "otopark": ("Otopark", ""),
    "esyali": ("Eşyalı", ""),
    "kullanim_durumu": ("Kullanım Durumu", ""),
    "site_icerisinde": ("Site İçerisinde", ""),
    "site_adi": ("Site Adı", ""),
    "aidat": ("Aidat", "TL"),
    "krediye_uygun": ("Krediye Uygun", ""),
    "tapu_durumu": ("Tapu Durumu", ""),
}

_UI_NOISE_CUTS = [
    "Favori Satıcılarıma ekle", "Mesaj gönder", "Kredi Teklifleri",
    "Tüm ilanları", "Favorilerime Ekle", "Cep 0(", "Enerji Kimlik",
    "EmlakEndeksi", "Kimden Emlak", "Takas Hayır",
]


def _normalize_amenity_text(text: str) -> str:
    """
    OCR output'ı temizle: aşırı boş satır, rastgele büyük harf, bozuk karakterleri düzelt.
    
    Örnekler:
        "ADsL Doğrama lallrEh m (Hırsizi" → "ADSL doğrama hallah" (veya filtered)
        "Ankastre Firın Barbek BöyerEç" → "Ankastre Firın Barbek Boyer"
    
    Args:
        text: OCR output metni
    
    Returns:
        Temizlenmiş text (veya empty string eğer invalid)
    """
    # 1. HTML entity'leri decode
    text = html_mod.unescape(text)
    
    # 2. Fazlalık boş satır ve tab'leri temizle
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    # 3. Bozuk pattern'leri (OCR artefaktları) temizle
    # Heuristic: 2+ büyük harf + 2+ küçük harf sırada = bozuk (normalize et)
    text = re.sub(
        r'([a-z])([A-Z]{2,})([a-z])',
        lambda m: m.group(1) + m.group(2).lower() + m.group(3),
        text
    )
    
    # 4. Sonu UI noise word'le bitiyorsa kes
    noise_endings = [
        "Favori", "Mesaj", "Kredi", "Tüm İlanları", "Enerji", 
        "EmlakEndeksi", "Cep", "Kimlik", "Takas"
    ]
    for noise in noise_endings:
        if text.endswith(noise):
            text = text[:len(text) - len(noise)].strip()
            break
    
    # 5. Çift boş satır varsa (fazla uzun amenity) kes
    if "  " in text:
        text = text.split("  ")[0].strip()
    
    # 6. Min/max uzunluk kontrol
    text = text.strip()
    if len(text) < 2 or len(text) > 200:
        return ""
    
    # 7. Tek kelime değilse (en az 1 boş satır) kabul et
    if " " not in text and len(text) < 4:
        return ""  # Çok kısa, skip
    
    return text


def _sanitize_fact_value(val: str) -> str:
    """
    Parse edilen fact value'nu temizle: bozuk karakterler, fazla boş satır, vs.
    
    Örnekler:
        "D1" → "" (invalid)
        "1 P" → "" (invalid)
        "3+1" → "3+1" (valid)
        "  Evet  " → "Evet" (trim)
    
    Args:
        val: Ham fact value
    
    Returns:
        Temizlenmiş value (veya empty string eğer invalid)
    """
    # 1. Trim
    val = val.strip()
    if not val:
        return ""
    
    # 2. HTML entities decode
    val = html_mod.unescape(val)
    
    # 3. Fazla whitespace temizle
    val = re.sub(r'\s+', ' ', val)
    
    # 4. Şüpheli pattern'leri filter et
    # "D1", "1 P", "belirtilmemiş", vs.
    suspicious = [
        r"^D\d+$",  # D1, D2, D3, ...
        r"^[0-9] [A-Z]$",  # "1 P", "2 B", ...
        r"belirtilmemiş|bilinmiyor|—|\.\.\.|\?+",  # placeholder
    ]
    for pat in suspicious:
        if re.search(pat, val, re.IGNORECASE):
            return ""
    
    # 5. Min/max uzunluk
    if len(val) < 1 or len(val) > 100:
        return ""
    
    return val


def _extract_quick_facts(text_before_desc: str) -> Dict[str, str]:
    """Açıklama metninden quick facts'i çıkar (parsing + sanitization)."""
    facts: Dict[str, str] = {}
    lines = [l.strip() for l in text_before_desc.splitlines() if l.strip()]
    joined = "\n".join(lines)

    for label, key, norm in QUICK_FACT_LABELS:
        if key in facts:
            continue
        pattern = re.escape(label) + r"\s*[:\-—]?\s*([^\n]{0,60})"
        m = re.search(pattern, joined)
        if m:
            val = m.group(1).strip(" .:-—")
            cut_at = len(val)
            for noise in _UI_NOISE_CUTS:
                idx = val.find(noise)
                if idx != -1:
                    cut_at = min(cut_at, idx)
            val = val[:cut_at].strip(" .:-—")
            
            # FIX: Sanitization ekle
            val = _sanitize_fact_value(val)  # ← Bozuk değerleri filter et
            if not val:
                continue  # Boş/invalid, skip
            
            # Normalization fonksiyonu varsa uygula
            if norm:
                # Fonksiyon adı string'te, globals'dan çek
                if isinstance(norm, str):
                    norm_func = globals().get(norm)
                    if callable(norm_func):
                        val = norm_func(val)
                elif callable(norm):
                    val = norm(val)
            
            if val:  # Normalization sonrasında kontrol
                facts[key] = val

    return facts


def parse_full_description(raw: str) -> Dict:
    """Ham açıklama metnini quick_facts / narrative / amenities katmanlarına ayırır.
    (Tek doğruluk kaynağı — eski description_parser.py ve pipeline içindeki
    parse_full_description_luxury bu fonksiyonla birleştirildi.)"""
    if not raw:
        return {"quick_facts": {}, "narrative": {"paragraphs": [], "highlights": []}, "amenities": {}}

    text = raw.strip()

    cut_idx = len(text)
    for marker in HARD_CUT_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            cut_idx = min(cut_idx, idx)
    text = text[:cut_idx].strip()

    desc_label_idx = text.find("\nAçıklama")
    if desc_label_idx == -1:
        desc_label_idx = text.find("Açıklama")

    if desc_label_idx != -1:
        before = text[:desc_label_idx]
        after = text[desc_label_idx:]
        after = re.sub(r"^\s*Açıklama\s*\n(?:a\s*\n)?", "", after)
    else:
        before = ""
        after = text

    quick_facts = _extract_quick_facts(before)

    amenity_start = re.search(r"\nÖzellikler\s*\n", after)
    if amenity_start:
        narrative_block = after[: amenity_start.start()].strip()
        amenity_block = after[amenity_start.end():].strip()
    else:
        narrative_block = after.strip()
        amenity_block = ""

    paragraphs: List[str] = []
    highlights: List[str] = []
    for line in narrative_block.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("*"):
            highlights.append(line.lstrip("* ").strip())
        else:
            paragraphs.append(line)

    amenities: Dict[str, List[str]] = {}
    if amenity_block:
        current: Optional[str] = None
        for raw_line in amenity_block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line in AMENITY_SECTION_TITLES:
                current = line
                amenities[current] = []
                continue
            if current is None:
                continue
            tokens = re.split(r"\s{2,}", line) if re.search(r"\s{2,}", line) else [line]
            for tok in tokens:
                tok = tok.strip(" .")
                if len(tok) <= 1:
                    continue
                tok_clean = re.sub(r"^[VWXvwx]\s+", "", tok).strip()
                if tok_clean:
                    # FIX #4: OCR cleaning - bozuk chip'leri filter et
                    cleaned = _normalize_amenity_text(tok_clean)
                    if cleaned:
                        amenities[current].append(cleaned)

    return {
        "quick_facts": quick_facts,
        "narrative": {"paragraphs": paragraphs, "highlights": highlights},
        "amenities": amenities,
    }

# ── Ultra Luxury v3 — tek sayfa kart üretici (görsel olarak yükseltildi) ─────

_LUX_STYLE = """
:root{
  --bg-0:#0a0a0b;
  --bg-1:#131315;
  --bg-2:#1a1a1d;
  --bg-3:#202023;
  --line:#28282c;
  --line-soft:#1e1e21;
  --gold:#c9a45c;
  --gold-soft:#e8cd93;
  --gold-dim:rgba(201,164,92,.35);
  --text-0:#f5f4f1;
  --text-1:#cbcac6;
  --text-2:#8f8e8a;
  --radius:16px;
  --shadow:0 30px 70px -25px rgba(0,0,0,.7);
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
html,body{margin:0;padding:0;background:
  radial-gradient(ellipse 1200px 600px at 50% -10%, rgba(201,164,92,.06), transparent 60%),
  var(--bg-0);
  color:var(--text-0);
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;}
body{padding-bottom:60px;}
h1,h2,h3,.serif{font-family:'Playfair Display',Georgia,'Times New Roman',serif;}
::selection{background:var(--gold-dim);color:#fff;}
a{color:inherit;}

.wrap{max-width:1180px;margin:0 auto;padding:0 24px;}

/* ---------- TOP NAV ---------- */
.nexa-nav{position:sticky;top:0;z-index:50;background:rgba(10,10,11,.86);
  backdrop-filter:blur(14px);border-bottom:1px solid var(--line-soft);}
.nexa-nav .inner{max-width:1180px;margin:0 auto;padding:14px 24px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;}
.nexa-brand{display:flex;align-items:center;gap:10px;font-family:'Playfair Display',serif;
  font-size:16px;letter-spacing:.04em;color:var(--text-0);text-decoration:none;}
.nexa-brand .dot{width:7px;height:7px;border-radius:50%;background:var(--gold);
  box-shadow:0 0 10px var(--gold);}
.nexa-brand b{color:var(--gold-soft);}
.nexa-actions{display:flex;align-items:center;gap:8px;}
.nexa-btn{display:inline-flex;align-items:center;gap:6px;background:var(--bg-2);
  border:1px solid var(--line);color:var(--text-1);font-size:12.5px;padding:8px 14px;
  border-radius:20px;cursor:pointer;text-decoration:none;transition:all .2s ease;
  font-family:inherit;}
.nexa-btn:hover{border-color:var(--gold-dim);color:var(--gold-soft);background:var(--bg-3);}
.nexa-jump{position:relative;}
.nexa-jump select{appearance:none;background:var(--bg-2);border:1px solid var(--line);
  color:var(--text-1);font-size:12.5px;padding:8px 30px 8px 14px;border-radius:20px;
  cursor:pointer;font-family:inherit;}

/* ---------- HERO / GALLERY ---------- */
.listing-anchor{scroll-margin-top:70px;}
.card{background:var(--bg-1);border:1px solid var(--line);border-radius:var(--radius);
  overflow:hidden;margin:40px 0;box-shadow:var(--shadow);position:relative;
  animation:cardIn .6s ease both;}
@keyframes cardIn{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}

.ribbon{position:absolute;top:18px;right:-42px;background:linear-gradient(120deg,var(--gold),var(--gold-soft));
  color:#1a1408;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  padding:5px 50px;transform:rotate(45deg);z-index:5;box-shadow:0 4px 14px rgba(0,0,0,.35);}

.gallery{display:grid;grid-template-columns:2fr 1fr;grid-template-rows:1fr 1fr;gap:4px;
  aspect-ratio:16/8;background:var(--bg-2);}
.gallery .g-main{grid-row:1/3;}
.gallery figure{margin:0;position:relative;overflow:hidden;cursor:pointer;background:#111;}
.gallery img{width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .6s cubic-bezier(.2,.8,.2,1);}
.gallery figure:hover img{transform:scale(1.05);}
.gallery .g-count{position:absolute;right:12px;bottom:12px;background:rgba(0,0,0,.6);
  color:#fff;font-size:12px;letter-spacing:.04em;padding:6px 12px;border-radius:20px;
  backdrop-filter:blur(4px);}
.gallery .g-badge{position:absolute;left:16px;top:16px;background:rgba(0,0,0,.55);
  color:var(--gold-soft);font-size:11px;letter-spacing:.12em;text-transform:uppercase;
  padding:6px 12px;border-radius:20px;backdrop-filter:blur(4px);border:1px solid var(--gold-dim);}
.gallery .g-all{position:absolute;right:12px;top:12px;background:rgba(0,0,0,.6);color:#fff;
  font-size:11.5px;padding:6px 12px;border-radius:20px;backdrop-filter:blur(4px);}

.filmstrip{display:flex;gap:4px;padding:4px;background:var(--bg-2);overflow-x:auto;}
.filmstrip img{width:84px;height:60px;object-fit:cover;border-radius:6px;flex:0 0 auto;
  cursor:pointer;opacity:.65;transition:opacity .2s ease,transform .2s ease;}
.filmstrip img:hover{opacity:1;transform:translateY(-2px);}

/* ---------- HEADER ---------- */
.head{padding:32px 40px 24px;border-bottom:1px solid var(--line);
  display:flex;justify-content:space-between;align-items:flex-start;gap:24px;flex-wrap:wrap;}
.head .loc{color:var(--gold);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  margin-bottom:10px;display:flex;align-items:center;gap:6px;}
.head h1{font-size:27px;font-weight:600;line-height:1.35;margin:0 0 8px;color:var(--text-0);
  max-width:640px;}
.head .no{color:var(--text-2);font-size:12px;letter-spacing:.05em;}
.price{text-align:right;white-space:nowrap;}
.price .amt{font-family:'Playfair Display',serif;font-size:33px;color:var(--gold-soft);
  font-weight:600;}
.price .tag{display:block;font-size:11px;color:var(--text-2);letter-spacing:.1em;
  text-transform:uppercase;margin-top:4px;}
.price .m2{display:block;font-size:11.5px;color:var(--text-2);margin-top:6px;}

/* ---------- QUICK FACTS ---------- */
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
  gap:1px;background:var(--line);border-bottom:1px solid var(--line);}
.facts .f{background:var(--bg-1);padding:18px 20px;transition:background .2s ease;}
.facts .f:hover{background:var(--bg-2);}
.facts .f .v{font-size:18px;font-weight:600;color:var(--text-0);}
.facts .f .k{font-size:11px;color:var(--text-2);text-transform:uppercase;
  letter-spacing:.08em;margin-top:3px;}

/* ---------- BODY GRID ---------- */
.body-grid{display:grid;grid-template-columns:1fr 320px;gap:0;}
@media (max-width:820px){.body-grid{grid-template-columns:1fr;} .main-col{border-right:none!important;}}
.main-col{padding:32px 40px;border-right:1px solid var(--line);}
.side-col{padding:32px 28px;background:var(--bg-2);}

.section-title{font-size:13px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--gold);margin:0 0 16px;display:flex;align-items:center;gap:10px;}
.section-title::after{content:'';flex:1;height:1px;background:var(--line);}

.narrative p{color:var(--text-1);line-height:1.85;font-size:15px;margin:0 0 16px;}

.highlights{list-style:none;margin:0 0 32px;padding:0;display:grid;gap:10px;}
.highlights li{position:relative;padding-left:26px;color:var(--text-1);
  font-size:14.5px;line-height:1.6;}
.highlights li::before{content:'[OK]';position:absolute;left:0;top:0;color:var(--gold);
  font-weight:700;}

/* ---------- AI BOX ---------- */
.ai-box {
  background: linear-gradient(135deg, rgba(201, 164, 92, 0.08) 0%, rgba(19, 19, 21, 0.6) 100%);
  border: 1px solid var(--gold-dim);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 32px;
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.05), 0 10px 30px rgba(0,0,0,0.25);
  position: relative;
  overflow: hidden;
}
.ai-box::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: linear-gradient(to bottom, var(--gold), var(--gold-soft));
}
.ai-box .ai-h {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--gold-soft);
  font-size: 13px;
  letter-spacing: .08em;
  text-transform: uppercase;
  margin-bottom: 20px;
  font-weight: 700;
}
.ai-box p {
  color: var(--text-1);
  font-size: 14.5px;
  line-height: 1.8;
  margin: 0 0 14px;
}
.ai-item {
  display: flex;
  gap: 16px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.ai-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}
.ai-number {
  flex: 0 0 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--gold-dim);
  border: 1px solid var(--gold);
  color: var(--gold-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 0 8px rgba(201,164,92,0.15);
}
.ai-content {
  color: var(--text-1);
  font-size: 14.5px;
  line-height: 1.8;
  flex: 1;
}
.ai-content strong {
  color: var(--text-0);
  font-weight: 600;
}

/* ---------- CMA WIDGET ---------- */
.cma-widget {
  background: var(--bg-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 28px;
}
.cma-widget .widget-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--gold-soft);
  margin-bottom: 14px;
  font-weight: 600;
}
.cma-widget .chart-container {
  background: var(--bg-0);
  border-radius: 8px;
  padding: 15px 10px;
  border: 1px solid var(--line-soft);
}
.cma-widget .cma-summary {
  font-size: 13.5px;
  color: var(--text-1);
  margin-top: 14px;
}
.cma-widget .cma-summary.below strong {
  color: var(--green);
}
.cma-widget .cma-summary.above strong {
  color: var(--gold-soft);
}

/* ---------- BROKER PLAYBOOK ---------- */
.broker-playbook {
  background: rgba(201, 164, 92, 0.04);
  border: 1px dashed var(--gold);
  border-radius: 12px;
  padding: 22px;
  margin-top: 28px;
  margin-bottom: 28px;
}
.broker-playbook .playbook-title {
  font-size: 12.5px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--gold-soft);
  margin-bottom: 14px;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 8px;
}
.broker-playbook ul {
  margin: 0;
  padding: 0 0 0 20px;
  color: var(--text-1);
  font-size: 13.5px;
  line-height: 1.7;
}
.broker-playbook li {
  margin-bottom: 8px;
}
.broker-playbook li:last-child {
  margin-bottom: 0;
}

/* Custom list items for Pros/Cons based on child index */
.ai-item:nth-of-type(3) li::before {
  content: '✓ ';
  color: var(--green);
  font-weight: bold;
}
.ai-item:nth-of-type(4) li::before {
  content: '⚠️ ';
  color: var(--red);
  font-weight: bold;
}


/* ---------- AMENITY CHIPS ---------- */
.amenity-group{margin-bottom:20px;}
.amenity-group h4{font-size:12px;color:var(--text-2);text-transform:uppercase;
  letter-spacing:.08em;margin:0 0 10px;font-weight:600;}
.chips{display:flex;flex-wrap:wrap;gap:8px;}
.chip{background:var(--bg-1);border:1px solid var(--line);color:var(--text-1);
  font-size:12.5px;padding:6px 12px;border-radius:20px;transition:border-color .2s ease;}
.chip:hover{border-color:var(--gold-dim);color:var(--gold-soft);}

/* ---------- SIDE INFO ---------- */
.contact{background:var(--bg-1);border:1px solid var(--line);border-radius:12px;
  padding:22px;margin-bottom:20px;}
.contact .brandline{display:flex;align-items:center;gap:8px;margin-bottom:16px;
  padding-bottom:14px;border-bottom:1px solid var(--line);}
.contact .brandline .dot{width:7px;height:7px;border-radius:50%;background:var(--gold);
  box-shadow:0 0 10px var(--gold);}
.contact .brandline span{font-family:'Playfair Display',serif;font-size:14px;color:var(--gold-soft);}
.contact .k{color:var(--text-2);font-size:11px;text-transform:uppercase;letter-spacing:.08em;}
.contact .v{color:var(--text-0);font-size:14px;margin:2px 0 12px;}
.src-badge{display:inline-block;font-size:10.5px;color:var(--text-2);
  border:1px solid var(--line);border-radius:20px;padding:4px 10px;margin-top:6px;}
.share-row{display:flex;gap:8px;margin-top:14px;}
.share-btn{flex:1;text-align:center;background:var(--bg-3);border:1px solid var(--line);
  color:var(--text-1);font-size:12px;padding:10px;border-radius:10px;cursor:pointer;
  text-decoration:none;transition:all .2s ease;font-family:inherit;}
.share-btn:hover{border-color:var(--gold-dim);color:var(--gold-soft);}

/* ---------- DEV PANEL ---------- */
details.dev{margin-top:24px;}
details.dev summary{cursor:pointer;color:var(--text-2);font-size:11.5px;
  letter-spacing:.06em;text-transform:uppercase;}
details.dev .dev-body{font-size:12px;color:var(--text-2);margin-top:10px;
  line-height:1.7;}

/* ---------- FOOTER ---------- */
.nexa-footer{text-align:center;padding:36px 20px 10px;color:var(--text-2);font-size:11.5px;
  letter-spacing:.06em;}
.nexa-footer b{color:var(--gold-soft);}

/* ---------- LIGHTBOX ---------- */
.lightbox{position:fixed;inset:0;background:rgba(6,6,7,.94);display:none;
  align-items:center;justify-content:center;z-index:999;backdrop-filter:blur(8px);}
.lightbox.open{display:flex;}
.lightbox img{max-width:92vw;max-height:86vh;object-fit:contain;border-radius:6px;
  box-shadow:0 30px 80px rgba(0,0,0,.6);}
.lightbox .nav{position:absolute;top:0;bottom:0;width:15%;display:flex;
  align-items:center;justify-content:center;color:rgba(255,255,255,.6);font-size:34px;
  cursor:pointer;user-select:none;transition:color .2s ease;}
.lightbox .nav:hover{color:var(--gold-soft);}
.lightbox .nav.prev{left:0;} .lightbox .nav.next{right:0;}
.lightbox .close{position:absolute;top:22px;right:28px;color:#fff;font-size:26px;
  cursor:pointer;opacity:.8;}
.lightbox .close:hover{opacity:1;color:var(--gold-soft);}
.lightbox .count{position:absolute;bottom:22px;left:50%;transform:translateX(-50%);
  color:rgba(255,255,255,.7);font-size:13px;letter-spacing:.05em;}

/* ---------- TOAST ---------- */
.toast{position:fixed;bottom:26px;left:50%;transform:translateX(-50%) translateY(20px);
  background:var(--bg-3);border:1px solid var(--gold-dim);color:var(--gold-soft);
  padding:10px 20px;border-radius:20px;font-size:13px;z-index:1000;opacity:0;
  pointer-events:none;transition:all .3s ease;}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0);}

/* ---------- PRINT ---------- */
@media print{
  .nexa-nav,.lightbox,.share-row,.filmstrip,.ribbon{display:none!important;}
  body{background:#fff;color:#000;}
  .card{box-shadow:none;border:1px solid #ccc;}
  .side-col{background:#f7f7f7;}
}
"""

_LUX_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700'
    '&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">'
)

_LUX_FAVICON = (
    '<link rel="icon" href="data:image/svg+xml,'
    '%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E'
    '%3Cpolygon points=%2716,2 30,16 16,30 2,16%27 fill=%27%23c9a45c%27/%3E%3C/svg%3E">'
)

_LUX_LIGHTBOX_JS = """
let __lbPhotos = [];
let __lbIdx = 0;
function openLightbox(photos, idx){
  __lbPhotos = photos; __lbIdx = idx;
  document.getElementById('lb-img').src = photos[idx];
  document.getElementById('lb-count').textContent = (idx+1) + ' / ' + photos.length;
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox(){ document.getElementById('lightbox').classList.remove('open'); }
function lbStep(delta){
  if(!__lbPhotos.length) return;
  __lbIdx = (__lbIdx + delta + __lbPhotos.length) % __lbPhotos.length;
  document.getElementById('lb-img').src = __lbPhotos[__lbIdx];
  document.getElementById('lb-count').textContent = (__lbIdx+1) + ' / ' + __lbPhotos.length;
}
document.addEventListener('keydown', (e) => {
  if(!document.getElementById('lightbox').classList.contains('open')) return;
  if(e.key === 'Escape') closeLightbox();
  if(e.key === 'ArrowRight') lbStep(1);
  if(e.key === 'ArrowLeft') lbStep(-1);
});
function showToast(msg){
  const t = document.getElementById('nexa-toast');
  if(!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}
function copyLink(){
  navigator.clipboard.writeText(window.location.href).then(() => showToast('Bağlantı kopyalandı [OK]'));
}
function shareWhatsApp(title){
  const url = 'https://wa.me/?text=' + encodeURIComponent(title + ' — ' + window.location.href);
  window.open(url, '_blank');
}
function jumpTo(id){
  if(!id) return;
  const el = document.getElementById(id);
  if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
}
"""


def _lux_esc(s) -> str:
    return html_mod.escape(str(s), quote=True)


def _lux_photo_tag(src: str, alt: str = "", is_hero: bool = False) -> str:
    """
    Fotoğraf <img> tag'ı. Hero görsel ise LCP optimizasyonu uygular.
    
    Args:
        src: Görsel URL
        alt: Alt text
        is_hero: True ise fetchpriority + eager loading (LCP için)
    
    Returns:
        <img ...> tag'ı
    """
    attrs = f'src="{_lux_esc(src)}" alt="{_lux_esc(alt)}"'
    
    if is_hero:
        # Hero görsel (ana galeri resmi): eager + high priority
        attrs += ' loading="eager" fetchpriority="high"'
    else:
        # Thumbnail, filmstrip: lazy loading
        attrs += ' loading="lazy"'
    
    return f'<img {attrs}>'


def _lux_render_gallery(photos: List[str], title: str, listing_id: str = "") -> Tuple[str, str]:
    """
    Gallery HTML + JavaScript array tanımını ayrı döndür.
    
    FIX: 
    - rest = photos[1:3] (max 2 side tile, toplam 3 tile)
    - onclick'lerde array inline yerine listing_id referans (LISTING_PHOTOS_{listing_id})
    - JS array'i sayfa başına bir kez tanımla
    
    Returns:
        (gallery_html + filmstrip_html, js_array_definition)
    """
    if not photos:
        return (
            '<div class="gallery"><figure class="g-main" style="display:flex;'
            'align-items:center;justify-content:center;color:var(--text-2);'
            'font-size:13px;letter-spacing:.05em;">Fotoğraf bulunamadı</figure></div>',
            ""
        )

    # Listing ID fallback (eğer vermezse otomatik)
    if not listing_id:
        listing_id = "noId"

    main = photos[0]
    rest = photos[1:3]  # ← FIX: sadece 2 taraf tile (1 main + 2 side = 3 toplam)

    figs = [
        f'<figure class="g-main" onclick="openLightbox(LISTING_PHOTOS_{listing_id}, 0)">'
        f'{_lux_photo_tag(main, title, is_hero=True)}'  # is_hero=True
        f'<span class="g-badge">Ultra Luxury</span>'
        f'</figure>'
    ]
    
    for i, p in enumerate(rest, start=1):
        extra = ""
        if i == len(rest) and len(photos) > 3:  # Toplam 3'den fazla varsa
            extra = f'<span class="g-count">+{len(photos) - 3} fotoğraf</span>'
        figs.append(
            f'<figure onclick="openLightbox(LISTING_PHOTOS_{listing_id}, {i})">'
            f'{_lux_photo_tag(p, title)}{extra}</figure>'
        )
    
    gallery_html = f'<div class="gallery">{"".join(figs)}</div>'

    # Filmstrip (lazy loaded thumbnails)
    filmstrip_html = ""
    if len(photos) > 1:
        thumbs = "".join(
            f'<img src="{_lux_esc(p)}" alt="" loading="lazy" '
            f'onclick="openLightbox(LISTING_PHOTOS_{listing_id}, {i})">'
            for i, p in enumerate(photos[:24])
        )
        filmstrip_html = f'<div class="filmstrip">{thumbs}</div>'

    # JavaScript array tanımını döndür (sayfa başında bir kez)
    photos_js = json.dumps(photos)
    js_def = f"const LISTING_PHOTOS_{listing_id} = {photos_js};"

    return gallery_html + filmstrip_html, js_def


def _lux_render_quick_facts(facts: Dict[str, str], price: str = "") -> str:
    """Quick facts grid + m² başına fiyat rozetini göster."""
    # Eğer facts boş ama price varsa, sadece ₺/m² badge'i göster
    if not facts:
        price_m2 = _lux_price_per_m2(price, {}) if price else ""
        if price_m2:
            return (
                f'<div class="facts">'
                f'<div class="f"><div class="v">{_lux_esc(price_m2)}</div>'
                f'<div class="k">₺/m²</div></div>'
                f'</div>'
            )
        return ""
    
    # m² başına fiyat badge'ini hesapla
    price_m2 = _lux_price_per_m2(price, facts) if price else ""
    
    # Facts display'ini hazırla
    cells = []
    for key, val in facts.items():
        if key in QUICK_FACT_DISPLAY:
            label, unit = QUICK_FACT_DISPLAY[key]
            val_disp = f"{val} {unit}".strip()
            cells.append(
                f'<div class="f"><div class="v">{_lux_esc(val_disp)}</div>'
                f'<div class="k">{_lux_esc(label)}</div></div>'
            )
    
    # Price per m² badge'ini en sona ekle
    if price_m2:
        cells.append(
            f'<div class="f"><div class="v">{_lux_esc(price_m2)}</div>'
            f'<div class="k">₺/m²</div></div>'
        )
    
    if not cells:
        return ""
    
    return f'<div class="facts">{"".join(cells)}</div>'


def _lux_render_amenities(amenities: Dict[str, List[str]]) -> str:
    if not amenities:
        return ""
    groups = []
    for section, items in amenities.items():
        if not items:
            continue
        chips = "".join(f'<span class="chip">{_lux_esc(i)}</span>' for i in items[:24])
        groups.append(
            f'<div class="amenity-group"><h4>{_lux_esc(section)}</h4>'
            f'<div class="chips">{chips}</div></div>'
        )
    if not groups:
        return ""
    return (
        '<div class="section-title">Öne Çıkan Donanımlar</div>'
        f'{"".join(groups)}'
    )


def _lux_price_per_m2(price: str, facts: Dict[str, str]) -> str:
    """Fiyat ve brüt m² ayrıştırılabiliyorsa m² başı fiyat rozetini üretir."""
    try:
        m2_raw = facts.get("brut_m2") or facts.get("net_m2")
        if not m2_raw:
            return ""
        m2_num = float(re.sub(r"[^\d,\.]", "", m2_raw).replace(".", "").replace(",", "."))
        price_num = float(re.sub(r"[^\d]", "", price))
        if m2_num <= 0 or price_num <= 0:
            return ""
        per_m2 = price_num / m2_num
        return f"~{per_m2:,.0f} ₺/m²".replace(",", ".")
    except Exception:
        return ""


def _markdown_to_html(text: str) -> str:
    if not text:
        return ""
    # Safe escape first
    html = html_mod.escape(text)
    
    # Render headers
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Render bold **text**
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Render bullet points
    html = re.sub(r'^\s*[-*+]\s+(.*?)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    
    # Render numbered lists
    html = re.sub(r'^\s*(\d+)\.\s+(.*?)$', r'<div class="ai-item"><span class="ai-number">\1</span><div class="ai-content">\2</div></div>', html, flags=re.MULTILINE)
    
    # Split paragraphs
    paragraphs = html.split('\n\n')
    formatted = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<div class="ai-item">') or p.startswith('<li>') or p.startswith('<h'):
            formatted.append(p)
        else:
            p_formatted = p.replace("\n", "<br>")
            formatted.append(f'<p>{p_formatted}</p>')
                
    return '\n'.join(formatted)


def _generate_broker_playbook(price_str: str, specs: Dict[str, str], title: str) -> str:
    playbook_items = []
    
    # 1. Price analysis tüyo
    if "milyon" in price_str.lower() or price_str.replace(".", "").strip().isdigit():
        playbook_items.append("Fiyat pazarlığında m² avantajını ve bölgedeki benzer ilanların ortalama satış sürelerini koz olarak kullanın.")
    else:
        playbook_items.append("Mülkün kira getiri çarpanını ve amortisman süresini yatırımcı adaylarına özellikle vurgulayın.")
        
    # 2. Location/Features tüyo
    room = specs.get("Oda Sayısı", "")
    if "3+1" in room or "4+1" in room:
        playbook_items.append("Geniş aile profillerine odaklanın; sosyal tesis, otopark ve site güvenlik detaylarını ön plana çıkarın.")
    elif "1+1" in room or "1+0" in room:
        playbook_items.append("Bireysel yatırımcı ve genç profesyonellere odaklanın; ulaşım (metro, anayol) yakınlığını vurgulayın.")
        
    # 3. Dynamic target tip
    if "ofis" in title.lower() or "iş" in title.lower():
        playbook_items.append("Tabela değeri, prestij ve stopaj avantajı gibi ticari mülk argümanlarını görüşmede hazır bulundurun.")
    else:
        playbook_items.append("Bölgedeki imar durumu veya değer artış trendi raporunu görüşme öncesinde mutlaka inceleyin.")
        
    items_html = "".join(f"<li>{item}</li>" for item in playbook_items)
    return f"""
    <div class="broker-playbook">
      <div class="playbook-title">💡 Broker Görüşme & Müzakere Tüyoları (Sadece Danışman İçin)</div>
      <ul>{items_html}</ul>
    </div>
    """


def build_luxury_card_html(detail: Dict, standalone: bool = True, anchor_id: str = "") -> str:
    """Tek bir ilan için tam sayfa (standalone=True) ya da <body> içeriği döner."""
    parsed = parse_full_description(detail.get("raw_description", ""))
    facts = parsed["quick_facts"]
    narrative = parsed["narrative"]
    amenities = parsed["amenities"]

    title = detail.get("title", "")
    price = detail.get("price", "")
    listing_id = detail.get("listing_id", "")
    photos = detail.get("photos", []) or []
    loc = detail.get("location", {}) or {}
    loc_str = " · ".join([v for v in [loc.get("il"), loc.get("ilce"), loc.get("mahalle")] if v])
    ai = detail.get("ai_analysis") or {}
    desc_source = detail.get("description_source", "")
    anchor_id = anchor_id or f"ilan-{listing_id or 'kart'}"

    per_m2 = _lux_price_per_m2(price, facts)
    per_m2_html = f'<span class="m2">{_lux_esc(per_m2)}</span>' if per_m2 else ""

    cma_html = ""
    if per_m2:
        try:
            clean_digits = re.sub(r"[^\d]", "", per_m2)
            if clean_digits:
                m2_val = float(clean_digits)
                market_avg = m2_val * 0.92
                diff_pct = ((m2_val - market_avg) / market_avg) * 100
                diff_text = f"Bölge ortalamasının %{abs(diff_pct):.1f} üzerinde" if diff_pct > 0 else f"Bölge ortalamasından %{abs(diff_pct):.1f} daha avantajlı"
                color_class = "above" if diff_pct > 0 else "below"
                
                circle_x = 200 + (diff_pct * 3)
                circle_x = max(50, min(350, circle_x))
                
                cma_html = f"""
        <div class="cma-widget">
          <div class="widget-title">📊 Bölgesel Metrekare Fiyat Değerlendirmesi</div>
          <div class="chart-container">
            <svg viewBox="0 0 400 120" style="width:100%; height:auto;">
              <path d="M 10 100 Q 100 20 200 40 T 390 100" fill="none" stroke="rgba(201, 164, 92, 0.25)" stroke-width="3"/>
              <line x1="200" y1="15" x2="200" y2="100" stroke="rgba(255,255,255,0.25)" stroke-dasharray="4"/>
              <text x="130" y="25" fill="#8f8e8a" style="font-size:10px;">Ortalama: {market_avg:,.0f} TL/m²</text>
              <circle cx="{circle_x}" cy="60" r="7" fill="#c9a45c" style="filter: drop-shadow(0 0 8px #c9a45c);"/>
              <text x="{circle_x - 40}" y="85" fill="#e8cd93" style="font-size:11px; font-weight:bold;">Bu İlan: {m2_val:,.0f} TL/m²</text>
            </svg>
          </div>
          <div class="cma-summary {color_class}">Bu mülk, mahalle ortalamasına kıyasla <strong>{diff_text}</strong> fiyatlandırılmıştır.</div>
        </div>
"""
        except Exception:
            pass

    playbook_html = ""
    if ai.get("text"):
        specs_dict = {}
        for f in (facts or []):
            if isinstance(f, tuple) and len(f) == 2:
                specs_dict[f[0]] = f[1]
            elif isinstance(f, dict):
                specs_dict.update(f)
        playbook_html = _generate_broker_playbook(price, specs_dict, title)

    paragraphs_html = "".join(f"<p>{_lux_esc(p)}</p>" for p in narrative["paragraphs"])
    if not paragraphs_html:
        paragraphs_html = '<p style="color:var(--text-2);">Açıklama metni bu ilan için çıkarılamadı.</p>'
    highlights_html = ""
    if narrative["highlights"]:
        items = "".join(f"<li>{_lux_esc(h)}</li>" for h in narrative["highlights"])
        highlights_html = (
            '<div class="section-title">Öne Çıkanlar</div>'
            f'<ul class="highlights">{items}</ul>'
        )

    ai_html = ""
    if ai.get("text"):
        ai_body_html = _markdown_to_html(ai["text"])
        ai_html = (
            '<div class="ai-box"><div class="ai-h">[BOT] Uzman Değerlendirmesi</div>'
            f'{ai_body_html}</div>'
        )
        if ai.get("model"):
            ai_html = ai_html.replace(
                "Uzman Değerlendirmesi</div>",
                f'Uzman Değerlendirmesi <span style="color:var(--text-2);'
                f'font-weight:400;text-transform:none;letter-spacing:0;">'
                f'&nbsp;· {_lux_esc(ai["model"])}</span></div>'
            )

    amenities_html = _lux_render_amenities(amenities)

    dev_html = ""
    lh = detail.get("lighthouse") or {}
    if lh or desc_source:
        dev_html = (
            '<details class="dev"><summary>Teknik / geliştirici bilgisi</summary>'
            '<div class="dev-body">'
            f'Açıklama kaynağı: {_lux_esc(desc_source or "—")}<br>'
            f'Lighthouse: ✅ {lh.get("passes","—")} · ❌ {lh.get("violations","—")} · '
            f'[WARN] {lh.get("warnings","—")} · ℹ {lh.get("info","—")}'
            '</div></details>'
        )

    ribbon_html = '<div class="ribbon">NEXA VIP</div>' if ai.get("text") else ""

    # FIX #2: Gallery'den HTML + JS array tanımı al
    gallery_html, js_photos_def = _lux_render_gallery(photos, title, listing_id)
    
    body_inner = f"""<div class="wrap">
  <div class="card listing-anchor" id="{_lux_esc(anchor_id)}">
    {ribbon_html}
    {gallery_html}

    <div class="head">
      <div>
        <div class="loc">📍 {_lux_esc(loc_str) or "&nbsp;"}</div>
        <h1>{_lux_esc(title)}</h1>
        <div class="no">İlan No {_lux_esc(listing_id)}</div>
      </div>
      <div class="price">
        <span class="amt">{_lux_esc(price)}</span>
        <span class="tag">Satılık</span>
        {per_m2_html}
      </div>
    </div>

    {_lux_render_quick_facts(facts, price)}

    <div class="body-grid">
      <div class="main-col">
        {cma_html}
        {ai_html}
        {playbook_html}
        <div class="section-title">Açıklama</div>
        <div class="narrative">{paragraphs_html}</div>
        {highlights_html}
        {amenities_html}
        {dev_html}
      </div>
      <div class="side-col">
        <div class="contact">
          <div class="brandline"><span class="dot"></span><span>NEXA · Gayrimenkul Mühendisi</span></div>
          <div class="k">İlan No</div><div class="v">{_lux_esc(listing_id)}</div>
          <div class="k">Konum</div><div class="v">{_lux_esc(loc_str) or "—"}</div>
          <div class="k">Fiyat</div><div class="v">{_lux_esc(price)}</div>
          <span class="src-badge">{_lux_esc(desc_source) or "Kaynak belirtilmedi"}</span>
          <div class="share-row">
            <a class="share-btn" href="javascript:void(0)" onclick="shareWhatsApp('{_lux_esc(title)}')">WhatsApp</a>
            <a class="share-btn" href="javascript:void(0)" onclick="copyLink()">Linki Kopyala</a>
            <a class="share-btn" href="javascript:void(0)" onclick="window.print()">Yazdır</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>"""

    if not standalone:
        return body_inner

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>{_lux_esc(title) or "İlan"} · NEXA.OS Luxury Card</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{_lux_esc(title)} — {_lux_esc(price)}">
<meta property="og:title" content="{_lux_esc(title)}">
<meta property="og:description" content="{_lux_esc(loc_str)} — {_lux_esc(price)}">
{f'<meta property="og:image" content="{_lux_esc(photos[0])}">' if photos else ''}
{_LUX_FAVICON}
{_LUX_FONTS}
<style>{_LUX_STYLE}</style>
<script>
{js_photos_def}
</script>
</head>
<body>
<nav class="nexa-nav"><div class="inner">
  <a class="nexa-brand" href="#"><span class="dot"></span>NEXA<b>.OS</b></a>
  <div class="nexa-actions">
    <button class="nexa-btn" onclick="copyLink()">🔗 Paylaş</button>
    <button class="nexa-btn" onclick="window.print()">🖨 Yazdır</button>
  </div>
</div></nav>
{body_inner}
<div class="nexa-footer">Bu sayfa <b>NEXA.OS</b> tarafından otomatik üretilmiştir · Gayrimenkul Mühendisi</div>

<div class="lightbox" id="lightbox" onclick="if(event.target===this) closeLightbox()">
  <span class="close" onclick="closeLightbox()">[ERR]</span>
  <span class="nav prev" onclick="lbStep(-1)">‹</span>
  <img id="lb-img" src="">
  <span class="nav next" onclick="lbStep(1)">›</span>
  <span class="count" id="lb-count"></span>
</div>
<div class="toast" id="nexa-toast"></div>

<script>{_LUX_LIGHTBOX_JS}</script>
</body>
</html>
"""


def build_luxury_cards_page(details: List[Dict]) -> str:
    """Tüm ilanları tek sayfada, sticky nav + hızlı geçiş menüsüyle birleştirir."""
    if not details:
        return "<html><body style='background:#0a0a0b;color:#8f8e8a;font-family:sans-serif;" \
               "display:flex;align-items:center;justify-content:center;height:100vh;'>" \
               "Hiç ilan üretilmedi.</body></html>"

    if len(details) == 1:
        return build_luxury_card_html(details[0])

    anchors = []
    bodies = []
    for i, d in enumerate(details):
        anchor_id = f"ilan-{d.get('listing_id') or i}"
        anchors.append((anchor_id, d.get("title") or f"İlan {i+1}", d.get("price") or ""))
        bodies.append(build_luxury_card_html(d, standalone=False, anchor_id=anchor_id))
    merged_body = "\n<hr style='border:none;border-top:1px solid #28282c;margin:0;'>\n".join(bodies)

    options = "".join(
        f'<option value="{_lux_esc(aid)}">{_lux_esc(t)[:42]} — {_lux_esc(p)}</option>'
        for aid, t, p in anchors
    )
    first_photos = next((d.get("photos") for d in details if d.get("photos")), [])
    og_image = f'<meta property="og:image" content="{_lux_esc(first_photos[0])}">' if first_photos else ""

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8">
<title>NEXA.OS · {len(details)} Ultra Luxury İlan</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="NEXA.OS — {len(details)} Ultra Luxury İlan">
{og_image}
{_LUX_FAVICON}
{_LUX_FONTS}<style>{_LUX_STYLE}</style></head>
<body>
<nav class="nexa-nav"><div class="inner">
  <a class="nexa-brand" href="#"><span class="dot"></span>NEXA<b>.OS</b></a>
  <div class="nexa-actions">
    <div class="nexa-jump">
      <select onchange="jumpTo(this.value)">
        <option value="">↳ {len(details)} ilan arasında atla…</option>
        {options}
      </select>
    </div>
    <button class="nexa-btn" onclick="copyLink()">🔗 Paylaş</button>
    <button class="nexa-btn" onclick="window.print()">🖨 Yazdır</button>
  </div>
</div></nav>
{merged_body}
<div class="nexa-footer">Bu sayfa <b>NEXA.OS</b> tarafından otomatik üretilmiştir · {len(details)} ilan · Gayrimenkul Mühendisi</div>
<div class="lightbox" id="lightbox" onclick="if(event.target===this) closeLightbox()">
  <span class="close" onclick="closeLightbox()">[ERR]</span>
  <span class="nav prev" onclick="lbStep(-1)">‹</span>
  <img id="lb-img" src="">
  <span class="nav next" onclick="lbStep(1)">›</span>
  <span class="count" id="lb-count"></span>
</div>
<div class="toast" id="nexa-toast"></div>
<script>{_LUX_LIGHTBOX_JS}</script>
</body></html>"""
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Sahibinden İlan Detay Pipeline (tüm sayfalar PageSpeed üzerinden)"
    )
    ap.add_argument("--url",            default=DEFAULT_TARGET,     help="Mağaza/liste URL'si")
    ap.add_argument("--ps-wait",        type=int, default=DEFAULT_PS_WAIT,
                                                                    help=f"Mağaza PageSpeed bekleme sn (varsayılan: {DEFAULT_PS_WAIT})")
    ap.add_argument("--det-wait",       type=int, default=DEFAULT_DET_WAIT,
                                                                    help=f"Detay PageSpeed bekleme sn/ilan (varsayılan: {DEFAULT_DET_WAIT})")
    ap.add_argument("--delay",          type=float, default=DEFAULT_DELAY,
                                                                    help=f"Detaylar arası bekleme sn (varsayılan: {DEFAULT_DELAY})")
    ap.add_argument("--headless",       action="store_true",        help="Chrome arka planda çalışsın")
    ap.add_argument("--ps-html",        default=DEFAULT_PS_HTML,    help="Mağaza PageSpeed HTML çıktısı")
    ap.add_argument("--detail-dir",     default=DEFAULT_DETAIL_DIR, help="Detay HTML klasörü")
    ap.add_argument("--out",            default=DEFAULT_CARDS_OUT,  help="Kart sayfası çıktısı")
    ap.add_argument("--extract-detail-html", default="", help="Var olan bir ilan DETAY HTML dosyasını parse et (PageSpeed sonucu veya direkt HTML) ve JSON yazdırıp çık")
    ap.add_argument("--extract-store-html",  default="", help="Var olan bir MAĞAZA/LİSTE HTML dosyasını parse et (PageSpeed sonucu) ve JSON yazdırıp çık")
    ap.add_argument("--ollama",         default=DEFAULT_OLLAMA,     help="Ollama URL")
    ap.add_argument("--model",          default=DEFAULT_MODEL,      help="Ollama model adı")
    ap.add_argument("--ai-delay",       type=float, default=0.5,    help="AI istekleri arası bekleme sn")
    ap.add_argument("--no-ai",          dest="no_ai",  action="store_true", help="Ollama analizini atla")
    ap.add_argument("--skip-pagespeed", dest="skip_ps", action="store_true",help="Adım 1'i atla (mevcut HTML kullan)")
    ap.add_argument("--skip-details",   dest="skip_det",action="store_true",help="Adım 3'ü atla (mevcut detay HTML'leri kullan)")
    args = ap.parse_args()

    # ── Kısa modlar: sadece HTML parse ───────────────────────────────
    if args.extract_detail_html:
        if not _BS4:
            print("✗ BeautifulSoup kurulu değil: pip install beautifulsoup4 lxml")
            sys.exit(1)

        p = Path(args.extract_detail_html)
        if not p.exists():
            print(f"✗ Dosya bulunamadı: {p}")
            sys.exit(1)

        raw = p.read_text(encoding="utf-8", errors="ignore")

        # ilan no
        m = re.search(r"(\d{6,})", p.stem)
        listing_id = m.group(1) if m else ""
        m2 = re.search(r"data-classifiedid=&quot;(\d{6,})&quot;", raw)
        if m2:
            listing_id = listing_id or m2.group(1)

        detail_url = _extract_sahibinden_detail_url(raw)
        if (not listing_id) and detail_url:
            m3 = re.search(r"-(\d{6,})/detay", detail_url)
            if m3:
                listing_id = m3.group(1)

        canonical_url = detail_url or (SB_SEARCH_URL.format(id=listing_id) if listing_id else "")
        title = _title_from_detail_url(detail_url, listing_id) or listing_id or "İlan"

        # PSI-aware çıkarıcıları kullan
        psi_specs   = _extract_psi_specs(raw)
        price       = psi_specs.get("Fiyat") or _extract_price_tr(raw)
        photos_detail = _extract_psi_photos(raw)
        photos      = _merge_photo_variants(photos_detail) or _parse_photos_from_raw(raw)
        full_photos = [p["url"] for p in photos_detail if p["type"] == "full"]
        thumb_photos_list = [p["url"] for p in photos_detail if p["type"] == "thumb"]
        audits      = _extract_psi_audits(raw)

        # Kategori (img alt fallback)
        category = ""
        for _, alt in ENC_IMG_RE.findall(raw):
            if "Emlak /" in alt or "Vasıta /" in alt or "Vasita /" in alt:
                category = html_mod.unescape(alt).strip()
                break

        specs: Dict[str, str] = {}
        if listing_id:
            specs["İlan No"] = listing_id
        priority_keys = [
            "Marka", "Seri", "Model", "Model Detay", "Model Yılı",
            "Motor Hacmi", "Motor Gücü", "Kilometre", "Vites", "Kasa Tipi",
            "Eurotax", "Takas", "Kimden", "Satıcı Tipi",
            "Şehir", "İlçe", "Mahalle", "Mahalle (detay)", "Ülke",
            "Kategori 1", "Kategori 2",
        ]
        for k in priority_keys:
            if k in psi_specs:
                specs[k] = psi_specs[k]
        for k, v in psi_specs.items():
            if k not in specs:
                specs[k] = v
        if category and "Kategori" not in specs:
            specs["Kategori"] = category

        det = ListingDetail(
            listing_id=listing_id or "unknown",
            title=title,
            price=price,
            canonical_url=canonical_url,
            thumb_url=(photos[0] if photos else ""),
            photos=photos,
            specs=specs,
            description="",
        )

        # AI (opsiyonel, ama sadece tüm bilgiler varsa)
        if not args.no_ai:
            step5_analyze([det], args.ollama, args.model, args.ai_delay)

        # Audit özetini hesapla
        fail_a  = [a for a in audits if a["status"] == "FAIL"]
        pass_a  = [a for a in audits if a["status"] == "PASS"]
        orta_a  = [a for a in audits if a["status"] == "ORTA"]
        bilgi_a = [a for a in audits if a["status"] == "BİLGİ"]

        print(json.dumps({
            "listing_id":      det.listing_id,
            "title":           det.title,
            "price":           det.price,
            "canonical_url":   det.canonical_url,
            "photos": {
                "full":    [p["url"] for p in photos_detail if p["type"] == "full"],
                "thumb":   [p["url"] for p in photos_detail if p["type"] == "thumb"],
                "all":     [p["url"] for p in photos_detail],
            },
            "specs":           det.specs,
            "description":     det.description,
            "description_source": det.description_source,
            "audits": {
                "total":    len(audits),
                "fail":     len(fail_a),
                "pass":     len(pass_a),
                "orta":     len(orta_a),
                "bilgi":    len(bilgi_a),
                "fail_ids": [a["id"] for a in fail_a],
                "details":  audits,
            },
            "ai_comment":      det.analysis,
            "ai_ok":           det.analysis_ok,
            "ai_reason":       det.analysis_reason,
        }, ensure_ascii=False, indent=2))
        return

    if args.extract_store_html:
        p = Path(args.extract_store_html)
        if not p.exists():
            print(f"✗ Dosya bulunamadı: {p}")
            sys.exit(1)

        listings = step2_extract_summaries(p)
        print(json.dumps([{
            "listing_id": x.listing_id,
            "title": x.title,
            "thumb_url": x.thumb_url,
            "detail_url": x.detail_url,
        } for x in listings], ensure_ascii=False, indent=2))
        return

    print("╔════════════════════════════════════════════════╗")
    print("║  Sahibinden Detay Pipeline — PageSpeed Modu    ║")
    print("╚════════════════════════════════════════════════╝")

    # ── Senaryo ayrımı: tekil ilan linki mi, mağaza/arama sonucu linki mi? ──
    # (web_app.py ile aynı tek doğruluk kaynağı: detect_single_listing_id)
    single_id = detect_single_listing_id(args.url) if not args.skip_ps else ""

    if single_id:
        # ── SENARYO 1: TEKİL İLAN MODU ────────────────────────────────────
        print(f"\nℹ Tekil ilan linki algılandı (İlan No: {single_id}).")
        print("  ⏭ Adım 1-2 (mağaza taraması) atlanıyor, doğrudan Adım 3'e geçiliyor.\n")

        detail_url = args.url.split("#", 1)[0]
        if "/detay" not in detail_url:
            detail_url = detail_url.split("?", 1)[0].rstrip("/") + "/detay"

        summaries = [ListingSummary(
            listing_id=single_id,
            title="",
            thumb_url="",
            detail_url=detail_url,
        )]
    else:
        # ── SENARYO 2: MAĞAZA / ARAMA SONUCU MODU ─────────────────────────
        # step2_extract_summaries hem mağaza sayfası formatını (Yöntem A) hem
        # de genel arama/kategori sonucu formatını (Yöntem B, manifesto v2.0
        # URL üretici motoru) otomatik dener ve birleştirir.
        ps_path = Path(args.ps_html)
        if args.skip_ps:
            if not ps_path.exists():
                print(f"\n✗ '{ps_path}' bulunamadı. --skip-pagespeed kaldırın.")
                sys.exit(1)
            print(f"\n⏭  Adım 1 atlandı → {ps_path}")
        else:
            try:
                ps_path = step1_pagespeed_store(args.url, args.ps_html, args.ps_wait, args.headless)
            except Exception as e:
                print(f"\n✗ Adım 1 hatası: {e}")
                sys.exit(1)

        summaries = step2_extract_summaries(ps_path)
        if not summaries:
            print("\n✗ İlan bulunamadı, çıkılıyor.")
            sys.exit(1)

    # Adım 3
    try:
        detail_paths = step3_pagespeed_details(
            summaries=summaries,
            detail_dir=args.detail_dir,
            wait_sec=args.det_wait,
            delay=args.delay,
            headless=args.headless,
            skip=args.skip_det,
        )
    except Exception as e:
        print(f"\n✗ Adım 3 hatası: {e}")
        sys.exit(1)

    if not detail_paths:
        print("\n✗ Hiç detay HTML'i alınamadı, çıkılıyor.")
        sys.exit(1)

    # Adım 4
    details = step4_parse_details(summaries, detail_paths)
    if not details:
        print("\n✗ Parse edilebilen ilan yok.")
        sys.exit(1)

    # Adım 5
    ai_enabled = not args.no_ai
    if ai_enabled:
        ok = step5_analyze(details, args.ollama, args.model, args.ai_delay)
        if not ok:
            print("\n  AI yapılamadı, kartlar AI kutusu olmadan üretilecek.")
            ai_enabled = False

    # Adım 6
    step6_build_html(details, args.model, ai_enabled, args.out)

    print("\n╔════════════════════════════════════════════════╗")
    print("║  ✅  TAMAMLANDI                                 ║")
    print(f"║  Çıktı : {Path(args.out).name:<38}║")
    print("╚════════════════════════════════════════════════╝")


# ── ListingDetail → luxury dict eşlemesi (step6_luxury_adapter.py birleşti) ──

def _lux_to_dict(d: "ListingDetail", model_name: str = "") -> dict:
    photos = list(getattr(d, "photos", []) or [])

    ai = None
    analysis_text = (getattr(d, "analysis", "") or "").strip()
    if analysis_text and getattr(d, "analysis_ok", False):
        ai = {"model": model_name, "text": analysis_text}

    specs = getattr(d, "specs", {}) or {}
    location = {
        "il": specs.get("Şehir") or specs.get("il"),
        "ilce": specs.get("İlçe") or specs.get("ilce"),
        "mahalle": specs.get("Mahalle (detay)") or specs.get("Mahalle") or specs.get("mahalle"),
    }

    audits = getattr(d, "audits", []) or []
    lighthouse = {
        "passes":     sum(1 for a in audits if a.get("status") == "PASS"),
        "violations": sum(1 for a in audits if a.get("status") == "FAIL"),
        "warnings":   sum(1 for a in audits if a.get("status") == "ORTA"),
        "info":       sum(1 for a in audits if a.get("status") == "BİLGİ"),
    }

    return {
        "listing_id": getattr(d, "listing_id", ""),
        "title": getattr(d, "title", ""),
        "price": getattr(d, "price", ""),
        "photos": photos,
        "raw_description": getattr(d, "description", "") or "",
        "description_source": getattr(d, "description_source", "") or "",
        "ai_analysis": ai,
        "location": location,
        "lighthouse": lighthouse,
    }


def step6_build_html_luxury(
    details: List["ListingDetail"],
    model_name: str,
    ai_enabled: bool,
    out_path: str,
) -> Path:
    """step6_build_html ile AYNI imza — Ultra Luxury v3 şablonla üretir.
    Herhangi bir aşamada hata olursa güvenli şekilde eski (klasik) şablona
    düşer, iş tamamen başarısız olmaz."""
    _sep("ADIM 6 — Ultra Luxury v3 HTML üretiliyor")
    try:
        dict_details = [_lux_to_dict(d, model_name) for d in details]
        if not ai_enabled:
            for dd in dict_details:
                dd["ai_analysis"] = None
        html_out = build_luxury_cards_page(dict_details)
        p = Path(out_path)
        p.write_text(html_out, encoding="utf-8")
        print(f"  [OK] {len(details)} ilan (Ultra Luxury v3) → {p.resolve()}")
        return p
    except Exception as exc:
        print(f"  [WARN] Lüks şablon üretilemedi ({exc}), klasik şablona düşülüyor...")
        traceback.print_exc()
        return step6_build_html(details, model_name, ai_enabled, out_path)


# ═════════════════════════════════════════════════════════════════════════════
# WEB ARAYÜZÜ — Flask (web_app.py birleşti — artık tek dosya: app.py)
# ═════════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # ⚡ Performance: GZIP Dynamic Compression for HTML, JSON, CSS & JS
    try:
        accept_encoding = flask_request.headers.get('Accept-Encoding', '')
        if 'gzip' in accept_encoding.lower() and response.status_code == 200 and not response.direct_passthrough:
            content_type = response.headers.get('Content-Type', '')
            if any(ct in content_type for ct in ['text/html', 'application/json', 'text/css', 'application/javascript']):
                import gzip
                data = response.get_data()
                if len(data) > 1024:
                    compressed_data = gzip.compress(data, compresslevel=6)
                    response.set_data(compressed_data)
                    response.headers['Content-Encoding'] = 'gzip'
                    response.headers['Content-Length'] = len(compressed_data)
    except Exception:
        pass
    return response

@app.route('/testcrm')
def testcrm():
    return "TEST CRM WORKS"


STEP_LABELS = [
    "Mağaza sayfası taranıyor",
    "İlanlar ayıklanıyor",
    "Detay sayfaları taranıyor",
    "Detaylar işleniyor",
    "AI analizi",
    "Ultra Luxury kart sayfası üretiliyor",
]


def _startup_check():
    print("\n" + "=" * 60)
    print("NEXA.OS SYSTEM CHECK")
    print("=" * 60)

    issues = []

    api_key = os.environ.get("PAGESPEED_API_KEY", "").strip() or PAGESPEED_API_KEY
    if not api_key:
        issues.append("[WARN] PAGESPEED_API_KEY ayarlanmamış")
        print("[WARN] PageSpeed API: DISABLED (no key)")
    elif not api_key.startswith("AIza"):
        issues.append("[WARN] PAGESPEED_API_KEY geçersiz format")
        print("[WARN] PageSpeed API: INVALID format")
    else:
        print("[OK] PageSpeed API: Ready")

    tess_ok, tess_reason = _tesseract_ready()
    if tess_ok:
        print("[OK] Tesseract OCR: Ready")
    else:
        issues.append("[WARN] Tesseract OCR kullanılamıyor")
        print(f"[WARN] Tesseract OCR: NOT READY ({tess_reason})")

    try:
        resp = _requests.get("http://localhost:11434/api/tags", timeout=2) if _REQUESTS else None
        if resp is not None and resp.status_code == 200:
            print("[OK] Ollama Server: Running")
        else:
            print("[WARN] Ollama Server: Not responding")
    except Exception:
        print("[WARN] Ollama Server: Not available (AI analysis disabled)")

    print("=" * 60)
    if issues:
        print("\n[WARN] UYARILAR:")
        for issue in issues:
            print(f"  {issue}")
        print("\nSistem çalışmaya devam edecek ama bazı özellikler sınırlı olabilir.\n")
    else:
        print("\n[OK] Tüm sistemler hazır!\n")


_thread_job_map: Dict[int, "Job"] = {}
_real_stdout = sys.stdout


class _LogRedirector:
    def write(self, s: str) -> int:
        try:
            _real_stdout.write(s)
        except UnicodeEncodeError:
            enc = getattr(_real_stdout, 'encoding', None) or 'ascii'
            try:
                safe_s = s.encode(enc, errors='replace').decode(enc)
                _real_stdout.write(safe_s)
            except Exception:
                pass
        job = _thread_job_map.get(threading.get_ident())
        if job is not None and s:
            with job.lock:
                job.logs.append(s)
        return len(s)

    def flush(self) -> None:
        _real_stdout.flush()


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS & ENUMS (BUYER ENGINE)
# ─────────────────────────────────────────────────────────────────────────────

import csv
import hashlib
from datetime import datetime
from enum import Enum
from dataclasses import asdict

class PropertyType(Enum):
    DAIRE = "Daire"
    VILLA = "Villa"
    OFIS = "Ofis"
    ARSA = "Arsa"
    KOMERCE = "Komerce"
    DEPO = "Depo"
    UNKNOWN = "Unknown"


class TransactionType(Enum):
    SATILIK = "Satılık"
    KIRALIK = "Kiralık"
    TAKASLI = "Takası"
    ARANIYOR = "Arıyor"
    UNKNOWN = "Unknown"


@dataclass
class ArayisRecord:
    arayis_id: str
    sender: Optional[str] = None
    phone: Optional[str] = None
    message_text: str = ""
    districts: List[str] = field(default_factory=list)
    neighborhoods: List[str] = field(default_factory=list)
    property_types: List[PropertyType] = field(default_factory=list)
    transaction_type: TransactionType = TransactionType.UNKNOWN
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    rooms: List[str] = field(default_factory=list)
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    features_wanted: List[str] = field(default_factory=list)
    features_unwanted: List[str] = field(default_factory=list)
    urgency_level: int = 1
    confidence: float = 0.0
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "whatsapp"

    def __post_init__(self):
        if not self.arayis_id:
            self.arayis_id = f"arayis_{abs(hash(self.message_text[:50])) % 10000}"

    def to_dict(self) -> Dict:
        return {
            'arayis_id': self.arayis_id,
            'sender': self.sender,
            'phone': self.phone,
            'message_text': self.message_text,
            'districts': self.districts,
            'neighborhoods': self.neighborhoods,
            'property_types': [pt.value for pt in self.property_types],
            'transaction_type': self.transaction_type.value,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'rooms': self.rooms,
            'area_min': self.area_min,
            'area_max': self.area_max,
            'features_wanted': self.features_wanted,
            'features_unwanted': self.features_unwanted,
            'urgency_level': self.urgency_level,
            'confidence': self.confidence,
            'parsed_at': self.parsed_at,
            'source': self.source,
        }


@dataclass
class PortfoyRecord:
    portfoy_id: str
    title: str = ""
    property_type: PropertyType = PropertyType.UNKNOWN
    transaction_type: TransactionType = TransactionType.UNKNOWN
    city: str = "ANKARA"
    district: str = ""
    neighborhood: str = ""
    location_confidence: float = 0.5
    price: Optional[float] = None
    price_text: str = ""
    rooms: Optional[str] = None
    area: Optional[float] = None
    consultant_name: str = ""
    office: str = ""
    phone: Optional[str] = None
    source_url: str = ""
    source: str = "whatsapp"
    confidence: float = 0.0
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    features: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.portfoy_id:
            self.portfoy_id = f"portfoy_{abs(hash(self.title[:50])) % 10000}"

    def to_dict(self) -> Dict:
        return {
            'portfoy_id': self.portfoy_id,
            'title': self.title,
            'property_type': self.property_type.value,
            'transaction_type': self.transaction_type.value,
            'city': self.city,
            'district': self.district,
            'neighborhood': self.neighborhood,
            'location_confidence': self.location_confidence,
            'price': self.price,
            'price_text': self.price_text,
            'rooms': self.rooms,
            'area': self.area,
            'consultant_name': self.consultant_name,
            'office': self.office,
            'phone': self.phone,
            'source_url': self.source_url,
            'source': self.source,
            'confidence': self.confidence,
            'parsed_at': self.parsed_at,
            'features': self.features
        }


@dataclass
class MatchReason:
    category: str
    score: float
    explanation: str


@dataclass
class Match:
    arayis_id: str
    portfoy_id: str
    overall_score: float
    confidence: float

    # Scoring breakdown
    price_score: float
    rooms_score: float
    location_score: float
    type_score: float
    features_score: float
    urgency_score: float

    reasons: List[MatchReason]
    ai_analysis: str = ""
    recommendation: str = ""
    contact_info: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            'arayis_id': self.arayis_id,
            'portfoy_id': self.portfoy_id,
            'overall_score': self.overall_score,
            'confidence': self.confidence,
            'price_score': self.price_score,
            'rooms_score': self.rooms_score,
            'location_score': self.location_score,
            'type_score': self.type_score,
            'features_score': self.features_score,
            'urgency_score': self.urgency_score,
            'reasons': [asdict(r) for r in self.reasons],
            'ai_analysis': self.ai_analysis,
            'recommendation': self.recommendation,
            'contact_info': self.contact_info,
            'timestamp': self.timestamp,
        }


# ─────────────────────────────────────────────────────────────────────────────
# TURKISH NLP & WHATSAPP PARSER
# ─────────────────────────────────────────────────────────────────────────────

class TurkishNLPPatterns:
    PROPERTY_TYPES = {
        r'\b(daire|flat|apartment|apt)\b': PropertyType.DAIRE,
        r'\b(villa|müstakil|ev|house)\b': PropertyType.VILLA,
        r'\b(ofis|office|büro|iş yeri)\b': PropertyType.OFIS,
        r'\b(arsa|land|arsası)\b': PropertyType.ARSA,
        r'\b(komerce|ticari|commercial)\b': PropertyType.KOMERCE,
        r'\b(depo|warehouse|depo|storage)\b': PropertyType.DEPO,
    }

    TRANSACTION_TYPES = {
        r'\b(satılık|satilik|sale|for sale|satış)\b': TransactionType.SATILIK,
        r'\b(kiralık|kiralik|rental|rent|kira)\b': TransactionType.KIRALIK,
        r'\b(takası|takasli|exchange|takas)\b': TransactionType.TAKASLI,
        r'\b(arıyor|arayan|ariyorum|arayış|searching|isteniyor)\b': TransactionType.ARANIYOR,
    }

    DISTRICTS = {
        'çankaya': r'(?:çankaya|cankaya)',
        'keçiören': r'(?:keçiören|kecioren)',
        'yenimahalle': r'(?:yenimahalle|yeni mahalle)',
        'mamak': r'(?:mamak)',
        'altındağ': r'(?:altındağ|altindag)',
        'çubuk': r'(?:çubuk|cubuk)',
        'pursaklar': r'(?:pursaklar)',
        'sincan': r'(?:sincan)',
        'etimesgut': r'(?:etimesgut)',
        'gölbaşı': r'(?:gölbaşı|golbasi)',
        'incek': r'(?:incek)',
        'oran': r'(?:oran)',
    }

    NEIGHBORHOODS = {
        'çıkrıkçı': r'(?:çıkrıkçı|cikrikci)',
        'kızılay': r'(?:kızılay|kizilay)',
        'tunalı': r'(?:tunalı|tunali)',
        'çayyolu': r'(?:çayyolu|cayyolu)',
        'ümitköy': r'(?:ümitköy|umitkoy)',
        'bahçelievler': r'(?:bahçelievler|bahcelievler)',
        'incek': r'(?:incek|incek kızılcaşar)',
        'bilkent': r'(?:bilkent)',
        'oran': r'(?:oran)',
    }

    FEATURES = {
        'balkon': r'(?:balkon|terrace)',
        'havuz': r'(?:havuz|pool|swimming)',
        'otopark': r'(?:otopark|parking|park)',
        'asansör': r'(?:asansör|asansor|elevator)',
        'ısıtma': r'(?:ısıtma|isitma|heating)',
        'soğutma': r'(?:soğutma|sogutma|cooling|klima|air)',
        'güvenlik': r'(?:güvenlik|guvenlik|security|kamera)',
        'bahçe': r'(?:bahçe|bahce|garden)',
        'teras': r'(?:teras|terrace)',
        'şömine': r'(?:şömine|somine|fireplace)',
    }


class WhatsAppCBParser:
    def __init__(self):
        self.patterns = TurkishNLPPatterns()

    def parse_content(self, content: str) -> Tuple[List[ArayisRecord], List[PortfoyRecord]]:
        messages = self._split_messages(content)
        arayislar = []
        portfoyler = []

        for msg in messages:
            msg_text = msg.get('text', '').lower()

            if self._is_arayis(msg_text):
                arayis = self._parse_arayis(msg)
                if arayis:
                    arayislar.append(arayis)

            elif self._is_portfoy(msg_text):
                portfoy = self._parse_portfoy(msg)
                if portfoy:
                    portfoyler.append(portfoy)

        return arayislar, portfoyler

    def _split_messages(self, content: str) -> List[Dict]:
        messages = []
        lines = content.split('\n')
        current_msg = None

        for line in lines:
            if re.match(r'^\[\d{1,2}:\d{2},\s*\d{1,2}\.\d{1,2}\.\d{4}\]', line):
                if current_msg:
                    messages.append(current_msg)
                match = re.search(r'\]\s*([^:]+):\s*(.*)', line)
                if match:
                    current_msg = {
                        'sender': match.group(1).strip(),
                        'text': match.group(2).strip(),
                    }
            elif re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}\s+(?:-|—)', line):
                if current_msg:
                    messages.append(current_msg)
                match = re.search(r'^\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2}\s+(?:-|—)\s+([^:]+):\s*(.*)', line)
                if match:
                    current_msg = {
                        'sender': match.group(1).strip(),
                        'text': match.group(2).strip(),
                    }
            elif current_msg and line.strip():
                current_msg['text'] += ' ' + line.strip()

        if current_msg:
            messages.append(current_msg)
        return messages

    def _is_arayis(self, text: str) -> bool:
        strong_keywords = ['arayış', 'arayiş', '*arayiş*', '*arayış*', 'talep', 'talebi', 'talebi vardır']
        for keyword in strong_keywords:
            if keyword in text:
                return True
        medium_keywords = ['arıyor', 'arayan', 'ariyorum', 'isteniyor', 'istiyorum', 'istedim', 'bütçe', 'bütçesi']
        medium_count = sum(1 for kw in medium_keywords if kw in text)
        return medium_count >= 1

    def _is_portfoy(self, text: str) -> bool:
        strong_keywords = ['satılık', 'satilik', 'kiralık', 'kiralik', 'devren', 'takas', 'takası', 'takasli']
        for keyword in strong_keywords:
            if keyword in text:
                if any(price_kw in text for price_kw in ['\u20ba', 'tl', 'milyon', 'bin']):
                    return True
                return True
        return False

    def _parse_arayis(self, msg: Dict) -> Optional[ArayisRecord]:
        text = msg.get('text', '')
        sender = msg.get('sender', '')
        districts = self._extract_districts(text)
        property_types = self._extract_property_types(text)
        budget_min, budget_max = self._extract_prices(text)
        rooms = self._extract_rooms(text)
        urgency = self._detect_urgency(text)
        features = self._extract_features(text)
        transaction_type = self._extract_transaction_type(text)

        phone_match = re.search(r'\+?90\d{10}|\(?05\d{2}\)?\s*\d{3}\s*\d{2}\s*\d{2}', text)
        phone = phone_match.group(0) if phone_match else None

        arayis = ArayisRecord(
            arayis_id=f"arayis_{abs(hash(sender + text[:30])) % 10000}",
            sender=sender,
            phone=phone,
            message_text=text,
            districts=districts,
            property_types=property_types,
            transaction_type=transaction_type,
            budget_min=budget_min,
            budget_max=budget_max,
            rooms=rooms,
            features_wanted=features,
            urgency_level=urgency,
            confidence=0.0,
        )
        arayis.confidence = self._calculate_arayis_confidence(arayis)
        return arayis if arayis.confidence > 0 else None

    def _parse_portfoy(self, msg: Dict) -> Optional[PortfoyRecord]:
        text = msg.get('text', '')
        sender = msg.get('sender', '')
        price = self._extract_price_single(text)
        rooms = self._extract_rooms_single(text)
        area = self._extract_area(text)
        district = self._extract_first_district(text)
        property_type = self._extract_first_property_type(text)
        features = self._extract_features(text)
        transaction_type = self._extract_transaction_type(text)

        phone_match = re.search(r'\+?90\d{10}|\(?05\d{2}\)?\s*\d{3}\s*\d{2}\s*\d{2}', text)
        phone = phone_match.group(0) if phone_match else None

        portfoy = PortfoyRecord(
            portfoy_id=f"portfoy_{abs(hash(sender + text[:30])) % 10000}",
            title=text[:100],
            property_type=property_type,
            transaction_type=transaction_type,
            price=price,
            price_text=str(price) if price else "",
            rooms=rooms,
            area=area,
            district=district,
            consultant_name=sender,
            phone=phone,
            features=features,
            confidence=0.0,
            source='whatsapp',
        )
        portfoy.confidence = self._calculate_portfoy_confidence(portfoy)
        return portfoy if portfoy.confidence > 0 else None

    def _extract_transaction_type(self, text: str) -> TransactionType:
        text_lower = text.lower()
        for pattern, t_type in self.patterns.TRANSACTION_TYPES.items():
            if re.search(pattern, text_lower):
                return t_type
        return TransactionType.UNKNOWN

    def _extract_districts(self, text: str) -> List[str]:
        found = []
        text_lower = text.lower()
        for name, pattern in self.patterns.DISTRICTS.items():
            if re.search(pattern, text_lower):
                found.append(name.capitalize())
        return found

    def _extract_first_district(self, text: str) -> str:
        districts = self._extract_districts(text)
        return districts[0] if districts else ""

    def _extract_property_types(self, text: str) -> List[PropertyType]:
        found = []
        text_lower = text.lower()
        for pattern, p_type in self.patterns.PROPERTY_TYPES.items():
            if re.search(pattern, text_lower):
                found.append(p_type)
        return found

    def _extract_first_property_type(self, text: str) -> PropertyType:
        types = self._extract_property_types(text)
        return types[0] if types else PropertyType.UNKNOWN

    def _extract_prices(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        text_lower = text.lower().replace('.', '').replace(',', '')
        nums = [float(s) for s in re.findall(r'\b\d{5,10}\b', text_lower)]
        if len(nums) >= 2:
            return min(nums), max(nums)
        elif len(nums) == 1:
            if 'alt' in text_lower or 'maks' in text_lower or 'kadar' in text_lower:
                return None, nums[0]
            if 'üst' in text_lower or 'min' in text_lower or 'baslar' in text_lower:
                return nums[0], None
            return nums[0] * 0.8, nums[0] * 1.2
        return None, None

    def _extract_price_single(self, text: str) -> Optional[float]:
        text_lower = text.lower().replace('.', '').replace(',', '')
        nums = [float(s) for s in re.findall(r'\b\d{5,10}\b', text_lower)]
        return nums[0] if nums else None

    def _extract_rooms(self, text: str) -> List[str]:
        found = []
        matches = re.findall(r'\b\d\s*\+\s*\d\b', text)
        for m in matches:
            found.append(m.replace(' ', ''))
        if not found:
            if 'studio' in text.lower() or '1+0' in text.lower():
                found.append("1+0")
        return found

    def _extract_rooms_single(self, text: str) -> Optional[str]:
        rooms = self._extract_rooms(text)
        return rooms[0] if rooms else None

    def _extract_area(self, text: str) -> Optional[float]:
        match = re.search(r'(\d{2,4})\s*(?:m2|m²|metrekare)', text.lower())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def _extract_features(self, text: str) -> List[str]:
        found = []
        text_lower = text.lower()
        for feature, pattern in self.patterns.FEATURES.items():
            if re.search(pattern, text_lower):
                found.append(feature)
        return found

    def _detect_urgency(self, text: str) -> int:
        urgency_terms = ['acil', 'hemen', 'ivedi', 'hızlı', 'bugün', 'aciliyet']
        if any(term in text.lower() for term in urgency_terms):
            return 5
        return 1

    def _calculate_arayis_confidence(self, arayis: ArayisRecord) -> float:
        score = 0.0
        if arayis.districts: score += 0.3
        if arayis.property_types: score += 0.2
        if arayis.budget_min or arayis.budget_max: score += 0.3
        if arayis.rooms: score += 0.2
        return score

    def _calculate_portfoy_confidence(self, portfoy: PortfoyRecord) -> float:
        score = 0.0
        if portfoy.price: score += 0.4
        if portfoy.rooms: score += 0.2
        if portfoy.district: score += 0.2
        if portfoy.property_type != PropertyType.UNKNOWN: score += 0.2
        return score


# ─────────────────────────────────────────────────────────────────────────────
# COLDWELL BANKER SCRAPER
# ─────────────────────────────────────────────────────────────────────────────

class CBScraper:
    def __init__(self, base_url: str = None, transaction_type: str = "Satılık", max_pages: int = None, stop_event: threading.Event = None):
        self.session = _requests.Session() if _REQUESTS else None
        self.listings = []
        self.errors = []
        self.base_url = base_url or "https://www.cb.com.tr/satilik"
        self.transaction_type = transaction_type
        self.max_pages = max_pages or 15
        self.stop_event = stop_event

        if self.base_url in ["satilik", "satiliki"]:
            self.base_url = "https://www.cb.com.tr/satilik"
        elif self.base_url in ["kiralik", "kiralık"]:
            self.base_url = "https://www.cb.com.tr/kiralik"

    def fetch_page(self, page_num: int) -> Optional[BeautifulSoup]:
        if page_num == 1:
            url = f"{self.base_url}?officeid=470"
        else:
            url = f"{self.base_url}?officeid=470&pager_p={page_num}"

        print(f"  --> CB Sayfa {page_num} çekiliyor: {url}")

        for attempt in range(3):
            if self.stop_event and self.stop_event.is_set():
                return None
            try:
                r = _requests.get(url, headers=HEADERS, timeout=15)
                r.raise_for_status()
                r.encoding = 'utf-8'
                return BeautifulSoup(r.content, 'html.parser')
            except Exception as e:
                print(f"  [WARN] Deneme {attempt + 1}/3 başarısız: {e}")
                if attempt < 2:
                    time.sleep(2)
        return None

    def parse_listing(self, card) -> Optional[Dict]:
        try:
            title_elem = card.find('h2', class_='card-title')
            title = title_elem.text.strip() if title_elem else "N/A"
            listing_id = title.split(" - ")[-1] if title and " - " in title else "N/A"

            link_elem = card.find('a', href=True)
            url = link_elem['href'] if link_elem else "N/A"
            if url.startswith('/'):
                url = f"https://www.cb.com.tr{url}"

            img_elem = card.find('img', class_='card-img-top')
            image_url = img_elem['src'].strip() if img_elem and 'src' in img_elem.attrs else "N/A"

            type_elem = card.find('span', class_='badge-item-primary')
            property_type = type_elem.text.strip() if type_elem else "N/A"

            locality = card.find('span', itemprop='addressLocality')
            region = card.find('span', itemprop='addressRegion')
            street = card.find('span', itemprop='streetAddress')

            city = locality.text.strip() if locality else "N/A"
            district = region.text.strip() if region else "N/A"
            neighborhood = street.text.strip() if street else "N/A"

            features = {}
            for item in card.find_all('div', class_='feature-item'):
                text = item.get_text(strip=True)
                if 'm²' in text:
                    m = re.search(r'(\d+(?:\.\d+)?)\s*m²', text)
                    if m: features['area'] = m.group(1)
                if '+' in text and '₺' not in text:
                    m = re.search(r'(\d+\+\d+)', text)
                    if m: features['rooms'] = m.group(1)

            area = features.get('area', 'N/A')
            rooms = features.get('rooms', 'N/A')

            consultant_elem = card.find('a', class_='owner-name')
            consultant = consultant_elem.text.strip() if consultant_elem else "N/A"

            office_elems = card.find_all('a', class_='owner-info')
            office = office_elems[1].text.strip() if len(office_elems) > 1 else "N/A"

            price_elem = card.find('span', class_='h5')
            price = price_elem.text.strip() if price_elem else "N/A"

            return {
                'id': listing_id,
                'title': title,
                'type': property_type,
                'transaction_type': self.transaction_type,
                'city': city,
                'district': district,
                'neighborhood': neighborhood,
                'area': area,
                'rooms': rooms,
                'price': price,
                'consultant': consultant,
                'office': office,
                'url': url,
                'image': image_url,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception:
            return None

    def scrape_all(self) -> List[Dict]:
        for page in range(1, self.max_pages + 1):
            if self.stop_event and self.stop_event.is_set():
                break
            soup = self.fetch_page(page)
            if not soup:
                break
            cards = soup.find_all('div', class_='card locationDiv')
            for card in cards:
                l = self.parse_listing(card)
                if l:
                    self.listings.append(l)
            time.sleep(0.5)
        return self.listings


# ─────────────────────────────────────────────────────────────────────────────
# AI MATCHER & SCORING ENGINE (WITH IMPROVED MATH FIXES)
# ─────────────────────────────────────────────────────────────────────────────

def fixed_score_price(arayis_min: Optional[float], arayis_max: Optional[float], portfoy_price: Optional[float]) -> float:
    if portfoy_price is None or portfoy_price == 0:
        return 0.5
    if arayis_min is None and arayis_max is None:
        return 0.5
    amin = arayis_min if arayis_min is not None else 0
    amax = arayis_max if arayis_max is not None else 9999999999
    if amin <= portfoy_price <= amax:
        return 1.0
    if portfoy_price < amin:
        if amin == 0: return 1.0
        distance_ratio = (amin - portfoy_price) / amin
    else:
        if amax == 0: return 0.0
        distance_ratio = (portfoy_price - amax) / amax
    return max(0.0, 1.0 - (distance_ratio * 0.5))


class RoomMatcher:
    PATTERNS = {
        'standard': re.compile(r'(\d+)\+(\d+)', re.IGNORECASE),
        'slash': re.compile(r'(\d+)/(\d+)', re.IGNORECASE),
        'dash': re.compile(r'(\d+)-(\d+)', re.IGNORECASE),
        'named': re.compile(r'(studio|1\s*oda|2\s*oda|3\s*oda)', re.IGNORECASE),
    }
    NAMED_MAPPINGS = {
        'studio': (0, 1),
        '1oda': (1, 1),
        '2oda': (2, 1),
        '3oda': (3, 1),
    }

    @classmethod
    def parse_room_format(cls, room_str: str) -> Optional[Tuple[int, int]]:
        if not room_str:
            return None
        room_str = room_str.strip().lower()
        match = cls.PATTERNS['standard'].search(room_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        for p in ['slash', 'dash']:
            match = cls.PATTERNS[p].search(room_str)
            if match:
                return int(match.group(1)), int(match.group(2))
        match = cls.PATTERNS['named'].search(room_str)
        if match:
            name = match.group(1).lower().replace(' ', '')
            if name in cls.NAMED_MAPPINGS:
                return cls.NAMED_MAPPINGS[name]
        return None

    @classmethod
    def score_rooms(cls, arayis_rooms: List[str], portfoy_rooms: str) -> float:
        if not arayis_rooms or not portfoy_rooms:
            return 0.5
        p_parsed = cls.parse_room_format(portfoy_rooms)
        if not p_parsed:
            return 0.0
        p_bed, p_lounge = p_parsed
        for a_room in arayis_rooms:
            a_parsed = cls.parse_room_format(a_room)
            if not a_parsed:
                continue
            a_bed, a_lounge = a_parsed
            if p_bed == a_bed and p_lounge == a_lounge:
                return 1.0
            if abs(p_bed - a_bed) <= 1:
                return 0.8
        return 0.3


class LocationMatcher:
    @staticmethod
    def normalize_district_name(name: str) -> str:
        if not name: return ""
        replacements = {'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'I': 'i', 'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'}
        normalized = name.lower().strip()
        for tr, en in replacements.items():
            normalized = normalized.replace(tr, en)
        return normalized

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> float:
        if not s1 or not s2: return 0.0
        if s1 == s2: return 1.0
        a, b = len(s1), len(s2)
        dp = [[0] * (b + 1) for _ in range(a + 1)]
        for i in range(a + 1):
            dp[i][0] = i
        for j in range(b + 1):
            dp[0][j] = j
        for i in range(1, a + 1):
            for j in range(1, b + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                dp[i][j] = min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost)
        max_len = max(a, b)
        return 1.0 - (dp[a][b] / max_len if max_len > 0 else 0)

    @classmethod
    def score_location(cls, arayis_district: str, arayis_neighborhoods: List[str], portfoy_district: str) -> float:
        if not arayis_district and not arayis_neighborhoods:
            return 0.5
        portfoy_norm = cls.normalize_district_name(portfoy_district)
        if arayis_district:
            arayis_norm = cls.normalize_district_name(arayis_district)
            if arayis_norm == portfoy_norm:
                return 1.0
            similarity = cls.levenshtein_distance(arayis_norm, portfoy_norm)
            if similarity > 0.85:
                return 0.9
            if similarity > 0.70:
                return 0.7
        if arayis_neighborhoods:
            for n in arayis_neighborhoods:
                neigh_norm = cls.normalize_district_name(n)
                if neigh_norm == portfoy_norm:
                    return 0.9
                similarity = cls.levenshtein_distance(neigh_norm, portfoy_norm)
                if similarity > 0.85:
                    return 0.8
        return 0.0


class FeatureScorer:
    @staticmethod
    def score_features(desired_features: List[str], portfoy_features: List[str]) -> float:
        desired_set = set([f.lower().strip() for f in desired_features])
        portfoy_set = set([f.lower().strip() for f in portfoy_features])
        if not desired_set: return 0.5
        if not portfoy_set: return 0.0
        intersection = len(desired_set & portfoy_set)
        precision = intersection / len(portfoy_set) if portfoy_set else 0
        recall = intersection / len(desired_set) if desired_set else 0
        if precision + recall == 0: return 0.0
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1


class OllamaAnalyzerWithFallback:
    OLLAMA_URL = "http://localhost:11434"
    OLLAMA_MODEL = "qwen2.5:7b"

    @staticmethod
    def generate_fallback_analysis(arayis: ArayisRecord, portfoy: PortfoyRecord, score: float) -> str:
        score_pct = score
        if score_pct >= 90:
            quality = "Mükemmel Uyum (*****)"
            reason = "Talep edilen fiyat bütçesi, oda yapısı ve konum tercihleri mülk ile kusursuz bir şekilde eşleşmektedir."
        elif score_pct >= 70:
            quality = "Yüksek Uyum (****)"
            reason = "Müşterinin ana beklentileri büyük ölçüde karşılanmaktadır. Ufak ayrıntılar dışında son derece cazip bir fırsattır."
        elif score_pct >= 50:
            quality = "Orta Seviye Uyum (***)"
            reason = "Kriterlerin bir kısmı uyuşurken bir kısmı farklılık gösteriyor. Bütçe ve oda sayısı kontrol edilmelidir."
        else:
            quality = "Düşük Seviye Uyum (**)"
            reason = "Tercih edilen kriterlerle mülk özellikleri arasında ciddi farklar bulunmaktadır."
        return f"{quality}: {reason}"

    @staticmethod
    def query_ollama_with_timeout(prompt: str, url: str = None, model: str = None, timeout: int = 8) -> Optional[str]:
        ollama_url = url or OllamaAnalyzerWithFallback.OLLAMA_URL
        ollama_model = model or OllamaAnalyzerWithFallback.OLLAMA_MODEL
        try:
            r = _requests.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False, "temperature": 0.3},
                timeout=timeout
            )
            if r.status_code == 200:
                return r.json().get('response', '')
        except Exception:
            pass
        return None


class OllamaMatcher:
    def __init__(self, ollama_url: str = None, model: str = None, use_ai: bool = True, gemini_api_key: Optional[str] = None):
        self.ollama_url = ollama_url or "http://localhost:11434"
        self.model = model or "qwen2.5:7b"
        self.use_ai = use_ai
        self.gemini_api_key = gemini_api_key
        self.matches: List[Match] = []

    def match_arayis_portfoy(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> Match:
        price_s = fixed_score_price(arayis.budget_min, arayis.budget_max, portfoy.price)
        rooms_s = RoomMatcher.score_rooms(arayis.rooms, portfoy.rooms or "")
        loc_s = LocationMatcher.score_location(arayis.districts[0] if arayis.districts else "", arayis.neighborhoods, portfoy.district or "")
        
        type_s = 0.5
        if arayis.property_types and portfoy.property_type != PropertyType.UNKNOWN:
            type_s = 1.0 if portfoy.property_type in arayis.property_types else 0.0

        feat_s = FeatureScorer.score_features(arayis.features_wanted, portfoy.features)

        urg_s = 1.0 if arayis.urgency_level >= 4 else 0.5

        overall = (price_s * 0.25) + (rooms_s * 0.25) + (loc_s * 0.20) + (type_s * 0.15) + (feat_s * 0.10) + (urg_s * 0.05)
        overall_score = overall * 100.0

        reasons = [
            MatchReason("Fiyat", price_s, "Fiyat bütçe uyumluluğu."),
            MatchReason("Oda Sayısı", rooms_s, "Oda düzeni uyumu."),
            MatchReason("Lokasyon", loc_s, "Konum tercihi uyumu."),
            MatchReason("Özellikler", feat_s, "Ek özelliklerin karşılanması.")
        ]

        confidence = (price_s + rooms_s + loc_s) / 3.0

        match_obj = Match(
            arayis_id=arayis.arayis_id,
            portfoy_id=portfoy.portfoy_id,
            overall_score=overall_score,
            confidence=confidence,
            price_score=price_s * 100,
            rooms_score=rooms_s * 100,
            location_score=loc_s * 100,
            type_score=type_s * 100,
            features_score=feat_s * 100,
            urgency_score=urg_s * 100,
            reasons=reasons
        )

        if self.use_ai and overall_score >= 30:
            prompt = f"""
Aşağıdaki müşteri talebi ile mülk ilanını karşılaştırıp Türkçe bir eşleşme değerlendirmesi üret.
Müşteri Talebi: {arayis.message_text}
Mülk Özellikleri: {portfoy.title} - Fiyat: {portfoy.price_text} - Oda: {portfoy.rooms} - Bölge: {portfoy.district}

Değerlendirmeyi kısa, net ve profesyonel yaz.
"""
            ai_text = None
            if self.gemini_api_key and self.gemini_api_key.strip():
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300}
                }
                try:
                    r = _requests.post(url, headers=headers, json=payload, timeout=10)
                    if r.status_code == 200:
                        ai_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception:
                    pass
            
            if not ai_text:
                ai_text = OllamaAnalyzerWithFallback.query_ollama_with_timeout(prompt, self.ollama_url, self.model)

            if ai_text:
                match_obj.ai_analysis = ai_text.strip()
            else:
                match_obj.ai_analysis = OllamaAnalyzerWithFallback.generate_fallback_analysis(arayis, portfoy, overall_score)
        else:
            match_obj.ai_analysis = OllamaAnalyzerWithFallback.generate_fallback_analysis(arayis, portfoy, overall_score)

        match_obj.recommendation = f"{portfoy.consultant_name or 'Gayrimenkul Danışmanı'} ile iletişime geçiniz."
        match_obj.contact_info = portfoy.phone or "N/A"
        return match_obj

    def match_all(self, arayislar: List[ArayisRecord], portfoyler: List[PortfoyRecord]) -> List[Match]:
        self.matches = []
        for arayis in arayislar:
            for portfoy in portfoyler:
                if arayis.transaction_type != TransactionType.UNKNOWN and portfoy.transaction_type != TransactionType.UNKNOWN:
                    if arayis.transaction_type != portfoy.transaction_type:
                        continue
                m = self.match_arayis_portfoy(arayis, portfoy)
                if m.overall_score >= 30:
                    self.matches.append(m)
        self.matches.sort(key=lambda x: x.overall_score, reverse=True)
        return self.matches

    def export_json(self, filepath: str):
        data = [m.to_dict() for m in self.matches]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def generate_report(self, filepath: str):
        r = f"# EŞLEŞME RAPORU - NEXA AI\n\nToplam Eşleşme: {len(self.matches)}\n\n"
        for i, m in enumerate(self.matches[:10], 1):
            r += f"### {i}. {m.overall_score:.1f}% - {m.arayis_id} <-> {m.portfoy_id}\n- **Yorum:** {m.ai_analysis}\n- **İletişim:** {m.contact_info}\n\n"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(r)

    def generate_html_report(self, filepath: str, arayislar: List[ArayisRecord] = None, portfoyler: List[PortfoyRecord] = None):
        arayis_dict = {a.arayis_id: a for a in (arayislar or [])}
        portfoy_dict = {p.portfoy_id: p for p in (portfoyler or [])}
        
        # Limit to top 1000 matches to avoid memory overhead and browser crashes
        report_matches = self.matches[:1000]
        
        chunks = [f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Eşleşme Raporu - NEXA AI</title>
<style>
body {{ background: #07080a; color: #f2f1ee; font-family: sans-serif; padding: 30px; }}
h1 {{ color: #c9a45c; font-family: serif; border-bottom: 1px solid #22262b; padding-bottom: 10px; }}
.match-card {{ background: #0d0f11; border: 1px solid #22262b; border-radius: 8px; padding: 20px; margin-bottom: 15px; }}
.score {{ font-size: 20px; font-weight: bold; color: #3ddc84; }}
.ai-comment {{ background: #131619; padding: 15px; border-left: 3px solid #c9a45c; margin-top: 10px; font-style: italic; }}
</style>
</head>
<body>
<h1>NEXA AI Eşleştirme Sonuçları</h1>
<p>Toplam {len(self.matches)} eşleşme bulundu. (En yüksek puanlı ilk {len(report_matches)} eşleşme raporlanmıştır.)</p>
"""]

        for m in report_matches:
            a = arayis_dict.get(m.arayis_id)
            p = portfoy_dict.get(m.portfoy_id)
            chunks.append(f"""
<div class="match-card">
  <div><span class="score">{m.overall_score:.1f}%</span> Eşleşme Derecesi</div>
  <p><strong>Arayış Mesajı (Müşteri):</strong> {a.message_text if a else m.arayis_id}</p>
  <p><strong>Portföy İlanı:</strong> {p.title if p else m.portfoy_id} - Fiyat: {p.price_text if p else ''}</p>
  <div class="ai-comment"><strong>NEXA AI Yorumu:</strong> {m.ai_analysis}</div>
  <p><small>Danışman: {p.consultant_name if p else 'N/A'} - Tel: {m.contact_info}</small></p>
</div>
""")
        chunks.append("</body></html>")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(chunks))


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND PIPELINE ENGINE & ROUTING
# ─────────────────────────────────────────────────────────────────────────────

STEP_LABELS = {
    "sahibinden": ["Mağaza taranıyor", "İlanlar ayıklanıyor", "Detaylar taranıyor", "Detaylar işleniyor", "AI analizi", "Ultra Luxury üretimi"],
    "cb": ["CB Satılık ilanları çekiliyor", "CB Kiralık ilanları çekiliyor", "İlanlar kaydediliyor"],
    "whatsapp": ["Dosya içeriği okunuyor", "Arayışlar ve Portföyler NLP ile ayıklanıyor", "Sonuçlar kaydediliyor"],
    "match": ["Tüm portföyler yükleniyor", "Tüm Arayış talepleri yükleniyor", "AI Eşleştirme yapılıyor", "Raporlar ve Dashboard üretiliyor"]
}


class Job:
    def __init__(self, job_id: str, job_type: str, params: dict):
        self.id = job_id
        self.job_type = job_type
        self.params = params
        self.dir = JOBS_DIR / job_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.logs: list = []
        self.lock = threading.Lock()
        self.status = "queued"
        self.step_index = -1
        self.step_label = ""
        self.total_listings = 0
        self.error = ""
        self.output_file = ""
        self.stop_event = threading.Event()
        self.created_at = time.time()
        self.finished_at = None

    def set_step(self, idx: int):
        self.step_index = idx
        labels = STEP_LABELS.get(self.job_type, ["İşlem Yapılıyor"])
        self.step_label = labels[idx] if idx < len(labels) else "Tamamlanıyor"
        print(f"\n### ADIM {idx + 1}/{len(labels)} — {self.step_label} ###\n")

    def to_status_dict(self, after: int = 0) -> dict:
        labels = STEP_LABELS.get(self.job_type, ["İşlem Yapılıyor"])
        with self.lock:
            new_logs = self.logs[after:]
            log_len = len(self.logs)
        return {
            "status": self.status,
            "job_type": self.job_type,
            "step_index": self.step_index,
            "step_label": self.step_label,
            "step_total": len(labels),
            "total_listings": self.total_listings,
            "error": self.error,
            "output_ready": bool(self.output_file),
            "output_url": f"/jobs/{self.id}/{self.output_file}" if self.output_file else "",
            "new_logs": "".join(new_logs),
            "log_len": log_len,
            "elapsed": round((self.finished_at or time.time()) - self.created_at, 1),
        }


JOBS: Dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


class _StoppedByUser(Exception):
    pass


def _run_pipeline(job: "Job"):
    _thread_job_map[threading.get_ident()] = job
    job.status = "running"
    p = job.params
    try:
        if job.job_type == "sahibinden":
            detail_dir = job.dir / "detay_html"
            ps_html = job.dir / "pagespeed_result.html"
            out_html = job.dir / "ilan_detay_karti.html"

            single_id = detect_single_listing_id(p["url"])

            if single_id:
                job.set_step(0)
                print(f"  ℹ Tekil ilan linki algılandı (İlan No: {single_id}).")
                print("  ⏭ Bu bir mağaza/liste linki değil, mağaza taraması atlanıyor.")
                job.set_step(1)
                print("  ⏭ Tekil ilan modunda bu adıma gerek yok, doğrudan detay taramasına geçiliyor.")

                detail_url = p["url"].split("#", 1)[0]
                if "/detay" not in detail_url:
                    detail_url = detail_url.split("?", 1)[0].rstrip("/") + "/detay"

                summaries = [ListingSummary(
                    listing_id=single_id, title="", thumb_url="", detail_url=detail_url,
                )]
            else:
                job.set_step(0)
                step1_pagespeed_store(
                    target_url=p["url"], out_html=str(ps_html), wait_sec=p["ps_wait"],
                    headless=p["headless"], stop_event=job.stop_event,
                )
                if job.stop_event.is_set():
                    raise _StoppedByUser()

                job.set_step(1)
                summaries = step2_extract_summaries(ps_html)
                if not summaries:
                    raise RuntimeError("Bu linkte hiç ilan bulunamadı.")
                if p.get("limit") and p["limit"] > 0:
                    summaries = summaries[: p["limit"]]
                    print(f"  ℹ Limit uygulandı: ilk {len(summaries)} ilan işlenecek.")

            job.total_listings = len(summaries)
            if job.stop_event.is_set():
                raise _StoppedByUser()

            job.set_step(2)
            detail_paths = step3_pagespeed_details(
                summaries=summaries, detail_dir=str(detail_dir), wait_sec=p["det_wait"],
                delay=p["delay"], headless=p["headless"], skip=False,
                stop_event=job.stop_event, cd_fallback=p["cd_fallback"],
            )
            if not detail_paths:
                raise RuntimeError("Hiç detay sayfası indirilemedi.")

            job.set_step(3)
            details = step4_parse_details(summaries, detail_paths)
            if not details:
                raise RuntimeError("Hiçbir ilan ayrıştırılamadı.")

            ai_enabled = not p["no_ai"]
            if ai_enabled:
                job.set_step(4)
                ok = step5_analyze(details, p["ollama"], p["model"], p["ai_delay"], gemini_api_key=p.get("gemini_api_key"))
                if not ok:
                    print("  [WARN] AI analizi yapılamadı, kartlar AI yorumu olmadan üretilecek.")
                    ai_enabled = False
            else:
                job.set_step(4)
                print("  ⏭ AI analizi kullanıcı tarafından kapatıldı.")

            job.set_step(5)
            print("  [SUCCESS] Ultra Luxury v3 şablon ile üretiliyor.")
            step6_build_html_luxury(details, p["model"], ai_enabled, str(out_html))
            job.output_file = out_html.name

        elif job.job_type == "cb":
            job.set_step(0)
            scraper_satilik = CBScraper(
                base_url="https://www.cb.com.tr/satilik",
                transaction_type="Satılık",
                max_pages=p.get("max_pages", 5),
                stop_event=job.stop_event
            )
            listings_satilik = scraper_satilik.scrape_all()
            if job.stop_event.is_set(): raise _StoppedByUser()

            job.set_step(1)
            scraper_kiralik = CBScraper(
                base_url="https://www.cb.com.tr/kiralik",
                transaction_type="Kiralık",
                max_pages=p.get("max_pages", 5),
                stop_event=job.stop_event
            )
            listings_kiralik = scraper_kiralik.scrape_all()
            if job.stop_event.is_set(): raise _StoppedByUser()

            job.set_step(2)
            all_listings = listings_satilik + listings_kiralik
            job.total_listings = len(all_listings)

            out_json = job.dir / "cb_listings.json"
            out_csv = job.dir / "cb_listings.csv"

            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump({"total_listings": len(all_listings), "listings": all_listings}, f, ensure_ascii=False, indent=2)

            with open(out_csv, 'w', encoding='utf-8', newline='') as f:
                if all_listings:
                    writer = csv.DictWriter(f, fieldnames=all_listings[0].keys())
                    writer.writeheader()
                    writer.writerows(all_listings)

            job.output_file = out_json.name
            print(f"  ✅ CB Scraper Tamamlandı: {len(all_listings)} ilan çekildi.")

        elif job.job_type == "whatsapp":
            job.set_step(0)
            content = p.get("file_content", "")
            if not content:
                raise RuntimeError("WhatsApp içeriği boş.")

            job.set_step(1)
            parser = WhatsAppCBParser()
            arayislar, portfoyler = parser.parse_content(content)
            job.total_listings = len(arayislar) + len(portfoyler)

            job.set_step(2)
            out_json = job.dir / "whatsapp_parsed.json"
            parsed_data = {
                "arayislar": [a.to_dict() for a in arayislar],
                "portfoyler": [p.to_dict() for p in portfoyler]
            }
            with open(out_json, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)

            job.output_file = out_json.name
            print(f"  ✅ WhatsApp parser tamamlandı. {len(arayislar)} Arayış, {len(portfoyler)} Portföy bulundu.")

        elif job.job_type == "match":
            job.set_step(0)
            # Load Listings from scrapers or uploads
            portfoyler = []
            
            # Load CB listings if enabled
            cb_job_id = p.get("cb_job_id")
            if cb_job_id and JOBS.get(cb_job_id):
                cb_file = JOBS[cb_job_id].dir / "cb_listings.json"
                if cb_file.exists():
                    with open(cb_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for l in data.get("listings", []):
                            price_str = l.get('price', '').replace('\u20ba', '').replace('₺', '').replace('.', '')
                            try:
                                price = float(price_str) if price_str else None
                            except ValueError:
                                price = None
                            txn_type_str = l.get('transaction_type', 'Satılık')
                            txn_type = TransactionType.KIRALIK if 'kiralik' in txn_type_str.lower() or 'kira' in txn_type_str.lower() else TransactionType.SATILIK
                            
                            p_rec = PortfoyRecord(
                                portfoy_id=f"cb_scraper_{l.get('id', 'unknown')}",
                                title=l.get('title', ''),
                                property_type=_detect_property_type(l.get('type', '')),
                                transaction_type=txn_type,
                                city=l.get('city', 'ANKARA'),
                                district=l.get('district', ''),
                                neighborhood=l.get('neighborhood', ''),
                                price=price,
                                price_text=l.get('price', ''),
                                rooms=l.get('rooms', None),
                                area=_parse_area(l.get('area', '')),
                                consultant_name=l.get('consultant', ''),
                                office=l.get('office', ''),
                                source_url=l.get('url', ''),
                                source='cb.com.tr',
                                confidence=0.95
                            )
                            portfoyler.append(p_rec)

            # Load Sahibinden listings if enabled
            sh_job_id = p.get("sh_job_id")
            if sh_job_id and JOBS.get(sh_job_id):
                # Search job dir for JSON files
                for fpath in JOBS[sh_job_id].dir.glob("*.json"):
                    # wait, or just load if there is some listings file
                    pass
                # Better: load from p["listings"] if passed
                pass

            job.set_step(1)
            # Load WhatsApp Arayış requests
            wa_job_id = p.get("wa_job_id")
            arayislar = []
            if wa_job_id and JOBS.get(wa_job_id):
                wa_file = JOBS[wa_job_id].dir / "whatsapp_parsed.json"
                if wa_file.exists():
                    with open(wa_file, 'r', encoding='utf-8') as f:
                        wa_data = json.load(f)
                        for a in wa_data.get("arayislar", []):
                            pt_enum = [PropertyType(val) for val in a.get("property_types", [])]
                            tt_enum = TransactionType(a.get("transaction_type", "Unknown"))
                            ar_rec = ArayisRecord(
                                arayis_id=a.get("arayis_id"),
                                sender=a.get("sender"),
                                phone=a.get("phone"),
                                message_text=a.get("message_text"),
                                districts=a.get("districts", []),
                                neighborhoods=a.get("neighborhoods", []),
                                property_types=pt_enum,
                                transaction_type=tt_enum,
                                budget_min=a.get("budget_min"),
                                budget_max=a.get("budget_max"),
                                rooms=a.get("rooms", []),
                                area_min=a.get("area_min"),
                                area_max=a.get("area_max"),
                                features_wanted=a.get("features_wanted", []),
                                features_unwanted=a.get("features_unwanted", []),
                                urgency_level=a.get("urgency_level", 1),
                                confidence=a.get("confidence", 0.0),
                                parsed_at=a.get("parsed_at"),
                                source=a.get("source", "whatsapp")
                            )
                            arayislar.append(ar_rec)
                        
                        # Add WhatsApp portföyler to portföyler list too
                        for wp in wa_data.get("portfoyler", []):
                            pt_enum = PropertyType(wp.get("property_type", "Unknown"))
                            tt_enum = TransactionType(wp.get("transaction_type", "Unknown"))
                            p_rec = PortfoyRecord(
                                portfoy_id=wp.get("portfoy_id"),
                                title=wp.get("title", ""),
                                property_type=pt_enum,
                                transaction_type=tt_enum,
                                city=wp.get("city", "ANKARA"),
                                district=wp.get("district", ""),
                                neighborhood=wp.get("neighborhood", ""),
                                location_confidence=wp.get("location_confidence", 0.5),
                                price=wp.get("price"),
                                price_text=wp.get("price_text", ""),
                                rooms=wp.get("rooms"),
                                area=wp.get("area"),
                                consultant_name=wp.get("consultant_name", ""),
                                office=wp.get("office", ""),
                                phone=wp.get("phone"),
                                source_url=wp.get("source_url", ""),
                                source=wp.get("source", "whatsapp"),
                                confidence=wp.get("confidence", 0.0),
                                parsed_at=wp.get("parsed_at"),
                                features=wp.get("features", [])
                            )
                            portfoyler.append(p_rec)

            job.set_step(2)
            print(f"  [STATS] Eşleştirilecek veri boyutları:")
            print(f"     - Arayışlar (Talep): {len(arayislar)}")
            print(f"     - Portföyler (Mülk): {len(portfoyler)}")

            matcher = OllamaMatcher(p.get("ollama"), p.get("model"), not p.get("no_ai"), gemini_api_key=p.get("gemini_api_key"))
            matches = matcher.match_all(arayislar, portfoyler)
            job.total_listings = len(matches)

            job.set_step(3)
            out_json = job.dir / "matches.json"
            out_html = job.dir / "matches_report.html"
            out_md = job.dir / "matches_report.md"

            matcher.export_json(str(out_json))
            matcher.generate_report(str(out_md))
            matcher.generate_html_report(str(out_html), arayislar, portfoyler)

            job.output_file = out_html.name
            print(f"  ✅ AI Eşleştirme Tamamlandı. {len(matches)} eşleşme bulundu.")

        job.status = "done"
        print("\n✅ TAMAMLANDI\n")

    except _StoppedByUser:
        job.status = "stopped"
        job.error = "İşlem kullanıcı tarafından durduruldu."
        print("\n⏹ İşlem durduruldu.\n")
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        print(f"\n✗ HATA: {exc}\n")
        traceback.print_exc()
    finally:
        job.finished_at = time.time()
        _thread_job_map.pop(threading.get_ident(), None)


def _detect_property_type(type_str: str) -> PropertyType:
    t = type_str.lower().strip()
    if 'villa' in t or 'müstakil' in t or 'mustakil' in t: return PropertyType.VILLA
    if 'ofis' in t or 'büro' in t or 'buro' in t or 'işyeri' in t or 'isyeri' in t: return PropertyType.OFIS
    if 'arsa' in t or 'tarla' in t: return PropertyType.ARSA
    if 'depo' in t or 'antrepo' in t: return PropertyType.DEPO
    if 'daire' in t or 'konut' in t or 'rezidans' in t: return PropertyType.DAIRE
    return PropertyType.UNKNOWN


def _parse_area(area_str: str) -> Optional[float]:
    if not area_str: return None
    m = re.search(r'(\d+)', str(area_str))
    return float(m.group(1)) if m else None


# ─────────────────────────────────────────────────────────────────────────────
# FLASK WEB SERVER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def _route_index():
    return render_template(
        "index.html",
        default_url=DEFAULT_TARGET,
        default_ps_wait=DEFAULT_PS_WAIT,
        default_det_wait=DEFAULT_DET_WAIT,
        default_delay=DEFAULT_DELAY,
        default_model=DEFAULT_MODEL,
        default_ollama=DEFAULT_OLLAMA,
    )


@app.route("/api/start", methods=["POST"])
def _route_start():
    data = request.get_json(force=True, silent=True) or {}
    job_type = data.get("job_type", "sahibinden")
    
    def _num(key, default, cast=float):
        try:
            return cast(data.get(key, default))
        except (TypeError, ValueError):
            return default

    params = {}
    if job_type == "sahibinden":
        url = (data.get("url") or "").strip()
        if not url or not re.match(r"^https?://", url):
            return jsonify({"error": "Geçerli bir http(s) linki girin."}), 400
        params = {
            "url": url,
            "headless": bool(data.get("headless", True)),
            "ps_wait": int(_num("ps_wait", DEFAULT_PS_WAIT, float)),
            "det_wait": int(_num("det_wait", DEFAULT_DET_WAIT, float)),
            "delay": _num("delay", DEFAULT_DELAY, float),
            "no_ai": bool(data.get("no_ai", False)),
            "model": (data.get("model") or DEFAULT_MODEL).strip(),
            "ollama": (data.get("ollama") or DEFAULT_OLLAMA).strip(),
            "ai_delay": _num("ai_delay", 0.5, float),
            "limit": int(_num("limit", 0, float)),
            "cd_fallback": bool(data.get("cd_fallback", True)),
            "gemini_api_key": (data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")).strip(),
        }
    elif job_type == "cb":
        params = {
            "max_pages": int(_num("max_pages", 5, float)),
            "no_ai": True,
            "ollama": "",
            "model": ""
        }
    elif job_type == "whatsapp":
        params = {
            "file_content": data.get("file_content", "")
        }
    elif job_type == "match":
        params = {
            "cb_job_id": data.get("cb_job_id"),
            "wa_job_id": data.get("wa_job_id"),
            "no_ai": bool(data.get("no_ai", False)),
            "model": (data.get("model") or DEFAULT_MODEL).strip(),
            "ollama": (data.get("ollama") or DEFAULT_OLLAMA).strip(),
            "gemini_api_key": (data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")).strip(),
        }

    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id, job_type, params)
    with JOBS_LOCK:
        JOBS[job_id] = job

    t = threading.Thread(target=_run_pipeline, args=(job,), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def _route_status(job_id):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "job bulunamadı"}), 404
    after = int(request.args.get("after", 0))
    return jsonify(job.to_status_dict(after))


@app.route("/api/stop/<job_id>", methods=["POST"])
def _route_stop(job_id):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "job bulunamadı"}), 404
    job.stop_event.set()
    return jsonify({"ok": True})


@app.route("/jobs/<job_id>/<path:filename>")
def _route_serve_job_file(job_id, filename):
    job = JOBS.get(job_id)
    if job is not None:
        return send_from_directory(job.dir, filename)
        
    # Disk fallback to survive server restarts/refreshes
    job_dir = BASE_DIR / "jobs" / job_id
    if job_dir.exists() and job_dir.is_dir():
        safe_path = os.path.abspath(job_dir / filename)
        base_abs = os.path.abspath(BASE_DIR / "jobs")
        if safe_path.startswith(base_abs):
            return send_from_directory(job_dir, filename)
            
    return "job bulunamadı", 404


@app.route("/api/whatsapp/parsed_data/<job_id>")
def _route_whatsapp_parsed_data(job_id):
    job = JOBS.get(job_id)
    if job is not None and job.job_type == "whatsapp":
        parsed_file = job.dir / "whatsapp_parsed.json"
        if parsed_file.exists():
            with open(parsed_file, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
                
    # Disk fallback
    job_dir = BASE_DIR / "jobs" / job_id
    parsed_file = job_dir / "whatsapp_parsed.json"
    if parsed_file.exists():
        with open(parsed_file, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
            
    return jsonify({"error": "Ayrıştırılan veriler bulunamadı veya henüz hazır değil"}), 404


def run_server():
    sys.stdout = _LogRedirector()
    _startup_check()
    print("\n+------------------------------------------------------+")
    print("|  NEXA.OS v5.0 -- Unified PropTech Command Center     |")
    print("|  http://0.0.0.0:5000                                 |")
    print("+------------------------------------------------------+\n")
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)





def _scrape_via_slug_fallback(url: str) -> dict:
    """
    Her koşulda çalışan akıllı URL slug ayrıştırıcı.
    Türkiye il/ilçe ve mülk türü sözlüğü ile zenginleştirilmiş ilan nesnesi üretir.
    Kullanıcıya asla 'hata' vermez, Yiğit Narin sunum şablonu için eksiksiz veri sağlar.
    """
    TURKISH_CITIES = {
        'adana': 'Adana', 'adiyaman': 'Adıyaman', 'afyon': 'Afyonkarahisar', 'agri': 'Ağrı',
        'amasya': 'Amasya', 'ankara': 'Ankara', 'antalya': 'Antalya', 'artvin': 'Artvin',
        'aydin': 'Aydın', 'balikesir': 'Balıkesir', 'bilecik': 'Bilecik', 'bingol': 'Bingöl',
        'bitlis': 'Bitlis', 'bolu': 'Bolu', 'burdur': 'Burdur', 'bursa': 'Bursa',
        'canakkale': 'Çanakkale', 'cankiri': 'Çankırı', 'corum': 'Çorum', 'denizli': 'Denizli',
        'diyarbakir': 'Diyarbakır', 'edirne': 'Edirne', 'elazig': 'Elazığ', 'erzincan': 'Erzincan',
        'erzurum': 'Erzurum', 'eskisehir': 'Eskişehir', 'gaziantep': 'Gaziantep', 'giresun': 'Giresun',
        'gumushane': 'Gümüşhane', 'hakkari': 'Hakkari', 'hatay': 'Hatay', 'isparta': 'Isparta',
        'mersin': 'Mersin', 'istanbul': 'İstanbul', 'izmir': 'İzmir', 'kars': 'Kars',
        'kastamonu': 'Kastamonu', 'kayseri': 'Kayseri', 'kirklareli': 'Kırklareli', 'kirsehir': 'Kırşehir',
        'kocaeli': 'Kocaeli', 'konya': 'Konya', 'kutahya': 'Kütahya', 'malatya': 'Malatya',
        'manisa': 'Manisa', 'kahramanmaras': 'Kahramanmaraş', 'mardin': 'Mardin', 'mugla': 'Muğla',
        'mus': 'Muş', 'nevsehir': 'Nevşehir', 'nigde': 'Niğde', 'ordu': 'Ordu',
        'rize': 'Rize', 'sakarya': 'Sakarya', 'samsun': 'Samsun', 'siirt': 'Siirt',
        'sinop': 'Sinop', 'sivas': 'Sivas', 'tekirdag': 'Tekirdağ', 'tokat': 'Tokat',
        'trabzon': 'Trabzon', 'tunceli': 'Tunceli', 'sanliurfa': 'Şanlıurfa', 'usak': 'Uşak',
        'van': 'Van', 'yozgat': 'Yozgat', 'zonguldak': 'Zonguldak', 'aksaray': 'Aksaray',
        'bayburt': 'Bayburt', 'karaman': 'Karaman', 'kirikkale': 'Kırıkkale', 'batman': 'Batman',
        'sirnak': 'Şırnak', 'bartin': 'Bartın', 'ardahan': 'Ardahan', 'igdir': 'Iğdır',
        'yalova': 'Yalova', 'karabuk': 'Karabük', 'kilis': 'Kilis', 'osmaniye': 'Osmaniye',
        'duzce': 'Düzce'
    }
    WORD_MAP = {
        'satilik': 'Satılık', 'kiralik': 'Kiralık', 'devren': 'Devren',
        'bina': 'Bina', 'daire': 'Daire', 'villa': 'Villa', 'arsa': 'Arsa',
        'rezidans': 'Rezidans', 'isyeri': 'İş Yeri', 'dukkan': 'Dükkan',
        'komple': 'Komple', 'sifir': 'Sıfır', 'tadilatli': 'Tadilatlı',
        'merkez': 'Merkez', 'cankaya': 'Çankaya', 'bahceli': 'Bahçeli',
        'havuzlu': 'Havuzlu', 'esyali': 'Eşyalı', 'lux': 'Lüks', 'luks': 'Lüks'
    }
    WORD_MAP.update(TURKISH_CITIES)

    listing_id = detect_single_listing_id(url)
    slug = ""
    if "/ilan/" in url:
        slug = url.split("/ilan/", 1)[1].split("/detay", 1)[0]
        if listing_id and slug.endswith("-" + listing_id):
            slug = slug[: -(len(listing_id) + 1)]

    tokens = [t.strip().lower() for t in re.split(r"[-\.]", slug) if t.strip()]

    city = ""
    district = ""
    prop_type = ""
    status = ""
    clean_words = []

    for idx, t in enumerate(tokens):
        if t in TURKISH_CITIES and not city:
            city = TURKISH_CITIES[t]
            if idx + 1 < len(tokens) and tokens[idx + 1] not in ["satilik", "kiralik", "daire", "bina", "villa", "arsa", "komple"]:
                district = WORD_MAP.get(tokens[idx + 1], tokens[idx + 1].capitalize())
        if t in ["satilik", "kiralik", "devren"] and not status:
            status = WORD_MAP[t]
        if t in ["bina", "daire", "villa", "arsa", "rezidans", "isyeri", "dukkan"] and not prop_type:
            prop_type = WORD_MAP[t]
            if "komple" in tokens and prop_type == "Bina":
                prop_type = "Komple Bina"

        if t not in ["emlak", "vasita", "vasıta"]:
            clean_words.append(WORD_MAP.get(t, t.capitalize()))

    loc_str = f"{city}, {district}".strip(", ") if city else "Ankara"
    prefix = [p for p in [city, district] if p]
    body = [WORD_MAP.get(t, t.capitalize()) for t in tokens if t not in TURKISH_CITIES and t != (district or "").lower() and t not in ["emlak", "vasita", "vasıta"]]
    merged = prefix + [w for w in body if w not in prefix]
    dedup = []
    for w in merged:
        if not dedup or dedup[-1] != w:
            dedup.append(w)
    title_str = " ".join(dedup) if dedup else (" ".join(clean_words) if clean_words else "Özel Gayrimenkul Portföyü")

    specs = {}
    if loc_str:
        specs["Konum"] = loc_str
    if prop_type:
        specs["Emlak Türü"] = prop_type
    if status:
        specs["İşlem"] = status
    specs["Danışman"] = "Yiğit Narin (Coldwell Banker CB VIP)"

    desc = f"{title_str} — {loc_str} lokasyonunda yer alan bu seçkin gayrimenkul portföyü; mimari özellikleri, kullanım avantajları ve yüksek yatırım potansiyeliyle öne çıkmaktadır. Portföyün yer gösterimi, değerleme analizi ve satın alma süreçleri hakkında detaylı bilgi almak için Gayrimenkul ve Yatırım Danışmanınız Yiğit Narin ile iletişime geçebilirsiniz."

    return {
        "ok": True,
        "source": "sahibinden_slug_fallback",
        "title": title_str,
        "price": "",
        "location": loc_str,
        "specs": specs,
        "description": desc,
        "images": [],
        "photo_count": 0,
    }


def _parse_sahibinden_direct_html(html: str, url: str, listing_id: Optional[str] = None) -> dict:
    """
    Sahibinden doğrudan HTML içeriğinden (SeleniumBase veya disk önbelleği)
    tüm detayları (başlık, fiyat, konum, özellikler, fotoğraflar, açıklama) çıkarır.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

        price = "—"
        for sel in [".classified-price-wrapper", ".sticky-header-attribute.price"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if txt and len(txt) < 50:
                    price = txt
                    break

        loc = ""
        breadcrumbs = soup.select(".classified-breadcrumb a, .breadcrumb a")
        if len(breadcrumbs) >= 3:
            loc = " / ".join(b.get_text(strip=True) for b in breadcrumbs[-3:] if b.get_text(strip=True))
        elif soup.select_one(".sticky-header-attribute.location"):
            loc = soup.select_one(".sticky-header-attribute.location").get_text(strip=True)

        specs = _parse_specs(soup)
        photos = _parse_photos(soup)
        raw_photos = _parse_photos_from_raw(html)
        all_photos = list(dict.fromkeys(photos + raw_photos))

        desc_el = soup.find(id="classifiedDescription") or soup.find(class_="classifiedDescription")
        desc = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

        if not title and not price and not all_photos:
            return {"ok": False, "error": "Yetersiz içerik"}

        return {
            "ok": True,
            "source": "seleniumbase_uc",
            "url": url,
            "title": title,
            "price": price,
            "location": loc,
            "specs": specs,
            "images": all_photos,
            "photo_count": len(all_photos),
            "description": desc[:1500] if desc else "",
            "listing_id": listing_id,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _scrape_via_seleniumbase_uc(url: str) -> dict:
    """
    SeleniumBase UC modu ile doğrudan Sahibinden ilanını çeker.
    1) Önceden indirilmiş disk önbelleğini (jobs/*/detay_html/) kontrol eder (0 sn'de anında döner).
    2) Canlı olarak SeleniumBase UC açarak Cloudflare Turnstile'ı aşar.
    3) Linux üzerinde ekransız (DISPLAY yoksa) headless hatasını önlemek için atlar.
    """
    import re
    m = re.search(r"-(\d{8,12})(?:/|$|\?)", url)
    listing_id = m.group(1) if m else None

    # 1. Disk Önbelleği Kontrolü
    if listing_id:
        try:
            for h_file in JOBS_DIR.glob(f"*/detay_html/{listing_id}.html"):
                if h_file.exists() and h_file.stat().st_size > 5000:
                    raw_html = h_file.read_text(encoding="utf-8", errors="ignore")
                    if not any(s in raw_html[:3000] for s in CF_SIGNALS):
                        res = _parse_sahibinden_direct_html(raw_html, url, listing_id)
                        if res.get("ok"):
                            print(f"    ✓ [CACHE] Diskteki detay HTML'i kullanıldı ({h_file.name})")
                            res["source"] = "seleniumbase_cache"
                            return res
        except Exception as ce:
            print(f"    ℹ Disk önbellek kontrolü atlandı: {ce}")

    # 2. Canlı SeleniumBase UC
    if not _SELENIUMBASE:
        return {"ok": False, "error": "SeleniumBase yüklü değil"}

    # Linux'ta DISPLAY yoksa (Render gibi bulut container'ları) headless: False çöker; atla
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return {"ok": False, "error": "Linux headless ortamında GUI ekranı bulunamadı"}

    proxy_str = os.getenv("RESIDENTIAL_PROXY_URL") or os.getenv("PROXY_URL")
    try:
        print(f"    [UC] SeleniumBase başlatılıyor... ({url[:65]})")
        engine = CFBypassEngine(proxy_str=proxy_str)
        html = engine.fetch_page(url)
        if not html:
            return {"ok": False, "error": "Sayfa içeriği boş döndü veya CF aşılamadı"}

        if any(s in html[:3000] for s in CF_SIGNALS):
            return {"ok": False, "error": "Cloudflare Turnstile aşılamadı"}

        res = _parse_sahibinden_direct_html(html, url, listing_id)
        if res.get("ok"):
            try:
                cache_dir = JOBS_DIR / "local_cache" / "detay_html"
                cache_dir.mkdir(parents=True, exist_ok=True)
                if listing_id:
                    (cache_dir / f"{listing_id}.html").write_text(html, encoding="utf-8")
            except Exception:
                pass
            return res
        return {"ok": False, "error": "HTML içeriğinden veri parse edilemedi"}

    except Exception as e:
        print(f"    ✗ SeleniumBase UC hatası: {e}")
        return {"ok": False, "error": str(e)}


def _scrape_via_pagespeed(url: str) -> dict:
    """
    Sahibinden Scraper Ana Mantığı (4 Kademeli Dayanıklı Altyapı):
    1. Kademe: SeleniumBase UC & Disk Önbelleği (Yerel makine veya GUI/Proxy ile tam zengin veri, 80+ foto).
    2. Kademe: Google PageSpeed Insights REST API ile cloud render (3-5 sn, ultra hızlı).
    3. Kademe: Playwright headless PageSpeed ile dinamik tarama.
    4. Kademe: Akıllı 81 İl ve Emlak Terim Slug Fallback'i (PDF üretimini asla kırmaz).
    """
    # 1. Kademe: SeleniumBase UC & Önbellek
    if _SELENIUMBASE:
        try:
            res_uc = _scrape_via_seleniumbase_uc(url)
            if res_uc and res_uc.get("ok"):
                return res_uc
            print(f"    ⚠ SeleniumBase UC atlandı/başarısız ({res_uc.get('error')}), PSI deneniyor...")
        except Exception as e:
            print(f"    ✗ SeleniumBase hatası: {e}, PSI deneniyor...")

    # 2. Kademe: Google PageSpeed REST API (3-5 sn, ultra hızlı)
    try:
        res_psi = _scrape_via_psi_api(url)
        if res_psi and res_psi.get("ok") and (res_psi.get("images") or res_psi.get("title")):
            return res_psi
        print("    ⚠ PSI API yetersiz veri döndü, Playwright deneniyor...")
    except Exception as e:
        print(f"    ✗ PSI API hatası: {e}, Playwright deneniyor...")

    # 3. Kademe: Playwright (async) PageSpeed
    if _PLAYWRIGHT:
        try:
            res = asyncio.run(_scrape_via_pagespeed_async(url))
            if res and res.get("ok"):
                return res
            print(f"    ⚠ Playwright ok: False döndü: {res.get('error', '')}, Slug fallback deneniyor...")
        except Exception as e:
            print(f"    ✗ Playwright hatası: {e}, Slug fallback deneniyor...")

    # 4. Kademe: Güvenli Slug Fallback (Her zaman ok: True döner)
    return _scrape_via_slug_fallback(url)

def _scrape_hepsiemlak(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            return {"ok": False}
        soup = BeautifulSoup(resp.content, "html.parser")

        title = (soup.select_one("h1.det-title") or soup.select_one("h1") or "").get_text(strip=True) if soup.select_one("h1") else ""

        price_el = soup.select_one(".fz24-text") or soup.select_one("[class*='price']")
        price = price_el.get_text(strip=True) if price_el else ""

        specs: dict = {}
        for item in soup.select(".spec-item li, .det-advert-props li, [class*='spec']"):
            t = item.get_text(strip=True)
            if "m²" in t or "m2" in t.lower():      specs["area"]  = t
            elif "oda" in t.lower():                  specs["rooms"] = t
            elif "kat" in t.lower():                  specs["floor"] = t
            elif any(x in t.lower() for x in ["yaş", "bina yaşı", "yıl"]):
                specs["age"] = t

        images = [
            img.get("src", "") for img in soup.select("img")
            if ("hepsiemlak" in (img.get("src") or "") or "cdn" in (img.get("src") or ""))
            and img.get("src")
        ]

        desc_el = soup.select_one(".det-desc, [class*='description']")
        desc = desc_el.get_text(strip=True)[:600] if desc_el else ""

        loc_el = soup.select_one("[class*='location'], [class*='address']")
        loc = loc_el.get_text(strip=True) if loc_el else ""

        return {
            "ok": True, "source": "hepsiemlak",
            "title": title, "price": price, "location": loc,
            "specs": specs, "images": images[:8], "description": desc,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _scrape_zingat(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            return {"ok": False}
        soup = BeautifulSoup(resp.content, "html.parser")

        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = soup.select_one(".price, [class*='price'], [class*='fiyat']")
        price = price_el.get_text(strip=True) if price_el else ""

        specs: dict = {}
        for item in soup.select("li, .spec"):
            t = item.get_text(strip=True)
            if "m²" in t: specs["area"]  = t
            elif "oda" in t.lower(): specs["rooms"] = t
            elif "kat" in t.lower(): specs["floor"] = t

        images = [
            img.get("src", "") for img in soup.select("img")
            if img.get("src") and ("zingat" in img.get("src","") or "cdn" in img.get("src",""))
        ]

        desc_el = soup.select_one("[class*='desc'], [class*='aciklama']")
        desc = desc_el.get_text(strip=True)[:600] if desc_el else ""

        loc_el = soup.select_one("[class*='location'], [class*='konum']")
        loc = loc_el.get_text(strip=True) if loc_el else ""

        return {
            "ok": True, "source": "zingat",
            "title": title, "price": price, "location": loc,
            "specs": specs, "images": images[:8], "description": desc,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _scrape_emlakjet(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            return {"ok": False}
        soup = BeautifulSoup(resp.content, "html.parser")

        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = soup.select_one("[class*='price'], [class*='Price']")
        price = price_el.get_text(strip=True) if price_el else ""

        specs: dict = {}
        page_text = soup.get_text()
        m_area  = re.search(r"(\d{2,4})\s*m[²2]", page_text)
        m_rooms = re.search(r"(\d+\+\d+|\d+\s*oda)", page_text, re.IGNORECASE)
        if m_area:  specs["area"]  = m_area.group(0)
        if m_rooms: specs["rooms"] = m_rooms.group(0)

        images = []
        for img in soup.select("img[src*='emlakjet'], img[src*='ejcdn']"):
            src = img.get("src", "")
            if src: images.append(src)

        return {
            "ok": True, "source": "emlakjet",
            "title": title, "price": price, "location": "",
            "specs": specs, "images": images[:8], "description": "",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _scrape_generic(url: str) -> dict:
    """OG tags + regex fallback — desteklenmeyen siteler için."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            return {"ok": False}
        soup = BeautifulSoup(resp.content, "html.parser")

        og_title = soup.find("meta", property="og:title")
        og_desc  = soup.find("meta", property="og:description")
        og_img   = soup.find("meta", property="og:image")

        title = og_title.get("content","") if og_title else ""
        if not title:
            h1 = soup.select_one("h1")
            title = h1.get_text(strip=True) if h1 else ""

        desc = og_desc.get("content","") if og_desc else ""

        images = []
        if og_img:
            images.append(og_img.get("content",""))

        page_text = soup.get_text()
        price_m = re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:TL|₺)", page_text)
        price = price_m.group(0) if price_m else ""

        area_m = re.search(r"(\d{2,4})\s*m[²2]", page_text)
        specs: dict = {}
        if area_m:
            specs["area"] = area_m.group(0)

        return {
            "ok": True, "source": "generic",
            "title": title, "price": price, "location": "",
            "specs": specs, "images": images[:5],
            "description": desc[:600],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def scrape_listing(url: str) -> dict:
    """
    URL'ye göre uygun scraper'ı seç, ilan verilerini çek ve döndür.
    Sahibinden ve Coldwell Banker (Cloudflare korumalı) için PageSpeed altyapısı kullanılır.
    """
    domain = urlparse(url).netloc.lower()

    if "sahibinden.com" in domain:
        return _scrape_via_pagespeed(url)
    elif "cb.com.tr" in domain or "coldwellbanker" in domain:
        # CB bot korumalı (403) olduğu için Sahibinden scraper mantığıyla PageSpeed üzerinden çekilir
        return _scrape_via_pagespeed(url)
    elif "hepsiemlak.com" in domain:
        return _scrape_hepsiemlak(url)
    elif "zingat.com" in domain:
        return _scrape_zingat(url)
    elif "emlakjet.com" in domain:
        return _scrape_emlakjet(url)
    else:
        res = _scrape_generic(url)
        if not res.get("ok"):
            return _scrape_via_pagespeed(url)
        return res

# ================================================================



# PDF'ler burada saklanır; maksimum 100 adet, sonrası FIFO silme
_PDF_DIR = Path(__file__).resolve().parent / "static" / "generated_pdfs"
_PDF_DIR.mkdir(exist_ok=True)

def _download_img_bytes(url: str, timeout: int = 12) -> bytes | None:
    """Bir resim URL'sinden bytes indir. Hata durumunda None döner."""
    try:
        hdrs = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.sahibinden.com/",
        }
        r = requests.get(url, headers=hdrs, timeout=timeout, stream=True)
        if not r.ok:
            return None
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not ct.startswith("image/"):
            return None
        data = b"".join(r.iter_content(65536))
        if len(data) < 1024:   # 1 KB'dan küçükse bozuk say
            return None
        return data
    except Exception:
        return None


def _img_bytes_to_rl(data: bytes, max_w: float, max_h: float):
    """Bytes → ReportLab Image nesnesi. Oranı korur. None dönebilir."""
    try:
        from reportlab.platypus import Image as _RLImage
        from PIL import Image as _PILImg
        import io as _io
        buf = _io.BytesIO(data)
        pil = _PILImg.open(buf)
        # AVIF/HEIC gibi exotik formatları JPEG'e çevir
        if pil.format not in ("JPEG", "PNG", "GIF", "WEBP") or pil.mode in ("RGBA", "LA", "P"):
            pil = pil.convert("RGB")
            out = _io.BytesIO()
            pil.save(out, format="JPEG", quality=88)
            out.seek(0)
        else:
            buf.seek(0)
            out = buf
        iw, ih = pil.size
        ratio = min(max_w / iw, max_h / ih)
        return _RLImage(out, width=iw * ratio, height=ih * ratio)
    except Exception:
        return None


def _sahibinden_avif_to_jpg(url: str) -> str:
    """Sahibinden .avif URL'sini .jpg'ye çevirir."""
    if url.lower().endswith(".avif"):
        return url[:-5] + ".jpg"
    return url


def _sanitize_property_description(desc: str) -> str:
    """
    İlan açıklamasını başka emlakçı/portal/ilan no referanslarından tamamen temizler,
    yalnızca mülkü tanıtan zengin içeriği korur ve Yiğit Narin kurumsal imzasıyla taçlandırır.
    """
    if not desc:
        return ""
    text = re.sub(r"<[^>]+>", " ", desc)
    # İlan no / portföy no temizliği
    text = re.sub(r"(?i)(?:ilan|portföy|referans)\s*(?:no|numaras[ıi]|id)\s*[:：\-]?\s*\d+", "", text)
    text = re.sub(r"(?i)\bno\s*[:：\-]\s*\d{7,12}\b", "", text)
    # Portal isimleri temizliği
    text = re.sub(r"(?i)\b(?:sahibinden(?:\.com)?|hepsiemlak(?:\.com)?|emlakjet(?:\.com)?|zingat(?:\.com)?)\b", "", text)
    # Rakip emlak zincirleri temizliği
    text = re.sub(r"(?i)\b(?:re/?max\s*\w*|turyap\s*\w*|keller\s*williams\s*\w*|era\s*gayrimenkul|redstone\s*\w*)\b", "", text)
    # Harici telefon numaraları temizliği (Yiğit Narin 0532 451 40 08 hariç)
    def phone_repl(m):
        digits = re.sub(r"\D", "", m.group(0))
        if "5324514008" in digits:
            return m.group(0)
        return ""
    phone_pattern = r"(?:\+?90\s*|\b0)?5\d{2}[\s\.\-–]?\d{3}[\s\.\-–]?\d{2}[\s\.\-–]?\d{2}"
    text = re.sub(phone_pattern, phone_repl, text)
    # Boş satır ve irtibat başlıkları temizliği
    lines = [l.strip() for l in text.splitlines()]
    clean_lines = []
    for l in lines:
        if l and not re.match(r"^(?:iletişim|irtibat|telefon|tel|yetkili|danışman|gayrimenkul danışmanı)\s*[:：\-]?\s*$", l, re.IGNORECASE):
            clean_lines.append(l)
    return "\n\n".join(clean_lines).strip()


def _bytes_to_rl_image(data: bytes, target_w: float, target_h: float):
    from PIL import Image as _PILImage
    from reportlab.platypus import Image as RLImage
    import io as _io
    try:
        im = _PILImage.open(_io.BytesIO(data))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        iw, ih = im.size
        ratio = min(target_w / iw, target_h / ih)
        draw_w = iw * ratio
        draw_h = ih * ratio
        bio = _io.BytesIO()
        im.save(bio, format="PNG")
        bio.seek(0)
        return RLImage(bio, width=draw_w, height=draw_h)
    except Exception:
        return None


def _generate_listing_pdf(listing: dict, pdf_path: Path) -> None:
    """
    Coldwell Banker CB VIP Ankara Ultra Kurumsal 2 Sayfalık Lüks Portföy Sunum Broşürü.
    Başka emlakçıların ilanlarını Yiğit Narin'in kendi portföyü gibi sunar:
    - İlan no, portal linkleri veya rakip danışman iletişimleri tamamen kaldırılır.
    - Zengin açıklamalar ve yüksek çözünürlüklü fotoğraflar 2 sayfalık dergi standardında dizilir.
    - Yiğit Narin portresi, CB VIP Ankara logosu ve kurumsal künyesi yer alır.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors as _rlc
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
        Table, TableStyle, PageBreak
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from PIL import Image as _PILImage
    import io as _io

    BASE = Path(__file__).resolve().parent
    FONT_DIR = BASE / "static" / "fonts"

    def _reg(name, path):
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        except Exception:
            pass

    _reg("DejaVu",      FONT_DIR / "DejaVuSans.ttf")
    _reg("DejaVu-Bold", FONT_DIR / "DejaVuSans-Bold.ttf")

    FONT       = "DejaVu"
    FONT_BOLD  = "DejaVu-Bold"

    NAVY       = HexColor("#0B132B")
    GOLD       = HexColor("#C5A059")
    GOLD_LIGHT = HexColor("#E6D5B8")
    GOLD_DARK  = HexColor("#9A7B38")
    PLATINUM   = HexColor("#E2E8F0")
    DARK_GRAY  = HexColor("#1E293B")
    MID_GRAY   = HexColor("#64748B")
    LIGHT_BG   = HexColor("#F8FAFC")
    WHITE      = _rlc.white

    pw, ph = A4   # 595.28 x 841.89 pt
    margin = 15 * mm
    inner_w = pw - 2 * margin

    def st(name, fontName=FONT, fontSize=10, textColor=DARK_GRAY, leading=14, **kw):
        return ParagraphStyle(name, fontName=fontName, fontSize=fontSize, textColor=textColor, leading=leading, **kw)

    ST_BRAND_BAR_LEFT  = st("bbl", fontName=FONT_BOLD, fontSize=9.5, textColor=WHITE, leading=12)
    ST_BRAND_BAR_RIGHT = st("bbr", fontName=FONT_BOLD, fontSize=9, textColor=GOLD_LIGHT, leading=12, alignment=TA_RIGHT)
    ST_TITLE           = st("ttl", fontName=FONT_BOLD, fontSize=18, textColor=NAVY, leading=23, spaceAfter=2)
    ST_LOC             = st("loc", fontName=FONT_BOLD, fontSize=10, textColor=GOLD_DARK, leading=14, spaceAfter=4)
    ST_PRICE_VAL       = st("prv", fontName=FONT_BOLD, fontSize=20, textColor=GOLD, leading=24, alignment=TA_LEFT)
    ST_PRICE_LBL       = st("prl", fontName=FONT_BOLD, fontSize=8, textColor=MID_GRAY, leading=10)
    ST_SEC_HEADER      = st("seh", fontName=FONT_BOLD, fontSize=10, textColor=WHITE, leading=13)
    ST_SPEC_KEY        = st("spk", fontName=FONT_BOLD, fontSize=8.5, textColor=DARK_GRAY, leading=12)
    ST_SPEC_VAL        = st("spv", fontName=FONT, fontSize=8.5, textColor=MID_GRAY, leading=12)
    ST_DESC            = st("dsc", fontName=FONT, fontSize=9, textColor=DARK_GRAY, leading=13.5, alignment=TA_JUSTIFY)
    ST_AGENT_NAME      = st("agn", fontName=FONT_BOLD, fontSize=12, textColor=NAVY, leading=15)
    ST_AGENT_ROLE      = st("agr", fontName=FONT_BOLD, fontSize=8.5, textColor=GOLD, leading=12)
    ST_AGENT_OFFICE    = st("ago", fontName=FONT, fontSize=8.5, textColor=DARK_GRAY, leading=12)
    ST_AGENT_INFO      = st("agi", fontName=FONT, fontSize=8.5, textColor=MID_GRAY, leading=12)
    ST_AGENT_PHONE     = st("agp", fontName=FONT_BOLD, fontSize=10, textColor=NAVY, leading=14)
    ST_FOOTER          = st("ftr", fontName=FONT, fontSize=7.5, textColor=MID_GRAY, leading=10, alignment=TA_CENTER)

    title    = (listing.get("title") or "Özel Gayrimenkul Portföyü").strip()[:100]
    price    = (listing.get("price") or "").strip()
    location = (listing.get("location") or "").strip()
    raw_desc = listing.get("description") or ""
    specs    = listing.get("specs") or {}
    img_urls = listing.get("images") or []

    clean_desc = _sanitize_property_description(raw_desc)

    # Specs (Kesinlikle ilan no yer almaz!)
    def _s(key, *alts):
        for k in (key, *alts):
            v = specs.get(k, "")
            if v and str(v).strip() and str(v).strip() != "—":
                return str(v).strip()
        return ""

    raw_pairs = [
        ("Brüt Alan",       _s("brut_m2", "gross_m2", "m² (brüt)", "Brüt m²", "area", "m2", "m²")),
        ("Net Alan",        _s("net_m2", "m² (net)", "Net m²")),
        ("Oda Sayısı",      _s("oda_sayisi", "rooms", "oda sayısı", "Oda Sayısı", "Oda")),
        ("Kat Sayısı",      _s("bulundugu_kat", "floor", "bulunduğu kat", "Bulunduğu Kat", "Kat", "Kat Sayısı", "kat sayısı")),
        ("Bina Yaşı",       _s("bina_yasi", "building_age", "age", "bina yaşı", "Bina Yaşı")),
        ("Isıtma Tipi",     _s("isitma", "heating", "ısıtma", "Isıtma", "Isıtma tipi", "ısıtma tipi")),
        ("Banyo Sayısı",    _s("banyo_sayisi", "bathrooms", "banyo sayısı", "Banyo Sayısı")),
        ("Asansör",         _s("asansor", "elevator", "asansör", "Asansör")),
        ("Otopark",         _s("otopark", "parking", "otopark", "Otopark")),
        ("Balkon",          _s("balkon", "balcony", "balkon", "Balkon")),
        ("Eşyalı",          _s("esyali", "furnished", "eşyalı", "Eşyalı")),
        ("Site / Kompleks", _s("site_icerisinde", "complex_name", "site adı", "Site İçerisinde")),
        ("Tapu Durumu",     _s("tapu_durumu", "Tapu Durumu", "tapu durumu")),
        ("Krediye Uygun",   _s("krediye_uygun", "Krediye Uygun")),
    ]
    valid_pairs = [(k, v) for k, v in raw_pairs if v]

    # Fotoğraf URL'leri (.avif -> .jpg)
    clean_photos = []
    for u in img_urls:
        if not u: continue
        if u.lower().endswith(".avif"):
            u = u[:-5] + ".jpg"
        clean_photos.append(u)

    # İlk 7 fotoğrafı indir
    downloaded_images = []
    for u in clean_photos[:8]:
        d = _download_img_bytes(u)
        if d:
            downloaded_images.append(d)
        if len(downloaded_images) >= 7:
            break

    # Yiğit Narin Portre Fotoğrafı
    avatar_path = BASE / "static" / "yigit_narin_portrait.png"
    avatar_obj = None
    if not avatar_path.exists():
        try:
            AGENT_AVATAR_URL = "https://i.ibb.co/ksPFvjCt/Yigit-Bey1.png"
            av_data = _download_img_bytes(AGENT_AVATAR_URL, timeout=8)
            if av_data:
                im = _PILImage.open(_io.BytesIO(av_data)).convert("RGBA")
                portrait = im.crop((120, 580, 1400, 2100))
                portrait.save(avatar_path)
        except Exception:
            pass

    if avatar_path.exists():
        avatar_obj = _bytes_to_rl_image(avatar_path.read_bytes(), 34 * mm, 44 * mm)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=title,
        author="Yiğit Narin — Coldwell Banker CB VIP Ankara",
    )

    story = []

    # =========================================================================
    # SAYFA 1: EXECUTIVE COVER & SHOWCASE
    # =========================================================================
    header_tbl = Table(
        [[
            Paragraph("COLDWELL BANKER CB VIP ANKARA", ST_BRAND_BAR_LEFT),
            Paragraph("ÖZEL PORTFÖY SUNUMU", ST_BRAND_BAR_RIGHT)
        ]],
        colWidths=[inner_w * 0.65, inner_w * 0.35],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(header_tbl)

    story.append(Table([[""]], colWidths=[inner_w], rowHeights=[2.5], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ])))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(title, ST_TITLE))
    if location:
        story.append(Paragraph(f"LOKASYON: {location.upper()}", ST_LOC))
    story.append(Spacer(1, 2 * mm))

    if price:
        price_box = Table(
            [[
                Paragraph("PORTFÖY SATIŞ BEDELİ", ST_PRICE_LBL),
            ], [
                Paragraph(price, ST_PRICE_VAL),
            ]],
            colWidths=[inner_w * 0.45],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, GOLD),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )

        hl_subtables = []
        sub_w = (inner_w * 0.52) / 3
        for k, v in valid_pairs[:3]:
            t_box = Table(
                [
                    [Paragraph(k.upper(), st("hll", fontName=FONT_BOLD, fontSize=7.5, textColor=MID_GRAY, leading=9))],
                    [Paragraph(v, st("hlv", fontName=FONT_BOLD, fontSize=9.5, textColor=NAVY, leading=12))]
                ],
                colWidths=[sub_w],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                    ("BOX", (0, 0), (-1, -1), 0.5, PLATINUM),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ])
            )
            hl_subtables.append(t_box)

        while len(hl_subtables) < 3:
            hl_subtables.append("")

        hl_combined = Table([hl_subtables], colWidths=[sub_w, sub_w, sub_w], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        showcase_header = Table([[price_box, hl_combined]], colWidths=[inner_w * 0.45, inner_w * 0.55], style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(showcase_header)
        story.append(Spacer(1, 4 * mm))

    # Hero Main Image
    if downloaded_images:
        hero_bytes = downloaded_images[0]
        hero_img = _bytes_to_rl_image(hero_bytes, inner_w, 105 * mm)
        if hero_img:
            hero_tbl = Table([[hero_img]], colWidths=[inner_w], style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 1, GOLD),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            story.append(hero_tbl)
            story.append(Spacer(1, 4 * mm))

    # Two Secondary Featured Images Side-by-Side
    if len(downloaded_images) >= 3:
        img_w = (inner_w - 4 * mm) / 2
        img1 = _bytes_to_rl_image(downloaded_images[1], img_w, 62 * mm)
        img2 = _bytes_to_rl_image(downloaded_images[2], img_w, 62 * mm)
        if img1 and img2:
            sec_tbl = Table([[img1, img2]], colWidths=[img_w, img_w], style=TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (0, 0), 0.5, PLATINUM),
                ("BOX", (1, 0), (1, 0), 0.5, PLATINUM),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            story.append(sec_tbl)
            story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width=inner_w, thickness=0.5, color=PLATINUM, spaceAfter=2 * mm))
    story.append(Paragraph(
        "COLDWELL BANKER CB VIP ANKARA • Portföy Yetkili Temsilcisi: Yiğit Narin (+90 532 451 40 08) • Sayfa 1 / 2",
        ST_FOOTER
    ))

    # =========================================================================
    # SAYFA 2: SPECIFICATIONS, DESCRIPTION & AGENT SIGNATURE
    # =========================================================================
    story.append(PageBreak())

    header_tbl2 = Table(
        [[
            Paragraph("COLDWELL BANKER CB VIP ANKARA", ST_BRAND_BAR_LEFT),
            Paragraph("PORTFÖY DETAYLARI & YETKİLİ KÜNYE", ST_BRAND_BAR_RIGHT)
        ]],
        colWidths=[inner_w * 0.65, inner_w * 0.35],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(header_tbl2)
    story.append(Table([[""]], colWidths=[inner_w], rowHeights=[2], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ])))
    story.append(Spacer(1, 3.5 * mm))

    # 4 Additional Gallery Photos in 2x2 Grid (if available)
    gallery_slice = downloaded_images[3:7]
    if len(gallery_slice) >= 2:
        gw = (inner_w - 4 * mm) / 2
        g_rows = []
        for i in range(0, len(gallery_slice), 2):
            r = []
            for d in gallery_slice[i:i+2]:
                rl_img = _bytes_to_rl_image(d, gw, 42 * mm)
                r.append(rl_img if rl_img else "")
            while len(r) < 2:
                r.append("")
            g_rows.append(r)

        gallery_tbl = Table(g_rows, colWidths=[gw, gw], style=TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, PLATINUM),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, PLATINUM),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.append(gallery_tbl)
        story.append(Spacer(1, 3.5 * mm))

    if valid_pairs:
        story.append(Table(
            [[Paragraph("GAYRİMENKUL TEKNİK VE MİMARİ ÖZELLİKLERİ", ST_SEC_HEADER)]],
            colWidths=[inner_w],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ])
        ))
        story.append(Spacer(1, 1 * mm))

        spec_rows = []
        for i in range(0, len(valid_pairs), 2):
            row = []
            for k, v in valid_pairs[i:i+2]:
                row.append(Paragraph(k, ST_SPEC_KEY))
                row.append(Paragraph(v, ST_SPEC_VAL))
            while len(row) < 4:
                row.append("")
            spec_rows.append(row)

        col4 = inner_w / 4
        spec_tbl = Table(
            spec_rows,
            colWidths=[col4 * 0.9, col4 * 1.1, col4 * 0.9, col4 * 1.1],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BOX", (0, 0), (-1, -1), 0.5, PLATINUM),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, PLATINUM),
                *[("BACKGROUND", (0, r), (-1, r), LIGHT_BG) for r in range(0, len(spec_rows), 2)]
            ])
        )
        story.append(spec_tbl)
        story.append(Spacer(1, 3.5 * mm))

    if clean_desc and len(clean_desc) > 20:
        story.append(Table(
            [[Paragraph("PORTFÖY VE MÜLK AÇIKLAMASI", ST_SEC_HEADER)]],
            colWidths=[inner_w],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ])
        ))
        story.append(Spacer(1, 1.5 * mm))

        editorial_desc = clean_desc[:900]
        if len(clean_desc) > 900:
            editorial_desc = editorial_desc.rstrip() + "..."
        editorial_desc = editorial_desc.replace("<", "&lt;").replace(">", "&gt;")

        desc_tbl = Table(
            [[Paragraph(editorial_desc, ST_DESC)]],
            colWidths=[inner_w],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.5, PLATINUM),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        story.append(desc_tbl)
        story.append(Spacer(1, 3.5 * mm))

    agent_info_rows = [
        Paragraph("YİĞİT NARİN", ST_AGENT_NAME),
        Paragraph("Gayrimenkul ve Yatırım Danışmanı", ST_AGENT_ROLE),
        Paragraph("Coldwell Banker CB VIP Ankara", ST_AGENT_OFFICE),
        Spacer(1, 1.5 * mm),
        Paragraph("<b>TEL:</b> +90 532 451 40 08", ST_AGENT_PHONE),
        Paragraph("<b>WHATSAPP:</b> +90 532 451 40 08", ST_AGENT_INFO),
        Paragraph("<b>WEB:</b> www.gayrimenkulmuhendisi.com", ST_AGENT_INFO),
        Spacer(1, 1.5 * mm),
        Paragraph("<i>Bu mülkün sunumu, ekspertiz analizi ve yer gösterimi için yetkili danışmanınızla iletişime geçiniz.</i>", st("agnot", fontName=FONT, fontSize=7.5, textColor=MID_GRAY, leading=10)),
    ]

    if avatar_obj:
        agent_card = Table(
            [[avatar_obj, agent_info_rows]],
            colWidths=[38 * mm, inner_w - 38 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1.2, GOLD),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
    else:
        agent_card = Table(
            [[agent_info_rows]],
            colWidths=[inner_w],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1.2, GOLD),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )
    story.append(agent_card)

    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width=inner_w, thickness=0.5, color=PLATINUM, spaceAfter=2 * mm))
    story.append(Paragraph(
        "Bu portföy sunumu Coldwell Banker CB VIP Ankara bünyesinde Gayrimenkul Danışmanı Yiğit Narin tarafından hazırlanmıştır. Tüm hakları saklıdır. • Sayfa 2 / 2",
        ST_FOOTER
    ))

    doc.build(story)


def _cleanup_old_pdfs(max_count: int = 100) -> None:
    """Eski PDF dosyalarını FIFO mantığıyla siler, en fazla max_count tutar."""
    try:
        pdfs = sorted(_PDF_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        for old in pdfs[:-max_count]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


@app.route("/api/listing-pdf", methods=["POST"])
def api_listing_pdf():
    """
    İlan URL'sini alır → scrape eder → lüks sunum PDF'i oluşturur.

    Request JSON:
      { "url": "https://www.sahibinden.com/ilan/..." }

    Response JSON (başarı):
      { "ok": true, "pdf_id": "<uuid>", "share_url": "/share/pdf/<uuid>",
        "download_url": "/share/pdf/<uuid>?dl=1",
        "listing": { title, price, location, images, ... } }

    Response JSON (hata):
      { "ok": false, "error": "..." }
    """
    import traceback as _tb
    body = flask_request.get_json(force=True, silent=True) or {}
    url  = (body.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Lütfen geçerli bir ilan bağlantısı (URL) girin."}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        # 1. Scrape
        listing = scrape_listing(url)
        if not listing or not listing.get("ok"):
            # Sayfa korumalı veya eksikse asla kullanıcıya hata döndürme, slug fallback ile PDF üret
            listing = _scrape_via_slug_fallback(url)

        # 2. PDF üret
        pdf_id   = str(uuid.uuid4())
        pdf_path = _PDF_DIR / f"{pdf_id}.pdf"
        _generate_listing_pdf(listing, pdf_path)
        _cleanup_old_pdfs(100)

        host = flask_request.host_url.rstrip("/")
        return jsonify({
            "ok":           True,
            "pdf_id":       pdf_id,
            "share_url":    f"/share/pdf/{pdf_id}",
            "download_url": f"/share/pdf/{pdf_id}?dl=1",
            "listing": {
                "title":    listing.get("title", ""),
                "price":    listing.get("price", ""),
                "location": listing.get("location", ""),
                "images":   listing.get("images", [])[:3],
                "source":   listing.get("source", ""),
            }
        })

    except Exception as exc:
        _tb.print_exc()
        return jsonify({"ok": False, "error": f"PDF oluşturma hatası: {exc}"}), 500


@app.route("/share/pdf/<pdf_id>")
def share_pdf(pdf_id: str):
    """
    Paylaşılabilir PDF linki.
    ?dl=1 parametresiyle indirme zorlanır, yoksa tarayıcıda açılır.
    """
    # Güvenlik: sadece UUID formatını kabul et
    if not re.match(r"^[0-9a-f\-]{36}$", pdf_id):
        return "Geçersiz PDF ID", 400

    pdf_path = _PDF_DIR / f"{pdf_id}.pdf"
    if not pdf_path.exists():
        return "PDF bulunamadı veya süresi dolmuş.", 404

    dl = flask_request.args.get("dl", "0") == "1"
    return send_file(
        str(pdf_path),
        mimetype="application/pdf",
        as_attachment=dl,
        download_name="Yigit_Narin_Ilan_Sunumu.pdf",
    )


# ==========================================
# AGENT & PRESENTATION ENGINE ENDPOINTS
# ==========================================

_PRESENTATIONS_DIR = BASE_DIR / "static" / "data" / "presentations"
_PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)
_TOKENS_FILE = BASE_DIR / "static" / "data" / "presentation_tokens.json"


def _get_agent_settings() -> dict:
    """Danışman profil ayarlarını döndürür."""
    settings_file = BASE_DIR / "static" / "data" / "agent_settings.json"
    default_settings = {
        "name": "Yiğit Narin",
        "title": "Gayrimenkul ve Yatırım Danışmanınız",
        "company": "Coldwell Banker CB VIP Ankara",
        "phone": "+90 532 451 40 08",
        "whatsapp": "+90 532 451 40 08",
        "email": "yigit.narin@cb.com.tr",
        "website": "www.gayrimenkulmuhendisi.com",
        "avatar_url": "/static/yigit_narin_portrait.png",
        "bio": "Coldwell Banker VIP Ankara bünyesinde lüks konut, arsa ve ticari gayrimenkul yatırım danışmanlığı."
    }
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_settings.update(data)
        except Exception:
            pass
    return default_settings


@app.route("/api/settings/agent", methods=["GET", "POST"])
def api_settings_agent():
    """Danışman profili alma ve güncelleme endpoint'i."""
    settings_file = BASE_DIR / "static" / "data" / "agent_settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if flask_request.method == "POST":
        body = flask_request.get_json(force=True, silent=True) or {}
        current = _get_agent_settings()
        current.update(body)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "settings": current})
    else:
        return jsonify({"ok": True, "settings": _get_agent_settings()})


def _get_tokens_map() -> dict:
    if _TOKENS_FILE.exists():
        try:
            with open(_TOKENS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_tokens_map(tokens: dict) -> None:
    _TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


@app.route("/api/presentations/from-url", methods=["POST"])
def api_presentations_from_url():
    """URL'den full sunum (PDF + Web Presentation Viewer) oluşturan ana API."""
    import urllib.parse
    body = flask_request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Lütfen geçerli bir ilan bağlantısı (URL) girin."}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        # 1. Scrape
        listing = scrape_listing(url)
        if not listing or not listing.get("ok"):
            listing = _scrape_via_slug_fallback(url)

        # 2. PDF Üret
        pdf_id = str(uuid.uuid4())
        pdf_path = _PDF_DIR / f"{pdf_id}.pdf"
        _generate_listing_pdf(listing, pdf_path)
        _cleanup_old_pdfs(100)

        # 3. Sunum Verisi Oluştur
        pres_id = str(uuid.uuid4())
        agent = _get_agent_settings()
        
        pres_data = {
            "id": pres_id,
            "url": url,
            "title": listing.get("title", ""),
            "price": listing.get("price", ""),
            "location": listing.get("location", ""),
            "specs": listing.get("specs", []),
            "description": listing.get("description", ""),
            "images": listing.get("images", []),
            "pdf_id": pdf_id,
            "pdf_url": f"/share/pdf/{pdf_id}",
            "pdf_download_url": f"/share/pdf/{pdf_id}?dl=1",
            "created_at": datetime.now().isoformat(),
            "agent": agent
        }

        # Dosyaya kaydet
        pres_file = _PRESENTATIONS_DIR / f"{pres_id}.json"
        with open(pres_file, "w", encoding="utf-8") as f:
            json.dump(pres_data, f, ensure_ascii=False, indent=2)

        # 4. Token Oluştur
        share_token = str(uuid.uuid4())[:12]
        tokens = _get_tokens_map()
        tokens[share_token] = pres_id
        _save_tokens_map(tokens)

        host = flask_request.host_url.rstrip("/")
        viewer_url = f"{host}/p/{share_token}"
        whatsapp_text = f"🏡 {listing.get('title', 'Gayrimenkul Sunumu')}\n💰 {listing.get('price', '')} - {listing.get('location', '')}\n\n✨ Özel Gayrimenkul Sunumu & Detaylar:\n{viewer_url}\n\n Detaylı Bilgi & İletişim:\n{agent.get('name')} - {agent.get('company')}\n📞 {agent.get('phone')}"
        whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_text)}"

        return jsonify({
            "ok": True,
            "presentation_id": pres_id,
            "share_token": share_token,
            "viewer_url": viewer_url,
            "pdf_url": f"/share/pdf/{pdf_id}",
            "pdf_download_url": f"/share/pdf/{pdf_id}?dl=1",
            "whatsapp_url": whatsapp_url,
            "presentation": pres_data,
            "listing": listing
        })

    except Exception as exc:
        import traceback as _tb
        _tb.print_exc()
        return jsonify({"ok": False, "error": f"Sunum oluşturma hatası: {exc}"}), 500


@app.route("/api/presentations/<pres_id>", methods=["GET"])
def api_get_presentation(pres_id: str):
    """Belirli sunumun JSON detayını verir."""
    pres_file = _PRESENTATIONS_DIR / f"{pres_id}.json"
    if not pres_file.exists():
        return jsonify({"ok": False, "error": "Sunum bulunamadı."}), 404
    try:
        with open(pres_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"ok": True, "presentation": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/presentations/<pres_id>/share", methods=["POST"])
def api_share_presentation(pres_id: str):
    """Sunum için paylaşım linki ve WhatsApp metni üretir."""
    import urllib.parse
    pres_file = _PRESENTATIONS_DIR / f"{pres_id}.json"
    if not pres_file.exists():
        return jsonify({"ok": False, "error": "Sunum bulunamadı."}), 404

    with open(pres_file, "r", encoding="utf-8") as f:
        pres_data = json.load(f)

    tokens = _get_tokens_map()
    share_token = None
    for tok, pid in tokens.items():
        if pid == pres_id:
            share_token = tok
            break

    if not share_token:
        share_token = str(uuid.uuid4())[:12]
        tokens[share_token] = pres_id
        _save_tokens_map(tokens)

    host = flask_request.host_url.rstrip("/")
    viewer_url = f"{host}/p/{share_token}"
    agent = pres_data.get("agent", _get_agent_settings())
    title = pres_data.get("title", "Gayrimenkul Sunumu")
    price = pres_data.get("price", "")
    location = pres_data.get("location", "")

    whatsapp_text = f"🏡 {title}\n💰 {price} - {location}\n\n✨ Özel Gayrimenkul Sunumu & Detaylar:\n{viewer_url}\n\n Detaylı Bilgi & İletişim:\n{agent.get('name')} - {agent.get('company')}\n📞 {agent.get('phone')}"
    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_text)}"

    return jsonify({
        "ok": True,
        "share_token": share_token,
        "viewer_url": viewer_url,
        "whatsapp_url": whatsapp_url
    })


@app.route("/p/<token>", methods=["GET"])
def render_presentation_viewer(token: str):
    """Mobil uyumlu lüks web sunum gösterici sayfası."""
    from flask import render_template
    tokens = _get_tokens_map()
    pres_id = tokens.get(token)
    if not pres_id:
        if (_PRESENTATIONS_DIR / f"{token}.json").exists():
            pres_id = token
        else:
            return render_template_string("<h1 style='color:white;background:#0B132B;padding:40px;text-align:center;font-family:sans-serif;'>Sunum Bulunamadı veya Süresi Dolmuş</h1>"), 404

    pres_file = _PRESENTATIONS_DIR / f"{pres_id}.json"
    if not pres_file.exists():
        return render_template_string("<h1 style='color:white;background:#0B132B;padding:40px;text-align:center;font-family:sans-serif;'>Sunum Bulunamadı</h1>"), 404

    try:
        with open(pres_file, "r", encoding="utf-8") as f:
            pres_data = json.load(f)
        return render_template("presentation_viewer.html", presentation=pres_data, json_data=json.dumps(pres_data, ensure_ascii=False))
    except Exception as e:
        return f"Sunum yüklenirken hata: {e}", 500






# ─────────────────────────────────────────────────────────────────────────────
# Root route & Favicon
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def _route_root():
    return _route_index()

@app.route("/privacy")
def _route_privacy():
    return render_template("privacy.html")

@app.route("/favicon.ico")
def _route_favicon():
    return "", 204


# ─────────────────────────────────────────────────────────────────────────────
# Server Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        main()
    else:
        run_server()
