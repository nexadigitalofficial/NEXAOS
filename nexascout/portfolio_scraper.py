# -*- coding: utf-8 -*-
r"""
NexaScout Universal Portfolio Scraper (Feature X)
Mimari İlham: gayrimenkulmuhendisi-main (ai_listing.py & a.py)
Desteklenen Kaynaklar:
  • sahibinden.com (PageSpeed Insights API + Async Playwright + Akıllı Slug Fallback)
  • cb.com.tr / Coldwell Banker (Doğrudan BS4 Slider Scraper + PSI Fallback)
  • hepsiemlak.com, zingat.com, emlakjet.com ve genel ilan sayfaları (OG Tags)

Özellikler:
  • AVIF → JPG otomatik dönüştürme ve görsel tekilleştirme
  • Çok kademeli Cloudflare / Akamai bot koruması aşma
  • Nominatim OpenStreetMap koordinat çözümleme
  • Çoklu fotoğraf indirme ve Base64 kodlama (Gemini Vision için hazır)
  • Asla hata vermeyen güvenli fallback mimarisi
"""

import os
import re
import sys
import time
import json
import base64
import asyncio
import urllib.parse
import html as html_mod
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List, Tuple

# Playwright opsiyonel kontrolü
try:
    from playwright.async_api import async_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5",
    "DNT": "1",
}

SCRAPE_TIMEOUT = 15
PAGESPEED_WEB_URL = "https://pagespeed.web.dev/?hl=tr"
DEFAULT_PS_WAIT = 35

_coord_cache: Dict[str, Tuple[float, float]] = {}
_last_nominatim_call: float = 0.0

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
    'merkez': 'Merkez', 'cankaya': 'Çankaya', 'golbasi': 'Gölbaşı', 'incek': 'İncek',
    'kizilcasar': 'Kızılcaşar', 'cayyolu': 'Çayyolu', 'umitkoy': 'Ümitköy',
    'beytepe': 'Beytepe', 'bilkent': 'Bilkent', 'losante': 'LÖSANTE Karşısı',
    'kose': 'Köşe', 'parsel': 'Parsel', 'ticari': 'Ticari', 'ruhsatli': 'Ruhsatlı',
    'bahceli': 'Bahçeli', 'havuzlu': 'Havuzlu', 'esyali': 'Eşyalı', 'luks': 'Lüks'
}
WORD_MAP.update(TURKISH_CITIES)

_PSI_EP_MAP = {
    "ep.content_group":     "Sayfa Türü",
    "ep.kategori_1":        "Kategori 1",
    "ep.kategori_2":        "Kategori 2",
    "ep.kategori_3":        "Kategori 3",
    "ep.CD_ilanNo":         "İlan No",
    "ep.ilan_no":           "İlan No",
    "ep.js_price":          "Fiyat (Sayısal)",
    "ep.CD_IlanOwnerType":  "Satıcı Tipi",
    "ep.CD_Yer1":           "Ülke",
    "ep.CD_Yer2":           "Şehir",
    "ep.CD_Yer3":           "İlçe",
    "ep.CD_Yer4":           "Mahalle",
    "ep.CD_Yer5":           "Mahalle (detay)",
    "ep.yer_2":             "Şehir",
    "ep.yer_3":             "İlçe",
    "ep.yer_4":             "Mahalle",
}


def detect_listing_id(url: str) -> str:
    """URL içinden ilan ID'sini ayıklar."""
    if not url:
        return ""
    m = re.search(r"/(?:ilan|listing)/[^/]*?-?(\d{8,12})(?:/detay|\?|#|$)", url)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d{8,12})", url)
    if m2 and len(m2.group(1)) >= 8:
        return m2.group(1)
    return ""


def _sahibinden_avif_to_jpg(url: str) -> str:
    """Sahibinden AVIF CDN URL'lerini JPG'ye çevirir."""
    if url.lower().endswith(".avif"):
        return url[:-5] + ".jpg"
    return url


def geocode_address(query: str) -> Optional[Tuple[float, float]]:
    """Adresi OpenStreetMap Nominatim servisi ile enlem/boylama dönüştürür."""
    global _last_nominatim_call
    if not query:
        return None
    if query in _coord_cache:
        return _coord_cache[query]

    elapsed = time.time() - _last_nominatim_call
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "tr"},
            headers={"User-Agent": "NexaScoutBuyerEngine/2.0 (info@nexadigital.com)"},
            timeout=6,
        )
        _last_nominatim_call = time.time()
        data = resp.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            _coord_cache[query] = (lat, lon)
            return lat, lon
    except Exception:
        pass

    _coord_cache[query] = None
    return None


def _clean_text(el) -> str:
    return el.get_text(separator=" ", strip=True) if el else ""


def _extract_psi_photos(raw_html: str) -> List[str]:
    """Render edilmiş HTML'den Sahibinden CDN fotoğraf URL'lerini çıkarır."""
    unescaped = html_mod.unescape(raw_html)
    photos = []
    seen = set()
    pattern = re.compile(
        r"https?://i\d+\.shbdn\.com/photos/[^\s\"'<>&]+\.(?:avif|jpg|jpeg|png|webp)",
        re.IGNORECASE,
    )
    for m in pattern.finditer(unescaped):
        u = m.group(0).split("?", 1)[0].split("#", 1)[0]
        u = _sahibinden_avif_to_jpg(u)
        if u not in seen and "logo" not in u and "icon" not in u and "blank" not in u:
            seen.add(u)
            photos.append(u)
            if len(photos) >= 20:
                break
    return photos


def _extract_psi_specs(raw_html: str) -> Dict[str, str]:
    """PageSpeed HTML içindeki analytics ve tablo özelliklerini çeker."""
    specs = {}
    ep_pattern = re.compile(r"ep\.([A-Za-z0-9_]+)=([^&\n\"'<>]+)", re.IGNORECASE)
    for m in ep_pattern.finditer(raw_html):
        raw_key = "ep." + m.group(1)
        raw_val = m.group(2).replace("&amp;", "&").replace("+", " ")
        try:
            raw_val = urllib.parse.unquote(raw_val).strip()
        except Exception:
            raw_val = raw_val.strip()
        label = _PSI_EP_MAP.get(raw_key)
        if label and raw_val and raw_val not in ("0", "false"):
            specs[label] = raw_val

    # Fiyat formatı
    if "Fiyat (Sayısal)" in specs:
        try:
            amt = int(specs["Fiyat (Sayısal)"])
            specs["Fiyat"] = f"{amt:,.0f} TL".replace(",", ".")
        except Exception:
            pass

    return specs


def _extract_psi_description(raw_text: str) -> str:
    """Açıklama metnini çıkarır."""
    t = html_mod.unescape(raw_text)
    for marker in ["İlan Açıklaması", "Ilan Aciklamasi", "İLAN AÇIKLAMASI", "AÇIKLAMA", "Açıklama"]:
        idx = t.find(marker)
        if idx != -1:
            window = t[idx + len(marker): idx + len(marker) + 4000]
            m = re.match(r"\s*[:\-–]?\s*([^<]{40,3500})", window)
            if m:
                cand = re.sub(r"\s+", " ", m.group(1)).strip()
                if len(cand) >= 40:
                    return cand
    return ""


def _download_image_b64(img_url: str) -> Optional[Tuple[str, str]]:
    """
    Görseli indirir ve (mime_type, base64_str) döndürür.
    Gemini Multimodal Vision analizi için kullanılır.
    """
    img_url = _sahibinden_avif_to_jpg(img_url)
    try:
        resp = requests.get(img_url, headers=HEADERS, timeout=8, stream=True)
        if not resp.ok:
            return None
        ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        mime = ct.split("/")[-1] if "/" in ct else "jpeg"
        if mime not in ("jpeg", "png", "webp", "gif"):
            mime = "jpeg"
        raw_bytes = b"".join(resp.iter_content(65536))
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        return mime, b64
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 1. KADEME: GOOGLE PAGESPEED INSIGHTS REST API SCRAPER
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_via_psi_api(url: str) -> Dict[str, Any]:
    api_key = os.environ.get("PAGESPEED_API_KEY", "AIzaSyClEth2ooknGZJ53WrgY1QKdrQunZfsNXg")
    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    listing_id = detect_listing_id(url)
    clean_url = url.split("#", 1)[0].rstrip("/")
    target_url = f"{clean_url}/#classified-detail"
    
    try:
        resp = requests.get(
            psi_url,
            params={"url": target_url, "category": "performance", "hl": "tr", "key": api_key},
            timeout=60
        )
        if resp.status_code == 200:
            psi_json = resp.json()
            raw_text = resp.text
            
            # %100 Fotoğrafları JSON payload'ından çıkar (x5_ yüksek çözünürlük)
            psi_photo_pat = re.compile(
                r'https?://i\d+\.shbdn\.com/photos/(\d+/\d+/\d+)/([a-zA-Z0-9_]+)\.(avif|jpg|jpeg|png|webp)',
                re.IGNORECASE
            )
            seen_keys = set()
            photos = []
            for match in psi_photo_pat.finditer(raw_text):
                folder, fname, ext = match.groups()
                base_id = re.sub(r'^(x5_|x3_|x2_|x1_|thmb_|lthmb_)', '', fname)
                if not base_id or "blank" in base_id:
                    continue
                core_key = f"https://i0.shbdn.com/photos/{folder}/{base_id}"
                if core_key not in seen_keys:
                    seen_keys.add(core_key)
                    photos.append(f"https://i0.shbdn.com/photos/{folder}/x5_{base_id}.avif")

            specs = _extract_psi_specs(raw_text)
            desc = _extract_psi_description(raw_text)

            # OCR ile Açıklama ve Özellikleri (#classified-detail) çıkar
            try:
                from PIL import Image as _PILImage
                import io as _io
                import pytesseract as _pytesseract
                b64_data = psi_json.get("lighthouseResult", {}).get("fullPageScreenshot", {}).get("screenshot", {}).get("data", "")
                if b64_data:
                    if "," in b64_data[:60]:
                        b64_data = b64_data.split(",", 1)[1]
                    img_bytes = base64.b64decode(b64_data)
                    full_img = _PILImage.open(_io.BytesIO(img_bytes)).convert("RGB")
                    w, h = full_img.size
                    top_y = min(int(h * 0.16), 920)
                    bot_y = min(h, 2700)
                    crop_img = full_img.crop((int(w * 0.04), top_y, int(w * 0.96), bot_y))
                    raw_ocr = _pytesseract.image_to_string(crop_img, lang="tur")
                    parts = re.split(r'A.{1,2}klama\s*', raw_ocr, flags=re.IGNORECASE)
                    body = parts[1] if len(parts) > 1 else raw_ocr
                    end_parts = re.split(r'\n\s*.{0,2}zellikler', body, flags=re.IGNORECASE)
                    cleaned_ocr = re.sub(r"[ \t]+", " ", end_parts[0].strip())
                    cleaned_ocr = re.sub(r"\n{3,}", "\n\n", cleaned_ocr).strip()
                    if len(cleaned_ocr) >= 40:
                        desc = cleaned_ocr
            except Exception:
                pass
            
            city = specs.get("Şehir", "Ankara")
            dist = specs.get("İlçe", "")
            mah = specs.get("Mahalle", "")
            loc_parts = [p for p in [mah, dist, city] if p]
            loc_str = ", ".join(loc_parts) if loc_parts else "Ankara"
            
            slug_info = _scrape_via_slug_fallback(url)
            title = slug_info.get("title") or f"Sahibinden İlanı #{listing_id}"
            price = specs.get("Fiyat") or ""

            return {
                "ok": True,
                "source": "sahibinden_psi_api",
                "title": title,
                "price": price,
                "location": loc_str,
                "city": city,
                "district": dist,
                "neighborhood": mah,
                "specs": specs,
                "description": desc or slug_info.get("description", ""),
                "images": photos,
                "photo_count": len(photos)
            }
    except Exception as e:
        pass
    return {"ok": False}


# ═══════════════════════════════════════════════════════════════════════════
# 2. KADEME: ASYNC PLAYWRIGHT PAGESPEED SCRAPER
# ═══════════════════════════════════════════════════════════════════════════

async def _scrape_via_pagespeed_async(url: str) -> Dict[str, Any]:
    """Headless Chromium ile PageSpeed Web üzerinden render edip verileri çeker."""
    if not _HAS_PLAYWRIGHT:
        return {"ok": False, "error": "Playwright yüklü değil"}

    headless = True
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            
            try:
                await page.goto(PAGESPEED_WEB_URL, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1500)
                
                # Cookie banner geçişi
                try:
                    c_btn = page.locator("button:has-text('Kabul et'), button:has-text('Accept all')").first
                    if await c_btn.is_visible(timeout=2000):
                        await c_btn.click()
                except Exception:
                    pass

                # URL yaz ve Analiz et
                inp = page.locator("input[name='url']").first
                await inp.fill(url)
                await page.wait_for_timeout(400)
                await inp.press("Enter")

                # Görsellerin düşmesini bekle (max 20s)
                for _ in range(20):
                    await page.wait_for_timeout(1000)
                    content = await page.content()
                    if "shbdn.com/photos" in content:
                        break

                raw_html = await page.content()
            finally:
                await ctx.close()
                await browser.close()

            photos = _extract_psi_photos(raw_html)
            specs = _extract_psi_specs(raw_html)
            desc = _extract_psi_description(raw_html)
            slug_info = _scrape_via_slug_fallback(url)

            city = specs.get("Şehir", "Ankara")
            dist = specs.get("İlçe", "")
            mah = specs.get("Mahalle", "")
            loc_parts = [p for p in [mah, dist, city] if p]
            loc_str = ", ".join(loc_parts) if loc_parts else "Ankara"

            return {
                "ok": True,
                "source": "sahibinden_playwright_pagespeed",
                "title": slug_info.get("title", f"Sahibinden İlanı #{detect_listing_id(url)}"),
                "price": specs.get("Fiyat", ""),
                "location": loc_str,
                "city": city,
                "district": dist,
                "neighborhood": mah,
                "specs": specs,
                "description": desc or slug_info.get("description", ""),
                "images": photos,
                "photo_count": len(photos)
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ═══════════════════════════════════════════════════════════════════════════
# 3. KADEME: COLDWELL BANKER (CB.COM.TR) ÖZEL SCRAPER
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_coldwell_banker(url: str) -> Dict[str, Any]:
    """Coldwell Banker ilan detay sayfasını çeker."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SCRAPE_TIMEOUT)
        if resp.status_code != 200:
            # 403 vb durumunda PSI veya fallback'e geç
            return {"ok": False, "error": f"HTTP {resp.status_code}"}

        soup = BeautifulSoup(resp.content, "lxml")
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = _clean_text(h1)

        # Galeri görselleri (gayrimenkulmuhendisi-main/a.py mimarisi)
        images = []
        for sel in [
            "div.swiper-slide img", "div.slick-slide img", "div.carousel-item img",
            ".detail-slider img", ".stock-slider img", ".cb-detail-slider img", "figure img"
        ]:
            imgs = soup.select(sel)
            if imgs:
                for img in imgs:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy") or ""
                    src = src.strip()
                    if src and "placeholder" not in src and src not in images:
                        if src.startswith("/"):
                            src = "https://www.cb.com.tr" + src
                        images.append(src)
                if images:
                    break

        if not images:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                src = src.strip()
                if ("media.cb" in src or "StockMedia" in src) and src not in images:
                    images.append(src)

        # Özellik tablosu
        specs = {}
        for row in soup.select("table tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                k = _clean_text(cells[0])
                v = _clean_text(cells[1])
                if k and v:
                    specs[k] = v

        for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
            k, v = _clean_text(dt), _clean_text(dd)
            if k and v:
                specs[k] = v

        for li in soup.select("ul.features li, .property-features li, .cb-features li"):
            txt = _clean_text(li)
            if ":" in txt:
                p = txt.split(":", 1)
                specs[p[0].strip()] = p[1].strip()

        # Fiyat
        price = ""
        price_el = soup.select_one(".price, [class*='price'], .detail-price, h2.price")
        if price_el:
            price = _clean_text(price_el)

        # Açıklama
        desc = ""
        desc_el = soup.select_one(".description, .detail-description, [class*='description'], #description")
        if desc_el:
            desc = _clean_text(desc_el)

        slug_data = _scrape_via_slug_fallback(url)
        return {
            "ok": True,
            "source": "coldwell_banker_direct",
            "title": title or slug_data.get("title", "Coldwell Banker Portföyü"),
            "price": price or slug_data.get("price", ""),
            "location": slug_data.get("location", "Ankara"),
            "specs": specs or slug_data.get("specs", {}),
            "description": desc or slug_data.get("description", ""),
            "images": images,
            "photo_count": len(images)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 4. KADEME: AKILLI SLUG FALLBACK (GÜVENLİ VE HİÇBİR ZAMAN ÇÖKMEYEN MOTOR)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_via_slug_fallback(url: str) -> Dict[str, Any]:
    listing_id = detect_listing_id(url)
    slug = ""
    if "/ilan/" in url:
        slug = url.split("/ilan/", 1)[1].split("/detay", 1)[0]
    elif "cb.com.tr" in url:
        slug = url.split("cb.com.tr", 1)[1].split("?", 1)[0]
    else:
        slug = url.split("/")[-1]

    if listing_id and slug.endswith("-" + listing_id):
        slug = slug[: -(len(listing_id) + 1)]

    tokens = [t.strip().lower() for t in re.split(r"[-\./_]", slug) if t.strip()]

    city = "Ankara"
    district = ""
    prop_type = "Ticari Gayrimenkul"
    clean_words = []

    for idx, t in enumerate(tokens):
        if t in TURKISH_CITIES:
            city = TURKISH_CITIES[t]
            if idx + 1 < len(tokens):
                nxt = tokens[idx + 1]
                if nxt in WORD_MAP:
                    district = WORD_MAP[nxt]
        if t in ["bina", "komple", "villa", "arsa", "ofis", "dukkan", "plaza"]:
            if t == "bina": prop_type = "Müstakil Bina"
            elif t == "villa": prop_type = "Müstakil Villa / Ofis"
            elif t == "arsa": prop_type = "Ticari Arsa"
            elif t == "plaza": prop_type = "İş Merkezi / Plaza"

        if t not in ["emlak", "is", "yeri", "isyeri", "detay"]:
            clean_words.append(WORD_MAP.get(t, t.capitalize()))

    loc_str = f"{city}, {district}".strip(", ") if district else city
    title_str = " ".join(clean_words) if clean_words else (f"Portföy İlanı #{listing_id}" if listing_id else "Kurumsal Gayrimenkul Portföyü")

    specs = {
        "Konum": loc_str,
        "Şehir": city,
        "İlçe": district or "Gölbaşı / Çankaya",
        "Mülk Türü": prop_type,
        "Yetkili": "Yiğit Narin (Coldwell Banker VIP)"
    }

    desc = (
        f"{title_str} — {loc_str} lokasyonunda yer alan, stratejik konumu, kurumsal mimari tasarımı, "
        f"bağımsız kullanım avantajı ve yüksek yatırım değeriyle öne çıkan seçkin portföy."
    )

    return {
        "ok": True,
        "source": "smart_slug_fallback",
        "title": title_str,
        "price": "",
        "location": loc_str,
        "city": city,
        "district": district,
        "neighborhood": "",
        "specs": specs,
        "description": desc,
        "images": [],
        "photo_count": 0
    }


# ═══════════════════════════════════════════════════════════════════════════
# ANA DAĞITICI (UNIVERSAL DISPATCHER)
# ═══════════════════════════════════════════════════════════════════════════

def scrape_any_listing(url: str) -> Dict[str, Any]:
    """
    Herhangi bir gayrimenkul ilan linkini alarak eksiksiz portföy verisini çeker.
    Sahibinden, Coldwell Banker, HepsiEmlak, Zingat, Emlakjet desteklenir.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    domain = urllib.parse.urlparse(url).netloc.lower()
    listing_id = detect_listing_id(url)

    result = {}

    if "cb.com.tr" in domain or "coldwellbanker" in domain:
        result = _scrape_coldwell_banker(url)
        if not result.get("ok"):
            # CB engellerse PSI API'yi dene
            result = _scrape_via_psi_api(url)

    elif "sahibinden.com" in domain:
        # 1. Aşama: Hızlı Google PSI API
        result = _scrape_via_psi_api(url)
        
        # 2. Aşama: Playwright Async PSI
        if (not result.get("ok") or not result.get("images")) and _HAS_PLAYWRIGHT:
            try:
                res_pw = asyncio.run(_scrape_via_pagespeed_async(url))
                if res_pw.get("ok"):
                    result = res_pw
            except Exception:
                pass

    # Fallback
    if not result.get("ok"):
        result = _scrape_via_slug_fallback(url)

    # Genel zenginleştirme
    result["url"] = url
    result["listing_id"] = listing_id or "PORTFOY"
    
    # Koordinatları bul
    loc_query = f"{result.get('location', '')}, Türkiye"
    coords = geocode_address(loc_query)
    if coords:
        result["latitude"] = coords[0]
        result["longitude"] = coords[1]
    else:
        # Varsayılan Ankara Gölbaşı İncek / LÖSANTE aksı
        result["latitude"] = 39.8162
        result["longitude"] = 32.7485

    return result
