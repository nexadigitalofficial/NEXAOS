# NEXA.OS v5.0 — Unified PropTech Command Center (Standalone)

Coldwell Banker VIP Ankara için özel olarak geliştirilmiş, bağımsız, hafif ve ultra güçlü gayrimenkul veri madenciliği, yapay zeka analiz ve lüks sunum motoru.

---

## 🚀 Hızlı Başlangıç

### 1. Gereksinimler
- Python 3.10 veya üzeri
- Google Chrome tarayıcısı
- (İsteğe bağlı) [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (Türkçe dil paketi ile)
- (İsteğe bağlı) [Ollama](https://ollama.ai) (`ollama pull qwen2.5:7b`)

### 2. Bağımlılıkları Yükleme
```bash
pip install -r requirements.txt
```

### 3. Sunucuyu Başlatma
```bash
python app.py
```
veya Windows'ta doğrudan `run.bat` dosyasına çift tıklayın.

Arayüze erişim:
👉 **http://localhost:5000** veya **http://localhost:5000/dashboard**

---

## 💎 Temel Modüller & Özellikler

1. **Sahibinden Scraper & Bot Aşımı**:
   - **Tekil İlan Modu**: SeleniumBase Undetected-Chromedriver (UC Mode) ile Cloudflare Turnstile bot korumasını saniyeler içinde aşar.
   - **Mağaza/Arama Modu**: PageSpeed Insights motoru üzerinden botlara yakalanmadan onlarca ilanı listeleyip çeker.
   - **Çok Katmanlı Ayrıştırıcı**: Başlık, fiyat, 80+ yüksek çözünürlüklü fotoğraf (x5_), künye özellikleri ve ilan açıklaması.
   - **Yapay Zeka Yorumu**: Yerel Ollama (`qwen2.5:7b`) veya Google Gemini ile 6 başlıklı profesyonel değerleme raporu.
   - **Ultra Luxury v3 Kart**: Koyu antrasit & altın temalı, interaktif fotoğraf galerili, popup detaylı tek sayfa sunum çıktısı (`ilan_detay_karti.html`).

2. **Coldwell Banker Scraper**:
   - `cb.com.tr` üzerinden Ankara satılık ve kiralık kurumsal portföyleri otomatik tarar ve JSON/CSV olarak kaydeder.

3. **WhatsApp Chat Log NLP Parser**:
   - Müşteri ve danışman WhatsApp sohbet günlüklerinden (`.txt`) Türkçe NLP kalıplarıyla **Arayış (Talep)** ve **Portföy (Arz)** kayıtlarını ayıklar.

4. **AI Matcher Engine**:
   - WhatsApp arayışları ile CB/Sahibinden portföyleri arasında bütçe, oda sayısı, lokasyon ve özellik bazlı akıllı eşleştirme ve rapor üretimi yapar.

5. **URL → PDF & Web Sunum Deck**:
   - Herhangi bir ilan URL'sini girerek 2 sayfalık kurumsal PDF broşürü veya mobil uyumlu lüks web sunum göstericisi (`/p/<token>`) üretir.

---

## 📁 Proje Dosya Yapısı

```
NEXAOS/
├── app.py                     # Ana Flask sunucusu ve 6 adımlı pipeline motoru
├── run.bat                    # Tek tıkla başlatıcı
├── requirements.txt           # Python bağımlılıkları
├── .env / .env.example        # Ortam değişkenleri
├── templates/
│   ├── index.html             # Command Center 5 sekmeli ana dashboard
│   ├── presentation_viewer.html # Web sunum deck göstericisi
│   └── dynamic_sunum.html     # Dinamik sunum slayt şablonu
├── static/
│   ├── fonts/                 # PDF için Türkçe DejaVu fontları
│   ├── images/                # Hero arka plan ve grafikler
│   ├── yigit_narin_portrait.png # Danışman portre görseli
│   ├── data/                  # Danışman ayarları ve sunum tokenları
│   └── generated_pdfs/        # Üretilen sunum PDF'leri
└── jobs/                      # Çalıştırılan işlerin log ve çıktı klasörü
```
