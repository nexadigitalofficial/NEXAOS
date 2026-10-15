# -*- coding: utf-8 -*-
"""
Deep Contact & Social Media Enrichment Module
Web sitelerinden e-posta, sosyal medya (Instagram, LinkedIn, Facebook vb.),
WhatsApp telefon formatı ve yetkili unvanlarını ayıklar.
"""

import re
import urllib.parse
import warnings
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def clean_phone_for_whatsapp(phone_str):
    """Telefon numarasını temizler ve uluslararası 90... formatına dönüştürür."""
    if not phone_str or phone_str == "N/A":
        return None
    # Sadece rakamları al
    digits = re.sub(r'\D', '', phone_str)
    if digits.startswith("90") and len(digits) == 12:
        return digits
    elif digits.startswith("0") and len(digits) == 11:
        return "9" + digits
    elif len(digits) == 10:
        return "90" + digits
    return digits if len(digits) >= 10 else None

def generate_whatsapp_url(phone_str, institution_name, distance_km=None):
    """Kişiselleştirilmiş WhatsApp doğrudan mesaj bağlantısı üretir."""
    clean_p = clean_phone_for_whatsapp(phone_str)
    if not clean_p:
        return "N/A"
    
    # GSM hatları (05xx) veya WhatsApp Business destekli numaralar için
    msg = (
        f"Merhaba {institution_name} yetkilisi, "
        f"İncek sağlık ve kurumsal aksında, LÖSANTE Hastanesi'nin tam karşısında yer alan "
        f"bölgenin tek tescilli 'TİCARİ' ruhsatlı müstakil gayrimenkulü hakkında "
        f"tarafınıza özel yatırım dosyamızı sunmak isteriz. "
        f"İlan Detayı: https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/ "
        f"Detaylı bilgi için: Yiğit Narin | Coldwell Banker VIP (0532 451 40 08)"
    )
    encoded_msg = urllib.parse.quote(msg)
    return f"https://wa.me/{clean_p}?text={encoded_msg}"

def enrich_from_website(website_url):
    """Web sitesi üzerinden derin e-posta ve sosyal medya taraması yapar."""
    result = {
        "email": "N/A",
        "instagram": "N/A",
        "linkedin": "N/A",
        "facebook": "N/A",
        "youtube": "N/A",
        "twitter": "N/A",
        "decision_makers": []
    }
    
    if not website_url or website_url == "N/A" or not website_url.startswith("http"):
        return result
        
    pages_to_check = [website_url]
    visited = set()
    found_emails = set()
    
    try:
        r = requests.get(website_url, headers=HEADERS, timeout=5, verify=False)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Find contact and about page links
            for a in soup.find_all("a", href=True):
                txt = (a.get_text() or "").lower()
                href = a["href"].lower()
                if any(k in txt or k in href for k in ["iletisim", "contact", "hakkimizda", "about", "ekibimiz", "doktor", "yonetim"]):
                    full_link = urllib.parse.urljoin(website_url, a["href"])
                    if full_link not in visited and len(pages_to_check) < 4:
                        pages_to_check.append(full_link)
                        visited.add(full_link)
    except Exception:
        pass
        
    # Check each identified page
    for page_url in pages_to_check:
        try:
            pr = requests.get(page_url, headers=HEADERS, timeout=4, verify=False)
            if pr.status_code != 200:
                continue
                
            p_soup = BeautifulSoup(pr.text, "html.parser")
            
            # 1. Emails
            for a in p_soup.find_all("a", href=True):
                href = a["href"]
                if "mailto:" in href:
                    clean_m = href.replace("mailto:", "").split("?")[0].strip()
                    if "@" in clean_m and "." in clean_m:
                        found_emails.add(clean_m)
                        
            # Regex email search
            raw_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', pr.text)
            for em in raw_emails:
                if not em.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif', '.css', '.js')):
                    found_emails.add(em)
                    
            # 2. Social Media Links
            for a in p_soup.find_all("a", href=True):
                href = a["href"].lower()
                if "instagram.com/" in href and result["instagram"] == "N/A":
                    clean_h = href.split("?")[0]
                    if not any(x in clean_h for x in ["/p/", "/share", "/explore"]):
                        result["instagram"] = clean_h
                elif "linkedin.com/company/" in href and result["linkedin"] == "N/A":
                    result["linkedin"] = href.split("?")[0]
                elif "facebook.com/" in href and result["facebook"] == "N/A":
                    if not any(x in href for x in ["sharer", "share.php"]):
                        result["facebook"] = href.split("?")[0]
                elif "youtube.com/" in href and result["youtube"] == "N/A":
                    result["youtube"] = href.split("?")[0]
                elif ("twitter.com/" in href or "x.com/" in href) and result["twitter"] == "N/A":
                    if not any(x in href for x in ["intent", "share"]):
                        result["twitter"] = href.split("?")[0]
                        
        except Exception:
            continue
            
    # Filter emails
    valid_emails = [e for e in found_emails if not any(x in e.lower() for x in ["sentry", "wix", "example", "domain", "noreply"])]
    if valid_emails:
        result["email"] = valid_emails[0]
        
    return result
