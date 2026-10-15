#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXA AI v2 — PROJE ZEKASI ANALİZ PİPERLİNE (FOLDER 3)
Masaüstü NEXA_PRIME_v2_ENTERPRISE veritabanından aktarılan GERÇEK proje/portföy verisiyle çalışır.
Her sorgu, bütçe / bölge / oda / amaç kıstaslarına göre GERÇEK puanlanır;
her proje için kendi verisinden (ilçe, ada/parsel, TKGM onayı, fiyat, oda, alan) üretilen
farklı gerekçeler (rationale) döndürülür.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "nexa_portfolio_data.json"
MAP_FILE = BASE_DIR / "projects_map.json"

# ─── VERİ YÜKLEME ───
import logging as _eng_log
_eng_logger = _eng_log.getLogger("nexa.engine")

def load_portfolio():
    """Öncelik: güncel proje haritası (31 kart); portföy ilanları zengin dosyadan eklenir."""
    items = []
    if MAP_FILE.exists():
        try:
            with open(MAP_FILE, "r", encoding="utf-8") as f:
                for it in json.load(f):
                    it = dict(it)
                    it.setdefault("type", "project")
                    items.append(it)
        except Exception as e:
            _eng_logger.warning("projects_map.json yuklenemedi: %s", e)
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                for it in json.load(f):
                    if it.get("type") == "portfolio":
                        items.append(it)
        except Exception as e:
            _eng_logger.warning("nexa_portfolio_data.json yuklenemedi (portfoy atlandi): %s", e)
    return items

# ─── NİTELİK ÇIKARIMI ───
ILCELER = [
    "çankaya", "cankaya", "etimesgut", "yenimahalle", "pursaklar", "çubuk", "cubuk",
    "gölbaşı", "golbasi", "sincan", "odunpazarı", "odunpazari", "bodrum", "alanya",
    "yahşihan", "yahsihan", "keçiören", "kecioren", "mamak", "eryaman", "batıkent",
    "muğla", "mugla", "yalıkavak", "yalikavak",
]
MAHALLELER = [
    "beytepe", "yaşamkent", "yasamkent", "çakırlar", "cakirlar", "incek", "çayyolu",
    "cayyolu", "ümitköy", "umitkoy", "yalıkavak", "cevizlidere", "eğrikin", "egrikin",
    "horos", "mustafa kemal", "atatürk", "adil bey",
]
PROJE_SINONIMLERI = {
    "angim": "ANGİM BEYTEPE", "angim beytepe": "ANGİM BEYTEPE", "beytepe": "ANGİM BEYTEPE",
    "ankaport": "ANKAPORT - SARAY", "ankaport saray": "ANKAPORT - SARAY",
    "evart": "EVART YALIKAVAK", "evart yalikavak": "EVART YALIKAVAK",
    "nexa royal": "NEXA Royal Yalıkavak", "nexa royal yalıkavak": "NEXA Royal Yalıkavak",
    "nexa royal yalikavak": "NEXA Royal Yalıkavak", "royal yalıkavak": "NEXA Royal Yalıkavak",
    "concept bulvar": "CONCEPT BULVAR", "concept": "CONCEPT BULVAR",
    "natura golf": "NATURA GOLF", "natura": "NATURA GOLF",
    "grande": "GRANDE YAŞAMKENT", "grande yaşamkent": "GRANDE YAŞAMKENT",
    "gökdemir star": "GÖKDEMİR STAR", "gokdemir star": "GÖKDEMİR STAR",
    "gökdemir imza": "GÖKDEMİR İMZA", "gokdemir imza": "GÖKDEMİR İMZA",
    "gökdemir": "GÖKDEMİR İMZA", "gokdemir": "GÖKDEMİR İMZA",
    "idea": "IDEA - START BRAVO", "start bravo": "IDEA - START BRAVO",
    "joven": "JOVEN KAMPÜS", "joven kampüs": "JOVEN KAMPÜS", "joven port": "JOVEN PORT",
    "bordo": "BORDO YAŞAM", "bordo yaşam": "BORDO YAŞAM",
    "monza moon": "MONZA MOON", "monza": "MONZA EYLÜL CONCEPT",
    "narcin": "NARÇİN RONYA CITY - 1", "narcın": "NARÇİN RONYA CITY - 1", "ronya": "NARÇİN RONYA CITY - 1",
    "neva": "NEVA - START BRAVO", "nest": "NEST İNCEK", "nest incek": "NEST İNCEK",
    "s point": "S POINT - VIP SARAY", "spoint": "S POINT - VIP SARAY",
    "smd": "SMD TWIN", "smd twin": "SMD TWIN", "smd protokol": "SMD PROTOKOL",
    "triole": "TRIOLE YAŞAM", "excelance": "EXCELANCE VADİ", "excelance vadi": "EXCELANCE VADİ",
    "excelance beytepe": "EXCELANCE BEYTEPE",
    "verde": "VERDE MONA", "verde mona": "VERDE MONA",
    "vip akademi": "VIP AKADEMİ", "vip akademi 2": "VIP AKADEMİ 2",
    "vip marin": "VIP MARIN", "vip yaşamkent": "VIP YAŞAMKENT - GÖKDEMİR STAR",
    "vip yenikent": "VIP YENİKENT", "vip çakırlar": "VIP ÇAKIRLAR",
    "vip üniversite": "VIP ÜNİVERSİTE", "viva": "VIVA - START BRAVO",
    "wm prime": "WM - PRIME", "wm": "WM - PRIME",
}

def norm_text(t):
    s = (t or "").replace("İ", "i").replace("I", "ı").lower()
    s = s.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
    return s.replace("\u0307", "")

def extract_budget(text):
    """Bütçe: '5 milyon', '3.5m', '60 bin', '5000000', '5.000.000', '₺5M', '5-10M', '5 buçuk milyon', '$100k', '150 bin USD'."""
    t = text.lower().replace("₺", "")
    
    # Döviz kuru çarpanı (USD / EUR)
    fx_rate = 1.0
    if re.search(r'dolar|usd|\$', t):
        fx_rate = 36.5
    elif re.search(r'euro|eur|avro|€', t):
        fx_rate = 38.5

    rng = re.search(r'(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)\s*(?:milyon|mln|m\b|bin|k\b|tl|usd|eur|\$|€)?', t)
    if rng:
        g0 = rng.group(0)
        hi = g0[-2:].lower()
        lo = float(rng.group(1).replace(',', '.') or 0)
        hi_n = float(rng.group(2).replace(',', '.'))
        if 'milyon' in g0 or 'mln' in g0 or ('m' in hi and 'bin' not in g0):
            return {"min": int(lo * 1_000_000 * fx_rate), "max": int(hi_n * 1_000_000 * fx_rate)}
        if 'bin' in g0 or 'k' in hi:
            return {"min": int(lo * 1_000 * fx_rate), "max": int(hi_n * 1_000 * fx_rate)}
        return {"min": int(lo * fx_rate), "max": int(hi_n * fx_rate)}
    
    is_under = any(w in t for w in ["alti", "altı", "altinda", "altında", "kadar", "gecmeyen", "geçmeyen", "maksimum", "en fazla", "ust limit", "üst limit"])
    
    # Tekli: milyon / m / mln / bin / k
    m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(milyon|mln|m\b|bin|k\b)', t)
    if m:
        num = float(m.group(1).replace(',', '.'))
        unit = m.group(2)
        mul = 1_000 if unit in ['bin', 'k'] else 1_000_000
        val = int(num * mul * fx_rate)
        if is_under:
            return {"min": 0, "max": val}
        return {"min": val, "max": None}
    
    # "5 buçuk milyon" / "5.5 milyon" (buçuk desteği)
    m3 = re.search(r'(\d+)\s*(?:buçuk|bucuk)\s*(milyon|mln|m\b|bin|k\b)', t)
    if m3:
        num = float(m3.group(1)) + 0.5
        mul = 1_000 if m3.group(2) in ['bin', 'k'] else 1_000_000
        val = int(num * mul * fx_rate)
        if is_under:
            return {"min": 0, "max": val}
        return {"min": val, "max": None}
    
    # Ham büyük sayı (binlik ayraçlı veya düz): "5.000.000", "5000000"
    m2 = re.search(r'((?:\d{1,3}(?:\.\d{3})+|\d{4,}))\s*(?:tl|lira|usd|eur|\$|€)?', t)
    if m2:
        raw = re.sub(r'\D', '', m2.group(1))
        if len(raw) >= 5:
            val = int(int(raw) * fx_rate)
            if is_under:
                return {"min": 0, "max": val}
            return {"min": val, "max": None}
    return None

def extract_region(text):
    """İlçe + mahalle + proje adı bölge eşleşmeleri."""
    t = norm_text(text)
    found = []
    for ilce in ILCELER:
        if ilce in t:
            label = {"cankaya": "Çankaya", "etimesgut": "Etimesgut", "yenimahalle": "Yenimahalle",
                     "pursaklar": "Pursaklar", "cubuk": "Çubuk", "golbasi": "Gölbaşı",
                     "sincan": "Sincan", "odunpazari": "Odunpazarı", "bodrum": "Bodrum",
                     "alanya": "Alanya", "yahsihan": "Yahşihan", "kecioren": "Keçiören",
                     "mamak": "Mamak", "eryaman": "Eryaman", "batikent": "Batıkent",
                     "mugla": "Muğla", "yalikavak": "Yalıkavak"}.get(ilce, ilce.capitalize())
            if label not in found:
                found.append(label)
    for mah in MAHALLELER:
        if mah in t:
            label = {"beytepe": "Beytepe", "yasamkent": "Yaşamkent", "cakirlar": "Çakırlar",
                     "incek": "İncek", "cayyolu": "Çayyolu", "umitkoy": "Ümitköy",
                     "yalikavak": "Yalıkavak", "cevizlidere": "Cevizlidere",
                     "egrikin": "Eğrikin", "horos": "Horos"}.get(mah, mah.capitalize())
            if label not in found:
                found.append(label)
    return found

def extract_rooms(text):
    """Oda tipi: '3+1', '4+1', '2 1', '1+0', 'studio', 'villa', 'dubleks'."""
    t = text.lower()
    if "stüdyo" in t or "studio" in t or "1+0" in t or "0+1" in t:
        return "1+0"
    m = re.search(r'(\d(?:\.5)?)\s*\+\s*(\d)', text)
    if m:
        return f"{m.group(1)}+{m.group(2)}"
    m2 = re.search(r'(?<![\d.])([1-9])\s+([0-4])(?![\d])', text)
    if m2:
        return f"{m2.group(1)}+{m2.group(2)}"
    if "villa" in t or "villas" in t:
        return "Villa"
    if "dubleks" in t or "dublex" in t:
        return "Dubleks"
    return None

def extract_goals(text):
    """Yatırım amaçları ve istem tipi (satılık/kiralık)."""
    t = text.lower()
    goals = []
    if "oturum" in t or "yaşam" in t or "yasam" in t or "kendim" in t or "taşınma" in t or "tasinma" in t:
        goals.append("oturum")
    if "yatırım" in t or "yatirim" in t or "prim" in t or "kazanç" in t or "kazanc" in t or "değer" in t or "deger" in t:
        goals.append("yatirim")
    if "kiralık" in t or "kiralik" in t or "kira" in t or "kiracı" in t or "kiraci" in t or "amortisman" in t:
        goals.append("kiralik")
    want_type = None
    if "kiralık" in t or "kiralik" in t or "kira" in t:
        want_type = "Kiralık"
    elif "satılık" in t or "satilik" in t or "satın" in t or "satin" in t or "alma" in t:
        want_type = "Satılık"
    if "yazlık" in t or "villa" in t or "villas" in t:
        goals.append("yazlık")
        # Yazılık projesi satılık ilan olarak kabul edilir;
        # want_type determined below based on listing_type match logic
    return goals, want_type

def extract_ada_parsel(text):
    """Sorgudaki ada/parsel numarası: 4-7 haneli bağımsız tam sayı.
    Bütçe kalıpları birim (milyon/bin) istediği için çakışmaz; para birimi olanlar elenir."""
    t = text.replace("₺", " ").replace("TL", " ").replace("$", " ").replace("€", " ")
    t = re.sub(r'\d[\d.,]*\s*(?:milyon|mln|bin|ay|gün|hafta)', ' ', t, flags=re.I)
    hits = re.findall(r'(?<![\d.])(\d{4,7})(?![\d])', t)
    return [h for h in hits if h not in ("0",)][:3]

def extract_keywords_and_projects(text):
    """Kullanıcının sorgusunda adı geçen projeler (M7: kısa sinonim, uzun eşleşmenin parçasıysa elenir)."""
    t = norm_text(text)
    matched = [k for k in PROJE_SINONIMLERI if norm_text(k) in t]
    keys = sorted(matched, key=len, reverse=True)
    out = []
    for k in keys:
        if any(norm_text(k) in norm_text(k2) and norm_text(k) != norm_text(k2) for k2 in keys):
            continue
        out.append(PROJE_SINONIMLERI[k])
    # Tam adı geçen proje varsa bölüm genişletmesi gereksiz (örn. "neva start bravo" → yalnızca NEVA)
    t_flat = re.sub(r'\s+', ' ', t.replace("-", " ")).strip()
    exact = [name for name in out
             if norm_text(name) in t or re.sub(r'\s+', ' ', norm_text(name).replace("-", " ")).strip() in t_flat]
    if exact:
        return list(dict.fromkeys(exact))
    # "START BRAVO" gibi ortak bölüm adı: aynı bölgedeki tüm projeleri de getir
    for name in list(out):
        if " - " in name:
            suffix = name.split(" - ", 1)[-1]
            if suffix and norm_text(suffix) in t:
                for other in PROJE_SINONIMLERI.values():
                    if other != name and other not in out and suffix in other:
                        out.append(other)
    return list(dict.fromkeys(out))


# ─── NİYET TESPİTİ VE DİYALOG YÖNETİMİ ───
def detect_property_type(text):
    """Metinden emlak kategorisini tespit eder."""
    t = norm_text(text)
    if any(w in t for w in ["villa", "yazlik", "yazlık", "mustakil"]):
        return "Villa"
    if any(w in t for w in ["ofis", "buro", "ticari", "isyeri", "işyeri", "dukkan", "dükkan"]):
        return "Ticari / Ofis"
    if any(w in t for w in ["arsa", "tarla", "parsel", "bahce", "bahçe"]):
        return "Arsa"
    if any(w in t for w in ["rezidans", "residence"]):
        return "Rezidans"
    if any(w in t for w in ["daire", "konut", "ev", "apartman", "kat"]):
        return "Konut / Daire"
    return None


def detect_intent(text):
    """Kullanıcının mesajını analiz ederek niyetleri ve çıkarılan varlıkları belirler."""
    t = norm_text(text)
    intents = {
        "project_search": ["proje", "ilan", "ariyorum", "arıyorum", "bul", "projeler"],
        "villa_search": ["yazlik", "yazlık", "villa", "villas", "luxury", "premium", "duplex", "vip villa"],
        "rental_search": ["kiralik", "kiralık", "kira", "kiraci", "kiracı", "kiralama"],
        "budget_inquiry": ["butce", "bütçe", "fiyat", "maliyet", "para", "cost"],
        "region_inquiry": ["bolge", "bölge", "il", "ilce", "ilçe", "nerede", "where"],
        "room_query": ["oda", "odasini", "3+1", "2+1", "1+1", "oda sayisi"],
        "tkdm_inquiry": ["tkgm", "tapu", "parsel", "ada"],
        "small_talk": ["merhaba", "selam", "gunaydin", "günaydın", "iyi gunler", "tesekkur", "teşekkür"],
    }
    scores = {}
    for intent, keywords in intents.items():
        score = sum(1 for w in keywords if w in t)
        if score > 0:
            scores[intent] = score
    primary = max(scores.keys(), key=lambda k: (scores[k], list(intents.keys()).index(k))) if scores else "general"
    secondary = [k for k, v in scores.items() if k != primary]
    entities = extract_all_entities(text)
    return primary, secondary, entities


def generate_clarification_question(missing_fields):
    """Eksik bilgi gerektiğinde kullanıcıya sorulacak akıllı soruları üretir."""
    questions = {
        "budget": "Bütçeniz ne kadardır? (örnek: 5 milyon TL, 10-15 milyon TL aralığı)",
        "region": "Hangi bölgeyi tercih ediyorsunuz? (Ankara, Çankaya, Beytepe, Bodrum vb.)",
        "rooms": "Kaç oda arıyorsunuz? (1+1, 2+1, 3+1 vb.)",
        "property_type": "Hangi tipi arıyorsunuz? (daire, villa, ofis, arsa)",
        "timeframe": "Projeniz ne zaman teslim edilsin? (hemen, 3 ay, 6 ay vb.)",
    }
    q_list = [questions[f] for f in missing_fields if f in questions]
    if len(q_list) == 1:
        return q_list[0]
    elif len(q_list) == 2:
        return f"{q_list[0]} ve {q_list[1]}?"
    elif len(q_list) >= 3:
        return "Lütfen şu bilgileri belirtiniz: " + "; ".join(q_list[:3])
    return "Size en uygun portföyü seçebilmem için bütçe ve bölge tercihinizi paylaşabilir misiniz?"


class ConversationContext:
    """Kullanıcı etkileşim geçmişini yönetir."""
    def __init__(self):
        self.budget = None
        self.region = None
        self.rooms = None
        self.property_type = None
        self.want_type = None
        self.goals = []
        self.conversation_history = []

    def update(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def add_history(self, user_msg, bot_resp):
        self.conversation_history.append({"user": user_msg, "bot_resp": bot_resp})
        if len(self.conversation_history) > 8:
            self.conversation_history = self.conversation_history[-8:]


def extract_all_entities(text):
    """Metinden tüm çıkarılabilir varlıkları çeker."""
    t = norm_text(text)
    entities = {}
    budget = extract_budget(text)
    if budget:
        entities["budget"] = budget
    region = extract_region(text)
    if region:
        entities["region"] = region
    rooms = extract_rooms(text)
    if rooms:
        entities["rooms"] = rooms
    prop_type = detect_property_type(t)
    if prop_type:
        entities["property_type"] = prop_type
    if any(k in t for k in ["tkgm", "tapu", "parsel", "ada"]):
        entities["tkgm"] = True
    timeframe_keywords = ["hemen", "bu ay", "bu yil", "yarin", "bu hafta", "3 ay", "6 ay", "teslim"]
    tfound = [kw for kw in timeframe_keywords if kw in t]
    if tfound:
        entities["timeframe"] = tfound[0]
    return entities


# ─── PUANLAMA ───
def _norm_price_num(raw):
    """Binlik/ondalık ayraç normalizasyonu: '2.400.000', '3,775,000', '360.000,00'."""
    s = raw.strip()
    if not s:
        return None
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or len(parts[-1]) == 3:
            s = s.replace(".", "")
    try:
        v = float(s)
    except (ValueError, TypeError):
        return None
    return int(v) if v.is_integer() else v


def price_numeric(item):
    """Fiyatı sayıya çevirir."""
    if item.get("price_numeric") and isinstance(item.get("price_numeric"), (int, float)) and item.get("price_numeric") > 0:
        return int(item["price_numeric"])
    pd = item.get("price_display") or ""
    m = re.search(r'([\d][\d.,]*)\s*(?:₺|TL|lira)|(?:₺|TL)\s*([\d][\d.,]*)', pd, re.I)
    if not m:
        m2 = re.search(r'([\d][\d.,]*)', pd)
        if not m2:
            return None
        return _norm_price_num(m2.group(1))
    return _norm_price_num(m.group(1) or m.group(2))


def price_range(item):
    """Fiyat bandını (min, max) döner."""
    if item.get("price_min") and item.get("price_max"):
        return int(item["price_min"]), int(item["price_max"])
    if item.get("price_numeric"):
        p = int(item["price_numeric"])
        return p, int(item.get("price_max") or p)
    pd = item.get("price_display") or ""
    nums = []
    for m in re.finditer(r'([\d][\d.,]*)\s*(?:₺|TL|lira)|(?:₺|TL)\s*([\d][\d.,]*)', pd, re.I):
        v = _norm_price_num(m.group(1) or m.group(2))
        if v:
            nums.append(v)
    if not nums:
        return None, None
    return min(nums), max(nums)

def score_item(item, budget, regions, rooms, goals, want_type, named_projects, ada_parsel=None):
    """Her kayıt için gerçek veriyle puan üretir."""
    score = 20
    parts = []
    item["_region_hit"] = False
    item["_name_hit"] = False

    ilce = norm_text(item.get("ilce") or "")
    il = norm_text(item.get("il") or "")
    mahalle = norm_text(item.get("mahalle") or "")
    title = item.get("title") or ""
    t = norm_text(title)

    # 0) Ada/parsel eşleşmesi (kullanıcı somut parsel sorduysa en güçlü sinyal)
    ada_hit = False
    if ada_parsel:
        kayit_ada = norm_text(str(item.get("ada_no") or ""))
        kayit_parsel = norm_text(str(item.get("parsel_no") or ""))
        for ap in ada_parsel:
            if ap == kayit_ada or (kayit_parsel and ap == kayit_parsel):
                score += 40
                ada_hit = True
                item["_ada_hit"] = True
                parts.append(f"Ada {item.get('ada_no')}/{item.get('parsel_no')} sorgunuzla birebir eşleşiyor")
                break

    # 1) Bölge eşleşmesi
    region_hit = False
    for reg in regions:
        rn = norm_text(reg)
        if rn and (rn in ilce or rn in mahalle or rn in t or rn in il):
            score += 35
            region_hit = True
            item["_region_hit"] = True
            parts.append(f"Bölgeniz {reg} ile eşleşiyor")
            break
    if not region_hit and regions and regions[0] not in ("Ankara",) and ilce:
        # sorguda bölge yoksa puanlama tarafsız kalır
        pass

    # 2) Proje adı eşleşmesi (doğrudan arama)
    if title in named_projects or any(np in t for np in named_projects):
        score += 30
        item["_name_hit"] = True
        parts.append("Sorgunuzda bu projenin adi gecti")
    elif any(syn in t for syn in PROJE_SINONIMLERI):
        pass

    # 3) Oda eşleşmesi
    if rooms:
        room_info = norm_text(item.get("room_info") or "")
        if rooms in room_info or re.search(re.escape(rooms), room_info):
            score += 25
            parts.append(f"{rooms} daire tipi aranizla uyumlu")
        elif room_info and ("daire" in room_info or "+" in room_info):
            score += 5
            parts.append(f"Oda tipi: {item.get('room_info')}")

    # 4) Bütçe eşleşmesi (fiyat bandı ile örtüşme kontrolü)
    pmin, pmax = price_range(item)
    is_rent = item.get("listing_type") == "Kiralık"
    if budget and pmin:
        if is_rent:
            # aylık kira, bütçe doğrudan aylık karşılaştırılır
            lo = budget.get("min") or 0
            hi = budget.get("max") or lo
            if lo and lo <= pmin <= (hi or lo):
                score += 25
                parts.append(f"Aylik {item.get('price_display')} kira bütcenize uygun")
            elif lo and pmin <= lo * 1.15:
                score += 12
                parts.append(f"Aylik kira: {item.get('price_display')}")
            else:
                score += 5
                parts.append(f"Aylik kira: {item.get('price_display')}")
        else:
            band_lo, band_hi = pmin, pmax or pmin
            if budget.get("max") and (budget.get("min") == 0 or budget.get("min") is None):
                hi = budget["max"]
                if band_lo <= hi:
                    score += 45
                    parts.append(f"{item.get('price_display')} fiyati {int(hi/1000000)} Milyon TL bütcenizin altindadir")
                else:
                    score -= 30
            else:
                if budget.get("min") and budget.get("max") is None:
                    # M1: tek fiyat bütçe (örn. "5 milyon") aynı aralık mantığıyla
                    # puanlanır: min = 0.85 × tek değer, max = tek değer
                    tek = budget["min"]
                    budget = {"min": int(tek * 0.85), "max": tek}
                lo = budget.get("min") or 0
                hi = budget.get("max") or lo
                # proje fiyat bandı ile bütçe aralığı örtüşüyor mu?
                if lo and band_hi >= lo * 0.85 and band_lo <= hi * 1.05:
                    if band_lo <= (hi or 999999999) * 0.75:
                        score += 35
                        parts.append(f"{item.get('price_display')} fiyati bütcenizin oldukca altinda ve avantajli")
                    else:
                        score += 25
                        parts.append(f"{item.get('price_display')} fiyat bandi bütce araliginizla örtüsüyor")
                elif hi == lo and band_lo <= lo * 1.15:
                    # eşit uçlu aralıkta tolerans: lo * 1.15'e kadar uygun
                    score += 20
                    parts.append(f"{item.get('price_display')} fiyati bütcenize yakin")
                else:
                    score += 5
                    parts.append(f"Fiyat: {item.get('price_display')}")
    elif budget and not pmin:
        score += 8
        parts.append("Guncel fiyat icin danisman bilgi verebilir")

    # 5) İlan tipi (satılık / kiralık / yazılık)
    if want_type:
        if item.get("listing_type") == want_type:
            score += 15
            parts.append(f"{want_type} istemiyle uyumlu")
        elif item.get("listing_type"):
            score -= 15
    # Yazılık (villa) tipi eklenmesi: listing_type "Yazılık" ise +15, degilse -15
    if "yazlık" in goals and item.get("listing_type"):
        if item.get("listing_type") == "Yazılık":
            score += 15
            parts.append("Yazılık istemiyle uyumlu")
        else:
            score -= 10

    # 6) TKGM onayı
    if item.get("tkgm_verified"):
        score += 6
        parts.append(f"TKGM onayli parsel (Ada {item.get('ada_no')}/{item.get('parsel_no')})")

    # 7) Kiralık hedefinde kiralık ilanlara öncelik
    if "kiralik" in goals and is_rent:
        score += 12
    if "yatirim" in goals and not is_rent:
        score += 8
    if "oturum" in goals and item.get("property_category") in ("Konut / Daire", "Villa"):
        score += 6

    # 8) "En ucuz" / "En uygun" / "Ekonomik" sorgu optimizasyonu
    is_cheap_query = any(w in norm_text(item.get("_query_raw", "")) for w in ["ucuz", "en uygun", "ekonomik", "en dusuk", "dusuk fiyat", "butceme uygun"])
    if is_cheap_query and pmin:
        if pmin <= 1500000:
            score += 45
            parts.append(f"Portföyün en avantajlı başlangıç fiyatına ({item.get('price_display')}) sahip projesidir")
        elif pmin <= 2000000:
            score += 35
            parts.append(f"2 Milyon TL altı bütçede ekonomik seçenektir ({item.get('price_display')})")
        elif pmin <= 3500000:
            score += 20
            parts.append(f"Bölge ortalamasının altında fiyat avantajı sunar")

    # 9) Kriter belirtilmediyse (ör. "En Uygun Projeler") Ankara portföyü öne çıkar
    ankara_scope = (not regions) or (len(regions) == 1 and norm_text(regions[0]) == "ankara")
    if ankara_scope and not named_projects and not rooms and not budget and not is_cheap_query:
        if il == "ankara":
            score += 10
            parts.append("Ankara portföyünde öne çıkan proje")

    return max(15, min(99, score)), parts

def item_region_label(item):
    return item.get("ilce") or item.get("mahalle") or "Ankara"

def item_price_label(item):
    pd = item.get("price_display")
    return pd if pd else "Güncel Fiyat Listesi İçin Danışın"

def _load_project_summaries():
    try:
        p = Path(__file__).parent / "nexa_project_summaries.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def build_rationale(item, parts):
    """Gerçek verilerden türetilmiş gerekçe."""
    extra = []
    if item.get("ada_no"):
        extra.append(f"Ada {item.get('ada_no')} / Parsel {item.get('parsel_no')}")
    if item.get("tkgm_verified"):
        extra.append("TKGM onaylı")
    if item.get("room_info"):
        extra.append(item.get("room_info"))
    if item.get("net_gross_area"):
        extra.append(item.get("net_gross_area"))
    loc = item_region_label(item)
    lead = f"{loc} bölgesinde {item.get('title')}"
    txt = " • ".join(parts) if parts else "Kriterlerinize yüksek uyum göstermektedir"
    if extra:
        txt += f". Kayıtlı veri: {item.get('title')} ({', '.join(extra)})"
    return f"{lead}. {txt}."

# ─── ANA İŞLEME ───
def process_nexa_query(user_query):
    try:
        items = load_portfolio()
    except Exception:
        items = []
    q = user_query.strip()
    ql = norm_text(q)

    budget = extract_budget(q)
    regions = extract_region(q)
    rooms = extract_rooms(q)
    goals, want_type = extract_goals(q)
    named_projects = extract_keywords_and_projects(q)
    ada_parsel = extract_ada_parsel(q)

    # Lead Qualification Scoring (1-10)
    lead_score = 3
    if any(w in ql for w in ["gormek", "randevu", "bu hafta", "yerinde", "satin al", "arayin", "gorusmek", "ofisiniz"]):
        lead_score = 9  # HOT LEAD
    elif any(w in ql for w in ["butcem", "odeme", "pesinat", "taksit", "kredi", "vade", "nakit"]):
        lead_score = 7  # SERIOUS LEAD
    elif any(w in ql for w in ["fiyat", "kac para", "teslim", "ne zaman", "m2", "kac daire"]):
        lead_score = 5  # CURIOUS LEAD
    else:
        lead_score = 3  # DISCOVERY

    scored = []
    for it in items:
        it["_query_raw"] = q
        # Kişisel portföy ilanları yalnızca kiralık isteminde skorlanır (kiralık envanter botta görünür)
        if it.get("type") == "portfolio" and want_type != "Kiralık":
            continue
        s, parts = score_item(it, budget, regions, rooms, goals, want_type, named_projects, ada_parsel)
        scored.append((s, it, parts))
    scored.sort(key=lambda x: -x[0])

    cbs = [(s, it, p) for s, it, p in scored if it.get("type") == "project" or it.get("type") == "portfolio"]
    if regions:
        # Bölge sorulduysa yalnızca o bölgedeki kayıtlar gösterilir (flag bazlı)
        region_hits = [x for x in cbs if x[1].get("_region_hit")]
        if region_hits:
            cbs = region_hits
    if named_projects:
        # Proje adı ile sorulduysa yalnızca adı geçen projeler gösterilir (flag bazlı)
        name_hits = [x for x in cbs if x[1].get("_name_hit")]
        if name_hits:
            cbs = name_hits
    if ada_parsel:
        # Ada/parsel sorulduysa o parsellik kayıtlar kesin önceliklidir
        ada_hits = [x for x in cbs if x[1].get("_ada_hit")]
        if ada_hits:
            cbs = ada_hits
    cb_matches = cbs[:3]

    rental_notice = ""
    if want_type == "Kiralık":
        kiralik_var = any(it.get("type") == "portfolio" and it.get("listing_type") == "Kiralık"
                          for it in items)
        if kiralik_var:
            rental_notice = ("\n_Not: Portföyümüzde kiralık ilanlarımız mevcut "
                             "(ör. 56.000 ₺/ay kiralık rezidans); isterseniz onları gösterebilirim, "
                             "aşağıdaki satılık projelerimiz de yatırım amaçlı değerlendirilebilir._")
        else:
            rental_notice = ("\n_Not: Kiralık envanterimiz şu an sistemde yer almıyor; aşağıdaki "
                             "satılık projeler yatırım amaçlı değerlendirilebilir._")

    # Rapor başlığı
    def fmt_money(v):
        return f"{v/1_000_000:g} Milyon TL" if v >= 1_000_000 else f"{v/1_000:g} Bin TL"
    bütçe_str = "Belirtilmedi"
    if budget:
        if budget["max"]:
            bütçe_str = f"{fmt_money(budget['min'])} - {fmt_money(budget['max'])}"
        else:
            bütçe_str = fmt_money(budget["min"])
    bölge_str = ", ".join(regions) if regions else "Ankara Genel"
    amaç_map = {"oturum": "Oturum", "yatirim": "Yatırım", "kiralik": "Kiralık"}
    amaç_str = ", ".join(amaç_map.get(g, g.capitalize()) for g in goals) if goals else "Oturum + Yatırım"

    lines = [
        f"**Nexa AI Proje Zekası Analiz Raporu:**\n",
        f"• **Bütçe:** {bütçe_str}",
        f"• **Bölge:** {bölge_str}",
        f"• **Oda Tercihi:** {rooms or 'Belirtilmedi'}",
        f"• **Yatırım Amacı:** {amaç_str}",
        "",
        "Tüm portföy proje verileri, ada/parsel ve TKGM kayıtlarıyla taranarak **gerçek uyum puanları** hesaplandı:",
    ]

    if not cb_matches:
        lines.append("\n_Ölçütlerinizle eşleşen markalı proje bulunamadı; portföy verileri değerlendirildi._")
    elif rental_notice:
        lines.append(rental_notice)

    # Çekirdek proje kartları
    for s, it, parts in cb_matches:
        ip = item_price_label(it)
        label = f"**{it['title']}** — %{s} Uyumlu\n📍 {item_region_label(it)} • 💰 {ip}"
        lines.append(f"\n{label}\n💡 {build_rationale(it, parts)}")

    lines.append("\n---\n_Detaylı sunum, güncel fiyat listesi ve parsel raporları için **0535 489 56 56** WhatsApp hattından ulaşabilirsiniz._")

    # Kart formatı (site.html uyumlu)
    summaries = _load_project_summaries()
    project_cards = []
    for s, it, parts in cb_matches:
        is_pf = it.get("type") == "portfolio"
        ozet = summaries.get(it["title"], {}).get("summary") or ""
        project_cards.append({
            "id": it["id"],
            "db_id": it.get("db_id"),
            "title": it["title"],
            "region": item_region_label(it),
            "price_display": item_price_label(it),
            "match_percent": s,
            "rationale": ozet or build_rationale(it, parts),
            "summary": ozet,
            "is_portfolio": is_pf,
            "media": ({} if is_pf else {
                "promo_video_url": it.get("tanitim_cloud_url") or it.get("cloud_direct_url") or it.get("cloud_video_url") or f"/stream/video/{it['id']}",
                "slideshow_video_url": it.get("slideshow_cloud_url") or it.get("cloud_video_url") or f"/stream/video/{it['id']}",
                "pdf_url": ("/" + it["pdf_path"]) if it.get("pdf_path") else "",
                "thumbnail_url": it.get("thumbnail") or "/static/img/pdf_previews/pdf_cover_1.png"
            })
        })

    return {
        "success": True,
        "response": "\n".join(lines),
        "lead_score": lead_score,
        "extracted_info": {
            "budget_tl": budget,
            "regions": regions,
            "rooms": rooms,
            "goals": goals
        },
        "projects": project_cards
    }

if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    tests = [
        "Ankara'da 3+1 proje arıyorum, bütçem 5 milyon",
        "Çankaya İlanları",
        "En Uygun Projeler",
        "Kiralık ofis arıyorum Çankaya'da bütçem 60 bin",
        "5-10M yatırım için lüks proje önerir misin?",
        "Gölbaşı'nda arsa veya villa var mı?",
        "MONZA MOON hakkında bilgi ver",
    ]
    for t in tests:
        print("=" * 70)
        print("SORU:", t)
        res = process_nexa_query(t)
        print(res["response"])
        for p in res["projects"]:
            print(f"  -> {p['title']} | %{p['match_percent']} | {p['region']} | {p['price_display']}")
        print()