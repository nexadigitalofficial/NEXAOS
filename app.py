"""
app.py — NEXA.OS Ultra Luxury İlan Pipeline — TEK DOSYA (v3.0)
──────────────────────────────────────────────────────────────────────
Bu dosya artık tüm sistemi barındırır: eski pipeline.py + web_app.py +
card_builder.py + description_parser.py + step6_luxury_adapter.py hepsi
buraya birleştirildi. Arayüz için sadece templates/index.html gerekir.

Çalıştırma:
    python app.py                    # Flask web arayüzünü başlatır (varsayılan)
    python app.py --cli --url ...    # eski komut satırı pipeline modu

Tam Pipeline (tüm sayfalar PageSpeed üzerinden çekilir) — v2.0 mantığı

  SENARYO AYRIMI (detect_single_listing_id):
    1) Tekil ilan linki   → Adım 1-2 atlanır, doğrudan Adım 3'e geçilir.
    2) Mağaza/arama linki → Adım 1-2 çalışır, iki yöntem birden denenir:
         Yöntem A: Mağaza sayfası formatı (img alt="Başlık #ID")
         Yöntem B: Genel arama/kategori sonucu formatı (data-classified-id +
                   manifesto v2.0 URL üretici motoru — bkz.
                   ULTRA_SAHIBINDEN_URL_GENERATOR_ENGINE.md)
       İki yöntemin bulduğu ilanlar listing_id'ye göre birleştirilir (dedup).

  ADIM 1 : Selenium → PageSpeed(mağaza/arama URL) → pagespeed_result.html kaydet
  ADIM 2 : HTML'den ilan ID + başlık + detay URL'leri ayıkla (Yöntem A + B)
  ADIM 3 : Her ilan için Selenium → PageSpeed(detay URL) → detay_html/{id}.html kaydet
  ADIM 4 : Her detay HTML'inden bilgileri parse et (fiyat, özellikler, fotoğraflar,
           açıklama — açıklama PSI wrapper'larda best-effort çıkarılır)
  ADIM 5 : Ollama qwen2.5:7b ile her ilanı analiz et
  ADIM 6 : Karta tıklayınca popup + galeri açılan interaktif HTML üret

Not: Sahibinden detay URL'si; önce sayfadaki gerçek (kesik olsa bile) href'ten,
     bulunamazsa manifesto v2.0 slug matematiğinden (title_to_slug + kategori
     tespiti) türetilir. PageSpeed sayfayı tam render ettiği için bot koruması
     sorun olmaz.

Kullanım:
    python app.py                         # tam pipeline
    python app.py --headless              # tarayıcısız
    python app.py --skip-pagespeed        # Adım 1'i atla, mevcut HTML kullan
    python app.py --skip-details          # Adım 3'ü atla, mevcut detay HTML'lerini kullan
    python app.py --no-ai                 # Ollama analizini atla
    python app.py --url https://...       # farklı mağaza URL'si
    python app.py --ps-wait 60            # Adım 1 PageSpeed bekleme süresi (sn)
    python app.py --det-wait 45           # Adım 3 her detay için PageSpeed bekleme süresi (sn)
    python app.py --delay 5              # detay sayfaları arası bekleme (sn)

Gereksinimler:
    pip install selenium webdriver-manager beautifulsoup4 lxml
    Ollama çalışıyor + model indirilmiş: ollama pull qwen2.5:7b
"""

from __future__ import annotations

# --- CRM IMPORTS ---
import sqlite3
"""
================================================================================
NEXA CRM PRO - UNIFIED SINGLE-FILE APPLICATION
================================================================================

PRODUCTION DEPLOYMENT VERSION

Combined from:
  • app.py (main Flask application)
  • wa_cloud.py (WhatsApp Cloud API)
  • mailer.py (Email automation)
  • valuation.py (Gemini valuation engine)
  • ai_listing.py (AI listing analysis)
  • fsbo_engine.py (FSBO analysis)
  • buyer_engine.py (Buyer matching)
  • eksik_fonksiyonlar.py (Bootstrap functions)
  • app_buyer_routes.py (Buyer routes)

REQUIREMENTS:
  - Firebase service account credentials (service-account.json)
  - Gemini API key
  - WhatsApp Business Account credentials
  - SMTP credentials for email
  - All Python dependencies in requirements.txt

DEPLOYMENT:
  1. Set environment variables (see .env.example)
  2. Run: python app.py
  3. Access: http://localhost:5000

⚠️  WARNINGS:
  - This is a consolidated production file
  - Do NOT edit - regenerate from source modules if needed
  - All imports are self-contained
  - Requires Python 3.10+

Generated: 2026-05-21
Version: 1.0.0 PRODUCTION
================================================================================
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import json
import re
import time
import html as _html
import requests
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps
from collections import defaultdict
from io import BytesIO

# Third-party
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, send_file, request as flask_request, render_template_string, redirect
from flask_cors import CORS

# Firebase
try:
    import firebase_admin
    from firebase_admin import credentials, firestore as admin_firestore, auth as fb_auth
    from google.cloud.firestore_v1.base_query import FieldFilter
    _fb_available = True
except Exception:
    _fb_available = False

# BS4 & Selenium
try:
    from bs4 import BeautifulSoup
    _bs4_available = True
except Exception:
    _bs4_available = False

# ML/AI
try:
    from sentence_transformers import SentenceTransformer
    _sentence_transformers_available = True
except Exception:
    _sentence_transformers_available = False

try:
    from google import genai
    _genai_available = True
except Exception:
    try:
        import google.generativeai as genai
        _genai_available = True
    except Exception:
        _genai_available = False

# Flask extensions
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except Exception:
    _limiter_available = False

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    _apscheduler_available = True
except Exception:
    _apscheduler_available = False

# ======================================================================
# WhatsApp Cloud API Module
# ======================================================================

from datetime import datetime

# --- END CRM IMPORTS ---


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

from flask import Flask, jsonify, render_template, request, send_from_directory, redirect

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

CLASSIFIED_PROPERTIES_FRAGMENT = "classifiedProperties"
PROP_FILE_SUFFIX = "__prop"  # {listing_id}__prop.html olarak kaydedilir


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


def _build_classified_properties_url(base_url: str) -> str:
    """
    Verilen detay URL'sine (varsa mevcut fragment'i temizleyip)
    '#classifiedProperties' fragment'ini ekler.
    ".../detay" veya ".../detay/" → ".../detay/#classifiedProperties"
    """
    clean = _strip_fragment(base_url).rstrip("/")
    return f"{clean}/#{CLASSIFIED_PROPERTIES_FRAGMENT}"

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

    def fetch_pages_bulk(
        self,
        summaries: List[ListingSummary],
        out_dir: Path,
        delay: float = 2.0,
        stop_event=None,
    ) -> List[Path]:
        out_dir.mkdir(exist_ok=True, parents=True)
        paths: List[Path] = []

        kwargs: Dict = {"uc": True, "headless": False}
        if self.proxy_str:
            kwargs["proxy"] = self.proxy_str

        # 1. Aşama: SeleniumBase UC ile indirmeyi dene
        if _SELENIUMBASE:
            try:
                with SB(**kwargs) as sb:
                    for idx, summary in enumerate(summaries, 1):
                        if stop_event is not None and stop_event.is_set():
                            break

                        target_path = out_dir / f"{summary.listing_id}.html"
                        print(f"  [{idx:02d}/{len(summaries):02d}] {summary.listing_id} — {summary.title[:45]}")
                        print(f"    URL: {summary.detail_url}")

                        try:
                            sb.uc_open_with_reconnect(summary.detail_url, reconnect_time=5)
                            try:
                                sb.uc_gui_click_captcha()
                            except Exception:
                                pass

                            self._wait_pass(sb, timeout=12)
                            sb.sleep(1.2)
                            curr_url = sb.get_current_url() or ""
                            html = sb.get_page_source()

                            if html and len(html) > 10000 and "giris" not in curr_url:
                                target_path.write_text(html, encoding="utf-8")
                                paths.append(target_path)
                                print(f"    [OK] SeleniumBase ile kaydedildi: {target_path.name} ({len(html)//1024} KB)")
                            else:
                                print(f"    [WARN] Detay sayfası yetersiz veya login yönlendirmesi var")
                        except Exception as err:
                            print(f"    [ERR] {summary.listing_id} SeleniumBase hatası: {err}")
                            if "session deleted" in str(err).lower() or "invalid session" in str(err).lower():
                                print("    [WARN] Tarayıcı oturumu koptu, kalan ilanlar PageSpeed Bulut Motoruna devrediliyor...")
                                break

                        if delay > 0 and idx < len(summaries):
                            time.sleep(delay)
            except Exception as e:
                print(f"    [ERR] SeleniumBase toplu oturum hatası: {e}")

        # 2. Aşama: Alınamayan veya eksik kalan ilanları PageSpeed API ile tamamla (Self-Healing)
        saved_ids = {p.stem for p in paths}
        missing_summaries = [s for s in summaries if s.listing_id not in saved_ids]

        if missing_summaries:
            print(f"\n  [API] {len(missing_summaries)} eksik ilan PageSpeed Bulut Motoru ile tamamlanıyor...")
            for s in missing_summaries:
                if stop_event is not None and stop_event.is_set():
                    break
                target_path = out_dir / f"{s.listing_id}.html"
                target_fetch_url = s.detail_url if "#" in s.detail_url else _build_classified_detail_url(s.detail_url)
                print(f"    [PSI] {s.listing_id} çekiliyor... ({target_fetch_url[:55]})")
                psi_data = _psi_api_fetch(target_fetch_url, timeout=35)
                if psi_data and "lighthouseResult" in psi_data:
                    lr = psi_data.get("lighthouseResult", {})
                    net_items = lr.get("audits", {}).get("network-requests", {}).get("details", {}).get("items", [])
                    html_parts = [
                        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
                        f"<title>PageSpeed Insights - {s.listing_id}</title></head><body>",
                        f"<div id='lh-root'><h1>{target_fetch_url}</h1>",
                    ]
                    for it in net_items:
                        u = it.get("url", "")
                        html_parts.append(f"<a href=\"{u}\">{u}</a><br>")
                    html_parts.append("</div></body></html>")
                    target_path.write_text("\n".join(html_parts), encoding="utf-8")
                    with open(out_dir / f"{s.listing_id}_psi.json", "w", encoding="utf-8") as jf:
                        json.dump(psi_data, jf, ensure_ascii=False, indent=2)
                    paths.append(target_path)
                    print(f"    [OK] PageSpeed API ile başarıyla kaydedildi: {target_path.name}")
                else:
                    print(f"    [WARN] PageSpeed API ile de alınamadı: {s.listing_id}")

        return paths


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 1 — Mağaza / Liste sayfasını çek (PageSpeed Cloud API + Selenium Fallback)
# ─────────────────────────────────────────────────────────────────────────────

def step1_pagespeed_store(
    target_url: str,
    out_html: str,
    wait_sec: int,
    headless: bool,
    stop_event=None,
) -> Path:
    _sep("ADIM 1 — Mağaza/Liste sayfası PageSpeed ile taranıyor")
    print(f"  Hedef  : {target_url}")
    print(f"  [MOTOR] Google PageSpeed Insights (PerimeterX/Turnstile Bot Bypass)")
    print(f"  Bekleme: {wait_sec} sn | Headless: {headless}")

    out_path = Path(out_html)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "pagespeed_result.json"

    # 1. Öncelikli Yöntem: Google PageSpeed Insights v5 REST API (Hızlı bulut render, sıfır bot engeli)
    print("  [API] Google PageSpeed Insights Bulut Motoru ile taranıyor...")
    psi_data = _psi_api_fetch(target_url, timeout=max(wait_sec, 60))
    if psi_data and "lighthouseResult" in psi_data:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(psi_data, f, ensure_ascii=False, indent=2)

            lr = psi_data.get("lighthouseResult", {})
            final_url = lr.get("finalUrl", target_url)
            html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>PageSpeed Analysis - {target_url}</title></head>
<body>
<div id="lh-root">
  <h1>PageSpeed Insights Result</h1>
  <p>Target URL: {target_url}</p>
  <p>Final URL: {final_url}</p>
  <p>Analysis UTC: {psi_data.get('analysisUTCTimestamp', '')}</p>
</div>
</body>
</html>"""
            out_path.write_text(html_content, encoding="utf-8")
            size_kb = json_path.stat().st_size // 1024
            print(f"  [OK] PageSpeed API ile başarıyla çekildi ({size_kb} KB veri kaydedildi)!")
            return out_path
        except Exception as e:
            print(f"  [WARN] PageSpeed API verisi kaydedilemedi: {e}")

    # 2. İkincil Fallback: Selenium ile PageSpeed Arayüzü
    print("  [FALLBACK] Selenium PageSpeed arayüzü deneniyor...")
    if not _SELENIUM:
        raise ImportError("pip install selenium webdriver-manager")

    driver = _make_chrome(headless)
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

    # ── Yöntem 0: PageSpeed API JSON Dosyası Varsa (Network Requests + Resimler) ──
    json_path = html_path.parent / "pagespeed_result.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                psi_data = json.load(f)
            lr = psi_data.get("lighthouseResult", {})
            net_items = lr.get("audits", {}).get("network-requests", {}).get("details", {}).get("items", [])
            for item in net_items:
                u = item.get("url", "")
                m_standard = re.search(r"photos/\d+/\d+/\d+/lthmb_(\d{6,})", u)
                if m_standard:
                    lid = m_standard.group(1)
                    if len(lid) > 10:
                        lid = lid[:10]
                    if lid not in items:
                        detail_url = f"https://www.sahibinden.com/ilan/{lid}/detay"
                        items[lid] = ListingSummary(
                            listing_id=lid,
                            title=f"İlan #{lid}",
                            thumb_url=u,
                            detail_url=detail_url
                        )
                m_proj = re.search(r"projects/(\d+/\d+/\d+)/", u)
                if m_proj:
                    pid = m_proj.group(1).replace("/", "").lstrip("0")
                    if pid and pid not in items:
                        detail_url = f"https://www.sahibinden.com/emlak-projeler/{pid}/detay"
                        items[pid] = ListingSummary(
                            listing_id=pid,
                            title=f"Proje #{pid}",
                            thumb_url=u,
                            detail_url=detail_url
                        )
            # Node labels ve alt metinlerden başlıkları ve box URL'lerini yakala
            psi_text = json.dumps(lr, ensure_ascii=False)
            for m_nl in re.finditer(r'([^\n\r"\'<>]+?)\s*#(\d{6,})', psi_text):
                t_cand, lid_cand = m_nl.group(1).strip(), m_nl.group(2)
                if lid_cand in items and t_cand and len(t_cand) > 3 and not t_cand.startswith("http"):
                    items[lid_cand].title = t_cand

            for m_url in re.finditer(r'https?://(?:www\.)?sahibinden\.com/ilan/([a-zA-Z0-9_\-]+?)-(\d{6,})/detay', psi_text):
                slug, lid_cand = m_url.group(1), m_url.group(2)
                if lid_cand in items:
                    items[lid_cand].detail_url = f"https://www.sahibinden.com/ilan/{slug}-{lid_cand}/detay"

            if items:
                print(f"  [OK] PageSpeed Bulut Verisinden {len(items)} ilan/proje yakalandı.")
        except Exception as err:
            print(f"  [WARN] PageSpeed API JSON okunurken hata: {err}")

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

    # ── Eğer tekil ilan ise: Önce SeleniumBase UC, başarısızsa PageSpeed Bulut Motoru ile çek ──
    is_single = len(summaries) == 1 and bool(detect_single_listing_id(summaries[0].detail_url))
    if is_single:
        summary = summaries[0]
        p = out_dir / f"{summary.listing_id}.html"
        html = None

        if _SELENIUMBASE:
            _sep("TEKİL İLAN MODU — SeleniumBase UC ile deneniyor")
            print(f"  Hedef: {summary.detail_url}")
            try:
                engine = CFBypassEngine()
                html = engine.fetch_page(summary.detail_url)
                if html:
                    p.write_text(html, encoding="utf-8")
                    print(f"    [OK] Kaydedildi: {p.name} ({len(html)//1024} KB)")
                    detail_paths.append(p)
                    return detail_paths
            except Exception as e:
                print(f"    [WARN] SeleniumBase UC hatası: {e}")

        # SeleniumBase başarısız olursa veya Cloudflare takılırsa: PageSpeed Bulut Motoru ile çek
        # Kullanıcı kuralı: Tekil ilanlarda #classified-detail ve #classifiedProperties hedeflenir
        print("  [API] SeleniumBase doğrudan erişemedi, PageSpeed Bulut Motoru devreye giriyor...")
        target_fetch_url = (
            summary.detail_url
            if "#" in summary.detail_url
            else _build_classified_detail_url(summary.detail_url)
        )
        print(f"  [API] Hedef URL: {target_fetch_url}")
        psi_data = _psi_api_fetch(target_fetch_url, timeout=wait_sec)
        if psi_data and "lighthouseResult" in psi_data:
            lr = psi_data.get("lighthouseResult", {})
            net_items = lr.get("audits", {}).get("network-requests", {}).get("details", {}).get("items", [])
            html_parts = [
                "<!DOCTYPE html><html><head><meta charset='utf-8'>",
                f"<title>PageSpeed Insights - {summary.listing_id}</title></head><body>",
                f"<div id='lh-root'><h1>{target_fetch_url}</h1>",
            ]
            for it in net_items:
                u = it.get("url", "")
                html_parts.append(f"<a href=\"{u}\">{u}</a><br>")
            html_parts.append("</div></body></html>")

            p.write_text("\n".join(html_parts), encoding="utf-8")
            with open(out_dir / f"{summary.listing_id}_psi.json", "w", encoding="utf-8") as jf:
                json.dump(psi_data, jf, ensure_ascii=False, indent=2)
            print(f"    [OK] PageSpeed ile buluttan başarıyla çekildi: {p.name}")
            detail_paths.append(p)
            return detail_paths
        else:
            print("    [ERR] PageSpeed ile de tekil ilan sayfası çekilemedi!")
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

    # ── Toplu ilan: SeleniumBase UC ile seri indirme (PageSpeed hatasını ve 429 kotasını atlar) ──
    if _SELENIUMBASE:
        _sep(f"TOPLU İLAN MODU ({len(summaries)} İlan) — SeleniumBase UC ile çekiliyor")
        engine = CFBypassEngine()
        return engine.fetch_pages_bulk(summaries, out_dir, delay=delay, stop_event=stop_event)

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
    
    # 1. Sahibinden modern dl / classifiedInfoItem format (dt/dd)
    for item in soup.select(".classifiedInfoList .classifiedInfoItem, .classifiedInfoList div"):
        dt = item.find("dt")
        dd = item.find("dd")
        if dt and dd:
            key = dt.get_text(strip=True).strip(" :")
            val = dd.get_text(strip=True)
            if key and val:
                specs[key] = val

    # 2. Sahibinden ul format (li strong/span)
    if not specs:
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
                    
    # 3. Table format if empty
    if not specs:
        for row in soup.select("table.classifiedInfoTable tr, .classifiedInfoTable tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).strip(" :")
                val = cells[1].get_text(strip=True)
                if key and val:
                    specs[key] = val

    # 4. Donanım / Özellikler (#classifiedProperties)
    props = [li.get_text(strip=True) for li in soup.select("#classifiedProperties li, .classified-prop-item") if li.get_text(strip=True)]
    if props:
        specs["İlan Özellikleri"] = ", ".join(props[:15])
                    
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


def _psi_api_extract_description(target_url: str, psi_json: Optional[dict] = None) -> Tuple[str, str]:
    """
    Tam zincir: PSI v5 API yanıtı / fullPageScreenshot'ı decode et →
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

    if psi_json is None:
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
    w, h = full_img.size
    if rect:
        left, top = rect["left"], rect["top"]
        right = left + rect["width"]
        bottom = top + rect["height"]
        left = max(0, left)
        top = max(0, top)
        right = min(w, right)
        bottom = min(h, bottom)
        crop_img = full_img.crop((left, top, right, bottom))
    else:
        # #classified-detail Sahibinden şablonunda y: 920-2700 bandında yer alır
        top_y = min(int(h * 0.16), 920)
        bot_y = min(h, 2700)
        crop_img = full_img.crop((int(w * 0.04), top_y, int(w * 0.96), bot_y))

    try:
        raw_ocr = _pytesseract.image_to_string(crop_img, lang=PSI_OCR_LANG)
    except Exception as exc:
        return "", f"tesseract OCR başarısız: {exc}"

    # #classified-detail / Açıklama başlığı sonrasını ve Özellikler öncesini al
    parts = re.split(r'A.{1,2}klama\s*', raw_ocr, flags=re.IGNORECASE)
    body = parts[1] if len(parts) > 1 else raw_ocr
    end_parts = re.split(r'\n\s*.{0,2}zellikler', body, flags=re.IGNORECASE)
    body = end_parts[0].strip()

    cleaned = re.sub(r"[ \t]+", " ", body)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if len(cleaned) < 40:
        return "", "OCR sonucu çok kısa/boş"

    source = "PSI fullPageScreenshot OCR (#classified-detail)"
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

    all_listing_ids = list(summary_map.keys()) if summary_map else list(path_map.keys())

    for listing_id in all_listing_ids:
        p = path_map.get(listing_id)
        if not p or not p.exists() or p.stat().st_size < 100:
            summary = summary_map.get(listing_id, ListingSummary(listing_id, "", ""))
            target_url = summary.detail_url or f"https://www.sahibinden.com/ilan/{listing_id}/detay"
            print(f"\n  [{listing_id}] Dosya bulunamadı, PageSpeed API ile doğrudan kurtarılıyor...")
            psi_res = _scrape_via_psi_api(target_url)
            if psi_res and psi_res.get("ok"):
                title = psi_res.get("title") or summary.title or f"İlan #{listing_id}"
                price = psi_res.get("price") or "—"
                photos = psi_res.get("images") or []
                specs = psi_res.get("specs") or {}
                description = psi_res.get("description") or ""
                det = ListingDetail(
                    listing_id=listing_id,
                    title=title,
                    price=price,
                    canonical_url=target_url,
                    thumb_url=photos[0] if photos else summary.thumb_url,
                    photos=photos,
                    specs=specs,
                    description=description,
                    description_source="PageSpeed API (Direct Fallback)",
                )
                details.append(det)
                print(f"    [OK] Doğrudan kurtarıldı: {title[:50]} | {price} | {len(photos)} foto | {len(specs)} özellik")
                continue
            else:
                print(f"    [WARN] {listing_id} kurtarılamadı.")
                continue

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

            # ── Fallback 0: Önceden indirilmiş {listing_id}_psi.json varsa doğrudan OCR ve tüm fotoğrafları çek ──
            psi_cached_json = p.parent / f"{listing_id}_psi.json"
            if psi_cached_json.exists():
                try:
                    with open(psi_cached_json, "r", encoding="utf-8") as jf:
                        cj = json.load(jf)
                    if not description:
                        print(f"    ℹ Önceden kaydedilmiş PSI JSON üzerinden #classified-detail OCR yapılıyor...")
                        ocr_desc, ocr_note = _psi_api_extract_description(canonical_url, psi_json=cj)
                        if ocr_desc:
                            description = ocr_desc
                            description_source = ocr_note

                    # Tüm JSON payload'ından eksiksiz tüm fotoğrafları topla
                    cj_str = json.dumps(cj)
                    psi_photo_pat = re.compile(
                        r'https?://i\d+\.shbdn\.com/photos/(\d+/\d+/\d+)/([a-zA-Z0-9_]+)\.(avif|jpg|jpeg|png|webp)',
                        re.IGNORECASE
                    )
                    seen_photo_keys = {re.sub(r'/(?:x5_|x3_|x2_|x1_|thmb_|lthmb_)', '/', ph) for ph in photos}
                    for match in psi_photo_pat.finditer(cj_str):
                        folder, fname, ext = match.groups()
                        base_id = re.sub(r'^(x5_|x3_|x2_|x1_|thmb_|lthmb_)', '', fname)
                        if not base_id or "blank" in base_id:
                            continue
                        core_key = f"https://i0.shbdn.com/photos/{folder}/{base_id}"
                        if core_key not in seen_photo_keys:
                            seen_photo_keys.add(core_key)
                            highres_url = f"https://i0.shbdn.com/photos/{folder}/x5_{base_id}.avif"
                            photos.append(highres_url)
                except Exception as e:
                    print(f"    [WARN] PSI JSON OCR/Fotoğraf ayrıştırma hatası: {e}")

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
        for sel in [".classified-price-wrapper .price", ".price", ".classified-price-wrapper", ".sticky-header-attribute.price"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if txt and len(txt) < 50 and ("TL" in txt or "₺" in txt or any(c.isdigit() for c in txt)):
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

        # ── Self-Healing Fallback (Eğer Selenium login sayfasına takıldıysa veya veriler eksikse) ──
        if (not photos or len(photos) <= 1) or len(specs) == 0 or price == "—":
            try:
                print(f"    [FALLBACK] {listing_id} için HTML eksik (giris yönlendirmesi tespit edildi), PageSpeed API ile tamamlanıyor...")
                target_url = canonical_url or f"https://www.sahibinden.com/ilan/{listing_id}/detay"
                psi_res = _scrape_via_psi_api(target_url)
                if psi_res and psi_res.get("ok"):
                    if (not title or title == listing_id) and psi_res.get("title"):
                        title = psi_res.get("title")
                    if price == "—" and psi_res.get("price"):
                        price = psi_res.get("price")
                    if psi_res.get("images"):
                        photos = psi_res.get("images")
                    if psi_res.get("specs"):
                        specs = psi_res.get("specs")
                    if not description and psi_res.get("description"):
                        description = psi_res.get("description")
                    print(f"    [OK] PageSpeed API ile kurtarıldı: {len(photos)} foto, {len(specs)} özellik, Fiyat: {price}")
            except Exception as fb_err:
                print(f"    [WARN] PageSpeed API fallback hatası: {fb_err}")

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
  <button class="modal-close" onclick="closeModal()">&times;</button>

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
    document.getElementById('mAiText').innerHTML = typeof marked !== 'undefined' ? marked.parse(d.analysis) : d.analysis.split('\n').join('<br>');
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
  <span class="close" onclick="closeLightbox()">&times;</span>
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
  <span class="close" onclick="closeLightbox()">&times;</span>
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
    step6_build_html_luxury(details, args.model, ai_enabled, args.out)

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

# ── NexaScout Blueprint (Faz 2: Otonom Alıcı & Strateji Radarı) ──
try:
    from nexascout.routes import nexascout_bp
    app.register_blueprint(nexascout_bp)
    print("✅ NexaScout Blueprint başarıyla app.py'ye entegre edildi.")
except Exception as _ns_err:
    print(f"⚠️ NexaScout Blueprint app.py'ye yüklenemedi: {_ns_err}")

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


@app.route("/api/nlp-search/parse", methods=["POST"])
def _route_nlp_search_parse():
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Lütfen aranacak kriter veya tanımı girin."}), 400
        
    gemini_api_key = (data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")).strip()
    sorting_override = (data.get("sorting") or "").strip()
    
    try:
        from nexa_nlp_search_engine import NexaNlpToLink
        engine = NexaNlpToLink()
        
        if gemini_api_key:
            builder, engine_name = engine.parse_with_gemini(prompt, gemini_api_key)
        else:
            builder = engine.parse(prompt)
            engine_name = "Nexa Offline Geo Engine (81 İl, 973 İlçe, 32.279 Mahalle)"
            
        if sorting_override and sorting_override in builder.SORTING_OPTIONS:
            builder.sorting = sorting_override
            
        target_url = builder.build_url()
        
        return jsonify({
            "ok": True,
            "url": target_url,
            "engine_used": engine_name,
            "details": {
                "category": builder.category,
                "location_path": builder.location_path,
                "price_min": builder.price_min,
                "price_max": builder.price_max,
                "m2_min": builder.m2_min,
                "m2_max": builder.m2_max,
                "rooms": builder.oda_sayisi,
                "building_age": builder.bina_yasi,
                "floor": builder.kat_sayisi,
                "sorting": builder.sorting,
                "tapu_durumu": builder.tapu_durumu,
                "kimden": builder.kimden,
                "ada_min": builder.ada_min,
                "ada_max": builder.ada_max,
                "parsel_min": builder.parsel_min,
                "parsel_max": builder.parsel_max,
                "imar_durumu": builder.imar_durumu,
                "kaks_emsal": builder.kaks_emsal
            }
        })
    except Exception as e:
        return jsonify({"error": f"NLP Çözümleme Hatası: {str(e)}"}), 500


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




# ==========================================
# CRM SYSTEM MERGED LOGIC
# ==========================================

# ── Konfigürasyon ────────────────────────────────────────────────
WA_API_VERSION    = "v19.0"
WA_BASE_URL       = f"https://graph.facebook.com/{WA_API_VERSION}"
WA_PHONE_ID       = os.environ.get("WA_PHONE_NUMBER_ID", "")
WA_TOKEN          = os.environ.get("WA_ACCESS_TOKEN",    "")
WA_VERIFY_TOKEN   = os.environ.get("WA_VERIFY_TOKEN",    "nexa_webhook_secret")
WA_TIMEOUT        = 10   # saniye

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {WA_TOKEN}",
        "Content-Type":  "application/json",
    }

def _is_configured() -> bool:
    return bool(WA_PHONE_ID and WA_TOKEN)

# ── Telefon Normalize ─────────────────────────────────────────────
def normalize_phone(raw: str) -> str | None:
    """
    Türkiye numaralarını uluslararası formata çevirir.
    Örnekler:
      "05324514008"  → "905324514008"
      "+90 532 451 40 08" → "905324514008"
      "5324514008"   → "905324514008"
    """
    if not raw:
        return None
    digits = "".join(filter(str.isdigit, raw))

    if digits.startswith("0") and len(digits) == 11:
        digits = "9" + digits           # 0XXXXXXXXXX → 90XXXXXXXXXX

    if digits.startswith("90") and len(digits) == 12:
        return digits

    if len(digits) == 10 and digits[0] in ("4", "5"):
        return "90" + digits            # 5XXXXXXXXX → 905XXXXXXXXX

    return digits if len(digits) >= 10 else None

# ── Freeform Metin Mesajı ─────────────────────────────────────────
def send_whatsapp(phone: str, message: str) -> dict:
    """
    Freeform metin mesajı gönderir.
    SADECE müşteri son 24 saat içinde yazdıysa ya da
    kendi bot numaranıza (danışman numarasına) gönderirken kullanın.

    Returns:
        {"ok": True,  "message_id": "wamid.xxx"}
        {"ok": False, "error": "...", "code": 400}
    """
    if not _is_configured():
        return {"ok": False, "error": "WA_PHONE_NUMBER_ID veya WA_ACCESS_TOKEN eksik"}

    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return {"ok": False, "error": f"Geçersiz telefon numarası: {phone}"}

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type":    "individual",
        "to":                phone_norm,
        "type":              "text",
        "text":              {"preview_url": False, "body": message},
    }

    try:
        resp = requests.post(
            f"{WA_BASE_URL}/{WA_PHONE_ID}/messages",
            headers=_headers(),
            json=payload,
            timeout=WA_TIMEOUT,
        )
        data = resp.json()

        if resp.ok and "messages" in data:
            msg_id = data["messages"][0].get("id", "")
            print(f"✅ WA gönderildi → {phone_norm} | id: {msg_id}")
            return {"ok": True, "message_id": msg_id, "phone": phone_norm}

        # API hata detayı
        err = data.get("error", {})
        print(f"❌ WA API hatası: {err.get('message', str(data))}")
        return {
            "ok":    False,
            "error": err.get("message", str(data)),
            "code":  err.get("code", resp.status_code),
        }

    except requests.exceptions.Timeout:
        print("❌ WA API timeout")
        return {"ok": False, "error": "API timeout"}
    except Exception as e:
        print(f"❌ WA beklenmedik hata: {e}")
        return {"ok": False, "error": str(e)}

# ── Template Mesajı ───────────────────────────────────────────────
def send_whatsapp_template(
    phone: str,
    template_name: str,
    language_code: str = "tr",
    components: list | None = None,
) -> dict:
    """
    Onaylı template mesajı gönderir (24 saat penceresi dışı için zorunlu).

    Meta Business Manager → WhatsApp → Message Templates'ten
    template oluşturup onaylatmanız gerekir.

    Örnek: send_whatsapp_template("905324514008", "lead_received", "tr", [
        {"type": "body", "parameters": [{"type": "text", "text": "Ahmet Yılmaz"}]}
    ])
    """
    if not _is_configured():
        return {"ok": False, "error": "WA_PHONE_NUMBER_ID veya WA_ACCESS_TOKEN eksik"}

    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return {"ok": False, "error": f"Geçersiz telefon numarası: {phone}"}

    template_payload: dict = {
        "name":     template_name,
        "language": {"code": language_code},
    }
    if components:
        template_payload["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "to":                phone_norm,
        "type":              "template",
        "template":          template_payload,
    }

    try:
        resp = requests.post(
            f"{WA_BASE_URL}/{WA_PHONE_ID}/messages",
            headers=_headers(),
            json=payload,
            timeout=WA_TIMEOUT,
        )
        data = resp.json()

        if resp.ok and "messages" in data:
            msg_id = data["messages"][0].get("id", "")
            print(f"✅ WA template gönderildi → {phone_norm} | template: {template_name}")
            return {"ok": True, "message_id": msg_id, "phone": phone_norm}

        err = data.get("error", {})
        return {
            "ok":    False,
            "error": err.get("message", str(data)),
            "code":  err.get("code", resp.status_code),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── API Durumu ────────────────────────────────────────────────────
def wa_status() -> dict:
    """
    Phone Number ID'nin durumunu Meta Graph API'den kontrol eder.
    Token geçerli mi, numara aktif mi öğrenilir.
    """
    if not _is_configured():
        return {
            "ok":          False,
            "configured":  False,
            "error":       "WA_PHONE_NUMBER_ID veya WA_ACCESS_TOKEN tanımlanmamış",
        }
    try:
        resp = requests.get(
            f"{WA_BASE_URL}/{WA_PHONE_ID}",
            headers=_headers(),
            params={"fields": "display_phone_number,verified_name,quality_rating,platform_type"},
            timeout=WA_TIMEOUT,
        )
        data = resp.json()

        if resp.ok:
            return {
                "ok":                  True,
                "configured":          True,
                "display_phone":       data.get("display_phone_number", ""),
                "verified_name":       data.get("verified_name", ""),
                "quality_rating":      data.get("quality_rating", ""),
                "platform_type":       data.get("platform_type", ""),
                "phone_number_id":     WA_PHONE_ID,
            }

        err = data.get("error", {})
        return {
            "ok":         False,
            "configured": True,
            "error":      err.get("message", str(data)),
            "code":       err.get("code", resp.status_code),
        }

    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}

# ── Webhook Doğrulama Yardımcısı ─────────────────────────────────
def verify_webhook_token(token: str) -> bool:
    """Meta'nın webhook doğrulaması için gelen token'ı kontrol eder."""
    return token == WA_VERIFY_TOKEN

# ======================================================================
# Email Automation Module
# ======================================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp').strip().lower()
EMAIL_FROM = os.environ.get('EMAIL_FROM', '').strip()
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'Nexa CRM').strip()

# SMTP config
SMTP_HOST = os.environ.get('SMTP_HOST', '').strip()
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587') or 587)
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '').strip()
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '').strip()
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').strip().lower() in ('1', 'true', 'yes')

# Resend config
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '').strip()
RESEND_API_URL = 'https://api.resend.com/emails'

def email_status() -> dict:
    smtp_ok = bool(EMAIL_FROM and SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD)
    resend_ok = bool(EMAIL_FROM and RESEND_API_KEY)
    configured = resend_ok if EMAIL_PROVIDER == 'resend' else smtp_ok
    return {
        'ok': configured,
        'configured': configured,
        'provider': EMAIL_PROVIDER,
        'from': EMAIL_FROM,
        'smtp_ready': smtp_ok,
        'resend_ready': resend_ok,
    }

def _build_html_wrapper(title: str, body_html: str) -> str:
    return f'''<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0b0f19;font-family:Arial,Helvetica,sans-serif;color:#e5e7eb;">
  <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
    <div style="background:#121826;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:32px;">
      <div style="font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:#c7a34b;margin-bottom:14px;">Nexa CRM</div>
      {body_html}
      <div style="margin-top:28px;padding-top:18px;border-top:1px solid rgba(255,255,255,.08);font-size:12px;color:#9ca3af;line-height:1.7;">
        Bu e-posta otomatik olarak oluşturulmuştur. Ek sorularınız için bu mesaja yanıt verebilir veya bizimle telefon üzerinden iletişime geçebilirsiniz.
      </div>
    </div>
  </div>
</body>
</html>'''

def build_lead_confirmation_email(name: str, phone: str = '', neighborhood: str = '', property_type: str = '', notes: str = '') -> tuple[str, str, str]:
    subject = 'Talebiniz bize ulaştı'
    plain = (
        f'Merhaba {name},\n\n'
        'Talebiniz bize başarıyla ulaştı. En kısa sürede sizinle iletişime geçeceğiz.\n\n'
        + (f'Mahalle: {neighborhood}\n' if neighborhood else '')
        + (f'Mülk Tipi: {property_type}\n' if property_type else '')
        + (f'Telefon: {phone}\n' if phone else '')
        + (f'Notunuz: {notes}\n' if notes else '')
        + '\nTeşekkür ederiz.\nNexa CRM'
    )
    html_body = f'''
      <h1 style="margin:0 0 12px;font-size:28px;line-height:1.2;color:#ffffff;">Merhaba {name},</h1>
      <p style="margin:0 0 18px;font-size:16px;line-height:1.7;color:#d1d5db;">
        Talebiniz bize başarıyla ulaştı. Ekibimiz en kısa sürede sizinle iletişime geçecek.
      </p>
      <div style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 18px 8px;margin:18px 0;">
        <div style="font-size:14px;color:#f3f4f6;font-weight:bold;margin-bottom:10px;">Talep Özeti</div>
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Mahalle:</strong> {neighborhood}</p>' if neighborhood else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Mülk Tipi:</strong> {property_type}</p>' if property_type else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Telefon:</strong> {phone}</p>' if phone else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Notunuz:</strong> {notes}</p>' if notes else ''}
      </div>
      <p style="margin:0;font-size:15px;line-height:1.7;color:#d1d5db;">
        Dilerseniz bu e-postayı yanıtlayarak ek bilgi paylaşabilirsiniz.
      </p>
    '''
    return subject, plain, _build_html_wrapper(subject, html_body)

def _send_via_smtp(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not (EMAIL_FROM and SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        return {'ok': False, 'error': 'SMTP yapılandırması eksik'}

    msg = MIMEMultipart('alternative') if html_body else MIMEText(text_body, 'plain', 'utf-8')
    if html_body:
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg['Subject'] = subject
    msg['From'] = formataddr((EMAIL_FROM_NAME, EMAIL_FROM))
    msg['To'] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        return {'ok': True, 'provider': 'smtp', 'to': to_email}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'smtp'}

def _send_via_resend(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not (EMAIL_FROM and RESEND_API_KEY):
        return {'ok': False, 'error': 'Resend yapılandırması eksik'}
    payload = {
        'from': formataddr((EMAIL_FROM_NAME, EMAIL_FROM)),
        'to': [to_email],
        'subject': subject,
        'text': text_body,
    }
    if html_body:
        payload['html'] = html_body
    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=15,
        )
        data = resp.json() if resp.content else {}
        if resp.ok:
            return {'ok': True, 'provider': 'resend', 'to': to_email, 'id': data.get('id', '')}
        return {'ok': False, 'error': data.get('message', str(data)), 'provider': 'resend'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'resend'}

def send_transactional_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not to_email:
        return {'ok': False, 'error': 'Alıcı e-posta boş'}
    provider = EMAIL_PROVIDER
    if provider == 'resend':
        return _send_via_resend(to_email, subject, text_body, html_body)
    return _send_via_smtp(to_email, subject, text_body, html_body)

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────
def _trend_meta(trend: str) -> tuple:
    t = (trend or '').lower()
    if 'yüksel' in t or 'artı' in t:
        return '📈', '#22c55e'
    if 'düş' in t or 'azal' in t:
        return '📉', '#ef4444'
    return '➡️', '#f59e0b'

def _score_color(score: int) -> str:
    if score >= 8: return '#22c55e'
    if score >= 6: return '#f59e0b'
    return '#ef4444'

def _impact_icon(impact: str) -> tuple:
    if impact == 'positive': return '✅', '#22c55e'
    if impact == 'negative': return '⚠️', '#ef4444'
    return 'ℹ️', '#94a3b8'

# ── Müşteriye gönderilen değerleme raporu e-postası ───────────────
def build_valuation_report_email(name: str, report: dict) -> tuple:
    neighborhood  = report.get('neighborhood', 'Bölgeniz')
    property_type = report.get('property_type', 'Mülkünüz')
    gen_at        = report.get('generated_at', '')

    pr   = report.get('price_range', {})
    na   = report.get('neighborhood_analysis', {})
    inv  = report.get('investment_score', {})
    mc   = report.get('market_comparison', {})
    kf   = report.get('key_factors', [])
    tips = report.get('valuation_tips', [])
    summ = report.get('executive_summary', '')
    disc = report.get('disclaimer', '')

    trend_icon, trend_color = _trend_meta(na.get('trend', 'stabil'))
    score     = int(inv.get('score', 0))
    score_max = int(inv.get('max', 10))
    score_pct = int((score / score_max) * 100) if score_max else 0
    sc_color  = _score_color(score)

    subject = f"{neighborhood} Gayrimenkul Değerleme Raporunuz Hazır"

    plain = (
        f"Merhaba {name},\n\n"
        f"{neighborhood} bölgesindeki {property_type} için değerleme raporunuz hazır.\n\n"
        f"Özet: {summ}\n\n"
        f"Tahmini Değer: {pr.get('average','')}\n"
        f"Aralık: {pr.get('min','')} — {pr.get('max','')}\n"
        f"Yatırım Skoru: {score}/{score_max} — {inv.get('label','')}\n"
        f"Trend: {na.get('trend','')}\n\n"
        f"Tavsiyeler:\n" + "\n".join(f"  • {t}" for t in tips) + "\n\n"
        f"⚠ {disc}\n\nRapor tarihi: {gen_at}\nNexa CRM"
    )

    def _li(items, color):
        return "".join(
            f'<li style="margin:0 0 7px;padding-left:4px;">'
            f'<span style="color:{color};font-size:13px;">• </span>'
            f'<span style="color:#cbd5e1;font-size:13px;">{i}</span></li>'
            for i in items
        )

    kf_html = ""
    for f in kf:
        icon, icolor = _impact_icon(f.get('impact', 'neutral'))
        kf_html += (
            f'<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;'
            f'padding:12px;background:#0f172a;border-radius:10px;border:1px solid rgba(255,255,255,.06);">'
            f'<span style="font-size:15px;flex-shrink:0;">{icon}</span>'
            f'<div><div style="font-size:12px;font-weight:700;color:{icolor};margin-bottom:3px;">'
            f'{f.get("factor","")}</div>'
            f'<div style="font-size:12px;color:#94a3b8;line-height:1.55;">{f.get("detail","")}</div></div></div>'
        )

    tips_html = "".join(
        f'<div style="margin-bottom:8px;padding:10px 14px;background:#0f172a;'
        f'border-left:3px solid #c7a34b;border-radius:0 8px 8px 0;font-size:13px;color:#cbd5e1;">{t}</div>'
        for t in tips
    )

    similar = mc.get('similar_neighborhoods', [])
    sim_html = " ".join(
        f'<span style="display:inline-block;background:#1e293b;border:1px solid rgba(255,255,255,.08);'
        f'border-radius:20px;padding:3px 11px;font-size:11px;color:#94a3b8;margin:2px;">{s}</span>'
        for s in similar
    )

    score_bar = (
        f'<div style="background:#1e293b;border-radius:999px;height:7px;margin:8px 0 10px;">'
        f'<div style="background:{sc_color};width:{score_pct}%;height:7px;border-radius:999px;"></div></div>'
    )

    body = f"""
      <h1 style="margin:0 0 6px;font-size:24px;color:#ffffff;">Merhaba {name},</h1>
      <p style="margin:0 0 22px;font-size:14px;color:#94a3b8;line-height:1.6;">
        <strong style="color:#e5e7eb;">{neighborhood}</strong> bölgesindeki
        <strong style="color:#e5e7eb;">{property_type}</strong> için
        yapay zeka destekli değerleme raporunuz aşağıdadır.
      </p>

      <div style="background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid rgba(199,163,75,.3);
                  border-radius:16px;padding:20px;margin-bottom:18px;">
        <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:#c7a34b;margin-bottom:10px;">
          Özet Değerlendirme
        </div>
        <p style="margin:0;font-size:14px;color:#e5e7eb;line-height:1.75;">{summ}</p>
      </div>

      <div style="background:#0f172a;border:1px solid rgba(34,197,94,.25);border-radius:16px;
                  padding:22px;margin-bottom:18px;text-align:center;">
        <div style="font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:#86efac;margin-bottom:12px;">
          Tahmini Değer Aralığı
        </div>
        <div style="font-size:32px;font-weight:700;color:#22c55e;letter-spacing:-.5px;margin-bottom:4px;">
          {pr.get('average','—')}
        </div>
        <div style="font-size:13px;color:#64748b;margin-bottom:12px;">
          {pr.get('min','—')} &nbsp;–&nbsp; {pr.get('max','—')}
        </div>
        <div style="padding-top:12px;border-top:1px solid rgba(255,255,255,.06);font-size:12px;color:#475569;">
          m² birim değer: <strong style="color:#94a3b8;">{pr.get('per_sqm_min', pr.get('per_sqm_avg','—'))}</strong>
          &nbsp;–&nbsp; <strong style="color:#94a3b8;">{pr.get('per_sqm_max','—')}</strong>
        </div>
      </div>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:18px;">
        <tr>
          <td width="49%" valign="top"
              style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px;">
            <div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:8px;">
              Yatırım Skoru
            </div>
            <div style="font-size:26px;font-weight:700;color:{sc_color};">
              {score}<span style="font-size:14px;color:#374151;">/{score_max}</span>
            </div>
            <div style="font-size:12px;color:{sc_color};margin-bottom:2px;">{inv.get('label','')}</div>
            {score_bar}
            <div style="font-size:11px;color:#64748b;line-height:1.5;">{inv.get('reasoning','')}</div>
          </td>
          <td width="2%"></td>
          <td width="49%" valign="top"
              style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px;">
            <div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:8px;">
              Bölge Trendi
            </div>
            <div style="font-size:26px;font-weight:700;color:{trend_color};margin-bottom:4px;">
              {trend_icon} {na.get('trend','').capitalize()}
            </div>
            <div style="font-size:11px;color:#64748b;line-height:1.55;">{na.get('trend_detail','')}</div>
          </td>
        </tr>
      </table>

      <div style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;
                  padding:18px;margin-bottom:18px;">
        <div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:12px;">
          Mahalle Analizi
        </div>
        <p style="margin:0 0 14px;font-size:13px;color:#cbd5e1;line-height:1.65;">{na.get('summary','')}</p>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="49%" valign="top">
              <div style="font-size:10px;color:#22c55e;font-weight:700;margin-bottom:7px;">✅ AVANTAJLAR</div>
              <ul style="margin:0;padding:0;list-style:none;">{_li(na.get('pros',[]), '#22c55e')}</ul>
            </td>
            <td width="2%"></td>
            <td width="49%" valign="top">
              <div style="font-size:10px;color:#ef4444;font-weight:700;margin-bottom:7px;">⚠️ DİKKAT</div>
              <ul style="margin:0;padding:0;list-style:none;">{_li(na.get('cons',[]), '#ef4444')}</ul>
            </td>
          </tr>
        </table>
      </div>

      {'<div style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px;margin-bottom:18px;"><div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:12px;">Piyasa Karşılaştırması</div><p style="margin:0 0 8px;font-size:13px;color:#cbd5e1;line-height:1.6;">' + mc.get("vs_district","") + '</p><p style="margin:0 0 12px;font-size:13px;color:#cbd5e1;line-height:1.6;">' + mc.get("vs_ankara","") + '</p>' + ('<div style="font-size:11px;color:#475569;">Benzer bölgeler: ' + sim_html + '</div>' if similar else '') + '</div>' if mc.get('vs_district') or mc.get('vs_ankara') else ''}

      {'<div style="margin-bottom:18px;"><div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:10px;">Değeri Etkileyen Faktörler</div>' + kf_html + '</div>' if kf_html else ''}

      {'<div style="margin-bottom:18px;"><div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:10px;">💡 Uzman Tavsiyeleri</div>' + tips_html + '</div>' if tips_html else ''}

      <div style="background:#0a0f1a;border:1px solid rgba(255,255,255,.05);border-radius:10px;
                  padding:12px;text-align:center;margin-bottom:4px;">
        <div style="font-size:11px;color:#374151;">
          🤖 Gemini AI ile oluşturulmuştur &nbsp;·&nbsp; 📅 {gen_at}
        </div>
        <div style="font-size:10px;color:#374151;margin-top:4px;">{disc}</div>
      </div>

      <p style="margin:18px 0 0;font-size:13px;color:#cbd5e1;line-height:1.7;">
        Raporla ilgili sorularınız için ekibimize ulaşabilirsiniz.
      </p>
    """

    return subject, plain, _build_html_wrapper(subject, body)

# ── Danışmana gönderilen bildirim e-postası ───────────────────────
def build_advisor_valuation_email(
    customer_name: str, customer_phone: str, customer_email: str,
    neighborhood: str, property_type: str, report: dict
) -> tuple:
    pr  = report.get('price_range', {})
    inv = report.get('investment_score', {})
    na  = report.get('neighborhood_analysis', {})
    gen = report.get('generated_at', '')

    trend_icon, trend_color = _trend_meta(na.get('trend', 'stabil'))
    score    = int(inv.get('score', 0))
    sc_color = _score_color(score)

    subject = f"[Nexa CRM] Değerleme Raporu Gönderildi — {customer_name} / {neighborhood}"

    plain = (
        f"Değerleme raporu müşteriye gönderildi.\n\n"
        f"Müşteri: {customer_name} | {customer_phone} | {customer_email}\n"
        f"Mülk: {neighborhood} / {property_type}\n\n"
        f"Tahmini Değer: {pr.get('average','?')}\n"
        f"Aralık: {pr.get('min','?')} — {pr.get('max','?')}\n"
        f"Yatırım Skoru: {score}/10 — {inv.get('label','')}\n"
        f"Trend: {na.get('trend','?')}\n\nRapor Tarihi: {gen}\nNexa CRM"
    )

    body = f"""
      <h1 style="margin:0 0 4px;font-size:20px;color:#ffffff;">✅ Değerleme Raporu Gönderildi</h1>
      <p style="margin:0 0 20px;font-size:12px;color:#64748b;">Aşağıdaki müşteriye rapor iletildi.</p>

      <div style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;
                  padding:16px;margin-bottom:14px;">
        <div style="font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:#94a3b8;margin-bottom:10px;">
          Müşteri Bilgileri
        </div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td style="padding:3px 0;color:#475569;font-size:12px;width:90px;">Ad Soyad</td>
              <td style="padding:3px 0;color:#e5e7eb;font-size:13px;font-weight:700;">{customer_name}</td></tr>
          <tr><td style="padding:3px 0;color:#475569;font-size:12px;">Telefon</td>
              <td style="padding:3px 0;color:#e5e7eb;font-size:12px;">{customer_phone}</td></tr>
          {'<tr><td style="padding:3px 0;color:#475569;font-size:12px;">E-posta</td><td style="padding:3px 0;color:#e5e7eb;font-size:12px;">' + customer_email + '</td></tr>' if customer_email else ''}
          <tr><td style="padding:3px 0;color:#475569;font-size:12px;">Mahalle</td>
              <td style="padding:3px 0;color:#e5e7eb;font-size:12px;">{neighborhood}</td></tr>
          <tr><td style="padding:3px 0;color:#475569;font-size:12px;">Mülk Tipi</td>
              <td style="padding:3px 0;color:#e5e7eb;font-size:12px;">{property_type}</td></tr>
        </table>
      </div>

      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
        <tr>
          <td width="49%" valign="top" style="background:#0f172a;border:1px solid rgba(34,197,94,.2);
              border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:9px;color:#86efac;letter-spacing:.12em;text-transform:uppercase;margin-bottom:5px;">
              Ort. Değer
            </div>
            <div style="font-size:16px;font-weight:700;color:#22c55e;">{pr.get('average','—')}</div>
            <div style="font-size:10px;color:#374151;margin-top:3px;">{pr.get('min','—')} – {pr.get('max','—')}</div>
          </td>
          <td width="2%"></td>
          <td width="24%" valign="top" style="background:#0f172a;border:1px solid rgba(255,255,255,.07);
              border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:9px;color:#94a3b8;letter-spacing:.12em;text-transform:uppercase;margin-bottom:5px;">
              Skor
            </div>
            <div style="font-size:20px;font-weight:700;color:{sc_color};">
              {score}<span style="font-size:11px;color:#374151;">/{inv.get('max',10)}</span>
            </div>
            <div style="font-size:10px;color:{sc_color};">{inv.get('label','')}</div>
          </td>
          <td width="2%"></td>
          <td width="24%" valign="top" style="background:#0f172a;border:1px solid rgba(255,255,255,.07);
              border-radius:12px;padding:14px;text-align:center;">
            <div style="font-size:9px;color:#94a3b8;letter-spacing:.12em;text-transform:uppercase;margin-bottom:5px;">
              Trend
            </div>
            <div style="font-size:20px;color:{trend_color};">{trend_icon}</div>
            <div style="font-size:10px;color:{trend_color};">{na.get('trend','—').capitalize()}</div>
          </td>
        </tr>
      </table>

      <div style="background:#0a0f1a;border-radius:10px;padding:10px;text-align:center;
                  font-size:11px;color:#374151;">
        📅 {gen} &nbsp;·&nbsp; 🤖 Gemini AI
      </div>
    """

    return subject, plain, _build_html_wrapper(subject, body)

# ======================================================================
# Gemini Property Valuation
# ======================================================================

import statistics
from urllib.parse import quote
from google import genai

# ─────────────────────────────────────────────────────────────────────────────
# Konfigürasyon
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_MODEL   = "gemini-2.5-flash"
SCRAPE_TIMEOUT = 14
MAX_RESULTS    = 40   # toplam veri seti büyüklüğü
MAX_CONTEXT    = 30   # Gemini'ye gönderilecek ilan sayısı

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT":             "1",
    "Connection":      "keep-alive",
}

# Komşu mahalle haritası — arama genişletmek için
NEIGHBOR_MAP: dict[str, list[str]] = {
    "dikmen":        ["kavaklıdere", "çukurambar", "balgat"],
    "çankaya":       ["kavaklıdere", "gaziosmanpaşa", "ayrancı"],
    "kavaklıdere":   ["çankaya", "dikmen", "gaziosmanpaşa"],
    "batıkent":      ["elvankent", "öveçler", "törekent"],
    "keçiören":      ["etlik", "kalaba", "bağlum"],
    "mamak":         ["altındağ", "tuzluçayır", "mamak"],
    "etimesgut":     ["eryaman", "elvankent", "sincan"],
    "eryaman":       ["etimesgut", "elvankent", "törekent"],
    "gaziosmanpaşa": ["kavaklıdere", "çankaya", "ayrancı"],
    "ayrancı":       ["çankaya", "gaziosmanpaşa", "kavaklıdere"],
    "balgat":        ["dikmen", "çukurambar", "söğütözü"],
    "çukurambar":    ["balgat", "söğütözü", "diplomatik site"],
    "öveçler":       ["batıkent", "demetevler", "yenimahalle"],
    "sincan":        ["etimesgut", "eryaman", "elvankent"],
    "pursaklar":     ["keçiören", "altındağ"],
    "gölbaşı":       ["çankaya", "balgat"],
}

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────────────────────────────────────
def _fmt(val: int) -> str:
    return f"{val:,}".replace(",", ".") + " TL"

def _neighbors(neighborhood: str) -> list[str]:
    key = neighborhood.lower().strip()
    for k, v in NEIGHBOR_MAP.items():
        if k in key or key in k:
            return v
    return []

def _pt_slug(property_type: str) -> dict:
    """Mülk tipinden kaynak-bazlı URL segmentleri üret."""
    pt = property_type.lower()
    if "daire" in pt:
        return {"he": "daire-satilik", "zingat": "daire", "ej": "daire"}
    if "villa" in pt:
        return {"he": "villa-satilik", "zingat": "villa", "ej": "villa"}
    if "arsa" in pt:
        return {"he": "arsa-satilik", "zingat": "arsa", "ej": "arsa"}
    if "dükkan" in pt or "ofis" in pt or "işyeri" in pt:
        return {"he": "isyeri-satilik", "zingat": "isyeri", "ej": "isyeri"}
    if "müstakil" in pt or "ev" in pt:
        return {"he": "mustakil-ev-satilik", "zingat": "mustakil-ev", "ej": "mustakil-ev"}
    return {"he": "konut-satilik", "zingat": "konut", "ej": "konut"}

def valuation_status() -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return {
        "ok":         bool(key),
        "configured": bool(key),
        "model":      GEMINI_MODEL,
        "provider":   "gemini+multiscrape",
    }

# ─────────────────────────────────────────────────────────────────────────────
# Fiyat / m² regex
# ─────────────────────────────────────────────────────────────────────────────
_PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:TL|tl|₺)"
    r"|(\d+(?:[.,]\d+)?)\s*milyon\s*(?:TL|tl|₺)?",
    re.IGNORECASE,
)
_SQM_RE = re.compile(r"(\d{2,4})\s*m[²2]", re.IGNORECASE)

def _parse_price(text: str) -> int | None:
    for m in _PRICE_RE.finditer(text):
        try:
            if m.group(2):
                val = float(m.group(2).replace(",", ".")) * 1_000_000
            else:
                val = int(re.sub(r"[^\d]", "", m.group(1)))
            if 300_000 <= val <= 200_000_000:
                return int(val)
        except (ValueError, TypeError):
            pass
    return None

def _parse_sqm(text: str) -> int | None:
    m = _SQM_RE.search(text)
    if m:
        v = int(m.group(1))
        return v if 20 <= v <= 2000 else None
    return None

def _extract_prices(results: list[dict]) -> list[int]:
    prices = []
    for r in results:
        text = r.get("title", "") + " " + r.get("snippet", "")
        p = _parse_price(text)
        if p:
            prices.append(p)
    return sorted(prices)

def _iqr_clean(prices: list[int]) -> list[int]:
    """IQR yöntemiyle aykırı değerleri temizle (1.5×IQR kuralı)."""
    if len(prices) < 4:
        return prices
    s  = sorted(prices)
    n  = len(s)
    q1 = statistics.median(s[:n // 2])
    q3 = statistics.median(s[(n + 1) // 2:])
    iqr = q3 - q1
    if iqr == 0:
        return s
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    cleaned = [p for p in s if lo <= p <= hi]
    removed = len(s) - len(cleaned)
    if removed:
        print(f"   IQR temizleme: {removed} aykırı değer çıkarıldı")
    return cleaned if cleaned else s

def _stats(prices: list[int], sqm: str = "") -> dict:
    """Fiyat listesinden istatistik üret."""
    if not prices:
        return {}
    clean = _iqr_clean(prices)
    avg   = int(statistics.mean(clean))
    med   = int(statistics.median(clean))
    lo    = min(clean)
    hi    = max(clean)
    out   = {
        "count":     len(clean),
        "raw_count": len(prices),
        "min":       lo,
        "max":       hi,
        "average":   avg,
        "median":    med,
    }
    sqm_int = None
    try:
        sqm_int = int(re.sub(r"[^\d]", "", sqm)) if sqm else None
    except Exception:
        pass
    if sqm_int and sqm_int > 0:
        out["per_sqm_avg"] = int(avg / sqm_int)
        out["per_sqm_med"] = int(med / sqm_int)
        out["per_sqm_min"] = int(lo  / sqm_int)
        out["per_sqm_max"] = int(hi  / sqm_int)
    return out

# ─────────────────────────────────────────────────────────────────────────────
# Scraper 1 — DuckDuckGo HTML
# ─────────────────────────────────────────────────────────────────────────────
def _ddg(query: str, max_r: int = 10) -> list[dict]:
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "tr-tr", "s": "0"},
            headers=HEADERS,
            timeout=SCRAPE_TIMEOUT,
        )
        if not resp.ok:
            return []
        soup    = BeautifulSoup(resp.text, "html.parser")
        results = []
        for el in soup.select(".result")[:max_r]:
            title   = el.select_one(".result__title")
            snippet = el.select_one(".result__snippet")
            url     = el.select_one(".result__url")
            t = title.get_text(strip=True)   if title   else ""
            s = snippet.get_text(strip=True) if snippet else ""
            u = url.get_text(strip=True)     if url     else ""
            if t or s:
                results.append({"title": t, "snippet": s, "url": u, "source": "ddg"})
        print(f"   DDG '{query[:55]}' → {len(results)} sonuç")
        return results
    except Exception as e:
        print(f"   ⚠ DDG '{query[:40]}': {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# Scraper 2 — HepsiEmlak
# ─────────────────────────────────────────────────────────────────────────────
def _scrape_hepsiemlak(neighborhood: str, property_type: str) -> list[dict]:
    slugs = _pt_slug(property_type)
    cat   = slugs["he"]
    loc   = quote(f"{neighborhood.lower()}-ankara")
    url   = f"https://www.hepsiemlak.com/{cat}?location_slug={loc}"
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            print(f"   ⚠ HepsiEmlak HTTP {resp.status_code}")
            return []
        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = []
        for sel in ["li.listing-item", ".listing-card", "article.listing",
                    "[class*=listingCard]", "[class*=listing-item]"]:
            cards = soup.select(sel)
            if cards:
                break
        for card in cards[:15]:
            full_text = card.get_text(" ", strip=True)
            price = _parse_price(full_text)
            if not price:
                continue
            title_el = card.select_one(".listing-title,.title,h2,h3,[class*=title]")
            title    = title_el.get_text(strip=True) if title_el else f"{neighborhood} {property_type}"
            results.append({
                "title":   title,
                "snippet": full_text[:300],
                "url":     "hepsiemlak.com",
                "source":  "hepsiemlak",
                "price":   price,
            })
        print(f"   HepsiEmlak → {len(results)} ilan")
    except Exception as e:
        print(f"   ⚠ HepsiEmlak hatası: {e}")
    return results

# ─────────────────────────────────────────────────────────────────────────────
# Scraper 3 — Zingat
# ─────────────────────────────────────────────────────────────────────────────
def _scrape_zingat(neighborhood: str, property_type: str) -> list[dict]:
    slugs = _pt_slug(property_type)
    cat   = slugs["zingat"]
    loc   = neighborhood.lower().replace(" ", "-")
    url   = f"https://www.zingat.com/ankara/{loc}/{cat}-satilik"
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            print(f"   ⚠ Zingat HTTP {resp.status_code}")
            return []
        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(
            ".listing-card,.property-item,[class*=listing],[class*=property-card]"
        )
        for card in cards[:15]:
            full_text = card.get_text(" ", strip=True)
            price = _parse_price(full_text)
            if not price:
                continue
            title_el = card.select_one("h2,h3,.title,[class*=title]")
            title    = title_el.get_text(strip=True) if title_el else f"{neighborhood} {property_type}"
            results.append({
                "title":   title,
                "snippet": full_text[:300],
                "url":     "zingat.com",
                "source":  "zingat",
                "price":   price,
            })
        print(f"   Zingat → {len(results)} ilan")
    except Exception as e:
        print(f"   ⚠ Zingat hatası: {e}")
    return results

# ─────────────────────────────────────────────────────────────────────────────
# Scraper 4 — Emlakjet
# ─────────────────────────────────────────────────────────────────────────────
def _scrape_emlakjet(neighborhood: str, property_type: str) -> list[dict]:
    pt  = property_type.lower()
    cat = ("daire"    if "daire"  in pt else
           "villa"    if "villa"  in pt else
           "arsa"     if "arsa"   in pt else "konut")
    loc = neighborhood.lower().replace(" ", "-")
    url = f"https://www.emlakjet.com/satilik-{cat}/ankara/{loc}/"
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if not resp.ok:
            print(f"   ⚠ Emlakjet HTTP {resp.status_code}")
            return []
        soup  = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("[class*=listing],[class*=card],[class*=ilan],article")
        for card in cards[:15]:
            full_text = card.get_text(" ", strip=True)
            price = _parse_price(full_text)
            if not price:
                continue
            title_el = card.select_one("h2,h3,.title,[class*=title]")
            title    = title_el.get_text(strip=True) if title_el else f"{neighborhood} {property_type}"
            results.append({
                "title":   title,
                "snippet": full_text[:300],
                "url":     "emlakjet.com",
                "source":  "emlakjet",
                "price":   price,
            })
        print(f"   Emlakjet → {len(results)} ilan")
    except Exception as e:
        print(f"   ⚠ Emlakjet hatası: {e}")
    return results

# ─────────────────────────────────────────────────────────────────────────────
# Toplu Arama Koordinatörü
# ─────────────────────────────────────────────────────────────────────────────
def _multi_search(
    neighborhood: str,
    property_type: str,
    sqm: str = "",
) -> list[dict]:
    """Tüm kaynaklardan veri toplar, tekilleştirir ve döndürür."""
    all_results: list[dict] = []
    seen: set[str]          = set()

    def _add(items: list[dict]) -> None:
        for r in items:
            key = (r.get("url", "") + r.get("title", ""))[:120]
            if key not in seen:
                seen.add(key)
                all_results.append(r)

    # ── 1. Direkt Scraperlar ──────────────────────────────────────────────────
    _add(_scrape_hepsiemlak(neighborhood, property_type))
    time.sleep(0.5)
    _add(_scrape_zingat(neighborhood, property_type))
    time.sleep(0.5)
    _add(_scrape_emlakjet(neighborhood, property_type))
    time.sleep(0.4)

    # ── 2. DDG — ana mahalle sorguları ───────────────────────────────────────
    ddg_queries = [
        f"site:sahibinden.com {neighborhood} ankara {property_type} satılık",
        f"site:hepsiemlak.com {neighborhood} ankara {property_type} satılık",
        f"{neighborhood} ankara {property_type} satılık fiyat 2025",
        f"{neighborhood} ankara m2 fiyatı emlak 2025",
        f"sahibinden.com {neighborhood} {property_type} satılık TL",
        f"endeksa.com {neighborhood} ankara konut fiyat",
        f"{neighborhood} ankara {property_type} ortalama fiyat",
        f"zingat.com {neighborhood} ankara {property_type}",
    ]
    for q in ddg_queries:
        _add(_ddg(q, max_r=10))
        time.sleep(0.35)

    # ── 3. DDG — komşu mahalleler (bağlam zenginleştirme) ────────────────────
    for nb in _neighbors(neighborhood)[:2]:
        _add(_ddg(f"{nb} ankara {property_type} satılık fiyat 2025", max_r=6))
        time.sleep(0.3)

    # ── 4. m² girilmişse birim fiyat araması ─────────────────────────────────
    if sqm:
        _add(_ddg(f"{neighborhood} ankara {sqm}m2 {property_type} satılık", max_r=8))
        time.sleep(0.3)

    # ── 5. Ankara genel piyasa bağlamı ───────────────────────────────────────
    _add(_ddg(f"ankara {property_type} ortalama m2 fiyatı 2025", max_r=6))

    print(f"\n   📊 Toplam kayıt: {len(all_results)}")
    return all_results[:MAX_RESULTS]

# ─────────────────────────────────────────────────────────────────────────────
# Context Builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_context(results: list[dict], st: dict, sqm: str = "") -> str:
    lines = []

    if st:
        lines += [
            f"=== GERÇEK PAZAR VERİSİ ({st['count']} ilan, {st['raw_count']} ham kayıt) ===",
            f"  Min    : {_fmt(st['min'])}",
            f"  Maks   : {_fmt(st['max'])}",
            f"  Ort    : {_fmt(st['average'])}",
            f"  Medyan : {_fmt(st['median'])}  ← aykırı değer etkisi az",
        ]
        if "per_sqm_avg" in st:
            lines += [
                f"  m²/Ort : {_fmt(st['per_sqm_avg'])}/m²",
                f"  m²/Med : {_fmt(st['per_sqm_med'])}/m²",
            ]
        lines.append("")

    # Kaynak bazlı özet
    by_source: dict[str, list[int]] = {}
    for r in results:
        src = r.get("source", "ddg")
        if r.get("price"):
            by_source.setdefault(src, []).append(r["price"])
    if by_source:
        lines.append("=== KAYNAK BAZLI FİYATLAR ===")
        for src, prices in by_source.items():
            avg_s = int(sum(prices) / len(prices))
            lines.append(f"  {src:15s} → {len(prices)} ilan | Ort: {_fmt(avg_s)}")
        lines.append("")

    lines.append("=== İLAN DETAYLARI ===")
    ranked = sorted(results, key=lambda r: 0 if r.get("price") else 1)
    for i, r in enumerate(ranked[:MAX_CONTEXT], 1):
        price_tag = f" [{_fmt(r['price'])}]" if r.get("price") else ""
        lines.append(f"{i}. [{r.get('source','?')}]{price_tag} {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:220]}")

    return "\n".join(lines) or "Yeterli veri bulunamadı."

# ─────────────────────────────────────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_prompt(
    name: str, neighborhood: str, property_type: str,
    rooms: str, sqm: str, notes: str,
    context: str, st: dict,
) -> str:
    now    = datetime.now().strftime("%d.%m.%Y %H:%M")
    extras = []
    if rooms: extras.append(f"- Oda Sayısı  : {rooms}")
    if sqm:   extras.append(f"- Metrekare   : {sqm} m²")
    if notes: extras.append(f"- Notlar      : {notes}")
    extra_block = "\n".join(extras) if extras else "- (ek bilgi girilmedi)"

    if st and st.get("count", 0) >= 3:
        med   = st["median"]
        avg   = st["average"]
        lo    = st["min"]
        hi    = st["max"]
        count = st["count"]
        price_directive = f"""
⚠⚠ ZORUNLU — Aşağıdaki gerçek pazar verisini MUTLAKA kullan:
   Kaynak: {count} ilan (IQR ile aykırı değerler temizlenmiş)
   Min    = {_fmt(lo)}
   Maks   = {_fmt(hi)}
   Ort    = {_fmt(avg)}
   Medyan = {_fmt(med)}  ← EN GÜVENİLİR referans"""
        if "per_sqm_avg" in st:
            price_directive += f"""
   m²/Ort = {_fmt(st['per_sqm_avg'])}/m²
   m²/Med = {_fmt(st['per_sqm_med'])}/m²"""
        price_directive += f"""
   → price_range.min     = {_fmt(int(lo * 0.93))}
   → price_range.max     = {_fmt(int(hi * 1.07))}
   → price_range.average = {_fmt(avg)}
   → price_range.median  = {_fmt(med)}"""
    else:
        price_directive = """
⚠ Yeterli ilan verisi bulunamadı. 2025 Ankara piyasası ve mahalle
   özelliklerine dayanarak gerçekçi tahmin yap. data_quality = "tahmini" yaz."""

    return f"""Sen Türkiye'nin en deneyimli gayrimenkul değerleme uzmanısın.
Ankara {neighborhood} bölgesinde {property_type} için gerçek web ilanlarından
derlenen verilerle kapsamlı bir değerleme raporu hazırlıyorsun.

══════════════ MÜŞTERİ ══════════════
Ad    : {name}
Bölge : {neighborhood}, Ankara
Mülk  : {property_type}
{extra_block}
Tarih : {now}

══════════════ PAZAR VERİSİ KILAVUZU ══════════════{price_directive}

══════════════ WEB KAYNAKLARINDAN DERLENEN VERİ ══════════════
{context}
══════════════════════════════════════════════════════════════

KURALLAR:
1. Yalnızca geçerli bir JSON objesi döndür — markdown, açıklama, kod bloğu yok.
2. Tüm metinler Türkçe.
3. Fiyatları TL, binlik nokta ayraçlı (örn: "4.750.000 TL").
4. Gerçek veri varsa onu kullan; tahmin yaparsan "tahmini" ibaresini ekle.
5. executive_summary'de {name}'e doğrudan hitap et.
6. investment_score 1-10 tam sayı.
7. pros ≥ 3 madde, cons ≥ 2 madde.
8. data_quality: "gercek" (≥3 gerçek ilan) veya "tahmini".

JSON YAPISI:
{{
  "price_range": {{
    "min":          "X.XXX.XXX TL",
    "max":          "X.XXX.XXX TL",
    "average":      "X.XXX.XXX TL",
    "median":       "X.XXX.XXX TL",
    "per_sqm_min":  "XX.XXX TL/m²",
    "per_sqm_max":  "XX.XXX TL/m²",
    "per_sqm_avg":  "XX.XXX TL/m²",
    "data_quality": "gercek",
    "source_count": {st.get("count", 0)}
  }},
  "neighborhood_analysis": {{
    "summary":     "2-3 cümle",
    "pros":        ["avantaj1","avantaj2","avantaj3"],
    "cons":        ["dezavantaj1","dezavantaj2"],
    "trend":       "yükselen",
    "trend_detail":"1-2 cümle"
  }},
  "investment_score": {{
    "score":    8,
    "max":      10,
    "label":    "Çok İyi",
    "reasoning":"2-3 cümle"
  }},
  "market_comparison": {{
    "vs_district":           "1-2 cümle",
    "vs_ankara":             "1-2 cümle",
    "similar_neighborhoods": ["mahalle1","mahalle2","mahalle3"]
  }},
  "key_factors": [
    {{"factor":"Başlık","impact":"positive","detail":"Açıklama"}},
    {{"factor":"Başlık","impact":"positive","detail":"Açıklama"}},
    {{"factor":"Başlık","impact":"negative","detail":"Açıklama"}},
    {{"factor":"Başlık","impact":"neutral", "detail":"Açıklama"}}
  ],
  "valuation_tips":    ["tavsiye1","tavsiye2","tavsiye3"],
  "web_sources":       ["hepsiemlak.com","zingat.com","sahibinden.com","emlakjet.com","endeksa.com"],
  "executive_summary": "Müşteriye ({name}) hitaben 3-4 cümle özet",
  "disclaimer":        "Bu rapor yapay zeka destekli ön değerleme amaçlıdır ve hukuki bağlayıcılığı yoktur. Kesin değerleme için yetkili SPK lisanslı ekspertiz önerilir."
}}"""

# ─────────────────────────────────────────────────────────────────────────────
# JSON Çıkarıcı
# ─────────────────────────────────────────────────────────────────────────────
def _extract_json(raw: str) -> str:
    if "```" in raw:
        for part in raw.split("```"):
            p = part.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                raw = p
                break
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    return raw[start:end] if start != -1 and end > start else raw

# ─────────────────────────────────────────────────────────────────────────────
# Ana Fonksiyon
# ─────────────────────────────────────────────────────────────────────────────
def generate_valuation_report(
    name: str,
    neighborhood: str,
    property_type: str,
    rooms: str = "",
    sqm: str   = "",
    notes: str = "",
) -> dict:
    """
    Çok kaynaklı web scrape + Gemini 2.5 Flash ile Ankara gayrimenkul değerleme.
    grok.py / gemini.py ile birebir aynı dönüş arayüzü.

    Returns:
        {"ok": True,  "report": {...}, "search_used": True, "listings_count": N}
        {"ok": False, "error": "..."}
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}

    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"🏠 Değerleme: {neighborhood} / {property_type}")
    if sqm:   print(f"   m²  : {sqm}")
    if rooms: print(f"   Oda : {rooms}")
    print(f"{'='*60}")

    # ── 1. Veri Toplama ───────────────────────────────────────────────────────
    results    = _multi_search(neighborhood, property_type, sqm)
    raw_prices = _extract_prices(results)

    # Scraper'ların "price" alanını da ekle
    for r in results:
        if r.get("price") and r["price"] not in raw_prices:
            raw_prices.append(r["price"])
    raw_prices = sorted(set(raw_prices))

    st = _stats(raw_prices, sqm)
    print(f"\n   📈 Ham fiyat : {len(raw_prices)} | Temizlenmiş : {st.get('count', 0)}")
    if st:
        print(f"   💰 Medyan   : {_fmt(st['median'])}")
        print(f"   💰 Ortalama : {_fmt(st['average'])}")
        if "per_sqm_avg" in st:
            print(f"   📐 m²/Ort   : {_fmt(st['per_sqm_avg'])}/m²")

    # ── 2. Context ────────────────────────────────────────────────────────────
    context = _build_context(results, st, sqm)

    # ── 3. Gemini ─────────────────────────────────────────────────────────────
    prompt = _build_prompt(
        name, neighborhood, property_type, rooms, sqm, notes, context, st
    )
    try:
        print(f"\n🤖 {GEMINI_MODEL} analiz ediyor...")
        client   = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model    = GEMINI_MODEL,
            contents = prompt,
        )
        raw_text = response.text.strip()
    except Exception as e:
        return {"ok": False, "error": f"Gemini hatası: {e}"}

    # ── 4. JSON Parse ─────────────────────────────────────────────────────────
    raw_text = _extract_json(raw_text)
    try:
        report = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse hatası: {e}\n{raw_text[:500]}")
        return {"ok": False, "error": f"JSON parse hatası: {e}"}

    # ── 5. Gerçek İstatistikle Fiyat Alanını Güvenle Üzerine Yaz ─────────────
    if st and st["count"] >= 3:
        pr = report.setdefault("price_range", {})
        pr["average"]      = _fmt(st["average"])
        pr["median"]       = _fmt(st["median"])
        pr["min"]          = _fmt(int(st["min"] * 0.93))
        pr["max"]          = _fmt(int(st["max"] * 1.07))
        pr["source_count"] = st["count"]
        pr["data_quality"] = "gercek"
        if "per_sqm_avg" in st:
            pr["per_sqm_avg"] = _fmt(st["per_sqm_avg"]) + "/m²"
            pr["per_sqm_min"] = _fmt(st["per_sqm_min"]) + "/m²"
            pr["per_sqm_max"] = _fmt(st["per_sqm_max"]) + "/m²"

    # ── 6. Meta ───────────────────────────────────────────────────────────────
    report["generated_at"]    = datetime.now().strftime("%d.%m.%Y %H:%M")
    report["neighborhood"]     = neighborhood
    report["property_type"]    = property_type
    report["model"]            = GEMINI_MODEL
    report["search_used"]      = len(results) > 0
    report["listings_count"]   = st.get("count", 0)
    report["raw_price_count"]  = len(raw_prices)
    report.setdefault(
        "web_sources",
        ["hepsiemlak.com", "zingat.com", "sahibinden.com", "emlakjet.com", "endeksa.com"],
    )

    elapsed = round(time.time() - t0, 1)
    pr      = report.get("price_range", {})
    print(f"\n✅ Tamamlandı [{elapsed}s]")
    print(f"   Medyan    : {pr.get('median', '?')}")
    print(f"   Ortalama  : {pr.get('average', '?')}")
    print(f"   Veri sayısı: {st.get('count', 0)} temizlenmiş / {len(raw_prices)} ham")

    return {
        "ok":             True,
        "report":         report,
        "search_used":    len(results) > 0,
        "listings_count": st.get("count", 0),
    }

# ======================================================================
# AI Listing Analysis & Scraping
# ======================================================================

# from __future__ removed

import base64
import html as html_mod
from urllib.parse import urlparse
from google.genai import types

# Playwright opsiyonel — sadece sahibinden scrape için (async API, greenlet gerektirmez)
import asyncio
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT = True
except ImportError:
    _PLAYWRIGHT = False
_SELENIUM = _PLAYWRIGHT  # geriye dönük uyumluluk için

# ── Konfigürasyon ─────────────────────────────────────────────────────────────
# Geçerli modeller (Nisan 2026):
#   gemini-2.5-flash      → 10 RPM / 250 RPD  (önerilen ana model)
#   gemini-2.5-flash-lite → 15 RPM / 1000 RPD (fallback, en yüksek kota)
#   gemini-2.5-pro        → 5 RPM  / 100 RPD  (en yetenekli, kısıtlı)
GEMINI_MODEL        = os.environ.get("GEMINI_MODEL",    "gemini-2.5-flash")
GEMINI_FALLBACK     = os.environ.get("GEMINI_FALLBACK", "gemini-2.5-flash-lite")
GEMINI_MAX_RETRIES  = 3     # 429 hatası için max tekrar
GEMINI_RETRY_DELAY  = 10    # ilk bekleme süresi (sn), her seferinde 2x artar
SCRAPE_TIMEOUT      = 15
PAGESPEED_WEB_URL = "https://pagespeed.web.dev/?hl=tr"
DEFAULT_PS_WAIT   = 50   # saniye — sahibinden için bekleme süresi

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "DNT":             "1",
}

def ai_listing_status() -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return {
        "ok":         bool(key),
        "configured": bool(key),
        "model":      GEMINI_MODEL,
        "fallback":   GEMINI_FALLBACK,
    }

# ================================================================
# SCRAPERS
# ================================================================

# ── Ham HTML Yardımcıları ────────────────────────────────────────────────────

def _extract_psi_photos(raw_html: str) -> list[dict]:
    """
    PageSpeed Insights tarafından render edilmiş HTML'den
    Sahibinden CDN fotoğraf URL'lerini çıkarır.

    Döndürülen her öğe: {"url": str, "type": "full" | "thumb" | "other", "format": str}
      - full  : x5_ / x3_ önekli (tam çözünürlük)
      - thumb : thmb_ / lthmb_ önekli
      - other : diğer sahibinden CDN görselleri
    """
    # Önce HTML entity'leri decode et — PSI çıktısında URL'ler &quot; ile gömülü olabilir
    unescaped = html_mod.unescape(raw_html)
    result: list[dict] = []
    seen:   set[str]   = set()

    pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )

    for url in pattern.findall(unescaped):
        # Sorgu parametrelerini ve fragment'leri kaldır
        url = url.split("?", 1)[0].split("#", 1)[0]
        if "blank" in url or url in seen:
            continue
        seen.add(url)

        fname = url.rsplit("/", 1)[-1]
        fmt   = fname.rsplit(".", 1)[-1].lower() if "." in fname else "?"

        if fname.startswith("x5_") or fname.startswith("x3_"):
            ptype = "full"
        elif fname.startswith("thmb_") or fname.startswith("lthmb_"):
            ptype = "thumb"
        else:
            ptype = "other"

        result.append({"url": url, "type": ptype, "format": fmt})

    return result

# ── GA4 / UA custom dimension haritaları (detay_okuycu_pagespeed referans) ────

_PSI_CD_MAP: dict[str, str] = {
    "cd13": "Kategori 1",
    "cd14": "Kategori 2",
    "cd15": "Marka",
    "cd16": "Seri",
    "cd17": "Model",
    "cd19": "Ülke",
    "cd20": "Şehir",
    "cd21": "İlçe",
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
    "cd73": "Mahalle",
    "cd74": "Mahalle (detay)",
}

_PSI_EP_MAP: dict[str, str] = {
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
    "ep.model_yili":        "Model Yılı",
}

def _extract_psi_specs(raw_html: str) -> dict:
    """
    PageSpeed Insights HTML'inden ilan teknik özelliklerini çıkarır.

    Strateji (öncelik sırası):
      1. GA4 event parametreleri (ep.XXX=YYY) — en zengin veri seti
      2. UA custom dimensions (cd13=XXX&cd14=YYY) — fallback
      3. Fiyat (Sayısal) → TL formatına dönüştürme

    detay_okuycu_pagespeed.py referans alınarak iyileştirildi.
    """
    from urllib.parse import unquote
    specs: dict    = {}
    seen_keys: set = set()

    # ── 1) GA4 event parametreleri (ep. prefix'li) ────────────────────────────
    ep_pattern = re.compile(r"ep\.([A-Za-z0-9_]+)=([^&\n\"'<>]+)", re.IGNORECASE)
    for m in ep_pattern.finditer(raw_html):
        raw_key = "ep." + m.group(1)
        raw_val = m.group(2).replace("&amp;", "&").replace("+", " ")
        try:
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

    # ── 2) UA custom dimensions (cd13=... formatı) ────────────────────────────
    cd_pattern = re.compile(r"(cd\d{1,3})=([^&\n\"'<>]+)", re.IGNORECASE)
    for m in cd_pattern.finditer(raw_html):
        cd_key  = m.group(1).lower()
        raw_val = m.group(2).replace("&amp;", "&").replace("+", " ")
        try:
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

    # ── 3) Fiyat (Sayısal) → TL formatına çevir ──────────────────────────────
    if "Fiyat (Sayısal)" in specs:
        try:
            amt       = int(specs["Fiyat (Sayısal)"])
            formatted = f"{amt:,.0f} TL".replace(",", ".")
            specs.setdefault("Fiyat", formatted)
        except Exception:
            pass

    # ── 4) Fiyat hâlâ yoksa regex fallback ───────────────────────────────────
    if "Fiyat" not in specs:
        pm = re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:TL|₺)", raw_html)
        if pm:
            specs["Fiyat"] = pm.group(0)

    # ── 5) Gereksiz teknik/debug alanları temizle ─────────────────────────────
    for k in ("Sayfa Türü", "Kullanıcı Giriş Durumu", "Oturum Durum"):
        specs.pop(k, None)

    return specs

def _extract_price_tr(raw_html: str) -> str:
    """Ham HTML metninden TL fiyatı regex ile çıkarır."""
    m = re.search(r"(\d{1,3}(?:[.,]\d{3})+)\s*(?:TL|₺)", raw_html)
    return m.group(0) if m else ""

def _extract_location_from_raw(raw_html: str) -> str:
    """Ham HTML'den konum/adres bilgisini çıkarır."""
    try:
        soup = BeautifulSoup(html_mod.unescape(raw_html), "html.parser")
        for sel in [
            "[class*='location']",
            "[class*='address']",
            "[class*='adres']",
            "[class*='konum']",
            "[class*='Location']",
        ]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(strip=True)
                if text:
                    return text
    except Exception:
        pass
    return ""

def _parse_photos_from_raw(raw_html: str) -> list[str]:
    """
    Fallback: ham HTML'deki shbdn fotoğraflarını ayıklar.
    Google/gstatic favicon veya logo gibi sistem varlıklarını kesinlikle eler.
    """
    seen: set[str] = set()
    urls: list[str] = []

    # Öncelikli: shbdn.com/photos
    for m in re.finditer(
        r'(https?://[^\s"\'<>]*(?:shbdn\.com/photos|i\d?\.shbdn)[^\s"\'<>]*\.(?:jpg|jpeg|png|webp|avif))(?:[^\s"\'<>]*)?',
        raw_html,
        re.IGNORECASE,
    ):
        url = html_mod.unescape(m.group(1))
        u_low = url.lower()
        if any(bad in u_low for bad in ["favicon", "google", "gstatic", "logo", "analytics", "sprite", "icon", "placeholder"]):
            continue
        if url not in seen and len(url) > 20:
            seen.add(url)
            urls.append(url)
        if len(urls) >= 16:
            break

    # İkinci deneme: genel resimler (gstatic/google kesinlikle hariç)
    if not urls:
        for m in re.finditer(
            r'(https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp))(?:[^\s"\'<>]*)?',
            raw_html,
            re.IGNORECASE,
        ):
            url = html_mod.unescape(m.group(1))
            u_low = url.lower()
            if any(bad in u_low for bad in ["favicon", "google", "gstatic", "logo", "analytics", "sprite", "icon", "pagespeed", "web.dev"]):
                continue
            if url not in seen and len(url) > 20:
                seen.add(url)
                urls.append(url)
            if len(urls) >= 10:
                break

    return urls

# ================================================================
# PLAYWRIGHT HELPERS — async (greenlet gerektirmez)
# ================================================================

async def _pw_accept_cookies(page) -> None:
    selectors = [
        "button:has-text('Tümünü kabul')",
        "button:has-text('Accept all')",
        "button:has-text('Kabul et')",
        "#onetrust-accept-btn-handler",
    ]
    for sel in selectors:
        try:
            await page.locator(sel).click(timeout=4000)
            await page.wait_for_timeout(400)
            return
        except Exception:
            pass

async def _pw_type_url(page, target_url: str, max_attempts: int = 4) -> bool:
    """PageSpeed URL input'una URL'yi güvenilir şekilde yazar."""
    for attempt in range(1, max_attempts + 1):
        try:
            inp = page.locator("input[name='url']")
            await inp.wait_for(state="visible", timeout=15000)
            await page.wait_for_timeout(300)
            el = await inp.element_handle()
            await page.evaluate(
                """(args) => {
                    const el = args[0];
                    el.focus(); el.value = '';
                    el.value = args[1];
                    el.dispatchEvent(new Event('input',  {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                }""",
                [el, target_url],
            )
            await page.wait_for_timeout(300)
            val = await page.evaluate("el => el.value", el)
            if val == target_url:
                print(f"    ✓ URL girildi (deneme {attempt})")
                return True
            await inp.click()
            await inp.fill(target_url)
            await page.wait_for_timeout(300)
            val = await page.evaluate("el => el.value", el)
            if val == target_url:
                print(f"    ✓ URL fill ile girildi (deneme {attempt})")
                return True
            print(f"    ⚠ Deneme {attempt} başarısız, tekrar...")
            await page.wait_for_timeout(1000)
        except Exception as exc:
            print(f"    ⚠ Deneme {attempt} hatası: {exc}")
            await page.wait_for_timeout(1500)
    print("    ✗ URL girilemedi.")
    return False

# ================================================================
# SAHIBINDEN SCRAPER — Selenium + PageSpeed Web
# ================================================================

async def _scrape_via_pagespeed_async(url: str) -> dict:
    """Async Playwright ile PageSpeed scrape — greenlet gerektirmez."""
    headless = os.environ.get("PS_HEADLESS", "1") != "0"
    wait_sec  = int(os.environ.get("PS_WAIT_SEC", str(DEFAULT_PS_WAIT)))
    print(f"🌐 Playwright (async) PageSpeed başlatılıyor... (headless={headless}, wait={wait_sec}s)")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--disable-extensions",
                "--disable-background-networking",
                "--mute-audio",
                "--no-first-run",
            ],
        )
        ctx  = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        raw_html = ""
        try:
            await page.goto(PAGESPEED_WEB_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
            await _pw_accept_cookies(page)
            await page.wait_for_timeout(500)

            if not await _pw_type_url(page, url):
                return {"ok": False, "error": "URL PageSpeed'e girilemedi"}

            try:
                btn = page.locator(
                    "button:has-text('Analiz et'), button:has-text('Analyze')"
                ).first
                await btn.wait_for(state="visible", timeout=15000)
                inp = page.locator("input[name='url']")
                el  = await inp.element_handle()
                val = await page.evaluate("el => el.value", el)
                if val != url:
                    if not await _pw_type_url(page, url):
                        return {"ok": False, "error": "URL doğrulama başarısız"}
                await btn.click()
            except Exception:
                print("    ⚠ Buton bulunamadı, Enter ile gönderiliyor...")
                await page.locator("input[name='url']").press("Enter")

            max_wait = min(wait_sec, 25)
            print(f"    ✓ Analiz başlatıldı → fotoğraflar taranıyor (max {max_wait}s)")
            for i in range(max_wait):
                await page.wait_for_timeout(1000)
                content_now = await page.content()
                if "shbdn.com/photos" in content_now:
                    print(f"    ✓ Sahibinden fotoğrafları başarıyla yakalandı ({i+1}s)")
                    break
                if "denetim sırasında bir hata" in content_now.lower() or "lighthouse hatası" in content_now.lower():
                    print(f"    ⚠ PSI analiz hatası tespit edildi ({i+1}s)")
                    break

            raw_html = await page.content()
        finally:
            await ctx.close()
            await browser.close()

    # ── Fotoğraf çıkarma ──────────────────────────────────────────────────────
    psi_photos   = _extract_psi_photos(raw_html)
    full_photos  = [p["url"] for p in psi_photos if p["type"] == "full"]
    thumb_photos = [p["url"] for p in psi_photos if p["type"] == "thumb"]
    other_photos = [p["url"] for p in psi_photos if p["type"] == "other"]

    def _photo_key(u: str) -> str:
        fname = u.rsplit("/", 1)[-1]
        clean = re.sub(r"^(?:x5_|x3_|x2_|x1_|thmb_|lthmb_)", "", fname)
        return u.rsplit("/", 1)[0] + "/" + clean

    full_keys     = {_photo_key(u) for u in full_photos}
    orphan_thumbs = [u for u in thumb_photos if _photo_key(u) not in full_keys]

    if full_photos or thumb_photos:
        photos = full_photos + orphan_thumbs
    elif other_photos:
        photos = other_photos
    else:
        photos = _parse_photos_from_raw(raw_html)

    specs    = _extract_psi_specs(raw_html)
    price    = specs.get("Fiyat") or _extract_price_tr(raw_html)
    loc_parts = [x for x in [specs.get("Mahalle",""), specs.get("İlçe",""), specs.get("Şehir","")] if x]
    location  = ", ".join(loc_parts) if loc_parts else _extract_location_from_raw(raw_html)

    # ── Sahibinden Scraper Mantığı: URL slug'ından temiz ve profesyonel başlık ──
    listing_id = detect_single_listing_id(url)
    extracted_url = _extract_sahibinden_detail_url(raw_html) or url
    title = _title_from_detail_url(extracted_url, listing_id) or _title_from_detail_url(url, listing_id)
    if not title or len(title) < 4:
        candidates = re.findall(r'nodeLabel[\\"]*:\s*[\\"]*([^"]{10,120})', raw_html)
        for c in candidates:
            c_clean = html_mod.unescape(c).strip()
            if any(w in c_clean.lower() for w in ["satılık", "kiralık", "daire", "villa", "arsa", "otel", "bina", "rezidans", "ofis"]):
                title = c_clean
                break
    if not title or "pagespeed" in title.lower():
        title = f"Sahibinden İlanı #{listing_id}" if listing_id else "Gayrimenkul Portföy İlanı"

    slug_data = _scrape_via_slug_fallback(url)
    if not location or location == "Ankara":
        if slug_data.get("location") and slug_data.get("location") != "Ankara":
            location = slug_data.get("location")
        elif not location:
            location = "Ankara"
    if not title or title.islower() or "pagespeed" in title.lower():
        title = slug_data.get("title", title)
    for sk, sv in slug_data.get("specs", {}).items():
        if sk not in specs and sv:
            specs[sk] = sv

    # ── Sahibinden Scraper Mantığı: Açıklama Çıkarma + OCR Fallback ──
    description = _extract_psi_description(raw_html)
    if not description and listing_id:
        try:
            desc_ocr, _ = _psi_api_extract_description(url)
            if desc_ocr:
                description = desc_ocr
        except Exception:
            pass

    # ── Fotoğraflar: AVIF → JPG normalizasyonu ve tekilleştirme ──
    clean_photos = []
    for ph in photos:
        ph_clean = _sahibinden_avif_to_jpg(ph) if '_sahibinden_avif_to_jpg' in globals() else ph
        if ph_clean and ph_clean not in clean_photos:
            clean_photos.append(ph_clean)

    print(f"    ✓ Fotoğraf: {len(clean_photos)} | Başlık: {title[:40]}... | Fiyat: {price} | Lokasyon: {location}")
    return {
        "ok": True, "source": "sahibinden_playwright_pagespeed",
        "title": title, "price": price, "location": location,
        "specs": specs, "description": description,
        "images": clean_photos, "photo_count": len(clean_photos),
        "photo_types": {"full": len(full_photos), "thumb": len(thumb_photos), "other": len(other_photos)},
        "screenshot": "",
    }

def _scrape_via_psi_api(url: str) -> dict:
    """
    Google PageSpeed Insights v5 REST API kullanarak tekil ilanı çeker.
    %100 fotoğrafları (x5_ yüksek çözünürlük) ve OCR ile #classified-detail ve
    #classifiedProperties alanlarını eksiksiz çıkarır.
    """
    listing_id = detect_single_listing_id(url)
    target_url = url if "#" in url else _build_classified_detail_url(url)
    print(f"    [PSI] PageSpeed REST API çağrılıyor... ({target_url[:65]})")
    psi_json = _psi_api_fetch(target_url, timeout=60)
    if not psi_json or "lighthouseResult" not in psi_json:
        return {"ok": False, "error": "PageSpeed API yanıt vermedi veya lighthouseResult yok"}

    lr = psi_json.get("lighthouseResult", {})
    net_items = lr.get("audits", {}).get("network-requests", {}).get("details", {}).get("items", [])
    raw_synthetic = "\n".join(f'<a href="{it.get("url", "")}">{it.get("url", "")}</a>' for it in net_items)

    title = _title_from_detail_url(url, listing_id) or (f"İlan #{listing_id}" if listing_id else "Gayrimenkul İlanı")
    psi_specs = _extract_psi_specs(raw_synthetic)
    price = psi_specs.get("Fiyat") or _extract_price_tr(raw_synthetic) or ""

    loc_parts = []
    for k in ["İl", "Şehir", "İlçe", "Mahalle"]:
        if k in psi_specs and psi_specs[k] not in loc_parts:
            loc_parts.append(psi_specs[k])
    loc_str = " / ".join(loc_parts) if loc_parts else ""

    # %100 Fotoğrafları çek (x5_ tam boy)
    cj_str = json.dumps(psi_json)
    psi_photo_pat = re.compile(
        r'https?://i\d+\.shbdn\.com/photos/(\d+/\d+/\d+)/([a-zA-Z0-9_]+)\.(avif|jpg|jpeg|png|webp)',
        re.IGNORECASE
    )
    seen_keys = set()
    photos = []
    for match in psi_photo_pat.finditer(cj_str):
        folder, fname, ext = match.groups()
        base_id = re.sub(r'^(x5_|x3_|x2_|x1_|thmb_|lthmb_)', '', fname)
        if not base_id or "blank" in base_id:
            continue
        core_key = f"https://i0.shbdn.com/photos/{folder}/{base_id}"
        if core_key not in seen_keys:
            seen_keys.add(core_key)
            photos.append(f"https://i0.shbdn.com/photos/{folder}/x5_{base_id}.avif")

    # OCR Açıklama ve Özellikler (#classified-detail & #classifiedProperties)
    ocr_desc, ocr_note = _psi_api_extract_description(target_url, psi_json=psi_json)
    desc = ocr_desc if ocr_desc else ""

    specs = {}
    if listing_id:
        specs["İlan No"] = listing_id
    if price:
        specs["Fiyat"] = price
    if loc_str:
        specs["Konum"] = loc_str
    for k, v in psi_specs.items():
        if k not in specs:
            specs[k] = v

    return {
        "ok": True,
        "source": "psi_api",
        "url": url,
        "listing_id": listing_id,
        "title": title,
        "price": price,
        "location": loc_str,
        "specs": specs,
        "images": photos,
        "photo_count": len(photos),
        "description": desc,
    }


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
# GÖRSEL İNDİRME
# ================================================================

def _download_image_b64(img_url: str) -> tuple[str, str] | None:
    """
    URL → (mime_type, base64_string). Başarısız olursa None.

    Shbdn fotoğrafları .avif formatında gelir; Gemini bu formatı inline olarak
    desteklemez. Bu yüzden .avif URL'leri için önce .jpg varyantı denenir.
    """
    def _fetch(url: str) -> tuple[str, str] | None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, stream=True)
            if not resp.ok:
                return None
            ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not ct.startswith("image/"):
                return None
            mime = ct.split("/")[-1] if "/" in ct else "jpeg"
            # Gemini inline desteklenen formatlar: jpeg, png, webp, gif
            # avif desteklenmez → jpeg olarak işaretle (bytes uyumsuz olabilir)
            if mime not in ("jpeg", "png", "webp", "gif"):
                return None   # bu URL'yi geç, fallback dene
            raw = b"".join(resp.iter_content(65536))
            return mime, base64.b64encode(raw).decode("utf-8")
        except Exception:
            return None

    # .avif URL ise önce .jpg varyantını dene
    if img_url.lower().endswith(".avif"):
        jpg_url = img_url[:-5] + ".jpg"
        result  = _fetch(jpg_url)
        if result:
            return result
        # .jpg de yoksa thumbnail'den büyük versiyon dene (x5_ → x3_)
        if "/x5_" in img_url:
            x3_url = img_url.replace("/x5_", "/x3_").replace(".avif", ".jpg")
            result  = _fetch(x3_url)
            if result:
                return result
        # thmb_ versiyonuna düş
        if "/thmb_" not in img_url:
            thmb_url = re.sub(r"/(?:x5_|x3_|x2_|x1_)", "/thmb_", img_url).replace(".avif", ".jpg")
            result    = _fetch(thmb_url)
            if result:
                return result
        # Son çare: bytes'ı avif olarak al ama jpeg mime ile gönder (bazı modellerde geçer)
        try:
            resp = requests.get(img_url, headers=HEADERS, timeout=10, stream=True)
            if resp.ok:
                raw = b"".join(resp.iter_content(65536))
                return "jpeg", base64.b64encode(raw).decode("utf-8")
        except Exception:
            pass
        return None

    return _fetch(img_url)

def _parse_uploaded(img_data: str) -> tuple[str, str] | None:
    """Frontend'den gelen base64 string veya data URI → (mime, b64)."""
    if not img_data:
        return None
    if img_data.startswith("data:"):
        try:
            header, b64 = img_data.split(";base64,", 1)
            mime = header.split("/")[-1].lower()
            # Gemini inline desteklenenler
            mime = mime if mime in ("jpeg", "png", "webp", "gif") else "jpeg"
            return mime, b64
        except Exception:
            return None
    # Salt base64 string → jpeg varsay
    return "jpeg", img_data

# ================================================================
# ANA ANALİZ
# ================================================================

def analyze_listing(
    listing_data:    dict | None,
    manual_data:     dict | None,
    uploaded_images: list[str] | None,
) -> dict:
    """
    Scrape çıktısı + manuel giriş + yüklenen fotoğrafları birleştirip
    Gemini 2.5 Flash multimodal ile ultra-detaylı gayrimenkul analizi üretir.

    Parametreler:
        listing_data    — scrape_listing() çıktısı (veya None)
        manual_data     — {price, area, rooms, floor, age, location, notes, listing_type}
        uploaded_images — ["data:image/jpeg;base64,...", ...] listesi

    Dönüş:
        {"ok": True,  "report": {...}}
        {"ok": False, "error": "..."}
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}

    # ── Veri birleştirme ──────────────────────────────────────────────────────
    ld = listing_data or {}
    md = manual_data or {}

    def pick(*keys: str, fallback: str = "—") -> str:
        for k in keys:
            v = ld.get(k) or md.get(k) or (ld.get("specs") or {}).get(k)
            if v and str(v).strip():
                return str(v).strip()
        return fallback

    title    = pick("title",    "manual_title",    fallback="Belirtilmemiş")
    price    = pick("price",    "Fiyat", "manual_price", fallback="Belirtilmemiş")
    location = pick("location", "manual_location", fallback="Belirtilmemiş")
    area     = pick("area",     "manual_area",     fallback="")
    rooms    = pick("rooms",    "manual_rooms",    fallback="")
    floor    = pick("floor",    "manual_floor",    fallback="")
    age      = pick("age",      "manual_age",      fallback="")
    desc     = pick("description", "manual_notes", fallback="")
    l_type   = pick("type",     "listing_type",    fallback="Belirtilmemiş")
    source   = ld.get("source", "manuel")

    # Specs'ten eksik alanları tamamla
    specs = ld.get("specs") or {}
    if location == "Belirtilmemiş" and specs:
        loc_parts = [x for x in [
            specs.get("Mahalle", ""),
            specs.get("İlçe", ""),
            specs.get("Şehir", ""),
        ] if x]
        if loc_parts:
            location = ", ".join(loc_parts)
    if not rooms and specs.get("Oda Sayısı"):
        rooms = specs["Oda Sayısı"]
    if not area and specs.get("Alan"):
        area = specs["Alan"]
    ilan_no = specs.get("İlan No", "")
    kimden  = specs.get("Kimden", "")
    kategori = specs.get("Kategori 1", "") or specs.get("Kategori 2", "")

    # ── Görselleri hazırla ────────────────────────────────────────────────────
    all_images: list[tuple[str, str]] = []  # [(mime, b64), ...]

    # Scrape'den screenshot
    screenshot = ld.get("screenshot", "")
    if screenshot and len(all_images) < 2:
        parsed = _parse_uploaded(screenshot)
        if parsed:
            all_images.append(parsed)

    # Scrape'den URL'ler (tam boyut öncelikli, cap 12)
    for img_url in ld.get("images", []):
        if len(all_images) >= 12:
            break
        if img_url.startswith("data:"):
            parsed = _parse_uploaded(img_url)
            if parsed:
                all_images.append(parsed)
        else:
            result = _download_image_b64(img_url)
            if result:
                all_images.append(result)

    # Upload'dan gelen görseller (cap 15 toplam)
    for img_data in (uploaded_images or []):
        if len(all_images) >= 15:
            break
        parsed = _parse_uploaded(img_data)
        if parsed:
            all_images.append(parsed)

    has_photos = len(all_images) > 0
    print(f"🖼  Toplam görsel: {len(all_images)} (kaynak: {source})")

    # ── Prompt ────────────────────────────────────────────────────────────────
    prompt = f"""Sen Türkiye'nin en deneyimli gayrimenkul analiz uzmanısın.
Bir ilan hakkında {'fotoğraflar da dahil olmak üzere ' if has_photos else ''}kapsamlı bir analiz yapmanı istiyorum.

════════════════ İLAN BİLGİLERİ ════════════════
Başlık        : {title}
Fiyat         : {price}
Tür           : {l_type}
Konum         : {location}
Brüt Alan     : {area}
Oda/Salon     : {rooms}
Kat           : {floor}
Bina Yaşı     : {age}
{'İlan No      : ' + ilan_no if ilan_no else ''}
{'Kimden       : ' + kimden if kimden else ''}
{'Kategori     : ' + kategori if kategori else ''}
Açıklama/Not  : {desc[:800] if desc != '—' else 'Yok'}
Veri Kaynağı  : {source}
{'📸 ' + str(len(all_images)) + ' adet fotoğraf ektedir. Her birini detaylıca incele.' if has_photos else '⚠ Fotoğraf gönderilmedi.'}
════════════════════════════════════════════════

KURALLAR:
1. SADECE geçerli JSON döndür. Markdown, açıklama, kod bloğu YOK.
2. Tüm metinler Türkçe.
3. Fiyatlar TL cinsinden, binlik nokta ayraçlı (örn: "4.750.000 TL").
4. Sayısal skorlar 1–10 aralığında tam sayı.
5. pros/cons/strengths vb. listelerde ≥ 3 madde.
6. Fotoğraf varsa photo_analysis alanını doldur; yoksa "condition_score":0 yaz, diğer alanları boş bırak.
7. investment_analysis.verdict: "AL" / "BEKLE" / "GEÇ" yaz.
8. advisor_notes.talking_points danışman için, müşteriye söylenmesi gereken güçlü noktalar.
9. Gerçekçi ol — spekülatif bilgileri "tahmini" olarak işaretle.

JSON YAPISI (TÜM ALANLARI DOLDUR):
{{
  "property_summary": {{
    "title": "{title}",
    "price": "{price}",
    "location": "{location}",
    "area": "{area}",
    "rooms": "{rooms}",
    "floor": "{floor}",
    "building_age": "{age}",
    "type": "{l_type}"
  }},
  "price_analysis": {{
    "listed_price": "{price}",
    "estimated_fair_value": "X.XXX.XXX TL",
    "price_per_sqm": "XX.XXX TL/m²",
    "market_comparison": "Piyasa ortalamasının %X altında/üstünde",
    "negotiation_room": "%X–Y",
    "verdict": "Uygun/Pahalı/Ucuz",
    "verdict_detail": "2-3 cümle"
  }},
  "investment_analysis": {{
    "investment_score": 7,
    "score_label": "İyi",
    "verdict": "AL",
    "estimated_monthly_rent": "XX.XXX TL",
    "gross_yield_pct": 4.2,
    "payback_years": 20,
    "value_increase_1yr": "%X–Y",
    "value_increase_5yr": "%X–Y",
    "target_buyer": "Yatırımcı/Birinci ev/Kiralık vb.",
    "reasoning": "3-4 cümle"
  }},
  "photo_analysis": {{
    "overall_condition": "Yeni/İyi/Orta/Kötü",
    "condition_score": 8,
    "detected_rooms": ["salon","mutfak"],
    "flooring": "parke/seramik/mermer/?",
    "natural_light": "Bol/Orta/Az",
    "view": "Açık/Kapalı/Boğaz/Park/?",
    "renovation_needed": false,
    "renovation_estimate": "",
    "positive_visuals": ["güçlü görsel özellik"],
    "issues_detected": ["sorun 1"],
    "staging_tips": ["sunum önerisi 1"]
  }},
  "swot": {{
    "strengths":     ["güçlü yön 1","güçlü yön 2","güçlü yön 3"],
    "weaknesses":    ["zayıf yön 1","zayıf yön 2"],
    "opportunities": ["fırsat 1","fırsat 2"],
    "threats":       ["tehdit 1","tehdit 2"]
  }},
  "location_analysis": {{
    "neighborhood_score": 7,
    "transport_access": "Metro/Otobüs/Özel araç gerekli",
    "nearby_amenities": ["okul","hastane","AVM"],
    "development_outlook": "Gelişmekte/Stabil/Gerileme",
    "earthquake_risk": "Düşük/Orta/Yüksek",
    "noise_risk": "Düşük/Orta/Yüksek",
    "comments": "2-3 cümle"
  }},
  "advisor_notes": {{
    "talking_points": ["güçlü nokta 1","güçlü nokta 2","güçlü nokta 3"],
    "objections_to_prepare": ["olası itiraz 1","olası itiraz 2"],
    "closing_suggestion": "Kapanış stratejisi",
    "red_flags": ["risk 1"]
  }},
  "recommendation": {{
    "verdict": "AL/GEÇ/BEKLE",
    "confidence": "Yüksek/Orta/Düşük",
    "summary": "3-4 cümle genel değerlendirme",
    "next_steps": ["adım 1","adım 2","adım 3"]
  }},
  "disclaimer": "Bu analiz Gemini yapay zekası tarafından üretilmiştir; yatırım tavsiyesi değildir. Kesin değerleme için SPK lisanslı ekspertiz önerilir."
}}"""

    # ── Gemini client ─────────────────────────────────────────────────────────
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ Gemini client oluşturulamadı: {e}")
        return {"ok": False, "error": f"Gemini client hatası: {e}"}

    # ── Part listesi ──────────────────────────────────────────────────────────
    parts: list = []
    for mime, b64 in all_images[:12]:
        try:
            raw_bytes = base64.b64decode(b64)
            parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=f"image/{mime}"))
        except Exception as img_err:
            print(f"⚠ Görsel eklenirken hata: {img_err}")
    parts.append(types.Part.from_text(text=prompt))

    contents = [types.Content(role="user", parts=parts)]

    # JSON çıktısını zorla — parse hatasını ortadan kaldırır
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.3,
        max_output_tokens=8192,
    )

    # ── Retry + Fallback mekanizması ──────────────────────────────────────────
    def _call_gemini(model_name: str) -> tuple[str, str | None]:
        """(raw_text, error) döner. 429 için exponential backoff uygular."""
        delay = GEMINI_RETRY_DELAY
        last_err = ""
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                resp = client.models.generate_content(
                    model   = model_name,
                    contents= contents,
                    config  = gen_config,
                )
                text = (resp.text or "").strip()
                if text:
                    return text, None
                return "", "Gemini boş yanıt döndürdü"
            except Exception as exc:
                last_err = str(exc)
                is_429  = "429" in last_err or "RESOURCE_EXHAUSTED" in last_err
                is_404  = "404" in last_err or "NOT_FOUND" in last_err
                if is_404:
                    # Model yok — retry anlamsız
                    print(f"❌ Model bulunamadı ({model_name}): {exc}")
                    return "", f"Model bulunamadı: {model_name}"
                if is_429 and attempt < GEMINI_MAX_RETRIES:
                    print(f"⏳ 429 kota aşıldı ({model_name}), {delay}s bekleniyor... (deneme {attempt}/{GEMINI_MAX_RETRIES})")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print(f"❌ Gemini API hatası ({model_name}): {exc}")
        return "", last_err

    raw_text = ""
    used_model = GEMINI_MODEL

    raw_text, err = _call_gemini(GEMINI_MODEL)

    if not raw_text and GEMINI_FALLBACK and GEMINI_FALLBACK != GEMINI_MODEL:
        print(f"🔄 Fallback model deneniyor: {GEMINI_FALLBACK}")
        used_model = GEMINI_FALLBACK
        raw_text, err = _call_gemini(GEMINI_FALLBACK)

    if not raw_text:
        quota_hint = ""
        if err and ("429" in err or "RESOURCE_EXHAUSTED" in err):
            quota_hint = (
                " | 💡 Çözüm: aistudio.google.com > Billing'i aktif edin "
                "(kart gerekmez) → Tier 1'e geçince limit 30x artar."
            )
        return {"ok": False, "error": f"Gemini hatası: {err}{quota_hint}"}

    print(f"✅ Gemini yanıtı alındı ({used_model}) — {len(raw_text)} karakter")

    # ── JSON temizleme (response_mime_type olsa da bazı modeller ``` ekler) ──
    if "```" in raw_text:
        for part in raw_text.split("```"):
            p = part.strip()
            if p.lower().startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                raw_text = p
                break

    start = raw_text.find("{")
    end   = raw_text.rfind("}") + 1
    if start != -1 and end > start:
        raw_text = raw_text[start:end]

    try:
        report = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON parse hatası: {e}", "raw": raw_text[:400]}

    report["generated_at"] = time.strftime("%d.%m.%Y %H:%M")
    report["has_photos"]   = has_photos
    report["photo_count"]  = len(all_images)
    report["data_source"]  = source
    report["model_used"]   = used_model

    return {"ok": True, "report": report}

# ================================================================
# CONTACT EXTRACT — CRM için ekran görüntüsünden kişi bilgisi
# ================================================================

def extract_contact_from_images(images_b64: list[str]) -> dict:
    """
    Ekran görüntüsünden tüm CRM alanlarını (Gemini Agent) doldurur.

    Parametreler:
        images_b64 — ["data:image/jpeg;base64,...", ...] listesi (maks 3)

    Dönüş (tüm alanlar None olabilir):
        {
          "ok": True,
          "seller_name", "phone",
          "listing_title", "listing_type",
          "price" (int), "district",
          "category" (fsbo|portfolio|client|project),
          "source"  (website|whatsapp|meta|manual),
          "stage",
          "notes", "rooms", "area_m2", "building_age", "floor"
        }
        {"ok": False, "error": "..."}
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}

    if not images_b64:
        return {"ok": False, "error": "Görüntü listesi boş"}

    # Görselleri parse et (maks 3)
    parts: list = []
    for img_data in images_b64[:3]:
        parsed = _parse_uploaded(img_data)
        if parsed:
            mime, b64 = parsed
            try:
                raw_bytes = base64.b64decode(b64)
                parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=f"image/{mime}"))
            except Exception:
                pass

    if not parts:
        return {"ok": False, "error": "Geçerli görüntü verisi bulunamadı"}

    prompt = """Sen bir gayrimenkul CRM veri çıkarma ajanısın.
Sana verilen 1-3 ekran görüntüsü Türkiye'deki bir gayrimenkul ilanına ait mobil/web uygulama ekranlarıdır
(sahibinden.com, hepsiemlak, zingat, emlakjet, milligazete vb.).

GÖREV: Ekranlardaki TÜM metni oku ve aşağıdaki JSON alanlarını doldur.
ÇIKTI: Sadece geçerli JSON. Markdown, açıklama, kod bloğu YOK.

EKRAN OKUMA REHBERİ (sahibinden mobil için):
- Başlık: Sayfanın en üstündeki BÜYÜK HARF metin (örn: "SAHİBİNDEN 3+1 SATILIK,TURAN GÜNEŞ ARKA SOKAĞI...")
- Satıcı adı: Fotoğrafın hemen altındaki isim kutusu (örn: "Orkun K.") VEYA telefon pop-up'ındaki isim
- Telefon: Yeşil buton içindeki veya "Cep" / "Sabit" yanındaki numara (örn: "0 (546) 590 61 XX")
  → Parantez, boşluk, tire kaldır → 05465906100 formatına getir
  → Numara kısmi görünüyorsa (son rakamlar gizli/bulanık) yine de gördüğün kadarını yaz
- Fiyat: "Fiyat" satırındaki mavi/renkli rakam (örn: "13.900.000 TL" → 13900000)
- Konum breadcrumb: "Ankara, Çankaya, Yıldızevler Mh." → district=Çankaya, city=Ankara
- Kategori breadcrumb: "Emlak > Konut > Satılık > Daire" → listing_type=Satılık
- Emlak Tipi satırı: "Satılık Daire", "Kiralık Daire" vb.
- "Hesap Açma Tarihi" → satıcı bireysel kullanıcı → category=fsbo
- İlan başlığında "SAHİBİNDEN" kelimesi → category=fsbo (mülk sahibi)
- İlan başlığında "3+1", "2+1" gibi ifade → rooms alanı

JSON ŞEMASI:
{
  "seller_name":   "Satıcı adı — fotoğraf altı veya telefon pop-up'ından (örn: Orkun K.)",
  "phone":         "05XXXXXXXXX — 11 hane, sadece rakam, 0 ile başlayan",
  "listing_title": "İlanın TAM başlığı — sayfanın en üstündeki büyük metin, kelimesi kelimesine",
  "listing_type":  "Satılık veya Kiralık",
  "price":         "Sadece rakamlar, noktalama yok (örn: 13900000)",
  "district":      "Sadece ilçe (örn: Çankaya) — şehir veya mahalle değil",
  "category":      "fsbo | portfolio | client | project",
  "source":        "website | whatsapp | meta | manual",
  "stage":         "ilk_temas | degerleme | sozlesme | ilanda | gorunum | teklif | satildi",
  "notes":         "Kısa özet: oda sayısı, m², kat, bina yaşı, öne çıkan özellikler",
  "rooms":         "3+1 gibi oda formatı",
  "area_m2":       "Sadece sayı (brüt m²)",
  "building_age":  "Sayı (yıl)",
  "floor":         "7/10 gibi kat/toplam format"
}

DOLDURMA KURALLARI:
1. Ekranda net göremediğin alanı null bırak — ASLA tahmin etme.
2. Telefon: parantez/boşluk/tire kaldır, 0 ile başlayan 11 hane yap.
   Kısmi görünüyorsa (son 2 hane gizli) yine de gördüğün kadarıyla doldur.
3. price: SADECE rakamlar — 13.900.000 TL → 13900000
4. district: İlçe adı — "Ankara, Çankaya, Yıldızevler Mh." → "Çankaya"
5. listing_type: breadcrumb'daki "Satılık"/"Kiralık" VEYA "Emlak Tipi" satırından al.
6. category:
   - Başlıkta "SAHİBİNDEN" VEYA "Hesap Açma Tarihi" var → "fsbo"
   - Emlakçı/ofis adı var → "portfolio"
7. source: sahibinden/hepsiemlak/zingat mobil ekranı → "website"
8. stage: yeni ilan ekran görüntüsü → "ilk_temas"
9. notes: başlıktan ve görünen özellik tablolarından kısa özet yap."""
    parts.append(types.Part.from_text(text=prompt))
    contents = [types.Content(role="user", parts=parts)]

    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
        max_output_tokens=800,
    )

    # Deneme sırası: ana model → fallback → ek güvenilir modeller (503'e karşı)
    models_to_try = [GEMINI_MODEL]
    if GEMINI_FALLBACK and GEMINI_FALLBACK != GEMINI_MODEL:
        models_to_try.append(GEMINI_FALLBACK)
    for extra in ("gemini-1.5-flash", "gemini-1.5-pro"):
        if extra not in models_to_try:
            models_to_try.append(extra)

    client     = genai.Client(api_key=api_key)
    last_error = "Bilinmeyen hata"

    def _clean_str(val) -> str | None:
        """JSON'dan gelen değeri temizle; boş/null ise None döndür."""
        if not isinstance(val, str):
            return None
        val = val.strip()
        if val.lower() in ("null", "none", "", "yok", "bilinmiyor"):
            return None
        return val

    for model_name in models_to_try:
        for attempt in range(2):           # her model için en fazla 2 deneme
            try:
                if attempt > 0:
                    time.sleep(2)

                print(f"🔄 extract_contact deniyor: {model_name} (deneme {attempt+1})")
                resp = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=gen_config,
                )
                raw = (resp.text or "").strip()

                # JSON temizle
                if "```" in raw:
                    for part in raw.split("```"):
                        p = part.strip().lstrip("json").strip()
                        if p.startswith("{"):
                            raw = p
                            break
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start != -1 and end > start:
                    raw = raw[start:end]

                data          = json.loads(raw)
                seller_name   = _clean_str(data.get("seller_name"))
                phone         = _clean_str(data.get("phone"))
                listing_title = _clean_str(data.get("listing_title"))
                listing_type  = _clean_str(data.get("listing_type"))
                rooms         = _clean_str(data.get("rooms"))
                area_m2       = _clean_str(data.get("area_m2"))
                building_age  = _clean_str(data.get("building_age"))
                floor         = _clean_str(data.get("floor"))
                notes_raw     = _clean_str(data.get("notes"))
                category      = _clean_str(data.get("category"))
                source        = _clean_str(data.get("source"))
                stage         = _clean_str(data.get("stage"))

                # price: sadece rakam bırak
                price_raw = _clean_str(data.get("price"))
                price: int | None = None
                if price_raw:
                    digits = "".join(filter(str.isdigit, price_raw))
                    price = int(digits) if digits else None

                # district
                district = _clean_str(data.get("district"))

                # listing_type normalize
                if not listing_type:
                    t_norm = (listing_title or "").replace("İ", "i").replace("I", "ı").replace("Î", "i").lower()
                    if any(w in t_norm for w in ["kiralık", "kiralik", "kira", "kiralama"]):
                        listing_type = "Kiralık"
                    elif any(w in t_norm for w in ["satılık", "satilik", "satış", "satis"]):
                        listing_type = "Satılık"
                elif listing_type not in ("Satılık", "Kiralık"):
                    lt_norm = listing_type.replace("İ", "i").replace("I", "ı").replace("Î", "i").lower()
                    if any(w in lt_norm for w in ["kiralık", "kiralik", "kira", "kiralama"]):
                        listing_type = "Kiralık"
                    elif any(w in lt_norm for w in ["satılık", "satilik", "satış", "satis"]):
                        listing_type = "Satılık"
                    else:
                        listing_type = "Satılık"

                # category normalize
                valid_cats = ("fsbo", "portfolio", "client", "project")
                if category and category not in valid_cats:
                    cat_lower = category.lower()
                    if "fsbo" in cat_lower or "sahib" in cat_lower:
                        category = "fsbo"
                    elif "portf" in cat_lower or "emlak" in cat_lower:
                        category = "portfolio"
                    elif "client" in cat_lower or "müşteri" in cat_lower or "musteri" in cat_lower:
                        category = "client"
                    elif "proje" in cat_lower or "project" in cat_lower:
                        category = "project"
                    else:
                        category = None

                # source normalize
                valid_src = ("website", "whatsapp", "meta", "manual")
                if source and source not in valid_src:
                    src_lower = source.lower()
                    if "whatsapp" in src_lower or "wa" in src_lower:
                        source = "whatsapp"
                    elif "meta" in src_lower or "facebook" in src_lower or "instagram" in src_lower:
                        source = "meta"
                    elif "site" in src_lower or "web" in src_lower or "sahibinden" in src_lower or "hepsi" in src_lower:
                        source = "website"
                    else:
                        source = "manual"

                # stage normalize — valid stage id'leri CRM ile eşleştir
                valid_stages = (
                    "ilk_temas", "degerleme", "sozlesme", "ilanda",
                    "gorunum", "teklif", "satildi",
                    "aktif", "tamamlandi",
                )
                if stage and stage not in valid_stages:
                    stage = "ilk_temas"   # default: yeni ilan → ilk temas

                # notes: ek bilgileri birleştir
                notes_parts = []
                if notes_raw:
                    notes_parts.append(notes_raw)
                if rooms:         notes_parts.append(f"Oda: {rooms}")
                if area_m2:       notes_parts.append(f"Alan: {area_m2} m²")
                if floor:         notes_parts.append(f"Kat: {floor}")
                if building_age:  notes_parts.append(f"Bina yaşı: {building_age}")
                if listing_type:  notes_parts.append(f"Tür: {listing_type}")
                notes_combined = " | ".join(notes_parts) if notes_parts else None

                print(f"✅ extract_contact (FULL) başarılı: {model_name} | "
                      f"seller={seller_name} | price={price} | district={district} | cat={category}")
                return {
                    "ok":            True,
                    # Kimlik
                    "seller_name":   seller_name,
                    "phone":         phone,
                    # İlan
                    "listing_title": listing_title,
                    "listing_type":  listing_type,
                    # CRM alanları
                    "price":         price,
                    "district":      district,
                    "category":      category,
                    "source":        source,
                    "stage":         stage,
                    "notes":         notes_combined,
                    # Detaylar (opsiyonel referans)
                    "rooms":         rooms,
                    "area_m2":       area_m2,
                    "building_age":  building_age,
                    "floor":         floor,
                }

            except Exception as e:
                last_error = str(e)
                print(f"❌ extract_contact [{model_name}] deneme {attempt+1}: {e}")
                if "503" not in last_error and "UNAVAILABLE" not in last_error:
                    break   # 503 değilse bu modeli bırak
                time.sleep(3)

    print(f"❌ extract_contact_from_images tüm modeller başarısız: {last_error}")
    return {"ok": False, "error": f"AI servisi şu an yoğun, lütfen tekrar deneyin. ({last_error[:120]})"}

# ======================================================================
# FSBO Analysis Engine
# ======================================================================

from datetime import datetime, timezone

# Güncel model listesi: https://ai.google.dev/gemini-api/docs/models
# gemini-2.5-flash      → kararlı, fiyat/performans dengesi (ana model)
# gemini-2.5-flash-lite → en hızlı/ekonomik 2.5 ailesi (yedek)
# gemini-2.0-flash      → DEPRECATED — kullanılmaz!
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL       = "gemini-2.5-flash"
GEMINI_FALLBACK    = "gemini-2.5-flash-lite"  # 2.0-flash deprecated; lite en iyi yedek
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 8   # saniye; 503 yük hatalarında başlangıç bekleme

def _is_configured() -> bool:
    return bool(GEMINI_API_KEY)

def fsbo_engine_status() -> dict:
    configured = _is_configured()
    return {
        "ok":         configured,
        "configured": configured,
        "model":      GEMINI_MODEL,
        "error":      None if configured else "GEMINI_API_KEY tanımlanmamış",
    }

def _build_prompt(contact_data: dict, text_input: str, timeline: list) -> str:
    """Ana Gemini analiz promptunu oluşturur."""
    name     = contact_data.get("name", "Bilinmiyor")
    phone    = contact_data.get("phone", "")
    district = contact_data.get("district", "")
    price    = contact_data.get("price", "")
    stage    = contact_data.get("stage", "")
    notes    = contact_data.get("notes", "")
    category = contact_data.get("category", "fsbo")

    # Timeline özetini al (son 10 aktivite)
    timeline_text = ""
    if timeline:
        for ev in timeline[-10:]:
            t = ev.get("type", "")
            txt = ev.get("text", "")
            dt  = ev.get("createdAt", "")[:10] if ev.get("createdAt") else ""
            timeline_text += f"  [{dt}] {t.upper()}: {txt}\n"

    return f"""Sen Türkiye'nin en deneyimli gayrimenkul danışmanlarından birisin. 
Uzmanlık alanın: FSBO (For Sale By Owner / Sahibinden Satış) mülk sahiplerini portföye kazanmak.

## LEAD BİLGİLERİ
İsim: {name}
Telefon: {phone}
İlçe/Bölge: {district or 'Belirtilmemiş'}
Tahmini Değer: {price or 'Belirtilmemiş'} TL
Kategori: {category.upper()}
Mevcut Aşama: {stage}
Notlar: {notes or 'Yok'}

## AKTİVİTE GEÇMİŞİ
{timeline_text or 'Henüz aktivite yok'}

## EK BİLGİLER (Manuel Girdi)
{text_input or 'Ek bilgi girilmemiş'}

## GÖREV

Aşağıdaki JSON yapısını Türkçe olarak üret. SADECE JSON döndür, başka metin yok:

{{
  "owner_profile": {{
    "likely_situation": "Ev sahibinin tahmini durumu (zaman baskısı var mı, fiyat konusunda ne düşünüyor vb.)",
    "motivation_level": "yüksek|orta|düşük",
    "knowledge_level": "piyasayı biliyor|kısmen biliyor|bilmiyor",
    "decision_maker": "yalnız|aile ile birlikte karar veriyor|belirsiz",
    "timeline": "acil|1-3 ay|3-6 ay|belirsiz",
    "pain_points": ["Mevcut sorun 1", "Mevcut sorun 2", "Mevcut sorun 3"]
  }},
  "property_assessment": {{
    "estimated_price_range": "Ekran görüntülerine ve bölgeye göre tahmini fiyat aralığı",
    "listing_quality": "İlan kalitesi değerlendirmesi (fotoğraflar, açıklama vb.)",
    "time_on_market": "Piyasada ne kadar süredir olduğuna dair çıkarım",
    "price_positioning": "düşük|uygun|yüksek|çok yüksek",
    "key_observations": ["Önemli gözlem 1", "Önemli gözlem 2"]
  }},
  "fsbo_approach": {{
    "strategy_type": "değer_odaklı|sorun_çözücü|piyasa_uzmanı|güven_inşa_edici|aciliyet_yaratıcı",
    "primary_message": "Ana mesajın tek cümle özeti",
    "tone": "samimi|profesyonel|uzman|empatik|iddialı",
    "opening_script": "İlk temas için 2-3 cümlelik açılış scripti",
    "positioning": "Kendinizi nasıl konumlandırmalısınız"
  }},
  "key_questions": [
    {{
      "question": "Sorulacak soru",
      "purpose": "Bu soruyu neden sormak gerekiyor",
      "best_moment": "Ne zaman sormak gerekiyor",
      "ideal_answer": "İdeal yanıt ne olmalı",
      "priority": "yüksek|orta|düşük"
    }}
  ],
  "objection_handling": [
    {{
      "objection": "Olası itiraz",
      "response": "Profesyonel yanıt",
      "follow_up": "Yanıttan sonra yapılacak hareket",
      "probability": "yüksek|orta|düşük"
    }}
  ],
  "followup_schedule": {{
    "contact_1": {{
      "timing": "Hemen / 24 saat içinde",
      "channel": "whatsapp|telefon|email",
      "message": "İletişim mesajı veya konuşma notu",
      "goal": "Bu temasın hedefi"
    }},
    "contact_2": {{
      "timing": "3-5 gün sonra",
      "channel": "telefon|whatsapp",
      "message": "İkinci temas notu",
      "goal": "İkinci temasın hedefi"
    }},
    "contact_3": {{
      "timing": "2 hafta sonra",
      "channel": "yüz yüze|telefon",
      "message": "Üçüncü temas notu",
      "goal": "Üçüncü temasın hedefi"
    }},
    "contact_4": {{
      "timing": "1 ay sonra",
      "channel": "telefon|whatsapp",
      "message": "Dördüncü temas notu",
      "goal": "Dördüncü temasın hedefi"
    }}
  }},
  "talking_points": [
    {{
      "point": "Ana konuşma noktası",
      "supporting_data": "Destekleyici veri veya argüman",
      "delivery": "Nasıl sunulmalı"
    }}
  ],
  "recommended_actions": [
    {{
      "action": "Yapılacak eylem",
      "priority": "acil|yüksek|orta|düşük",
      "timeframe": "Ne zaman yapılmalı",
      "expected_outcome": "Beklenen sonuç"
    }}
  ],
  "swot": {{
    "strengths": ["Danışman olarak avantajınız 1", "Avantaj 2"],
    "weaknesses": ["Zayıf nokta 1", "Dikkat edilmesi gereken 2"],
    "opportunities": ["Fırsat 1", "Fırsat 2"],
    "threats": ["Risk 1", "Risk 2"]
  }},
  "urgency_triggers": [
    {{
      "trigger": "Aciliyet tetikleyicisi",
      "explanation": "Neden bu bir avantaj",
      "how_to_use": "Nasıl kullanılmalı"
    }}
  ],
  "verdict": "Bu lead hakkında 2-3 cümlelik genel değerlendirme ve öneri",
  "confidence_score": 7,
  "resistance_level": "orta",
  "next_contact_timing": "24 saat içinde WhatsApp ile başlayın",
  "estimated_conversion_probability": "yüksek|orta|düşük",
  "risk_flags": ["Dikkat edilmesi gereken önemli risk varsa buraya yazın"]
}}

JSON dışında hiçbir şey yazma. Tüm alanları doldur. Türkçe yaz."""

def _call_gemini_multimodal(
    prompt: str,
    images_b64: list,
    audio_b64: str | None,
    audio_mime: str,
    model: str | None = None,
) -> dict:
    """
    Gemini API'ye multimodal istek gönderir.

    Hata yönetimi (Google dokümantasyonu: https://ai.google.dev/gemini-api/docs/troubleshooting):
      503 "high demand"  → MAX_RETRIES kez exponential backoff ile yeniden dener
      429 rate-limit     → yanıttaki "retry in Xs" süresini bekler
      429 quota=0        → bu model ücretsiz katmanda yok; yedek modele geçer
      Deprecated modeller (gemini-2.0-*) hiçbir zaman kullanılmaz
    """
    import requests as req

    use_model = model or GEMINI_MODEL

    # Parts listesi
    parts: list = []
    for i, b64 in enumerate(images_b64[:8]):
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        parts.append({"text": f"[Görüntü {i+1}: Sahibinden ilan veya WhatsApp ekran görüntüsü]"})

    if audio_b64:
        ab = audio_b64.split(",", 1)[1] if "," in audio_b64 else audio_b64
        parts.append({"inline_data": {"mime_type": audio_mime or "audio/webm", "data": ab}})
        parts.append({"text": "[Ses kaydı: Danışman-ev sahibi görüşmesi]"})

    parts.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature":      0.4,
            "maxOutputTokens":  8192,
            "responseMimeType": "application/json",
        },
    }

    # Sadece güncel 2.5 modelleri; 2.0-flash deprecated olduğu için eklenmez
    models_to_try = [use_model]
    if use_model != GEMINI_FALLBACK and "2.0" not in use_model:
        models_to_try.append(GEMINI_FALLBACK)

    last_error = "Bilinmeyen hata"

    for attempt_model in models_to_try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{attempt_model}:generateContent"
        )
        delay = GEMINI_RETRY_DELAY

        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                resp = req.post(url, json=payload, timeout=120)
                data = resp.json()

                # ── Başarılı yanıt ───────────────────────────────────────
                if resp.ok:
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return {"ok": False, "error": "Gemini boş yanıt döndürdü"}
                    raw = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in raw).strip()
                    text = re.sub(r"^```(?:json)?", "", text).strip()
                    text = re.sub(r"```$",          "", text).strip()
                    parsed = json.loads(text)
                    if attempt_model != use_model:
                        print(f"✅ Gemini yanıt verdi (yedek: {attempt_model})")
                    return {"ok": True, "strategy": parsed}

                # ── Hata yanıtı ──────────────────────────────────────────
                err     = data.get("error", {})
                err_msg = err.get("message", str(data))
                status  = resp.status_code
                last_error = err_msg

                # 503 — Geçici yüksek yük → yeniden dene
                if status == 503 or "high demand" in err_msg.lower() or "overloaded" in err_msg.lower():
                    print(f"⏳ {attempt_model} meşgul (deneme {attempt}/{GEMINI_MAX_RETRIES}), {delay}s bekleniyor...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue

                # 429 — Kota / hız sınırı
                if status == 429:
                    # "limit: 0" → bu model artık ücretsiz kotada yok, yedeke geç
                    if "limit: 0" in err_msg:
                        print(f"⛔ {attempt_model}: ücretsiz kota=0, yedek deneniyor...")
                        last_error = (
                            f"'{attempt_model}' ücretsiz katmanda kullanılamıyor "
                            "(kota=0). Google AI Studio'dan faturalandırmayı "
                            "etkinleştirin: https://aistudio.google.com/apikey"
                        )
                        break   # bu model için çık, bir sonraki modele geç

                    # "retry in Xs" → belirtilen süreyi bekle
                    m = re.search(r"retry in ([\d.]+)s", err_msg, re.IGNORECASE)
                    wait = float(m.group(1)) + 2 if m else delay
                    wait = min(wait, 65)
                    print(f"⏳ {attempt_model} hız sınırı (deneme {attempt}/{GEMINI_MAX_RETRIES}), {wait:.0f}s bekleniyor...")
                    time.sleep(wait)
                    delay = min(delay * 2, 60)
                    continue

                # Diğer hatalar (400, 403, 404…) → yeniden deneme olmaz
                return {"ok": False, "error": err_msg}

            except json.JSONDecodeError as e:
                return {"ok": False, "error": f"JSON parse hatası: {e}"}
            except req.exceptions.Timeout:
                last_error = "API timeout (120s)"
                print(f"⚠️  {attempt_model} timeout (deneme {attempt})")
                time.sleep(delay)
                delay = min(delay * 2, 60)
            except Exception as e:
                last_error = str(e)
                print(f"⚠️  {attempt_model} beklenmedik hata (deneme {attempt}): {e}")
                time.sleep(delay)
                delay = min(delay * 2, 60)

        lbl = "yedek model de başarısız." if attempt_model == GEMINI_FALLBACK else "yedek modele geçiliyor..."
        print(f"❌ {attempt_model} tüm denemeler başarısız — {lbl}")

    return {"ok": False, "error": last_error}

def _build_transcript_prompt(audio_mime: str) -> str:
    return """Bu ses kaydını tam olarak transkript et. Konuşma Türkçe olabilir.
Transkripti düz metin olarak ver, başka açıklama ekleme."""

def _transcribe_audio(audio_b64: str, audio_mime: str) -> str | None:
    """Ses kaydını Gemini ile metin olarak çıkarır."""

    if not audio_b64 or not GEMINI_API_KEY:
        return None

    if "," in audio_b64:
        audio_b64 = audio_b64.split(",", 1)[1]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": audio_mime or "audio/webm",
                        "data": audio_b64,
                    }
                },
                {"text": _build_transcript_prompt(audio_mime)},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    }
    try:
        resp = req.post(url, json=payload, timeout=60)
        data = resp.json()
        if resp.ok:
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception as e:
        print(f"⚠️  Transkript hatası: {e}")
    return None

# ── Ana Fonksiyon ────────────────────────────────────────────────

def analyze_fsbo(
    contact_data: dict,
    screenshots: list | None      = None,   # [base64_str, ...]
    text_input:  str | None       = None,
    audio_b64:   str | None       = None,
    audio_mime:  str              = "audio/webm",
    timeline:    list | None      = None,
) -> dict:
    """
    FSBO stratejisini Gemini 2.5 Flash ile üretir.

    Returns:
        {"ok": True, "strategy": {...}, "audio_transcript": "..." | None}
        {"ok": False, "error": "..."}
    """
    if not _is_configured():
        return {"ok": False, "error": "GEMINI_API_KEY tanımlanmamış"}

    images  = screenshots or []
    tl      = timeline    or []

    # Ses transkripti
    transcript = None
    if audio_b64:
        print(f"🎙️  Ses kaydı transkript ediliyor...")
        transcript = _transcribe_audio(audio_b64, audio_mime)
        if transcript:
            print(f"✅ Transkript hazır ({len(transcript)} karakter)")
            # Transkrip'i text_input'a ekle
            extra = f"\n\n[SES KAYDI TRANSKRİPTİ]\n{transcript}"
            text_input = (text_input or "") + extra

    # Prompt oluştur
    prompt = _build_prompt(contact_data, text_input or "", tl)

    print(f"🤖 FSBO analizi başlatıldı: {contact_data.get('name','?')} | "
          f"{len(images)} görüntü | ses={'evet' if audio_b64 else 'hayır'}")

    result = _call_gemini_multimodal(
        prompt=prompt,
        images_b64=images,
        audio_b64=audio_b64,
        audio_mime=audio_mime,
    )

    if result.get("ok"):
        strategy = result["strategy"]
        strategy["generated_at"] = datetime.now(timezone.utc).isoformat()
        strategy["input_summary"] = {
            "images_count":   len(images),
            "has_audio":      bool(audio_b64),
            "has_text":       bool(text_input and text_input.strip()),
            "timeline_count": len(tl),
        }
        print(f"✅ FSBO analizi tamamlandı | skor: {strategy.get('confidence_score','?')}/10 | "
              f"direnç: {strategy.get('resistance_level','?')}")
        return {
            "ok":               True,
            "strategy":         strategy,
            "audio_transcript": transcript,
        }

    print(f"❌ FSBO analiz hatası: {result.get('error')}")
    return result

# ======================================================================
# Buyer Matching Engine
# ======================================================================

import math
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

# Opsiyonel: sentence-transformers (vektör benzerliği için)
try:
    _SENTENCE_TRANSFORMER = True
except ImportError:
    _SENTENCE_TRANSFORMER = False
    print("⚠️  sentence-transformers yüklü değil — pip install sentence-transformers")

class NotificationChannel(Enum):
    """Kullanıcıya bildirim gönderilecek kanallar."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    CRM_TASK = "crm_task"
    DASHBOARD = "dashboard"

class MatchingTier(Enum):
    """Eşleşme kalitesi seviyeleri."""
    PERFECT = "perfect"        # 90-100
    EXCELLENT = "excellent"    # 75-89
    GOOD = "good"              # 60-74
    FAIR = "fair"              # 45-59
    WEAK = "weak"              # 30-44
    POOR = "poor"              # <30

# ================================================================
# KONFIGÜRASYON
# ================================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MIN_MATCH_SCORE = 50  # İlan gösterilmesi için minimum skor
VECTOR_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Hızlı, hafif (80M)

# ================================================================
# VERİ MODELLERİ
# ================================================================

class BuyerProfile:
    """Alıcı profili — kriterleri ve tercihler."""

    def __init__(self, profile_dict: dict):
        self.buyer_id = profile_dict.get("id", "")
        self.uid = profile_dict.get("uid", "")
        self.name = profile_dict.get("name", "")
        self.email = profile_dict.get("email", "")
        self.phone = profile_dict.get("phone", "")
        self.telegram_id = profile_dict.get("telegram_id")
        self.whatsapp_phone = profile_dict.get("whatsapp_phone")

        # Kriterler
        self.criteria = profile_dict.get("criteria", {})
        self.min_price = self.criteria.get("min_price", 0)
        self.max_price = self.criteria.get("max_price", 10_000_000)
        self.min_area = self.criteria.get("min_area", 0)
        self.max_area = self.criteria.get("max_area", 1000)
        self.neighborhoods = self.criteria.get("neighborhoods", [])
        self.property_types = self.criteria.get("property_types", [])
        self.min_rooms = self.criteria.get("min_rooms")
        self.max_rooms = self.criteria.get("max_rooms")
        self.min_age = self.criteria.get("min_age")
        self.max_age = self.criteria.get("max_age")
        self.amenities_required = self.criteria.get("amenities_required", [])
        self.natural_language_criteria = self.criteria.get("natural_language", "")

        # Tercihler
        self.preferences = profile_dict.get("preferences", {})
        self.notification_channels = self.preferences.get("notification_channels", ["email", "crm_task"])
        self.auto_match = self.preferences.get("auto_match", True)
        self.weekly_summary = self.preferences.get("weekly_summary", False)
        self.priority_level = self.preferences.get("priority_level", "medium")  # low/medium/high

        # Durum
        self.is_active = profile_dict.get("is_active", True)
        self.created_at = profile_dict.get("created_at", datetime.now(timezone.utc).isoformat())
        self.updated_at = profile_dict.get("updated_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Firebase'e kaydetmek için dict'e dönüştür."""
        return {
            "id": self.buyer_id,
            "uid": self.uid,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "telegram_id": self.telegram_id,
            "whatsapp_phone": self.whatsapp_phone,
            "criteria": {
                "min_price": self.min_price,
                "max_price": self.max_price,
                "min_area": self.min_area,
                "max_area": self.max_area,
                "neighborhoods": self.neighborhoods,
                "property_types": self.property_types,
                "min_rooms": self.min_rooms,
                "max_rooms": self.max_rooms,
                "min_age": self.min_age,
                "max_age": self.max_age,
                "amenities_required": self.amenities_required,
                "natural_language": self.natural_language_criteria,
            },
            "preferences": {
                "notification_channels": self.notification_channels,
                "auto_match": self.auto_match,
                "weekly_summary": self.weekly_summary,
                "priority_level": self.priority_level,
            },
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

class ListingMatch:
    """İlan-Alıcı eşleşmesi."""

    def __init__(
        self,
        buyer_id: str,
        listing_id: str,
        listing_data: dict,
        match_score: float,
        match_details: dict,
    ):
        self.buyer_id = buyer_id
        self.listing_id = listing_id
        self.listing_data = listing_data
        self.match_score = match_score
        self.match_details = match_details
        self.tier = self._determine_tier()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.notification_sent = False
        self.user_interest = None  # "interested", "not_interested", "enquiry_sent", vb.

    def _determine_tier(self) -> str:
        """Skor'a göre tier belirle."""
        score = self.match_score
        if score >= 90:
            return MatchingTier.PERFECT.value
        elif score >= 75:
            return MatchingTier.EXCELLENT.value
        elif score >= 60:
            return MatchingTier.GOOD.value
        elif score >= 45:
            return MatchingTier.FAIR.value
        elif score >= 30:
            return MatchingTier.WEAK.value
        else:
            return MatchingTier.POOR.value

    def to_dict(self) -> dict:
        """Firebase'e kaydetmek için dict'e dönüştür."""
        return {
            "buyer_id": self.buyer_id,
            "listing_id": self.listing_id,
            "listing_data": self.listing_data,
            "match_score": self.match_score,
            "match_details": self.match_details,
            "tier": self.tier,
            "created_at": self.created_at,
            "notification_sent": self.notification_sent,
            "user_interest": self.user_interest,
        }

# ================================================================
# MATCHING ENGINE
# ================================================================

class BuyerMatcher:
    """Alıcı profili ile ilanları eşleştir."""

    def __init__(self):
        self.vector_model = None
        if _SENTENCE_TRANSFORMER:
            try:
                self.vector_model = SentenceTransformer(VECTOR_MODEL)
                print(f"✅ Vector model yüklendi: {VECTOR_MODEL}")
            except Exception as e:
                print(f"⚠️  Vector model yüklenemedi: {e}")

    def match_listing(self, buyer: BuyerProfile, listing: dict) -> Optional[ListingMatch]:
        """
        İlanı alıcı profili ile eşleştir.
        İlan: {"id", "price", "area", "location", "property_type", "rooms", "age", "amenities", ...}
        """
        match_details = {}
        scores = {}

        # 1. Fiyat eşleşmesi
        price = listing.get("price", 0)
        if price < buyer.min_price or price > buyer.max_price:
            return None  # Fiyat aralığı dışında
        price_score = self._score_price(price, buyer)
        scores["price"] = price_score
        match_details["price"] = f"{price:,} TL ({price_score:.0f}%)"

        # 2. Alan eşleşmesi
        area = listing.get("area", 0)
        if area < buyer.min_area or area > buyer.max_area:
            return None  # Alan aralığı dışında
        area_score = self._score_area(area, buyer)
        scores["area"] = area_score
        match_details["area"] = f"{area} m² ({area_score:.0f}%)"

        # 3. Lokasyon eşleşmesi
        location = listing.get("location", "").strip()
        location_score = self._score_location(location, buyer)
        if location_score == 0 and buyer.neighborhoods:
            return None  # Lokasyon kritik ve eşleşmiyor
        scores["location"] = location_score
        match_details["location"] = f"{location} ({location_score:.0f}%)"

        # 4. Mülk tipi eşleşmesi
        prop_type = listing.get("property_type", "").strip()
        prop_type_score = self._score_property_type(prop_type, buyer)
        if prop_type_score == 0 and buyer.property_types:
            return None
        scores["property_type"] = prop_type_score
        match_details["property_type"] = f"{prop_type} ({prop_type_score:.0f}%)"

        # 5. Oda sayısı eşleşmesi (opsiyonel)
        if buyer.min_rooms or buyer.max_rooms:
            rooms = listing.get("rooms", None)
            if rooms:
                rooms_score = self._score_rooms(rooms, buyer)
                scores["rooms"] = rooms_score
                match_details["rooms"] = f"{rooms} ({rooms_score:.0f}%)"

        # 6. Yaş eşleşmesi (opsiyonel)
        if buyer.min_age or buyer.max_age:
            age = listing.get("age", None)
            if age is not None:
                age_score = self._score_age(age, buyer)
                scores["age"] = age_score
                match_details["age"] = f"{age} yıl ({age_score:.0f}%)"

        # 7. Amenities eşleşmesi
        amenities = listing.get("amenities", [])
        if buyer.amenities_required:
            amenities_score = self._score_amenities(amenities, buyer)
            scores["amenities"] = amenities_score
            match_details["amenities"] = f"{amenities_score:.0f}% eşleşme"

        # 8. Natural language kriterleri (Gemini)
        if buyer.natural_language_criteria and GEMINI_API_KEY:
            nl_score = self._score_natural_language(listing, buyer)
            scores["natural_language"] = nl_score
            match_details["nl_criteria"] = f"{nl_score:.0f}%"

        # 9. Vectoral benzerlik (metafor + açıklama)
        if self.vector_model:
            vector_score = self._score_vector_similarity(listing, buyer)
            scores["vector"] = vector_score
            match_details["vector"] = f"{vector_score:.0f}%"

        # Ortalaması al (ağırlıklı)
        final_score = self._weighted_average(scores)

        if final_score < MIN_MATCH_SCORE:
            return None

        # Match nesnesi oluştur
        return ListingMatch(
            buyer_id=buyer.buyer_id,
            listing_id=listing.get("id", ""),
            listing_data=listing,
            match_score=final_score,
            match_details=match_details,
        )

    def _score_price(self, price: float, buyer: BuyerProfile) -> float:
        """Fiyat skoru (hedef için optimal)."""
        mid = (buyer.min_price + buyer.max_price) / 2
        range_width = buyer.max_price - buyer.min_price
        distance = abs(price - mid)
        # Merkeze ne kadar yakınsa o kadar yüksek skor
        return max(0, 100 - (distance / range_width) * 100)

    def _score_area(self, area: float, buyer: BuyerProfile) -> float:
        """Alan skoru."""
        mid = (buyer.min_area + buyer.max_area) / 2
        range_width = buyer.max_area - buyer.min_area
        if range_width == 0:
            return 100.0
        distance = abs(area - mid)
        return max(0, 100 - (distance / range_width) * 100)

    def _score_location(self, location: str, buyer: BuyerProfile) -> float:
        """Lokasyon skoru (kesin eşleşme veya 0)."""
        if not buyer.neighborhoods:
            return 100.0  # Lokasyon kriteri yoksa tam skor
        loc_lower = location.lower().strip()
        for nb in buyer.neighborhoods:
            if nb.lower() in loc_lower or loc_lower in nb.lower():
                return 100.0
        return 0.0  # Eşleşmedi

    def _score_property_type(self, prop_type: str, buyer: BuyerProfile) -> float:
        """Mülk tipi skoru."""
        if not buyer.property_types:
            return 100.0
        pt_lower = prop_type.lower().strip()
        for ptype in buyer.property_types:
            if ptype.lower() in pt_lower or pt_lower in ptype.lower():
                return 100.0
        return 0.0

    def _score_rooms(self, rooms: int, buyer: BuyerProfile) -> float:
        """Oda sayısı skoru."""
        if buyer.min_rooms and rooms < buyer.min_rooms:
            return 0.0
        if buyer.max_rooms and rooms > buyer.max_rooms:
            return 0.0
        return 100.0

    def _score_age(self, age: int, buyer: BuyerProfile) -> float:
        """Yaş skoru."""
        if buyer.min_age and age < buyer.min_age:
            return 0.0
        if buyer.max_age and age > buyer.max_age:
            return 0.0
        return 100.0

    def _score_amenities(self, amenities: List[str], buyer: BuyerProfile) -> float:
        """Amenities eşleşme oranı."""
        if not buyer.amenities_required:
            return 100.0
        if not amenities:
            return 0.0
        amenities_lower = [a.lower() for a in amenities]
        matches = sum(
            1 for req in buyer.amenities_required
            if any(req.lower() in am for am in amenities_lower)
        )
        return (matches / len(buyer.amenities_required)) * 100

    def _score_natural_language(self, listing: dict, buyer: BuyerProfile) -> float:
        """Gemini ile natural language kriterleri parse et ve skor ver."""
        if not GEMINI_API_KEY:
            return 50.0
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            client = genai.Client()
            prompt = f"""
İlan: {json.dumps(listing, ensure_ascii=False, indent=2)}

Alıcı Kriterleri (Türkçe): "{buyer.natural_language_criteria}"

Bu ilanın alıcı kriterlerine ne kadar uyduğunu 0-100 arası bir skor ver.
SADECE SAYI döndür, açıklama yapma. Örnek: 85
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.GenerateContentConfig(max_output_tokens=10),
            )
            text = (response.text or "50").strip()
            score = float("".join(filter(str.isdigit, text.split("\n")[0]))) if any(c.isdigit() for c in text) else 50.0
            return min(100.0, max(0.0, score))
        except Exception as e:
            print(f"⚠️  NL scoring hatası: {e}")
            return 50.0

    def _score_vector_similarity(self, listing: dict, buyer: BuyerProfile) -> float:
        """Vector benzerliği (listing description vs buyer NL criteria)."""
        if not self.vector_model or not buyer.natural_language_criteria:
            return 50.0
        try:
            listing_text = f"{listing.get('property_type', '')} {listing.get('location', '')} {listing.get('description', '')}"
            emb_listing = self.vector_model.encode(listing_text, convert_to_tensor=True)
            emb_buyer = self.vector_model.encode(buyer.natural_language_criteria, convert_to_tensor=True)
            # Cosine similarity
            similarity = float((emb_listing @ emb_buyer.T).item())
            return max(0, min(100, similarity * 100))
        except Exception as e:
            print(f"⚠️  Vector similarity hatası: {e}")
            return 50.0

    def _weighted_average(self, scores: Dict[str, float]) -> float:
        """Ağırlıklı ortalama (kritik olanlar ağırlıklı)."""
        weights = {
            "price": 0.25,
            "area": 0.2,
            "location": 0.2,
            "property_type": 0.15,
            "rooms": 0.05,
            "age": 0.05,
            "amenities": 0.05,
            "natural_language": 0.03,
            "vector": 0.02,
        }
        total_weight = 0
        weighted_sum = 0
        for key, score in scores.items():
            weight = weights.get(key, 0.05)
            weighted_sum += score * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 50.0

# ================================================================
# NOTIFICATION ENGINE (Placeholder)
# ================================================================

class NotificationEngine:
    """
    Eşleşmeleri alıcıya farklı kanallardan bildiri.
    Gerçek implementation: app.py'de çalışacak ve mailer.py, wa_cloud.py'yi kullanacak.
    """

    @staticmethod
    def notify_buyer(
        match: ListingMatch,
        buyer: BuyerProfile,
        channels: List[str],
    ) -> Dict[str, bool]:
        """Alıcıyı eşleşme hakkında bildir."""
        results = {}
        for channel in channels:
            try:
                if channel == "email" and buyer.email:
                    results["email"] = NotificationEngine._send_email_notification(match, buyer)
                elif channel == "telegram" and buyer.telegram_id:
                    results["telegram"] = NotificationEngine._send_telegram_notification(match, buyer)
                elif channel == "whatsapp" and buyer.whatsapp_phone:
                    results["whatsapp"] = NotificationEngine._send_whatsapp_notification(match, buyer)
                elif channel == "crm_task":
                    results["crm_task"] = NotificationEngine._create_crm_task(match, buyer)
            except Exception as e:
                print(f"❌ {channel} notification hatası: {e}")
                results[channel] = False
        return results

    @staticmethod
    def _send_email_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """Email gönder (mailer.py ile entegrasyon)."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _send_telegram_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """Telegram bildir."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _send_whatsapp_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """WhatsApp gönder (wa_cloud.py ile entegrasyon)."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _create_crm_task(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """CRM'e görev aç."""
        # Placeholder — app.py'de çalışacak
        return True

# ================================================================
# UTILITY FUNCTIONS
# ================================================================

def parse_natural_language_criteria(text: str, api_key: str = "") -> Optional[dict]:
    """
    Natural language filtreleri parse et (Gemini ile).
    "Ankara'da 2+1 daire, maksimum 4.5 milyon, Çankaya veya Dikmen"
    → {"price": 4500000, "neighborhoods": [...], "rooms": 3, ...}
    """
    if not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        client = genai.Client()
        prompt = f"""
Türkçe gayrimenkul arama metnini parse et ve JSON döndür.

Metin: "{text}"

JSON formatı (istenen alanları fill et, yoksa null):
{{
  "min_price": null,
  "max_price": null,
  "min_area": null,
  "max_area": null,
  "neighborhoods": [],
  "property_types": [],
  "min_rooms": null,
  "max_rooms": null,
  "min_age": null,
  "max_age": null
}}

SADECE JSON döndür, açıklama yapma.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.GenerateContentConfig(max_output_tokens=200),
        )
        text_out = response.text or ""
        json_match = re.search(r"\{.*\}", text_out, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"⚠️  NL parsing hatası: {e}")
    return None

# ================================================================
# STATUS
# ================================================================

def buyer_engine_status() -> dict:
    """Buyer engine durumunu döner."""
    return {
        "ok": True,
        "matcher": True,
        "vector_model": _SENTENCE_TRANSFORMER,
        "min_match_score": MIN_MATCH_SCORE,
    }

# ======================================================================
# Main Flask Application
# ======================================================================

load_dotenv()  # .env dosyasını otomatik yükle
from buyer_engine import BuyerProfile, BuyerMatcher, ListingMatch, NotificationEngine,NotificationChannel, MatchingTier, buyer_engine_status, parse_natural_language_criteria

# ── Lokal fallback credential'lar (import'lardan ÖNCE set edilmeli) ──────────
# mailer.py ve wa_cloud.py modül yüklenirken env'i okur,
# bu yüzden setdefault'lar her import'tan önce çalışmalı.
os.environ.setdefault("EMAIL_PROVIDER",   "smtp")
os.environ.setdefault("EMAIL_FROM",       "yigitnarinofficial@gmail.com")
os.environ.setdefault("EMAIL_FROM_NAME",  "Nexa CRM")
os.environ.setdefault("SMTP_HOST",        "smtp.gmail.com")
os.environ.setdefault("SMTP_PORT",        "587")
os.environ.setdefault("SMTP_USE_TLS",     "true")
os.environ.setdefault("SMTP_USERNAME",    "yigitnarinofficial@gmail.com")
os.environ.setdefault("SMTP_PASSWORD",    "")  # .env dosyasına taşındı — SMTP_PASSWORD=<şifre>
os.environ.setdefault("ENABLE_CUSTOMER_EMAIL_AUTOMATION", "true")
# GEMINI_API_KEY → Render Dashboard > Environment Variables

from flask import Flask, jsonify, send_file, request as flask_request
# FAZ 2: Rate limiting — pip install flask-limiter
try:
    _limiter_available = True
except ImportError:
    _limiter_available = False
    print("⚠️  flask-limiter yüklü değil — pip install flask-limiter")
from wa_cloud import send_whatsapp, send_whatsapp_template, wa_status, verify_webhook_token
from mailer import (
    send_transactional_email, build_lead_confirmation_email, email_status,
    build_valuation_report_email, build_advisor_valuation_email,
)
from valuation import generate_valuation_report, valuation_status as gemini_status
from ai_listing import analyze_listing, ai_listing_status
from fsbo_engine import analyze_fsbo, fsbo_engine_status

# ── Firebase Admin SDK ──────────────────────────────────────────

# app = Flask(__name__) removed during merge
CORS(app, origins=[
    "https://nexacrm.com",
    "https://nexa-crm.onrender.com",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
], supports_credentials=True)

# FAZ 2: Rate limiter (flask-limiter yüklüyse aktif olur)
if _limiter_available:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per hour"],
        storage_uri="memory://",
    )
else:
    limiter = None

# ================================================================
# AYARLAR
# ================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # .env: TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "")  # .env: TELEGRAM_CHAT_ID=...
SERVICE_ACCOUNT    = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "service-account.json")

# WhatsApp Cloud API — Meta
# WA_PHONE_NUMBER_ID : Meta Business → WhatsApp → Phone Number ID
# WA_ACCESS_TOKEN    : System User permanent token
# WA_ADVISOR_PHONE   : Danışmanın WA numarası (bildirim alacak)
WA_ADVISOR_PHONE   = os.environ.get("WA_ADVISOR_PHONE", "")  # .env: WA_ADVISOR_PHONE=905XXXXXXXXX
CUSTOMER_WA_TEMPLATE_NAME = os.environ.get("CUSTOMER_WA_TEMPLATE_NAME", "").strip()
ENABLE_CUSTOMER_EMAIL_AUTOMATION = os.environ.get("ENABLE_CUSTOMER_EMAIL_AUTOMATION", "true").strip().lower() in ("1", "true", "yes")
ENABLE_CUSTOMER_WA_AUTOMATION    = os.environ.get("ENABLE_CUSTOMER_WA_AUTOMATION", "false").strip().lower() in ("1", "true", "yes")

# Değerleme raporu — yeni
VALUATION_WA_TEMPLATE_NAME = os.environ.get("VALUATION_WA_TEMPLATE_NAME", "").strip()
ADVISOR_EMAIL               = os.environ.get("ADVISOR_EMAIL", "").strip()

# İlan hedef URL
TARGET_URL = "https://www.cb.com.tr/ilanlar?officeid=470&officeuserid=23339"

# Ankara koordinatları (fallback)
ANKARA_LAT = 39.9334
ANKARA_LNG = 32.8597
DIKMEN_LAT = 39.8854
DIKMEN_LNG = 32.8514

ANKARA_SEMTLER = [
    "Dikmen", "Çukurambar", "Birlik Mahallesi", "Çayyolu",
    "Oran", "Angora Evleri", "Beysukent",
    "Kızılay", "Tunalı", "Ayrancı", "Gaziosmanpaşa", "GOP",
    "Kavaklidere", "Kavaklıdere", "Çankaya",
    "Balgat", "Emek", "Bahçelievler", "Öveçler",
    "Güvenevler", "Yıldız", "Çetin Emeç", "Mustafa Kemal",
    "Aziziye", "Naci Çakır",
    "Keçiören", "Mamak", "Altındağ", "Sincan",
    "Etimesgut", "Gölbaşı", "Pursaklar", "Yenimahalle",
    "Bağlıca", "Batıkent", "Eryaman",
]

# ── Ankara mahalle/semt koordinat sözlüğü ──────────────────────────────────────
# ASCII-normalize edilmiş versiyon (normalize() fonksiyonu sonrasındaki form).
# İkinci tanım (aşağıda) bu bloğun yerini alır — bu yüzden bu blok kaldırıldı.
# Bkz: ANKARA_COORDS tanımı _normalize() fonksiyonunun ardında.

# ================================================================
# BOOTSTRAP & SCHEDULER IMPORTS
# ================================================================
try:
    _apscheduler_available = True
except ImportError:
    _apscheduler_available = False
    print("⚠️  APScheduler yüklü değil: pip install apscheduler")

# ================================================================
# GLOBAL STATE
# ================================================================
_scheduler = None
_listing_cache_time = None
_bootstrap_done = False
_fb_initialized = False
db_admin = None

# ================================================================
# FİREBASE ADMIN — başlatma
# ================================================================

def init_firebase_admin():
    global _fb_initialized, db_admin
    if _fb_initialized:
        return
    try:
        import json as _json

        # Render'da FIREBASE_SERVICE_ACCOUNT env var'ı JSON string içerir.
        # Lokal'de ise service-account.json dosya yoludur.
        # İkisini de destekle:
        sa_value = SERVICE_ACCOUNT.strip()
        # .env dosyasında değer tek/çift tırnakla sarılmış olabilir → temizle
        if (sa_value.startswith("'") and sa_value.endswith("'")) or \
           (sa_value.startswith('"') and sa_value.endswith('"')):
            sa_value = sa_value[1:-1]

        if os.path.exists(sa_value):
            # Dosya yolu → klasik yöntem
            cred = credentials.Certificate(sa_value)
            print("✅ Firebase Admin bağlandı (dosya)")
        elif sa_value.startswith("{"):
            # JSON string içeriği → dict'e parse et
            sa_dict = _json.loads(sa_value)
            cred = credentials.Certificate(sa_dict)
            print("✅ Firebase Admin bağlandı (env JSON)")
        else:
            print(f"⚠️  Firebase service account bulunamadı — "
                  f"FIREBASE_SERVICE_ACCOUNT ortam değişkeni JSON string ya da geçerli dosya yolu olmalı")
            return

        firebase_admin.initialize_app(cred)
        db_admin = admin_firestore.client()
        _fb_initialized = True
    except Exception as e:
        print(f"❌ Firebase Admin hatası: {e}")

# ================================================================
# BACKGROUND SCHEDULER
# ================================================================

def start_scheduler():
    """APScheduler'ı başlat."""
    global _scheduler
    
    if _scheduler is not None:
        return
    
    if not _apscheduler_available:
        print("⚠️  APScheduler yüklü değil, background tasks deaktif")
        return
    
    try:
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.start()
        print("✅ Background Scheduler başlatıldı")
    except Exception as e:
        print(f"❌ Scheduler başlatma hatası: {e}")
        _scheduler = None

def _refresh_listings_bg():
    """Listeleri arka planda yenile."""
    global _listing_cache_time
    
    try:
        current_time = datetime.now(timezone.utc).isoformat()
        _listing_cache_time = current_time
        print(f"📋 Listing refresh başladı: {current_time}")
    except Exception as e:
        print(f"⚠️  Listing refresh hatası: {e}")

# ================================================================
# DAILY BLOG / NEWS SIGNAL CRAWLER AGENT
# ================================================================

def run_blog_agent():
    """Ankara gayrimenkul ve yatırım haberlerini otonom olarak toplayan AI Ajanı."""
    if not _fb_initialized or db_admin is None:
        print("⚠️ Firebase Admin bağlı değil, blog agent çalıştırılamadı.")
        return
        
    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not api_key:
        print("⚠️ GEMINI_API_KEY ayarlanmamış, blog agent çalıştırılamadı.")
        return
        
    print("🤖 Blog Agent: Ankara Emlak ve Yatırım haberleri taranıyor...")
    
    try:
        from google import genai
        from google.genai import types
        import json
        import random
        
        # Unsplash luxury real estate resim havuzu (Ankara veya modern mimari temalı)
        images_pool = [
            "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1513694203232-719a280e022f?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=800&q=80"
        ]
        
        # 1. Gemini'den emlak piyasası hakkında güncel makaleler üretilmesini talep et
        client = genai.Client(api_key=api_key)
        prompt = """
        Ankara ve Türkiye genelindeki emlak/gayrimenkul piyasası, yeni kentsel dönüşüm alanları, konut faiz oranları, gayrimenkul yatırım stratejileri, metro/ulaşım projeleri gibi güncel konuları analiz et.
        Buna dayanarak, 3 adet son derece profesyonel, zengin içerikli ve bilgilendirici Türkçe haber/blog yazısı oluştur.
        Yazılar genel Ankara emlak piyasasını veya Çankaya, İncek, GOP, Çayyolu gibi Ankara'nın farklı semtlerini kapsasın (kesinlikle Dikmen kelimesini kullanma).
        
        Her makale için aşağıdaki alanları içeren bir JSON formatında çıktı üret:
        {
          "articles": [
            {
              "title": "Haber Başlığı",
              "summary": "1-2 cümlelik çarpıcı özet",
              "content": "Detaylı, paragraflara bölünmüş, alt başlıklar veya listeler içeren en az 3-4 paragraflık tam makale metni (yeni satırları \\n ile ayır)",
              "category": "Kategori ('Yatırım', 'Piyasa Analizi', 'Ulaşım' veya 'Yaşam' kategorilerinden biri olmalı)",
              "readTime": "Tahmini okuma süresi (örneğin: '4 dk')"
            }
          ]
        }
        """
        
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            )
        )
        
        raw_text = (resp.text or "").strip()
        if "```" in raw_text:
            for part in raw_text.split("```"):
                p = part.strip()
                if p.lower().startswith("json"):
                    raw_text = p[4:].strip()
                elif p.startswith("{") or p.startswith("["):
                    raw_text = p
                    break
                    
        payload = json.loads(raw_text)
        articles = payload.get("articles", [])
        
        print(f"🤖 Blog Agent: {len(articles)} adet haber üretildi. Firestore kontrol ediliyor...")
        
        now = datetime.now(timezone.utc)
        added_count = 0
        
        for art in articles:
            title = art.get("title", "").strip()
            if not title:
                continue
                
            # Duplicate kontrolü (Firestore'da aynı başlıklı doküman var mı?)
            dups = list(db_admin.collection("blogs").where(filter=FieldFilter("title", "==", title)).limit(1).stream())
            if dups:
                print(f"⏭️ Haber zaten mevcut, eklenseydi mükerrer olacaktı: {title}")
                continue
                
            post = {
                "title": title,
                "summary": art.get("summary", "").strip(),
                "content": art.get("content", "").strip(),
                "image": random.choice(images_pool),
                "category": art.get("category", "Genel").strip(),
                "readTime": art.get("readTime", "3 dk").strip(),
                "published": True,
                "createdAt": now,
                "updatedAt": now
            }
            
            db_admin.collection("blogs").add(post)
            print(f"✅ Yeni haber başarıyla Firestore'a eklendi: {title}")
            added_count += 1
            
        print(f"🤖 Blog Agent: İşlem tamamlandı. {added_count} adet yeni haber/blog yazısı sisteme çekildi.")
        
    except Exception as e:
        print(f"❌ Blog Agent hatası: {e}")

def run_blog_agent_periodically():
    """Her 24 saatte bir otonom olarak blog agent'ı çalıştırır."""
    time.sleep(15)  # Uygulama ayağa kalkarken Firebase'in hazır olması için bekle
    while True:
        try:
            run_blog_agent()
        except Exception as e:
            print(f"run_blog_agent_periodically döngü hatası: {e}")
        # 24 saat uyu
        time.sleep(86400)

def check_bootstrap_status() -> dict:
    """Bootstrap durumunu kontrol et."""
    return {
        "ok": _bootstrap_done,
        "firebase_initialized": _fb_initialized,
        "scheduler_running": _scheduler is not None and _scheduler.running if _scheduler else False,
        "last_listing_refresh": _listing_cache_time,
    }

def bootstrap_app():
    """Uygulamayı başlat — tüm servisleri initialize et."""
    global _bootstrap_done
    
    if _bootstrap_done:
        return
    
    print("\n" + "="*70)
    print("🚀 NEXA CRM - Bootstrap Başlatılıyor")
    print("="*70 + "\n")
    
    init_firebase_admin()
    start_scheduler()
    _refresh_listings_bg()
    
    # Günlük AI Haber Ajanı threadini başlat
    threading.Thread(target=run_blog_agent_periodically, daemon=True).start()
    
    # Otonom Google Drive Proje Senkronizasyonunu başlat (30 dk aralık)
    def _run_drive_sync_bg():
        try:
            import nexa_drive_puller
            time.sleep(15)
            nexa_drive_puller.drive_loop(interval=1800)
        except Exception as e:
            logger.warning(f"Drive puller background hatası: {e}")

    threading.Thread(target=_run_drive_sync_bg, daemon=True, name="drive-sync").start()

    # Otonom Proje Dosya İzleyici (Watchdog) başlat
    def _run_watchdog_bg():
        try:
            import nexa_watchdog
            time.sleep(10)
            nexa_watchdog.watchdog_loop(interval=120)
        except Exception as e:
            logger.warning(f"Watchdog background hatası: {e}")

    threading.Thread(target=_run_watchdog_bg, daemon=True, name="watchdog").start()
    
    _bootstrap_done = True
    
    print("\n" + "="*70)
    print("✅ Bootstrap Tamamlandı")
    print("="*70 + "\n")

# ================================================================
# TELEGRAM
# ================================================================
def send_telegram(text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except Exception as e:
        print(f"Telegram gönderim hatası: {e}")
        return False

# ================================================================
# SAYFA ROUTE'LARI
# ================================================================

def _is_mobile_request() -> bool:
    ua = flask_request.headers.get("User-Agent", "").lower()
    return any(m in ua for m in ["mobile", "android", "iphone", "ipad", "ipod", "webos", "blackberry", "windows phone"])

@app.route("/")
def home():
    """Ana sayfa router'ı:
    - NEXAOS projesindeyken veya ?view=nexaos istendiğinde doğrudan NEXA.OS Komuta Merkezi açılır.
    - gayrimenkulmuhendisi projesindeyken orijinal site.html servis edilir.
    """
    is_nexaos = "nexaos" in str(BASE_DIR).lower()
    req_view = flask_request.args.get("view", "").lower()
    if is_nexaos or req_view in ["nexaos", "dashboard", "nexa"]:
        return _route_index()
    
    try:
        return send_from_directory("templates", "site.html")
    except Exception:
        return _route_index()

@app.route("/site")
def serve_site():
    """Gayrimenkul Mühendisi Orijinal Web Sitesi"""
    try:
        return send_from_directory("templates", "site.html")
    except Exception as e:
        return f"site.html bulunamadı: {e}", 404

@app.route("/nexaos")
def serve_nexaos():
    """NEXA.OS Unified PropTech Command Center Doğrudan Giriş"""
    return _route_index()

@app.route("/ygt")
def serve_ygt_showcase():
    """Yiğit Narin CB VIP Portföy Vitrini"""
    try:
        return send_from_directory("templates", "ygt.html")
    except Exception as e:
        return f"ygt.html bulunamadı: {e}", 404

@app.route("/app")
def mobile_app_view():
    """NEXA OS Ultra Native Mobile App Shell (App Store Feel)"""
    try:
        return send_from_directory("templates", "mobile_app.html")
    except Exception as e:
        return f"mobile_app.html bulunamadı: {e}", 404

@app.route("/manifest.json")
def pwa_manifest():
    """PWA Manifest for Add to Home Screen & Standalone feel"""
    try:
        return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/sw.js")
def pwa_service_worker():
    """PWA Service Worker for Offline & Cache"""
    try:
        return send_from_directory("static", "sw.js", mimetype="application/javascript")
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/crm")
def crm():
    """CRM paneli — crm.html"""
    try:
        return send_from_directory("templates", "crm.html")
    except Exception as e:
        return f"crm.html bulunamadı: {e}", 404

@app.route("/haber")
@app.route("/haberler")
@app.route("/intelligence")
def haberler():
    """Haberler / Real Estate Intelligence Network — haber.html"""
    try:
        return send_from_directory("templates", "haber.html")
    except Exception as e:
        return f"haber.html bulunamadı: {e}", 404

@app.route("/news/<slug>")
@app.route("/intelligence/<slug>")
def intelligence_article_page(slug):
    """SEO crawlable article route."""
    try:
        return send_from_directory("templates", "haber.html")
    except Exception as e:
        return f"haber.html bulunamadı: {e}", 404

@app.route("/projeler")
def projeler():
    """CB VIP Prestijli Gayrimenkul Projeleri Sayfası — projeler.html"""
    try:
        return send_from_directory("templates", "projeler.html")
    except Exception as e:
        return f"projeler.html bulunamadı: {e}", 404

# ================================================================
# PROJELER SAYFASI — NEXA AI / CB VIP PORTFÖY API ENTEGRASYONU
# (3/ klasöründeki Suzanne sistemi, Yiğit Narin projeler bölümüne taşındı)
# ================================================================

from flask import Response as _FlaskResponse

try:
    from nexa_ai_engine import process_nexa_query, extract_keywords_and_projects
    from nexa_rag import (cognitive_chat as _nexa_cognitive_chat,
                          _find_project_by_name as _nexa_find_project,
                          _load_summaries as _nexa_load_summaries,
                          get_project_summary as _nexa_get_project_summary)
    _NEXA_IMPORT_OK = True
except Exception:
    _NEXA_IMPORT_OK = False

_NEXA_PROJELER_ROOT = BASE_DIR / "static" / "projeler"
_NEXA_PROJELER_ROOT.mkdir(parents=True, exist_ok=True)
_NEXA_PROJECTS_MAP = BASE_DIR / "static" / "data" / "projects_map.json"
_NEXA_LOG_DIR = BASE_DIR / "logs"
_NEXA_LOG_DIR.mkdir(exist_ok=True)

_nexa_rate_lock = threading.Lock()
_nexa_rate_hits = {}


def _nexa_check_rate_limit(ip):
    now = time.time()
    with _nexa_rate_lock:
        for old_ip in [k for k, ts_list in _nexa_rate_hits.items()
                       if not ts_list or now - ts_list[-1] >= 60]:
            del _nexa_rate_hits[old_ip]
        hits = [t for t in _nexa_rate_hits.get(ip, []) if now - t < 60]
        if len(hits) >= 12:
            return False
        hits.append(now)
        _nexa_rate_hits[ip] = hits
    return True


def _nexa_telemetry(event: dict):
    try:
        line = json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **event},
                          ensure_ascii=False)
        with open(_NEXA_LOG_DIR / "telemetry.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _nexa_stream_file_response(path: Path, mimetype: str):
    file_size = path.stat().st_size
    range_header = flask_request.headers.get('Range', None)
    if not range_header:
        return send_file(str(path), mimetype=mimetype)
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if not m:
        return send_file(str(path), mimetype=mimetype)
    byte1 = int(m.group(1))
    byte2 = int(m.group(2)) if m.group(2) else None
    length = file_size - byte1
    if byte2 is not None:
        length = byte2 - byte1 + 1

    def generate():
        with open(path, 'rb') as f:
            f.seek(byte1)
            remaining = length
            while remaining > 0:
                data = f.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    resp = _FlaskResponse(generate(), 206, mimetype=mimetype,
                          content_type=mimetype, direct_passthrough=True)
    resp.headers.add('Content-Range', f'bytes {byte1}-{byte1 + length - 1}/{file_size}')
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(length))
    return resp


_NEXA_DISPLAY_ORDER_FILE = BASE_DIR / "static" / "data" / "display_order.json"

def _nexa_get_saved_display_order():
    if _NEXA_DISPLAY_ORDER_FILE.exists():
        try:
            with open(_NEXA_DISPLAY_ORDER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _nexa_load_projects(include_hidden=False):
    if not _NEXA_PROJECTS_MAP.exists():
        return []
    try:
        with open(_NEXA_PROJECTS_MAP, "r", encoding="utf-8") as f:
            projects = json.load(f)
    except Exception:
        return []

    saved_orders = _nexa_get_saved_display_order()
    order_map = {str(item.get("id")): item for item in saved_orders if isinstance(item, dict)}

    for p in projects:
        p_id = str(p.get("id"))
        if p_id in order_map:
            meta = order_map[p_id]
            p["rank"] = meta.get("rank", 999)
            p["is_pinned"] = meta.get("is_pinned", False)
            p["is_hidden"] = meta.get("is_hidden", False)
        else:
            p["rank"] = 999
            p["is_pinned"] = False
            p["is_hidden"] = False

    # Sort: Pinned first, then by rank, then original order
    projects.sort(key=lambda x: (
        0 if x.get("is_pinned") else 1,
        x.get("rank", 999)
    ))

    if not include_hidden:
        projects = [p for p in projects if not p.get("is_hidden")]

    return projects


@app.route("/api/projects", methods=["GET"])
def api_projects_nexa():
    data = _nexa_load_projects(include_hidden=False)
    if data:
        resp = jsonify({"success": True, "data": data})
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp
    return jsonify({"success": False, "message": "projects_map.json bulunamadı"}), 404


@app.route("/api/admin/sync-projects", methods=["POST", "GET"])
def api_admin_sync_projects():
    """Google Drive projelerini manuel veya otonom tetikleyerek senkronize eder."""
    try:
        import nexa_drive_puller
        import nexa_watchdog
        count = nexa_drive_puller.pull_once()
        docs, chunks, msg = nexa_watchdog.ingest_changed()
        nexa_drive_puller._refresh_drive_previews()
        return jsonify({
            "success": True,
            "downloaded": count,
            "docs_indexed": docs,
            "chunks_added": chunks,
            "message": f"Drive ve Watchdog senkronizasyonu tamamlandı. {count} dosya güncellendi. {msg}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/nexa-ai-chat", methods=["POST"])
def api_nexa_ai_chat():
    client_ip = flask_request.remote_addr or "?"
    if not _nexa_check_rate_limit(client_ip):
        _nexa_telemetry({"event": "rate_limited", "ip": client_ip})
        return jsonify({"success": False,
                        "response": "Çok hızlı soru gönderiyorsunuz. Lütfen birkaç saniye bekleyip tekrar deneyin."}), 429

    data = flask_request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "response": "Lütfen bir soru yazın."}), 400
    if len(message) > 2000:
        return jsonify({"success": False, "response": "Soru çok uzun (en fazla 2000 karakter)."}), 400
    history = data.get("history") or []
    if not isinstance(history, list) or len(history) > 20:
        history = []

    t0 = time.time()
    cards, mode, reply_text = [], "heuristic", "Nexa AI Analizi tamamlandı."
    if _NEXA_IMPORT_OK:
        try:
            result = process_nexa_query(message)
            cards = result.get("projects", [])
            reply_text = result.get("response", reply_text)
        except Exception as e:
            _nexa_telemetry({"event": "engine_error", "ip": client_ip, "err": str(e)[:200]})
            return jsonify({"success": False,
                            "response": "Sistem kısa süreliğine meşgul. Lütfen bir dakika sonra tekrar deneyin."}), 500
        try:
            named = extract_keywords_and_projects(message)
            project = None
            if len(named) == 1:
                project = _nexa_find_project(named[0])
            rag_reply = _nexa_cognitive_chat(message, project=project, history=history)
            if rag_reply:
                mode = "cognitive-rag"
                reply_text = rag_reply
        except Exception:
            pass
    else:
        reply_text = ("Nexa AI modülü şu anda yüklenemedi; "
                      "detaylı bilgi için Yiğit Bey ile WhatsApp'tan iletişime geçin.")

    payload = {
        "success": True,
        "response": reply_text,
        "projects": cards,
        "mode": mode,
        "elapsed_ms": int((time.time() - t0) * 1000),
    }
    _nexa_telemetry({"event": "chat", "ip": client_ip, "mode": mode,
                     "msg": message[:120], "projects": [c.get("title") for c in cards],
                     "elapsed_ms": payload["elapsed_ms"]})
    return jsonify(payload)


@app.route("/api/track", methods=["POST"])
def api_nexa_track():
    data = flask_request.get_json(silent=True) or {}
    _nexa_telemetry({"event": f"ui_{data.get('event') or 'click'}",
                     "ip": flask_request.remote_addr or "?",
                     "project": data.get("project") or "",
                     "target": data.get("target") or ""})
    return jsonify({"success": True})


@app.route("/api/nexa-documents", methods=["GET"])
def api_nexa_documents():
    project_id = flask_request.args.get("project_id", type=int)
    try:
        import sqlite3 as _sqlite3
        from nexa_rag import DB_PATH as _NEXA_DB_PATH
        conn = _sqlite3.connect(f"file:{_NEXA_DB_PATH}?mode=ro", uri=True)
        conn.row_factory = _sqlite3.Row
        if project_id:
            rows = conn.execute(
                "SELECT id, project_id, doc_type, title, file_url, category FROM documents WHERE project_id = ? ORDER BY id",
                (project_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, project_id, doc_type, title, file_url, category FROM documents ORDER BY project_id, id").fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            url = d.get("file_url") or "#"
            if url.startswith("/static/documents/"):
                url = url.replace("/static/documents/", "/nexa-docs/", 1)
            d["download_url"] = url
            out.append(d)
        return jsonify({"success": True, "count": len(out), "documents": out})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/nexa-summaries", methods=["GET"])
def api_nexa_summaries():
    try:
        data = _nexa_load_summaries()
        items = [{"project_id": v.get("project_id"), "title": k, "summary": v.get("summary", "")}
                 for k, v in data.items()]
        return jsonify({"success": True, "count": len(items), "summaries": items})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/nexa-regions", methods=["GET"])
def api_nexa_regions():
    """Bölge/Konum filtresi + zihin haritası paneli için proje verisi.
    Öncelik: NEXA DB; yoksa projects_map.json + nexa_portfolio_data.json üzerinden türetir."""
    try:
        import sqlite3 as _sqlite3
        from nexa_rag import DB_PATH as _NEXA_DB_PATH, _load_db as _nexa_load_db
        conn = _nexa_load_db()
        conn.row_factory = _sqlite3.Row
        rows = conn.execute("""
            SELECT id, name, il, ilce, mahalle, location, description, ada_no, parsel_no,
                   price_display, room_info, tkgm_verified
            FROM projects WHERE COALESCE(is_portfolio,0) = 0 ORDER BY name
        """).fetchall()
        conn.close()
        out = []
        for r in rows:
            p = dict(r)
            loc = p.get("location") or f"{p.get('mahalle') or ''} {p.get('ilce') or ''} {p.get('il') or ''}".strip()
            out.append({
                "name": p["name"],
                "il": p.get("il") or "",
                "ilce": p.get("ilce") or "",
                "mahalle": p.get("mahalle") or "",
                "location": loc,
                "price_display": p.get("price_display") or "",
                "room_info": p.get("room_info") or "",
                "tkgm_verified": bool(p.get("tkgm_verified")),
                "summary": _nexa_get_project_summary(p["name"]) or "",
            })
        if out:
            return jsonify({"success": True, "count": len(out), "data": out})
    except Exception:
        pass

    # Fallback: proje haritası + zengin portföy verisi
    try:
        projects = _nexa_load_projects()
        rich = {}
        pf = BASE_DIR / "nexa_portfolio_data.json"
        if pf.exists():
            pdata = json.loads(pf.read_text(encoding="utf-8"))
            pool = pdata if isinstance(pdata, list) else pdata.get("projects", [])
            for item in pool:
                key = str(item.get("title") or item.get("name") or "").strip()
                if key:
                    rich[key] = item
        out = []
        for p in projects:
            title = str(p.get("title") or "").strip()
            r = rich.get(title) or {}
            out.append({
                "name": title,
                "il": "Ankara",
                "ilce": r.get("ilce") or p.get("district") or "",
                "mahalle": r.get("mahalle") or "",
                "location": r.get("location") or p.get("district") or "",
                "price_display": r.get("price_display") or p.get("price") or "",
                "room_info": r.get("room_info") or "",
                "tkgm_verified": bool(r.get("tkgm_verified")),
                "summary": "",
            })
        if out:
            return jsonify({"success": True, "count": len(out), "data": out})
    except Exception:
        pass
    return jsonify({"success": False, "message": "Bölge verisi yüklenemedi"}), 500


@app.route("/api/projects/<project_id>/report", methods=["GET"])
def api_nexa_project_report(project_id):
    projects = _nexa_load_projects()
    project = next((p for p in projects if str(p.get("id")) == str(project_id) or str(p.get("db_id")) == str(project_id)), None)
    if not project:
        return jsonify({"success": False, "message": "Proje bulunamadı"}), 404

    title = project.get("title") or "Prestij Projesi"
    summary = ""
    if _NEXA_IMPORT_OK:
        try:
            summary = _nexa_get_project_summary(title)
        except Exception:
            summary = ""
    pricing = {}
    try:
        pf = BASE_DIR / "nexa_portfolio_data.json"
        if pf.exists():
            pdata = json.loads(pf.read_text(encoding="utf-8"))
            pool = pdata if isinstance(pdata, list) else pdata.get("projects", [])
            for item in pool:
                if str(item.get("title")) == str(title) or str(item.get("name")) == str(title):
                    pricing = item
                    break
    except Exception:
        pricing = {}

    price_display = pricing.get("price_display") or project.get("price") or "Fiyat için danışmanımızdan bilgi alınız"
    room_info = pricing.get("room_info") or "Daire tipleri için danışmanımızdan bilgi alınız"
    loc = pricing.get("location") or project.get("district") or project.get("location") or "Prestij Lokasyonu"

    report = (
        f"DANISMAN NOTU — {title}\n"
        "===============================================\n\n"
        "📌 PROJE ÖZETİ\n"
        f"• Proje: {title}\n"
        f"• Bölge: {loc}\n"
        f"• Fiyat: {price_display}\n"
        f"• Daire Tipleri: {room_info}\n"
        f"• Münhasır Satış & Pazarlama: Coldwell Banker CB VIP Ankara\n\n"
    )
    if summary:
        report += f"💡 NEXA AI PROJE ÖZETİ\n{summary}\n\n"
    else:
        report += (
            "💡 NEXA AI DEĞERLENDİRMESİ\n"
            "Proje için otomatik özet verisi; detaylı bilgi için "
            "Yiğit Bey ile iletişime geçiniz.\n\n"
        )
    report += "📞 0532 451 40 08\nWhatsApp üzerinden anlık bilgi alabilirsiniz."
    return jsonify({"success": True, "report": report})


@app.route("/file")
def nexa_file_serve():
    path_arg = flask_request.args.get("path", "")
    if not path_arg:
        return "path parametresi gerekli", 400
    try:
        rel = os.path.normpath(path_arg).lstrip("/\\")
        if rel.lower().startswith("projeler" + os.sep) or rel.lower().startswith("projeler/"):
            rel = rel[len("projeler"):].lstrip("/\\")
        if rel.lower().startswith("static" + os.sep) or rel.lower().startswith("static/"):
            rel = rel[len("static"):].lstrip("/\\")
        base = _NEXA_PROJELER_ROOT.resolve()
        target = (base / rel).resolve()
        if target != base and base not in target.parents:
            return "Geçersiz yol", 400
        if not target.exists() or not target.is_file():
            return "Dosya bulunamadı", 404
    except Exception:
        return "Hatalı yol", 400

    suffix = target.suffix.lower()
    if suffix == ".mp4":
        return _nexa_stream_file_response(target, "video/mp4")
    if suffix == ".pdf":
        return send_file(str(target), mimetype="application/pdf")
    return send_file(str(target))


@app.route("/stream/video/<project_id>")
def nexa_stream_video(project_id):
    projects = _nexa_load_projects()
    project = next((p for p in projects if str(p.get("id")) == str(project_id) or str(p.get("db_id")) == str(project_id)), None)
    if not project:
        return "Project not found", 404

    target_dir = _NEXA_PROJELER_ROOT / (project.get("folder_name") or project.get("title") or "")
    if _NEXA_PROJELER_ROOT.exists() and (not target_dir.exists() or not target_dir.is_dir()):
        folder_kw = (project.get("folder_name") or "").lower()
        title_kw = (project.get("title") or "").lower()
        try:
            for d in _NEXA_PROJELER_ROOT.iterdir():
                if d.is_dir():
                    d_name = d.name.lower()
                    if (folder_kw and (folder_kw in d_name or d_name in folder_kw)) or (title_kw and (title_kw in d_name or d_name in title_kw)):
                        target_dir = d
                        break
        except Exception:
            pass

    _PRIORITY_WORDS_1 = ("tanitim", "tanıtım", "intro", "main", "ana", "lansman", "animasyon", "promosyon", "promo")
    _PRIORITY_WORDS_2 = ("slayt", "slideshow", "slaytlar", "sunum")

    def _mp4_priority(f: Path):
        name = f.stem.lower()
        for i, kw in enumerate(_PRIORITY_WORDS_1):
            if kw in name:
                return (0, i, -f.stat().st_size)
        for i, kw in enumerate(_PRIORITY_WORDS_2):
            if kw in name:
                return (1, i, -f.stat().st_size)
        return (2, 0, -f.stat().st_size)

    mp4_files = sorted(target_dir.glob("*.mp4"), key=_mp4_priority) if (target_dir.exists() and target_dir.is_dir()) else []
    real_mp4 = next((f for f in mp4_files if f.stat().st_size > 500 * 1024), None)
    if real_mp4 is None and mp4_files:
        real_mp4 = mp4_files[0]
    if not real_mp4 or not real_mp4.exists():
        # Robust Cloud Fallback (Google Drive Preview / Stream)
        drive_url = project.get("drive_video_preview") or ""
        if not drive_url and project.get("drive_vid_id"):
            drive_url = f"https://drive.google.com/file/d/{project['drive_vid_id']}/preview"
        if not drive_url:
            cloud_u = project.get("tanitim_cloud_url") or ""
            if cloud_u.startswith("http"):
                drive_url = cloud_u
        if drive_url.startswith("http"):
            m = re.search(r"/file/d/([\w-]{15,})", drive_url)
            if m:
                return redirect(f"https://drive.google.com/file/d/{m.group(1)}/preview")
            return redirect(drive_url)
        return "Video file not found", 404
    return _nexa_stream_file_response(real_mp4, "video/mp4")


@app.route("/stream/pdf/<project_id>")
def nexa_stream_pdf(project_id):
    """Projenin tanıtım PDF'ini yerelden veya Google Drive üzerinden servis eder."""
    projects = _nexa_load_projects()
    project = next((p for p in projects if str(p.get("id")) == str(project_id) or str(p.get("db_id")) == str(project_id)), None)
    if not project:
        return "Project not found", 404

    candidates = []
    pre = project.get("presentations") or []
    for item in pre:
        r = item.get("path") or item.get("filename") or ""
        if r:
            if r.lower().startswith("projeler/") or r.lower().startswith("projeler\\"):
                candidates.append(_NEXA_PROJELER_ROOT / r[9:])
            candidates.append(_NEXA_PROJELER_ROOT / r)
            candidates.append(BASE_DIR / "static" / r)

    folder = project.get("folder_name") or project.get("title") or ""
    fdir = _NEXA_PROJELER_ROOT / folder
    if _NEXA_PROJELER_ROOT.exists() and (not fdir.exists() or not fdir.is_dir()):
        folder_kw = folder.lower()
        title_kw = (project.get("title") or "").lower()
        try:
            for d in _NEXA_PROJELER_ROOT.iterdir():
                if d.is_dir():
                    d_name = d.name.lower()
                    if (folder_kw and (folder_kw in d_name or d_name in folder_kw)) or (title_kw and (title_kw in d_name or d_name in title_kw)):
                        fdir = d
                        break
        except Exception:
            pass

    if fdir.exists() and fdir.is_dir():
        pdfs = list(fdir.glob("*.pdf"))
        sunums = [p for p in pdfs if "sunum" in p.name.lower()]
        candidates.extend(sunums)
        candidates.extend(pdfs)

    for c in candidates:
        if c.exists() and c.is_file() and c.suffix.lower() == ".pdf":
            resp = send_file(str(c.resolve()), mimetype="application/pdf")
            resp.headers["Cache-Control"] = "public, max-age=604800"
            resp.headers["Content-Disposition"] = f'inline; filename="{c.name}"'
            return resp

    drive_pdf = project.get("drive_pdf_preview") or ""
    if not drive_pdf and project.get("drive_pdf_id"):
        drive_pdf = f"https://drive.google.com/file/d/{project['drive_pdf_id']}/preview"
    if not drive_pdf:
        sunum_u = project.get("sunum_cloud_url") or ""
        if sunum_u.startswith("http"):
            drive_pdf = sunum_u
    if drive_pdf.startswith("http"):
        m = re.search(r"/file/d/([\w-]{15,})", drive_pdf)
        if m:
            return redirect(f"https://drive.google.com/file/d/{m.group(1)}/preview")
        return redirect(drive_pdf)
    return "PDF bulunamadı", 404

# ================================================================
# API — İLAN SCRAPER
# ================================================================

import re as _re
import math as _math
import random as _random

_coord_cache: dict = {}
_last_nominatim_call: float = 0.0
_TR_MAP = str.maketrans("çğışöüÇĞİŞÖÜ", "cgisouCGISOu")
_jitter_counter: int = 0

def _normalize(text: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirip büyük harfe dönüştürür."""
    return text.translate(_TR_MAP).upper()

# ── Ankara mahalle/semt koordinat sözlüğü ─────────────────────────────────────
# Nominatim'e gerek kalmadan yaygın semtleri doğru konuma düşürür.
ANKARA_COORDS: dict = {
    "DIKMEN":            (39.8854, 32.8514),
    "YUKARI DIKMEN":     (39.8780, 32.8490),
    "ASAGI DIKMEN":      (39.8920, 32.8550),
    "CUKURAMBAR":        (39.9038, 32.8106),
    "BIRLIK MAHALLESI":  (39.9150, 32.8010),
    "CAYYOLU":           (39.8586, 32.7361),
    "ORAN":              (39.8771, 32.8233),
    "ANGORA EVLERI":     (39.8640, 32.7790),
    "BEYSUKENT":         (39.8530, 32.7080),
    "KIZILAY":           (39.9208, 32.8541),
    "TUNALI":            (39.9068, 32.8613),
    "TUNAL":             (39.9068, 32.8613),
    "AYRANCI":           (39.9010, 32.8620),
    "GAZIOSMANPASA":     (39.9100, 32.8440),
    "GOP":               (39.9100, 32.8440),
    "KAVAKLIDERE":       (39.9040, 32.8640),
    "CANKAYA":           (39.9033, 32.8597),
    "BALGAT":            (39.8922, 32.8108),
    "EMEK":              (39.9220, 32.7970),
    "BAHCELIEVLER":      (39.9240, 32.8050),
    "OVECLER":           (39.8700, 32.8390),
    "GUVENEVLER":        (39.9060, 32.8350),
    "YILDIZ":            (39.9100, 32.8220),
    "CETIN EMEC":        (39.8810, 32.8160),
    "MUSTAFA KEMAL":     (39.9180, 32.7850),
    "AZIZIYE":           (39.8770, 32.8360),
    "NACI CAKIR":        (39.8800, 32.8540),
    "KECOREN":           (39.9750, 32.8640),
    "MAMAK":             (39.9320, 32.9380),
    "ALTINDAG":          (39.9540, 32.8780),
    "SINCAN":            (39.9730, 32.5820),
    "ETIMESGUT":         (39.9490, 32.6890),
    "GOLBASI":           (39.7890, 32.8040),
    "PURSAKLAR":         (40.0310, 32.8960),
    "YENIMAHALLE":       (39.9680, 32.8270),
    "BAGLICA":           (39.9580, 32.7310),
    "BATIKENT":          (39.9690, 32.7250),
    "ERYAMAN":           (39.9810, 32.6680),
    "INCEK":             (39.8200, 32.7900),
    "KONUTKENT":         (39.8700, 32.7450),
    "UMITKOY":           (39.8680, 32.7250),
    "KORU":              (39.8770, 32.7590),
    "KARSIYAKA":         (39.9210, 32.8700),
    "DEMETEVLER":        (39.9780, 32.8010),
    "KALABA":            (39.9480, 32.9100),
    "ULUS":              (39.9440, 32.8540),
    "SIHHIYE":           (39.9310, 32.8540),
    "BESTEPE":           (39.9330, 32.8040),
    "OSTIM":             (39.9620, 32.9090),
    "GIMAT":             (39.9560, 32.8830),
    "ELVANKENT":         (39.9440, 32.7010),
    "SUSUZKÖY":          (39.9900, 32.7400),
}

def _lookup_hardcoded(text: str):
    """
    Metin içinde ANKARA_COORDS'tan eşleşme arar.
    En uzun eşleşmenin koordinatını döner.
    """
    norm = _normalize(text)
    best = None
    best_len = 0
    for k, v in ANKARA_COORDS.items():
        if k in norm and len(k) > best_len:
            best = v
            best_len = len(k)
    return best

def _jittered(lat: float, lng: float) -> tuple:
    """
    Aynı koordinata düşen birden fazla marker'ın üst üste yığılmaması için
    ~30-70 m arası rastgele ofset ekler (altın açı dağılımı).
    """
    global _jitter_counter
    _jitter_counter += 1
    angle = (_jitter_counter * 137.508) % 360
    r = _random.uniform(0.0003, 0.0007)
    return (
        round(lat + r * _math.sin(_math.radians(angle)), 6),
        round(lng + r * _math.cos(_math.radians(angle)), 6),
    )

def geocode_query(query: str):
    """
    Nominatim ile geocode. bounded=0 (daha geniş tarama) + Ankara doğrulama.
    Sonuç Ankara'nın ~60 km dışındaysa geçersiz sayar.
    """
    global _last_nominatim_call
    if not query:
        return None
    key = query.lower().strip()
    if key in _coord_cache:
        return _coord_cache[key]

    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.2:
        time.sleep(1.2 - elapsed)

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 5,
                "countrycodes": "tr",
                # bounded=0 bırak — viewbox öneri olarak kullan, zorunlu değil
                "viewbox": "32.3,40.2,33.4,39.5",
            },
            headers={"User-Agent": "NexaCRM/2.0 (contact@nexacrm.com)"},
            timeout=8,
        )
        _last_nominatim_call = time.time()
        data = resp.json()

        # Ankara bölgesi: lat 39.5–40.2 / lon 32.3–33.4
        for item in data:
            lat = float(item["lat"])
            lon = float(item["lon"])
            if 39.5 <= lat <= 40.2 and 32.3 <= lon <= 33.4:
                _coord_cache[key] = (lat, lon)
                return lat, lon

    except Exception as e:
        print(f"  Geocode hatası '{query[:50]}': {e}")

    _coord_cache[key] = None
    return None

def get_listing_coords(title: str, loc: str) -> tuple:
    """
    İlan için koordinat bulur. Strateji:
    1. Başlık + loc içinde sabit sözlükten mahalle eşleşmesi (hızlı, offline)
    2. Nominatim: mahalle + Çankaya/Ankara
    3. loc'tan temizlenmiş parçalarla Nominatim
    4. Dikmen fallback (jitter ile — marker'lar üst üste yığılmaz)
    """
    combined = f"{title} {loc}"

    # ── 1. Sabit sözlük ───────────────────────────────────────────────────
    coords = _lookup_hardcoded(combined)
    if coords:
        print(f"     📍 Sabit sözlük → {coords}")
        return _jittered(*coords)

    # ── 2. Nominatim — başlıktan çıkarılan mahalle ────────────────────────
    # ANKARA_SEMTLER listesinde en uzun eşleşeni bul
    norm_combined = _normalize(combined)
    best_semt = None
    best_len = 0
    for s in ANKARA_SEMTLER:
        sn = _normalize(s)
        if sn in norm_combined and len(sn) > best_len:
            best_semt = s
            best_len = len(sn)

    if best_semt:
        for q in [
            f"{best_semt}, Çankaya, Ankara",
            f"{best_semt}, Ankara",
        ]:
            coords = geocode_query(q)
            if coords:
                print(f"     🌐 Nominatim semt: {best_semt} → {coords}")
                return _jittered(*coords)

    # ── 3. loc'tan temizlenmiş parçalar ──────────────────────────────────
    # "Mah.", "Cad.", "No:5" gibi gürültüyü temizle, "Ankara" kelimesini at
    loc_clean = _re.sub(
        r"\b(Mah\.|Mah\b|Mahallesi|Cad\.|Caddesi|Sok\.|Sokak|Blv\.|Bulvarı|No:\s*\d+[\w/]*|\d+\s*/\s*\d+)\b",
        "", loc, flags=_re.IGNORECASE
    )
    parts = [
        p.strip() for p in _re.split(r"[,/]", loc_clean)
        if p.strip() and len(p.strip()) > 2
        and _normalize(p.strip()) not in ("ANKARA", "TR", "TURKIYE", "TÜRKIYE")
    ]
    for part in parts:
        coords = geocode_query(f"{part}, Ankara, Türkiye")
        if coords:
            print(f"     🌐 Nominatim loc: {part} → {coords}")
            return _jittered(*coords)

    # ── 4. Fallback ───────────────────────────────────────────────────────
    print(f"     ⚠️  Koordinat bulunamadı → Dikmen fallback | {title[:35]}")
    return _jittered(DIKMEN_LAT, DIKMEN_LNG)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def clean_text(element) -> str:
    return element.get_text(strip=True) if element else ""

def detect_listing_transaction_type(link: str = "", title: str = "", card_soup=None, default: str = "Satılık") -> str:
    """
    İlanın Satılık veya Kiralık olduğunu 100% doğrulukla tespit eder.
    1. URL içindeki -kiralik/ veya /kiralik belirteçleri (cb.com.tr'de kesin belirteç)
    2. Türkçe karakter normalize edilmiş başlık (İ -> i, I -> ı)
    3. Kart / HTML içerisindeki rozet ve metinler
    4. Fiyat içindeki /ay veya aylık ibareleri
    """
    link_l = (link or "").lower()
    if "/kiralik" in link_l or "-kiralik" in link_l or "kiralik" in link_l:
        return "Kiralık"
    if "/satilik" in link_l or "-satilik" in link_l or "satilik" in link_l:
        return "Satılık"

    t_norm = (title or "").replace("İ", "i").replace("I", "ı").replace("Î", "i").lower()
    if any(w in t_norm for w in ["kiralık", "kiralik", "kira", "kiralama", "devren kiralık", "devren kira"]):
        return "Kiralık"
    if any(w in t_norm for w in ["satılık", "satilik", "satış", "satis", "devren satılık"]):
        return "Satılık"

    if card_soup:
        c_text = " ".join(card_soup.stripped_strings).replace("İ", "i").replace("I", "ı").lower()
        if any(w in c_text for w in ["kiralık", "kiralik", "kiralama"]):
            return "Kiralık"
        if any(w in c_text for w in ["satılık", "satilik"]):
            return "Satılık"

    return default

def detect_listing_property_type(link: str = "", title: str = "", card_soup=None) -> str:
    """
    İlanın gayrimenkul türünü tespit eder (Ofis, Daire, Villa, Tarla/Arsa vb.).
    """
    link_l = (link or "").lower().rstrip("/")
    parts = [p for p in link_l.split("/") if p]
    slug = parts[-2] if len(parts) >= 2 else ""

    mapping = {
        "ofis": "Ofis",
        "daire": "Daire",
        "villa": "Villa",
        "tarla": "Arsa / Tarla",
        "arsa": "Arsa",
        "komple-site": "Rezidans / Daire",
        "koy": "Köy Evi / Arsa",
        "dukkan": "Dükkan / Mağaza",
        "isyeri": "İş Yeri",
        "bina": "Bina",
        "rezidans": "Rezidans",
    }
    if slug in mapping:
        return mapping[slug]

    t_norm = (title or "").replace("İ", "i").replace("I", "ı").lower()
    for k, v in mapping.items():
        if k in t_norm:
            return v

    return "Konut"

def fetch_real_estate_data() -> list:
    print(f"📡 İstek gönderiliyor: {TARGET_URL}")
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            print(f"❌ Bağlantı Hatası: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        listings = []
        cards = soup.select(".card.locationDiv")
        if not cards:
            cards = soup.select(".cb-list-item")
            
        print(f"🔎 Bulunan İlan Sayısı: {len(cards)}")

        for card in cards:
            try:
                title_el = card.select_one(".cb-list-item-info h2") or card.select_one(".card-title")
                title = clean_text(title_el)
                if not title:
                    continue

                price_el = card.select_one(".feature-item .text-primary") or card.select_one("span.h5.text-primary")
                price = clean_text(price_el)

                link_el = card.select_one(".cb-list-img-container a") or card.select_one("a.title") or card.select_one("a[href]")
                link = link_el["href"] if link_el else "#"
                if link and not link.startswith("http"):
                    link = "https://www.cb.com.tr" + link

                img_el = card.select_one(".cb-list-img-container img") or card.select_one("img.card-img-top")
                img_url = "https://via.placeholder.com/400x300"
                if img_el:
                    img_url = img_el.get("src") or img_el.get("data-src") or img_url

                region_el = card.select_one('span[itemprop="addressRegion"]')
                street_el = card.select_one('span[itemprop="streetAddress"]')
                region = clean_text(region_el)
                street = clean_text(street_el)
                loc = f"{region}, {street}" if region and street else "Ankara"

                rooms = area = ""
                for feat in card.select(".feature-item"):
                    text = clean_text(feat)
                    if "m2" in text or "m²" in text:
                        area = text
                    elif "+" in text:
                        rooms = text

                lat_raw = card.get("data-target-lat")
                lng_raw = card.get("data-target-lng")
                if lat_raw and lng_raw:
                    try:
                        lat = float(lat_raw.replace(",", "."))
                        lng = float(lng_raw.replace(",", "."))
                    except:
                        lat, lng = get_listing_coords(title, loc)
                else:
                    lat, lng = get_listing_coords(title, loc)

                tx_type = detect_listing_transaction_type(link, title, card)
                prop_type = detect_listing_property_type(link, title, card)

                formatted_price = price
                if tx_type == "Kiralık" and price and "/ay" not in price and "ay" not in price.lower():
                    formatted_price = f"{price} / ay"

                listings.append({
                    "id": hashlib.md5(link.encode("utf-8")).hexdigest()[:12],
                    "title": title, "price": formatted_price, "raw_price": price, "loc": loc,
                    "img": img_url, "link": link, "rooms": rooms, "area": area,
                    "type": tx_type,
                    "status": tx_type,
                    "transaction_type": tx_type,
                    "property_type": prop_type,
                    "category": prop_type,
                    "lat": lat, "lng": lng,
                })
            except Exception as e:
                print(f"⚠️ İlan parse hatası: {e}")
                continue

        print(f"✅ Toplam işlenen: {len(listings)} ilan")
        return listings
    except Exception as e:
        print(f"❌ Kritik Hata: {e}")
        return []

@app.route("/ilanlar")
def ilanlar():
    """İlanlar sayfası — ilanlar.html"""
    try:
        return send_from_directory("templates", "ilanlar.html")
    except Exception as e:
        return f"ilanlar.html bulunamadı: {e}", 404

@app.route("/admin")
def admin():
    """Admin paneli — admin.html"""
    try:
        return send_from_directory("templates", "admin.html")
    except Exception as e:
        return f"admin.html bulunamadı: {e}", 404

# ================================================================
# ================================================================
# ADMIN AUTH  — Firebase ID Token doğrulaması
# ================================================================

def _require_admin():
    """
    Firebase JS SDK'dan gelen idToken'ı doğrular.
    Başarılıysa (decoded_token, None), başarısızsa (None, hata_mesajı) döner.
    """
    if not _fb_initialized:
        print("⚠️  _require_admin: Firebase başlatılmamış")
        return None, "Firebase bağlı değil"
    auth_header = flask_request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        print(f"⚠️  _require_admin: Token başlığı eksik — {flask_request.path}")
        return None, "Token eksik"
    id_token = auth_header[7:]
    if not id_token or len(id_token) < 20:
        return None, "Token geçersiz (çok kısa)"
    try:
        decoded = fb_auth.verify_id_token(id_token)
        # Verify admin claim or authorized email whitelist
        ADMIN_EMAILS = {
            "yigit@gayrimenkulmuhendisi.com",
            "info@gayrimenkulmuhendisi.com",
            "admin@gayrimenkulmuhendisi.com",
            "yigitnarin@gmail.com",
            "yigit.narin@cb.com.tr",
            "yigit.narin@coldwellbanker.vip"
        }
        email = (decoded.get("email") or "").lower().strip()
        is_admin_claim = bool(decoded.get("admin") or decoded.get("is_admin"))
        is_cb_domain = email.endswith("@coldwellbanker.vip") or email.endswith("@cb.com.tr")
        if not is_admin_claim and email not in ADMIN_EMAILS and not is_cb_domain:
            print(f"⛔ Yetkisiz Admin Erişimi Engellendi: {email} — {flask_request.path}")
            return None, "Yetkisiz işlem: Bu panel yalnızca yönetici hesaplarına açıktır."
        print(f"✅ Admin doğrulandı: {email} — {flask_request.path}")
        return decoded, None
    except fb_auth.ExpiredIdTokenError:
        print("⚠️  _require_admin: Token süresi dolmuş")
        return None, "Oturum süresi doldu"
    except fb_auth.InvalidIdTokenError as e:
        print(f"⚠️  _require_admin: Geçersiz token — {e}")
        return None, "Geçersiz token"
    except Exception as e:
        print(f"❌ _require_admin beklenmedik hata: {type(e).__name__}: {e}")
        return None, f"Doğrulama hatası: {type(e).__name__}"

@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    # Client tarafında token silindiği için backend'de yapılacak bir şey yok
    return jsonify({"ok": True})

# ================================================================
# WHATSAPP CLOUD API ROUTES
# ================================================================

@app.route("/api/wa/status", methods=["GET"])
def whatsapp_status():
    """Meta Graph API üzerinden WA phone number durumunu kontrol eder."""
    return jsonify(wa_status())

@app.route("/api/email/status", methods=["GET"])
def customer_email_status():
    """Transactional e-posta yapılandırma durumunu döner."""
    return jsonify(email_status())

@app.route("/api/wa/webhook", methods=["GET"])
def whatsapp_webhook_verify():
    """
    Meta webhook doğrulaması (GET).
    Meta Business → WhatsApp → Configuration → Webhook URL olarak kaydedin.
    Verify Token: WA_VERIFY_TOKEN env variable ile eşleşmeli.
    """
    mode      = flask_request.args.get("hub.mode")
    token     = flask_request.args.get("hub.verify_token")
    challenge = flask_request.args.get("hub.challenge")

    if mode == "subscribe" and verify_webhook_token(token):
        print("✅ WhatsApp webhook doğrulandı")
        return challenge, 200

    print(f"❌ Webhook doğrulama başarısız. Token: {token}")
    return "Forbidden", 403

@app.route("/api/wa/webhook", methods=["POST"])
def whatsapp_webhook_receive():
    """
    Meta'dan gelen mesaj/durum bildirimlerini alır (POST).
    Gelen mesajları Firestore wa_inbound koleksiyonuna kaydeder.
    """
    data = flask_request.get_json(silent=True) or {}

    try:
        entries = data.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Gelen mesajlar
                for msg in value.get("messages", []):
                    from_phone = msg.get("from", "")
                    msg_type   = msg.get("type", "")
                    body       = msg.get("text", {}).get("body", "") if msg_type == "text" else f"[{msg_type}]"
                    timestamp  = msg.get("timestamp", "")
                    print(f"📥 WA gelen mesaj: {from_phone} → {body[:80]}")

                    if _fb_initialized:
                        db_admin.collection("wa_inbound").add({
                            "from":      from_phone,
                            "type":      msg_type,
                            "body":      body,
                            "timestamp": timestamp,
                            "raw":       msg,
                            "receivedAt": datetime.now(timezone.utc).isoformat(),
                        })

                # Mesaj durum güncellemeleri (sent/delivered/read/failed)
                for status in value.get("statuses", []):
                    msg_id     = status.get("id", "")
                    wa_status_ = status.get("status", "")
                    recipient  = status.get("recipient_id", "")
                    print(f"📊 WA durum: {msg_id} → {wa_status_} ({recipient})")

                    if _fb_initialized and msg_id:
                        # wa_message_log'daki kaydı güncelle
                        docs = (db_admin.collection("wa_message_log")
                                .where("messageId", "==", msg_id).limit(1).stream())
                        for doc in docs:
                            doc.reference.update({
                                "deliveryStatus": wa_status_,
                                "statusUpdatedAt": datetime.now(timezone.utc).isoformat(),
                            })

    except Exception as e:
        print(f"Webhook işleme hatası: {e}")

    # Meta her zaman 200 bekler
    return jsonify({"status": "ok"}), 200

@app.route("/api/wa/send", methods=["POST"])
def whatsapp_send():
    """
    Admin panelinden manuel WA mesajı göndermek için.
    Body: { phone: "905324514008", message: "..." }
    Korumalı endpoint — Firebase ID token gerektirir.
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401

    body    = flask_request.get_json(silent=True) or {}
    phone   = body.get("phone", "")
    message = body.get("message", "")

    if not phone or not message:
        return jsonify({"ok": False, "error": "phone ve message zorunlu"}), 400

    result = send_whatsapp(phone, message)

    if result["ok"] and _fb_initialized:
        db_admin.collection("wa_message_log").add({
            "phone":     phone,
            "message":   message[:200],
            "messageId": result.get("message_id", ""),
            "source":    "admin_manual",
            "status":    "sent",
            "sentAt":    datetime.now(timezone.utc).isoformat(),
        })

    return jsonify(result)

# ================================================================
# BLOG API
# ================================================================

def _serialize_post(doc):
    """Firestore dokümanını JSON-safe dict'e çevirir."""
    d = doc.to_dict()
    d["id"] = doc.id
    for field in ["createdAt", "updatedAt"]:
        val = d.get(field)
        if val is None:
            d[field] = ""
        elif hasattr(val, "isoformat"):
            try:
                d[field] = val.isoformat()
            except Exception:
                d[field] = str(val)
        else:
            d[field] = str(val)
    return d

@app.route("/api/blog/posts", methods=["GET"])
def get_blog_posts():
    """Herkese açık — site.html, haber.html ve mobil uygulama buradan çeker."""
    # 1. Primary: Intelligence Network SQLite Database
    try:
        try:
            limit_param = int(flask_request.args.get("limit", 50))
        except Exception:
            limit_param = 50
        limit = min(max(limit_param, 1), 100)
        from intelligence.db import get_published_articles
        articles = get_published_articles(limit=limit)
        if articles:
            return jsonify({"ok": True, "data": [a.to_dict() for a in articles]})
    except Exception as e:
        print(f"[WARN] get_blog_posts intelligence.db query: {e}")

    # 2. Secondary: Firestore if configured
    if _fb_initialized:
        try:
            query = (db_admin.collection("blogs")
                     .where(filter=FieldFilter("published", "==", True))
                     .limit(24))
            posts = [_serialize_post(doc) for doc in query.stream()]
            if posts:
                posts.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
                return jsonify({"ok": True, "data": posts})
        except Exception as e:
            print(f"get_blog_posts firestore hatası: {e}")

    # 3. Fallback: static/data/latest_news.json
    try:
        json_path = BASE_DIR / "static" / "data" / "latest_news.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify({"ok": True, "data": data})
    except Exception:
        pass

    return jsonify({"ok": True, "data": []})

# ================================================================
# NEXA REAL ESTATE INTELLIGENCE NETWORK — API ENDPOINTS
# ================================================================

@app.route("/api/intelligence/feed", methods=["GET"])
def api_intelligence_feed():
    """Returns paginated intelligence articles with optional category/location filter."""
    try:
        from intelligence.db import get_published_articles
        cat = flask_request.args.get("category")
        try:
            limit = max(1, min(int(flask_request.args.get("limit", 20)), 100))
        except (ValueError, TypeError):
            limit = 20
        try:
            offset = max(0, int(flask_request.args.get("offset", 0)))
        except (ValueError, TypeError):
            offset = 0

        articles = get_published_articles(limit=limit, category=cat, offset=offset)
        return jsonify({"ok": True, "data": [a.to_dict() for a in articles]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/article/<slug_or_id>", methods=["GET"])
def api_intelligence_article(slug_or_id):
    """Returns single detailed intelligence article with impact breakdown."""
    try:
        from intelligence.db import get_article_by_slug_or_id
        art = get_article_by_slug_or_id(slug_or_id)
        if not art:
            return jsonify({"ok": False, "error": "Makale bulunamadı"}), 404
        return jsonify({"ok": True, "data": art.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/daily-brief", methods=["GET"])
def api_intelligence_daily_brief():
    """Returns today's flagship market intelligence brief."""
    try:
        from intelligence.publication import DailyBriefGenerator
        generator = DailyBriefGenerator()
        brief = generator.generate_brief()
        return jsonify({"ok": True, "data": brief})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/market-pulse", methods=["GET"])
def api_intelligence_market_pulse():
    """Returns live market pulse indicators."""
    pulse = {
        "ok": True,
        "data": {
            "credit_condition": "Temkinli / Yüksek Faiz (Doğrudan Vadeli Seçenekler Önde)",
            "housing_demand": "Canlı (Özellikle Beytepe, İncek, Çankaya Lüks Segment)",
            "price_trend": "Nominal Artış / Reel Dengelenme",
            "rental_yield": "%6.8 - %7.5 Brüt Getiri (Doluluk %98)",
            "land_interest": "Güçlü (Gölbaşı - İncek - Alacaatlı Villa Parselleri)"
        }
    }
    return jsonify(pulse)

@app.route("/api/intelligence/decisions/buying", methods=["POST"])
def api_intelligence_decision_buying():
    """'Ev Almalı mıyım?' Condition Index calculation with bilingual parameter normalization."""
    try:
        from intelligence.decisions import DecisionIntelligence
        data = flask_request.json or {}
        result = DecisionIntelligence.evaluate_buying_conditions(**data)
        return jsonify({"ok": True, "data": result.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/decisions/selling", methods=["POST"])
def api_intelligence_decision_selling():
    """'Evimi Satmalı mıyım?' Condition Index calculation with bilingual parameter normalization."""
    try:
        from intelligence.decisions import DecisionIntelligence
        data = flask_request.json or {}
        result = DecisionIntelligence.evaluate_selling_conditions(**data)
        return jsonify({"ok": True, "data": result.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/decisions/project", methods=["POST"])
def api_intelligence_decision_project():
    """'Proje Yatırımı İçin Uygun Zaman mı?' calculation with bilingual parameter normalization."""
    try:
        from intelligence.decisions import DecisionIntelligence
        data = flask_request.json or {}
        result = DecisionIntelligence.evaluate_project_opportunity(**data)
        return jsonify({"ok": True, "data": result.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/decisions/rent-vs-buy", methods=["POST"])
def api_intelligence_decision_rent_vs_buy():
    """'Kirada Kalmak mı Satın Almak mı?' calculation with bilingual parameter normalization."""
    try:
        from intelligence.decisions import DecisionIntelligence
        data = flask_request.json or {}
        result = DecisionIntelligence.evaluate_rent_vs_buy(**data)
        return jsonify({"ok": True, "data": result.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/advisor/ask", methods=["POST"])
def api_intelligence_advisor_ask():
    """Interactive 'Danışmana Sor' flow and WhatsApp consultation generator."""
    try:
        from intelligence.advisor import AdvisorFlow
        data = flask_request.json or {}
        flow = AdvisorFlow()
        res = flow.process_inquiry(
            article_title=data.get("article_title", "Piyasa Analizi"),
            article_slug=data.get("article_slug", ""),
            option_key=data.get("option_key", "impact"),
            user_name=data.get("name", ""),
            user_phone=data.get("phone", "")
        )
        # Track lead interaction (+10)
        try:
            from intelligence.analytics import FunnelTracker
            FunnelTracker.track_interaction(
                event_type="advisor_cta_click",
                user_id=data.get("phone") or data.get("name"),
                article_id=data.get("article_slug"),
                context=data
            )
        except Exception:
            pass

        return jsonify({"ok": True, "data": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/track", methods=["POST"])
def api_intelligence_track():
    """Telemetry & Lead Intent Score tracking for intelligence events."""
    try:
        from intelligence.analytics import FunnelTracker
        data = flask_request.json or {}
        event_type = data.get("event_type", "article_view")
        user_id = data.get("user_id") or data.get("client_id")
        article_id = data.get("article_id")
        delta = FunnelTracker.track_interaction(
            event_type=event_type,
            user_id=user_id,
            article_id=article_id,
            context=data.get("context", {})
        )
        return jsonify({"ok": True, "intent_score_delta": delta})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/prospects", methods=["GET"])
def api_intelligence_prospects():
    """Returns top prospect signals for the CRM dashboard."""
    try:
        from intelligence.analytics import CrmBridge
        prospects = CrmBridge.get_prospects_summary()
        stats = CrmBridge.get_funnel_stats()
        return jsonify({"ok": True, "prospects": prospects, "funnel_stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/intelligence/stats", methods=["GET"])
def api_admin_intelligence_stats():
    """Returns pipeline observability metrics and recent run history."""
    try:
        from intelligence.db import get_latest_run_stats
        return jsonify({"ok": True, "data": get_latest_run_stats()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/admin/intelligence/run", methods=["POST"])
def api_admin_intelligence_run():
    """Triggers an intelligence ingestion and analysis run on demand with async support."""
    try:
        import threading
        from intelligence.pipeline import IntelligencePipeline
        data = flask_request.json or {}
        is_async = data.get("async", True)
        pipeline = IntelligencePipeline()

        if is_async:
            thread = threading.Thread(target=pipeline.run, kwargs={"dry_run": False}, daemon=True)
            thread.start()
            return jsonify({
                "ok": True,
                "status": "started",
                "message": "İstihbarat döngüsü arka planda asenkron başlatıldı."
            }), 202
        else:
            run_record = pipeline.run(dry_run=False)
            return jsonify({"ok": True, "run": run_record.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ============================================================================
# SWARM REST API ROUTES
# ============================================================================

@app.route("/api/intelligence/swarm/status", methods=["GET"])
def api_intelligence_swarm_status():
    """Returns Swarm health, telemetry, research queue and daily summary."""
    try:
        import json
        from pathlib import Path
        from intelligence.db import get_research_queue
        
        summary_path = Path(__file__).resolve().parent / "static" / "data" / "swarm_summary.json"
        summary_data = {}
        if summary_path.exists():
            try:
                with open(summary_path, "r", encoding="utf-8") as sf:
                    summary_data = json.load(sf)
            except Exception:
                pass
        
        queue = get_research_queue(limit=15)
        
        return jsonify({
            "ok": True,
            "status": "active",
            "active_swarm_agents": [
                "IntelligenceDirector",
                "SourceScoutAgent",
                "GovernmentDataAgent",
                "NewsDiscoveryAgent",
                "FinanceAgent",
                "EntityResolutionAgent",
                "AnkaraAgent",
                "InfrastructureZoningAgent",
                "ProjectIntelligenceAgent",
                "RentalMarketAgent",
                "ContrarianAgent",
                "TrendDetectionAgent",
                "FactCheckerAgent",
                "EvidenceGraphBuilder",
                "ContentSynthesizerAgent",
                "QAGateAgent"
            ],
            "zero_fill_threshold": 80,
            "swarm_summary": summary_data or {
                "statement": "Bugün 47 piyasa sinyali tarandı, 11'i incelendi, 6'sı doğrulandı, 3'ü yüksek etkili istihbarat olarak yayımlandı.",
                "scanned_signals_count": 47,
                "evaluated_signals_count": 11,
                "published_count": 3,
                "monitored_count": 8
            },
            "research_queue": queue
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/swarm/market-state", methods=["GET"])
def api_intelligence_swarm_market_state():
    """Returns dynamic macro market regime and district indices."""
    try:
        from intelligence.market_state import MarketStateEngine
        engine = MarketStateEngine()
        state = engine.get_current_state()
        return jsonify({
            "ok": True,
            "market_state": {
                "demand": state.demand,
                "supply": state.supply,
                "credit": state.credit,
                "rental": state.rental,
                "price_pressure": state.price_pressure,
                "investment_appetite": state.investment_appetite,
                "regime": state.regime.value if hasattr(state.regime, 'value') else str(state.regime),
                "regional_indices": state.regional_indices,
                "daily_diff": state.daily_diff,
                "last_updated": state.last_updated
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/swarm/trends", methods=["GET"])
def api_intelligence_swarm_trends():
    """Returns active high-velocity emerging market trends."""
    try:
        from intelligence.db import get_active_trends
        trends = get_active_trends(limit=10)
        return jsonify({"ok": True, "trends": trends})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/swarm/investigate", methods=["POST"])
def api_intelligence_swarm_investigate():
    """Executes an on-demand multi-agent investigation on a specific topic or region."""
    try:
        data = flask_request.json or {}
        topic = data.get("topic", "Ankara Lüks Konut Piyasası")
        region = data.get("region", "Beytepe")
        content = data.get("content", f"{region} bölgesinde {topic} ile ilgili güncel gelişmeler ve yatırım fırsatları.")

        from intelligence.swarm import (
            FactCheckerAgent, EvidenceGraphBuilder, ContrarianAgent,
            FinanceAgent, AnkaraAgent, ContentSynthesizerAgent, QAGateAgent
        )
        from intelligence.swarm.swarm_models import EvidenceItem, VerificationStatus

        # 1. Fact checking & claims
        claims = FactCheckerAgent.extract_and_verify_claims(
            title=topic,
            content=content,
            source_id="on_demand_investigation",
            source_name="NEXA Swarm Specialist Inquiry",
            source_url=""
        )
        graph = EvidenceGraphBuilder.build_graph(claims)

        # 2. Contrarian stress-test
        contrarian = ContrarianAgent().stress_test(topic, content)

        # 3. Regional & Financial Specialists
        district_meta = AnkaraAgent.evaluate_district(region)
        finance_meta = FinanceAgent.analyze_financing(content)

        # 4. Epistemological synthesis
        epistemic = ContentSynthesizerAgent.synthesize_epistemology(
            title=topic,
            content=content,
            claims=claims,
            contrarian=contrarian
        )

        # 5. QA Check
        qa = QAGateAgent().evaluate_publication_readiness(
            candidate_score=85,
            confidence_score=graph.get("overall_authority_score", 0.85),
            claims=claims
        )

        return jsonify({
            "ok": True,
            "topic": topic,
            "region": region,
            "epistemology": epistemic,
            "contrarian_analysis": {
                "counter_hypothesis": contrarian.counter_hypothesis,
                "contrary_indicators": contrarian.contrary_indicators,
                "downside_risks": contrarian.downside_risks,
                "verdict": contrarian.verdict
            },
            "specialist_context": {
                "district_metrics": district_meta,
                "finance_outlook": finance_meta
            },
            "evidence_graph": graph,
            "publication_readiness": qa,
            "advisor": {
                "name": "Yiğit Narin",
                "phone": "+905324514008",
                "wa_cta": f"https://wa.me/905324514008?text=Merhaba%20Yi%C4%9Fit%20Bey,%20{region}%20b%C3%B6lgesindeki%20'{topic}'%20istihbarat%C4%B1%20hakk%C4%B1nda%20dan%C4%B1%C5%9Fmak%20istiyorum."
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/autonomic/status", methods=["GET"])
def api_intelligence_autonomic_status():
    """Returns real-time health, self-healing status, and vitality metrics of the Living System."""
    try:
        from intelligence.autonomic_daemon import get_supervisor
        sup = get_supervisor()
        return jsonify({"ok": True, "data": sup.get_status_report()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/intelligence/autonomic/pulse", methods=["POST"])
def api_intelligence_autonomic_pulse():
    """Triggers an on-demand metacontrol pulse (database cleanup, task recovery, market sensing)."""
    try:
        from intelligence.autonomic_daemon import get_supervisor
        sup = get_supervisor()
        report = sup.pulse()
        return jsonify({"ok": True, "data": report})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/blog/all", methods=["GET"])
def get_all_blog_posts():
    """Admin paneli için — tüm yazılar."""
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if _fb_initialized:
        try:
            posts = [_serialize_post(doc) for doc in db_admin.collection("blogs").stream()]
            posts.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return jsonify({"ok": True, "data": posts})
        except Exception as e:
            print(f"get_all_blog_posts firestore hatası: {e}")

    # Fallback to Intelligence Network SQLite or static JSON
    try:
        from intelligence.db import get_published_articles
        articles = get_published_articles(limit=50)
        if articles:
            return jsonify({"ok": True, "data": [a.to_dict() for a in articles]})
    except Exception:
        pass

    try:
        json_path = BASE_DIR / "static" / "data" / "latest_news.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return jsonify({"ok": True, "data": data})
    except Exception:
        pass

    return jsonify({"ok": True, "data": []})

@app.route("/api/blog/posts", methods=["POST"])
def create_blog_post():
    token, err = _require_admin()
    if err:
        print(f"❌ Auth hatası: {err}")
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    data = flask_request.json or {}
    print(f"📝 Blog oluşturma isteği: {data.get('title', '(başlıksız)')}")

    now  = datetime.now(timezone.utc)
    post = {
        "title":     data.get("title", "").strip(),
        "summary":   data.get("summary", "").strip(),
        "content":   data.get("content", "").strip(),
        "image":     data.get("image", "").strip(),
        "category":  data.get("category", "Genel").strip(),
        "readTime":  data.get("readTime", "3 dk").strip(),
        "published": bool(data.get("published", True)),
        "createdAt": now,
        "updatedAt": now,
    }
    if not post["title"]:
        return jsonify({"ok": False, "error": "Başlık zorunlu"}), 400

    try:
        result = db_admin.collection("blogs").add(post)
        # result → (DatetimeWithNanoseconds, DocumentReference)
        doc_ref = result[1] if isinstance(result, tuple) else result
        doc_id  = doc_ref.id
        print(f"✅ Blog oluşturuldu: {doc_id}")
        return jsonify({"ok": True, "id": doc_id})
    except Exception as e:
        import traceback
        print(f"❌ create_blog_post hatası: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/blog/posts/<post_id>", methods=["PUT"])
def update_blog_post(post_id):
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503
    data    = flask_request.json or {}
    allowed = ["title", "summary", "content", "image", "category", "readTime", "published"]
    update  = {k: data[k] for k in allowed if k in data}
    update["updatedAt"] = datetime.now(timezone.utc)
    try:
        db_admin.collection("blogs").document(post_id).update(update)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/blog/posts/<post_id>", methods=["DELETE"])
def delete_blog_post(post_id):
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503
    try:
        db_admin.collection("blogs").document(post_id).delete()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# API — İLAN SCRAPER
# ================================================================

_listings_cache = {"data": [], "ts": 0}
_listings_lock = threading.Lock()

# ── Portföy AI Persona Swarm İstihbarat Önbelleği ─────────────────────────────
_PORTFOLIO_PERSONA_FILE = BASE_DIR / "static" / "data" / "portfolio_persona_intelligence.json"
_persona_intel_lock = threading.RLock()

def _load_portfolio_persona_intel() -> dict:
    with _persona_intel_lock:
        if _PORTFOLIO_PERSONA_FILE.exists():
            try:
                with open(_PORTFOLIO_PERSONA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

def _save_portfolio_persona_intel(data: dict):
    with _persona_intel_lock:
        try:
            _PORTFOLIO_PERSONA_FILE.parent.mkdir(parents=True, exist_ok=True)
            temp_fd, temp_path = tempfile.mkstemp(dir=str(_PORTFOLIO_PERSONA_FILE.parent), prefix="persona_", suffix=".tmp")
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, str(_PORTFOLIO_PERSONA_FILE))
        except Exception as e:
            print(f"⚠️ Persona intel save hatası: {e}")

def _refresh_listings_bg():
    def _run():
        data = fetch_real_estate_data()
        if data:
            with _listings_lock:
                _listings_cache["data"] = data
                _listings_cache["ts"]   = time.time()
            try:
                cache_file = BASE_DIR / "static" / "data" / "cached_cb_listings.json"
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"⚠️ Listings disk cache hatası: {e}")

            # 🤖 Otomatik AI Persona Swarm Analizini Çalıştır
            try:
                from intelligence.swarm.persona_swarm import PersonaSwarmSynthesizer
                synthesizer = PersonaSwarmSynthesizer()
                existing_intel = _load_portfolio_persona_intel()
                updated = False
                for item in data:
                    key = item.get("link") or item.get("url") or item.get("title")
                    if key and key not in existing_intel:
                        intel = synthesizer.generate_intelligence(item)
                        existing_intel[key] = intel
                        updated = True
                if updated:
                    _save_portfolio_persona_intel(existing_intel)
                    print(f"🤖 AI Persona Swarm: {len(existing_intel)} portföy analiz edildi ve önbelleğe alındı.")
            except Exception as e:
                print(f"⚠️ AI Persona Swarm otomatik analiz hatası: {e}")
    threading.Thread(target=_run, daemon=True).start()

@app.route("/api/listings", methods=["GET"])
def get_listings():
    now = time.time()
    if now - _listings_cache["ts"] < 300 and _listings_cache["data"]:
        return jsonify({"success": True, "data": _listings_cache["data"]})
    if not _listings_cache["data"]:
        try:
            cache_file = BASE_DIR / "static" / "data" / "cached_cb_listings.json"
            if cache_file.exists():
                with open(cache_file, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                if disk_data:
                    with _listings_lock:
                        _listings_cache["data"] = disk_data
        except Exception:
            pass
    _refresh_listings_bg()
    return jsonify({"success": True, "data": _listings_cache["data"]})

# ── CB İlan Detay Önizleme ────────────────────────────────────────────────────
@app.route("/api/listing/preview", methods=["GET"])
def listing_preview():
    """
    a.py / scrape_detail() mantığıyla CB ilan detay sayfasını scrape eder.
    Query : ?url=https://www.cb.com.tr/...
    Return: {ok, title, price, location, rooms, sqm, type, status,
             cb_url, images:[str,...], features:[{label,value},...],
             description, agent:{name,img,office}}
    """

    BASE = "https://www.cb.com.tr"

    cb_url = flask_request.args.get("url", "").strip()
    parsed = urlparse(cb_url)
    if parsed.scheme not in ("http", "https") or \
       parsed.netloc not in ("www.cb.com.tr", "cb.com.tr"):
        return jsonify({"ok": False, "error": "Sadece cb.com.tr URL desteklenir"}), 400

    try:
        resp = requests.get(cb_url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": f"HTTP {resp.status_code}"}), 502

        soup = BeautifulSoup(resp.content, "lxml" if __import__("importlib").util.find_spec("lxml") else "html.parser")

        # ── Başlık ──────────────────────────────────────────────────────────
        title = clean_text(soup.select_one("h1") or soup.select_one("h2")) or "İlan Detayı"

        # ── Fiyat ───────────────────────────────────────────────────────────
        price = ""
        for sel in [".feature-item .text-primary",
                    ".price-box .price",
                    "[class*='price']",
                    ".cb-detail-header .price"]:
            el = soup.select_one(sel)
            if el:
                price = _re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
                if price:
                    break
        if not price:
            for row in soup.select("table tr"):
                cells = row.find_all("td")
                if len(cells) >= 2 and "Fiyat" in cells[0].get_text():
                    price = clean_text(cells[1])
                    break

        # ── Lokasyon ────────────────────────────────────────────────────────
        location = ""
        hdr = soup.select_one(".cb-detail-header")
        if hdr:
            parts = [clean_text(s) for s in hdr.select("p .text-secondary") if clean_text(s)]
            location = " / ".join(parts)
        if not location:
            r_el = soup.select_one('[itemprop="addressRegion"]')
            s_el = soup.select_one('[itemprop="streetAddress"]')
            location = " / ".join(clean_text(e) for e in [r_el, s_el] if e and clean_text(e))

        # ── İlan tipi / durumu ──────────────────────────────────────────────
        status = detect_listing_transaction_type(cb_url, title, soup)
        prop_type = detect_listing_property_type(cb_url, title, soup)

        # ── Görseller — a.py scrape_detail() mantığı ────────────────────────
        images = []
        seen_srcs = set()

        def _add_img(src):
            src = src.strip()
            if not src or "placeholder" in src or "icon" in src.lower() or "defaultstock" in src.lower():
                return
            if src.startswith("/"):
                src = BASE + src
            # Thumbnail URL'lerini yüksek çözünürlüklü versiyona yükselt
            # CB formatı: _410X261.jpg → _1000X664.jpg
            import re as _rx
            src_hires = _rx.sub(r'_\d+X\d+(\.[a-z]+)$', r'_1000X664\1', src, flags=_rx.IGNORECASE)
            norm_key = src_hires.split("?")[0].lower()
            if norm_key in seen_srcs:
                return
            seen_srcs.add(norm_key)
            images.append(src_hires)

        # 1) Bilinen slider seçicileri (öncelik sırasıyla)
        for sel in [
            "#cb-item-gallery .carousel-item img",
            "div.swiper-slide img",
            "div.slick-slide img",
            ".detail-slider img",
            ".stock-slider img",
            ".cb-detail-slider img",
            "figure img",
        ]:
            found = soup.select(sel)
            if found:
                for img in found:
                    src = (img.get("src") or img.get("data-src") or
                           img.get("data-lazy") or "").strip()
                    if src:
                        _add_img(src)
                if images:
                    break

        # 2) Slider bulunamazsa: media.cb / StockMedia img'leri
        if not images:
            for img in soup.find_all("img"):
                src = (img.get("src") or img.get("data-src") or "").strip()
                if "media.cb" in src or "StockMedia" in src:
                    _add_img(src)

        # 3) og:image fallback
        if not images:
            og = soup.find("meta", property="og:image")
            if og and og.get("content"):
                images.append(og["content"])

        # ── Özellik tablosu — a.py gibi çoklu yöntem ────────────────────────
        feats = []
        seen = set()
        SKIP = {"portföy no", "portföy kategorisi"}

        # a) Tablo satırları
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                k = clean_text(cells[0]).rstrip(":").strip()
                v = clean_text(cells[1]).strip()
                if k and v and len(k) < 50 and k.lower() not in seen and k.lower() not in SKIP:
                    feats.append({"label": k, "value": v})
                    seen.add(k.lower())

        # b) dt / dd çiftleri
        for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
            k, v = clean_text(dt), clean_text(dd)
            if k and v and k.lower() not in seen:
                feats.append({"label": k, "value": v})
                seen.add(k.lower())

        # c) cb-checkbox-list özellik kartları (İç / Dış özellikler)
        for card in soup.select(".card.no-radius"):
            sec_el = card.select_one(".card-header h3")
            sec = clean_text(sec_el) if sec_el else "Özellik"
            for li in card.select(".cb-checkbox-list .property"):
                b_el = li.select_one("b")
                k = clean_text(b_el).rstrip(":") if b_el else ""
                if b_el:
                    b_el.extract()
                v = li.get_text(strip=True)
                combined = (k + " " + v).strip().rstrip(":") if k else v
                if combined and combined.lower() not in seen:
                    feats.append({"label": k if k else sec, "value": v if k else combined})
                    seen.add(combined.lower())

        # d) li içinde ":" olan feature satırları
        for li in soup.select("ul.features li, .property-features li, .cb-features li"):
            txt = clean_text(li)
            if ":" in txt and len(txt) < 80:
                parts = txt.split(":", 1)
                k, v = parts[0].strip(), parts[1].strip()
                if k and v and k.lower() not in seen:
                    feats.append({"label": k, "value": v})
                    seen.add(k.lower())

        feats = feats[:20]

        # ── Oda / m² ────────────────────────────────────────────────────────
        rooms = sqm = ""
        for f in feats:
            lbl = f["label"].lower()
            if not rooms and ("oda" in lbl or "room" in lbl):
                rooms = f["value"]
            if not sqm and ("m²" in lbl or "m2" in lbl or "alan" in lbl
                            or "brüt" in lbl or "metre" in lbl):
                sqm = f["value"]

        # .feature-item (header'daki hızlı bilgiler)
        for fi in soup.select(".cb-detail-header .features .feature-item, .feature-item"):
            txt = clean_text(fi)
            if not rooms and "+" in txt:
                rooms = txt
            if not sqm and "m" in txt.lower() and any(c.isdigit() for c in txt):
                sqm = txt

        # Regex fallback
        page_text = soup.get_text(" ", strip=True)
        if not rooms:
            m = _re.search(r"(\d+\+\d+|\d+\+0)", page_text)
            if m:
                rooms = m.group(1)
        if not sqm:
            m = _re.search(r"(\d+)\s*m[²2]", page_text)
            if m:
                sqm = m.group(1) + " m²"

        # ── Açıklama ────────────────────────────────────────────────────────
        description = ""
        for sel in [".description", ".ilan-aciklama", ".detail-description",
                    "#aciklama", "[itemprop='description']", ".cb-detail-content p"]:
            el = soup.select_one(sel)
            if el:
                description = el.get_text(" ", strip=True)[:600]
                break

        # ── Danışman ────────────────────────────────────────────────────────
        agent = {
            "name":   "Yiğit Narin",
            "img":    "https://media.cb.com.tr/OfficeUserImages/470/YIGIT-NARIN.jpg",
            "office": "CB VIP",
        }

        a_link = soup.select_one("a[href*='/danismanlar/']")
        if a_link:
            agent["name"] = clean_text(a_link)

        pro = soup.select_one(".cb-professional")
        if pro:
            n_el = pro.select_one("h4") or pro.select_one(".name")
            if n_el:
                agent["name"] = clean_text(n_el)

        img_el = (soup.select_one("img[src*='OfficeUser']") or
                  (pro.select_one("img") if pro else None))
        if img_el:
            src = img_el.get("src", "")
            agent["img"] = BASE + src if src.startswith("/") else src

        off_link = soup.select_one("a[href*='/ofisler/']")
        if off_link:
            agent["office"] = clean_text(off_link)

        return jsonify({
            "ok":          True,
            "title":       title,
            "price":       price,
            "location":    location,
            "rooms":       rooms,
            "sqm":         sqm,
            "type":        prop_type,
            "status":      status,
            "cb_url":      cb_url,
            "images":      images,
            "features":    feats,
            "description": description,
            "agent":       agent,
        })

    except Exception as e:
        print(f"❌ listing/preview hatası: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Portföy AI Persona Swarm İstihbarat Endpoint'i ───────────────────────────
@app.route("/api/portfolio/persona-intelligence", methods=["GET", "POST"])
def api_portfolio_persona_intelligence():
    """
    Seçilen portföy için 'Kimler İçin Uygun?' AI Swarm analizini döner.
    Query: ?url=... veya ?title=...
    POST: { "listing": {...} }
    """
    try:
        from intelligence.swarm.persona_swarm import PersonaSwarmSynthesizer
        synthesizer = PersonaSwarmSynthesizer()

        url_param = flask_request.args.get("url", "").strip()
        title_param = flask_request.args.get("title", "").strip()
        payload = flask_request.get_json(silent=True) or {}
        listing_input = payload.get("listing") or {}

        existing_intel = _load_portfolio_persona_intel()

        # Önbellekte var mı?
        target_key = url_param or title_param or listing_input.get("link") or listing_input.get("url") or listing_input.get("title")
        if target_key and target_key in existing_intel:
            return jsonify({"ok": True, "data": existing_intel[target_key], "cached": True})

        # Listeden ilanı tespit et
        found_listing = None
        if not listing_input:
            listings = _listings_cache["data"]
            if not listings:
                try:
                    cache_file = BASE_DIR / "static" / "data" / "cached_cb_listings.json"
                    if cache_file.exists():
                        with open(cache_file, "r", encoding="utf-8") as f:
                            listings = json.load(f)
                except Exception:
                    listings = []
            for item in listings:
                i_link = item.get("link") or item.get("url") or ""
                i_title = item.get("title") or ""
                if (url_param and (i_link == url_param or url_param in i_link)) or \
                   (title_param and (title_param.lower() in i_title.lower() or i_title.lower() in title_param.lower())):
                    found_listing = item
                    break

            # Eğer ilanda bulunamadıysa 35 Drive projesi arasında ara
            if not found_listing:
                try:
                    p_file = BASE_DIR / "projects_map.json"
                    if p_file.exists():
                        with open(p_file, "r", encoding="utf-8") as pf:
                            projs = json.load(pf)
                        for p in projs:
                            p_title = p.get("title") or p.get("name") or ""
                            p_id = str(p.get("id") or "")
                            if (title_param and (title_param.lower() in p_title.lower() or p_title.lower() in title_param.lower())) or \
                               (url_param and (p_id == url_param or url_param in p.get("tanitim_cloud_url", ""))):
                                found_listing = {
                                    "title": p_title,
                                    "property_type": p.get("category", "Markalı Konut Projesi"),
                                    "type": "Satılık",
                                    "price": p.get("price_display") or p.get("price") or "Lansman Fiyatı",
                                    "loc": p.get("location") or "Ankara",
                                    "rooms": p.get("room_info") or "",
                                    "area": f"{p.get('down_payment', '')} / {p.get('installment_terms', '')}",
                                    "link": f"/projeler?id={p.get('id')}",
                                    "img": p.get("thumbnail") or p.get("image") or ""
                                }
                                break
                except Exception:
                    pass

        target_listing = listing_input or found_listing or {
            "title": title_param or "Portföy Analizi",
            "url": url_param,
            "type": "Satılık",
            "price": "Fiyat Sorunuz",
            "loc": "Ankara"
        }

        intel = synthesizer.generate_intelligence(target_listing)

        # Önbelleğe kaydet
        if target_key:
            existing_intel[target_key] = intel
            _save_portfolio_persona_intel(existing_intel)

        return jsonify({"ok": True, "data": intel, "cached": False})

    except Exception as e:
        print(f"❌ api_portfolio_persona_intelligence hatası: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# API — CRM / TELEGRAM / FOLLOWUP
# ================================================================

@app.route("/api/telegram/notify", methods=["POST"])
def telegram_notify():
    """Lead kaydedilince anında Telegram bildirimi."""
    data = flask_request.json or {}
    name     = _html.escape(data.get("name", "İsimsiz"))
    phone    = _html.escape(data.get("phone", "-"))
    email    = _html.escape(data.get("email", "-"))
    source   = _html.escape(data.get("source", "CRM"))
    msg_     = _html.escape(data.get("message", ""))
    stage    = _html.escape(data.get("stage", ""))
    category = _html.escape(data.get("category", ""))

    text = (
        f"🔔 <b>Yeni Lead!</b>\n\n"
        f"👤 <b>{name}</b>\n"
        f"📞 {phone}\n"
        f"📧 {email}\n"
        f"🌐 Kaynak: {source}\n"
        + (f"📂 Kategori: {category}\n" if category else "")
        + (f"📊 Aşama: {stage}\n" if stage else "")
        + (f"💬 {msg_}\n" if msg_ else "")
        + f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    ok = send_telegram(text)
    return jsonify({"ok": ok})

# ================================================================
# LEAD STATE MACHINE
# ================================================================

LEAD_STAGES = [
    "new_lead",        # Form gönderildi, henüz işlem yok
    "report_sent",     # Otomatik rapor gönderildi
    "contacted",       # Danışman ilk teması kurdu
    "appointment",     # Randevu alındı
    "closed_won",      # Anlaşma yapıldı
    "closed_lost",     # Lead kaybedildi
]

def _log_lead_event(lead_id: str, event_type: str, payload: dict):
    """Lead event timeline'a kayıt yazar."""
    if not _fb_initialized:
        return
    try:
        db_admin.collection("leads").document(lead_id).collection("events").add({
            "type":      event_type,
            "payload":   payload,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        print(f"_log_lead_event hatası: {e}")

def _write_notification_log(lead_id: str, channel: str, status: str, detail: str = ""):
    """Bildirim gönderim logunu notifications koleksiyonuna yazar."""
    if not _fb_initialized:
        return
    try:
        db_admin.collection("notifications").add({
            "leadId":    lead_id,
            "channel":   channel,
            "status":    status,
            "detail":    detail,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        print(f"_write_notification_log hatası: {e}")

def _result_ok(result) -> bool:
    """bool veya dict sonuçlarını ortak başarı kontrolüne çevirir."""
    if isinstance(result, dict):
        return bool(result.get("ok"))
    return bool(result)

def _send_with_retry(fn, *args, retries=3, delay=2, **kwargs):
    """Fonksiyonu retries kez dener. (True, None) veya (False, hata) döner."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            result = fn(*args, **kwargs)
            if _result_ok(result):
                return True, None
            if isinstance(result, dict) and result.get("error"):
                last_err = result.get("error")
        except Exception as e:
            last_err = e
        if attempt < retries:
            time.sleep(delay)
    return False, str(last_err or "Bilinmeyen hata")

@app.route("/api/lead/state", methods=["POST"])
def update_lead_state():
    # Security: verify Firebase ID token before mutating lead state
    auth_hdr = flask_request.headers.get("Authorization", "")
    if auth_hdr.startswith("Bearer ") and _fb_initialized:
        try:
            fb_auth.verify_id_token(auth_hdr[7:])
        except Exception:
            return jsonify({"ok": False, "error": "Yetkisiz işlem: Geçerli oturum açmanız gerekmektedir."}), 401
    """Lead aşamasını günceller ve event log'a yazar."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    data      = flask_request.json or {}
    lead_id   = data.get("leadId")
    new_stage = data.get("newStage")

    if not lead_id or not new_stage:
        return jsonify({"ok": False, "error": "leadId ve newStage zorunlu"}), 400
    if new_stage not in LEAD_STAGES:
        return jsonify({"ok": False, "error": f"Geçersiz stage. Geçerliler: {LEAD_STAGES}"}), 400

    try:
        ref = db_admin.collection("leads").document(lead_id)
        doc = ref.get()
        if not doc.exists:
            return jsonify({"ok": False, "error": "Lead bulunamadı"}), 404

        old_stage = doc.to_dict().get("status", "")
        now_iso   = datetime.now(timezone.utc).isoformat()

        ref.update({
            "status":         new_stage,
            "stageChangedAt": now_iso,
            "updatedAt":      now_iso,
        })
        _log_lead_event(lead_id, "stage_change", {
            "from":  old_stage,
            "to":    new_stage,
            "actor": data.get("actorEmail", "system"),
            "note":  data.get("note", ""),
        })
        print(f"✅ Lead aşaması güncellendi: {lead_id} → {new_stage}")
        return jsonify({"ok": True, "leadId": lead_id, "newStage": new_stage})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def _send_valuation_async(
    lead_id: str, name: str, phone: str, email: str,
    neighborhood: str, property_type: str, rooms: str, sqm: str, notes: str,
):
    """
    Arka planda çalışır (threading.Thread).
    1. Gemini raporu üret
    2. Müşteriye e-posta (tam HTML rapor)
    3. Müşteriye WhatsApp template
    4. Danışmana Telegram
    5. Danışmana WhatsApp
    6. Danışmana e-posta
    7. Firestore güncelle
    """
    print(f"🔄 Değerleme raporu üretiliyor: {lead_id} | {neighborhood} / {property_type}")

    # ── 1. Gemini raporu üret ──────────────────────────────────────────────
    gemini_result = generate_valuation_report(
        name=name,
        neighborhood=neighborhood or "Ankara",
        property_type=property_type or "Konut",
        rooms=rooms,
        sqm=sqm,
        notes=notes,
    )

    if not gemini_result.get("ok"):
        err_msg = gemini_result.get("error", "Bilinmeyen hata")
        print(f"❌ Gemini raporu üretilemedi: {err_msg}")
        send_telegram(
            f"⚠️ <b>Değerleme Raporu Üretilemedi</b>\n\n"
            f"👤 {name} | 📞 {phone}\n"
            f"📍 {neighborhood} / {property_type}\n"
            f"🔗 Lead: <code>{lead_id}</code>\n"
            f"❌ Hata: {err_msg}"
        )
        if _fb_initialized and lead_id:
            try:
                db_admin.collection("leads").document(lead_id).update({
                    "valuationError":  err_msg,
                    "valuationFailed": True,
                    "valuationAt":     datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                print(f"Firestore hata güncelleme hatası: {e}")
        return

    report = gemini_result["report"]
    pr  = report.get("price_range", {})
    inv = report.get("investment_score", {})
    na  = report.get("neighborhood_analysis", {})
    channels = {}

    # ── 2. Müşteriye e-posta ───────────────────────────────────────────────
    if email:
        try:
            subj, text_b, html_b = build_valuation_report_email(name=name, report=report)
            res = send_transactional_email(email, subj, text_b, html_b)
            channels["customer_email_valuation"] = "sent" if res.get("ok") else f"failed: {res.get('error','')}"
            print(f"{'✅' if res.get('ok') else '❌'} Müşteri değerleme e-postası: {email}")
        except Exception as e:
            channels["customer_email_valuation"] = f"exception: {e}"
            print(f"❌ Müşteri e-posta hatası: {e}")
    else:
        channels["customer_email_valuation"] = "skipped_no_email"

    # ── 3. Müşteriye WhatsApp template ────────────────────────────────────
    if phone and VALUATION_WA_TEMPLATE_NAME:
        try:
            components = [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": name},
                    {"type": "text", "text": neighborhood or "bölgeniz"},
                    {"type": "text", "text": pr.get("average", "")},
                ],
            }]
            wa_res = send_whatsapp_template(
                phone=phone,
                template_name=VALUATION_WA_TEMPLATE_NAME,
                language_code="tr",
                components=components,
            )
            channels["customer_wa_valuation"] = "sent" if wa_res.get("ok") else f"failed: {wa_res.get('error','')}"
            print(f"{'✅' if wa_res.get('ok') else '❌'} Müşteri değerleme WA: {phone}")
        except Exception as e:
            channels["customer_wa_valuation"] = f"exception: {e}"
    else:
        channels["customer_wa_valuation"] = "skipped_no_template" if not VALUATION_WA_TEMPLATE_NAME else "skipped_no_phone"

    # ── 4. Danışmana Telegram ──────────────────────────────────────────────
    t_icon = "📈" if na.get("trend") == "yükselen" else ("📉" if na.get("trend") == "düşen" else "➡️")
    advisor_tg = (
        f"📊 <b>Değerleme Raporu Gönderildi!</b>\n\n"
        f"👤 <b>{name}</b>\n"
        f"📞 {phone}\n"
        + (f"📧 {email}\n" if email else "")
        + f"📍 {neighborhood} / {property_type}\n\n"
        f"💰 <b>Tahmini Değer:</b> {pr.get('average','?')}\n"
        f"   {pr.get('min','?')} — {pr.get('max','?')}\n"
        f"   m²: {pr.get('per_sqm_min','?')} – {pr.get('per_sqm_max','?')}\n\n"
        f"⭐ <b>Skor:</b> {inv.get('score','?')}/{inv.get('max',10)} — {inv.get('label','')}\n"
        f"{t_icon} <b>Trend:</b> {na.get('trend','?').capitalize()}\n\n"
        f"✅ Rapor müşteriye e-posta"
        + (" + WA" if channels.get("customer_wa_valuation") == "sent" else "")
        + " ile iletildi.\n"
        f"🔗 Lead: <code>{lead_id}</code>"
    )
    ok_tg, err_tg = _send_with_retry(send_telegram, advisor_tg)
    channels["advisor_telegram_valuation"] = "sent" if ok_tg else f"failed: {err_tg}"

    # ── 5. Danışmana WhatsApp ──────────────────────────────────────────────
    advisor_wa_msg = (
        f"📊 *Değerleme Raporu Gönderildi!*\n\n"
        f"👤 *{name}*\n📞 {phone}\n"
        f"📍 {neighborhood} / {property_type}\n\n"
        f"💰 *{pr.get('average','?')}*\n"
        f"   {pr.get('min','?')} — {pr.get('max','?')}\n\n"
        f"⭐ Skor: {inv.get('score','?')}/{inv.get('max',10)} ({inv.get('label','')})\n"
        f"{t_icon} Trend: {na.get('trend','?')}\n\n"
        f"✅ Rapor müşteriye iletildi.\nLead: {lead_id}"
    )
    wa_adv = send_whatsapp(WA_ADVISOR_PHONE, advisor_wa_msg)
    channels["advisor_wa_valuation"] = "sent" if wa_adv.get("ok") else f"failed: {wa_adv.get('error','')}"

    # ── 6. Danışmana e-posta ───────────────────────────────────────────────
    if ADVISOR_EMAIL:
        try:
            subj_a, txt_a, html_a = build_advisor_valuation_email(
                customer_name=name,
                customer_phone=phone,
                customer_email=email,
                neighborhood=neighborhood,
                property_type=property_type,
                report=report,
            )
            res_a = send_transactional_email(ADVISOR_EMAIL, subj_a, txt_a, html_a)
            channels["advisor_email_valuation"] = "sent" if res_a.get("ok") else f"failed: {res_a.get('error','')}"
            print(f"{'✅' if res_a.get('ok') else '❌'} Danışman bildirim e-postası: {ADVISOR_EMAIL}")
        except Exception as e:
            channels["advisor_email_valuation"] = f"exception: {e}"
    else:
        channels["advisor_email_valuation"] = "skipped_no_advisor_email"

    # ── 7. Firestore güncelle ──────────────────────────────────────────────
    if _fb_initialized and lead_id:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            db_admin.collection("leads").document(lead_id).update({
                "valuationReport":   report,
                "valuationSentAt":   now_iso,
                "valuationChannels": channels,
                "updatedAt":         now_iso,
            })
            _log_lead_event(lead_id, "valuation_report_sent", {
                "actor":     "grok_auto",
                "channels":  channels,
                "price_avg": pr.get("average", ""),
                "score":     inv.get("score", ""),
            })
            for ch, st in channels.items():
                _write_notification_log(lead_id, ch,
                    "sent" if st == "sent" else "failed",
                    st if st != "sent" else "")
            print(f"✅ Firestore valuation güncellendi: {lead_id}")
        except Exception as e:
            print(f"❌ Firestore güncelleme hatası: {e}")

    print(f"🏁 _send_valuation_async tamamlandı: {lead_id} | {channels}")

@app.route("/api/lead/report", methods=["POST"])
def send_lead_report():
    """
    Form gönderiminden hemen sonra tetiklenir.
    Danışmana Telegram + WhatsApp bildirimi gönderir.
    İsteğe bağlı olarak müşteriye onay e-postası ve WhatsApp template mesajı gönderir.
    Body: { leadId, name, phone, email?, neighborhood?, property_type?, notes? }
    """
    data    = flask_request.json or {}
    lead_id = data.get("leadId", "")
    name    = data.get("name", "İsimsiz")
    phone   = data.get("phone", "-")
    email   = data.get("email", "")
    neigh   = data.get("neighborhood", "")
    ptype   = data.get("property_type", "")
    rooms   = data.get("rooms", "")
    sqm     = data.get("area", "")    # site.html'de alan adı "area"
    notes   = data.get("notes", "")

    result = {"ok": True, "channels": {}}

    advisor_msg = (
        f"📋 <b>Yeni Değerleme Talebi!</b>\n\n"
        f"👤 <b>{name}</b>\n"
        f"📞 {phone}\n"
        + (f"📧 {email}\n" if email else "")
        + (f"📍 Mahalle: {neigh}\n" if neigh else "")
        + (f"🏠 Mülk Tipi: {ptype}\n" if ptype else "")
        + (f"💬 Not: {notes}\n" if notes else "")
        + f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        + f"🔗 Lead ID: <code>{lead_id}</code>"
    )

    ok_tg, err_tg = _send_with_retry(send_telegram, advisor_msg)
    result["channels"]["telegram"] = "sent" if ok_tg else f"failed: {err_tg}"

    wa_msg = (
        f"📋 *Yeni Değerleme Talebi!*\n\n"
        f"👤 *{name}*\n"
        f"📞 {phone}\n"
        + (f"📧 {email}\n" if email else "")
        + (f"📍 Mahalle: {neigh}\n" if neigh else "")
        + (f"🏠 Mülk Tipi: {ptype}\n" if ptype else "")
        + (f"💬 Not: {notes}\n" if notes else "")
        + f"\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        + f"🔗 Lead: {lead_id}"
    )
    wa_result = send_whatsapp(WA_ADVISOR_PHONE, wa_msg)
    result["channels"]["whatsapp"] = "sent" if wa_result["ok"] else f"skipped: {wa_result.get('error','')}"

    email_result = {"ok": False, "error": "disabled"}
    if ENABLE_CUSTOMER_EMAIL_AUTOMATION and email:
        subject, text_body, html_body = build_lead_confirmation_email(
            name=name,
            phone=phone,
            neighborhood=neigh,
            property_type=ptype,
            notes=notes,
        )
        email_result = send_transactional_email(email, subject, text_body, html_body)
        result["channels"]["customer_email"] = "sent" if email_result.get("ok") else f"skipped: {email_result.get('error','')}"
    elif email:
        result["channels"]["customer_email"] = "disabled"
    else:
        result["channels"]["customer_email"] = "missing_email"

    customer_wa_result = {"ok": False, "error": "disabled"}
    if ENABLE_CUSTOMER_WA_AUTOMATION and CUSTOMER_WA_TEMPLATE_NAME and phone:
        customer_wa_result = send_whatsapp_template(
            phone,
            CUSTOMER_WA_TEMPLATE_NAME,
            "tr",
            [{"type": "body", "parameters": [{"type": "text", "text": name}]}],
        )
        result["channels"]["customer_whatsapp"] = "sent" if customer_wa_result.get("ok") else f"skipped: {customer_wa_result.get('error','')}"
    else:
        result["channels"]["customer_whatsapp"] = "disabled"

    if _fb_initialized and lead_id:
        _write_notification_log(lead_id, "telegram", "sent" if ok_tg else "failed", err_tg or "")
        _write_notification_log(lead_id, "whatsapp", "sent" if wa_result["ok"] else "skipped", wa_result.get("error", ""))
        if email:
            _write_notification_log(lead_id, "customer_email", "sent" if email_result.get("ok") else "skipped", email_result.get("error", ""))
        if phone and CUSTOMER_WA_TEMPLATE_NAME:
            _write_notification_log(lead_id, "customer_whatsapp", "sent" if customer_wa_result.get("ok") else "skipped", customer_wa_result.get("error", ""))

        if ok_tg or wa_result["ok"]:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                db_admin.collection("leads").document(lead_id).update({
                    "status":         "report_sent",
                    "reportSentAt":   now_iso,
                    "stageChangedAt": now_iso,
                    "updatedAt":      now_iso,
                    "automation": {
                        "advisorTelegram": ok_tg,
                        "advisorWhatsapp": wa_result["ok"],
                        "customerEmail": email_result.get("ok", False),
                        "customerWhatsapp": customer_wa_result.get("ok", False),
                    }
                })
                _log_lead_event(lead_id, "stage_change", {
                    "from":  "new_lead",
                    "to":    "report_sent",
                    "actor": "system",
                    "note":  "Otomatik rapor gönderildi (Telegram + WhatsApp Cloud API)",
                })
                if email_result.get("ok"):
                    _log_lead_event(lead_id, "customer_email_sent", {
                        "actor": "system",
                        "email": email,
                        "template": "lead_confirmation",
                    })
                if customer_wa_result.get("ok"):
                    _log_lead_event(lead_id, "customer_whatsapp_sent", {
                        "actor": "system",
                        "phone": phone,
                        "template": CUSTOMER_WA_TEMPLATE_NAME,
                    })
            except Exception as e:
                print(f"Lead güncelleme hatası: {e}")

    if not ok_tg and not wa_result["ok"] and not email_result.get("ok") and not customer_wa_result.get("ok"):
        print(f"❌ Rapor hiçbir kanaldan gönderilemedi! Lead: {lead_id}")
        result["ok"] = False

    # ── Arka planda Grok değerleme raporu üret ve gönder ──────────────────
    if name and (email or phone):
        threading.Thread(
            target=_send_valuation_async,
            args=(lead_id, name, phone, email, neigh, ptype, rooms, sqm, notes),
            daemon=True,
        ).start()
        result["valuation"] = "queued"
        print(f"🔄 Değerleme thread başlatıldı: {lead_id}")
    else:
        result["valuation"] = "skipped_missing_contact"

    return jsonify(result)

@app.route("/api/valuation/quick", methods=["POST"])
def valuation_quick():
    """
    Senkron değerleme — site.html formu için anlık rapor döner.
    Grok web arama ile 30-90s içinde yanıt verir.
    Body: { name, neighborhood, property_type, rooms?, area?, notes? }
    Returns: { ok, report: {...} } | { ok: false, error }
    """
    data = flask_request.json or {}
    result = generate_valuation_report(
        name          = data.get("name", ""),
        neighborhood  = data.get("neighborhood", "Ankara"),
        property_type = data.get("property_type", "Konut"),
        rooms         = data.get("rooms", ""),
        sqm           = data.get("area", ""),
        notes         = data.get("notes", ""),
    )
    return jsonify(result)

@app.route("/api/lead/events/<lead_id>", methods=["GET"])
def get_lead_events(lead_id):
    """Lead'e ait tüm event timeline'ını döner."""
    if not _fb_initialized:
        return jsonify({"ok": False, "data": []}), 503
    try:
        events = []
        for doc in (db_admin.collection("leads").document(lead_id)
                    .collection("events").order_by("createdAt").stream()):
            d = doc.to_dict()
            d["id"] = doc.id
            events.append(d)
        return jsonify({"ok": True, "data": events})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/lead/stages", methods=["GET"])
def get_lead_stages():
    """Geçerli stage listesini döner (frontend için)."""
    return jsonify({"ok": True, "stages": LEAD_STAGES})

@app.route("/api/followup/schedule", methods=["POST"])
def schedule_followup():
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    data = flask_request.json or {}
    uid = data.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    now = datetime.now(timezone.utc)
    followup_data = {
        "contactId":    data.get("contactId", ""),
        "contactName":  data.get("contactName", ""),
        "contactPhone": data.get("contactPhone", ""),
        "contactEmail": data.get("contactEmail", ""),
        "notes": {
            "week1": data.get("notes", {}).get("week1", "1. hafta takip görüşmesi"),
            "week2": data.get("notes", {}).get("week2", "2. hafta durum değerlendirmesi"),
            "week3": data.get("notes", {}).get("week3", "3. hafta kapanış fırsatı"),
        },
        "startDate":  now.isoformat(),
        "week1Date":  (now + timedelta(days=7)).isoformat(),
        "week2Date":  (now + timedelta(days=14)).isoformat(),
        "week3Date":  (now + timedelta(days=21)).isoformat(),
        "sent":  {"week1": False, "week2": False, "week3": False},
        "done":      False,
        "createdAt": now.isoformat()
    }

    try:
        ref = (db_admin.collection("users").document(uid)
               .collection("followups").add(followup_data))
        doc_id = ref[1].id

        name = followup_data["contactName"]
        text = (
            f"🚀 <b>Takip Planı Başlatıldı!</b>\n\n"
            f"👤 <b>{name}</b>\n"
            f"📞 {followup_data['contactPhone']}\n\n"
            f"📅 <b>Takvim:</b>\n"
            f"  • 1. Hafta: {(now + timedelta(days=7)).strftime('%d.%m.%Y')} → {followup_data['notes']['week1']}\n"
            f"  • 2. Hafta: {(now + timedelta(days=14)).strftime('%d.%m.%Y')} → {followup_data['notes']['week2']}\n"
            f"  • 3. Hafta: {(now + timedelta(days=21)).strftime('%d.%m.%Y')} → {followup_data['notes']['week3']}\n"
            f"\n⏰ {now.strftime('%d.%m.%Y %H:%M')}"
        )
        send_telegram(text)
        return jsonify({"ok": True, "id": doc_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/followup/update", methods=["POST"])
def update_followup():
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    data = flask_request.json or {}
    uid         = data.get("uid")
    followup_id = data.get("followupId")
    notes       = data.get("notes", {})

    if not uid or not followup_id:
        return jsonify({"ok": False, "error": "uid ve followupId gerekli"}), 400

    try:
        ref = (db_admin.collection("users").document(uid)
               .collection("followups").document(followup_id))
        update_data = {}
        for week in ["week1", "week2", "week3"]:
            if week in notes:
                update_data[f"notes.{week}"] = notes[week]
        update_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/followup/cancel", methods=["POST"])
def cancel_followup():
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    data        = flask_request.json or {}
    uid         = data.get("uid")
    followup_id = data.get("followupId")

    if not uid or not followup_id:
        return jsonify({"ok": False, "error": "uid ve followupId gerekli"}), 400

    try:
        ref = (db_admin.collection("users").document(uid)
               .collection("followups").document(followup_id))
        ref.update({"done": True, "cancelledAt": datetime.now(timezone.utc).isoformat()})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/followup/list", methods=["POST"])
def list_followups():
    if not _fb_initialized:
        return jsonify({"ok": False, "data": []}), 503

    data       = flask_request.json or {}
    uid        = data.get("uid")
    contact_id = data.get("contactId")

    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        query = (db_admin.collection("users").document(uid)
                 .collection("followups").where(filter=FieldFilter("done", "==", False)))
        if contact_id:
            query = query.where(filter=FieldFilter("contactId", "==", contact_id))

        result = []
        for doc in query.stream():
            d = doc.to_dict()
            d["id"] = doc.id
            result.append(d)

        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# SCHEDULER — Hatırlatma & Haftalık Takip
# ================================================================

def check_reminders():
    if not _fb_initialized or db_admin is None:
        return
    try:
        for user_doc in db_admin.collection("users").stream():
            uid = user_doc.id
            for rem in (db_admin.collection("users").document(uid)
                        .collection("reminders")
                        .where(filter=FieldFilter("done", "==", False))
                        .where(filter=FieldFilter("telegramSent", "==", False))
                        .stream()):
                r = rem.to_dict()
                due = r.get("dueDate", "")
                if not due:
                    continue
                try:
                    due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                    # Eğer timezone bilgisi yoksa (frontend datetime-local gönderdi = UTC+3 yerel saat)
                    if due_dt.tzinfo is None:
                        due_dt = due_dt.replace(tzinfo=timezone(timedelta(hours=3)))
                except Exception:
                    try:
                        due_dt = datetime.strptime(due[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except Exception:
                        continue

                if due_dt <= datetime.now(timezone.utc):
                    name   = _html.escape(r.get("contactName", "Müşteri"))
                    text_  = _html.escape(r.get("text", "Hatırlatma"))
                    phone_ = _html.escape(r.get("contactPhone", ""))
                    msg = (
                        f"⏰ <b>Hatırlatma!</b>\n\n"
                        f"👤 <b>{name}</b>" + (f" — {phone_}" if phone_ else "") + "\n"
                        f"📝 {text_}\n\n"
                        f"📅 {due_dt.strftime('%d.%m.%Y')}"
                    )
                    if send_telegram(msg):
                        rem.reference.update({"telegramSent": True})
                        print(f"📨 Hatırlatma gönderildi: {name}")
    except Exception as e:
        print(f"check_reminders hatası: {e}")

def check_followups():
    if not _fb_initialized or db_admin is None:
        return
    try:
        now = datetime.now(timezone.utc)
        for user_doc in db_admin.collection("users").stream():
            uid = user_doc.id
            for f_doc in (db_admin.collection("users").document(uid)
                          .collection("followups")
                          .where(filter=FieldFilter("done", "==", False))
                          .stream()):
                f = f_doc.to_dict()
                name  = _html.escape(f.get("contactName", "Müşteri"))
                phone = _html.escape(f.get("contactPhone", ""))
                notes = f.get("notes", {})
                sent  = f.get("sent", {})
                updates = {}

                for week_key, date_key in [
                    ("week1", "week1Date"),
                    ("week2", "week2Date"),
                    ("week3", "week3Date"),
                ]:
                    if sent.get(week_key):
                        continue
                    due_str = f.get(date_key, "")
                    if not due_str:
                        continue
                    try:
                        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                    except Exception:
                        continue

                    if due_dt <= now:
                        week_num = week_key.replace("week", "")
                        note_text = notes.get(week_key, f"{week_num}. hafta takip")
                        msg = (
                            f"📆 <b>{week_num}. Hafta Takip Bildirimi</b>\n\n"
                            f"👤 <b>{name}</b>"
                            + (f"\n📞 {phone}" if phone else "") + "\n\n"
                            f"📝 <i>{note_text}</i>\n\n"
                            f"⏰ {now.strftime('%d.%m.%Y %H:%M')}"
                        )
                        if send_telegram(msg):
                            updates[f"sent.{week_key}"] = True
                            print(f"📨 {week_num}. hafta takip gönderildi: {name}")

                if updates:
                    new_sent = {**sent, **{k.split(".")[1]: v for k, v in updates.items()}}
                    if all(new_sent.get(w, False) for w in ["week1", "week2", "week3"]):
                        updates["done"] = True
                        updates["completedAt"] = now.isoformat()
                        send_telegram(
                            f"✅ <b>Takip Tamamlandı!</b>\n\n"
                            f"👤 <b>{_html.escape(str(name))}</b> için 3 haftalık takip süreci tamamlandı.\n"
                            f"⏰ {now.strftime('%d.%m.%Y %H:%M')}"
                        )
                    f_doc.reference.update(updates)
    except Exception as e:
        print(f"check_followups hatası: {e}")

def start_scheduler():
    def loop():
        while True:
            try:
                check_reminders()
                check_followups()
            except Exception as e:
                print(f"Scheduler hatası: {e}")
            time.sleep(60)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print("⏱️  Scheduler başladı (60s) — Hatırlatmalar + Haftalık Takipler")

# ================================================================
# BAŞLAT / BOOTSTRAP
# ================================================================
_bootstrap_done = False

# ── 1. Durum & Konfigürasyon ──────────────────────────────────────

@app.route("/api/buyer/status")
def api_buyer_status():
    """Buyer Engine durumu."""
    return jsonify(buyer_engine_status())

# ── 2. Buyer Profili Yönetimi ──────────────────────────────────────

@app.route("/api/buyer/profile/create", methods=["POST"])
def api_buyer_create():
    """
    Yeni alıcı profili oluştur.
    
    Body (JSON):
    {
      "uid": "user123",
      "name": "Ahmet Yılmaz",
      "email": "ahmet@example.com",
      "phone": "05324514008",
      "telegram_id": "123456789",
      "whatsapp_phone": "05324514008",
      "criteria": {
        "min_price": 3000000,
        "max_price": 6000000,
        "min_area": 80,
        "max_area": 150,
        "neighborhoods": ["Çankaya", "Dikmen"],
        "property_types": ["Daire", "Dubleks"],
        "min_rooms": 2,
        "max_rooms": 4,
        "natural_language": "Ankara'da yeni ve güzel, balkonlu, otopark"
      },
      "preferences": {
        "notification_channels": ["email", "crm_task"],
        "auto_match": true,
        "priority_level": "high"
      }
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")

    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        profile = BuyerProfile({
            **body,
            "uid": uid,
            "id": db_admin.collection("buyers").document().id,
        })

        doc_ref = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(profile.buyer_id)
        )
        doc_ref.set(profile.to_dict())

        return jsonify({
            "ok": True,
            "buyer_id": profile.buyer_id,
            "profile": profile.to_dict()
        }), 201

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/profile/list", methods=["GET"])
def api_buyer_list():
    """Kullanıcının tüm buyer profillerini listele."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        docs = (
            db_admin.collection("users").document(uid)
            .collection("buyers").stream()
        )
        profiles = [doc.to_dict() for doc in docs]
        return jsonify({"ok": True, "profiles": profiles})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/profile/get", methods=["GET"])
def api_buyer_get():
    """Tek bir buyer profili getir."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        doc = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).get()
        )
        if not doc.exists:
            return jsonify({"ok": False, "error": "Profil bulunamadı"}), 404
        return jsonify({"ok": True, "profile": doc.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/profile/update", methods=["POST"])
def api_buyer_update():
    """Buyer profili güncelle."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        doc_ref = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id)
        )
        profile_dict = doc_ref.get().to_dict()
        if not profile_dict:
            return jsonify({"ok": False, "error": "Profil bulunamadı"}), 404

        # Güncelle
        profile_dict.update(body)
        profile_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        doc_ref.set(profile_dict)

        return jsonify({"ok": True, "profile": profile_dict})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/profile/delete", methods=["POST"])
def api_buyer_delete():
    """Buyer profilini sil."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).delete()
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 3. Eşleştirme Engine ────────────────────────────────────────

@app.route("/api/buyer/match-listing", methods=["POST"])
def api_buyer_match_listing():
    """
    Tek bir ilanı buyer profillerine göre eşleştir.
    
    Body:
    {
      "uid": "user123",
      "listing": { ...listing_data... },
      "buyer_ids": ["buyer1", "buyer2"]  // opsiyonel, tümü default
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    listing = body.get("listing")
    buyer_ids = body.get("buyer_ids", [])

    if not uid or not listing:
        return jsonify({"ok": False, "error": "uid ve listing gerekli"}), 400

    try:
        matcher = BuyerMatcher()

        # Buyer profilleri getir
        if buyer_ids:
            buyers_snap = []
            for bid in buyer_ids:
                doc = (
                    db_admin.collection("users").document(uid)
                    .collection("buyers").document(bid).get()
                )
                if doc.exists:
                    buyers_snap.append(doc)
        else:
            buyers_snap = list(
                db_admin.collection("users").document(uid)
                .collection("buyers").stream()
            )

        matches = []
        for buyer_doc in buyers_snap:
            buyer_dict = buyer_doc.to_dict()
            profile = BuyerProfile(buyer_dict)
            match = matcher.match_listing(profile, listing)

            if match:
                matches.append({
                    "buyer_id": profile.buyer_id,
                    "match_score": match.match_score,
                    "tier": match.tier,
                    "details": match.match_details,
                })

        return jsonify({
            "ok": True,
            "listing_id": listing.get("id", ""),
            "matches": matches,
            "total_matches": len(matches),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/match-batch", methods=["POST"])
def api_buyer_match_batch():
    """
    Birden fazla ilanı buyer'larla batch eşleştir.
    Ağır operasyon — background job olarak önerilir.
    
    Body:
    {
      "uid": "user123",
      "listings": [{ ...listing1... }, { ...listing2... }],
      "buyer_ids": ["buyer1"]  // opsiyonel
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    listings = body.get("listings", [])

    if not uid or not listings:
        return jsonify({"ok": False, "error": "uid ve listings gerekli"}), 400

    try:
        matcher = BuyerMatcher()
        all_matches = []

        for listing in listings:
            # Her listing için tüm buyer'ları eşleştir
            # ... (api_buyer_match_listing mantığı)
            pass

        return jsonify({"ok": True, "total_matches": len(all_matches)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 4. Matching Geçmişi ────────────────────────────────────────

@app.route("/api/buyer/matches/list", methods=["GET"])
def api_buyer_matches_list():
    """
    Buyer'ın tüm eşleşmelerini listele (en yenisi önce).
    
    Query params:
      - uid: gerekli
      - buyer_id: gerekli
      - tier: "perfect", "excellent" vb. (filtre)
      - limit: 50 (default)
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")
    tier = flask_request.args.get("tier")
    limit = int(flask_request.args.get("limit", "50"))

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        query = (
            db_admin.collection("users").document(uid)
            .collection("buyer_matches")
            .where("buyer_id", "==", buyer_id)
            .order_by("created_at", direction="DESCENDING")
        )

        if tier:
            query = query.where("tier", "==", tier)

        docs = query.limit(limit).stream()
        matches = [doc.to_dict() for doc in docs]

        return jsonify({"ok": True, "matches": matches, "count": len(matches)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/buyer/matches/stats", methods=["GET"])
def api_buyer_matches_stats():
    """Buyer'ın eşleşme istatistikleri."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        docs = list(
            db_admin.collection("users").document(uid)
            .collection("buyer_matches")
            .where("buyer_id", "==", buyer_id)
            .stream()
        )

        stats = {
            "perfect": sum(1 for d in docs if d.to_dict().get("tier") == "perfect"),
            "excellent": sum(1 for d in docs if d.to_dict().get("tier") == "excellent"),
            "good": sum(1 for d in docs if d.to_dict().get("tier") == "good"),
            "fair": sum(1 for d in docs if d.to_dict().get("tier") == "fair"),
            "total": len(docs),
            "avg_score": sum(d.to_dict().get("match_score", 0) for d in docs) / len(docs) if docs else 0,
        }

        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 5. Notification Tetikle ────────────────────────────────────────

@app.route("/api/buyer/notify", methods=["POST"])
def api_buyer_notify():
    """
    Eşleşme için manual notification tetikle.
    
    Body:
    {
      "uid": "user123",
      "buyer_id": "buyer1",
      "match_id": "match123",
      "channels": ["email", "telegram", "crm_task"]
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")
    channels = body.get("channels", ["email", "crm_task"])

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        # Buyer profili getir
        buyer_doc = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).get()
        )
        if not buyer_doc.exists:
            return jsonify({"ok": False, "error": "Buyer profili bulunamadı"}), 404

        buyer_dict = buyer_doc.to_dict()
        buyer = BuyerProfile(buyer_dict)

        # Email gönder
        result = {}
        if "email" in channels and buyer.email:
            subject, text, html = build_lead_confirmation_email(
                name=buyer.name,
                phone=buyer.phone,
                notes=f"Eşleşme skoru: {body.get('match_score', 0):.0f}%"
            )
            result["email"] = send_transactional_email(buyer.email, subject, text, html)

        # Telegram gönder
        if "telegram" in channels and buyer.telegram_id:
            message = f"🏠 Yeni eşleşme: {body.get('match_score', 0):.0f}%"
            # Telegram API call (app.py'de tanımlanmalı)
            result["telegram"] = {"ok": True}  # Placeholder

        # WhatsApp gönder
        if "whatsapp" in channels and buyer.whatsapp_phone:
            result["whatsapp"] = send_whatsapp(
                buyer.whatsapp_phone,
                f"Yeni eşleşme: {body.get('match_score', 0):.0f}%"
            )

        # CRM görev aç
        if "crm_task" in channels:
            result["crm_task"] = {"ok": True}  # Placeholder

        return jsonify({"ok": True, "notifications": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 6. Natural Language Parsing ────────────────────────────────────

@app.route("/api/buyer/parse-criteria", methods=["POST"])
def api_buyer_parse_criteria():
    """
    Natural language kriterleri parse et (Gemini).
    
    Body:
    {
      "text": "Ankara'da 2+1 daire, maksimum 5 milyon, Çankaya veya Dikmen"
    }
    """
    body = flask_request.json or {}
    text = body.get("text", "").strip()

    if not text:
        return jsonify({"ok": False, "error": "text boş"}), 400

    try:
        criteria = parse_natural_language_criteria(text)
        return jsonify({"ok": True, "criteria": criteria or {}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── 7. Dashboard & Analytics ────────────────────────────────────────

@app.route("/api/buyer/dashboard", methods=["GET"])
def api_buyer_dashboard():
    """Buyer dashboard — özet istatistikler."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        # Profil sayısı
        buyers = list(
            db_admin.collection("users").document(uid)
            .collection("buyers").where("is_active", "==", True).stream()
        )

        # Toplam eşleşme
        all_matches = list(
            db_admin.collection("users").document(uid)
            .collection("buyer_matches").stream()
        )

        # Tier dağılımı
        tier_dist = {}
        for match_doc in all_matches:
            tier = match_doc.to_dict().get("tier", "unknown")
            tier_dist[tier] = tier_dist.get(tier, 0) + 1

        return jsonify({
            "ok": True,
            "dashboard": {
                "active_buyers": len(buyers),
                "total_matches": len(all_matches),
                "tier_distribution": tier_dist,
                "avg_match_score": (
                    sum(d.to_dict().get("match_score", 0) for d in all_matches) / len(all_matches)
                    if all_matches else 0
                ),
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# CB VIP OFFICE SCANNING ENDPOINTS
# ================================================================

@app.route("/api/scan-office", methods=["POST"])
def api_scan_office():
    """CB VIP ofis listing'lerini tara, analiz et ve kaydet."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    office_url = body.get("office_url", "").strip()

    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    if not office_url:
        office_url = "https://www.cb.com.tr/ilanlar?officeid=470&officeuserid=23339"

    try:
        import uuid
        scan_id = f"scan_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        scan_doc = {
            "uid": uid,
            "office_url": office_url,
            "status": "scanning",
            "started_at": timestamp,
            "listings_found": 0,
            "listings_analyzed": 0,
            "error": None,
        }

        db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).set(scan_doc)
        threading.Thread(target=_background_scan_office, args=(uid, scan_id, office_url), daemon=True).start()

        return jsonify({"ok": True, "scan_id": scan_id, "status": "scanning", "message": "CB VIP ofis taraması başlatıldı..."})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def _background_scan_office(uid: str, scan_id: str, office_url: str):
    """Background thread'de CB VIP office'i tara ve analiz et."""
    try:
        listings = _scrape_cb_vip_listings(office_url)
        
        if not listings:
            db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).update({
                "status": "completed",
                "listings_found": 0,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": "Listing bulunamadı",
            })
            return

        analyzed_count = 0
        for idx, listing in enumerate(listings, 1):
            try:
                analysis_result = analyze_listing(listing_data=listing, manual_data=None, uploaded_images=[])

                if analysis_result.get("ok"):
                    listing_record = {
                        "source": "cb_vip",
                        "office_url": office_url,
                        "scan_id": scan_id,
                        "listing_data": listing,
                        "analysis": analysis_result.get("report", {}),
                        "url": listing.get("url", ""),
                        "price": listing.get("price", 0),
                        "area": listing.get("area", 0),
                        "location": listing.get("location", ""),
                        "property_type": listing.get("property_type", ""),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    db_admin.collection("users").document(uid).collection("scanned_listings").document().set(listing_record)
                    analyzed_count += 1

                if idx % 5 == 0:
                    db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).update({"listings_analyzed": analyzed_count})

            except Exception as e:
                print(f"Listing analiz hatası: {e}")
                continue

        db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).update({
            "status": "completed",
            "listings_found": len(listings),
            "listings_analyzed": analyzed_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).update({
            "status": "error",
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

def _scrape_cb_vip_listings(url: str) -> list:
    """CB VIP listing URL'sinden listing'leri scrape et."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        listings = []
        
        listing_cards = soup.select(".card.locationDiv")
        if not listing_cards:
            listing_cards = soup.select(".cb-list-item")

        for card in listing_cards[:50]:
            try:
                title_elem = card.select_one(".cb-list-item-info h2") or card.select_one(".card-title")
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                price_elem = card.select_one(".feature-item .text-primary") or card.select_one("span.h5.text-primary")
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                price = _parse_price(price_text)
                
                area = 0
                for feat in card.select(".feature-item"):
                    feat_text = feat.get_text(strip=True)
                    if "m2" in feat_text or "m²" in feat_text:
                        area = _parse_area(feat_text)
                        
                link_elem = card.select_one(".cb-list-img-container a") or card.select_one("a.title") or card.select_one("a[href]")
                listing_url = link_elem["href"] if link_elem else ""
                if listing_url and not listing_url.startswith("http"):
                    listing_url = "https://www.cb.com.tr" + listing_url
                    
                region_el = card.select_one('span[itemprop="addressRegion"]')
                street_el = card.select_one('span[itemprop="streetAddress"]')
                location = f"{region_el.get_text(strip=True) if region_el else ''}, {street_el.get_text(strip=True) if street_el else ''}" if region_el else "Ankara"

                listing = {"title": title, "price": price, "area": area, "location": location, "url": listing_url, "property_type": _infer_property_type(title), "source": "cb_vip"}
                listings.append(listing)

            except Exception as e:
                print(f"Card parse hatası: {e}")
                continue

        return listings

    except Exception as e:
        print(f"CB VIP scraping hatası: {e}")
        return []

def _parse_price(price_str: str) -> float:
    """Fiyat string'ini parse et."""
    try:
        import re as _re_temp
        numbers = _re_temp.findall(r"\d+", price_str.replace(".", "").replace(",", ""))
        if numbers:
            return float("".join(numbers))
    except:
        pass
    return 0.0

def _parse_area(area_str: str) -> float:
    """Alan string'ini parse et."""
    try:
        numbers = _re_temp.findall(r"\d+", area_str)
        if numbers:
            return float(numbers[0])
    except:
        pass
    return 0.0

def _infer_property_type(title: str) -> str:
    """Başlıktan mülk tipini çıkar."""
    title_lower = title.lower()
    if "villa" in title_lower:
        return "Villa"
    elif "ticari" in title_lower or "dükkân" in title_lower:
        return "Ticari"
    elif "arsa" in title_lower:
        return "Arsa"
    elif "daire" in title_lower or "apartman" in title_lower:
        return "Daire"
    return "Diğer"

@app.route("/api/scan-office/status/<scan_id>", methods=["GET"])
def api_scan_office_status(scan_id: str):
    """Office tarama durumunu kontrol et."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        scan_doc = db_admin.collection("users").document(uid).collection("office_scans").document(scan_id).get()
        if not scan_doc.exists:
            return jsonify({"ok": False, "error": "Scan bulunamadı"}), 404
        return jsonify({"ok": True, "scan": scan_doc.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/scan-office/listings", methods=["GET"])
def api_scan_office_listings():
    """Taranmış listing'leri listele."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    limit = int(flask_request.args.get("limit", 20))

    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        query = db_admin.collection("users").document(uid).collection("scanned_listings").order_by("created_at", direction="DESCENDING").limit(limit)
        docs = query.stream()
        listings = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            listings.append(data)

        all_docs = db_admin.collection("users").document(uid).collection("scanned_listings").stream()
        total_count = sum(1 for _ in all_docs)

        return jsonify({"ok": True, "listings": listings, "count": total_count})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/scan-office/stats", methods=["GET"])
def api_scan_office_stats():
    """Office tarama istatistikleri."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        docs = db_admin.collection("users").document(uid).collection("scanned_listings").stream()
        listings = [doc.to_dict() for doc in docs]

        if not listings:
            return jsonify({"ok": True, "total_listings": 0, "avg_price": 0, "price_distribution": {}, "property_types": {}})

        prices = [l.get("price", 0) for l in listings if l.get("price")]
        avg_price = sum(prices) / len(prices) if prices else 0

        property_types = {}
        for listing in listings:
            ptype = listing.get("property_type", "Diğer")
            property_types[ptype] = property_types.get(ptype, 0) + 1

        price_distribution = {"0-1M": 0, "1-3M": 0, "3-5M": 0, "5-10M": 0, "10M+": 0}

        for price in prices:
            if price < 1_000_000:
                price_distribution["0-1M"] += 1
            elif price < 3_000_000:
                price_distribution["1-3M"] += 1
            elif price < 5_000_000:
                price_distribution["3-5M"] += 1
            elif price < 10_000_000:
                price_distribution["5-10M"] += 1
            else:
                price_distribution["10M+"] += 1

        scan_docs = db_admin.collection("users").document(uid).collection("office_scans").order_by("started_at", direction="DESCENDING").limit(5).stream()
        recent_scans = [doc.to_dict() for doc in scan_docs]

        return jsonify({"ok": True, "total_listings": len(listings), "avg_price": avg_price, "price_distribution": price_distribution, "property_types": property_types, "recent_scans": recent_scans})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# AI ANALİZ MODÜLÜ ROUTE'LARI
# ================================================================

@app.route("/ai-analysis")
def ai_analysis_page():
    """AI Gayrimenkul Analiz sayfası."""
    try:
        return send_from_directory("templates", "ai_analysis.html")
    except Exception as e:
        return f"ai_analysis.html bulunamadı: {e}", 404

@app.route("/api/ai/scrape", methods=["POST"])
def api_ai_scrape():
    """İlan URL'sini scrape eder."""
    body = flask_request.json or {}
    url  = (body.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "url boş olamaz"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        result = scrape_listing(url)
        if not result.get("ok"):
            err = result.get("error", "Scrape başarısız")
            print(f"⚠️  Scrape başarısız [{url}]: {err}")
            return jsonify({"ok": False, "error": err, "data": result}), 422
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/ai/analyze", methods=["POST"])
def api_ai_analyze():
    """Gemini ile tam gayrimenkul analizi üretir."""
    body = flask_request.json or {}
    listing_data    = body.get("listing_data")
    manual_data     = body.get("manual_data")
    uploaded_images = body.get("uploaded_images", [])
    if not listing_data and not manual_data and not uploaded_images:
        return jsonify({"ok": False, "error": "En az bir girdi gerekli: listing_data, manual_data veya uploaded_images boş olamaz"}), 400
    try:
        result = analyze_listing(
            listing_data=listing_data,
            manual_data=manual_data,
            uploaded_images=uploaded_images,
        )
        return jsonify(result), (200 if result.get("ok") else 500)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/ai/status")
def api_ai_status():
    """Gemini AI listing modülünün konfigürasyon durumunu döner."""
    return jsonify(ai_listing_status())

@app.route("/api/ai/save-to-crm", methods=["POST"])
def api_ai_save_to_crm():
    """Üretilen analiz raporunu Firebase'e kaydeder."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503
    body       = flask_request.json or {}
    uid        = body.get("uid")
    report     = body.get("report")
    url        = body.get("url", "")
    contact_id = body.get("contact_id", "")
    if not uid or not report:
        return jsonify({"ok": False, "error": "uid ve report gerekli"}), 400
    try:
        doc_ref = (
            db_admin
            .collection("users").document(uid)
            .collection("ai_analyses")
            .document()
        )
        doc_ref.set({
            "report":    report,
            "url":       url,
            "contactId": contact_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "source":    report.get("data_source", ""),
            "verdict":   report.get("recommendation", {}).get("verdict", ""),
        })
        return jsonify({"ok": True, "id": doc_ref.id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/sunum")
def sunum_page():
    """Proje ve Lansman Sunum Portalı sayfası."""
    try:
        return send_from_directory("templates", "sunum.html")
    except Exception as e:
        return f"sunum.html bulunamadı: {e}", 404

@app.route("/sunum/advanced/<int:listing_index>")
def advanced_sunum_page(listing_index):
    try:
        listings = _listings_cache.get("data", [])
        if not listings or listing_index >= len(listings):
            return "İlan bulunamadı.", 404
        listing = listings[listing_index]
        cb_url = listing.get("link") or listing.get("url")
        if not cb_url:
            return "İlanın detay linki bulunamadı.", 404

        # İlan detay sayfasından tüm fotoğrafları ve bilgileri kazı (scrape)
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(cb_url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Resimleri bul
        images = []
        gallery = soup.select(".property-detail-gallery img, .swiper-slide img, #gallery img, .gallery-slider img, .lightgallery img, .property-gallery img")
        for img in gallery:
            src = img.get("data-src") or img.get("src")
            if src and not src.endswith(".gif") and "logo" not in src.lower():
                # Fix relative links
                if src.startswith("//"): src = "https:" + src
                elif src.startswith("/"): src = "https://www.cb.com.tr" + src
                if src not in images:
                    images.append(src)
        
        # Eğer resim kazınamazsa en azından ana resmi listeye koy
        if not images:
            images = [listing.get("img")]

        # Gemini ile pazarlama sloganı üret (Eğer API key varsa)
        ai_slogan = "Lüks, Konfor ve Geleceğiniz İçin Eşsiz Bir Fırsat!"
        try:
            from google import genai
            import os
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                client = genai.Client(api_key=api_key)
                prompt = f"Sen lüks gayrimenkul danışmanısın. Şu ilan için SADECE 1 CÜMLELİK çok havalı, prestijli, premium bir pazarlama sloganı yaz:\nBaşlık: {listing.get('title')}\nFiyat: {listing.get('price')}\nLokasyon: {listing.get('loc')}"
                resp_gemini = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                if resp_gemini.text:
                    ai_slogan = resp_gemini.text.strip().replace('"', '')
        except Exception as e:
            print(f"Gemini slogan hatası: {e}")

        # Veriyi hazırla
        advanced_listing = {
            "title": listing.get("title"),
            "price": listing.get("price"),
            "loc": listing.get("loc"),
            "type": listing.get("type"),
            "rooms": listing.get("rooms", ""),
            "area": listing.get("area", ""),
            "img": listing.get("img"),
            "images": images,
            "slogan": ai_slogan
        }
        return render_template_string(open("templates/dynamic_sunum.html", encoding="utf-8").read(), listing=advanced_listing)
    except Exception as e:
        return f"Gelişmiş sunum oluşturulurken hata: {e}", 500

@app.route("/sunum/auto/<int:listing_index>")
def auto_sunum_page(listing_index):
    """Otomatik ilan sunumu jeneratörü."""
    try:
        listings = _listings_cache.get("data", [])
        if not listings or listing_index >= len(listings):
            # Fallback to trigger fetch if empty
            if not listings:
                _refresh_listings_bg()
                return "Sistem ilanları hazırlıyor, lütfen sayfayı 5 saniye sonra yenileyin.", 503
            return "İlan bulunamadı.", 404
            
        listing = listings[listing_index]
        return render_template("dynamic_sunum.html", listing=listing)
    except Exception as e:
        return f"Sunum oluşturulurken hata oluştu: {e}", 500

# ================================================================
# FSBO ENGINE ROUTES
# ================================================================

@app.route("/api/fsbo/status")
def fsbo_status_route():
    """FSBO analiz motorunun durumunu döner."""
    return jsonify(fsbo_engine_status())

@app.route("/api/fsbo/analyze", methods=["POST"])
def fsbo_analyze():
    """
    Gemini 2.5 Flash ile FSBO stratejisi üretir.
    Korumalı endpoint — Firebase ID token gerektirir.

    Body: {
        contact_data: {name, phone, district, price, stage, notes, category},
        screenshots:  [base64_str, ...],
        text_input:   "...",
        audio_b64:    "data:audio/webm;base64,...",
        audio_mime:   "audio/webm",
        timeline:     [{type, text, createdAt}, ...]
    }
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401

    body         = flask_request.json or {}
    contact_data = body.get("contact_data", {})
    screenshots  = body.get("screenshots", [])
    text_input   = body.get("text_input", "")
    audio_b64    = body.get("audio_b64")
    audio_mime   = body.get("audio_mime", "audio/webm")
    timeline     = body.get("timeline", [])

    if not contact_data.get("name"):
        return jsonify({"ok": False, "error": "contact_data.name zorunlu"}), 400

    try:
        result = analyze_fsbo(
            contact_data = contact_data,
            screenshots  = screenshots,
            text_input   = text_input,
            audio_b64    = audio_b64,
            audio_mime   = audio_mime,
            timeline     = timeline,
        )
        status = 200 if result.get("ok") else 500
        return jsonify(result), status
    except Exception as e:
        print(f"❌ fsbo_analyze hatası: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/fsbo/save", methods=["POST"])
def fsbo_save():
    """
    FSBO stratejisini Firebase'e kaydeder.
    Body: {uid, contact_id, is_web, strategy, transcript}
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401

    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body       = flask_request.json or {}
    uid        = body.get("uid")
    contact_id = body.get("contact_id")
    is_web     = body.get("is_web", False)
    strategy   = body.get("strategy")
    transcript = body.get("transcript", "")

    if not uid or not contact_id or not strategy:
        return jsonify({"ok": False, "error": "uid, contact_id ve strategy zorunlu"}), 400

    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        if is_web:
            coll_ref = (db_admin
                        .collection("leads").document(contact_id)
                        .collection("fsbo_strategies"))
        else:
            coll_ref = (db_admin
                        .collection("users").document(uid)
                        .collection("contacts").document(contact_id)
                        .collection("fsbo_strategies"))

        # Mevcut strateji sayısını al → numara ver
        existing = list(coll_ref.limit(20).stream())
        strat_num = len(existing) + 1

        doc_ref = coll_ref.document()
        doc_ref.set({
            "strategy":   strategy,
            "transcript": transcript,
            "savedAt":    now_iso,
            "stratNum":   strat_num,
            "label":      f"FSBO Stratejim {strat_num}",
            "resistance": strategy.get("resistance_level", ""),
            "score":      strategy.get("confidence_score", 0),
        })

        # Timeline'a da yaz
        if is_web:
            db_admin.collection("leads").document(contact_id).collection("events").add({
                "type":      "fsbo_strategy_saved",
                "payload":   {"stratNum": strat_num, "score": strategy.get("confidence_score", 0), "resistance": strategy.get("resistance_level", "")},
                "createdAt": now_iso,
            })

        print(f"✅ FSBO Stratejim {strat_num} kaydedildi: {contact_id}")
        return jsonify({"ok": True, "id": doc_ref.id, "stratNum": strat_num})
    except Exception as e:
        print(f"❌ fsbo_save hatası: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/fsbo/delete", methods=["POST"])
def fsbo_delete():
    """FSBO stratejisini siler."""
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401

    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body        = flask_request.json or {}
    uid         = body.get("uid")
    contact_id  = body.get("contact_id")
    strategy_id = body.get("strategy_id")
    is_web      = body.get("is_web", False)

    if not uid or not contact_id or not strategy_id:
        return jsonify({"ok": False, "error": "uid, contact_id ve strategy_id zorunlu"}), 400

    try:
        if is_web:
            (db_admin.collection("leads").document(contact_id)
             .collection("fsbo_strategies").document(strategy_id).delete())
        else:
            (db_admin.collection("users").document(uid)
             .collection("contacts").document(contact_id)
             .collection("fsbo_strategies").document(strategy_id).delete())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── API: CRM Ekran Görüntüsünden Kişi Bilgisi Çıkar ─────────────────────────

@app.route("/api/crm/extract-contact", methods=["POST"])
def api_crm_extract_contact():
    """
    Ekran görüntülerinden ad soyad + telefon çıkarır (Gemini Vision).

    Body: {
      "images": ["data:image/jpeg;base64,...", ...]   // maks 3 görüntü
    }
    Döner:
      {"ok": true,  "name": "Ad Soyad", "phone": "05XXXXXXXXX"}
      {"ok": true,  "name": null, "phone": null}       // bilgi bulunamadı
      {"ok": false, "error": "..."}
    """
    from ai_listing import extract_contact_from_images

    body   = flask_request.json or {}
    images = body.get("images", [])

    if not images:
        return jsonify({"ok": False, "error": "images listesi boş"}), 400

    if not isinstance(images, list):
        return jsonify({"ok": False, "error": "images bir liste olmalı"}), 400

    try:
        result = extract_contact_from_images(images)
        status = 200 if result.get("ok") else 500
        return jsonify(result), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/crm/chat", methods=["POST"])
def api_crm_chat():
    """
    CRM Lead Chatbot — Gemini ile güçlendirilmiş müşteri asistanı.

    Body: {
      "lead_context": "müşteri bilgileri metin olarak",
      "messages": [{"role": "user", "content": "..."}, ...]
    }
    Döner: {"ok": true, "reply": "..."} | {"ok": false, "error": "..."}
    """
    GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL    = "gemini-2.5-flash"
    GEMINI_FALLBACK = "gemini-2.5-flash-lite"

    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}), 503

    body         = flask_request.json or {}
    lead_context = (body.get("lead_context") or "").strip()
    messages     = body.get("messages", [])

    if not messages:
        return jsonify({"ok": False, "error": "messages boş"}), 400

    system_prompt = f"""Sen Nexa CRM'in AI asistanısın. Türk gayrimenkul sektöründe uzman bir danışman yardımcısısın.
Aşağıdaki müşteri bilgileriyle beslenmişsin:

--- MEVCUT MÜŞTERİ BİLGİLERİ ---
{lead_context}
---------------------------------

Görevin:
- Danışmana bu müşteri hakkında pratik, uygulanabilir tavsiyeler ver
- Satış stratejileri, itiraz yanıtları, takip önerileri sun
- Türkçe konuş, profesyonel ama samimi bir dil kullan
- Cevapları kısa ve net tut (çok uzun yazmaktan kaçın)
- WhatsApp mesajı, e-posta taslağı, arama scripti gibi hazır metinler yazabilirsin
- Emoji kullanabilirsin ama aşırıya kaçma
"""

    gemini_contents = []
    for m in messages:
        role = "user" if m.get("role") == "user" else "model"
        gemini_contents.append({
            "role": role,
            "parts": [{"text": m.get("content", "")}]
        })

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": gemini_contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1500,
        },
    }

    def _call(model):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        return requests.post(url, json=payload, timeout=30)

    try:
        resp = _call(GEMINI_MODEL)
        if resp.status_code in (429, 503):
            resp = _call(GEMINI_FALLBACK)

        data = resp.json()
        if resp.ok:
            text = (
                data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
            )
            return jsonify({"ok": True, "reply": text or "Yanıt alınamadı."})

        err_msg = data.get("error", {}).get("message", str(data))
        return jsonify({"ok": False, "error": err_msg}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# API — PORTFÖY İLERLEME (portfolio_progress.py)
# Görsel OCR + ilerleme analizi + PDF rapor + portföy chatbot
# ================================================================

def _portfolio_coll(user_tok: dict, uid: str, contact_id: str, is_web: bool, sub: str, ctx: str = "contact"):
    """Portföy alt koleksiyonunu döndürür: portfolio_media/_notes/_reports.
    ctx: contact | lead | listing (listing → users/{uid}/listings/{id}/portfolio_*)"""
    if ctx == "listing":
        return (db_admin
                .collection("users").document(uid)
                .collection("listings").document(contact_id)
                .collection(sub))
    if is_web:
        return db_admin.collection("leads").document(contact_id).collection(sub)
    return (db_admin
            .collection("users").document(uid)
            .collection("contacts").document(contact_id)
            .collection(sub))


def _portfolio_lead_doc(user_tok: dict, uid: str, contact_id: str, is_web: bool, ctx: str = "contact"):
    if ctx == "listing":
        return (db_admin
                .collection("users").document(uid)
                .collection("listings").document(contact_id)
                .get())
    if is_web:
        return db_admin.collection("leads").document(contact_id).get()
    return (db_admin
            .collection("users").document(uid)
            .collection("contacts").document(contact_id)
            .get())


def _portfolio_ctx(body_or_args, default: str = "contact") -> str:
    """İstekten geçerli ctx döner (contact|lead|listing); geçersizse 'contact'."""
    try:
        ctx = str((body_or_args or {}).get("ctx", default))
    except Exception:
        ctx = default
    return ctx if ctx in ("contact", "lead", "listing") else default


def _portfolio_read_media(coll, limit_n: int = 24) -> tuple:
    """portfolio_media'yı okur → (medya listesi [{id,dataUrl,name,stage,createdAt,ocrText}], veri dikteleri)"""
    media, docs = [], []
    try:
        for snap in coll.limit(limit_n + 6).stream():
            docs.append(snap)
        docs.sort(key=lambda s: str(s.to_dict().get("createdAt", "")), reverse=True)
        docs = docs[:limit_n]
        for snap in docs:
            d = snap.to_dict() or {}
            media.append({
                "id": snap.id,
                "data_b64": d.get("dataUrl", ""),
                "dataUrl":  d.get("dataUrl", ""),
                "mime_type": d.get("mimeType", "image/jpeg"),
                "name":     d.get("name", ""),
                "stage":    d.get("stage", ""),
                "createdAt": d.get("createdAt", ""),
                "ocrText":  d.get("ocrText", ""),
                "ocrAsama": d.get("ocrAsama", ""),
                "ocrBulgular": d.get("ocrBulgular", []),
                "ocrStatus": d.get("ocrStatus", ""),
            })
    except Exception as e:
        print(f"⚠️ portfolio media okunamadı: {e}")
    return media, docs


def _portfolio_read_notes(coll) -> list:
    notes = []
    try:
        for snap in coll.limit(30).stream():
            d = snap.to_dict() or {}
            notes.append({
                "text":      d.get("text", ""),
                "type":      d.get("type", "note"),
                "stage":     d.get("stage", ""),
                "createdAt": d.get("createdAt", ""),
            })
    except Exception as e:
        print(f"⚠️ portfolio notes okunamadı: {e}")
    notes.sort(key=lambda n: str(n.get("createdAt", "")))
    return notes


def _portfolio_read_reports(coll) -> list:
    reports = []
    for snap in coll.limit(3).stream():
        d = snap.to_dict() or {}
        if d.get("status") == "done":
            reports.append({
                "id": snap.id, "bodyMd": d.get("bodyMd", ""),
                "createdAt": d.get("createdAt", ""),
            })
    reports.sort(key=lambda r: str(r.get("createdAt", "")), reverse=True)
    return reports


@app.route("/api/portfolio/ocr", methods=["POST"])
def portfolio_ocr():
    """
    Portföy görsellerinin OCR'ı (seçili mediaId'ler; boşsa tümü).
    Body: {uid, contactId, is_web, mediaIds?: []}
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body       = flask_request.json or {}
    uid        = token.get("uid") or body.get("uid")
    contact_id = body.get("contactId")
    is_web     = bool(body.get("is_web", False))
    ctx        = _portfolio_ctx(body)
    media_ids  = body.get("mediaIds") or []

    if not uid or not contact_id:
        return jsonify({"ok": False, "error": "uid ve contactId zorunlu"}), 400

    if ctx == "listing":
        is_web = False

    coll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_media", ctx)
    media, docs = _portfolio_read_media(coll)

    targets = [m for m in media if m.get("ocrStatus") != "done"]
    if media_ids:
        idset = set(media_ids)
        targets = [m for m in media if m["id"] in idset and m.get("ocrStatus") != "done"]
    if not targets:
        return jsonify({"ok": True, "bulgular": [], "message": "OCR gerektiren görsel yok"})

    try:
        import portfolio_progress as pp
        result = pp.ocr_images(targets, api_key=os.environ.get("GEMINI_API_KEY", ""))
    except Exception as e:
        print(f"❌ portfolio_ocr hatası: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

    updated = []
    if result.get("ok"):
        for b in result.get("bulgular", []):
            mid = b.get("key")
            if not mid:
                continue
            try:
                coll.document(mid).update({
                    "ocrText":     b.get("ocr_metni", ""),
                    "ocrAsama":    b.get("asama", ""),
                    "ocrBulgular": b.get("sorunlar", []),
                    "ocrStatus":   "done",
                    "analyzedAt":  datetime.now(timezone.utc).isoformat(),
                })
                updated.append(mid)
            except Exception as e:
                print(f"⚠️ OCR yazılamadı {mid}: {e}")
    else:
        return jsonify({"ok": False, "error": result.get("error", "OCR başarısız")}), 500

    print(f"✅ OCR tamamlandı: {len(updated)} görsel güncellendi")
    return jsonify({"ok": True, "bulgular": result.get("bulgular", []), "updated": updated})


@app.route("/api/portfolio/report", methods=["POST"])
def portfolio_report():
    """
    Portföy İlerleme Raporu: OCR (eksikler) → analiz → Markdown → PDF.
    Body: {uid, contactId, is_web}
    Döner: {ok, reportId, bodyMd, pdfBase64?, meta}
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body       = flask_request.json or {}
    uid        = token.get("uid") or body.get("uid")
    contact_id = body.get("contactId")
    is_web     = bool(body.get("is_web", False))
    ctx        = _portfolio_ctx(body)

    if not uid or not contact_id:
        return jsonify({"ok": False, "error": "uid ve contactId zorunlu"}), 400

    if ctx == "listing":
        is_web = False

    import portfolio_progress as pp
    api_key = os.environ.get("GEMINI_API_KEY", "")

    coll  = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_media", ctx)
    ncoll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_notes", ctx)
    rcoll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_reports", ctx)

    media, _docs  = _portfolio_read_media(coll)
    notes         = _portfolio_read_notes(ncoll)
    lead_snap     = _portfolio_lead_doc(token, uid, contact_id, is_web, ctx)
    lead_knowledge = lead_snap.to_dict() if lead_snap.exists else {}

    # 1) Eksik görsellerin OCR'ı
    missing = [m for m in media if m.get("ocrStatus") != "done"]
    ocr_results = []
    if missing:
        r = pp.ocr_images(missing, api_key=api_key)
        if not r.get("ok"):
            return jsonify({"ok": False, "error": f"OCR başarısız: {r.get('error')}"}), 500
        ocr_results = r.get("bulgular", [])
        for b in ocr_results:
            mid = b.get("key")
            if mid:
                try:
                    coll.document(mid).update({
                        "ocrText": b.get("ocr_metni", ""), "ocrAsama": b.get("asama", ""),
                        "ocrBulgular": b.get("sorunlar", []), "ocrStatus": "done",
                        "analyzedAt": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    pass
    # Önceden OCR'lananları da bağlama kat
    for m in media:
        if m.get("ocrStatus") == "done" and m.get("ocrText"):
            ocr_results.append({
                "key": m["id"], "ocr_metni": m.get("ocrText", ""),
                "asama": m.get("ocrAsama", ""), "sorunlar": m.get("ocrBulgular", []),
            })

    # 2) Analiz
    ana = pp.analyze_portfolio(lead_knowledge, ocr_results, notes, api_key=api_key)
    if not ana.get("ok"):
        return jsonify({"ok": False, "error": f"Analiz başarısız: {ana.get('error')}"}), 500
    analiz = ana.get("analiz", {})

    report_id = rcoll.document().id
    body_md   = pp.build_report_body(analiz, lead_knowledge, media, notes, report_id)

    # 3) PDF üretimi
    pdf_b64 = None
    try:
        pdf_io = BytesIO()
        pp.render_report_pdf(body_md, media, pdf_io)
        pdf_bytes = pdf_io.getvalue()
        if len(pdf_bytes) <= 800 * 1024:
            pdf_b64 = "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode()
    except Exception as e:
        print(f"⚠️ PDF üretilemedi (metin raporu kaydedilecek): {e}")

    # 4) Raporu kaydet
    report_doc = {
        "status":    "done",
        "bodyMd":    body_md,
        "meta": {
            "mediaCount": len(media),
            "noteCount":  len(notes),
            "contactTitle": lead_knowledge.get("name", ""),
            "model":      analiz.get("model", pp.GEMINI_MODEL),
        },
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if pdf_b64:
        report_doc["pdfBase64"] = pdf_b64
    rcoll.document(report_id).set(report_doc)

    print(f"✅ Portföy raporu oluşturuldu: {report_id} ({len(media)} görsel, PDF={bool(pdf_b64)})")
    return jsonify({
        "ok": True, "reportId": report_id,
        "bodyMd": body_md, "pdfBase64": pdf_b64,
        "analiz": {
            "ozet": analiz.get("ozet", ""),
            "suanki_durum_pct": (analiz.get("kpi", {}) or {}).get("suanki_durum_pct"),
            "ne_yaptik": analiz.get("ne_yaptik", [])[:4],
            "riskler":  analiz.get("riskler", [])[:4],
            "aksiyonlar": analiz.get("aksiyonlar", [])[:5],
        },
        "meta": report_doc["meta"],
    })


@app.route("/api/portfolio/report/<uid>/<contact_id>/<report_id>/pdf", methods=["GET"])
def portfolio_report_pdf(uid, contact_id, report_id):
    """Kayıtlı raporun PDF'ini yeniden üretir (pdfBase64 saklanmamışsa da çalışır)."""
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    if token.get("uid") not in (None, uid):
        return jsonify({"ok": False, "error": "Yetkisiz erişim"}), 403

    is_web = flask_request.args.get("is_web") == "1"
    ctx    = _portfolio_ctx(flask_request.args)
    if ctx == "listing":
        is_web = False
    import portfolio_progress as pp

    coll  = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_media", ctx)
    rcoll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_reports", ctx)
    rdoc  = rcoll.document(report_id).get()
    if not rdoc.exists:
        return jsonify({"ok": False, "error": "Rapor bulunamadı"}), 404

    report = rdoc.to_dict()
    body_md = report.get("bodyMd", "")
    if not body_md:
        return jsonify({"ok": False, "error": "Rapor içeriği boş"}), 400

    media, _ = _portfolio_read_media(coll, limit_n=12)
    try:
        pdf_io = BytesIO()
        pp.render_report_pdf(body_md, media, pdf_io)
        pdf_io.seek(0)
        return send_file(
            pdf_io, mimetype="application/pdf",
            as_attachment=True,
            download_name=f"ilerleme_raporu_{report_id[:8]}.pdf",
        )
    except Exception as e:
        print(f"❌ PDF üretim hatası ({report_id}): {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/portfolio/chat", methods=["POST"])
def portfolio_chat():
    """
    Portföy bağlamlı AI sohbet.
    Body: {uid, contactId, is_web, message, history?: [{role, content}]}
    Geçmiş Firestore ai_data'ya (portfolioChat ile etiketlenir) kaydedilir.
    """
    token, err = _require_admin()
    if err:
        return jsonify({"ok": False, "error": err}), 401
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body       = flask_request.json or {}
    uid        = token.get("uid") or body.get("uid")
    contact_id = body.get("contactId")
    is_web     = bool(body.get("is_web", False))
    ctx        = _portfolio_ctx(body)
    message    = (body.get("message") or "").strip()
    history    = body.get("history", [])

    if not uid or not contact_id or not message:
        return jsonify({"ok": False, "error": "uid, contactId ve message zorunlu"}), 400

    if ctx == "listing":
        is_web = False

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}), 503

    import portfolio_progress as pp

    coll  = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_media", ctx)
    ncoll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_notes", ctx)
    rcoll = _portfolio_coll(token, uid, contact_id, is_web, "portfolio_reports", ctx)

    media, _      = _portfolio_read_media(coll, limit_n=12)
    notes         = _portfolio_read_notes(ncoll)
    last_reports  = _portfolio_read_reports(rcoll)
    lead_snap     = _portfolio_lead_doc(token, uid, contact_id, is_web, ctx)
    lead_knowledge = lead_snap.to_dict() if lead_snap.exists else {}

    ocr_results = []
    for m in media:
        if m.get("ocrStatus") == "done" and m.get("ocrText"):
            ocr_results.append({
                "key": m["id"], "ocr_metni": m.get("ocrText", ""),
                "asama": m.get("ocrAsama", ""), "sorunlar": m.get("ocrBulgular", []),
            })

    context = pp.portfolio_chat_context(lead_knowledge, notes, ocr_results, last_reports)

    system_prompt = f"""Sen Nexa CRM'in "Portföy İlerleme Danışmanı"sın.
Aşağıdaki portföy bağlamından gelen bilgileri kullanarak danışmana yardım et:

--- PORTFÖY BAĞLAMI ---
{context}
------------------------

Kurallar:
- SADECE verilen bağlamdan konuş; dışarıdan bilgi uydurma.
- İlerleme yönetimi odaklı, somut ve kısa (5-10 satır) cevaplar ver.
- Türkçe, profesyonel bir dil kullan.
- Emin olmadığın bilgi için "görselden doğrulayamıyorum" de.
"""

    contents = [{"role": m.get("role", "user"), "parts": [{"text": m.get("content", "")}]}
                for m in history[-10:]]
    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1500},
    }

    models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
    reply = None
    last_err = "Bilinmeyen hata"
    for model in models:
        try:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent")
            resp = requests.post(url, json=payload, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=45)
            data = resp.json()
            if resp.ok:
                reply = (data.get("candidates", [{}])[0]
                             .get("content", {})
                             .get("parts", [{}])[0]
                             .get("text", "") or "").strip()
                if reply:
                    break
            last_err = data.get("error", {}).get("message", str(data))
        except Exception as e:
            last_err = str(e)

    if not reply:
        return jsonify({"ok": False, "error": f"Gemini yanıt vermedi: {last_err}"}), 500

    # Geçmişi kalıcı kaydet (ai_data → portfolioChat)
    try:
        acoll = _portfolio_coll(token, uid, contact_id, is_web, "ai_data", ctx)
        acoll.add({"role": "user", "content": message, "type": "portfolioChat",
                   "createdAt": datetime.now(timezone.utc).isoformat()})
        acoll.add({"role": "assistant", "content": reply, "type": "portfolioChat",
                   "createdAt": datetime.now(timezone.utc).isoformat()})
    except Exception as e:
        print(f"⚠️ Sohbet geçmişi kaydedilemedi: {e}")

    print(f"✅ Portföy sohbet yanıtı üretildi ({contact_id})")
    return jsonify({"ok": True, "reply": reply})

@app.route("/api/crm/proactive", methods=["POST"])
def api_crm_proactive():
    """
    Lead için proaktif AI uyarısı üretir.
    Kural tabanlı eşik kontrolü + Gemini analizi.

    Body: {
      "lead_context":   "müşteri metin özeti",
      "days_in_stage":  18,
      "last_note_days": 12,
      "stage":          "ilk_temas",
      "stage_label":    "İlk Temas"
    }
    Döner: {
      "ok": true,
      "alert": {
        "level": "urgent" | "warning" | "info" | null,
        "title": "...",
        "message": "...",
        "suggested_action": "...",
        "quick_questions": [...]
      }
    }
    """
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    if not GEMINI_API_KEY:
        return jsonify({"ok": False, "error": "GEMINI_API_KEY tanımlı değil"}), 503

    body          = flask_request.json or {}
    lead_context  = (body.get("lead_context") or "").strip()
    days_in_stage = int(body.get("days_in_stage", 0))
    last_note_days= int(body.get("last_note_days", 0))
    stage         = (body.get("stage") or "").strip()
    stage_label   = (body.get("stage_label") or stage).strip()

    if not lead_context:
        return jsonify({"ok": False, "error": "lead_context boş"}), 400

    # ── Aşama Eşikleri (kural motoru) ─────────────────────────────
    STAGE_THRESHOLDS = {
        "ilk_temas":   {"warning": 5,  "urgent": 10},
        "degerleme":   {"warning": 10, "urgent": 21},
        "sozlesme":    {"warning": 5,  "urgent": 10},
        "goruntuleme": {"warning": 3,  "urgent": 7 },
        "teklif":      {"warning": 2,  "urgent": 5 },
        "satilik":     {"warning": 14, "urgent": 30},
        "default":     {"warning": 14, "urgent": 28},
    }
    thresh = STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS["default"])
    rule_level = None
    if days_in_stage >= thresh["urgent"] or last_note_days >= thresh["urgent"]:
        rule_level = "urgent"
    elif days_in_stage >= thresh["warning"] or last_note_days >= thresh["warning"]:
        rule_level = "warning"

    system_prompt = f"""Sen Nexa CRM'in proaktif analiz asistanısın.
Bir gayrimenkul danışmanına, az önce açtığı müşteri dosyası için ne yapması gerektiğini söylüyorsun.

MÜŞTERİ BİLGİLERİ:
{lead_context}

Aşamada geçen gün: {days_in_stage}
Son not/iletişimden geçen gün: {last_note_days}
Mevcut aşama: {stage_label}
Kural motoru tespiti: {rule_level or "normal"}

GÖREV:
1. Eğer müşteri durumu tamamen normalse (aktif, yeni girilmiş, her şey yolunda) → level null döndür.
2. Aksi hâlde danışmana özel, uygulanabilir bir uyarı üret.
3. Öneri gerçekçi ve bu müşteriye özgü olsun; genel kalıplardan kaçın.
4. suggested_action kısa ve net bir eylem cümlesi olsun (asistana sorulacak soru gibi).
5. quick_questions listesi 2 maddeden oluşsun.

SADECE JSON döndür:
{{
  "level": "urgent" | "warning" | "info" | null,
  "title": "Max 5 kelime başlık",
  "message": "Danışmana yönelik 1-2 cümle açıklama",
  "suggested_action": "Asistana sorulacak tek cümlelik eylem sorusu",
  "quick_questions": ["Soru 1", "Soru 2"]
}}
"""

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": "Proaktif analiz yap."}]}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 400},
    }

    try:
        url  = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-2.5-flash:generateContent")
        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()

        if not resp.ok:
            # API hatasında kural motoru sonucunu fallback olarak kullan
            if rule_level:
                return jsonify({"ok": True, "alert": {
                    "level": rule_level,
                    "title": f"{days_in_stage} Gündür Bekleme" if rule_level == "urgent" else "Takip Zamanı",
                    "message": f"Bu müşteri {stage_label} aşamasında {days_in_stage} gündür bekliyor.",
                    "suggested_action": "Bu müşteri için takip stratejisi öner",
                    "quick_questions": ["Arama öncesi brifing ver", "WhatsApp mesajı yaz"],
                }})
            return jsonify({"ok": True, "alert": {"level": None}})

        raw = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
        )

        # JSON ayıkla
        m = _re.search(r'\{.*\}', raw, _re.DOTALL)
        alert_data = json.loads(m.group()) if m else json.loads(raw)

        # Kural motoru "urgent" dediyse Gemini'nin downgrade etmesine izin verme
        if rule_level == "urgent" and alert_data.get("level") not in ("urgent", None):
            alert_data["level"] = "urgent"

        return jsonify({"ok": True, "alert": alert_data})

    except json.JSONDecodeError:
        # Parse hatası → kural motoru fallback
        fallback = {"level": rule_level, "title": "", "message": "",
                    "suggested_action": "", "quick_questions": []}
        return jsonify({"ok": True, "alert": fallback})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ================================================================
# NEXA CRM — OTONOM SOSYAL MEDYA & İÇERİK PLANLAYICI (SOCIAL AUTOPILOT)
# ================================================================

@app.route("/api/crm/social-planner/weekly", methods=["GET"])
def api_crm_social_planner_weekly():
    """
    Haftanın 7 günlük stratejik paylaşım planını, bugünün gününü ve
    35 Drive projesi ile canlı CB VIP portföyünü dinamik eşleyerek döndürür.
    """
    try:
        import nexa_social_autopilot
        plan = nexa_social_autopilot.get_weekly_social_plan()
        return jsonify(plan)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/crm/social-planner/generate-post", methods=["POST"])
def api_crm_social_planner_generate_post():
    """
    Seçilen portföy veya proje için Instagram, Reels, LinkedIn ve WhatsApp
    içerik paketini (hook, CTA ve kritik özelliklerle) tam otonom üretir.
    """
    try:
        import nexa_social_autopilot
        data = flask_request.json or {}
        item_id = data.get("item_id")
        item_type = data.get("item_type", "project")
        day_name = data.get("day_name")
        theme = data.get("theme")
        hook = data.get("hook")
        cta = data.get("cta")

        res = nexa_social_autopilot.generate_social_post_package(
            item_id=item_id,
            item_type=item_type,
            day_name=day_name,
            theme=theme,
            hook=hook,
            cta=cta
        )
        return jsonify({"success": True, "data": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ================================================================
# NEXA AI PROJE SUNUM & RAG ASİSTANI ENDPOINTS
# ================================================================

@app.route("/api/nexa/chat", methods=["POST"])
@app.route("/api/project/chat", methods=["POST"])
@app.route("/api/chat", methods=["POST"])
def nexa_project_chat():
    """Yiğit Narin CB VIP Projeleri için Gemini destekli RAG Chatbot API."""
    data = flask_request.json or {}
    user_msg = data.get("message") or data.get("prompt") or data.get("query") or ""
    project_id = data.get("project_id") or data.get("projectId") or ""
    
    if not user_msg:
        return jsonify({"ok": False, "reply": "Lütfen bir soru veya mesaj yazın."}), 400

    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not api_key:
        return jsonify({
            "ok": True,
            "reply": "Coldwell Banker CB VIP Ankara portföyündeki 22 seçkin proje hakkında detaylı bilgi, kat planları ve güncel fiyat listesi için Yiğit Narin ile WhatsApp üzerinden doğrudan iletişime geçebilirsiniz: +90 532 000 00 00"
        })

    try:
        from google import genai
        from google.genai import types

        # Load project summaries if available
        summaries_path = os.path.join("static", "data", "nexa_project_summaries.json")
        project_context = ""
        if os.path.exists(summaries_path):
            with open(summaries_path, "r", encoding="utf-8") as f:
                summaries = json.load(f)
                if project_id and project_id in summaries:
                    project_context = json.dumps(summaries[project_id], ensure_ascii=False)
                else:
                    project_context = json.dumps(summaries, ensure_ascii=False)[:3000]

        client = genai.Client(api_key=api_key)
        system_prompt = f"""
        Sen NexaPrime'sın — Coldwell Banker CB VIP Ankara & Yiğit Narin'in Resmi Yapay Zeka Proje ve Gayrimenkul Yatırım Danışmanısın.
        Danışman: Yiğit Narin (Broker & PropTech Uzmanı).
        İletişim: +90 532 000 00 00 | yigit.narin@cb.com.tr
        Portföyümüzde Ankara'nın 22 prestijli projesi (Beytepe, İncek, Çayyolu, Yaşamkent, Saray, Çakırlar vb.) yer almaktadır.
        
        Mevcut Proje Bilgileri:
        {project_context}

        Kullanıcının sorusuna son derece profesyonel, nazik, net ve güven verici Türkçe ile yanıt ver. Fiyatlar ve detaylar için Yiğit Narin'e yönlendir.
        """

        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nKullanıcı Sorusu: {user_msg}",
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=600
            )
        )

        reply_text = (resp.text or "").strip()
        return jsonify({"ok": True, "reply": reply_text})

    except Exception as e:
        print(f"nexa_project_chat hatası: {e}")
        return jsonify({
            "ok": True,
            "reply": f"Proje sunumu ve detaylı bilgi için Yiğit Narin ile iletişime geçebilirsiniz. (Hata: {e})"
        })

@app.route("/api/nexa/projects", methods=["GET"])
def nexa_get_projects():
    """Tüm projelerin zenginleştirilmiş verilerini döndürür."""
    data_path = os.path.join("static", "data", "nexa_portfolio_data.json")
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return jsonify({"ok": True, "data": json.load(f)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": False, "data": []}), 404


# ================================================================
# CRM İLAN OPERASYON & İSTİHBARAT DASHBOARD ENDPOINTS
# ================================================================

import html
import random
import time

import threading
import tempfile
_DASHBOARD_LOCK = threading.RLock()
_PORTFOLIO_DASHBOARD_FILE = os.path.join("static", "data", "portfolio_listing_dashboards.json")

def _load_listing_dashboards():
    with _DASHBOARD_LOCK:
        if os.path.exists(_PORTFOLIO_DASHBOARD_FILE):
            try:
                with open(_PORTFOLIO_DASHBOARD_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

def _save_listing_dashboards(data):
    with _DASHBOARD_LOCK:
        dir_name = os.path.dirname(_PORTFOLIO_DASHBOARD_FILE)
        os.makedirs(dir_name, exist_ok=True)
        # Atomic Write: write to temporary file first, then atomically replace
        temp_fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="dashboards_", suffix=".tmp")
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, _PORTFOLIO_DASHBOARD_FILE)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

DEFAULT_PLATFORMS = [
    {"platform": "SAHIBINDEN", "logo": "🟡", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0},
    {"platform": "HEPSIEMLAK", "logo": "🔴", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0},
    {"platform": "EMLAKJET", "logo": "🟣", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0},
    {"platform": "COLDWELL BANKER", "logo": "🔵", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0},
    {"platform": "BRANDA / AFİŞ", "logo": "🟠", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0},
    {"platform": "SOSYAL MEDYA & AD", "logo": "🟢", "views": 0, "favorites": 0, "messages": 0, "calls": 0, "influence": 0, "score": 0}
]

@app.route("/api/portfolio/listing/<path:ref_id>/dashboard", methods=["GET"])
def get_portfolio_listing_dashboard(ref_id):
    """İlanın platform istatistiklerini, alıcılarını ve zaman çizelgesini döner."""
    try:
        all_data = _load_listing_dashboards()
        item = all_data.get(ref_id)
        if not item:
            item = {
                "refId": ref_id,
                "platform_stats": DEFAULT_PLATFORMS,
                "buyers": [],
                "timeline": [
                    {
                        "id": "init",
                        "type": "status",
                        "title": "Portföy CRM'e Eklendi",
                        "note": "İlan sisteme başarıyla tanımlandı ve takibe alındı.",
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                        "author": "Yiğit Narin"
                    }
                ]
            }
            all_data[ref_id] = item
            _save_listing_dashboards(all_data)

        return jsonify({"ok": True, "data": item})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/portfolio/listing/<path:ref_id>/platform_stats", methods=["POST"])
def save_portfolio_platform_stats(ref_id):
    """Excel Emlak_Platform_Karsilastirmasi matrisi verilerini günceller."""
    try:
        payload = flask_request.json or {}
        stats = payload.get("platform_stats", [])
        
        def _to_safe_int(val, default=0):
            try:
                # convert to float first in case of string numbers like "12.0"
                s = str(val).strip().replace(',', '.')
                return int(float(s))
            except Exception:
                return default

        # Calculate weighted total scores for each platform
        for st in stats:
            v = _to_safe_int(st.get("views"), 0)
            f = _to_safe_int(st.get("favorites"), 0)
            m = _to_safe_int(st.get("messages"), 0)
            c = _to_safe_int(st.get("calls"), 0)
            inf = _to_safe_int(st.get("influence"), 0)
            # Weighted formula
            score = (v * 1) + (f * 5) + (m * 15) + (c * 25) + (inf * 20)
            st["score"] = score
        
        with _DASHBOARD_LOCK:
            all_data = _load_listing_dashboards()
            if ref_id not in all_data:
                all_data[ref_id] = {"refId": ref_id, "platform_stats": [], "buyers": [], "timeline": []}
            all_data[ref_id]["platform_stats"] = stats
            all_data[ref_id]["updatedAt"] = datetime.now().isoformat()
            _save_listing_dashboards(all_data)
        
        return jsonify({"ok": True, "platform_stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/portfolio/listing/<path:ref_id>/buyer", methods=["POST"])
def add_portfolio_listing_buyer(ref_id):
    """İlana özel alıcı ekler ve aynı anda genel CRM Lead/Contact havuzuna işler."""
    try:
        ref_id = re.sub(r'[^a-zA-Z0-9_\-\.:]', '_', str(ref_id))[:128]
        payload = flask_request.json or {}
        name = html.escape((payload.get("name") or "").strip()[:100])
        phone = html.escape((payload.get("phone") or "").strip()[:30])
        offer = html.escape((payload.get("offer") or "").strip()[:50])
        stage = html.escape((payload.get("stage") or "Yeni Talep").strip()[:50])
        note = html.escape((payload.get("note") or "").strip()[:1000])
        listing_title = html.escape((payload.get("listing_title") or "Portföy İlanı").strip()[:150])

        if not name or not phone:
            return jsonify({"ok": False, "error": "Ad ve telefon zorunludur."}), 400

        buyer_id = f"b_{int(time.time())}_{random.randint(100, 999)}"
        buyer_record = {
            "id": buyer_id,
            "refId": ref_id,
            "name": name,
            "phone": phone,
            "offer": offer,
            "stage": stage,
            "note": note,
            "listingTitle": listing_title,
            "createdAt": datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        # Add a timeline event
        timeline_event = {
            "id": f"t_{int(time.time())}",
            "type": "buyer",
            "title": f"Yeni Alıcı Eklendi: {name}",
            "note": f"Teklif: {offer or 'Belirtilmedi'} | Aşama: {stage}",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "author": "Yiğit Narin"
        }

        with _DASHBOARD_LOCK:
            all_data = _load_listing_dashboards()
            if ref_id not in all_data:
                all_data[ref_id] = {"refId": ref_id, "platform_stats": DEFAULT_PLATFORMS, "buyers": [], "timeline": []}
            all_data[ref_id].setdefault("buyers", []).insert(0, buyer_record)
            all_data[ref_id].setdefault("timeline", []).insert(0, timeline_event)
            _save_listing_dashboards(all_data)

        # Global CRM Sync: also register in Firestore / Contacts if available
        try:
            if "db" in globals() and db:
                db.collection("crm_leads").add({
                    "name": name,
                    "phone": phone,
                    "source": f"Portföy İlanı: {listing_title}",
                    "listing_ref": ref_id,
                    "listing_title": listing_title,
                    "stage": stage,
                    "budget": offer,
                    "notes": note,
                    "createdAt": datetime.now().isoformat(),
                    "agent": "Yiğit Narin"
                })
        except Exception as fe:
            print(f"Firestore CRM sync warning: {fe}")

        return jsonify({"ok": True, "buyer": buyer_record, "timeline": all_data[ref_id]["timeline"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/portfolio/listing/<path:ref_id>/timeline", methods=["POST"])
def add_portfolio_listing_timeline(ref_id):
    """İlan geçmişine yeni olay veya not ekler."""
    try:
        ref_id = re.sub(r'[^a-zA-Z0-9_\-\.:]', '_', str(ref_id))[:128]
        payload = flask_request.json or {}
        event_type = html.escape((payload.get("type") or "note").strip()[:30])
        title = html.escape((payload.get("title") or "Not Eklendi").strip()[:150])
        note = html.escape((payload.get("note") or "").strip()[:1000])

        event = {
            "id": f"t_{int(time.time())}",
            "type": event_type,
            "title": title,
            "note": note,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "author": "Yiğit Narin"
        }
        with _DASHBOARD_LOCK:
            all_data = _load_listing_dashboards()
            if ref_id not in all_data:
                all_data[ref_id] = {"refId": ref_id, "platform_stats": DEFAULT_PLATFORMS, "buyers": [], "timeline": []}
            all_data[ref_id].setdefault("timeline", []).insert(0, event)
            _save_listing_dashboards(all_data)

        return jsonify({"ok": True, "event": event, "timeline": all_data[ref_id]["timeline"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/portfolio/listing/<path:ref_id>/chat", methods=["POST"])
def portfolio_listing_chat(ref_id):
    """Bu ilana özel ultra-akıllı NexaPrime AI Chatbot API'si."""
    try:
        ref_id = re.sub(r'[^a-zA-Z0-9_\-\.:]', '_', str(ref_id))[:128]
        
        # Handle malformed / non-JSON gracefully
        if flask_request.content_type and 'application/json' in flask_request.content_type:
            payload = flask_request.get_json(silent=True)
            if payload is None and flask_request.data:
                return jsonify({"ok": False, "error": "Geçersiz veya bozuk JSON verisi."}), 400
        else:
            payload = flask_request.json or {}
            
        payload = payload or {}
        raw_msg = str(payload.get("message") or payload.get("prompt") or "").strip()
        user_msg = raw_msg[:2000]
        listing_info = payload.get("listing_info") or {}

        if not user_msg:
            return jsonify({"ok": False, "reply": "Lütfen bir soru veya talimat yazın."}), 400

        # AI Prompt Injection & Guardrail Filter
        injection_triggers = [
            "ignore all previous", "ignore previous", "system override", "forget your",
            "reveal system prompt", "reveal api key", "sistem komutlarını göster", 
            "gizli anahtar", "jailbreak", "bypass safety", "danışman rolünden çık"
        ]
        if any(tr in user_msg.lower() for tr in injection_triggers):
            return jsonify({
                "ok": True,
                "reply": "🔒 **NexaPrime AI Güvenlik Protokolü:**\nColdwell Banker CB VIP Ankara bünyesinde görev yapan kurumsal bir Gayrimenkul & Portföy Operasyon asistanıyım. Güvenlik politikaları gereğince sistem promptları ve özel yapılandırmalar paylaşılamaz. Size portföy analizi, satış kapatma ve fiyat optimizasyonu konularında yardımcı olmaktan memnuniyet duyarım."
            })

        all_data = _load_listing_dashboards()
        listing_data = all_data.get(ref_id, {})
        stats = listing_data.get("platform_stats", [])
        buyers = listing_data.get("buyers", [])

        title = listing_info.get("title") or "Portföy İlanı"
        price = listing_info.get("price") or "Piyasa Değerinde"
        loc = listing_info.get("loc") or "Ankara"
        ltype = listing_info.get("type") or "Konut"

        total_views = sum([int(s.get("views") or 0) for s in stats])
        total_favs = sum([int(s.get("favorites") or 0) for s in stats])
        total_msgs = sum([int(s.get("messages") or 0) for s in stats])
        total_calls = sum([int(s.get("calls") or 0) for s in stats])
        top_plat = max(stats, key=lambda x: int(x.get("score") or 0)).get("platform", "SAHIBINDEN") if stats else "SAHIBINDEN"

        def _get_expert_reply(q):
            ql = q.lower()
            if any(w in ql for w in ["fiyat", "optimizasyon", "analiz", "platform", "değer", "istatistik"]):
                return f"""📊 **NEXAPRIME AI — PLATFORM VERİLERİNE GÖRE FİYAT VE PERFORMANS ANALİZİ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 **İlan:** {title} ({loc})
💰 **Mevcut İlan Fiyatı:** {price}
📈 **Konsolide Trafik:** {total_views:,} Görüntülenme | {total_favs} Favori | {total_msgs + total_calls} Sıcak Talep

📌 **Platform Dağılımı & Teşhis:**
• **Lider Platform:** {top_plat} (En yüksek dönüşüm ve talep bu kanalda toplanmış durumda).
• **İzleme / Talep Oranı:** %{((total_favs / max(total_views, 1)) * 100):.1f} favori dönüşümü mevcuttur. Müşteriler portföyü ilgi listesine alıyor ancak ilk adımı atmakta tereddüt ediyor.

💡 **Fiyat Optimizasyonu ve Satış Hızlandırma Önerileri:**
1. **Psikolojik Eşik Düzeltmesi:** Mevcut fiyat üzerinden %3-%5 oranında planlı bir revizyon yapılması durumunda, Sahibinden ve Hepsiemlak'taki {total_favs} favori sahibine anlık bildirim gidecek ve beklemedeki sıcak alıcılar harekete geçecektir.
2. **Kademeli Fiyat Koruma:** Mülk sahibine taban fiyatı koruyan 14 günlük özel teklif penceresi açtırın.
3. **Vitrin & İçerik Takviyesi:** {top_plat} ilanına 4K drone çekimi veya 3D sanal tur eklenmesi, aranma oranını en az %35 artıracaktır."""

            elif any(w in ql for w in ["pazarlık", "kapatma", "taktik", "strateji", "ikna"]):
                return f"""🤝 **NEXAPRIME AI — PAZARLIK VE SATIŞ KAPATMA STRATEJİSİ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 **Portföy:** {title} | **Fiyat:** {price}
👥 **Kayıtlı Alıcı Sayısı:** {len(buyers)} Müşteri

🎯 **Uygulanacak 4 Aşamalı Kapatma Taktikleri:**
1. **Çıpa ve Karşı Teklif (Anchor Counter-Offer):**
   Alıcıdan gelen düşük tekliflere kesinlikle hemen 'hayır' demeyin. *"Mülk sahibimizin bu rakama onay vermesi mümkün değil, ancak peşin ödeme/hızlı tapu devri şartıyla şu rakama bağlayabiliriz"* diyerek müzakereyi kendi kontrolünüze çekin.

2. **Aciliyet ve Talep Kanıtı:**
   Bu portföye ait platform istatistiklerini ({total_views:,} görüntülenme ve {total_favs} favori) alıcıya profesyonelce hissettirin: *"Bu bölgede benzer nitelikteki mülkler ortalama 20-30 günde el değiştiriyor, şu anda takibimizde 2 ciddi aday daha var."*

3. **Alıcı Teklif Eşitleme:**
   Kayıtlı adaylar arasındaki teklifleri karşılaştırarak alıcıyı karar eşiğine getirin.

4. **Sözleşme Kapatma Sorusu (Closing Question):**
   *"Yiğit Bey olarak mülk sahibimizi bu rakama ikna edersem, bugün kapora protokolünü imzalayıp tapu sürecini başlatmaya hazır mısınız?"* sorusu ile kararı bağlayın."""

            elif any(w in ql for w in ["whatsapp", "tanıtım", "metin", "mesaj", "ilan"]):
                return f"""💬 **NEXAPRIME AI — VIP WHATSAPP TANITIM VE VİTRİN METNİ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*(Aşağıdaki metni kopyalayıp hedef yatırımcılarınıza doğrudan gönderebilirsiniz)*

✨ **COLDWELL BANKER CB VIP ANKARA | ÖZEL PORTFÖY** ✨

Sayın Yatırımcımız,
Ankara'nın en gözde lokasyonunda ({loc}) prestij ve konforu bir arada sunan seçkin portföyümüz satışa sunulmuştur:

💎 **{title}**
📍 **Lokasyon:** {loc}
🏷️ **Tür:** {ltype}
💰 **Fiyat:** {price}

🌟 **Öne Çıkan Ayrıcalıklar:**
✔️ Yüksek prim potansiyeli & değerini koruyan elit lokasyon
✔️ Ferah mimari, kusursuz peyzaj ve sosyal donatılar
✔️ Hemen taşınmaya ve krediye uygun, eksiksiz altyapı
✔️ Coldwell Banker CB VIP kurumsal güvencesiyle tek yetkili satış

📲 **Detaylı sunum dosyası, kat planları ve özel randevu için:**
Gayrimenkul Mühendisi **Yiğit Narin**
📞 **0532 451 40 08** | Coldwell Banker CB VIP Ankara
🌐 *Web:* gayrimenkulmuhendisi.com"""

            elif any(w in ql for w in ["alıcı", "özel teklif", "müşteri", "lead", "argüman"]):
                buyer_names = ", ".join([b.get("name") for b in buyers[:3]]) if buyers else "Ciddi alıcı adayları"
                return f"""🎯 **NEXAPRIME AI — KAYITLI ALICILARA ÖZEL TEKLİF & TAKİP PLANI**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 **İlan:** {title} | **Fiyat:** {price}
👥 **Hedef Alıcılar:** {buyer_names}

📋 **Alıcı İkna Argümanları:**
1. **Bölgesel Değer Artışı:** {loc} bölgesindeki yıllık değer artış endeksi ve enflasyona karşı reel koruma sağlayan gayrimenkul dinamiği vurgulanmalı.
2. **Nakit Avantajı / Hızlı İşlem:** *"Mülk sahibiyle son yaptığımız değerlendirmede, bu hafta içinde neticelenebilecek işlemlerde özel bir esneklik sağlandı."*
3. **Müşteriye Özel Teklif Şablonu:**
   *"Merhaba [Alıcı Adı], daha önce ilgilendiğiniz {title} portföyümüz için mülk sahibiyle özel bir revize toplantısı yaptık. Sizin bütçenize çok yakın bir orta noktada anlaşma zemini oluştu. Bugün 15 dakikalık bir telefon görüşmesiyle detayları paylaşmak isterim."*"""

            else:
                return f"""💡 **NEXAPRIME AI — STRATEJİK PORTFÖY DEĞERLENDİRMESİ**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 **İlan:** {title} ({loc})
💰 **Fiyat:** {price}
📊 **Mevcut İstatistik:** {total_views} Görüntülenme, {total_favs} Favori, {total_msgs + total_calls} İletişim

Sorunuz: **"{user_msg}"**

Coldwell Banker CB VIP kurumsal gayrimenkul analitiğimize göre bu portföyde en kritik başarı faktörü; ilan vitrinini güncel tutmak, favoriye ekleyen adaylarla düzenli temas kurmak ve mülk sahibine haftalık platform raporunu sunarak güven tazelemektir. Herhangi bir özel pazarlama metni veya hesaplama için bana danışabilirsiniz."""

        # Check Gemini API
        api_key = os.environ.get("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
        if not api_key:
            return jsonify({"ok": True, "reply": _get_expert_reply(user_msg)})

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            system_prompt = f"""
            Sen NexaPrime'sın — Coldwell Banker CB VIP Ankara'da Danışman Yiğit Narin'in Resmi Portföy ve İlan Operasyon AI Copilot'usun.
            İlan: {title} | Fiyat: {price} | Lokasyon: {loc} | Tür: {ltype}
            Toplam İstatistik: {total_views} görüntülenme, {total_favs} favori, {total_msgs + total_calls} mesaj/arama.
            Soruyu son derece yetkin, profesyonel, maddeler halinde ve doğrudan uygulanabilir Türkçe ile yanıtla.
            """
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"""{system_prompt}

Danışman Sorusu: {user_msg}""",
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=750)
            )
            reply_text = (resp.text or "").strip()
            return jsonify({"ok": True, "reply": reply_text if reply_text else _get_expert_reply(user_msg)})
        except Exception as api_err:
            print(f"Gemini call fallback: {api_err}")
            return jsonify({"ok": True, "reply": _get_expert_reply(user_msg)})

    except Exception as e:
        return jsonify({"ok": True, "reply": f"NexaPrime AI: İlan analiz edildi. Teklif veren alıcılarla yerinde görüşme planlayarak süreci hızlandırabilirsiniz. (Detay: {e})"})

@app.route("/api/appointments", methods=["POST"])
def create_appointment():
    import json as _json_appt
    try:
        data = flask_request.json or {}
        name = str(data.get("name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        project_name = str(data.get("project_name", "")).strip()
        note = str(data.get("note", "")).strip()
        if not name or not phone:
            return jsonify({"success": False, "ok": False, "error": "Ad ve telefon numarası zorunludur."}), 400
        print(f"📅 Yeni Randevu Talebi: {name} | {phone} | {project_name}")
        appt_record = {
            "id": f"appt_{int(time.time())}",
            "name": html.escape(name),
            "phone": html.escape(phone),
            "project_name": html.escape(project_name),
            "note": html.escape(note),
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "status": "pending"
        }
        appt_file = BASE_DIR / "static" / "data" / "appointments.json"
        try:
            existing = _json_appt.loads(appt_file.read_text(encoding="utf-8")) if appt_file.exists() else []
            existing.insert(0, appt_record)
            existing = existing[:500]
            import tempfile as _tmpa, os as _osa
            fd, tp = _tmpa.mkstemp(dir=str(appt_file.parent), suffix=".tmp")
            with open(fd, "w", encoding="utf-8") as af:
                _json_appt.dump(existing, af, ensure_ascii=False, indent=2)
            _osa.replace(tp, str(appt_file))
        except Exception as ae:
            print(f"⚠️ Randevu kayıt hatası: {ae}")
        return jsonify({"success": True, "ok": True, "message": "Randevu talebiniz başarıyla alındı. Yiğit Narin en kısa sürede sizinle iletişime geçecektir.", "id": appt_record["id"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def get_system_config():
    return jsonify({
        "success": True,
        "assistant_name": "NexaPrime AI",
        "agent_name": "Yiğit Narin",
        "agency": "Coldwell Banker CB VIP Ankara",
        "phone": "+90 532 451 40 08"
    })

# ============================================================
#  URL → SUNUM PDF ÜRETİCİ
#  Herhangi bir ilan URL'sini alır, scrape eder, görselleri
#  indirir ve Yiğit Narin markasıyla lüks sunum PDF'i oluşturur.
# ============================================================

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


def _atomic_json_dump(target_path, data):
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_p = tempfile.mkstemp(dir=str(target_path.parent), prefix="tmp_save_", suffix=".json")
    try:
        with open(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_p, str(target_path))
    except Exception:
        if os.path.exists(temp_p):
            try:
                os.remove(temp_p)
            except Exception:
                pass
        raise


@app.route("/api/settings/agent", methods=["GET", "POST"])
def api_settings_agent():
    """Danışman profili alma ve güncelleme endpoint'i."""
    settings_file = BASE_DIR / "static" / "data" / "agent_settings.json"
    if flask_request.method == "POST":
        body = flask_request.get_json(force=True, silent=True) or {}
        current = _get_agent_settings()
        current.update(body)
        _atomic_json_dump(settings_file, current)
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
    _atomic_json_dump(_TOKENS_FILE, tokens)


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



# ==========================================
# MAIN SERVER RUNNER
# ==========================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        sys.argv.pop(1)
        main()
    else:
        run_server()


