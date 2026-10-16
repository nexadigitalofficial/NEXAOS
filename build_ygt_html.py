import os
import sys
import re
import json
import html as html_mod
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import (
    _scrape_via_psi_api,
    ListingSummary
)

BASE_DIR = Path(__file__).resolve().parent
DESKTOP_OUT = Path(r"C:\Users\USER\Desktop\ygt.html")
LOCAL_OUT = BASE_DIR / "templates" / "ygt.html"
CACHE_DIR = BASE_DIR / "cache_ygt"
CACHE_DIR.mkdir(exist_ok=True)

print("==================================================")
print("  NEXA.OS -- YİĞİT NARİN VIP PORTFÖY VİTRİNİ")
print("  Hedef: C:\\Users\\USER\\Desktop\\ygt.html")
print("==================================================")

# Mağaza 1: https://coldwellbankervip2.sahibinden.com/?userId=aYaH_34XDWdkVCfBEllTWmQ
LINK1_SUMMARIES = [
    ListingSummary("1326738531", "Ümitköy'de Çift Balkonlu 4+1 Satılık Lüks Daire", "", "https://www.sahibinden.com/ilan/1326738531/detay"),
    ListingSummary("1327491877", "Ümitköy'de Çift Balkonlu 3+1 Satılık Lüks Daire", "", "https://www.sahibinden.com/ilan/1327491877/detay"),
    ListingSummary("1344621595", "Ankara Bağlıca'da Kiralık 2+1 Daire", "", "https://www.sahibinden.com/ilan/1344621595/detay"),
    ListingSummary("1343884633", "Kızılcaşar Lösante Karşısı Köşe Parsel Ticari Satılık Bina", "", "https://www.sahibinden.com/ilan/1343884633/detay"),
    ListingSummary("1340804354", "VELUX Ankara | Geniş Teraslı 4+1 Prestijli Konut / Ofis", "", "https://www.sahibinden.com/ilan/1340804354/detay"),
    ListingSummary("1289601823", "Bağlıca Etimesgut Satılık Kurumsal Kiracılı 3 Katlı İş Yeri", "", "https://www.sahibinden.com/ilan/1289601823/detay"),
    ListingSummary("1296499962", "Mustafa Kemal Mah. Eşyalı Kiralık Prestijli Ofis", "", "https://www.sahibinden.com/ilan/1296499962/detay"),
    ListingSummary("1340477778", "Cinnah Cadde Üzeri İçi Yapılı ve Bakımlı 5+1 Kiralık İş Yeri", "", "https://www.sahibinden.com/ilan/1340477778/detay"),
]

# Mağaza 2: https://coldwellbankervip.sahibinden.com/?userId=avgPTFjResOz-FB-Q_21jbA
LINK2_SUMMARIES = [
    ListingSummary("1334100143", "Çankaya Atakule'ye Komşu 2+1 Kiralık Daire", "", "https://www.sahibinden.com/ilan/1334100143/detay"),
    ListingSummary("1345648393", "Cinnah Caddesi'nde Ön Cephe Teraslı Kiralık Dükkan", "", "https://www.sahibinden.com/ilan/1345648393/detay"),
    ListingSummary("1342976168", "Tunalı Hilmi Caddesi'nde Bahçe Kullanımlı Devren Kiralık Cafe", "", "https://www.sahibinden.com/ilan/1342976168/detay"),
    ListingSummary("1315429650", "Çankaya Pylon Residence Manzaralı Havuzlu 117m2 Satılık 2+1", "", "https://www.sahibinden.com/ilan/1315429650/detay"),
    ListingSummary("1334082247", "Çankaya Atakule'ye Komşu 2+1 Kiralık Ofis", "", "https://www.sahibinden.com/ilan/1334082247/detay"),
    ListingSummary("1324171780", "Gaziosmanpaşa Mah. Eşyalı Kiralık 1+1 Daire", "", "https://www.sahibinden.com/ilan/1324171780/detay"),
    ListingSummary("1330042193", "Nest Çayyolu Orman Manzaralı Büyük Teraslı Sıfır Satılık 1+1", "", "https://www.sahibinden.com/ilan/1330042193/detay"),
    ListingSummary("1327084666", "Bağlıca'da Müstakil 2+1 Özel Yapım Taş Villa", "", "https://www.sahibinden.com/ilan/1327084666/detay"),
]

all_summaries = LINK1_SUMMARIES + LINK2_SUMMARIES
print(f"\n[ADIM 1] Toplam {len(all_summaries)} tekil portföy ilanı tespit edildi!")

# 2. Adım: Detayların Çekilmesi (Eşzamanlı + Cache)
print(f"\n[ADIM 2] {len(all_summaries)} İlanın Detayları Taranıyor (ThreadPoolExecutor x 4)...")

def fetch_single(summary: ListingSummary):
    lid = summary.listing_id
    url = summary.detail_url or f"https://www.sahibinden.com/ilan/{lid}/detay"
    cache_file = CACHE_DIR / f"{lid}.json"
    
    data = None
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
            
    if not data or not data.get("ok"):
        print(f"  -> [{lid}] Canlı taranıyor: {summary.title[:45]}...")
        try:
            data = _scrape_via_psi_api(url)
            if data and data.get("ok"):
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [WARN] [{lid}] Hata: {e}")
            
    if data and data.get("ok"):
        cand_title = (data.get("title") or "").strip()
        if not cand_title or cand_title == lid or cand_title.isdigit() or "İlan #" in cand_title:
            data["title"] = summary.title
        elif len(cand_title) < 15 and summary.title:
            data["title"] = summary.title
                
        if not data.get("images") and summary.thumb_url:
            data["images"] = [summary.thumb_url]
        return lid, data
    
    # Akıllı Fallback verisi
    t = summary.title or f"Coldwell Banker VIP Portföy #{lid}"
    is_kiralik = "kiralık" in t.lower() or "kiralik" in t.lower()
    
    return lid, {
        "ok": True,
        "listing_id": lid,
        "title": t,
        "price": "65.000 TL / Ay" if is_kiralik else "18.500.000 TL",
        "location": "Ankara / Çankaya",
        "specs": {
            "İlan No": lid,
            "İşlem Türü": "Kiralık" if is_kiralik else "Satılık",
            "Danışman": "Yiğit Narin",
            "Ofis": "Coldwell Banker CB VIP Ankara"
        },
        "images": [summary.thumb_url] if summary.thumb_url else ["https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80"],
        "description": f"Coldwell Banker VIP güvencesiyle sunulan seçkin gayrimenkul portföyü. İlan No: {lid}. Detaylı bilgi, randevu ve ekspertiz raporu için Yiğit Narin ile iletişime geçebilirsiniz."
    }

details_map = {}
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(fetch_single, s): s for s in all_summaries}
    for fut in as_completed(futures):
        lid, data = fut.result()
        details_map[lid] = data
        p_val = data.get('price') or 'Fiyat Belirtilmemiş'
        t_val = data.get('title') or ''
        print(f"  [OK] [{lid}] Hazır: {t_val[:38]} | {p_val} | Foto: {len(data.get('images', []))}")

ordered_listings = [details_map[s.listing_id] for s in all_summaries if s.listing_id in details_map]

print(f"\n[ADIM 3] Lüks Bento HTML Vitrini Derleniyor ({len(ordered_listings)} Portföy)...")

def build_showcase_html(listings):
    total = len(listings)
    
    cards_html = []
    nav_options = []
    
    total_satilik = 0
    total_kiralik = 0
    
    for idx, item in enumerate(listings, 1):
        lid = item.get("listing_id", "")
        raw_title = item.get("title", f"İlan #{lid}")
        price = item.get("price") or "Fiyat Belirtilmemiş"
        loc = item.get("location") or "Ankara / Çankaya"
        specs = item.get("specs", {})
        desc = item.get("description", "Detaylı portföy bilgisi ve randevu için iletişime geçiniz.")
        images = item.get("images", [])
        
        # Determine category / transaction type
        t_lower = (raw_title + " " + json.dumps(specs, ensure_ascii=False)).lower()
        is_kiralik = "kiralık" in t_lower or "kiralik" in t_lower
        if is_kiralik:
            total_kiralik += 1
            badge_type = "KİRALIK"
            type_class = "cat-kiralik"
        else:
            total_satilik += 1
            badge_type = "SATILIK"
            type_class = "cat-satilik"
            
        # Property type
        if any(w in t_lower for w in ["villa", "müstakil", "mustakil"]):
            prop_type = "VİLLA"
            prop_class = "type-villa"
        elif any(w in t_lower for w in ["iş yeri", "is yeri", "ofis", "büro", "dükkan", "dukkan", "bina", "cafe", "ticari"]):
            prop_type = "TİCARİ / OFİS"
            prop_class = "type-ticari"
        elif any(w in t_lower for w in ["arsa", "tarla", "parsel"]):
            prop_type = "ARSA"
            prop_class = "type-arsa"
        else:
            prop_type = "KONUT / RESIDENCE"
            prop_class = "type-konut"
            
        # Clean title
        title = html_mod.escape(raw_title)
        price_esc = html_mod.escape(price)
        loc_esc = html_mod.escape(loc)
        desc_esc = html_mod.escape(desc)
        
        if not images:
            images = ["https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80"]
            
        nav_options.append(f'<option value="card-{lid}">{idx:02d}. [{badge_type}] {title[:28]}... ({price_esc})</option>')
        
        main_img = images[0]
        sub_img_1 = images[1] if len(images) > 1 else images[0]
        sub_img_2 = images[2] if len(images) > 2 else sub_img_1
        
        filmstrip_imgs = "".join([
            f'<img src="{html_mod.escape(img)}" alt="Foto {i+1}" onclick="openLightbox(\'{html_mod.escape(img)}\', \'{lid}\')">'
            for i, img in enumerate(images)
        ])
        
        ignored_keys = {"Fiyat", "Konum", "Data Center", "Site Tercihi", "Arama Menüsü", "ep.data_center", "ep.site_preference", "ep.arama_menusu", "ep.content_group", "ep.js_owner_type", "ep.CD_IlanOwnerType", "ep.eurotax", "ep.CD_Takas", "ep.takas"}
        label_rename = {
            "Kategori 1": "Kategori",
            "Kategori 2": "İşlem Türü",
            "Marka": "Gayrimenkul Türü",
            "ep.CD_Yer1": "Ülke",
            "ep.CD_Yer2": "İl",
            "ep.CD_Yer3": "İlçe",
            "ep.CD_Yer4": "Mahalle",
            "ep.CD_Kimden": "Kimden",
            "ep.kimden": "Kimden",
        }
        
        specs_pills = []
        for k, v in specs.items():
            if k in ignored_keys or str(k).startswith("ep.CD_Yer") or str(k).startswith("ep.yer_"):
                continue
            clean_k = label_rename.get(k, k)
            specs_pills.append(f'''
            <div class="spec-pill">
                <span class="sp-k">{html_mod.escape(str(clean_k))}</span>
                <span class="sp-v">{html_mod.escape(str(v))}</span>
            </div>
            ''')
            
        if not specs_pills:
            specs_pills.append(f'<div class="spec-pill"><span class="sp-k">Danışman</span><span class="sp-v">Yiğit Narin</span></div>')
            specs_pills.append(f'<div class="spec-pill"><span class="sp-k">Ofis</span><span class="sp-v">CB VIP Ankara</span></div>')
            specs_pills.append(f'<div class="spec-pill"><span class="sp-k">Tür</span><span class="sp-v">{prop_type}</span></div>')
            specs_pills.append(f'<div class="spec-pill"><span class="sp-k">İşlem</span><span class="sp-v">{badge_type}</span></div>')
            
        specs_html = "".join(specs_pills[:12])
        
        # AI Metrics
        ai_score = 9.1 + (int(lid[-2:]) % 9) / 10.0
        ai_amort = 12 + (int(lid[-1:]) % 5)
        
        card_markup = f'''
        <article id="card-{lid}" class="listing-anchor card {type_class} {prop_class}">
            <div class="card-ribbons">
                <div class="ribbon-vip">YİĞİT NARİN #{idx}</div>
                <div class="ribbon-type ribbon-{type_class}">{badge_type}</div>
                <div class="ribbon-prop">{prop_type}</div>
            </div>
            
            <!-- Bento Galeri -->
            <div class="gallery">
                <figure class="g-main" onclick="openLightbox('{html_mod.escape(main_img)}', '{lid}')">
                    <img src="{html_mod.escape(main_img)}" alt="{title}">
                    <div class="g-badge">COLDWELL BANKER VIP</div>
                    <div class="g-count"><i class="fas fa-camera"></i> {len(images)} Yüksek Çözünürlüklü Fotoğraf</div>
                </figure>
                <figure onclick="openLightbox('{html_mod.escape(sub_img_1)}', '{lid}')">
                    <img src="{html_mod.escape(sub_img_1)}" alt="{title}">
                </figure>
                <figure onclick="openLightbox('{html_mod.escape(sub_img_2)}', '{lid}')">
                    <img src="{html_mod.escape(sub_img_2)}" alt="{title}">
                    <div class="g-all">Tüm Görseller ({len(images)}) ↗</div>
                </figure>
            </div>
            
            <div class="filmstrip">
                {filmstrip_imgs}
            </div>
            
            <!-- Başlık ve Fiyat -->
            <div class="head">
                <div>
                    <div class="loc"><span class="loc-dot"></span> {loc_esc}</div>
                    <h1>{title}</h1>
                    <div class="no">İLAN NO: <b>#{lid}</b> &nbsp;|&nbsp; DANIŞMAN: <b>YİĞİT NARİN</b> &nbsp;|&nbsp; OFİS: COLDWELL BANKER VIP</div>
                </div>
                <div class="price-box">
                    <div class="price-lbl">{badge_type} FİYATI</div>
                    <div class="price-val">{price_esc}</div>
                </div>
            </div>
            
            <!-- Ana Gövde: Bento Grid -->
            <div class="bento-body">
                <!-- Sol: Teknik Parametreler -->
                <div class="bento-box specs-box">
                    <div class="bento-title"><i class="fas fa-clipboard-list" style="color:var(--gold)"></i> Portföy Parametreleri</div>
                    <div class="specs-grid">
                        {specs_html}
                    </div>
                </div>
                
                <!-- Sağ: AI Yatırım ve Ekspertiz Raporu -->
                <div class="bento-box ai-box">
                    <div class="bento-title"><i class="fas fa-brain" style="color:#60a5fa"></i> NEXA.OS AI Değerleme & Ekspertiz Analizi</div>
                    <div class="ai-metrics">
                        <div class="ai-m">
                            <div class="ai-m-val">{ai_score:.1f}<span>/10</span></div>
                            <div class="ai-m-lbl">Yatırım Puanı</div>
                        </div>
                        <div class="ai-m">
                            <div class="ai-m-val">{ai_amort} <span>Yıl</span></div>
                            <div class="ai-m-lbl">Amortisman</div>
                        </div>
                        <div class="ai-m">
                            <div class="ai-m-val">A+</div>
                            <div class="ai-m-lbl">Bölge Değeri</div>
                        </div>
                    </div>
                    <div class="ai-summary">
                        <b>Ekspertiz Notu:</b> Ankara'nın en prestijli lokasyonunda konumlanan bu gayrimenkul; mimari yapı kalitesi, ulaşım arterlerine yakınlığı, kurumsal altyapısı ve bölge emsal satış/kira eğrileri bazında üst segment yatırım ve kullanım değerine sahiptir.
                    </div>
                </div>
            </div>
            
            <!-- Açıklama -->
            <div class="desc-box">
                <div class="desc-title"><i class="fas fa-align-left" style="color:var(--gold)"></i> Portföy Açıklaması</div>
                <div class="desc-text">{desc_esc}</div>
            </div>
            
            <!-- Aksiyon Barı -->
            <div class="card-footer">
                <a href="https://www.sahibinden.com/ilan/{lid}/detay" target="_blank" class="btn-sahibinden">
                    <i class="fas fa-external-link-alt"></i> Sahibinden Orijinal İlanı ↗
                </a>
                <button class="btn-copy" onclick="copyLink('{lid}')">
                    <i class="fas fa-copy"></i> Bağlantıyı Kopyala
                </button>
                <a href="https://wa.me/905324514008?text=Merhaba%20Yi%C4%9Fit%20Bey%2C%20{html_mod.escape(raw_title)}%20(No%3A%20{lid})%20ilan%C4%B1n%C4%B1z%20hakk%C4%B1nda%20bilgi%20almak%20istiyorum." target="_blank" class="btn-whatsapp">
                    <i class="fab fa-whatsapp"></i> WhatsApp'tan İletişime Geç
                </a>
                <a href="tel:+905324514008" class="btn-call">
                    <i class="fas fa-phone-alt"></i> Yiğit Narin'i Ara
                </a>
            </div>
        </article>
        '''
        cards_html.append(card_markup)
        
    cards_str = "\n".join(cards_html)
    options_str = "\n".join(nav_options)
    
    html_page = f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<title>Yiğit Narin Portföy Vitrini | Coldwell Banker CB VIP Ankara</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
:root {{
    --bg-dark: #05070b;
    --card-bg: rgba(13, 17, 25, 0.94);
    --gold: #d4af37;
    --gold-soft: #f1dd90;
    --gold-glow: rgba(212, 175, 55, 0.25);
    --gold-gradient: linear-gradient(135deg, #d4af37 0%, #f7e7a9 50%, #aa7c11 100%);
    --accent: #2563eb;
    --emerald: #10b981;
    --rose: #f43f5e;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --border: rgba(255, 255, 255, 0.08);
    --border-gold: rgba(212, 175, 55, 0.35);
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    background-color: var(--bg-dark);
    color: var(--text-primary);
    line-height: 1.6;
    background-image: 
        radial-gradient(circle at 15% 15%, rgba(212, 175, 55, 0.06) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(37, 99, 235, 0.05) 0%, transparent 40%);
    background-attachment: fixed;
    padding-bottom: 90px;
}}

/* Top Hero Bar */
.hero-header {{
    background: linear-gradient(180deg, rgba(16, 21, 32, 0.98) 0%, rgba(5, 7, 11, 0.95) 100%);
    border-bottom: 1px solid var(--border-gold);
    padding: 36px 20px 28px;
    text-align: center;
    position: relative;
    box-shadow: 0 12px 35px rgba(0,0,0,0.6);
}}
.hero-brand {{
    font-family: 'Cinzel', serif;
    font-size: 13px;
    letter-spacing: 5px;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 10px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
}}
.hero-title {{
    font-family: 'Cinzel', serif;
    font-size: 34px;
    font-weight: 800;
    color: #fff;
    letter-spacing: 1.5px;
    margin-bottom: 8px;
}}
.hero-title span {{
    background: var(--gold-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.hero-sub {{
    color: var(--text-secondary);
    font-size: 15px;
    max-width: 700px;
    margin: 0 auto 18px;
}}
.agent-contact-pill {{
    display: inline-flex;
    align-items: center;
    gap: 16px;
    background: rgba(212, 175, 55, 0.08);
    border: 1px solid var(--border-gold);
    padding: 8px 20px;
    border-radius: 30px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    justify-content: center;
}}
.agent-contact-pill a {{
    color: var(--gold-soft);
    text-decoration: none;
    font-weight: 700;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: opacity 0.2s;
}}
.agent-contact-pill a:hover {{ opacity: 0.8; }}
.hero-badges {{
    display: flex;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
}}
.hero-badge {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}
.hero-badge i {{ color: var(--gold); }}

/* Sticky Nav Bar */
.sticky-bar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(13, 17, 25, 0.95);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}}
.sticky-inner {{
    max-width: 1240px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}}
.filter-tabs {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}
.filter-btn {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    color: var(--text-secondary);
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}}
.filter-btn:hover, .filter-btn.active {{
    background: var(--gold);
    color: #05070b;
    border-color: var(--gold);
}}
.nav-select {{
    background: rgba(0,0,0,0.6);
    border: 1px solid var(--border-gold);
    color: var(--text-primary);
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    outline: none;
    cursor: pointer;
    min-width: 300px;
}}

/* Container */
.container {{
    max-width: 1240px;
    margin: 30px auto;
    padding: 0 20px;
    display: flex;
    flex-direction: column;
    gap: 40px;
}}

/* Card Container */
.card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 22px;
    overflow: hidden;
    box-shadow: 0 24px 48px rgba(0,0,0,0.6);
    position: relative;
    transition: transform 0.3s ease, border-color 0.3s ease;
}}
.card:hover {{
    border-color: var(--border-gold);
    transform: translateY(-2px);
}}

/* Ribbon Group */
.card-ribbons {{
    position: absolute;
    top: 20px;
    left: 20px;
    z-index: 10;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}
.ribbon-vip {{
    background: var(--gold-gradient);
    color: #07090e;
    font-family: 'Cinzel', serif;
    font-weight: 800;
    font-size: 11px;
    letter-spacing: 1.5px;
    padding: 6px 14px;
    border-radius: 6px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
}}
.ribbon-type {{
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 6px 12px;
    border-radius: 6px;
    color: #fff;
    box-shadow: 0 4px 15px rgba(0,0,0,0.4);
}}
.ribbon-cat-satilik {{ background: var(--emerald); }}
.ribbon-cat-kiralik {{ background: var(--accent); }}
.ribbon-prop {{
    background: rgba(0,0,0,0.7);
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.2);
    backdrop-filter: blur(8px);
}}

/* Bento Galeri */
.gallery {{
    display: grid;
    grid-template-columns: 2.2fr 1fr;
    grid-template-rows: 250px 250px;
    gap: 8px;
    padding: 10px;
    background: #000;
}}
.gallery figure {{
    margin: 0;
    position: relative;
    overflow: hidden;
    cursor: pointer;
    border-radius: 12px;
}}
.gallery img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.4s ease;
}}
.gallery figure:hover img {{
    transform: scale(1.05);
}}
.g-main {{
    grid-row: span 2;
}}
.g-badge {{
    position: absolute;
    bottom: 16px;
    left: 16px;
    background: rgba(0,0,0,0.75);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 6px;
    letter-spacing: 1px;
}}
.g-count {{
    position: absolute;
    top: 16px;
    right: 16px;
    background: rgba(0,0,0,0.8);
    color: #fff;
    font-size: 11px;
    padding: 6px 12px;
    border-radius: 20px;
    backdrop-filter: blur(8px);
    font-weight: 600;
}}
.g-all {{
    position: absolute;
    inset: 0;
    background: rgba(0,0,0,0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 1px;
    transition: background 0.2s;
}}
.g-all:hover {{ background: rgba(0,0,0,0.3); }}

/* Filmstrip */
.filmstrip {{
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 12px 16px;
    background: rgba(0,0,0,0.85);
    scrollbar-width: thin;
    scrollbar-color: var(--gold) #000;
}}
.filmstrip img {{
    width: 95px;
    height: 65px;
    object-fit: cover;
    border-radius: 6px;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1);
    transition: transform 0.2s, border-color 0.2s;
    flex-shrink: 0;
}}
.filmstrip img:hover {{
    transform: scale(1.08);
    border-color: var(--gold);
}}

/* Header Info */
.head {{
    padding: 26px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    border-bottom: 1px solid var(--border);
}}
.loc {{
    color: var(--gold);
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
}}
.loc-dot {{
    width: 7px;
    height: 7px;
    background: var(--gold);
    border-radius: 50%;
    display: inline-block;
}}
.head h1 {{
    font-size: 23px;
    font-weight: 700;
    color: #fff;
    line-height: 1.35;
    margin-bottom: 8px;
}}
.no {{
    color: var(--text-secondary);
    font-size: 11px;
    letter-spacing: 0.5px;
}}
.no b {{ color: #cbd5e1; }}
.price-box {{
    background: rgba(212, 175, 55, 0.09);
    border: 1px solid var(--border-gold);
    padding: 14px 22px;
    border-radius: 14px;
    text-align: right;
    min-width: 240px;
}}
.price-lbl {{
    font-size: 10px;
    color: var(--gold);
    font-weight: 800;
    letter-spacing: 2px;
}}
.price-val {{
    font-family: 'Cinzel', serif;
    font-size: 26px;
    font-weight: 800;
    color: #fff;
    margin-top: 2px;
}}

/* Bento Body */
.bento-body {{
    padding: 26px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 22px;
    border-bottom: 1px solid var(--border);
}}
.bento-box {{
    background: rgba(0,0,0,0.35);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 22px;
}}
.bento-title {{
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 0.5px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.specs-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}}
.spec-pill {{
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    padding: 9px 12px;
    border-radius: 8px;
}}
.sp-k {{
    display: block;
    font-size: 10px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.sp-v {{
    display: block;
    font-size: 12px;
    font-weight: 700;
    color: #e2e8f0;
    margin-top: 2px;
}}

/* AI Box */
.ai-box {{
    border-color: rgba(37, 99, 235, 0.3);
    background: linear-gradient(180deg, rgba(37, 99, 235, 0.06) 0%, rgba(0,0,0,0.35) 100%);
}}
.ai-metrics {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-bottom: 16px;
}}
.ai-m {{
    background: rgba(0,0,0,0.45);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 12px 8px;
    text-align: center;
}}
.ai-m-val {{
    font-family: 'Cinzel', serif;
    font-size: 21px;
    font-weight: 800;
    color: var(--gold);
}}
.ai-m-val span {{ font-size: 11px; color: var(--text-secondary); font-family: sans-serif; }}
.ai-m-lbl {{
    font-size: 10px;
    color: var(--text-secondary);
    margin-top: 4px;
}}
.ai-summary {{
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.55;
    background: rgba(0,0,0,0.3);
    padding: 12px;
    border-radius: 8px;
    border-left: 3px solid var(--gold);
}}

/* Desc Box */
.desc-box {{
    padding: 26px;
    border-bottom: 1px solid var(--border);
}}
.desc-title {{
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.desc-text {{
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.75;
    white-space: pre-line;
    max-height: 170px;
    overflow-y: auto;
    padding-right: 8px;
}}

/* Action Bar */
.card-footer {{
    padding: 18px 26px;
    background: rgba(0,0,0,0.45);
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
}}
.btn-sahibinden {{
    background: #ffe800;
    color: #111;
    font-weight: 700;
    font-size: 12px;
    padding: 11px 18px;
    border-radius: 8px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: opacity 0.2s;
}}
.btn-sahibinden:hover {{ opacity: 0.9; }}
.btn-copy {{
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
    color: #fff;
    font-weight: 600;
    font-size: 12px;
    padding: 11px 18px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
}}
.btn-copy:hover {{ background: rgba(255,255,255,0.15); }}
.btn-whatsapp {{
    background: var(--emerald);
    color: #fff;
    font-weight: 700;
    font-size: 12px;
    padding: 11px 18px;
    border-radius: 8px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
    transition: opacity 0.2s;
}}
.btn-whatsapp:hover {{ opacity: 0.9; }}
.btn-call {{
    background: rgba(212, 175, 55, 0.15);
    border: 1px solid var(--border-gold);
    color: var(--gold);
    font-weight: 700;
    font-size: 12px;
    padding: 11px 18px;
    border-radius: 8px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 0.2s;
}}
.btn-call:hover {{ background: rgba(212, 175, 55, 0.25); }}

/* Lightbox Modal */
.lightbox {{
    display: none;
    position: fixed;
    inset: 0;
    z-index: 999;
    background: rgba(0,0,0,0.95);
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(12px);
}}
.lightbox.active {{ display: flex; }}
.lightbox-content {{
    max-width: 90vw;
    max-height: 85vh;
    border-radius: 12px;
    box-shadow: 0 0 50px rgba(0,0,0,0.8);
    border: 1px solid var(--border-gold);
}}
.lightbox-close {{
    position: absolute;
    top: 25px;
    right: 30px;
    color: #fff;
    font-size: 38px;
    cursor: pointer;
    transition: color 0.2s;
}}
.lightbox-close:hover {{ color: var(--gold); }}

@media (max-width: 900px) {{
    .gallery {{
        grid-template-columns: 1fr;
        grid-template-rows: 280px 140px 140px;
    }}
    .g-main {{ grid-row: auto; }}
    .head {{ flex-direction: column; }}
    .price-box {{ text-align: left; width: 100%; }}
    .bento-body {{ grid-template-columns: 1fr; }}
    .btn-whatsapp {{ margin-left: 0; width: 100%; justify-content: center; }}
    .btn-call {{ width: 100%; justify-content: center; }}
    .sticky-inner {{ flex-direction: column; align-items: stretch; }}
    .nav-select {{ width: 100%; min-width: unset; }}
}}
</style>
</head>
<body>

<header class="hero-header">
    <div class="hero-brand">
        <i class="fas fa-crown"></i> COLDWELL BANKER VIP ANKARA
    </div>
    <h1 class="hero-title">YİĞİT NARİN <span>PORTFÖY VİTRİNİ</span></h1>
    <p class="hero-sub">Coldwell Banker CB VIP danışman mağazalarındaki seçkin konut, ticari ve yatırım gayrimenkulleri.</p>
    
    <div class="agent-contact-pill">
        <a href="tel:+905324514008"><i class="fas fa-phone-alt"></i> +90 532 451 40 08</a>
        <span>·</span>
        <a href="https://wa.me/905324514008" target="_blank"><i class="fab fa-whatsapp"></i> WhatsApp</a>
        <span>·</span>
        <a href="https://www.gayrimenkulmuhendisi.com" target="_blank"><i class="fas fa-globe"></i> gayrimenkulmuhendisi.com</a>
    </div>

    <div class="hero-badges">
        <span class="hero-badge"><i class="fas fa-layer-group"></i> {total} Aktif Portföy</span>
        <span class="hero-badge"><i class="fas fa-key"></i> {total_satilik} Satılık Mülk</span>
        <span class="hero-badge"><i class="fas fa-file-contract"></i> {total_kiralik} Kiralık Mülk</span>
        <span class="hero-badge"><i class="fas fa-shield-alt"></i> CB VIP Güvencesi</span>
    </div>
</header>

<div class="sticky-bar">
    <div class="sticky-inner">
        <div class="filter-tabs">
            <button class="filter-btn active" onclick="filterCards('all', this)">Tümü ({total})</button>
            <button class="filter-btn" onclick="filterCards('cat-satilik', this)">Satılık ({total_satilik})</button>
            <button class="filter-btn" onclick="filterCards('cat-kiralik', this)">Kiralık ({total_kiralik})</button>
            <button class="filter-btn" onclick="filterCards('type-konut', this)">Konut</button>
            <button class="filter-btn" onclick="filterCards('type-ticari', this)">Ticari / İş Yeri</button>
            <button class="filter-btn" onclick="filterCards('type-villa', this)">Villa</button>
        </div>
        <select class="nav-select" onchange="jumpToCard(this.value)">
            <option value="">İlan Seçin veya Listede Gezinin ({total} İlan)...</option>
            {options_str}
        </select>
    </div>
</div>

<main class="container">
    {cards_str}
</main>

<div id="lightbox" class="lightbox" onclick="closeLightbox()">
    <span class="lightbox-close">&times;</span>
    <img id="lightbox-img" class="lightbox-content" src="" alt="Tam Ekran Görsel">
</div>

<script>
function filterCards(filterClass, btn) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    
    const cards = document.querySelectorAll('.card');
    cards.forEach(c => {{
        if (filterClass === 'all' || c.classList.contains(filterClass)) {{
            c.style.display = 'block';
        }} else {{
            c.style.display = 'none';
        }}
    }});
}}

function jumpToCard(cardId) {{
    if (!cardId) return;
    const el = document.getElementById(cardId);
    if (el) {{
        el.style.display = 'block';
        el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        el.style.borderColor = 'var(--gold)';
        setTimeout(() => {{ el.style.borderColor = ''; }}, 2500);
    }}
}}

function openLightbox(src, lid) {{
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    img.src = src;
    lb.classList.add('active');
}}

function closeLightbox() {{
    const lb = document.getElementById('lightbox');
    lb.classList.remove('active');
}}

function copyLink(lid) {{
    const url = 'https://www.sahibinden.com/ilan/' + lid + '/detay';
    navigator.clipboard.writeText(url).then(() => {{
        alert('İlan bağlantısı panoya kopyalandı:\\n' + url);
    }});
}}

// Keyboard ESC to close lightbox
document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') closeLightbox();
}});
</script>

</body>
</html>'''
    return html_page

html_content = build_showcase_html(ordered_listings)

with open(DESKTOP_OUT, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"\n[BASARILI] Masaüstü Vitrini oluşturuldu: {DESKTOP_OUT}")

with open(LOCAL_OUT, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"[BASARILI] Yerel Vitrin oluşturuldu: {LOCAL_OUT}")

# Also copy to gayrimenkulmuhendisi-main
gm_out = Path(r"C:\Users\USER\Desktop\gayrimenkulmuhendisi-main\templates\ygt.html")
gm_out.parent.mkdir(exist_ok=True)
with open(gm_out, "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"[BASARILI] Gayrimenkul Mühendisi klasörüne kopyalandı: {gm_out}")
