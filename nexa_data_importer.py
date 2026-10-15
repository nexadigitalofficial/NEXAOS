#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXA VERİ ZENGİNLEŞTİRİCİ (P6)
NEXA DB'deki doküman chunk'larından markalı projelerin FİYAT / ODA / TESLİM
verilerini çıkarır:
  1) nexa_project_prices.json  → proje bazlı çıkarılmış veri
  2) nexa_portfolio_data.json  → price_display / room_info / description güncelle
Kullanım: python nexa_data_importer.py
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "nexa_database.db"
PRICES_OUT = BASE_DIR / "nexa_project_prices.json"
PORTFOLIO_OUT = BASE_DIR / "nexa_portfolio_data.json"

GARBAGE = re.compile(r"[\u0080-\u02FF]{4,}")
PRICE_RE = re.compile(r"([\d][\d.,]*)\s*(?:₺|TL)|(?:₺)\s*([\d][\d.,]*)", re.I)
ROOM_RE = re.compile(r"(\d)\s*\+\s*(\d)")
MONTH_RE = re.compile(r"(\d{1,2})\s*Ay\b", re.I)
# Taksit/peşinat/kapora/ayda gibi ödeme bağlamı: bu sözcüklere bitişik fiyatlar
# toplam fiyat DEĞİLDİR, elenir.
BAD_CTX = re.compile(r"(kapora|kaparo|taksit|peşinat|pesinat|ayda|aylık|aylik|vade|öde|ode|%50|%40|%30|hisse|gönderim|maksimum|minimum)", re.I)
CTX_BEFORE, CTX_AFTER = 30, 45


def is_bad_price_context(text, start, end):
    """Fiyat eşleşmesinin çevresinde ödeme bağlamı varsa True."""
    low = text
    s = max(0, start - CTX_BEFORE)
    e = min(len(text), end + CTX_AFTER)
    return bool(BAD_CTX.search(low[s:e]))


def norm_price(raw):
    """Binlik/ondalık ayraçları Türkçe gayrimenkul formatında normalleştirir."""
    s = raw.strip()
    if not s:
        return None
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if s.count(",") == 1 and len(s.split(",")[1]) <= 2:
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
    if not (500_000 <= v <= 500_000_000):
        return None
    return int(v)


def good_text(chunk):
    """Anlamlı metin mi? (çöp glyph yok, yeterli kelime var)"""
    if not chunk:
        return False
    if GARBAGE.search(chunk):
        return False
    words = [w for w in chunk.split() if w.strip()]
    if len(words) < 8 or len(chunk) < 90:
        return False
    if "belirtilen" in chunk.lower() and len(words) < 20:
        return False
    return True


def norm_title(s):
    """Başlık normalizasyonu: parantez içleri, noktalama ve Türkçe karakterlerden
    arındırılmış eşleşme anahtarı (örn. 'NARÇİN RONYA CITY - 1 (VIP WEST)'
    ile 'NARÇİN RONYA CITY - 1' aynı anahtarı üretir)."""
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s or "")
    s = re.sub(r"[^\w\sİŞĞÜÖÇıişğüöç]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("İ", "i").replace("I", "i").replace("ı", "i")
    s = s.replace("Ş", "s").replace("ş", "s").replace("Ğ", "g").replace("ğ", "g")
    s = s.replace("Ç", "c").replace("ç", "c").replace("Ö", "o").replace("ö", "o")
    s = s.replace("Ü", "u").replace("ü", "u")
    return s.lower()


SATIS_TAKIP_RE = re.compile(r"sat\s*ış|satis|takip|fiyat\s*liste|listesi", re.I)


def find_satis_takip(folder):
    """Proje klasöründe SATIŞ TAKİP / FİYAT LİSTESİ dosyasını arar."""
    d = BASE_DIR / "projeler" / (folder or "")
    if not d.exists():
        return None
    cands = [f for f in d.iterdir()
             if f.suffix.lower() in (".pdf", ".xlsx", ".xls", ".csv")
             and SATIS_TAKIP_RE.search(f.name)]
    if not cands:
        return None
    pri = ["satis takip", "satış takip", "satıştakip", "satistakip", "fiyat listesi", "fiyat"]
    cands.sort(key=lambda f: next((i for i, k in enumerate(pri) if k in f.name.lower()), len(pri)))
    return cands[0]


def extract_pdf_prices(path):
    """PDF metninden tüm gerçek fiyatları toplar (ödeme bağlamı elenir)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    prices = []
    try:
        r = PdfReader(str(path))
        for page in r.pages:
            t = page.extract_text() or ""
            for m in PRICE_RE.finditer(t):
                raw = m.group(1) or m.group(2)
                if is_bad_price_context(t, m.start(), m.end()):
                    continue
                v = norm_price(raw)
                if v:
                    prices.append(v)
    except Exception:
        pass
    return prices


def extract_xlsx_prices(path):
    """xlsx'ten fiyat sütunlarını bulup gerçek fiyatları toplar."""
    import openpyxl
    prices = []
    try:
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            header = next(rows, None)
            if not header:
                continue
            price_cols = []
            for i, h in enumerate(header):
                hs = str(h or "").lower()
                if any(k in hs for k in ("fiyat", "satış", "satis", "₺", "tl", "tutar", "bedel", "price")):
                    price_cols.append(i)
            for row in rows:
                for i in price_cols:
                    v = row[i] if i < len(row) else None
                    if isinstance(v, (int, float)) and v >= 500_000:
                        prices.append(int(v))
                    elif isinstance(v, str):
                        for m in PRICE_RE.finditer(v):
                            raw = m.group(1) or m.group(2)
                            if is_bad_price_context(v, m.start(), m.end()):
                                continue
                            nv = norm_price(raw)
                            if nv:
                                prices.append(nv)
        wb.close()
    except Exception:
        pass
    return prices


def satis_takip_prices(folder):
    """SATIŞ TAKİP / FİYAT LİSTESİ dosyası varsa (min, max, display) döner."""
    f = find_satis_takip(folder)
    if not f:
        return None
    prices = []
    if f.suffix.lower() == ".pdf":
        prices = extract_pdf_prices(f)
    elif f.suffix.lower() in (".xlsx", ".xls"):
        prices = extract_xlsx_prices(f)
    elif f.suffix.lower() == ".csv":
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                for m in PRICE_RE.finditer(line):
                    raw = m.group(1) or m.group(2)
                    if is_bad_price_context(line, m.start(), m.end()):
                        continue
                    v = norm_price(raw)
                    if v:
                        prices.append(v)
        except Exception:
            pass
    prices = sorted(set(prices))
    if not prices:
        return None
    lo, hi = prices[0], prices[-1]
    if lo == hi:
        display = (f"₺{lo:,}").replace(",", ".")
    else:
        display = (f"₺{lo:,} - ₺{hi:,}").replace(",", ".")
    return {"price_display": display, "price_min": lo, "price_max": hi, "source": f.name}


def main():
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    projects = db.execute(
        "SELECT * FROM projects WHERE COALESCE(is_portfolio,0)=0 ORDER BY id").fetchall()

    result = {}
    result_by_id = {}
    for p in projects:
        pid = p["id"]
        name = p["name"]
        chunks = db.execute("""
            SELECT d.title, dc.chunk_text
            FROM document_chunks dc JOIN documents d ON dc.document_id = d.id
            WHERE d.project_id = ? ORDER BY dc.id
        """, (pid,)).fetchall()

        prices, rooms, months, desc_cand = [], set(), [], []

        db_price = (p["price_display"] or "").strip()
        for c in chunks:
            t = c["chunk_text"] or ""
            title = c["title"] or ""
            low = t.lower()
            if not db_price:
                for m in PRICE_RE.finditer(t):
                    raw = m.group(1) or m.group(2)
                    if is_bad_price_context(t, m.start(), m.end()):
                        continue
                    v = norm_price(raw)
                    if v:
                        prices.append(v)
            for rm in ROOM_RE.finditer(t):
                rooms.add(f"{rm.group(1)}+{rm.group(2)}")
            if re.search(r"taksit|vade|ödeme|öde|peşinat|kapora", low):
                continue
            for mm in MONTH_RE.finditer(t):
                months.append(int(mm.group(1)))
            if good_text(t) and "iban" not in low and "bank" not in low:
                desc_cand.append(t)

        if db_price and db_price.lower() not in ("bos", "yok", "-", "fiyat"):
            price_display = db_price
            price_min, price_max = None, None
            parts = re.split(r"\s*-\s*|–", db_price.replace("₺", "").replace("TL", "").strip())
            vals = [norm_price(x) for x in parts if x.strip()]
            vals = [v for v in vals if v]
            if vals:
                price_min, price_max = vals[0], vals[-1]
        elif prices:
            if len(prices) >= 4:
                lo, hi = prices[len(prices) // 4], prices[-1]
            else:
                lo, hi = prices[0], prices[-1]
            if lo == hi:
                price_display = (f"₺{lo:,}").replace(",", ".")
            else:
                price_display = (f"₺{lo:,} - ₺{hi:,}").replace(",", ".")
            price_min, price_max = lo, hi
        else:
            price_display, price_min, price_max = "", None, None

        room_list = sorted(rooms, key=lambda r: (int(r.split("+")[0]), int(r.split("+")[1])))
        teslim_ay = max(months) if months else None
        desc = ""
        if desc_cand:
            best = max(desc_cand, key=len)
            desc = re.sub(r"\s+", " ", best).strip()[:320]

        # Preserve canonical knowledge graph fields (down_payment, installment_terms, delivery_months)
        kg_path = BASE_DIR / "nexa_sales_knowledge_graph.json"
        kg_item = {}
        if kg_path.exists():
            try:
                kg_data = json.loads(kg_path.read_text(encoding="utf-8"))
                kg_item = kg_data.get(name) or kg_data.get(p["name"]) or {}
            except Exception:
                pass

        down_payment = kg_item.get("down_payment") or (f"{int(price_min*0.5):,} TL (%50)".replace(",", ".") if price_min else "Peşin / Görüşülür")
        installment_terms = kg_item.get("installment_terms") or "24-36 Ay Vade"
        delivery_months = kg_item.get("delivery_months") or teslim_ay or 24

        result[name] = {
            "title": name,
            "price_display": price_display or kg_item.get("price_display") or "Fiyat Sorunuz",
            "price_min": price_min or kg_item.get("price_min"),
            "price_max": price_max or kg_item.get("price_max"),
            "down_payment": down_payment,
            "installment_terms": installment_terms,
            "delivery_months": delivery_months,
            "teslim_ay": delivery_months,
            "rooms": room_list or kg_item.get("rooms") or ["1+1"],
            "room_types": room_list or kg_item.get("rooms") or ["1+1"],
            "description": desc or kg_item.get("description") or "",
            "chunk_count": len(chunks),
        }
        result_by_id[pid] = result[name]
        print(f"[{pid}] {name}: {price_display or 'fiyat yok'} | odalar: {', '.join(room_list) or '-'} | teslim: {delivery_months or '-'} ay | chunk: {len(chunks)}")

    PRICES_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    if PORTFOLIO_OUT.exists():
        pf = json.loads(PORTFOLIO_OUT.read_text(encoding="utf-8"))
        by_norm = {}
        for key, info in result.items():
            by_norm.setdefault(norm_title(key), info)
        updated = 0
        for item in pf:
            if item.get("type") != "project":
                continue
            info = result.get(item.get("title"))
            if not info:
                nt = norm_title(item.get("title"))
                if nt in by_norm:
                    info = by_norm[nt]
                else:
                    for key, cand in by_norm.items():
                        if nt and (key.startswith(nt) or nt.startswith(key)):
                            info = cand
                            break
            if not info and item.get("db_id"):
                info = result_by_id.get(int(item["db_id"]))
            if not info:
                continue
            
            if info.get("price_display"):
                item["price_display"] = info["price_display"]
            if info.get("price_numeric") is not None and str(info.get("price_numeric")).strip() != "":
                item["price_numeric"] = info["price_numeric"]
            if info.get("price_min") is not None and str(info.get("price_min")).strip() != "":
                item["price_min"] = info["price_min"]
            if info.get("price_max") is not None and str(info.get("price_max")).strip() != "":
                item["price_max"] = info["price_max"]
                
            item["room_info"] = ", ".join(info["rooms"]) if info["rooms"] else ""
            if info.get("description"):
                item["description"] = info["description"]
            updated += 1

        # P19: DB'deki portföy ilanları (is_portfolio=1) JSON envantere senkron —
        # Susanne'in CB sync'i DB'yi günceller; buradan chat/filtre envanteri
        # otonom olarak canlı kalır (db_id veya title ile eşleşme).
        pf_rows = db.execute(
            "SELECT * FROM projects WHERE COALESCE(is_portfolio,0)=1 ORDER BY id"
        ).fetchall()
        pf_ids = {int(it["db_id"]) for it in pf if it.get("db_id")}
        synced = 0
        for p in pf_rows:
            pid = p["id"]
            row = dict(p)
            loc = " / ".join(x for x in [row.get("il"), row.get("ilce"), row.get("mahalle")] if x)
            db_item = {
                "price_display": row.get("price_display") or "",
                "room_info": row.get("room_info") or "",
                "net_gross_area": row.get("net_gross_area") or "",
                "listing_type": row.get("listing_type") or "Satılık",
                "property_category": row.get("property_category") or "Konut / Daire",
                "il": row.get("il") or "",
                "ilce": row.get("ilce") or "",
                "mahalle": row.get("mahalle") or "",
                "ada_no": row.get("ada_no") or "",
                "parsel_no": row.get("parsel_no") or "",
                "tkgm_verified": bool(row.get("tkgm_verified")),
                "description": row.get("description") or "",
            }
            found = next((it for it in pf if int(it.get("db_id") or -1) == pid
                          or it.get("title") == row.get("name")), None)
            if found:
                if "location" in found and not loc:
                    loc = found["location"]
                for k, v in db_item.items():
                    found[k] = v
                if loc:
                    found["location"] = loc
                found["db_id"] = pid
            else:
                pf.append({
                    "id": f"cbvip-prj-db{pid}",
                    "type": "portfolio",
                    "title": row.get("name"),
                    "db_id": pid,
                    "listing_type": row.get("listing_type") or "Satılık",
                    "property_category": row.get("property_category") or "Konut / Daire",
                    **db_item,
                    "location": loc,
                })
            synced += 1
        PORTFOLIO_OUT.write_text(json.dumps(pf, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nnexa_portfolio_data.json guncellendi: {updated}/{len(result)} proje "
              f"+ {synced} portföy ilanı senkron")
    else:
        print("\nnexa_portfolio_data.json bulunamadi — yalnizca fiyat dosyasi yazildi.")

    db.close()
    print(f"nexa_project_prices.json yazildi ({len(result)} proje)")

    _sync_projects_map()


def _sync_projects_map(db_rows=None):
    """DB'deki guncel fiyat/lokasyon verilerini projects_map.json kartlarina isler.
    DB bos alanlari map'teki mevcut degeri korur (kanonik veri kaybi olmaz).
    Boylece CB -> DB -> importer -> MAP -> site zinciri otonom tamamlanir."""
    map_path = BASE_DIR / "static" / "data" / "projects_map.json" if (BASE_DIR / "static" / "data" / "projects_map.json").exists() else BASE_DIR / "projects_map.json"
    if not map_path.exists():
        return
    try:
        with open(map_path, "r", encoding="utf-8") as f:
            projects = json.load(f)
    except Exception as e:
        print(f"projects_map.json okunamadi: {e}")
        return
    if db_rows is None:
        db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            db_rows = db.execute("SELECT * FROM projects").fetchall()
        finally:
            db.close()
    by_id = {r["id"]: r for r in db_rows if r["id"] is not None}
    changed = 0
    for p in projects:
        dbid = p.get("db_id")
        if dbid is None or int(dbid) not in by_id:
            continue
        row = by_id[int(dbid)]
        updates = {}
        for key, col in (("price_display", "price_display"), ("room_info", "room_info"),
                         ("price_min", "price_min"), ("price_max", "price_max"),
                         ("down_payment", "down_payment"), ("price_numeric", "price_numeric")):
            val = row[col]
            if val is not None and str(val).strip() != "":
                updates[key] = val
        il, ilce, mahalle = row["il"], row["ilce"], row["mahalle"]
        if il and ilce and (p.get("il") != il or p.get("ilce") != ilce or p.get("mahalle") != mahalle):
            updates.update({"il": il, "ilce": ilce, "mahalle": mahalle})
            updates["location"] = f"{ilce}, {il}"
            if il and ilce and mahalle:
                updates["location_full"] = f"{il} / {ilce} / {mahalle}"
        for k, v in updates.items():
            if p.get(k) != v:
                p[k] = v
                changed += 1
    if changed:
        map_path.write_text(json.dumps(projects, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"projects_map.json senkron: {changed} alan guncellendi")

    # SATIŞ TAKİP / FİYAT LİSTESİ dosyaları varsa fiyatları ez (daha güncel kaynak).
    st_changed = 0
    for p in projects:
        st = satis_takip_prices(p.get("folder_name"))
        if not st:
            continue
        for k in ("price_display", "price_min", "price_max"):
            if p.get(k) != st[k]:
                p[k] = st[k]
                st_changed += 1
        if st["price_min"] and p.get("price_numeric") != st["price_min"]:
            p["price_numeric"] = st["price_min"]
            st_changed += 1
    if st_changed:
        map_path.write_text(json.dumps(projects, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"SATIS TAKIP fiyat kaynagi: {st_changed} alan guncellendi")

    # Kartlari en uygun fiyatli -> en pahali olarak diz (fiyati bilinmeyenler sona).
    def _card_price(c):
        v = c.get("price_numeric") or c.get("price_min")
        if v:
            return v
        pd = c.get("price_display") or ""
        vals = [norm_price(x) for x in re.split(r"\s*-\s*|–", pd.replace("₺", "").replace("TL", "").strip()) if x.strip()]
        vals = [v for v in vals if v]
        return vals[0] if vals else float("inf")

    keyed = [(c, _card_price(c), i) for i, c in enumerate(projects)]
    keyed.sort(key=lambda x: (x[1] == float("inf"), x[1], x[2]))
    sorted_projects = [c for c, _, _ in keyed]
    if [c.get("id") for c in sorted_projects] != [c.get("id") for c in projects]:
        map_path.write_text(json.dumps(sorted_projects, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"kartlar fiyata gore siralandi (ucuzdan pahaliya): {len(projects)} kart")
        projects = sorted_projects
    return projects


if __name__ == "__main__":
    main()
