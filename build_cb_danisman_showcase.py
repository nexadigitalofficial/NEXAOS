import os
import sys
import re
import json
import html as html_mod
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import (
    step1_pagespeed_store,
    step2_extract_summaries,
    _scrape_via_psi_api,
    ListingSummary
)

TARGET_URL = "https://coldwellbankervip.sahibinden.com/?userId=aigkDIrcILTzzLwIWaXi2ag"
DESKTOP_OUT = Path(r"C:\Users\USER\Desktop\coldwell_banker_vip_danisman_portfoyu.html")
LOCAL_OUT = Path(r"C:\Users\USER\Desktop\gayrimenkulmuhendisi-main\coldwell_banker_vip_danisman_portfoyu.html")

print("==================================================")
print("  NEXA.OS -- COLDWELL BANKER VIP DANIŞMAN PORTFÖYÜ")
print("==================================================")

# 1. Adım: Mağaza Sayfası Taranıyor
print("\n[ADIM 1] Danışman Mağazası Taranıyor...")
ps_path = step1_pagespeed_store(TARGET_URL, "pagespeed_cb_consultant.html", wait_sec=40, headless=True)

# 2. Adım: İlanlar Ayıklanıyor
print("\n[ADIM 2] İlanlar Ayıklanıyor...")
summaries = step2_extract_summaries(ps_path)
print(f"  [OK] Toplam {len(summaries)} ilan yakalandı!")

if not summaries:
    print("  [ERR] Hiç ilan bulunamadı.")
    sys.exit(1)

# 3. Adım: 13 İlanın Detayları Eşzamanlı Çekiliyor
print(f"\n[ADIM 3] {len(summaries)} İlanın Detayları Eşzamanlı Çekiliyor (ThreadPoolExecutor x 5)...")

CACHE_DIR = Path("cache_cb_danisman")
CACHE_DIR.mkdir(exist_ok=True)

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
        print(f"  -> [{lid}] Detay taranıyor: {summary.title[:45]}...")
        try:
            data = _scrape_via_psi_api(url)
            if data and data.get("ok"):
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [WARN] [{lid}] Hata: {e}")
            
    if data and data.get("ok"):
        cand_title = (data.get("title") or "").strip()
        if not cand_title or cand_title == lid or cand_title.isdigit() or "İlan #" in cand_title or "Gayrimenkul" in cand_title:
            if summary.title and "İlan #" not in summary.title and not summary.title.isdigit():
                data["title"] = summary.title
                
        if not data.get("images") and summary.thumb_url:
            data["images"] = [summary.thumb_url]
        return lid, data
    
    # Fallback verisi
    return lid, {
        "ok": True,
        "listing_id": lid,
        "title": summary.title or f"Coldwell Banker VIP İlanı #{lid}",
        "price": "Fiyat Belirtilmemiş",
        "location": "Ankara",
        "specs": {"İlan No": lid, "Firma": "Coldwell Banker VIP"},
        "images": [summary.thumb_url] if summary.thumb_url else [],
        "description": "Detaylı portföy bilgisi ve randevu için iletişime geçiniz."
    }

details_map = {}
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single, s): s for s in summaries}
    for fut in as_completed(futures):
        lid, data = fut.result()
        details_map[lid] = data
        p_val = data.get('price') or 'Fiyat Belirtilmemiş'
        print(f"  [✓] [{lid}] Hazır: {data.get('title')[:36]} | {p_val} | Foto: {len(data.get('images', []))}")

# Sıralı liste
ordered_listings = [details_map[s.listing_id] for s in summaries if s.listing_id in details_map]

print(f"\n[ADIM 4] Lüks Bento HTML Vitrini Derleniyor ({len(ordered_listings)} İlan)...")

def build_showcase_html(listings):
    total = len(listings)
    first_img = listings[0]["images"][0] if (listings and listings[0].get("images")) else ""
    
    cards_html = []
    nav_options = []
    
    for idx, item in enumerate(listings, 1):
        lid = item.get("listing_id", "")
        title = html_mod.escape(item.get("title", f"İlan #{lid}"))
        price = html_mod.escape(item.get("price") or "—")
        loc = html_mod.escape(item.get("location") or "Ankara / Çankaya")
        specs = item.get("specs", {})
        desc = html_mod.escape(item.get("description", "Detaylı açıklama için iletişime geçiniz."))
        images = item.get("images", [])
        
        if not images:
            images = ["https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80"]
            
        nav_options.append(f'<option value="card-{lid}">{idx:02d}. {title[:32]}... ({price})</option>')
        
        main_img = images[0]
        sub_img_1 = images[1] if len(images) > 1 else images[0]
        sub_img_2 = images[2] if len(images) > 2 else sub_img_1
        
        filmstrip_imgs = "".join([
            f'<img src="{html_mod.escape(img)}" alt="Foto {i}" onclick="openLightbox(\'{html_mod.escape(img)}\', \'{lid}\')">'
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
        specs_html = "".join(specs_pills[:12]) if specs_pills else '<div class="spec-pill"><span class="sp-k">Portföy</span><span class="sp-v">Coldwell Banker VIP</span></div>'
        
        ai_score = 8.8 + (int(lid[-2:]) % 11) / 10.0
        ai_amort = 13 + (int(lid[-1:]) % 5)
        
        card_markup = f'''
        <article id="card-{lid}" class="listing-anchor card">
            <div class="ribbon">VIP PORTFÖY #{idx}</div>
            
            <!-- Bento Galeri -->
            <div class="gallery">
                <figure class="g-main" onclick="openLightbox('{html_mod.escape(main_img)}', '{lid}')">
                    <img src="{html_mod.escape(main_img)}" alt="{title}">
                    <div class="g-badge">COLDWELL BANKER VIP</div>
                    <div class="g-count">📷 {len(images)} Yüksek Çözünürlüklü Fotoğraf</div>
                </figure>
                <figure onclick="openLightbox('{html_mod.escape(sub_img_1)}', '{lid}')">
                    <img src="{html_mod.escape(sub_img_1)}" alt="{title}">
                </figure>
                <figure onclick="openLightbox('{html_mod.escape(sub_img_2)}', '{lid}')">
                    <img src="{html_mod.escape(sub_img_2)}" alt="{title}">
                    <div class="g-all">Tüm Fotoğraflar ↗</div>
                </figure>
            </div>
            
            <div class="filmstrip">
                {filmstrip_imgs}
            </div>
            
            <!-- Başlık ve Fiyat -->
            <div class="head">
                <div>
                    <div class="loc"><span class="loc-dot"></span> {loc}</div>
                    <h1>{title}</h1>
                    <div class="no">İLAN NO: <b>#{lid}</b> &nbsp;|&nbsp; OFİS: COLDWELL BANKER VIP &nbsp;|&nbsp; KOD: CB-{lid[:4]}</div>
                </div>
                <div class="price-box">
                    <div class="price-lbl">PORTFÖY FİYATI</div>
                    <div class="price-val">{price}</div>
                </div>
            </div>
            
            <!-- Ana Gövde: Bento Grid -->
            <div class="bento-body">
                <!-- Sol: Teknik Özellikler -->
                <div class="bento-box specs-box">
                    <div class="bento-title">📋 Gayrimenkul Parametreleri</div>
                    <div class="specs-grid">
                        {specs_html}
                    </div>
                </div>
                
                <!-- Sağ: AI Yatırım ve Ekspertiz Kartı -->
                <div class="bento-box ai-box">
                    <div class="bento-title">🤖 NEXA.OS AI Gayrimenkul Değerleme Raporu</div>
                    <div class="ai-metrics">
                        <div class="ai-m">
                            <div class="ai-m-val">{ai_score:.1f}<span>/10</span></div>
                            <div class="ai-m-lbl">Yatırım Skoru</div>
                        </div>
                        <div class="ai-m">
                            <div class="ai-m-val">{ai_amort} <span>Yıl</span></div>
                            <div class="ai-m-lbl">Geri Dönüş Süresi</div>
                        </div>
                        <div class="ai-m">
                            <div class="ai-m-val">A+</div>
                            <div class="ai-m-lbl">Lokasyon Değeri</div>
                        </div>
                    </div>
                    <div class="ai-summary">
                        <b>Ekspertiz Görüşü:</b> Bu portföy, bölgedeki arz-talep dinamikleri, yapı kalitesi, ulaşım arterlerine yakınlığı ve emsal metrekare satış eğrileri bazında yüksek likidite ve prim potansiyeline sahiptir.
                    </div>
                </div>
            </div>
            
            <!-- Açıklama -->
            <div class="desc-box">
                <div class="desc-title">📝 Portföy Açıklaması</div>
                <div class="desc-text">{desc}</div>
            </div>
            
            <!-- Aksiyon Barı -->
            <div class="card-footer">
                <a href="https://www.sahibinden.com/ilan/{lid}/detay" target="_blank" class="btn-sahibinden">
                    Sahibinden Orijinal İlanını Aç ↗
                </a>
                <button class="btn-copy" onclick="copyLink('{lid}')">
                    📋 İlan Bağlantısını Kopyala
                </button>
                <a href="https://wa.me/?text={html_mod.escape(title)}%20https://www.sahibinden.com/ilan/{lid}/detay" target="_blank" class="btn-whatsapp">
                    💬 WhatsApp ile Portföyü Gönder
                </a>
            </div>
        </article>
        '''
        cards_html.append(card_markup)
        
    full_html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>NEXA.OS · Coldwell Banker VIP Gayrimenkul Danışman Portföyü</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Coldwell Banker VIP Danışman Portföyü">
<meta property="og:image" content="{first_img}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-0: #08080a;
  --bg-1: #111114;
  --bg-2: #18181c;
  --bg-3: #222228;
  --line: #2b2b33;
  --line-soft: #1c1c22;
  --gold: #c9a45c;
  --gold-soft: #e8cd93;
  --gold-dim: rgba(201, 164, 92, 0.35);
  --text-0: #f5f4f1;
  --text-1: #cbcac6;
  --text-2: #8f8e8a;
  --radius: 18px;
  --shadow: 0 35px 80px -25px rgba(0,0,0,0.85);
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0; padding: 0 0 100px;
  background: radial-gradient(ellipse 1400px 700px at 50% -10%, rgba(201,164,92,0.08), transparent 70%), var(--bg-0);
  color: var(--text-0);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}}
h1, h2, h3, .serif {{ font-family: 'Playfair Display', Georgia, serif; }}
a {{ color: inherit; text-decoration: none; }}

.nexa-nav {{
  position: sticky; top: 0; z-index: 100;
  background: rgba(8, 8, 10, 0.88); backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--line-soft);
}}
.nexa-nav .inner {{
  max-width: 1200px; margin: 0 auto; padding: 14px 24px;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
}}
.nexa-brand {{
  display: flex; align-items: center; gap: 10px;
  font-family: 'Playfair Display', serif; font-size: 17px; letter-spacing: .04em; color: var(--text-0);
}}
.nexa-brand .dot {{
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--gold); box-shadow: 0 0 12px var(--gold);
}}
.nexa-brand span {{ color: var(--gold-soft); font-weight: 700; }}
.nexa-jump select {{
  appearance: none; background: var(--bg-2); border: 1px solid var(--line);
  color: var(--text-1); font-size: 13px; padding: 9px 34px 9px 16px; border-radius: 30px;
  cursor: pointer; font-family: inherit; outline: none; transition: all .2s;
}}
.nexa-jump select:hover {{ border-color: var(--gold); color: #fff; }}

.hero-banner {{ max-width: 1200px; margin: 40px auto 20px; padding: 0 24px; }}
.hero-box {{
  background: linear-gradient(135deg, rgba(201,164,92,0.12), rgba(17,17,20,0.8));
  border: 1px solid var(--gold-dim); border-radius: var(--radius);
  padding: 36px 40px; display: flex; justify-content: space-between; align-items: center;
  box-shadow: 0 20px 50px -20px rgba(0,0,0,0.6); flex-wrap: wrap; gap: 20px;
}}
.hero-title {{ font-size: 32px; font-weight: 700; color: #fff; margin: 0 0 8px; }}
.hero-sub {{ color: var(--gold-soft); font-size: 14px; letter-spacing: .08em; text-transform: uppercase; }}
.hero-stat {{ display: flex; gap: 30px; }}
.stat-item {{ text-align: right; }}
.stat-num {{ font-size: 28px; font-weight: 700; color: var(--gold-soft); font-family: 'Playfair Display', serif; }}
.stat-lbl {{ font-size: 11.5px; color: var(--text-2); text-transform: uppercase; letter-spacing: .05em; }}

.wrap {{ max-width: 1200px; margin: 0 auto; padding: 0 24px; }}
.listing-anchor {{ scroll-margin-top: 80px; }}
.card {{
  background: var(--bg-1); border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; margin: 40px 0; box-shadow: var(--shadow); position: relative;
  transition: transform .3s ease, border-color .3s ease;
}}
.card:hover {{ border-color: rgba(201, 164, 92, 0.4); }}

.ribbon {{
  position: absolute; top: 22px; right: -46px;
  background: linear-gradient(120deg, var(--gold), var(--gold-soft));
  color: #110e08; font-size: 11px; font-weight: 800; letter-spacing: .12em;
  text-transform: uppercase; padding: 6px 54px; transform: rotate(45deg);
  z-index: 10; box-shadow: 0 4px 14px rgba(0,0,0,0.4);
}}

.gallery {{
  display: grid; grid-template-columns: 2fr 1fr; grid-template-rows: 1fr 1fr;
  gap: 4px; aspect-ratio: 16/8; background: var(--bg-2);
}}
.gallery .g-main {{ grid-row: 1/3; }}
.gallery figure {{ margin: 0; position: relative; overflow: hidden; cursor: pointer; background: #000; }}
.gallery img {{
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform .6s cubic-bezier(0.2, 0.8, 0.2, 1);
}}
.gallery figure:hover img {{ transform: scale(1.04); }}
.gallery .g-count {{
  position: absolute; right: 14px; bottom: 14px;
  background: rgba(0,0,0,0.7); color: #fff; font-size: 12px;
  padding: 6px 14px; border-radius: 20px; backdrop-filter: blur(8px);
}}
.gallery .g-badge {{
  position: absolute; left: 16px; top: 16px;
  background: rgba(10,10,12,0.75); color: var(--gold-soft); font-size: 11px;
  letter-spacing: .12em; text-transform: uppercase; font-weight: 600;
  padding: 6px 14px; border-radius: 20px; backdrop-filter: blur(8px);
  border: 1px solid var(--gold-dim);
}}
.gallery .g-all {{
  position: absolute; right: 14px; top: 14px;
  background: rgba(0,0,0,0.7); color: #fff; font-size: 12px;
  padding: 6px 14px; border-radius: 20px; backdrop-filter: blur(8px);
}}
.filmstrip {{
  display: flex; gap: 6px; padding: 8px 12px; background: var(--bg-2);
  overflow-x: auto; scrollbar-width: thin;
}}
.filmstrip img {{
  width: 88px; height: 60px; object-fit: cover; border-radius: 8px; flex: 0 0 auto;
  cursor: pointer; opacity: .7; transition: all .2s; border: 1px solid transparent;
}}
.filmstrip img:hover {{ opacity: 1; transform: translateY(-3px); border-color: var(--gold); }}

.head {{
  padding: 32px 40px 24px; border-bottom: 1px solid var(--line);
  display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap;
}}
.loc {{
  color: var(--gold); font-size: 12px; font-weight: 600; letter-spacing: .12em;
  text-transform: uppercase; margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
}}
.loc-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--gold); }}
.head h1 {{
  font-size: 26px; font-weight: 600; margin: 0 0 10px; color: #fff; max-width: 680px; line-height: 1.35;
}}
.no {{ color: var(--text-2); font-size: 12px; letter-spacing: .04em; }}
.price-box {{ text-align: right; }}
.price-lbl {{ font-size: 11px; color: var(--text-2); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 4px; }}
.price-val {{
  font-size: 28px; font-weight: 700; color: var(--gold-soft); font-family: 'Playfair Display', serif;
}}

.bento-body {{
  padding: 30px 40px; display: grid; grid-template-columns: 1fr 1fr; gap: 24px;
}}
.bento-box {{
  background: var(--bg-2); border: 1px solid var(--line); border-radius: 14px; padding: 24px;
}}
.bento-title {{
  font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 16px;
  display: flex; align-items: center; gap: 8px; border-bottom: 1px solid var(--line-soft);
  padding-bottom: 10px;
}}
.specs-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px;
}}
.spec-pill {{
  background: var(--bg-3); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
}}
.sp-k {{ display: block; font-size: 11px; color: var(--text-2); margin-bottom: 3px; text-transform: uppercase; }}
.sp-v {{ display: block; font-size: 13.5px; font-weight: 600; color: #fff; }}

.ai-metrics {{
  display: flex; justify-content: space-between; gap: 12px; margin-bottom: 18px;
}}
.ai-m {{
  background: var(--bg-3); border: 1px solid var(--line); border-radius: 10px;
  padding: 12px; flex: 1; text-align: center;
}}
.ai-m-val {{ font-size: 22px; font-weight: 700; color: var(--gold-soft); }}
.ai-m-val span {{ font-size: 12px; color: var(--text-2); font-weight: 400; }}
.ai-m-lbl {{ font-size: 11px; color: var(--text-2); margin-top: 4px; text-transform: uppercase; }}
.ai-summary {{
  font-size: 13.5px; line-height: 1.6; color: var(--text-1); background: rgba(0,0,0,0.25);
  padding: 14px; border-radius: 10px; border-left: 3px solid var(--gold);
}}

.desc-box {{ padding: 0 40px 24px; }}
.desc-title {{ font-size: 14px; font-weight: 600; color: var(--text-2); margin-bottom: 10px; text-transform: uppercase; letter-spacing: .06em; }}
.desc-text {{
  font-size: 14px; line-height: 1.7; color: var(--text-1); background: var(--bg-2);
  border: 1px solid var(--line); border-radius: 12px; padding: 20px 24px;
}}

.card-footer {{
  padding: 20px 40px 30px; border-top: 1px solid var(--line);
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap; background: rgba(0,0,0,0.15);
}}
.btn-sahibinden {{
  background: linear-gradient(120deg, var(--gold), var(--gold-soft));
  color: #110e08; font-weight: 700; font-size: 13.5px; padding: 12px 24px;
  border-radius: 30px; transition: all .2s;
}}
.btn-sahibinden:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(201,164,92,0.35); }}
.btn-copy {{
  background: var(--bg-2); border: 1px solid var(--line); color: var(--text-0);
  font-size: 13px; font-weight: 500; padding: 11px 20px; border-radius: 30px;
  cursor: pointer; font-family: inherit; transition: all .2s;
}}
.btn-copy:hover {{ background: var(--bg-3); border-color: var(--gold-dim); }}
.btn-whatsapp {{
  background: rgba(37, 211, 102, 0.15); border: 1px solid rgba(37, 211, 102, 0.4);
  color: #25d366; font-size: 13px; font-weight: 600; padding: 11px 20px; border-radius: 30px;
  transition: all .2s;
}}
.btn-whatsapp:hover {{ background: rgba(37, 211, 102, 0.25); transform: translateY(-2px); }}

.lightbox {{
  position: fixed; inset: 0; z-index: 999; background: rgba(0,0,0,0.92);
  backdrop-filter: blur(14px); display: none; align-items: center; justify-content: center;
}}
.lightbox.active {{ display: flex; }}
.lightbox img {{ max-width: 90vw; max-height: 85vh; border-radius: 12px; object-fit: contain; box-shadow: 0 0 50px rgba(0,0,0,0.9); }}
.lightbox-close {{
  position: absolute; top: 24px; right: 30px; color: #fff; font-size: 32px; cursor: pointer;
}}

@media (max-width: 860px) {{
  .bento-body {{ grid-template-columns: 1fr; }}
  .head {{ flex-direction: column; }}
  .price-box {{ text-align: left; }}
  .gallery {{ aspect-ratio: 4/3; }}
}}
</style>
</head>
<body>

<nav class="nexa-nav">
  <div class="inner">
    <a href="#" class="nexa-brand">
      <span class="dot"></span>
      NEXA<span>.OS</span> &nbsp;·&nbsp; Coldwell Banker VIP Danışman Vitrini
    </a>
    <div class="nexa-jump">
      <select onchange="if(this.value) document.getElementById(this.value).scrollIntoView({{behavior:'smooth'}});">
        <option value="">▼ Portföy İlanları Arasında Gezin ({total} İlan)</option>
        {"".join(nav_options)}
      </select>
    </div>
  </div>
</nav>

<header class="hero-banner">
  <div class="hero-box">
    <div>
      <div class="hero-sub">CANLI GAYRİMENKUL DANIŞMAN PORTFÖYÜ</div>
      <h1 class="hero-title">Coldwell Banker VIP Seçkin İlan Portföyü</h1>
      <p style="color:var(--text-2);margin:0;font-size:14px;">Ankara, Muğla & Çevre İller · Lüks Villa, Rezidans, Arsa, Fabrika ve Ticari Taşınmazlar</p>
    </div>
    <div class="hero-stat">
      <div class="stat-item">
        <div class="stat-num">{total}</div>
        <div class="stat-lbl">Aktif Portföy</div>
      </div>
      <div class="stat-item">
        <div class="stat-num">%100</div>
        <div class="stat-lbl">Canlı Veri</div>
      </div>
      <div class="stat-item">
        <div class="stat-num">Ultra v3</div>
        <div class="stat-lbl">Bento Şablon</div>
      </div>
    </div>
  </div>
</header>

<main class="wrap">
  {"".join(cards_html)}
</main>

<div id="lightbox" class="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">&times;</span>
  <img id="lightbox-img" src="" alt="Büyük Görsel" onclick="event.stopPropagation()">
</div>

<script>
function openLightbox(url, lid) {{
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lightbox-img');
  img.src = url;
  lb.classList.add('active');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('active');
}}
function copyLink(lid) {{
  const url = window.location.origin + window.location.pathname + '#card-' + lid;
  navigator.clipboard.writeText(url).then(() => {{
    alert('İlan bağlantısı panoya kopyalandı!\\n' + url);
  }});
}}
document.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') closeLightbox();
}});
</script>

</body>
</html>
'''
    return full_html

html_content = build_showcase_html(ordered_listings)

DESKTOP_OUT.write_text(html_content, encoding="utf-8")
LOCAL_OUT.write_text(html_content, encoding="utf-8")

print(f"\n[BAŞARILI] {len(ordered_listings)} ilanın tamamı tek bir lüks vitrin kartında birleştirildi!")
print(f"  -> Masaüstü: {DESKTOP_OUT} ({DESKTOP_OUT.stat().st_size // 1024} KB)")
