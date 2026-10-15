# -*- coding: utf-8 -*-
"""
nexa_social_autopilot.py
Coldwell Banker VIP Ankara — Otonom Sosyal Medya & Pazarlama Planlayıcı Motoru (v3.0 ENTERPRISE)
Tüm veritabanı (35 Drive Projesi + 11 Canlı CB VIP Portföyü) ile %100 kapsayıcı ve tam otonom çalışır.
Haftanın 7 günü için yatırımcı psikolojisi, peak yayın saatleri, dinamik kanca (hook) motoru ve 4 haftalık rotasyon içerir.
"""

import os
import json
import re
import urllib.parse
import tempfile
import threading
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Portföy AI Persona Swarm Entegrasyonu & Önbellek ─────────────────────────
_persona_cache_file = BASE_DIR / "static" / "data" / "portfolio_persona_intelligence.json"
_persona_lock = threading.RLock()
_persona_synthesizer = None

def _get_synthesizer():
    global _persona_synthesizer
    if _persona_synthesizer is None:
        try:
            from intelligence.swarm.persona_swarm import PersonaSwarmSynthesizer
            _persona_synthesizer = PersonaSwarmSynthesizer()
        except Exception:
            _persona_synthesizer = None
    return _persona_synthesizer

def get_persona_intel_for_item(item, is_project=True):
    """
    İlan veya proje için Persona Swarm istihbaratını getirir.
    Önbellekte varsa anında çeker, yoksa anlık hafif sentezleyiciyle türetir ve önbelleğe yazar.
    """
    if not item:
        return {}
    
    url = item.get("link") or item.get("url") or (f"/projeler?id={item.get('id')}" if item.get("id") else "")
    title = item.get("title") or item.get("name") or ""
    item_id = str(item.get("id") or "")
    
    # 1. Önbellek kontrolü
    with _persona_lock:
        if _persona_cache_file.exists():
            try:
                with open(_persona_cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    for k in (url, title, item_id):
                        if k and k in cache:
                            return cache[k]
                    for k, v in cache.items():
                        if title and len(title) > 5 and (title.lower() in k.lower() or k.lower() in title.lower()):
                            return v
            except Exception:
                pass

    # 2. Dinamik Sentez
    syn = _get_synthesizer()
    if syn:
        try:
            target_dict = {
                "title": title,
                "property_type": item.get("category", "Konut"),
                "type": "Satılık" if is_project else (item.get("type") or "Satılık"),
                "price": item.get("price_display") or item.get("price") or item.get("raw_price") or "Fiyat Sorunuz",
                "loc": item.get("location") or item.get("loc") or "Ankara",
                "rooms": item.get("room_info") or item.get("rooms") or "",
                "area": item.get("area") or "",
                "link": url,
                "img": item.get("thumbnail") or item.get("image") or item.get("img") or ""
            }
            intel = syn.generate_intelligence(target_dict)
            if intel and intel.get("ok"):
                with _persona_lock:
                    try:
                        cache = {}
                        if _persona_cache_file.exists():
                            with open(_persona_cache_file, "r", encoding="utf-8") as f:
                                cache = json.load(f)
                        cache_key = url or title or item_id
                        cache[cache_key] = intel
                        _persona_cache_file.parent.mkdir(parents=True, exist_ok=True)
                        temp_fd, temp_path = tempfile.mkstemp(dir=str(_persona_cache_file.parent), prefix="persona_", suffix=".tmp")
                        with open(temp_fd, "w", encoding="utf-8") as f:
                            json.dump(cache, f, ensure_ascii=False, indent=2)
                        os.replace(temp_path, str(_persona_cache_file))
                    except Exception:
                        pass
                return intel
        except Exception:
            pass

    return {}

def resolve_autonomous_day_for_item(item, is_project=True):
    """
    Herhangi bir yeni proje veya ilan için kesin ve deterministik tematik gün belirler.
    Asla hiçbir portföy/proje açıkta kalmaz; yeni gelen her veri haftalık plana otomatik oturur.
    """
    text = (item.get("title") or item.get("name") or "") + " " + \
           (item.get("folder_name") or "") + " " + \
           (item.get("location") or item.get("loc") or "") + " " + \
           (item.get("category") or "") + " " + \
           str(item.get("id") or "")
    text_upper = text.upper()

    if is_project:
        for d, cluster in PROJECT_THEME_CLUSTERS.items():
            if any(k in text_upper for k in cluster.get("keys", [])):
                return d
    else:
        for d, keys in LISTING_THEME_CLUSTERS.items():
            if any(k in text_upper for k in keys):
                return d

    t_lower = text.lower()
    if any(k in t_lower for k in ["ticari", "avm", "ofis", "iş yeri", "isyeri", "dükkan", "b2b", "yatırım", "plaza"]):
        return 0
    if any(k in t_lower for k in ["villa", "lüks", "luks", "rezidans", "beytepe", "incek", "çankaya", "cankaya", "dubleks", "penthouse"]):
        return 1
    if any(k in t_lower for k in ["arsa", "tarla", "parsel", "imar", "kırıkkale", "kirikkale", "sanayi", "bahçe", "bahce", "arazi"]):
        return 2
    if any(k in t_lower for k in ["yaşamkent", "yasamkent", "sincan", "yenikent", "aile", "site", "3+1", "4+1", "peyzaj", "çocuk"]):
        return 3
    if any(k in t_lower for k in ["kule", "tower", "kat", "çakırlar", "cakirlar", "manzara", "gökyüzü", "imza"]):
        return 4
    if any(k in t_lower for k in ["alanya", "bodrum", "yalıkavak", "yalikavak", "yazlık", "yazlik", "ege", "akdeniz", "marina", "sayfiye"]):
        return 5
    if any(k in t_lower for k in ["kampüs", "kampus", "öğrenci", "ogrenci", "1+1", "2+1", "taş ev", "tas ev", "huzur", "doğa", "doga", "toprak"]):
        return 6

    seed = str(item.get("id") or item.get("title") or "nexa_autopilot")
    return abs(hash(seed)) % 7

# ── Gün İsimleri & İndeks Eşleştirmesi ──────────────────────────────────────────
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# ── 35 Drive Projesinin 7 Günlük Tematik Dağılım Matrisi ────────────────────────
# Her proje, yatırımcı karakteristiğine göre 7 günden birine atanmıştır.
# Hiçbir proje açıkta bırakılmamış, 35 projenin tamamı sınıflandırılmıştır.
PROJECT_THEME_CLUSTERS = {
    0: {  # PAZARTESİ: Rasyonel / Yatırım & B2B (Ticari, AVM Hisseli, Nakit Akışı)
        "keys": ["ANKAPORT", "MIOSTELLA", "TRIOLE", "SMD PROTOKOL", "CADDE MAĞAZA", "SARAY"],
        "badge": "Ticari / B2B Lansman"
    },
    1: {  # SALI: Pratik / Konfor & Lüks / Prestij (Villa & High-Ticket Rezidans)
        "keys": ["ANGİM BEYTEPE", "EXCELANCE BEYTEPE", "EXCELANCE VADİ", "NEST İNCEK", "MONZA MOON", "SB VİVA"],
        "badge": "Lüks / High-Ticket"
    },
    2: {  # ÇARŞAMBA: Strateji / Vizyon & Arsa / Parsel (Tek Tapu Parsel, GES, İmar Arbitrajı)
        "keys": ["KIRIKKALE", "MÜSTAKİL", "NARÇİN RONYA", "VIP ÜNİVERSİTE", "VIP YENİKENT", "YAHŞİHAN"],
        "badge": "Arsa / Müstakil Parsel"
    },
    3: {  # PERŞEMBE: Açık Alan / Ölçek & Aile Yaşam Alanları (Geniş 3+1/4+1 Siteler & Peyzaj)
        "keys": ["GRANDE YAŞAMKENT", "MAS YAŞAMKENT", "SARITAŞ MAS LORA", "IDEA", "START BRAVO", "GÖKDEMİR STAR"],
        "badge": "Aile & Yaşam Sitesi"
    },
    4: {  # CUMA: Prestij / Zirve & Kule Rezidans (İkonik Mimari, Gökyüzü Kuleleri, Hafta Sonu Kararı)
        "keys": ["GÖKDEMİR İMZA", "SMD TWIN", "S POINT", "BORDO YAŞAM", "MONZA EYLÜL", "VIP ÇAKIRLAR"],
        "badge": "Prestij Rezidans Kule"
    },
    5: {  # CUMARTESİ: Kaçış / Tatil & Sayfiye / Sıcak Randevu (Alanya, Bodrum & Şehirlerarası Kaçış)
        "keys": ["VIP MARIN", "ALANYA", "EVART YALIKAVAK", "YALIKAVAK", "WM - PRIME", "ODUNPAZARI"],
        "badge": "Sayfiye / Tatil Rezidansı"
    },
    6: {  # PAZAR: Huzur / Toprak & Ulaşılabilir Yatırım (Kampüs & Öğrenci Konsepti, Sakin Yaşam)
        "keys": ["JOVEN KAMPÜS", "JOVEN PORT", "VIP AKADEMİ", "VERDE MONA", "VIVA", "NEVA"],
        "badge": "Yüksek Kira Getirili / Sakin"
    }
}

# ── 11 Canlı CB VIP İlanının Günlük Eşleşme Anahtarları ──────────────────────────
LISTING_THEME_CLUSTERS = {
    0: ["İŞ YERİ", "OFİS", "CİNNAH", "373541", "366936"],                       # Cinnah 5+1 & 2+1 Ofis
    1: ["BEYTEPE", "LODUMU", "369019", "ALTINORAN", "364460"],                   # Beytepe Lüks 3+1 & Sinpaş
    2: ["YAHŞİHAN", "ARSA", "EĞRİEKİN", "GÜNALAN", "360908", "358662", "359079"], # Yahşihan 7820m2, Çubuk, Gölbaşı
    3: ["SİNCAN", "YENİKENT", "358645", "357866", "CEVİZLİDERE", "371520"],     # Yenikent 3+1/4+1 & Cevizlidere
    4: ["TAŞ VİLLA", "ÇAMLIDERE", "358156", "BEYTEPE", "LÜKS"],                  # Çamlıdere Taş Villa & Prestij
    5: ["CEVİZLİDERE", "ALTINORAN", "KİRALIK", "DAİRE", "371520"],                # Cumartesi Sıcak Randevu İlanları
    6: ["ÇAMLIDERE", "GÜNALAN", "BAHÇE", "MÜSTAKİL", "359079", "358156"]          # Pazar Huzurlu Toprak & Villa
}

def load_projects_data():
    """35 Prestij Projesini yükler ve normalize eder."""
    paths = [
        BASE_DIR / "projects_map.json",
        BASE_DIR / "static" / "data" / "projects_map.json"
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                pass
    return []

def load_listings_data():
    """Canlı CB VIP İlanlarını yükler ve tekilleştirir."""
    paths = [
        BASE_DIR / "static" / "data" / "cached_cb_listings.json",
        BASE_DIR / "static" / "data" / "portfolio_listing_dashboards.json"
    ]
    seen_ids = set()
    combined = []
    
    for p in paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, dict) and "title" in v:
                                v_copy = dict(v)
                                v_copy["id"] = k
                                items.append(v_copy)
                    for item in items:
                        iid = str(item.get("id") or item.get("title") or "")
                        if iid and iid not in seen_ids:
                            seen_ids.add(iid)
                            combined.append(item)
            except Exception:
                pass
    return combined

def synthesize_algorithmic_hook(item, day_theme="Prestij & Yatırım", day_name="Pazartesi"):
    """
    Seçilen proje veya ilan için gerçek finansal/fiziki verilerinden
    sarsıcı ve yüksek dönüşümlü 3 algoritmik kanca (hook) türetir.
    """
    if not item:
        return "Ankara gayrimenkul piyasasında ezber bozan yatırım fırsatını kaçırmayın!"
        
    title = item.get("title") or item.get("name") or "Prestij Mülkü"
    price = item.get("price_display") or item.get("price") or item.get("raw_price") or ""
    down = item.get("down_payment") or ""
    inst = item.get("installment_terms") or item.get("installment") or ""
    loc = item.get("location") or item.get("loc") or "Ankara"
    rooms = item.get("room_info") or item.get("rooms") or ""
    is_project = (item.get("type") == "project" or "prj-" in str(item.get("id", "")))
    
    # Başlık temizliği
    clean_title = re.sub(r' - \d+$', '', title).strip()
    
    # 1. ENFLASYON ARBİTRAJI & FİNANSAL KALKAN KANCASI
    if "taksit" in inst.lower() or "vade" in inst.lower() or down:
        hook_finance = f"Aylık sabit taksit avantajıyla {loc} aksında tapulu mülk edinin: Enflasyona karşı paranızı gayrimenkulle zırhlayın!"
    elif "kiralık" in clean_title.lower() or "/ ay" in price:
        hook_finance = f"{loc} lokasyonunda yüksek prestij ve kurumsal imaj sunan kiralık fırsat!"
    else:
        hook_finance = f"{clean_title}: {loc} bölgesinin en yüksek prim potansiyeline sahip lokasyonunda yerinizi alın!"

    # 2. STATÜ, RÖNTGENCİLİK & MERAK KANCASI
    if "villa" in clean_title.lower() or "müstakil" in clean_title.lower():
        hook_curiosity = f"Şehrin gürültüsüne kalıcı veda: {loc} sınırlarında doğayla iç içe müstakil yaşam konsepti!"
    elif "avm" in clean_title.lower() or "hisse" in clean_title.lower() or "ankaport" in clean_title.lower():
        hook_curiosity = f"Geleceğin AVM hissedarı olun: {price if price else 'Özel lansman şartlarıyla'} düzenli nakit akışı sağlayan ticari ortaklık!"
    elif "arsa" in clean_title.lower() or "parsel" in clean_title.lower():
        hook_curiosity = f"{loc} aksında hemen tapu teslim, imarlı ve prim vadeden tek tapu müstakil parsel!"
    elif "rezidans" in clean_title.lower() or "kule" in clean_title.lower():
        hook_curiosity = f"Gökyüzünde prestijin yeni tanımı: {clean_title} ile mimari estetiğin zirvesini keşfedin!"
    else:
        hook_curiosity = f"{clean_title} ile hem oturum konforunu hem de yüksek sermaye getirisini bir araya getirin!"

    # 3. RAKAM VE LOKASYON ODAKLI SARSICI KANCA (HERO HOOK)
    if "ankaport" in clean_title.lower():
        hero_hook = "550.000 TL peşinatla AVM hissedarı olun: Yıllık döviz bazlı getiri ve düzenli kira çarpanı fırsatı!"
    elif "kırıkkale" in clean_title.lower() or "yahşihan" in loc.lower():
        hero_hook = "Ankara'da aylık 18.000 TL taksitle tek tapu müstakil villa arsası sahibi olun: Lansmana özel son parseller!"
    elif "angim" in clean_title.lower() or "beytepe" in loc.lower():
        hero_hook = "Beytepe'de 36 ay vade farksız taksitle mega kule lansmanı: Kapalı satış listesindeki fiyatları yakalayın!"
    elif "yaşamkent" in loc.lower() or "grande" in clean_title.lower():
        hero_hook = "Yaşamkent'in en huzurlu peyzajında 36 ay sabit taksitle geniş yaşam şehri yükseliyor!"
    elif "çamlıdere" in clean_title.lower():
        hero_hook = "Çamlıdere'nin çam ormanlarında özel yapım müstakil taş villa: Şömineli ve tam donanımlı huzur durağı!"
    elif "cinnah" in clean_title.lower():
        hero_hook = "Cinnah Caddesi üzerinde Atakule'ye komşu, kurumsal kimliğinize güç katacak prestijli iş yeri & ofis!"
    elif price and down:
        hero_hook = f"{clean_title}: {down} ve {inst if inst else 'avantajlı ödeme planıyla'} hemen sahip olun!"
    else:
        hero_hook = hook_curiosity

    return {
        "primary_hook": hero_hook,
        "finance_hook": hook_finance,
        "curiosity_hook": hook_curiosity
    }

def format_project_card(p, custom_badge="Lansman Projesi"):
    """Proje nesnesini kart ve stüdyo formatına dönüştürür."""
    if not p:
        return None
    title = p.get("title") or p.get("name") or "Prestij Projesi"
    price = p.get("price_display") or p.get("price") or "Fiyat Sorunuz"
    down = p.get("down_payment") or ""
    inst = p.get("installment_terms") or ""
    loc = p.get("location") or (f"{p.get('ilce', '')}, {p.get('il', '')}").strip(", ") or "Ankara"
    room = p.get("room_info") or ""
    thumb = p.get("thumbnail") or p.get("image") or "/static/img/placeholder.jpg"
    
    hooks = synthesize_algorithmic_hook(p)
    persona_intel = get_persona_intel_for_item(p, is_project=True)
    top_p = persona_intel.get("top_personas", [{}])[0] if persona_intel.get("top_personas") else {}
    anti_p = persona_intel.get("auditor_analysis", {}).get("anti_personas", [])
    
    return {
        "id": p.get("id"),
        "db_id": p.get("db_id"),
        "type": "project",
        "title": title,
        "badge": custom_badge,
        "location": loc,
        "price": price,
        "down_payment": down,
        "installment": inst,
        "room_info": room,
        "delivery": p.get("delivery_display") or (f"{p.get('delivery_months', '')} Ay Teslim" if p.get("delivery_months") else "Proje Aşamasında"),
        "thumbnail": thumb,
        "has_video": bool(p.get("has_video") or p.get("tanitim_cloud_url")),
        "has_pdf": bool(p.get("has_presentation") or p.get("drive_pdf_preview") or p.get("presentation")),
        "sales_highlights": p.get("sales_highlights") or p.get("description") or "Coldwell Banker VIP güvencesiyle yüksek getiri vadeden marka proje.",
        "hook": hooks["primary_hook"],
        "hook_alternatives": hooks,
        "top_persona": top_p.get("title", "Hedef Yatırımcı & Aile Kitlesi"),
        "persona_score": top_p.get("score", 95),
        "persona_badge": top_p.get("badge", "Yüksek Uyum"),
        "persona_suitability": top_p.get("suitability", ""),
        "anti_persona": anti_p[0] if anti_p else "Kısa vadeli spekülatif alıcılar",
        "ideal_scale": persona_intel.get("ideal_scale", ""),
        "persona_summary": persona_intel.get("executive_summary", "")
    }

def format_listing_card(l, custom_badge="Canlı CB VIP İlanı"):
    """İlan nesnesini kart ve stüdyo formatına dönüştürür."""
    if not l:
        return None
    title = l.get("title") or "Özel Portföy İlanı"
    price = l.get("price") or l.get("raw_price") or "Fiyat Sorunuz"
    loc = l.get("loc") or "Ankara, Çankaya"
    rooms = l.get("rooms") or ""
    area = l.get("area") or ""
    thumb = l.get("img") or "https://images.unsplash.com/photo-1560518883-ce09059eeffa?auto=format&fit=crop&w=800&q=80"
    
    hooks = synthesize_algorithmic_hook(l)
    persona_intel = get_persona_intel_for_item(l, is_project=False)
    top_p = persona_intel.get("top_personas", [{}])[0] if persona_intel.get("top_personas") else {}
    anti_p = persona_intel.get("auditor_analysis", {}).get("anti_personas", [])
    
    return {
        "id": l.get("id"),
        "type": "listing",
        "title": title,
        "badge": custom_badge,
        "location": loc,
        "price": price,
        "down_payment": "Peşin / Krediye Uygun",
        "installment": "Banka Kredisine Uygun" if "satılık" in title.lower() else "Aylık Sabit Kira",
        "room_info": f"{rooms} - {area}".strip(" - "),
        "delivery": "Hemen Teslim / Taşınmaya Hazır",
        "thumbnail": thumb,
        "has_video": False,
        "has_pdf": False,
        "sales_highlights": f"{loc} bölgesinde kurumsal Coldwell Banker VIP tek yetkili portföyü.",
        "hook": hooks["primary_hook"],
        "hook_alternatives": hooks,
        "top_persona": top_p.get("title", "Hedef Alıcı Kitlesi"),
        "persona_score": top_p.get("score", 95),
        "persona_badge": top_p.get("badge", "Yüksek Uyum"),
        "persona_suitability": top_p.get("suitability", ""),
        "anti_persona": anti_p[0] if anti_p else "Kısa vadeli spekülatif alıcılar",
        "ideal_scale": persona_intel.get("ideal_scale", ""),
        "persona_summary": persona_intel.get("executive_summary", "")
    }

def get_weekly_social_plan():
    """
    7 günlük stratejik paylaşım planını canlı verilerle birleştirerek üretir.
    35 Drive projesini ve 11 canlı ilanı tam olarak kapsar.
    Takvim haftası rotasyonu (ISO Calendar Week) sayesinde her hafta yeni vitrin oluşturur.
    """
    projects = load_projects_data()
    listings = load_listings_data()
    
    now = datetime.now()
    current_weekday = now.weekday()  # 0: Pazartesi ... 6: Pazar
    iso_year, iso_week, _ = now.isocalendar()

    # ── 7 Günlük Psikolojik ve Algoritmik Blueprint ─────────────────────────
    days_config = [
        {
            "day_index": 0,
            "day_name": "Pazartesi",
            "theme": "Rasyonel / Yatırım & B2B",
            "concept_short": "Ticari Gayrimenkul, AVM Hisseli Yatırım & Kurumsal Kira Getirisi",
            "peak_hours": "09:00 (LinkedIn B2B) | 12:30 (Reels & Shorts)",
            "channels": ["LinkedIn B2B", "Instagram Reels", "YouTube Shorts", "WhatsApp VIP"],
            "format": "Infografik Carousel + ROI Tablosu + B2B Raporu",
            "default_hook": "Geleceğin AVM hissedarı olun: 550.000 TL peşinatla düzenli kira getirili ticari ortaklık!",
            "target_audience": "Kurumsal firmalar, nakit akışı ve kira çarpanı arayan B2B yatırımcılar.",
            "cta": "B2B yatırım fizibilitesi ve portföy sunumu için DM'den 'YATIRIM' yazın."
        },
        {
            "day_index": 1,
            "day_name": "Salı",
            "theme": "Pratik / Konfor & Lüks / Prestij",
            "concept_short": "Hızlı Teslim Rezidanslar, High-Ticket Villalar & Çankaya Aksı",
            "peak_hours": "19:45 (Peak Instagram & TikTok Prime Time)",
            "channels": ["Instagram Reels (HD)", "TikTok Dikey", "WhatsApp Durum"],
            "format": "Sinematik Dikey Video (Reels) / Hızlı Kurgu / FPV Tur",
            "default_hook": "Beytepe ve İncek aksında lüksü yeniden tanımlayan özel mimari rezidanslar!",
            "target_audience": "Konfor arayan seçkin alıcılar, üst düzey bürokrat ve iş insanları.",
            "cta": "Özel VIP sunum ve yerinde randevu için DM / Yorumlara 'VİLLA' yazın."
        },
        {
            "day_index": 2,
            "day_name": "Çarşamba",
            "theme": "Strateji / Vizyon & Arsa / İmar Arbitrajı",
            "concept_short": "Müstakil Parseller, Tek Tapu Villa Arsaları & Gelişim Koridoru",
            "peak_hours": "12:00 & 20:30 (Gündüz & Akşam Kuşağı)",
            "channels": ["Instagram Carousel", "Reels (İmar Overlay)", "LinkedIn Post"],
            "format": "Master Plan & Uydu / İmar Çizgisi + Taksit Simülasyonu",
            "default_hook": "Aylık 18.000 TL sabit taksitle Ankara çevresinde tapulu müstakil parsel sahibi olun!",
            "target_audience": "Gelişim aksında yüksek sermaye kazancı (ROI) hedefleyen arsa yatırımcıları.",
            "cta": "İmar durumu, ada-parsel bilgisi ve taksit tablosu için hemen mesaj atın."
        },
        {
            "day_index": 3,
            "day_name": "Perşembe",
            "theme": "Açık Alan / Ölçek & Aile Yaşam Şehirleri",
            "concept_short": "Geniş 3+1 ve 4+1 Daireler, Sosyal Donatılı Mega Siteler",
            "peak_hours": "18:30 (Mesai Çıkışı & Aile Karar Kuşağı)",
            "channels": ["Instagram 10-Slayt Carousel", "Meta Reklam Seti", "WhatsApp"],
            "format": "Örnek Daire Gezisi + Kat Planı İnceleme Carousel'i",
            "default_hook": "Geniş peyzajlı, çocuk oyun alanlı ve 36 ay taksitli mega yaşam sitelerinde yerinizi ayırtın!",
            "target_audience": "Çocuklu aileler, geniş sosyal donatılı site arayanlar, ferah ev arayışındakiler.",
            "cta": "Örnek daireyi bu hafta sonu görmek için randevu butonuna tıklayın."
        },
        {
            "day_index": 4,
            "day_name": "Cuma",
            "theme": "Prestij / Zirve & Kule Rezidans Yaşamı",
            "concept_short": "32 Katlı Kule Projeleri, Panoramik Şehir Manzarası & Hafta Sonu Kararı",
            "peak_hours": "17:00 & 20:00 (Hafta Sonu Öncesi Karar Kuşağı)",
            "channels": ["Instagram Sinematik Reels", "Pinterest", "Meta Retargeting"],
            "format": "Sinematik Kule Çekimi + Gün Batımı Manzara Reels",
            "default_hook": "Ankara silüetine bakan 32 katlı gökyüzü kulelerinde sınırlı sayıdaki lansman fırsatı!",
            "target_audience": "Prestij ve statü arayan üst düzey yöneticiler ve mimari estetik tutkunları.",
            "cta": "Hafta sonu başlamadan VIP sunum dosyanızı indirin ve yerinizi ayırtın."
        },
        {
            "day_index": 5,
            "day_name": "Cumartesi",
            "theme": "Kaçış / Tatil & Sayfiye / Sıcak Randevu",
            "concept_short": "Akdeniz & Ege Yazlık Rezidansları + Hafta Sonu Canlı Portföy Gezileri",
            "peak_hours": "11:30 & 16:00 (Saha Ziyareti & Canlı İnceleme Saatleri)",
            "channels": ["Instagram Story Serisi", "Reels Turu", "Doğrudan Arama / DM"],
            "format": "Yaşam Tarzı (Lifestyle) Video + Detaylı Story Serisi",
            "default_hook": "Akdeniz ve Ege'de denize sıfır yazlık rezidans konsepti: 24 ay sabit taksit imkanıyla!",
            "target_audience": "Sayfiye yatırımı arayanlar ve hafta sonu Ankara'da portföy gezen alıcılar.",
            "cta": "Bu hafta sonu yerinde görmek ve lansman fiyatlarından yararlanmak için hemen arayın."
        },
        {
            "day_index": 6,
            "day_name": "Pazar",
            "theme": "Huzur / Toprak & Ulaşılabilir Portföy Özet Raporu",
            "concept_short": "Doğa İçi Müstakil Taş Evler, Kampüs Rezidansları & Haftalık Pazar Analizi",
            "peak_hours": "14:00 & 20:30 (Evde Sakin Araştırma Kuşağı)",
            "channels": ["Instagram Long-Form", "Haftalık E-Bülten", "WhatsApp VIP Liste"],
            "format": "Uzun Format Storytelling + Haftalık Portföy Özet Raporu",
            "default_hook": "Pazar sakinliğinde geleceğinizi planlayın: Yüksek kira çarpanlı daireler ve müstakil taş evler!",
            "target_audience": "Pazar günü evinde sakin bütçe ve gelecek planlaması yapan gayrimenkul alıcıları.",
            "cta": "Haftalık fırsat bültenimizi WhatsApp'tan almak için mesaj atabilirsiniz."
        }
    ]

    schedule = []
    
    # ── 35 Projenin Her Gün İçin Kümelenmesi ──────────────────────────────────
    for day in days_config:
        day_idx = day["day_index"]
        is_today = (day_idx == current_weekday)
        cluster_info = PROJECT_THEME_CLUSTERS.get(day_idx, {"keys": [], "badge": "Lansman Projesi"})
        theme_keys = cluster_info["keys"]
        
        # 1. Bu günün temasına uyan tüm projeleri filtrele (Otonom garantili eşleşme)
        matched_projects = []
        for p in projects:
            p_day = resolve_autonomous_day_for_item(p, is_project=True)
            title = (p.get("title") or p.get("name") or "").upper()
            folder = (p.get("folder_name") or "").upper()
            loc = (p.get("location") or "").upper()
            cat = (p.get("category") or "").upper()
            if p_day == day_idx or any(k in title or k in folder or k in loc or k in cat for k in theme_keys):
                if p not in matched_projects:
                    matched_projects.append(p)
                
        # Eğer katalogda hiç eşleşen yoksa modüler güvenlik ağı
        if not matched_projects and projects:
            matched_projects = [projects[i] for i in range(len(projects)) if i % 7 == day_idx]
            if not matched_projects:
                matched_projects = [projects[day_idx % len(projects)]]

        # 2. Bu günün temasına uyan tüm canlı ilanları filtrele (Otonom garantili eşleşme)
        listing_keys = LISTING_THEME_CLUSTERS.get(day_idx, [])
        matched_listings = []
        for l in listings:
            l_day = resolve_autonomous_day_for_item(l, is_project=False)
            ltitle = (l.get("title") or "").upper()
            lloc = (l.get("loc") or "").upper()
            lid = str(l.get("id") or "").upper()
            if l_day == day_idx or any(k in ltitle or k in lloc or k in lid for k in listing_keys):
                if l not in matched_listings:
                    matched_listings.append(l)
        if not matched_listings and listings:
            matched_listings = [listings[day_idx % len(listings)]]

        # 3. Haftalık Döngüsel Rotasyon (ISO Week Rotation)
        # Her hafta Hero ve Secondary projeler otomatik kayarak tüm 35 projeyi vitrine taşır.
        proj_count = len(matched_projects)
        hero_idx = (iso_week + day_idx) % proj_count if proj_count > 0 else 0
        sec_idx = (hero_idx + 1) % proj_count if proj_count > 1 else hero_idx
        
        hero_proj_raw = matched_projects[hero_idx] if proj_count > 0 else None
        sec_proj_raw = matched_projects[sec_idx] if proj_count > 1 else None
        
        # İlan rotasyonu
        list_count = len(matched_listings)
        list_idx = (iso_week + day_idx) % list_count if list_count > 0 else 0
        hero_list_raw = matched_listings[list_idx] if list_count > 0 else None

        # Kart formatlama
        hero_card = format_project_card(hero_proj_raw, cluster_info["badge"])
        sec_card = format_project_card(sec_proj_raw, "Öne Çıkan Alternatif") if sec_proj_raw and sec_proj_raw.get("id") != hero_proj_raw.get("id") else None
        list_card = format_listing_card(hero_list_raw, "Canlı CB VIP İlanı") if hero_list_raw else None

        # Tematik Havuz: Bu günün temasındaki tüm proje ve ilanların listesi
        thematic_pool = []
        for p in matched_projects:
            c = format_project_card(p, cluster_info["badge"])
            if c:
                thematic_pool.append(c)
        for l in matched_listings:
            c = format_listing_card(l, "Canlı CB VIP İlanı")
            if c:
                thematic_pool.append(c)

        # Öncelikli Liste (UI için items)
        priority_items = []
        if hero_card:
            priority_items.append(hero_card)
        if sec_card:
            priority_items.append(sec_card)
        if list_card:
            priority_items.append(list_card)

        # Günün genel kancasını hero kartının kancasıyla güncelle
        active_day_hook = hero_card["hook"] if hero_card else day["default_hook"]

        schedule.append({
            "day_index": day_idx,
            "day_name": day["day_name"],
            "is_today": is_today,
            "theme": day["theme"],
            "concept_short": day["concept_short"],
            "peak_hours": day["peak_hours"],
            "channels": day["channels"],
            "format": day["format"],
            "hook": active_day_hook,
            "target_audience": day["target_audience"],
            "cta": day["cta"],
            "hero_item": hero_card,
            "secondary_item": sec_card,
            "listing_item": list_card,
            "thematic_pool": thematic_pool,
            "thematic_pool_count": len(thematic_pool),
            "items": priority_items
        })

    today_item = next((d for d in schedule if d["is_today"]), schedule[0])

    return {
        "success": True,
        "current_date": now.strftime("%d.%m.%Y"),
        "current_time": now.strftime("%H:%M"),
        "today_day_name": DAYS_TR[current_weekday],
        "today_plan": today_item,
        "weekly_schedule": schedule,
        "inventory_stats": {
            "total_projects": len(projects),
            "total_listings": len(listings),
            "calendar_week": iso_week,
            "rotation_cycle": f"Hafta {iso_week} / Yıl {iso_year}"
        }
    }

def generate_social_post_package(item_id, item_type="project", day_name=None, theme=None, hook=None, cta=None):
    """
    Seçilen proje veya ilan için tam otonom 4 kanallı sosyal medya içerik paketi üretir.
    Gemini AI (mevcut ise) veya yüksek dönüşümlü kural tabanlı deterministik motor kullanır.
    """
    projects = load_projects_data()
    listings = load_listings_data()

    item_data = None
    if item_type == "project":
        for p in projects:
            if str(p.get("id")) == str(item_id) or str(p.get("db_id")) == str(item_id):
                item_data = p
                break
    else:
        for l in listings:
            if str(l.get("id")) == str(item_id):
                item_data = l
                break

    if not item_data:
        # Fallback to first project or listing
        if item_type == "project" and projects:
            item_data = projects[0]
        elif listings:
            item_data = listings[0]
        else:
            item_data = {
                "title": "Coldwell Banker VIP Prestij Portföyü",
                "price": "Fiyat Sorunuz",
                "location": "Ankara"
            }

    # Kritik parametreleri ayıkla
    title = item_data.get("title") or item_data.get("name") or "Prestij Portföyü"
    clean_title = re.sub(r' - \d+$', '', title).strip()
    price = item_data.get("price_display") or item_data.get("price") or item_data.get("raw_price") or "Fiyat Sorunuz"
    down = item_data.get("down_payment") or "Özel Lansman Peşinatı"
    installment = item_data.get("installment_terms") or ("36 Ay Vade Farksız Taksit" if item_type == "project" else "Banka Kredisine Uygun")
    loc = item_data.get("location") or item_data.get("loc") or "Ankara"
    rooms = item_data.get("room_info") or item_data.get("rooms") or ""
    delivery = item_data.get("delivery_display") or (f"{item_data.get('delivery_months')} Ay Teslim" if item_data.get("delivery_months") else "Hemen Teslim")
    highlights = item_data.get("sales_highlights") or item_data.get("description") or "Prestijli lokasyonda yüksek prim potansiyeline sahip fırsat."

    if not day_name:
        day_name = DAYS_TR[datetime.now().weekday()]
    if not theme:
        theme = "Prestij & Yatırım"
    
    # Dinamik hook türet
    hooks = synthesize_algorithmic_hook(item_data, theme, day_name)
    if not hook:
        hook = hooks["primary_hook"]
    if not cta:
        cta = "Detaylı portföy sunumu, kat planları ve yerinde randevu için hemen DM atın veya arayın."

    critical_specs = {
        "title": clean_title,
        "price": price,
        "down_payment": down,
        "installment": installment,
        "location": loc,
        "rooms": rooms,
        "delivery": delivery,
        "type": "Lansman Projesi" if item_type == "project" else "Canlı Portföy İlanı",
        "primary_hook": hook,
        "finance_hook": hooks["finance_hook"],
        "curiosity_hook": hooks["curiosity_hook"]
    }

    # Gemini AI Denemesi
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    if GEMINI_API_KEY:
        prompt_text = f"""
Sen Coldwell Banker VIP Ankara Gayrimenkul Mühendisliği Direktörü Yiğit Narin adına içerik üreten elit bir Sosyal Medya & Kopya Yazarı AI'sın.
Aşağıdaki portföy bilgileriyle TAM OTONOM, yüksek dönüşümlü (high-converting) içerik paketi üret.

PORTFÖY BİLGİLERİ:
- Başlık: {clean_title}
- Tür: {item_type}
- Fiyat / Fiyat Aralığı: {price}
- Peşinat: {down}
- Taksit / Ödeme Şartı: {installment}
- Lokasyon: {loc}
- Oda / Alan: {rooms}
- Teslim / Durum: {delivery}
- Öne Çıkan Özellikler: {highlights}
- Paylaşım Günü: {day_name}
- Günün Konsepti: {theme}
- Algoritmik Hook: {hook}
- CTA: {cta}

İSTENEN ÇIKTI (JSON Formatında):
{{
  "instagram": {{
    "hook": "Dikkat çekici başlık (1 cümle)",
    "caption": "Instagram gönderi metni (Bullet pointlar, emojiler, finansal şartlar ve CTA ile)",
    "hashtags": "#ColdwellBankerVIP #AnkaraGayrimenkul #YigitNarin #LuksKonut ..."
  }},
  "reels": {{
    "hook": "Video başı 3 saniyelik görsel & sözel kanca",
    "duration_sec": 25,
    "script_steps": [
      {{"scene": "0-3s", "visual": "Kamera açısı ve görsel talimat", "voiceover": "Söylenecek etkileyici seslendirme metni"}},
      {{"scene": "3-10s", "visual": "İç mekan / mimari detaylar", "voiceover": "Proje özellikleri ve ödeme avantajı"}},
      {{"scene": "10-18s", "visual": "Lokasyon ve sosyal olanaklar", "voiceover": "Prim potansiyeli ve teslim süresi"}},
      {{"scene": "18-25s", "visual": "Coldwell Banker VIP brövesi ve iletişim", "voiceover": "Güçlü harekete geçirici çağrı (CTA)"}}
    ]
  }},
  "linkedin": {{
    "headline": "B2B Yatırım Başlığı",
    "post_body": "Yatırımcılar ve yöneticiler için analitik, ROI ve makro gayrimenkul odaklı profesyonel metin",
    "cta": "Kurumsal CTA"
  }},
  "whatsapp": {{
    "status_text": "WhatsApp Hikaye (Durum) için 3 satırlık vurucu özet",
    "broadcast_msg": "VIP Alıcı & Yatırımcı listesine DM olarak fırlatılacak samimi ve profesyonel 2 paragraflık şablon"
  }}
}}
SADECE GEÇERLİ BİR JSON DÖNDÜR.
"""
        try:
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            payload = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {"temperature": 0.3}
            }
            headers = {"Content-Type": "application/json"}
            resp = requests.post(f"{url}?key={GEMINI_API_KEY}", json=payload, headers=headers, timeout=15)
            if resp.ok:
                data = resp.json()
                raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group())
                    parsed["critical_specs"] = critical_specs
                    parsed["source"] = "gemini-ai"
                    
                    # Direct WhatsApp link generator
                    wa_text = parsed.get("whatsapp", {}).get("broadcast_msg", "")
                    parsed["whatsapp"]["quick_wa_link"] = f"https://wa.me/?text={urllib.parse.quote(wa_text)}"
                    
                    # Persona Raporunu Ekle
                    p_intel = get_persona_intel_for_item(item_data, is_project=(item_type == "project"))
                    parsed["persona_report"] = {
                        "executive_summary": p_intel.get("executive_summary", ""),
                        "top_personas": p_intel.get("top_personas", []),
                        "anti_personas": p_intel.get("auditor_analysis", {}).get("anti_personas", []),
                        "ideal_scale": p_intel.get("ideal_scale", ""),
                        "advisory_honesty_note": p_intel.get("auditor_analysis", {}).get("advisory_honesty_note", "")
                    }
                    return parsed
        except Exception:
            pass

    # ── Deterministik Yüksek Dönüşümlü Kural Motoru (Garantili Fallback) ──
    p_intel = get_persona_intel_for_item(item_data, is_project=(item_type == "project"))
    persona_report = {
        "executive_summary": p_intel.get("executive_summary", ""),
        "top_personas": p_intel.get("top_personas", []),
        "anti_personas": p_intel.get("auditor_analysis", {}).get("anti_personas", []),
        "ideal_scale": p_intel.get("ideal_scale", ""),
        "advisory_honesty_note": p_intel.get("auditor_analysis", {}).get("advisory_honesty_note", "")
    }

    ig_caption = f"""✨ {hook}

📍 Lokasyon: {loc}
💰 Fiyat: {price}
💳 Peşinat: {down}
🗓️ Ödeme Kolaylığı: {installment}
📐 Tipler / Alan: {rooms if rooms else 'Farklı Tipler & Seçenekler'}
⏳ Durum: {delivery}

✦ {highlights}

Ankara gayrimenkul piyasasında fırsatları doğru zamanda yakalamak kazandırır. Coldwell Banker VIP güvencesiyle detaylı portföy sunumu ve randevu için iletişime geçin.

👉 {cta}
📲 Detaylar & Randevu: 0532 451 40 08
👤 Yiğit Narin | Gayrimenkul Mühendisi"""

    ig_hashtags = f"#ColdwellBankerVIP #YiğitNarin #AnkaraGayrimenkul #GayrimenkulMühendisliği #YatırımFırsatı #{loc.split(',')[0].replace(' ', '').replace('/', '')} #LüksKonut #LansmanProjesi"

    reels_script = [
        {"scene": "0-3s", "visual": f"Hızlı dikey drone / giriş çekimi: {clean_title} yazısı ekranda parlar.", "voiceover": f"'{hook}'"},
        {"scene": "3-10s", "visual": f"{loc} bölgesindeki mimari detaylar ve örnek daire gösterilir.", "voiceover": f"{price} ve {down} ile bu prestijli projede yeriniz hazır."},
        {"scene": "10-18s", "visual": "Sosyal donatılar, peyzaj ve kat planları hızlı geçişle akar.", "voiceover": f"{installment} avantajıyla hem oturum hem de yüksek prim potansiyeli bir arada."},
        {"scene": "18-25s", "visual": "Yiğit Narin & Coldwell Banker VIP logosu belirir.", "voiceover": f"{cta} Hemen profilimizdeki linkten bize ulaşın."}
    ]

    linkedin_post = f"""【GAYRİMENKUL YATIRIM ANALİZİ & MAKRO FIRSAT】

Portföy: {clean_title} ({loc})
Finansal Çerçeve: {price} | {down} | {installment}

Ankara'nın gelişen gayrimenkul koridorunda sermaye verimliliği ve nakit akışı odaklı yatırımcılar için kritik parametreler:

1. Bölgesel Değer Artışı: {loc} aksında son 12 ayda reel getiri enflasyonun üzerinde gerçekleşmiştir.
2. Finansal Esneklik: {installment} modeli, sermayenizi optimize ederken değer artışından ilk günden faydalanmanızı sağlar.
3. Çıkış Stratejisi: {delivery} sürecinde kurumsal kiralama veya ikincil el prim realizasyonu imkanı.

Portföyün detaylı finansal projeksiyonunu ve sunum dosyasını incelemek için direkt mesaj (DM) ile iletişime geçebilirsiniz.

Saygılarımla,
Yiğit Narin
Gayrimenkul Mühendisi | Coldwell Banker VIP Ankara"""

    whatsapp_status = f"""🔥 {hook}
📍 {loc} | 💰 {price}
💳 {down} + {installment}
📲 Detaylı sunum ve randevu için DM / WhatsApp: 0532 451 40 08"""

    whatsapp_broadcast = f"""Merhaba Sayın Yatırımcımız,

{day_name} gününe özel portföy bültenimizde öne çıkan fırsatımız:

📌 *{clean_title}* — {loc}
💰 *Fiyat:* {price}
💳 *Ödeme:* {down} / {installment}
📐 *Detay:* {rooms} ({delivery})

✦ *Neden Bu Portföy?*
{highlights}

Bu portföyün sunum dosyasını (PDF) veya tanıtım filmini incelemek isterseniz bana buradan yazabilirsiniz.

Saygılarımla,
*Yiğit Narin* | Coldwell Banker VIP Ankara
📞 0532 451 40 08"""

    quick_wa = f"https://wa.me/?text={urllib.parse.quote(whatsapp_broadcast)}"

    return {
        "source": "deterministic-autopilot",
        "critical_specs": critical_specs,
        "persona_report": persona_report,
        "instagram": {
            "hook": hook,
            "caption": ig_caption,
            "hashtags": ig_hashtags
        },
        "reels": {
            "hook": hook,
            "duration_sec": 25,
            "script_steps": reels_script
        },
        "linkedin": {
            "headline": f"{clean_title} | Ankara Gayrimenkul Yatırım & Değer Analizi",
            "post_body": linkedin_post,
            "cta": "B2B sunum ve detaylı fizibilite raporu için mesaj atabilirsiniz."
        },
        "whatsapp": {
            "status_text": whatsapp_status,
            "broadcast_msg": whatsapp_broadcast,
            "quick_wa_link": quick_wa
        }
    }
