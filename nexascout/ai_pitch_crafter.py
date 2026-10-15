# -*- coding: utf-8 -*-
"""
NexaScout AI Copywriting & Institutional Pitch Crafter Engine
Ankara İncek / LÖSANTE Karşısı Ticari Mülk Özel İletişim Motoru

Her kurum için otomatik analiz yapar ve kullanıcının özel tarzında 4 farklı çıktı üretir:
1. Kurumsal E-Posta (Konu + Gövde - Yatırım Direktörlüğü Odaklı)
2. WhatsApp VIP Yönetici Teaser'ı (C-Level / YKB Odaklı)
3. Değerli Meslektaşlarım / Emlak Grubu Mesajı (İş Birliği & Müşteri Getirme Odaklı)
4. Görsel / Afiş / Story Vitrin Taslak Metni
"""

import os
import re
import urllib.parse

# Mülk ve Danışman Sabitleri
AGENT_NAME = "YİĞİT NARİN"
AGENT_TITLE = "Tek Yetkili Gayrimenkul ve Yatırım Danışmanı"
AGENT_COMPANY = "Coldwell Banker VIP Real Gayrimenkul"
AGENT_PHONE = "0532 451 40 08"
SAHIBINDEN_URL = "https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/"
RUHSAT_KODU = "Yapı Kayıt Belgesi: C278DFHU"

PROPERTY_SPECS = {
    "lokasyon": "Gölbaşı Kızılcaşar, LÖSANTE Hastanesi Tam Karşısı, Cadde Üzeri, Köşe Parsel",
    "arsa_m2": "398 m²",
    "kapali_m2": "420 m²",
    "kat_sayisi": "4 Katlı (Kot 1/Bahçe + Giriş + 1. Kat + Çatı Dubleksi)",
    "ruhsat_durumu": "Konut + TİCARİ Çift Ruhsatlı (Bölgedeki TEK Ticari İş Yeri Açma ve Çalışma Ruhsatlı Yapı)",
    "mimari": "Serbest Mimari Proje (Standart kooperatif villalarından tamamen bağımsız prestijli taş cephe)",
    "asansor": "Bodrumdan çatı dubleksine kadar devam eden dikey asansör şaftı mimari boşluğu hazır",
    "su_deposu": "8-10 ton kapasiteli su deposu ve hidrofor sistemi",
    "isinma": "Baymak doğalgaz kombi + kış bahçesi dahil ısıtma altyapısı + 2 adet şömine",
    "otopark": "Müstakil kapalı garaj + köşe parsel avantajıyla geniş açık otopark imkânı",
    "bahce": "İki farklı noktadan (cadde + sokak) girişli müstakil peyzajlı bahçe ve taş barbekü",
}

SECTOR_PERSONAS = {
    "SAGLIK": {
        "keywords": ["hastane", "sağlık", "klinik", "poliklinik", "tıp", "diş", "dent", "estetik", "göz", "fizik tedavi", "laboratuvar", "diyaliz", "onkoloji", "medikal", "doktor", "cerrahi"],
        "angle": "Sağlık Yatırımı / Yeni Hizmet Noktası & Prestijli Klinik Fırsatı",
        "positioning": "Medikal Genişleme ve VIP Hasta Hizmet Merkezi",
        "unfair_advantage": (
            "LÖSANTE Hastanesi'nin tam karşısında yer alması ve Sağlık Bakanlığı Ayakta Teşhis ve Tedavi "
            "Yönetmeliği'ne uygun TİCARİ RUHSATLI bölgedeki TEK müstakil yapı olması sayesinde ruhsat alma "
            "ve faaliyete geçme süresinde benzersiz bir hız ve yasal tekel avantajı sunmaktadır. "
            "Ayrıca asansör şaftı boşluğunun hazır olması ve 8-10 tonluk su deposu medikal gereksinimleri eksiksiz karşılar."
        ),
        "target_audience": "Yönetim Kurulu Başkanlığı, Başhekimlik ve Yatırım/Geliştirme Direktörlüğü"
    },
    "SAVUNMA": {
        "keywords": ["savunma", "aselsan", "havelsan", "roketsan", "tusaş", "stm", "mühendislik", "arge", "ar-ge", "yazılım", "teknoloji", "siber", "bilişim", "elektronik", "havacılık"],
        "angle": "Güvenlikli Stratejik Ar-Ge & Kurumsal Karargâh Fırsatı",
        "positioning": "Müstakil Savunma Sanayii ve İleri Teknoloji Yönetim Merkezi",
        "unfair_advantage": (
            "ASELSAN Gölbaşı Yerleşkesi ve Ankara Çevre Yolu aksına doğrudan bağlantısı, yüksek mahremiyet "
            "sağlayan çevre duvarları, müstakil kapalı/açık otoparkı ve bağımsız serbest mimarisiyle "
            "gizlilik ve güvenlik gerektiren projeler için rakipsiz bir yönetim üssüdür."
        ),
        "target_audience": "Yönetim Kurulu Başkanlığı ve Genel Müdürlük"
    },
    "EGITIM": {
        "keywords": ["kolej", "okul", "anaokulu", "kreş", "eğitim", "akademi", "kurs", "enstitü", "üniversite", "ted", "maya", "bilkent"],
        "angle": "MEB Standartlarına Uygun Butik Kampüs & Eğitim Merkezi Fırsatı",
        "positioning": "VIP Erken Çocukluk Akademisi veya Butik Eğitim Kampüsü",
        "unfair_advantage": (
            "MEB Özel Öğretim Kurumları standartlarında aranan TİCARİ RUHSAT ve bina kullanım iznine "
            "bölgede sahip olan tek müstakil parseldir. 398 m² güvenli müstakil bahçesi, çift giriş kapısı, "
            "geniş sınıflara bölünebilir 4 katlı serbest mimarisiyle butik eğitim için hazırdır."
        ),
        "target_audience": "Kurucu Temsilciliği ve Genel Müdürlük"
    },
    "HUKUK_DENETIM": {
        "keywords": ["hukuk", "avukat", "baro", "danışmanlık", "denetim", "ymm", "mali müşavir", "arabuluculuk", "tahkim", "finans"],
        "angle": "Prestijli Hukuk ve Danışmanlık Yönetim Karargâhı Fırsatı",
        "positioning": "İncek Aksında Müstakil Villa Ofis & Kurumsal Merkez",
        "unfair_advantage": (
            "Çayyolu ve İncek aksında müvekkillerine otopark sorunu yaşatmayan, prestijli doğal taş kaplama "
            "dış cepheye sahip, şömineli VIP toplantı ve kabul salonları ile kot 1'de bağımsız arşiv/çalışma "
            "alanları barındıran tam bağımsız kurumsal villa ofis niteliğindedir."
        ),
        "target_audience": "Yönetici Ortaklar ve Kurucu Avukatlar"
    },
    "YATIRIM_FONU": {
        "keywords": ["holding", "yatırım", "portföy", "gyf", "fon", "gayrimenkul", "finansal", "family office", "girişim"],
        "angle": "Yüksek Kira Çarpanlı ve Yasal Tekel Avantajlı Ticari Gayrimenkul Yatırımı",
        "positioning": "Güçlü Amortisman ve Yüksek Nakit Akışı Sağlayan Ticari Varlık",
        "unfair_advantage": (
            "Bölgedeki tüm kooperatif parselleri konut statüsündeyken, Çevre ve Şehircilik Bakanlığı onaylı "
            "tek ticari yapı kayıt belgesine sahip olması sayesinde bölge ortalamasının çok altında "
            "amortisman süresi ve kurumsal kiracı garantili yüksek kira çarpanı potansiyeli sunar."
        ),
        "target_audience": "Yatırım Komitesi ve Portföy Yöneticileri"
    },
    "KURUMSAL": {
        "keywords": [],
        "angle": "İncek Aksında Cadde Üzeri Müstakil Genel Merkez & Karargah Fırsatı",
        "positioning": "Prestijli Kurumsal Şirket Genel Merkezi",
        "unfair_advantage": (
            "LÖSANTE Hastanesi karşısında, köşe parsel cadde cepheli, 4 katlı 420 m² kapalı alanı, "
            "serbest mimarisi, hazır asansör şaftı ve geniş otopark kapasitesiyle kurumsal markanızı "
            "bölgenin en prestijli noktasında konumlandırır."
        ),
        "target_audience": "Üst Yönetim ve Yatırım Direktörlüğü"
    }
}


def detect_sector_persona(kurum_adi, is_kolu="", ana_kategori=""):
    """Kurum adı ve faaliyet alanına göre en uygun hedef persona ve argüman setini seçer."""
    text_to_search = f"{kurum_adi} {is_kolu} {ana_kategori}".lower()
    for sec_key, sec_data in SECTOR_PERSONAS.items():
        if sec_key == "KURUMSAL":
            continue
        for kw in sec_data["keywords"]:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_to_search):
                return sec_key, sec_data
    return "KURUMSAL", SECTOR_PERSONAS["KURUMSAL"]


def craft_institution_pitch_suite(kurum_adi, is_kolu="", ana_kategori="", mesafe_km=None, web_sitesi=None, decision_maker_name=None, decision_maker_title=None):
    """
    Her kurum için 4 farklı pazarlama çıktısını oluşturur.
    """
    sec_key, persona = detect_sector_persona(kurum_adi, is_kolu, ana_kategori)
    
    # 1. Mesafe cümlesi
    mesafe_str = ""
    if mesafe_km and mesafe_km != "N/A":
        try:
            m_val = float(mesafe_km)
            mesafe_str = f"Mevcut lokasyonunuza yalnızca {m_val:.1f} km mesafede, "
        except Exception:
            pass

    # Karar verici hitabı
    if decision_maker_name and decision_maker_title:
        hitap_unvan = f"Sayın {decision_maker_name} ({decision_maker_title})"
        hitap_kisa = f"Sayın {decision_maker_name}"
    else:
        hitap_unvan = f"{kurum_adi} {persona['target_audience']} Dikkatine"
        hitap_kisa = "Merhaba, iyi çalışmalar"

    # =========================================================================
    # FORMAT 1: KURUMSAL E-POSTA (Yatırım Direktörlüğü & C-Suite Odaklı)
    # =========================================================================
    email_subject = f"{kurum_adi} İçin Stratejik Lokasyon & Yatırım Fırsatı | Gölbaşı Kızılcaşar (LÖSANTE Karşısı)"
    
    email_body = f"""{hitap_kisa},

Ben {AGENT_NAME}, {AGENT_COMPANY} {AGENT_TITLE}yım.

{kurum_adi}’nin sektöründeki büyüme vizyonunu ve hizmet ağını yakından takip etmekteyiz. Kurumunuzun büyüme ve yeni yatırım planları açısından yüksek katma değer sağlayacağını düşündüğümüz, Ankara'nın en değerli kurumsal aksında yer alan özel bir mülk için size doğrudan ulaşmak istedim.

{mesafe_str}Gölbaşı Kızılcaşar’da, LÖSANTE Hastanesi’nin tam karşısında, cadde üzeri ve köşe parsel konumlu 4 katlı tam müstakil binamız satışa sunulmuştur.

MÜLKÜN ÖNE ÇIKAN STRATEJİK AVANTAJLARI:
• YASAL TEKEL & RUHSAT AVANTAJI: Çevre ve Şehircilik Bakanlığı onaylı bölgedeki TEK konut + TİCARİ çift ruhsatlı ({RUHSAT_KODU}) yapıdır. Bölgedeki tüm yapılar konut statüsündeyken, ticari iş yeri açma ve çalışma ruhsatına sahip tek yapıdır.
• KÜNYE: 398 m² arsa payı, 420 m² brüt kapalı alan, 4 katlı tam müstakil kullanım.
• MİMARİ VE TEKNİK ALTYAPI: Sitedeki tip yapılardan tamamen bağımsız serbest mimari proje; bodrumdan çatı dubleksine kadar devam eden dikey asansör şaftı mimari boşluğu hazır; 8–10 ton su deposu ve hidrofor altyapısı mevcuttur.
• OTOPARK VE ERİŞİM: Müstakil kapalı garaj ve köşe parsel avantajıyla geniş açık otopark alanı; iki farklı cepheden (cadde ve sokak) müstakil giriş imkânı.

{persona['unfair_advantage']}

Mülkümüz doğrudan mülk sahibinden tek yetki sözleşmesiyle temsil edilmekte olup, kurumunuzun ilgili yatırım / gayrimenkul geliştirme birimine yönlendirebilirseniz memnuniyet duyarım.

Detaylı teknik şartname dosyasını paylaşmak ve uygun göreceğiniz bir zaman diliminde yerinde inceleme sunumu gerçekleştirmek isteriz.

Resmi İlan Detayı ve Fotoğraflar:
{SAHIBINDEN_URL}

Saygılarımla,

{AGENT_NAME}
{AGENT_TITLE}
{AGENT_COMPANY}
Telefon: {AGENT_PHONE}
"""

    # =========================================================================
    # FORMAT 2: WHATSAPP VIP YÖNETİCİ TEASER'I (C-Level / Direkt Temas)
    # =========================================================================
    whatsapp_teaser = f"""{hitap_kisa}. Ben Yiğit Narin, Gayrimenkul ve Yatırım Danışmanıyım.

{kurum_adi}’nin büyüme ve yeni yatırım hedefleri doğrultusunda değerlendirebileceğinizi düşündüğüm çok özel bir mülk için şahsınıza ulaşmak istedim.

📍 Gölbaşı Kızılcaşar’da, LÖSANTE Hastanesi’nin tam karşısında;
🏢 398 m² arsa payı | 420 m² kapalı alan | 4 katlı tam müstakil bina
📄 Çevre ve Şehircilik Bakanlığı onaylı, bölgedeki TEK konut + TİCARİ çift ruhsatlı yapı
📐 Serbest mimari, asansör şaftı boşluğu hazır, 8-10 ton su deposu ve geniş otopark kapasitesi

{kurum_adi} için {persona['positioning'].lower()} olarak kullanıma hazır durumdadır.

İlgili yatırım veya gayrimenkul geliştirme biriminize yönlendirebilirseniz memnuniyet duyarım. Müsait olduğunuzda teknik dosyayı paylaşmak ve yerinde göstermek isterim.

🔗 Resmi İlan Linki:
{SAHIBINDEN_URL}

📞 Yiğit Narin — {AGENT_PHONE}
Coldwell Banker VIP Gayrimenkul"""

    # =========================================================================
    # FORMAT 3: DEĞERLİ MESLEKTAŞLARIM / EMLAK GRUBU İŞ BİRLİĞİ MESAJI
    # =========================================================================
    emlak_grubu_mesaji = f"""🚨 DEĞERLİ MESLEKTAŞLARIM
📍 GÖLBAŞI KIZILCAŞAR – LÖSANTE HASTANESİ KARŞISI
KONUT + TİCARİ RUHSATLI | TAM MÜSTAKİL | 4 KATLI | KÖŞE PARSEL | CADDE ÜZERİ

🏢 398 m² arsa
📐 420 m² kapalı alan
📄 Bölgede ticari kullanım ve çalışma ruhsatı avantajına sahip TEK özel mülk
🛗 Asansör şaftı mimari boşluğu hazır
🚗 Müstakil kapalı garaj + geniş açık otopark imkânı

Özellikle klinik / sağlık merkezi / şirket merkezi / ofis / butik okul veya yüksek kira getirili yatırım arayan müşteriniz varsa GETİRİN, BİRLİKTE GÖSTERELİM.

🤝 Meslektaş iş birliğine açığız.
📞 YİĞİT NARİN — {AGENT_PHONE}
Coldwell Banker VIP Gayrimenkul

Müşteriniz varsa, mülk hazır. 🔑
İlan: {SAHIBINDEN_URL}"""

    # =========================================================================
    # FORMAT 4: GÖRSEL / AFİŞ / STORY İÇİN TİPOGRAFİK VİTRİN METNİ
    # =========================================================================
    gorsel_afis_metni = f"""🚨 ANKARA GÖLBAŞI KIZILCAŞAR – LÖSANTE HASTANESİ KARŞISI
⭐ BÖLGEDEKİ TEK KONUT + TİCARİ ÇİFT RUHSATLI MÜSTAKİL BİNA

✔ 398 m² Arsa Payı • 420 m² Kapalı Alan
✔ 4 Katlı Tam Müstakil • Köşe Parsel • Çift Cephe
✔ Hazır Asansör Şaftı • 8-10 Ton Su Deposu + Hidrofor
✔ Kapalı Garaj + Geniş Açık Otopark
✔ Sağlık Merkezi • Klinik • Şirket Karargâhı • VIP Ofis Uygun

💼 Tek Yetkili Danışman: YİĞİT NARİN
📱 0532 451 40 08 | Coldwell Banker VIP Real Gayrimenkul
🔗 sahibinden.com/ilan/1343884633"""

    # =========================================================================
    # WHATSAPP WEB URL
    # =========================================================================
    wa_encoded = urllib.parse.quote(whatsapp_teaser)
    
    return {
        "kurum_adi": kurum_adi,
        "sektor": sec_key,
        "persona_angle": persona["angle"],
        "email_subject": email_subject,
        "email_body": email_body,
        "whatsapp_teaser": whatsapp_teaser,
        "emlak_grubu_mesaji": emlak_grubu_mesaji,
        "gorsel_afis_metni": gorsel_afis_metni,
        "whatsapp_encoded": wa_encoded
    }
