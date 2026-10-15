# -*- coding: utf-8 -*-
r"""
NexaScout C-Suite & Decision-Maker Hunter Engine
Hedef kurumların web sitelerinden Yönetim Kurulu Başkanı, Kurucu, Başhekim, Genel Müdür
ve Yatırım Direktörü profillerini ayrıştırır; doğrudan karar vericiye hitap eden
VIP 'Off-Market' gizli ikna teaser metinleri üretir.
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

TITLE_PATTERNS = [
    (r"(y[oö]netim\s*kurulu\s*ba[sş]kan[ıi]|ykb|chairman|president)", "Yönetim Kurulu Başkanı"),
    (r"(kurucu\s*(ortak)?|founder|co-founder)", "Kurucu / Ortak"),
    (r"(ba[sş]hekim|chief\s*physician|medical\s*director)", "Başhekim / Tıbbi Direktör"),
    (r"(genel\s*m[uü]d[uü]r|ceo|managing\s*director)", "Genel Müdür / CEO"),
    (r"(yat[ıi]r[ıi]m\s*(ve\s*i[sş]\s*geli[sş]tirme)?\s*direkt[oö]r[uü]|expansion\s*director)", "Yatırım & İş Geliştirme Direktörü"),
    (r"(kurucu\s*temsilcisi|okul\s*m[uü]d[uü]r[uü])", "Kurucu Temsilcisi / Okul Müdürü"),
    (r"(prof\.\s*dr\.\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)", "Profesör Doktor / Klinik Sahibi"),
    (r"(y[oö]netici\s*ortak|managing\s*partner)", "Yönetici Ortak")
]

MANAGEMENT_PATHS = [
    "/hakkimizda", "/about", "/about-us",
    "/yonetim", "/yonetim-kurulu", "/management", "/board",
    "/ekibimiz", "/team", "/kadromuz",
    "/hekimlerimiz", "/doktorlarimiz", "/doctors",
    "/iletisim", "/contact"
]

def find_decision_makers(website_url, timeout=4):
    """
    Kurumun web sitesini ve kurumsal sayfalarını tarayarak karar vericileri tespit eder.
    """
    if not website_url or website_url == "N/A" or not website_url.startswith("http"):
        return []

    identified_people = []
    base_domain = urllib.parse.urlparse(website_url).netloc
    
    pages_to_check = [website_url]
    parsed_base = urllib.parse.urlparse(website_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    
    for path in MANAGEMENT_PATHS[:5]: # En kritik 5 sayfayı tara
        pages_to_check.append(urllib.parse.urljoin(origin, path))

    visited = set()
    for url in pages_to_check:
        if url in visited:
            continue
        visited.add(url)
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            
            # Unvan ve isim eşleştirmeleri
            for regex, title_label in TITLE_PATTERNS:
                matches = re.finditer(regex, text, re.IGNORECASE)
                for m in matches:
                    start = max(0, m.start() - 60)
                    end = min(len(text), m.end() + 60)
                    snippet = text[start:end].strip()
                    # İsim temizliği
                    words = [w for w in re.split(r'\s+', snippet) if len(w) > 2]
                    clean_context = " ".join(words[:12])
                    
                    identified_people.append({
                        "title": title_label,
                        "raw_snippet": clean_context,
                        "source_url": url
                    })
                    if len(identified_people) >= 3:
                        break
                if len(identified_people) >= 3:
                    break
        except Exception:
            continue
            
        if len(identified_people) >= 3:
            break

    return identified_people

def generate_confidential_teaser(lead_data, decision_maker_name=None, decision_maker_title=None):
    """
    Karar vericiye özel, adresi doğrudan ifşa etmeyen 'Off-Market Confidential Teaser' üretir.
    """
    kurum_adi = lead_data.get("kurum_adi", "Değerli Kurum")
    sektor = lead_data.get("is_kolu", "Sektör Lideri")
    mesafe = lead_data.get("mesafe_km", "1.5")
    
    dm_salutation = f"Sayın {decision_maker_name} ({decision_maker_title})" if decision_maker_name and decision_maker_title else f"{kurum_adi} Yönetim Kurulu Başkanlığı & Üst Yönetimi Dikkatine"
    
    teaser = f"""KURUMA ÖZEL STRATEJİK YATIRIM TEASER'I
Kime: {dm_salutation}
Gönderen: Yiğit Narin - Coldwell Banker VIP Gayrimenkul Yatırım Direktörlüğü
Konu: Ankara İncek / LÖSANTE Karşısı - Bölgedeki Tek Yasal Ticari Ruhsatlı Müstakil Kompleks Hakkında

Sayın Yetkili,

{kurum_adi}'nin {sektor} alanındaki prestijli büyüme vizyonunu yakından takip etmekteyiz.

Mevcut lokasyonunuza yalnızca {mesafe} km mesafede, Ankara İncek'in en değerli sağlık ve kurumsal aksında, müstesna bir ticari gayrimenkulü portföyümüze almış bulunmaktayız.

MÜLKÜN STRATEJİK & RAKİPSİZ ÖZELLİKLERİ:
1. YASAL TEKEL STATÜSÜ: Çevre, Şehircilik ve İklim Değişikliği Bakanlığı onaylı 'TİCARİ Yapı Kayıt Belgesi' (Belge No: C278DFHU). Bölgedeki konut kooperatifi dokusu içerisinde ticari faaliyet ve kurum açma iznine sahip TEK müstakil parseldir.
2. LOKASYON GÜCÜ: LÖSANTE Hastanesi'nin tam karşısında, köşe parsel, 398 m² arsa ve ~420 m² brüt 4 katlı müstakil kullanım.
3. KULLANIM ALTYAPISI: Özel otopark alanı, müstakil bahçe, bağımsız girişler ve sağlık/klinik/eğitim/savunma standartlarına tam uygun mimari.

Yatırım detayları ve teknik şartname dosyasını şahsınıza özel olarak arz etmek üzere, uygun göreceğiniz bir zaman diliminde bir ön görüşme teklif etmekteyiz.

Resmi İlan Detayı: https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/

Saygılarımla,

Yiğit Narin
Coldwell Banker VIP Gayrimenkul
Lüks Konut & Ticari Gayrimenkul Danışmanı
İletişim: 0532 451 40 08
"""
    return teaser
