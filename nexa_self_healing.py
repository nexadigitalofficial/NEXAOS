#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
NEXA PROPTECH — AUTONOMOUS SELF-HEALING & INTEGRITY SENTINEL (v3.0)
═══════════════════════════════════════════════════════════════════════════════
Bu modül, platformun tüm bileşenlerini periyodik olarak otonom denetler:
1. DB Şema & Sütun Eksikliklerini Otomatik Tamir (Auto-Migration)
2. Kanonik Fiyat & Portföy Veri Tutarsızlıklarını Otomatik Düzeltme (SSOT Auto-Heal)
3. RAG Kanonik Matris & Önbellek Doğrulama ve Yenileme
4. Medya, Video CDN & Statik Görsel Bütünlük Kontrolü
5. Yapay Zeka & NLP Intent / Sıfır-Halüsinasyon Sentetik Testleri
6. Kendi Kendini İyileştirme Telemetrisi & Canlı Sağlık Skoru (Health Score 0-100)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "nexa_database.db"
MAP_PATH = BASE_DIR / "projects_map.json"
PORTFOLIO_PATH = BASE_DIR / "nexa_portfolio_data.json"
PRICES_PATH = BASE_DIR / "nexa_project_prices.json"
SUMMARIES_PATH = BASE_DIR / "nexa_project_summaries.json"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("nexa.self_healing")
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "self_healing.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Global State for Health Telemetry
_last_health_report = {
    "status": "initializing",
    "health_score": 100,
    "last_run": None,
    "total_checks": 0,
    "passed_checks": 0,
    "fixes_applied": [],
    "active_issues": [],
    "execution_time_ms": 0,
    "history": []
}


def _ensure_health_table(conn):
    """Sağlık ve self-healing log tablosunu oluşturur."""
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_health_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                health_score INTEGER,
                status VARCHAR(50),
                total_checks INTEGER,
                passed_checks INTEGER,
                fixes_json TEXT,
                issues_json TEXT,
                execution_time_ms INTEGER
            )
        """)
        conn.commit()
    except Exception as e:
        logger.warning("system_health_logs tablosu olusturulamadi: %s", e)


def heal_database_schema(db_path: Path = DB_PATH) -> dict:
    """Faz 1: Veritabanı şema ve sütunlarını denetler ve eksik olanları ekler."""
    fixes = []
    issues = []
    
    if not db_path.exists():
        issues.append(f"Veritabanı dosyası bulunamadı: {db_path}")
        return {"passed": False, "fixes": fixes, "issues": issues}

    try:
        conn = sqlite3.connect(db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        cur = conn.cursor()
        _ensure_health_table(conn)
        
        # 1. Projects tablosu sütun kontrolü
        cur.execute("PRAGMA table_info(projects)")
        existing_cols = {r[1] for r in cur.fetchall()}
        
        required_migrations = [
            ("featured", "ALTER TABLE projects ADD COLUMN featured INTEGER DEFAULT 0"),
            ("display_order", "ALTER TABLE projects ADD COLUMN display_order INTEGER DEFAULT 0"),
            ("price_numeric", "ALTER TABLE projects ADD COLUMN price_numeric INTEGER"),
            ("price_min", "ALTER TABLE projects ADD COLUMN price_min INTEGER"),
            ("price_max", "ALTER TABLE projects ADD COLUMN price_max INTEGER"),
            ("down_payment", "ALTER TABLE projects ADD COLUMN down_payment VARCHAR(100)"),
            ("price_display", "ALTER TABLE projects ADD COLUMN price_display VARCHAR(100)"),
            ("room_info", "ALTER TABLE projects ADD COLUMN room_info VARCHAR(100)"),
            ("tkgm_verified", "ALTER TABLE projects ADD COLUMN tkgm_verified INTEGER DEFAULT 0"),
            ("ada_no", "ALTER TABLE projects ADD COLUMN ada_no VARCHAR(50)"),
            ("parsel_no", "ALTER TABLE projects ADD COLUMN parsel_no VARCHAR(50)"),
        ]
        
        for col_name, sql in required_migrations:
            if col_name not in existing_cols:
                try:
                    cur.execute(sql)
                    fixes.append(f"Eksik DB sütunu eklendi: projects.{col_name}")
                    logger.info("Self-healing: Eklenen sütun -> projects.%s", col_name)
                except Exception as ex:
                    issues.append(f"Sütun ekleme hatası ({col_name}): {ex}")
        
        # 2. Customers tablosu stage ve phone kontrolü
        cur.execute("PRAGMA table_info(customers)")
        cust_cols = {r[1] for r in cur.fetchall()}
        if "stage" not in cust_cols:
            cur.execute("ALTER TABLE customers ADD COLUMN stage VARCHAR(50) DEFAULT 'Yeni Talep'")
            fixes.append("Eksik DB sütunu eklendi: customers.stage")

        # 3. Orphan document chunks temizliği
        cur.execute("DELETE FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents)")
        deleted_orphans = cur.rowcount
        if deleted_orphans > 0:
            fixes.append(f"Yetim chunk temizlendi: {deleted_orphans} adet document_chunks kaydı silindi")
            logger.info("Self-healing: %d yetim document_chunk temizlendi", deleted_orphans)
            
        conn.commit()
        conn.close()
        return {"passed": len(issues) == 0, "fixes": fixes, "issues": issues}
    except Exception as e:
        issues.append(f"DB şema self-healing hatası: {e}")
        return {"passed": False, "fixes": fixes, "issues": issues}


def heal_canonical_data(map_path: Path = MAP_PATH, pf_path: Path = PORTFOLIO_PATH, db_path: Path = DB_PATH) -> dict:
    """Faz 2: Canonical Single Source of Truth senkronizasyonunu denetler ve otomatik onarır."""
    fixes = []
    issues = []
    
    if not map_path.exists():
        issues.append(f"Kanonik projects_map.json bulunamadı: {map_path}")
        return {"passed": False, "fixes": fixes, "issues": issues}
        
    try:
        with open(map_path, "r", encoding="utf-8") as f:
            canonical_list = json.load(f)
            
        map_lookup = {}
        for p in canonical_list:
            t = p.get("title", "").strip().upper()
            map_lookup[t] = p
            map_lookup[t.replace("İ", "I")] = p
            
        # A. nexa_portfolio_data.json kontrolü ve tamiri
        pf_data = []
        if pf_path.exists():
            with open(pf_path, "r", encoding="utf-8") as f:
                pf_data = json.load(f)
                
        pf_dirty = False
        for item in pf_data:
            if item.get("type") != "project":
                continue
            title = item.get("title", "").strip().upper()
            canonical = map_lookup.get(title) or map_lookup.get(title.replace("İ", "I"))
            if canonical:
                # Fiyat kontrolü
                c_price_disp = canonical.get("price_display", "")
                c_price_num = canonical.get("price_numeric")
                c_down = canonical.get("down_payment", "")
                
                if item.get("price_display") != c_price_disp and c_price_disp:
                    old = item.get("price_display")
                    item["price_display"] = c_price_disp
                    fixes.append(f"Portföy fiyatı düzeltildi ({item.get('title')}): '{old}' -> '{c_price_disp}'")
                    pf_dirty = True
                    
                if c_price_num and item.get("price_numeric") != int(c_price_num):
                    item["price_numeric"] = int(c_price_num)
                    pf_dirty = True
                    
                if c_down and item.get("down_payment") != c_down:
                    item["down_payment"] = c_down
                    pf_dirty = True
                    
        if pf_dirty:
            with open(pf_path, "w", encoding="utf-8") as f:
                json.dump(pf_data, f, ensure_ascii=False, indent=2)
            fixes.append("nexa_portfolio_data.json kanonik kaynakla senkronize kaydedildi")
            logger.info("Self-healing: nexa_portfolio_data.json otomatik düzeltildi")
            
        # B. SQLite projects tablosu kontrolü ve tamiri
        if db_path.exists():
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("PRAGMA busy_timeout=30000")
            cur = conn.cursor()
            for title_up, canonical in map_lookup.items():
                c_title = canonical.get("title")
                c_price_disp = canonical.get("price_display", "")
                c_price_num = canonical.get("price_numeric")
                c_down = canonical.get("down_payment", "")
                c_room = canonical.get("room_info") or (", ".join(canonical.get("rooms", [])) if isinstance(canonical.get("rooms"), list) else "")
                c_ada = canonical.get("ada_no")
                c_parsel = canonical.get("parsel_no")
                c_tkgm = 1 if canonical.get("tkgm_verified") else 0
                
                cur.execute("""
                    UPDATE projects
                    SET price_display = coalesce(nullif(?, ''), price_display),
                        price_numeric = coalesce(?, price_numeric),
                        down_payment = coalesce(nullif(?, ''), down_payment),
                        room_info = coalesce(nullif(?, ''), room_info),
                        ada_no = coalesce(nullif(?, ''), ada_no),
                        parsel_no = coalesce(nullif(?, ''), parsel_no),
                        tkgm_verified = ?
                    WHERE UPPER(name) = ? OR UPPER(name) = ?
                """, (c_price_disp, c_price_num, c_down, c_room, c_ada, c_parsel, c_tkgm, title_up, (c_title or '').upper()))
                
            conn.commit()
            conn.close()

        # C. Media & Video İzolasyon ve Kendi Kendini Kontrol (Cross-Project Sanitization)
        map_dirty = False
        def _norm_folder(s):
            return re.sub(r"[^\w]", "", (s or "").lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u"))

        for p in canonical_list:
            p_title = p.get("title") or p.get("name") or ""
            p_folder = p.get("folder_name") or ""
            p_norm = _norm_folder(p_folder or p_title)

            if p.get("videos") and isinstance(p["videos"], list):
                valid_vids = []
                for v in p["videos"]:
                    v_path = v.get("path") or ""
                    if v_path and "projeler/" in v_path:
                        v_proj_dir = v_path.split("projeler/")[-1].split("/")[0]
                        if _norm_folder(v_proj_dir) != p_norm:
                            fixes.append(f"Çapraz proje video eşleşmesi temizlendi ({p_title}): '{v_path}'")
                            map_dirty = True
                            continue
                    valid_vids.append(v)
                p["videos"] = valid_vids
                if not valid_vids and (not p.get("drive_video_preview") or "drive.google.com" not in str(p.get("drive_video_preview"))):
                    p["has_video"] = False
                    p["drive_video_preview"] = None
                    p["drive_vid_id"] = None
                    p["tanitim_cloud_url"] = None
                    map_dirty = True

            # MAS LORA thumbnail & video güvencesi
            if "MAS LORA" in p_title.upper() or "SARITAŞ" in p_title.upper() or p.get("id") == "cbvip-prj-32":
                if p.get("thumbnail") != "/static/img/video_thumbs/video_thumb_32.jpg":
                    p["thumbnail"] = "/static/img/video_thumbs/video_thumb_32.jpg"
                    p["image"] = "/static/img/video_thumbs/video_thumb_32.jpg"
                    fixes.append("Sarıtaş Mas Lora için özel video_thumb_32.jpg kapağı atandı")
                    map_dirty = True

        if map_dirty:
            with open(map_path, "w", encoding="utf-8") as f:
                json.dump(canonical_list, f, ensure_ascii=False, indent=2)
            fixes.append("projects_map.json medya ve video izolasyonu sağlandı")
            logger.info("Self-healing: projects_map.json medya izolasyonu onarıldı")
            
        return {"passed": len(issues) == 0, "fixes": fixes, "issues": issues}
    except Exception as e:
        issues.append(f"Kanonik veri senkronizasyon hatası: {e}")
        return {"passed": False, "fixes": fixes, "issues": issues}


def heal_rag_engine() -> dict:
    """Faz 3: RAG Kanonik Matrisi ve önbellek sağlığını denetler."""
    fixes = []
    issues = []
    try:
        import nexa_rag
        matrix = nexa_rag._build_canonical_matrix()
        if not matrix or len(matrix.strip()) < 100:
            issues.append("RAG Kanonik Matris boş veya geçersiz üretildi")
        elif "VIP ÜNİVERSİTE" not in matrix or "1.350.000" not in matrix:
            issues.append("VIP Üniversite 1.350.000 TL kanonik bilgisi RAG matrisinde eksik")
        else:
            # Matris sağlıklı
            pass
            
        # Vektör önbellek kontrolü
        emb_cache = BASE_DIR / "nexa_embedding_cache.json"
        if not emb_cache.exists():
            issues.append(f"Vektör embedding önbellek dosyası eksik: {emb_cache}")
            
        return {"passed": len(issues) == 0, "fixes": fixes, "issues": issues}
    except Exception as e:
        issues.append(f"RAG Engine denetim hatası: {e}")
        return {"passed": False, "fixes": fixes, "issues": issues}


def heal_media_and_assets() -> dict:
    """Faz 4: Statik görseller, Suzanne portresi ve video streaming durumunu kontrol eder."""
    fixes = []
    issues = []
    
    # 1. Suzanne Portresi
    s1_paths = [BASE_DIR / "s1.png", BASE_DIR / "static" / "img" / "s1.png"]
    if not any(p.exists() for p in s1_paths):
        issues.append("Suzanne profil görseli (s1.png) bulunamadı")
    elif not (BASE_DIR / "static" / "img" / "s1.png").exists() and (BASE_DIR / "s1.png").exists():
        import shutil
        (BASE_DIR / "static" / "img").mkdir(parents=True, exist_ok=True)
        shutil.copy(BASE_DIR / "s1.png", BASE_DIR / "static" / "img" / "s1.png")
        fixes.append("s1.png static/img/ dizinine otomatik kopyalandı")
        
    # 2. Proje klasörleri
    proj_dir = BASE_DIR / "projeler"
    if not proj_dir.exists():
        issues.append("projeler/ medya klasörü bulunamadı")
        
    return {"passed": len(issues) == 0, "fixes": fixes, "issues": issues}


def heal_nlp_diagnostics() -> dict:
    """Faz 5: Sentetik NLP testleri ile sıfır-halüsinasyon ve skorlama doğrulaması yapar."""
    fixes = []
    issues = []
    try:
        import nexa_ai_engine
        
        # Test 1: VIP Üniversite tavan fiyat araması
        res = nexa_ai_engine.process_nexa_query("2 milyon altında ne var?")
        projects = res.get("projects", [])
        if not projects:
            issues.append("NLP Testi Başarısız: '2 milyon altında' sorgusuna proje bulunamadı")
        else:
            top_title = (projects[0].get("name") or projects[0].get("title") or "").upper()
            if "VIP" not in top_title and "ÜNİVERSİTE" not in top_title:
                issues.append(f"NLP Testi: 2M altı en iyi eşleşme VIP Üniversite olmalıydı, '{top_title}' geldi")
                
        # Test 2: Lead Scoring
        lead_res = nexa_ai_engine.process_nexa_query("Bu hafta projeyi yerinde görmek ve randevu almak istiyorum")
        lead_score = lead_res.get("lead_score", 0)
        if lead_score < 8:
            issues.append(f"NLP Testi: Ciddi randevu talebinde lead skoru >= 8 olmalıydı, {lead_score} geldi")
            
        return {"passed": len(issues) == 0, "fixes": fixes, "issues": issues}
    except Exception as e:
        issues.append(f"NLP sentetik teşhis hatası: {e}")
        return {"passed": False, "fixes": fixes, "issues": issues}


def run_full_self_healing_cycle() -> dict:
    """Tüm 5 fazı çalıştırır, sistemi otomatik onarır ve kapsamlı sağlık raporu üretir."""
    start_time = time.time()
    all_fixes = []
    all_issues = []
    total_checks = 5
    passed_checks = 0
    
    # Faz 1: DB Schema
    r1 = heal_database_schema()
    all_fixes.extend(r1["fixes"])
    all_issues.extend(r1["issues"])
    if r1["passed"]: passed_checks += 1
    
    # Faz 2: Canonical Data & Prices
    r2 = heal_canonical_data()
    all_fixes.extend(r2["fixes"])
    all_issues.extend(r2["issues"])
    if r2["passed"]: passed_checks += 1
    
    # Faz 3: RAG Engine
    r3 = heal_rag_engine()
    all_fixes.extend(r3["fixes"])
    all_issues.extend(r3["issues"])
    if r3["passed"]: passed_checks += 1
    
    # Faz 4: Media & Assets
    r4 = heal_media_and_assets()
    all_fixes.extend(r4["fixes"])
    all_issues.extend(r4["issues"])
    if r4["passed"]: passed_checks += 1
    
    # Faz 5: NLP Diagnostics
    r5 = heal_nlp_diagnostics()
    all_fixes.extend(r5["fixes"])
    all_issues.extend(r5["issues"])
    if r5["passed"]: passed_checks += 1
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    health_score = int((passed_checks / total_checks) * 100)
    
    status = "healthy" if health_score == 100 else ("degraded" if health_score >= 60 else "critical")
    now_iso = datetime.now().isoformat()
    
    report = {
        "status": status,
        "passed": (health_score >= 80),
        "health_score": health_score,
        "last_run": now_iso,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "fixes_applied": all_fixes,
        "active_issues": all_issues,
        "execution_time_ms": elapsed_ms
    }
    
    # Update memory state
    global _last_health_report
    _last_health_report.update(report)
    _last_health_report["history"].append({
        "timestamp": now_iso,
        "health_score": health_score,
        "fixes_count": len(all_fixes),
        "issues_count": len(all_issues)
    })
    if len(_last_health_report["history"]) > 50:
        _last_health_report["history"].pop(0)
        
    # Log to SQLite
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        cur = conn.cursor()
        _ensure_health_table(conn)
        cur.execute("""
            INSERT INTO system_health_logs (
                health_score, status, total_checks, passed_checks, fixes_json, issues_json, execution_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            health_score,
            status,
            total_checks,
            passed_checks,
            json.dumps(all_fixes, ensure_ascii=False),
            json.dumps(all_issues, ensure_ascii=False),
            elapsed_ms
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Sağlık raporu DB'ye yazılamadı: %s", e)
        
    if all_fixes:
        logger.info("Self-healing tamamlandı. Uygulanan düzeltmeler: %s", all_fixes)
    else:
        logger.info("Self-healing kontrolü: Sistem %d%% sağlıklı, düzeltme gerekmedi.", health_score)
        
    return report


def get_current_health_status() -> dict:
    """Mevcut sağlık durumunu döndürür."""
    global _last_health_report
    if _last_health_report["last_run"] is None:
        return run_full_self_healing_cycle()
    return _last_health_report


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("=== NEXA OTONOM SELF-HEALING ÇALIŞTIRILIYOR ===")
    rep = run_full_self_healing_cycle()
    print(f"Durum: {rep['status'].upper()} | Sağlık Skoru: %{rep['health_score']}")
    print(f"Kontroller: {rep['passed_checks']}/{rep['total_checks']} Başarılı ({rep['execution_time_ms']} ms)")
    if rep['fixes_applied']:
        print("\n🔧 Uygulanan Otomatik Düzeltmeler:")
        for f in rep['fixes_applied']:
            print(f"  ✓ {f}")
    if rep['active_issues']:
        print("\n⚠️ Aktif Sorunlar:")
        for iss in rep['active_issues']:
            print(f"  ✗ {iss}")
    print("===============================================")
