# ================================================================
# APP.PY'YE EKLENECEk BÖLÜM
# ================================================================
# Bu dosyadaki fonksiyonlar app.py'nin içinde yer almalıdır.
# Konumu: app.py'nin 150-180 satırları (import'lardan sonra)
#
# ⚠️ UYARI: Flask app = Flask(__name__) satırından ÖNCE ekle!
#
# Bootstrap edilen fonksiyonlar:
# - init_firebase_admin()    → Firebase Admin SDK başlatma
# - start_scheduler()        → APScheduler başlatma (background tasks)
# - _refresh_listings_bg()   → İlanları arka planda yenile
# ================================================================

import os
import logging
from datetime import datetime, timezone

# ── SCHEDULER IMPORT ─────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    _apscheduler_available = True
except ImportError:
    _apscheduler_available = False
    print("⚠️  APScheduler yüklü değil: pip install apscheduler")

# ── GLOBAL STATE ─────────────────────────────────────────────
_scheduler = None
_listing_cache_time = None

# ================================================================
# BOOTSTRAP FONKSIYONLARI
# ================================================================

def init_firebase_admin():
    """
    Firebase Admin SDK'yı başlat.
    
    Gerekli ortam değişkenleri:
      FIREBASE_SERVICE_ACCOUNT  → service-account.json dosyasının yolu
    """
    global _fb_initialized, db_admin
    
    # Zaten başlatılmışsa, tekrar başlatma
    if _fb_initialized:
        return
    
    try:
        # Service account dosyasının yolunu al
        service_account_path = os.environ.get(
            "FIREBASE_SERVICE_ACCOUNT", 
            "service-account.json"
        )
        
        # Dosya kontrol et
        if not os.path.exists(service_account_path):
            print(f"⚠️  Firebase credential dosyası bulunamadı: {service_account_path}")
            print("   Beklenen konum: service-account.json (ya da FIREBASE_SERVICE_ACCOUNT env var)")
            _fb_initialized = False
            return
        
        # Firebase Admin SDK başlat
        from firebase_admin import credentials, firestore as admin_firestore
        
        cred = credentials.Certificate(service_account_path)
        import firebase_admin
        
        # Eğer zaten initialize edilmişse, hatayı yakala
        try:
            firebase_admin.initialize_app(cred)
        except ValueError:
            # Zaten initialize edilmiş
            pass
        
        db_admin = admin_firestore.client()
        _fb_initialized = True
        
        print("✅ Firebase Admin SDK başlatıldı")
        print(f"   📁 Credential: {service_account_path}")
        
    except Exception as e:
        print(f"❌ Firebase başlatma hatası: {e}")
        print("   Çözüm: Firebase credential dosyasını kontrol et")
        _fb_initialized = False


def start_scheduler():
    """
    APScheduler'ı başlat (follow-up notifications, otomatik refresh vb. için).
    
    Background tasks:
      - Listing refresh (5 dakika aralığı)
      - Lead follow-up notifications (hourly)
      - Daily reports (8:00 AM)
    """
    global _scheduler
    
    # Zaten başlatılmışsa
    if _scheduler is not None:
        return
    
    if not _apscheduler_available:
        print("⚠️  APScheduler yüklü değil, background tasks deaktif")
        return
    
    try:
        _scheduler = BackgroundScheduler(daemon=True)
        
        # İsteğe bağlı: Scheduler job'larını ekle
        # Not: Bu fonksiyonlar tanımlanmalıdır
        
        # Örnek 1: Listeleri 5 dakikada bir yenile
        # _scheduler.add_job(
        #     func=_refresh_listings_bg,
        #     trigger=IntervalTrigger(minutes=5),
        #     id="refresh_listings",
        #     name="Refresh listings from scrapers",
        #     replace_existing=True
        # )
        
        # Örnek 2: Lead follow-up notifications (her saat)
        # _scheduler.add_job(
        #     func=_check_followup_alerts,
        #     trigger=IntervalTrigger(hours=1),
        #     id="followup_alerts",
        #     name="Check lead follow-up alerts",
        #     replace_existing=True
        # )
        
        _scheduler.start()
        print("✅ Background Scheduler başlatıldı")
        
    except Exception as e:
        print(f"❌ Scheduler başlatma hatası: {e}")
        _scheduler = None


def _refresh_listings_bg():
    """
    Listeleri arka planda yenile.
    
    Bu fonksiyon scheduler tarafından çağrılır.
    Sahibinden, Hepsiemlak, Emlakjet vb. API'lerden veri çeker.
    
    Faz 2'de tam implement edilecek.
    """
    global _listing_cache_time
    
    try:
        # Şu an sadece log tutuluyor
        current_time = datetime.now(timezone.utc).isoformat()
        _listing_cache_time = current_time
        
        print(f"📋 Listing refresh başladı: {current_time}")
        
        # İleride: Sahibinden API, Hepsiemlak scraper vb. çağrıları
        # result = scrape_listing("https://www.sahibinden.com/...")
        
        # Telegram/WhatsApp notification gönder (opsiyonel)
        # if WA_ADVISOR_PHONE:
        #     send_whatsapp(WA_ADVISOR_PHONE, "📋 İlanlar yenilendi")
        
    except Exception as e:
        print(f"⚠️  Listing refresh hatası: {e}")


# ================================================================
# BOOTSTRAP ORCHESTRATOR
# ================================================================

def bootstrap_app():
    """
    Uygulamayı başlat — tüm servisleri initialize et.
    
    Bu fonksiyon app.py'nin sonunda, if __name__ == "__main__" 
    bloğundan ÖNCE çağrılır.
    
    Sıra:
    1. Firebase Admin SDK başlat
    2. Background Scheduler başlat
    3. İlanları ön-yükle (cache)
    """
    global _bootstrap_done
    
    # Zaten çalıştırılmışsa, tekrar çalıştırma
    if _bootstrap_done:
        return
    
    print("\n" + "="*70)
    print("🚀 NEXA CRM - Bootstrap Başlatılıyor")
    print("="*70 + "\n")
    
    # 1. Firebase
    init_firebase_admin()
    
    # 2. Scheduler
    start_scheduler()
    
    # 3. Listing cache
    _refresh_listings_bg()
    
    # 4. Mark complete
    _bootstrap_done = True
    
    print("\n" + "="*70)
    print("✅ Bootstrap Tamamlandı")
    print("="*70 + "\n")


# ================================================================
# UTILITY FONKSIYONLARI (İsteğe bağlı)
# ================================================================

def check_bootstrap_status() -> dict:
    """Bootstrap durumunu kontrol et."""
    return {
        "ok": _bootstrap_done,
        "firebase_initialized": _fb_initialized,
        "scheduler_running": _scheduler is not None and _scheduler.running,
        "last_listing_refresh": _listing_cache_time,
    }


# ================================================================
# KURULUM TESİ
# ================================================================

def test_bootstrap():
    """Bootstrap'ı test et (CLI için)."""
    print("\n🧪 Bootstrap Test Başlıyor...\n")
    
    bootstrap_app()
    
    status = check_bootstrap_status()
    print(f"\nBootstrap Durumu:")
    print(f"  ✅ Bootstrap tamamlandı: {status['ok']}")
    print(f"  ✅ Firebase: {status['firebase_initialized']}")
    print(f"  ✅ Scheduler: {status['scheduler_running']}")
    print(f"  📋 Son refresh: {status['last_listing_refresh']}")
    
    return status['ok']


# ================================================================
# ÖRNEK KULLANIM (app.py içinde)
# ================================================================

"""
# app.py'nin SON BÖLÜMÜ:

if __name__ == "__main__":
    bootstrap_app()  # ← Sunucuyu başlatmadan önce bootstrap et
    
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 CRM: http://0.0.0.0:{port}/crm")
    print(f"⚙️  Admin: http://0.0.0.0:{port}/admin")
    
    app.run(host="0.0.0.0", port=port, debug=False)
"""
