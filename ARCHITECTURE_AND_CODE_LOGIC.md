# NEXA.OS v5.0 — PropTech Command Center & Pipeline Mimari ve Kod Mantığı Raporu

Bu doküman, **NEXA.OS v5.0 Unified PropTech Command Center** sisteminin mimarisini, veri madenciliği motorlarını, bot koruma aşma algoritmalarını, yapay zeka analiz mantığını ve arayüz entegrasyonunu **ultra detaylı** olarak açıklamaktadır.

---

## 1. GENEL MİMARİ VE ÇALIŞMA PRENSİBİ

NEXA.OS; Coldwell Banker VIP Ankara operasyonları için sıfırdan geliştirilmiş, harici bağımlılıkları minimize edilmiş, tek bir Python sürecinde çalışan tam teşekküllü bir **PropTech İşletim Sistemi**dir.

Sistemin kalbinde, web arayüzünden gelen talepleri arka plan iş parçacıklarına (`threading.Thread`) devreden ve gerçek zamanlı stdout akışını web soketi gerektirmeksizin bufferlayan bir **Job Queue & Pipeline Engine** yer alır.

```
                    ┌────────────────────────────────────────┐
                    │     KULLANICI ARAYÜZÜ (HTML5 / JS)     │
                    │   http://localhost:5000 / /dashboard   │
                    └───────────────────┬────────────────────┘
                                        │ (POST /api/start)
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           FLASK WEB SERVER & JOB MANAGER                         │
│  - Job ID Üretimi (UUID)                                                         │
│  - _LogRedirector: stdout akışını hem konsola hem iş kuyruğuna aktarır          │
│  - Durum Sorgulama API (GET /api/status/<job_id>?after=N)                        │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴────────────────────┐
                    ▼                                        ▼
    ┌───────────────────────────────┐        ┌───────────────────────────────┐
    │     TEKİL İLAN MODU           │        │     MAĞAZA / LİSTE MODU       │
    │  (detect_single_listing_id)   │        │   (Mağaza & Arama Sayfaları)  │
    └───────────────┬───────────────┘        └───────────────┬───────────────┘
                    │                                        │
                    │ Adım 1 & 2 ATLANIR                     │ ADIM 1: PageSpeed Store Scrape
                    │                                        │ ADIM 2: İlan Linki & ID Ayıklama
                    ▼                                        ▼
    ┌───────────────────────────────┐        ┌───────────────────────────────┐
    │ ADIM 3: SELENIUMBASE UC MODE  │        │ ADIM 3: PAGESPEED DETAY       │
    │  - Undetected-Chromedriver    │        │  - Google Chrome Oturumu      │
    │  - Cloudflare Turnstile Aşımı │        │  - #classified-detail Fallback│
    │  - sb.uc_gui_click_captcha()  │        │  - PSI v5 REST API + OCR      │
    └───────────────┬───────────────┘        └───────────────┬───────────────┘
                    │                                        │
                    └───────────────────┬────────────────────┘
                                        ▼
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ ADIM 4: ÇOK KATMANLI DETAY AYRIŞTIRICI (step4_parse_details)                │
    │  - Doğrudan HTML Ayrıştırma (h1, price, breadcrumb, özellik tabloları)       │
    │  - GA4 / UA Analytics Dimension Haritalama (cd13..cd74, ep.kategori...)      │
    │  - Akıllı Fotoğraf Birleştirme: x5_ tam boy ve thmb_ varyantları tekilleştirme│
    │  - İlan Açıklaması: HTML > #classified-detail > PSI OCR (Tesseract Türkçe)   │
    └───────────────────────────────────┬──────────────────────────────────────────┘
                                        ▼
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ ADIM 5: YAPAY ZEKA DEĞERLEME & YORUM MOTORU (step5_analyze)                  │
    │  - Öncelikli: Yerel Ollama (qwen2.5:7b) @ http://localhost:11434             │
    │  - İkincil Fallback: Google Gemini API (gemini-1.5 / gemini-2.0)             │
    │  - 6 Başlıklı Yapılandırılmış Türk Gayrimenkul Değerleme Raporu              │
    └───────────────────────────────────┬──────────────────────────────────────────┘
                                        ▼
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │ ADIM 6: ULTRA LUXURY v3 İNTERAKTİF KART ÜRETİMİ (step6_build_html_luxury)    │
    │  - Bağımsız, tek dosya HTML/CSS/JS çıktısı: jobs/<job_id>/ilan_detay_karti   │
    │  - Tam ekran fotoğraf galerisi (Lightbox), teknik özellik çipleri            │
    │  - Yapay zeka değerleme modalı, tek tıkla WhatsApp paylaşım bağlantısı       │
    └──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. ADIM ADIM PİPELİNE ÇALIŞMA MANTIĞI

### Başlangıç: Sistem Sağlık Kontrolü (`_startup_check`)
Sunucu çalıştırıldığında (`python app.py` veya `run.bat`):
1. `PAGESPEED_API_KEY`: `.env` veya kod içindeki anahtarın varlığı ve geçerli Google formatında (`AIza...`) olup olmadığı denetlenir.
2. `_tesseract_ready()`: Windows üzerinde `C:\Program Files\Tesseract-OCR	esseract.exe` dosyasının fiziksel olarak var olduğu ve binary versiyon verebildiği kontrol edilir.
3. `Ollama`: `http://localhost:11434/api/tags` endpoint'ine 2 saniyelik timeout ile ping atılarak yerel yapay zeka sunucusunun ayakta olup olmadığı doğrulanır.

---

### ADIM 1 & 2: Mağaza Taraması ve Tekil İlan Algılama

#### 1. Tekil İlan Algılama (`detect_single_listing_id`)
Kullanıcı arayüzdeki URL kutusuna bir bağlantı girdiğinde regex kuralları çalıştırılır:
- Standart format: `/ilan/(?:[a-z0-9\-]+-)?(\d{8,11})` (Örn: `.../yasamkent-mesa-yonca-evler-2-kiralik-3-plus1-daire-1336042356/detay`)
- Kısa/Yönlendirme formatı: `sahibinden.com/[a-z0-9\-]+/(\d{8,11})`
- Arama parametreli format: `query_text=(\d{8,11})`

**Mantık**:
Eğer regex bir ilan numarası yakalarsa (`single_id` doluysa), pipeline **Adım 1 (Mağaza PageSpeed taraması)** ve **Adım 2 (Mağaza içi ilan ayıklama)** adımlarını **otomatik olarak atlar**. Çünkü kullanıcının hedefi zaten bellidir. Böylece dakikalar sürecek gereksiz sayfa gezme süreci 0 saniyeye iner.

#### 2. Mağaza / Liste Modu (Çoklu İlan)
Eğer link bir mağaza veya arama linki ise:
- Selenium ile PageSpeed (`pagespeed.web.dev/?hl=tr`) açılır.
- `_type_url_robust()` ile mağaza linki girilir ve analiz başlatılır.
- Dönen HTML'den iki bağımsız metotla (`Method A`: Mağaza vitrin görselleri `img alt="... #ID"`, `Method B`: data-classified-id öznitelikleri) ilanlar toplanır ve ID'ye göre tekilleştirilir (`dedup`).

---

### ADIM 3: Detay Sayfalarının Çekilmesi & Cloudflare Turnstile Aşımı

Paylaştığınız logdaki en kritik işlem bu adımda gerçekleşmiştir:

```
TEKİL İLAN MODU (PageSpeed Atlanıyor) — SeleniumBase UC ile çekiliyor
Hedef: https://www.sahibinden.com/ilan/...-1336042356/detay
[BOT] Turnstile tıklandı
[OK] CF geçildi (1. kontrol)
[OK] Kaydedildi: 1336042356.html (538 KB)
```

#### SeleniumBase UC (Undetected-Chromedriver) ve CFBypassEngine Mantığı:
Sahibinden, doğrudan yapılan HTTP isteklerine (veya standart Selenium'a) **Cloudflare Turnstile** ve **Akamai Bot Protection** engeli koyar.

Sistemimiz bunu şu özel mimariyle çözer:
1. `CFBypassEngine.fetch_page(url)` çağrılır.
2. `seleniumbase.SB(uc=True, headless=False)` context manager'ı başlatılır:
   - `uc=True` (Undetected Mode): Chrome'un `navigator.webdriver` bayrağını, runtime ID'lerini ve CDP (Chrome DevTools Protocol) izlerini tamamen gizler.
   - Gerçek kullanıcı gibi `reconnect_time=6` ile sayfayı açar (`sb.uc_open_with_reconnect`).
3. **Turnstile Tespiti & Tıklama (`_wait_pass`)**:
   - Sayfa kaynağında `CF_SIGNALS` ("Bir dakika lütfen", "challenges.cloudflare.com", "cf-spinner") aranır.
   - Cloudflare challenge tespit edildiğinde `sb.uc_gui_click_captcha()` tetiklenir. Bu fonksiyon ekran koordinatları üzerinden insan fare tıklaması simüle ederek Turnstile kutucuğunu tıklar.
   - Logdaki `[BOT] Turnstile tıklandı` çıktısı bu fonksiyon tarafından üretilir.
4. Tıklama sonrası 1-3 saniye içinde Cloudflare doğrulamayı onaylar (`[OK] CF geçildi`).
5. Sayfa tam render edilmiş haliyle `sb.get_page_source()` ile alınır ve `detay_html/<listing_id>.html` olarak diske yazılır.

#### Çoklu İlan Modunda PageSpeed ve Fallback Zinciri:
Tekil ilan değil de 50 ilanlık bir mağaza taranıyorsa, her ilan için ayrı ayrı UC açmak tarayıcıyı yorabileceğinden sistem **PageSpeed Insights** moduna geçer:
- Google'ın kendi sunucuları Sahibinden sayfasına gider.
- Eğer PageSpeed HTML'inde açıklama eksik kalırsa:
  1. **#classified-detail Fragment Fallback**: URL sonuna `/#classified-detail` eklenerek tekrar çekilir (JS sekmesi açılır).
  2. **PSI v5 REST API + OCR Fallback**: Google API'den `fullPageScreenshot` (base64 WebP) çekilir, `_psi_api_find_desc_rect` ile açıklama bölgesi kırpılır ve **Tesseract OCR (Türkçe)** ile metne dönüştürülür!

---

### ADIM 4: Çok Katmanlı HTML Ayrıştırma (`step4_parse_details`)

Kaydedilen `1336042356.html` dosyası işlenirken sistem sayfanın doğrudan Sahibinden HTML'i mi yoksa PageSpeed wrapper'ı mı olduğunu anlar:

1. **Başlık**: `soup.find("h1")` üzerinden ilan başlığı net olarak alınır.
2. **Fiyat**: `.classified-price-wrapper` ve `.sticky-header-attribute.price` sınıfları taranır. TL, EUR, USD para birimleri ve sayısal formatlar normalize edilir.
3. **Özellikler (Specs)**: `.classifiedInfoList` veya `.classifiedInfoTable` içerisindeki tüm `key: value` çiftleri (İlan Tarihi, Emlak Tipi, m² Brüt, m² Net, Oda Sayısı, Bulunduğu Kat, Isıtma, vb.) çıkarılır.
4. **Fotoğraflar**:
   - Sahibinden sayfalarındaki tembel yükleme (`data-src`), `meta[property='og:image']` ve HTML içinde geçen tüm `x5_` (1024x768 yüksek çözünürlük) görsel linkleri regex ile taranır.
   - Thumbnail (`thmb_`) linkleri tam boyut (`x5_`) linklerine yükseltilir.
   - Tekilleştirme sonucunda ilan başına **80-95 adet net fotoğraf** eksiksiz toplanır.
5. **Açıklama**: `#classifiedDescription` alanındaki metin alınır; gereksiz HTML etiketlerinden ve script kodlarından arındırılır.

---

### ADIM 5: Yapay Zeka Değerleme ve Analiz (`step5_analyze`)

İlan verileri toplandıktan sonra sistem `OllamaClient` üzerinden yerel LLM'e bağlanır:
- Varsayılan Model: `qwen2.5:7b` (Türkçe dil kabiliyeti ve gayrimenkul muhakemesi yüksek model).
- Sunucu: `http://localhost:11434` (Yerel makinede GPU hızlandırmasıyla çalışır, harici internet/API ücreti gerektirmez).

#### Sistem İstemi ve Yapılandırılmış Çıktı:
Modele iletilen sistem promptu, modeli kıdemli bir **Türkiye Gayrimenkul Değerleme Uzmanı** rolüne sokar:

```
Raporunda şu bölümleri numaralı madde olarak açıkça yaz:
1. 💰 **Fiyat ve m² Değerlendirmesi**: mülkün fiyatının konumu ve özelliklerine göre makul olup olmadığını yorumla
2. 📍 **Konum ve Çevre Analizi**: bölgesel değer artış potansiyeli ve ulaşım imkanları
3. 🏢 **Cephe, Kat ve Fiziksel Nitelikler**: kullanım avantajları ve dezavantajları
4. 🌟 **Sosyal Donatılar ve Güvenlik**: site/bina imkanları
5. 🎯 **Hedef Kitle ve Kullanım Amacı**: aile, öğrenci, yatırımcı, kurumsal
6. 📋 **Genel Değerlendirme & Tavsiye**: nihai yatırım/kiralama kararı özeti
```

Eğer Ollama sunucusu kapalıysa ve kullanıcı bir `gemini_api_key` sağlamışsa sistem otomatik olarak **Google Gemini** API'sine geçer; hiçbir şekilde hata verip durmaz.

---

### ADIM 6: Ultra Luxury v3 İnteraktif Kart Üretimi (`step6_build_html_luxury`)

AI analiz raporu ile ilan künyesi birleştirilerek `jobs/<job_id>/ilan_detay_karti.html` oluşturulur:
- **Tasarım Dili**: Koyu mod (`#0a0a0b`), mat altın (`#c9a45c`) ve derin antrasit tonlarında lüks emlak vitrini.
- **İnteraktif Galeri**: Fare veya klavye yön tuşlarıyla gezilebilen tam ekran Lightbox galerisi.
- **Teknik Özellik Çipleri**: Brüt/Net m², Oda Sayısı, Bina Yaşı, Isıtma Tipi gibi bilgileri ikonlarla vurgulayan modern grid.
- **Yapay Zeka Görüşü Modalı**: "AI Değerleme Raporunu İncele" butonuna tıklandığında açılan şık popup pencere.
- **WhatsApp Paylaşımı**: İlan başlığını, fiyatını ve linkini otomatik mesaj haline getirip tek tıkla müşteriye gönderme butonu.
- **Yazdırma (Print) CSS**: Sayfa Ctrl+P ile yazdırıldığında veya PDF olarak kaydedildiğinde arka plan siyahlıklarını optimize eden profesyonel baskı şablonu.

---

## 3. EK MODÜLLER VE KULLANIMLARI

Dashboard'un üst sekmesinde (`templates/index.html`) bulunan diğer 4 güçlü modül:

### 1. Coldwell Banker Scraper (`CBScraper`)
- `https://www.cb.com.tr/satilik` ve `/kiralik` sayfalarını gezer.
- Ofis portföyündeki tüm mülklerin başlık, fiyat, danışman, oda, m² ve detay URL'lerini çeker.
- Çıktıyı `jobs/<job_id>/cb_listings.json` ve `.csv` formatında kaydeder.

### 2. WhatsApp Chat NLP Parser (`WhatsAppCBParser`)
- Danışman veya ofis WhatsApp grup sohbeti `.txt` dışa aktarım dosyasını okur.
- Gelişmiş Türkçe Regex ve NLP kurallarıyla iki ana tablo üretir:
  - **Arayışlar (Talep)**: "Çayyolu 4+1 kiralık arıyorum, bütçe 70 bin" gibi mesajlardan bütçe, oda, ilçe ve aciliyet derecesini ayrıştırır.
  - **Portföyler (Arz)**: "İncek Vista'da satılık 2+1 fırsat daire..." mesajlarından mülk kayıtları oluşturur.

### 3. AI Matcher Engine (`OllamaMatcher`)
- WhatsApp'tan gelen müşteri arayışları ile CB veya Sahibinden'den çekilen mülkleri eşleştirir.
- Eşleşme skoru hesaplar:
  - Fiyat Skoru (Bütçe aralığı toleransı)
  - Oda Skoru (3+1 arayana 3+1 veya 3.5+1 eşleşmesi)
  - Lokasyon Skoru (İlçe ve mahalle yakınlığı)
- Çıktı: `matches_report.html` ve `matches.json`.

### 4. URL → PDF & Web Sunum Deck (`_generate_listing_pdf` & `/p/<token>`)
- Herhangi bir ilan URL'si girildiğinde ReportLab motoru ile **Coldwell Banker VIP Ankara kurumsal 2 sayfalık lüks PDF broşürü** üretir.
- Aynı zamanda mobil uyumlu, hikaye/deck formatında bir web sunumu üretir (`/p/<token>`). Müşteriye WhatsApp'tan atıldığında doğrudan zengin önizleme ve lüks web göstericisi açılır.

---

## 4. API ENDPOINT REFERANSI

| Metot | Endpoint | Açıklama |
| :--- | :--- | :--- |
| `GET` | `/` veya `/dashboard` | Command Center ana kontrol paneli arayüzünü döndürür. |
| `POST` | `/api/start` | Yeni bir tarama, ayıklama veya eşleştirme işi başlatır (`job_type`: `sahibinden`, `cb`, `whatsapp`, `match`). |
| `GET` | `/api/status/<job_id>` | Çalışan işin durumunu, aktif adımını, toplam ilan sayısını ve log satırlarını döndürür. |
| `POST` | `/api/stop/<job_id>` | Arka planda koşan Selenium/PageSpeed sürecini anında güvenle durdurur. |
| `GET` | `/jobs/<job_id>/<file>` | İş çıktısını (HTML kart, PDF, JSON, CSV) tarayıcıda açar veya indirir. |
| `GET` | `/api/whatsapp/parsed_data/<job_id>` | WhatsApp parser sonucundaki Arayış ve Portföy listesini JSON olarak verir. |
| `POST` | `/api/presentations/from-url` | Verilen ilan URL'sinden anında PDF ve Web Sunum Deck oluşturur. |
| `GET` | `/p/<token>` | Üretilen web sunumunun müşteriye özel lüks gösterici sayfası. |
| `GET` | `/share/pdf/<pdf_id>` | Üretilen sunum PDF'ini tarayıcıda görüntüler veya `?dl=1` ile indirir. |
| `GET/POST`| `/api/settings/agent` | Danışman adı, unvanı, telefon ve portre ayarlarını okur/günceller. |

---

## 5. SORUN GİDERME VE İPUÇLARI

1. **Cloudflare Turnstile Geçilmezse Ne Yapmalı?**
   - SeleniumBase UC modu varsayılan olarak `headless=False` (görünür tarayıcı) çalışır. Tıklamanın gerçekleşmesi için Chrome penceresinin simge durumuna küçültülmemesi önerilir.
   - İlan linkini doğrudan `http://localhost:5000/dashboard` üzerindeki Sahibinden Scraper sekmesine yapıştırıp başlatmanız yeterlidir.

2. **Ollama AI Yorumu Üretilmezse:**
   - Komut satırında `ollama list` yazarak modelin kurulu olduğunu teyit edin (`qwen2.5:7b`).
   - Kurulu değilse: `ollama pull qwen2.5:7b` komutunu çalıştırın.
   - Ollama yerine Gemini kullanmak isterseniz paneldeki "Gemini API Key" kutusuna anahtarınızı yazabilirsiniz.

3. **PDF Üretiminde Türkçe Karakterler:**
   - `static/fonts/` klasörüne `DejaVuSans.ttf` ve `DejaVuSans-Bold.ttf` fontları entegre edilmiştir. Bu sayede `ğ, ş, ı, ö, ç, ü` harfleri kusursuz basılır.
