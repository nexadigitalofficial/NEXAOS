import os
import re
import json
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Base paths
BASE_DIR = Path(__file__).resolve().parent
GEO_DB_PATH = BASE_DIR / "data" / "geo" / "turkiye_geo.db"

def tr_slugify(text: str) -> str:
    """Normalize Turkish text into ASCII lowercase slug."""
    if not text:
        return ""
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
    text = text.replace("Ğ", "g").replace("ğ", "g")
    text = text.replace("Ü", "u").replace("ü", "u")
    text = text.replace("Ş", "s").replace("ş", "s")
    text = text.replace("Ö", "o").replace("ö", "o")
    text = text.replace("Ç", "c").replace("ç", "c")
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    return re.sub(r"[\s-]+", "-", text)

class GeoRegistry:
    """
    Offline registry indexing 81 provinces, 973 districts, and 32,279 neighborhoods in Turkey.
    Enables sub-millisecond natural language location extraction.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or GEO_DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(f"Geo database not found at {self.db_path}. Run build_geo_index.py first.")
        
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.cur = self.conn.cursor()
        self._load_cache()

    def _load_cache(self):
        # Cache provinces and districts in memory for speed
        self.cur.execute("SELECT id, name, slug FROM provinces")
        self.provinces = {row[2]: {"id": row[0], "name": row[1], "slug": row[2]} for row in self.cur.fetchall()}
        
        self.cur.execute("SELECT id, province_id, name, slug FROM districts")
        self.districts = {}
        for row in self.cur.fetchall():
            self.districts[row[3]] = {
                "id": row[0],
                "province_id": row[1],
                "name": row[2],
                "slug": row[3]
            }

    def resolve_location(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Scans free text for Turkey province, district, and neighborhood entities.
        Returns: (province_slug, district_slug, neighborhood_slug, sahibinden_location_path)
        """
        # Normalize and stem tokens
        raw_tokens = tr_slugify(text).split("-")
        
        # Stem Turkish suffixes from tokens for matching
        def stem_token(tok: str) -> str:
            # Strip locative/ablative/genitive suffixes
            s = re.sub(r"(?:daki|deki|dan|den|tan|ten|da|de|ta|te|nin|nın|ın|in|ya|ye)$", "", tok)
            return s if len(s) >= 3 else tok

        norm_tokens = [stem_token(t) for t in raw_tokens]
        # Also keep original raw tokens
        all_tokens = set(raw_tokens + norm_tokens)

        found_province = None
        found_district = None
        found_neighborhood = None
        found_neighborhood_slug = None
        
        # 1. Match Province
        for prov_slug, prov_data in self.provinces.items():
            if prov_slug in all_tokens:
                found_province = prov_data
                break
                
        # 2. Match District
        if found_province:
            self.cur.execute(
                "SELECT id, name, slug FROM districts WHERE province_id = ?",
                (found_province["id"],)
            )
            dist_rows = self.cur.fetchall()
            for did, dname, dslug in dist_rows:
                if dslug in all_tokens:
                    found_district = {"id": did, "province_id": found_province["id"], "name": dname, "slug": dslug}
                    break
        else:
            # Check all districts if province was omitted
            for dist_slug, dist_data in self.districts.items():
                if dist_slug in all_tokens:
                    found_district = dist_data
                    for p_slug, p_data in self.provinces.items():
                        if p_data["id"] == dist_data["province_id"]:
                            found_province = p_data
                            break
                    break

        # 3. Match Neighborhood (within district)
        # Exclude common search keywords from accidental neighborhood matching
        NEIGH_STOPWORDS = {"yeni", "eski", "merkez", "orta", "satilik", "kiralik", "villa", "daire", "arsa", "tarla", "konut", "ilanlar", "ilan"}
        if found_district:
            self.cur.execute(
                "SELECT id, name, slug FROM neighborhoods WHERE district_id = ? ORDER BY length(slug) DESC",
                (found_district["id"],)
            )
            neigh_rows = self.cur.fetchall()
            for nid, nname, nslug in neigh_rows:
                # If slug is a stopword, require exact 'mahalle' mention
                if nslug in NEIGH_STOPWORDS and not any(m in text.lower() for m in [f"{nslug} mah", f"{nslug} mh"]):
                    continue
                if nslug in all_tokens:
                    found_neighborhood = {"id": nid, "name": nname, "slug": nslug}
                    found_neighborhood_slug = nslug
                    break

        # 4. Fallback: Check if there's a custom mevki/ada token right in text (e.g. bozburunadalari)
        custom_mevki = None
        if found_district and not found_neighborhood_slug:
            EXCLUDE_MEVKI = ["satilik", "kiralik", "hisseli", "tapu", "parsel", "arsa", "villa", "daire", "fiyat", "yeni", "milyon", "bin", "metrekare", "katli", "odali", "yasinda", "artan", "azalan", "getir", "olan"]
            for tok in raw_tokens:
                if tok not in [found_province["slug"] if found_province else "", found_district["slug"]] and len(tok) >= 5:
                    if not any(k in tok for k in EXCLUDE_MEVKI):
                        custom_mevki = tok
                        break

        # Build Sahibinden location path
        if found_province and found_district and (found_neighborhood_slug or custom_mevki):
            p_slug = found_province["slug"]
            d_slug = found_district["slug"]
            if found_neighborhood_slug:
                n_slug = found_neighborhood_slug
                n_slug_path = f"{n_slug}." if n_slug.endswith("-mah") else f"{n_slug}-mah."
                path = f"{p_slug}-{d_slug}-{d_slug}-{n_slug_path}"
                return p_slug, d_slug, found_neighborhood_slug, path
            else:
                # Custom mevki path (e.g. izmir-aliaga-aliaga-bozburunadalari)
                path = f"{p_slug}-{d_slug}-{d_slug}-{custom_mevki}"
                return p_slug, d_slug, custom_mevki, path
            
        elif found_province and found_district:
            p_slug = found_province["slug"]
            d_slug = found_district["slug"]
            path = f"{p_slug}-{d_slug}"
            return p_slug, d_slug, None, path
            
        elif found_province:
            p_slug = found_province["slug"]
            return p_slug, None, None, p_slug
            
        return None, None, None, ""

class SahibindenUrlBuilder:
    """
    Precision URL Builder for Sahibinden real estate search queries.
    Encapsulates all reverse-engineered attribute IDs, path embeddings, and multi-value parameters.
    """
    
    # Reverse-Engineered Attribute Constants
    ODA_SAYISI_MAP = {
        "1+0": 40599, "stüdyo": 40599,
        "1+1": 40600,
        "2+1": 40601,
        "3+1": 40602,
        "4+1": 40603,
        "5+1": 40604,
        "6+1": 40605,
    }
    
    BINA_YASI_MAP = {
        "0": 40590, "sıfır": 40590,
        "1": 40591,
        "2": 40592,
        "3": 40593,
        "4": 40594,
        "5": 40595,
    }
    
    KAT_SAYISI_MAP = {
        "1": 40582,
        "2": 40583,
        "3": 40584,
        "4": 40585,
    }
    
    BULUNDUGU_KAT_MAP = {
        "1": 40570,
        "2": 40571,
        "3": 40572,
        "bahçe katı": 40565,
        "yüksek giriş": 40568,
        "arakat": 40575,
        "en üst kat": 40578
    }
    
    KIMDEN_MAP = {
        "sahibinden": 38460,
        "emlak ofisinden": 38461,
        "emlakçı": 38461,
        "inşaat firmasından": 38462,
        "bankadan": 1137837
    }
    
    TAPU_DURUMU_PATH_MAP = {
        "hisseli tapu": "hisseli-tapu",
        "hisseli": "hisseli-tapu",
        "müstakil tapu": "mustakil-tapu",
        "müstakil parsel": "mustakil-parsel",
        "müstakil": "mustakil-tapu",
        "tahsis tapu": "tahsis-tapu",
        "zilliyet": "zilliyet-tapu",
        "kooperatif": "kooperatif-hisseli-tapu"
    }
    
    IMAR_DURUMU_MAP = {
        "eğitim": 1312094,
        "konut": 1312085,
        "ticari": 1312086,
        "sanayi": 1312088,
        "tarla": 1312090,
        "bağ & bahçe": 1312091,
        "bağ bahçe": 1312091
    }
    
    KAKS_EMSAL_MAP = {
        "0.12": 70787,
        "0.05": 70784,
        "0.10": 70786,
        "0.15": 70788,
        "0.20": 70789,
        "0.25": 70790
    }
    
    SORTING_OPTIONS = {
        "price_asc": "price_asc",        # Fiyata göre artan (en düşük)
        "price_desc": "price_desc",      # Fiyata göre azalan (en yüksek)
        "date_desc": "date_desc",        # Tarihe göre en yeni
        "date_asc": "date_asc",          # Tarihe göre en eski
        "m2_asc": "m2_asc",              # m²'ye göre artan
        "m2_desc": "m2_desc",            # m²'ye göre azalan
    }

    def __init__(
        self,
        category: str = "satilik",
        location_path: str = "",
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        m2_min: Optional[int] = None,
        m2_max: Optional[int] = None,
        oda_sayisi: Optional[List[str]] = None,
        bina_yasi: Optional[List[str]] = None,
        kat_sayisi: Optional[str] = None,
        bulundugu_kat: Optional[str] = None,
        kimden: Optional[str] = None,
        tapu_durumu: Optional[str] = None,
        ada_min: Optional[int] = None,
        ada_max: Optional[int] = None,
        parsel_min: Optional[int] = None,
        parsel_max: Optional[int] = None,
        imar_durumu: Optional[str] = None,
        kaks_emsal: Optional[str] = None,
        sorting: Optional[str] = None,
        paging_offset: int = 0
    ):
        self.category = category.strip("/ ")
        self.location_path = location_path.strip("/ ")
        self.price_min = price_min
        self.price_max = price_max
        self.m2_min = m2_min
        self.m2_max = m2_max
        self.oda_sayisi = oda_sayisi or []
        self.bina_yasi = bina_yasi or []
        self.kat_sayisi = kat_sayisi
        self.bulundugu_kat = bulundugu_kat
        self.kimden = kimden
        self.tapu_durumu = tapu_durumu
        self.ada_min = ada_min
        self.ada_max = ada_max
        self.parsel_min = parsel_min
        self.parsel_max = parsel_max
        self.imar_durumu = imar_durumu
        self.kaks_emsal = kaks_emsal
        self.sorting = sorting
        self.paging_offset = paging_offset

    def build_url(self) -> str:
        """
        Generates the exact Sahibinden URL following all reverse-engineered rules.
        """
        # 1. Base Path
        base = "https://www.sahibinden.com"
        path_parts = [self.category]
        if self.location_path:
            path_parts.append(self.location_path)
            
        # Tapu Durumu is appended to path segment if present
        if self.tapu_durumu:
            norm_tapu = self.tapu_durumu.lower().strip()
            tapu_slug = self.TAPU_DURUMU_PATH_MAP.get(norm_tapu, tr_slugify(norm_tapu))
            path_parts.append(tapu_slug)
            
        full_path = "/" + "/".join(path_parts)
        
        # 2. Query Parameters
        params: List[Tuple[str, Any]] = []
        
        # Price
        if self.price_min is not None:
            params.append(("price_min", str(self.price_min)))
        if self.price_max is not None:
            params.append(("price_max", str(self.price_max)))
            
        # Square Meters (Brüt a24 & Net a107889)
        if self.m2_min is not None:
            params.append(("a24_min", str(self.m2_min)))
            params.append(("a107889_min", str(self.m2_min)))
        if self.m2_max is not None:
            params.append(("a24_max", str(self.m2_max)))
            params.append(("a107889_max", str(self.m2_max)))
            
        # Room Count (a812 - Multi-select supported!)
        for oda in self.oda_sayisi:
            oda_clean = oda.strip().lower()
            if oda_clean in self.ODA_SAYISI_MAP:
                params.append(("a812", str(self.ODA_SAYISI_MAP[oda_clean])))
                
        # Building Age (a811 - Multi-select supported!)
        for yas in self.bina_yasi:
            yas_clean = str(yas).strip().lower()
            if yas_clean in self.BINA_YASI_MAP:
                params.append(("a811", str(self.BINA_YASI_MAP[yas_clean])))
                
        # Kat Sayısı (a810)
        if self.kat_sayisi and str(self.kat_sayisi) in self.KAT_SAYISI_MAP:
            params.append(("a810", str(self.KAT_SAYISI_MAP[str(self.kat_sayisi)])))
            
        # Kimden (a27)
        if self.kimden:
            k_clean = self.kimden.strip().lower()
            if k_clean in self.KIMDEN_MAP:
                params.append(("a27", str(self.KIMDEN_MAP[k_clean])))
                
        # Ada No (a28364_min / max)
        if self.ada_min is not None:
            params.append(("a28364_min", str(self.ada_min)))
        if self.ada_max is not None:
            params.append(("a28364_max", str(self.ada_max)))
            
        # Parsel No (a28365_min / max)
        if self.parsel_min is not None:
            params.append(("a28365_min", str(self.parsel_min)))
        if self.parsel_max is not None:
            params.append(("a28365_max", str(self.parsel_max)))
            
        # İmar Durumu (a4243)
        if self.imar_durumu:
            imar_clean = self.imar_durumu.strip().lower()
            if imar_clean in self.IMAR_DURUMU_MAP:
                params.append(("a4243", str(self.IMAR_DURUMU_MAP[imar_clean])))
                
        # KAKS / Emsal (a3790)
        if self.kaks_emsal:
            kaks_clean = str(self.kaks_emsal).strip().lower()
            if kaks_clean in self.KAKS_EMSAL_MAP:
                params.append(("a3790", str(self.KAKS_EMSAL_MAP[kaks_clean])))
                
        # Sorting (asc/desc)
        if self.sorting and self.sorting in self.SORTING_OPTIONS:
            params.append(("sorting", self.sorting))
            
        # Paging offset
        if self.paging_offset > 0:
            params.append(("pagingOffset", str(self.paging_offset)))
            
        # Construct Query String
        if params:
            query_str = urllib.parse.urlencode(params, doseq=True)
            return f"{base}{full_path}?{query_str}"
        return f"{base}{full_path}"

class NexaNlpToLink:
    """
    Intelligent Natural Language Processor that translates Turkish real estate prompts into
    fully compliant Sahibinden search URLs.
    """
    def __init__(self, geo_registry: Optional[GeoRegistry] = None):
        self.geo = geo_registry or GeoRegistry()

    def parse_with_gemini(self, prompt: str, api_key: str) -> Tuple[SahibindenUrlBuilder, str]:
        """
        Uses Gemini API (gemini-1.5-flash) to extract real estate search criteria,
        then validates and resolves locations against the official 32,279 neighborhoods registry.
        """
        if not api_key or not api_key.strip():
            return self.parse(prompt), "Nexa Offline Geo Engine (32.279 Mahalle)"
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
        headers = {"Content-Type": "application/json"}
        
        system_instruction = (
            "Sen uzman bir Türk gayrimenkul analistisin. Kullanıcının Türkçe arama metnini analiz edip JSON döndür.\n"
            "Döndürülecek JSON Şeması:\n"
            "{\n"
            '  "action": "satilik" veya "kiralik",\n'
            '  "category": "villa", "daire", "arsa", "is-yeri", "bina" veya "konut",\n'
            '  "province": "il adı" veya null,\n'
            '  "district": "ilçe adı" veya null,\n'
            '  "neighborhood": "mahalle veya mevki adı" veya null,\n'
            '  "price_min": integer (TL) veya null,\n'
            '  "price_max": integer (TL) veya null,\n'
            '  "m2_min": integer veya null,\n'
            '  "m2_max": integer veya null,\n'
            '  "rooms": ["4+1", "3+1"] vb veya [],\n'
            '  "building_age": ["0", "1", "2"] vb veya [],\n'
            '  "floor": string veya null,\n'
            '  "from_who": "bankadan", "sahibinden", "emlak ofisinden" veya null,\n'
            '  "title_status": "hisseli tapu", "müstakil tapu" vb veya null,\n'
            '  "ada_min": integer veya null,\n'
            '  "ada_max": integer veya null,\n'
            '  "parsel_min": integer veya null,\n'
            '  "parsel_max": integer veya null,\n'
            '  "imar_durumu": "eğitim", "konut", "ticari", "sanayi", "tarla" veya null,\n'
            '  "kaks_emsal": "0.12" vb veya null,\n'
            '  "sorting": "price_asc", "price_desc", "date_desc", "date_asc" veya null\n'
            "}\n"
            "ÖNEMLİ: Sadece saf JSON döndür. Ek açıklama yazma."
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_instruction}\n\nArama Metni: \"{prompt}\"\n\nJSON Çıktısı:"}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 600,
                "responseMimeType": "application/json"
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                g_data = json.loads(raw_text)
                
                # Combine location terms to resolve officially
                loc_query = " ".join([
                    g_data.get("province") or "",
                    g_data.get("district") or "",
                    g_data.get("neighborhood") or ""
                ]).strip()
                if not loc_query:
                    loc_query = prompt
                    
                prov, dist, neigh, loc_path = self.geo.resolve_location(loc_query)
                
                # Determine category
                action = g_data.get("action") or "satilik"
                cat_raw = g_data.get("category") or "konut"
                if cat_raw in ["villa", "daire", "arsa", "is-yeri", "bina"]:
                    cat = f"{action}-{cat_raw}"
                else:
                    cat = f"{action}"
                    
                # Sorting
                sort = g_data.get("sorting") or self._extract_sorting(prompt.lower())
                
                # Price and m2 with local engine fallback
                p_min = g_data.get("price_min")
                p_max = g_data.get("price_max")
                if p_min is None and p_max is None:
                    p_min, p_max = self._extract_price_range(prompt)
                    
                m_min = g_data.get("m2_min")
                m_max = g_data.get("m2_max")
                if m_min is None and m_max is None:
                    m_min, m_max = self._extract_m2_range(prompt)

                builder = SahibindenUrlBuilder(
                    category=cat,
                    location_path=loc_path,
                    price_min=p_min,
                    price_max=p_max,
                    m2_min=m_min,
                    m2_max=m_max,
                    oda_sayisi=g_data.get("rooms") or [],
                    bina_yasi=g_data.get("building_age") or [],
                    kat_sayisi=g_data.get("floor"),
                    kimden=g_data.get("from_who"),
                    tapu_durumu=g_data.get("title_status"),
                    ada_min=g_data.get("ada_min"),
                    ada_max=g_data.get("ada_max"),
                    parsel_min=g_data.get("parsel_min"),
                    parsel_max=g_data.get("parsel_max"),
                    imar_durumu=g_data.get("imar_durumu"),
                    kaks_emsal=g_data.get("kaks_emsal"),
                    sorting=sort
                )
                return builder, "Gemini 1.5 Flash + Nexa Geo Registry"
        except Exception as e:
            print(f"[WARN] Gemini API çağrısı başarısız, yerel motor devrede: {e}")
            return self.parse(prompt), "Nexa Offline Geo Engine (32.279 Mahalle)"

    def parse(self, prompt: str) -> SahibindenUrlBuilder:
        """
        Parses free-form Turkish text into a SahibindenUrlBuilder instance.
        """
        p_lower = prompt.lower()
        
        # 1. Action Type: Satılık vs Kiralık
        is_kiralik = any(w in p_lower for w in ["kiralik", "kiralık", "kira"])
        action = "kiralik" if is_kiralik else "satilik"
        
        # 2. Main Category
        category = "satilik" if action == "satilik" else "kiralik"
        if any(w in p_lower for w in ["arsa", "tarla", "parsel", "arazi"]):
            category = f"{action}-arsa"
        elif any(w in p_lower for w in ["villa", "müstakil", "mustakil"]):
            category = f"{action}-villa"
        elif any(w in p_lower for w in ["daire", "rezidans", "residence", "apartman"]):
            category = f"{action}-daire"
        elif any(w in p_lower for w in ["iş yeri", "is yeri", "dükkan", "dukkan", "ofis", "fabrika", "depo"]):
            category = f"{action}-is-yeri"
        elif any(w in p_lower for w in ["bina", "apartman binası"]):
            category = f"{action}-bina"
            
        # 3. Location Resolution (İl, İlçe, Mahalle)
        prov, dist, neigh, loc_path = self.geo.resolve_location(prompt)
        
        # 4. Price Parsing (e.g., 2 milyon ile 5 milyon, 2.000.000 - 5.000.000, 20 bin, vb.)
        price_min, price_max = self._extract_price_range(prompt)
        
        # 5. Square Meter Parsing (e.g. 100 ile 200 m2, 150 metrekare)
        m2_min, m2_max = self._extract_m2_range(prompt)
        
        # 6. Room Count Parsing (e.g. 4+1, 3+1, 2+1, 1+1)
        rooms = re.findall(r"\b([1-6]\+[0-2])\b", prompt)
        
        # 7. Building Age Parsing (e.g. sıfır bina, 2 yaşında, 0-5 yaş)
        bina_yasi = []
        if "sıfır" in p_lower or "0 yaş" in p_lower:
            bina_yasi.append("0")
        age_match = re.search(r"\b([1-5])\s*(?:yaş|yas|yasinda|yaşında)\b", p_lower)
        if age_match:
            bina_yasi.append(age_match.group(1))
            
        # 8. Kat Sayısı / Bulunduğu Kat
        kat_sayisi = None
        ks_match = re.search(r"\b([1-7])\s*katlı\b", p_lower)
        if ks_match:
            kat_sayisi = ks_match.group(1)
            
        # 9. Kimden Parsing (Bankadan, Sahibinden, Emlakçıdan)
        kimden = None
        if "bankadan" in p_lower:
            kimden = "bankadan"
        elif "sahibinden" in p_lower:
            kimden = "sahibinden"
        elif "emlakçı" in p_lower or "emlak ofisi" in p_lower:
            kimden = "emlak ofisinden"
            
        # 10. Tapu Durumu (Arsa için)
        tapu_durumu = None
        if "hisseli" in p_lower:
            tapu_durumu = "hisseli tapu"
        elif "müstakil" in p_lower or "mustakil" in p_lower:
            tapu_durumu = "müstakil tapu"
            
        # 11. Ada & Parsel (Arsa için: ada 100-105 parsel 5-6)
        ada_min, ada_max = self._extract_range(prompt, r"ada\s*(\d+)(?:\s*(?:-|ile|to)\s*(\d+))?")
        parsel_min, parsel_max = self._extract_range(prompt, r"parsel\s*(\d+)(?:\s*(?:-|ile|to)\s*(\d+))?")
        
        # 12. İmar Durumu & Emsal/KAKS
        imar_durumu = None
        for imar_key in SahibindenUrlBuilder.IMAR_DURUMU_MAP:
            if imar_key in p_lower:
                imar_durumu = imar_key
                break
                
        kaks_emsal = None
        kaks_match = re.search(r"(?:kaks|emsal)\s*[:=]?\s*(0\.\d{2})", p_lower)
        if kaks_match:
            kaks_emsal = kaks_match.group(1)
            
        # 13. Sorting (Fiyata göre artan/azalan, tarihe göre yeni/eski, vb.)
        sorting = self._extract_sorting(p_lower)
        
        return SahibindenUrlBuilder(
            category=category,
            location_path=loc_path,
            price_min=price_min,
            price_max=price_max,
            m2_min=m2_min,
            m2_max=m2_max,
            oda_sayisi=rooms,
            bina_yasi=bina_yasi,
            kat_sayisi=kat_sayisi,
            kimden=kimden,
            tapu_durumu=tapu_durumu,
            ada_min=ada_min,
            ada_max=ada_max,
            parsel_min=parsel_min,
            parsel_max=parsel_max,
            imar_durumu=imar_durumu,
            kaks_emsal=kaks_emsal,
            sorting=sorting
        )

    def _extract_sorting(self, text: str) -> Optional[str]:
        """Detects user sorting preference (asc, desc, date, etc.)."""
        if any(w in text for w in ["fiyata göre artan", "fiyat artan", "artan fiyat", "en ucuz", "en uygun", "ucuzdan pahalıya", "price_asc", "asc"]):
            return "price_asc"
        elif any(w in text for w in ["fiyata göre azalan", "fiyat azalan", "azalan fiyat", "en pahalı", "pahalıdan ucuza", "price_desc", "desc"]):
            return "price_desc"
        elif any(w in text for w in ["tarihe göre en yeni", "en yeni", "yeni ilanlar", "son eklenen", "tarihe göre", "date_desc"]):
            return "date_desc"
        elif any(w in text for w in ["tarihe göre en eski", "en eski", "date_asc"]):
            return "date_asc"
        elif any(w in text for w in ["m2 artan", "metrekare artan", "küçükten büyüğe"]):
            return "m2_asc"
        elif any(w in text for w in ["m2 azalan", "metrekare azalan", "büyükten küçüğe"]):
            return "m2_desc"
        return None

    def _extract_range(self, text: str, pattern: str) -> Tuple[Optional[int], Optional[int]]:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return None, None
        v1 = int(match.group(1))
        v2 = int(match.group(2)) if match.group(2) else v1
        return min(v1, v2), max(v1, v2)

    def _extract_price_range(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Parses millions, thousands, or raw numbers for price ranges and target budgets."""
        t = text.lower()
        
        # 1. Range millions: e.g. 20-40 milyon, 20 milyon ile 40 milyon
        m_range = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:milyon)?\s*(?:-|ile|ve|ila|ila\s+kadar)\s*(\d+(?:[.,]\d+)?)\s*milyon', t)
        if m_range:
            v1 = float(m_range.group(1).replace(',', '.')) * 1_000_000
            v2 = float(m_range.group(2).replace(',', '.')) * 1_000_000
            return int(min(v1, v2)), int(max(v1, v2))

        # 2. Range thousands: e.g. 20-50 bin, 20 bin ile 50 bin
        k_range = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:bin)?\s*(?:-|ile|ve|ila)\s*(\d+(?:[.,]\d+)?)\s*bin', t)
        if k_range:
            v1 = float(k_range.group(1).replace(',', '.')) * 1_000
            v2 = float(k_range.group(2).replace(',', '.')) * 1_000
            return int(min(v1, v2)), int(max(v1, v2))

        # 3. Raw number range: e.g. 2.000.000 - 5.000.000
        raw_range = re.search(r'(\d{1,3}(?:\.\d{3})+|\d{5,10})\s*(?:-|ile)\s*(\d{1,3}(?:\.\d{3})+|\d{5,10})', t)
        if raw_range:
            v1 = int(raw_range.group(1).replace('.', ''))
            v2 = int(raw_range.group(2).replace('.', ''))
            return min(v1, v2), max(v1, v2)

        # 4. Single million with min indicators (uzeri, baslayan, en az, minimum, min)
        min_m = re.search(r'(?:en az|minimum|min|başlayan|baslayan)\s*(\d+(?:[.,]\d+)?)\s*milyon|(\d+(?:[.,]\d+)?)\s*milyon(?:dan|den)?\s*(?:üzeri|uzeri|fazla|üstü|ustu|başlayan|baslayan)', t)
        if min_m:
            val_str = min_m.group(1) or min_m.group(2)
            v = int(float(val_str.replace(',', '.')) * 1_000_000)
            return v, None

        # 5. Single million with max or target indicators (40 milyona, 40 milyonluk, 40 milyon tl, 40 milyona kadar, vb.)
        max_m = re.search(r'(\d+(?:[.,]\d+)?)\s*milyon(?:a\s+kadar|a|luk|lük|lik|e|e\s+kadar|\s+altı|\s+alti|\s+altinda|\s+kadar|\s+tl)?', t)
        if max_m:
            v = int(float(max_m.group(1).replace(',', '.')) * 1_000_000)
            return None, v

        # 6. Single thousands with max indicators (50 bine, 50 binlik, 50 bin tl)
        max_k = re.search(r'(\d+(?:[.,]\d+)?)\s*bin(?:e\s+kadar|e|lik|lik|\s+altı|\s+alti|\s+kadar|\s+tl)?', t)
        if max_k:
            v = int(float(max_k.group(1).replace(',', '.')) * 1_000)
            return None, v

        return None, None

    def _extract_m2_range(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Parses square meter ranges."""
        m2_match = re.search(r"(\d+)\s*(?:-|ile|to)\s*(\d+)\s*(?:m2|m²|metrekare)", text, re.IGNORECASE)
        if m2_match:
            v1, v2 = int(m2_match.group(1)), int(m2_match.group(2))
            return min(v1, v2), max(v1, v2)
        single_m2 = re.search(r"(\d+)\s*(?:m2|m²|metrekare)", text, re.IGNORECASE)
        if single_m2:
            val = int(single_m2.group(1))
            if any(w in text.lower() for w in ["üzeri", "en az", "minimum"]):
                return val, None
            elif any(w in text.lower() for w in ["altı", "en çok", "maksimum"]):
                return None, val
            return val, val
        return None, None

class NexaUltraSearchPipeline:
    """
    End-to-End Autonomous Pipeline:
    Natural Language Prompt -> Search URL -> Cloud Scraper -> Bento Showcase
    """
    def __init__(self):
        self.nlp = NexaNlpToLink()

    def execute(
        self,
        nlp_prompt: str,
        auto_scrape: bool = False,
        max_items: int = 10,
        desktop_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes NLP translation and optional scraping pipeline.
        """
        print("\n" + "="*60)
        print("  NEXA.OS NLP TO LINK & AUTONOMOUS CRAWLER ENGINE")
        print("="*60)
        print(f"  [NLP SORGUSU] : {nlp_prompt}")
        
        # 1. Step: Parse NLP to Sahibinden URL
        builder = self.nlp.parse(nlp_prompt)
        target_url = builder.build_url()
        
        print(f"  [KATEGORİ]    : {builder.category}")
        print(f"  [LOKASYON]    : {builder.location_path}")
        print(f"  [FİYAT]       : {builder.price_min} - {builder.price_max}")
        print(f"  [SIRALAMA]    : {builder.sorting or 'Varsayılan'}")
        print(f"\n  [URETILEN URL]:\n  -> {target_url}\n")
        
        result: Dict[str, Any] = {
            "prompt": nlp_prompt,
            "url": target_url,
            "builder": {
                "category": builder.category,
                "location_path": builder.location_path,
                "price_min": builder.price_min,
                "price_max": builder.price_max,
                "m2_min": builder.m2_min,
                "m2_max": builder.m2_max,
                "oda_sayisi": builder.oda_sayisi,
                "bina_yasi": builder.bina_yasi,
                "sorting": builder.sorting,
                "tapu_durumu": builder.tapu_durumu,
                "kimden": builder.kimden,
                "ada_min": builder.ada_min,
                "ada_max": builder.ada_max,
                "parsel_min": builder.parsel_min,
                "parsel_max": builder.parsel_max,
            },
            "scraped": False,
            "listings": []
        }
        
        # 2. Step: Optional Scraping
        if auto_scrape:
            try:
                from app import step1_pagespeed_store, step2_extract_summaries, _scrape_via_psi_api
                print("[SCRAPE] PageSpeed Bulut Motoru ile taranıyor...")
                ps_html = step1_pagespeed_store(target_url, "pagespeed_nlp_search.html", wait_sec=40)
                summaries = step2_extract_summaries(ps_html)
                print(f"[SCRAPE] {len(summaries)} ilan tespit edildi!")
                
                # Take up to max_items
                selected = summaries[:max_items]
                listings = []
                for s in selected:
                    u = s.detail_url or f"https://www.sahibinden.com/ilan/{s.listing_id}/detay"
                    dt = _scrape_via_psi_api(u)
                    if dt and dt.get("ok"):
                        listings.append(dt)
                        
                result["scraped"] = True
                result["listings"] = listings
                print(f"[OK] {len(listings)} adet ilan tam detaylarıyla çekildi.")
            except Exception as e:
                print(f"[WARN] Otomatik kazıma sırasında hata: {e}")
                result["scrape_error"] = str(e)
                
        return result

if __name__ == "__main__":
    import sys
    pipeline = NexaUltraSearchPipeline()
    
    if len(sys.argv) > 1:
        auto_scrape_flag = "--scrape" in sys.argv
        query_parts = [a for a in sys.argv[1:] if a != "--scrape"]
        custom_query = " ".join(query_parts)
        pipeline.execute(custom_query, auto_scrape=auto_scrape_flag)
    else:
        # Default test suite
        test_queries = [
            "Ankara Çankaya Alacaatlı'da 20 milyon ile 40 milyon arası 4+1 satılık villa getir fiyata göre artan",
            "İzmir Aliağa Bozburunadaları hisseli tapu ada 100-105 parsel 5-6 satılık arsa en yeni ilanlar",
            "Antalya Döşemealtı Çığlık Ayanlar kiralık daire fiyata göre azalan",
            "Ankara bankadan satılık konut 2 milyon ile 5 milyon arası 4+1 2 yaşında 100-200 metrekare"
        ]
        
        for q in test_queries:
            res = pipeline.execute(q, auto_scrape=False)
            print("-" * 60)
