# -*- coding: utf-8 -*-
r"""
NexaScout Strategic Scoring & PropFit Engine
Mülkün yasal tekel durumunu (Ticari Yapı Kayıt Belgesi No: C278DFHU, LÖSANTE Karşısı Konumu)
hedef kurumların regülatif zorunlulukları ve finansal güçleriyle eşleştirerek 0-100 arası PropFit puanı hesaplar.
"""

def calculate_propfit_score(lead):
    """
    Hedef kurumun verilerini analiz ederek PropFit (Mülk Uygunluk) skorunu hesaplar.
    
    Kriterler:
    1. Regülatif Zorunluluk (0-35 Puan): Sağlık Bakanlığı ve MEB ticari imar zorunluluğu.
    2. Finansal Likidite Kapasitesi (0-25 Puan): 75M-80M TL satın alma/yatırım gücü.
    3. Mekânsal Sinerji (0-20 Puan): LÖSANTE'ye yakınlık ve sağlık vadisi aksı.
    4. Prestij & Müstakil Bina İhtiyacı (0-20 Puan): Genel merkez, diplomatik, VIP klinik ihtiyacı.
    """
    score = 0
    breakdown = {}
    
    kurum_adi = (lead.get("kurum_adi") or "").lower()
    is_kolu = (lead.get("is_kolu") or lead.get("ana_kategori") or "").lower()
    puan = float(lead.get("puan") or 0.0)
    
    # Mesafe hesabı
    try:
        dist = float(lead.get("mesafe_km") or 999.0)
    except Exception:
        dist = 999.0

    # 1. REGÜLATİF ZORUNLULUK (0 - 35 PUAN)
    # Sağlık Bakanlığı Ayakta Teşhis ve Tedavi Yönetmeliği uyarınca ticari ruhsat şartı en katı olanlardır.
    reg_score = 15
    if any(k in is_kolu or k in kurum_adi for k in ["sağlık", "poliklinik", "tıp merkezi", "diş", "klinik", "hastane", "estetik", "cerrahi", "fizik tedavi"]):
        reg_score = 35 # Yasal tekel: Bölgedeki tek ticari ruhsatlı villa
    elif any(k in is_kolu or k in kurum_adi for k in ["kolej", "anaokulu", "okul", "eğitim"]):
        reg_score = 30 # MEB özel öğretim kurumları müstakil bahçe + ticari imar zorunluluğu
    elif any(k in is_kolu or k in kurum_adi for k in ["savunma", "diplomatik", "elçilik", "embassy"]):
        reg_score = 25 # Yüksek güvenlik ve diplomatik dokunulmazlık/müstakillik
    elif any(k in is_kolu or k in kurum_adi for k in ["hukuk", "denetim", "ymm"]):
        reg_score = 20
    score += reg_score
    breakdown["regulative_score"] = reg_score

    # 2. FİNANSAL LİKİDİTE KAPASİTESİ (0 - 25 PUAN)
    # Kurumun büyüklüğü, zincir olup olmaması, kurumsal unvanı
    fin_score = 12
    if any(k in kurum_adi for k in ["holding", "hastane", "vakfı", "aselsan", "elçilik", "büyükelçilik", "koleji", "üniversite", "group", "a.ş.", "merkezi"]):
        fin_score = 25
    elif any(k in kurum_adi for k in ["polikliniği", "tıp merkezi", "okulları", "savunma", "teknoloji"]):
        fin_score = 20
    elif any(k in kurum_adi for k in ["prof.", "dr.", "ortaklığı", "klinik"]):
        fin_score = 17
    score += fin_score
    breakdown["financial_score"] = fin_score

    # 3. MEKÂNSAL SİNERJİ & LÖSANTE YAKINLIĞI (0 - 20 PUAN)
    if dist <= 1.0:
        dist_score = 20 # Yürüme mesafesi - Doğrudan LÖSANTE karşısı
    elif dist <= 3.0:
        dist_score = 17 # İncek merkez çekirdek havza
    elif dist <= 5.0:
        dist_score = 14 # Çayyolu / Beytepe / İncek bağlantı aksı
    elif dist <= 10.0:
        dist_score = 10 # Bölgesel çevre
    else:
        dist_score = 5
    score += dist_score
    breakdown["spatial_score"] = dist_score

    # 4. PRESTİJ & REPUTASYON SKORU (0 - 20 PUAN)
    # Google Puanı ve kurumsal ağırlık
    rep_score = 10
    if puan >= 4.5:
        rep_score += 10
    elif puan >= 4.0:
        rep_score += 6
    elif puan > 0:
        rep_score += 3
    else:
        rep_score += 5
    score += min(20, rep_score)
    breakdown["prestige_score"] = min(20, rep_score)

    total_score = min(100, max(0, score))
    
    # TIER BELİRLEME
    if total_score >= 82:
        tier = "Tier 1 - VIP Alpha Hedef (Müstakil Yatırımcı)"
        tier_badge = "danger" # Kırmızı
        approach_action = "Broker Özel Teması (Doğrudan YKB / Kurucu / Başhekim Seviyesi)"
    elif total_score >= 68:
        tier = "Tier 2 - Yüksek Stratejik Öncelik"
        tier_badge = "warning" # Turuncu/Sarı
        approach_action = "Genel Müdür / Yatırım Direktörüne Özel Teaser Gönderimi"
    else:
        tier = "Tier 3 - Kurumsal Kiralama / Portföy Adayı"
        tier_badge = "info" # Mavi
        approach_action = "Kurumsal Bilgilendirme Dosyası (Standart Pitch)"

    return {
        "propfit_score": total_score,
        "tier": tier,
        "tier_badge": tier_badge,
        "approach_action": approach_action,
        "breakdown": breakdown
    }
