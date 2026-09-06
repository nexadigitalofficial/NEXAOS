# NEXA.OS — Google Play Store Yükleme ve Yayınlama Kılavuzu

Bu kılavuz, üretilen **NEXAOS.aab** ve **NEXAOS.apk** paketlerini Google Play Store'a yüklemek için izlemeniz gereken resmi adımları içermektedir.

---

## 📦 1. Hazır Dosyalarınız

Tüm dosyalar Masaüstünüzde ve **NEXAOS/dist/** klasöründe hazırdır:

1. **NEXAOS.aab** (7.6 MB): Google Play Store'a yüklenecek olan resmi **Android App Bundle** paketi.
2. **NEXAOS.apk** (8.0 MB): Kendi Android telefonunuza doğrudan kabloyla/WhatsApp'la atıp hemen kurabileceğiniz test sürümü.
3. **nexaos-release-key.jks**: Paketin imzalandığı güvenlik sertifikası (Şifresi: nexaos1234, Alias: nexaos).
4. **icon_512.png** (512x512): Google Play Store uygulama simgesi.
5. **feature_graphic_1024x500.png** (1024x500): Google Play Store vitrin afişi.
6. **privacy.html**: Google'ın zorunlu kıldığı Gizlilik Politikası sayfası (Sunucunuzda http://alanadiniz.com/privacy olarak yayında).

---

## 🚀 2. Google Play Console Yükleme Adımları

### Adım 1: Google Play Console Girişi
1. https://play.google.com/console adresine gidin.
2. Google hesabınızla giriş yapın (Geliştirici hesabı yoksa 25$ tek seferlik kayıt ücreti ödenir).

### Adım 2: Yeni Uygulama Oluşturma
- **Uygulama Adı**: NEXA.OS — PropTech Command Center
- **Varsayılan Dil**: Türkçe (tr-TR)
- **Tür**: Uygulama (App)
- **Ücret**: Ücretsiz (Free)
- Şartları onaylayıp **Uygulama Oluştur** butonuna basın.

### Adım 3: Mağaza Girişini Doldurma (Store Listing)
Sol menüden **Büyüme → Ana Mağaza Girişi** sekmesine tıklayın:
- **Kısa Açıklama** (Maks 80 karakter):
  Lüks gayrimenkul veri madenciliği, yapay zeka değerleme ve portföy yönetim merkezi.
- **Tam Açıklama**:
  NEXA.OS, Coldwell Banker CB VIP Ankara ve profesyonel gayrimenkul danışmanları için geliştirilmiş yeni nesil PropTech komuta merkezidir. Sahibinden ve CB portföylerini tarar, WhatsApp sohbet günlüklerinden arayış/portföy eşleştirmesi yapar, yapay zeka ile 6 başlıklı değerleme raporu üretir ve tek tıkla kurumsal lüks PDF broşürleri hazırlar.
- **Uygulama Simgesi**: NEXAOS/dist/icon_512.png dosyasını yükleyin.
- **Özellik Grafiği**: NEXAOS/dist/feature_graphic_1024x500.png dosyasını yükleyin.
- **Telefon Ekran Görüntüleri**: Bilgisayarda veya telefonda açık olan NEXA.OS dashboard ekranından en az 2 adet ekran görüntüsü alıp sürükleyin.

### Adım 4: Uygulama İçeriği ve Gizlilik Politikası
Sol menüden **Politika ve Programlar → Uygulama İçeriği** sekmesine gidin:
1. **Gizlilik Politikası**: Sunucu linkinizi girin (Örn: https://app.nexaos.com/privacy veya http://192.168.1.36:5000/privacy).
2. **Reklamlar**: 'Hayır, uygulamamda reklam yok' seçin.
3. **Uygulama Erişimi**: 'Tüm işlevler kısıtlama olmaksızın kullanılabilir' seçin.
4. **Hedef Kitle**: 18 yaş ve üzeri seçin.
5. **Veri Güvenliği**: Uygulamanın üçüncü taraflarla kullanıcı verisi paylaşmadığını beyan edin.

### Adım 5: .aab Paketini Yükleme
1. Sol menüden **Sürümler → Üretim (Production)** veya **Kapalı Test (Closed Testing)** sekmesine gidin.
2. **Yeni Sürüm Oluştur** butonuna tıklayın.
3. Masaüstünüzdeki **NEXAOS.aab** dosyasını yükleme alanına sürükleyip bırakın.
4. Sürüm adı otomatik olarak 1.0.0 (1) olacaktır.
5. Sürüm notlarına: 'İlk resmi sürüm: NEXA.OS PropTech Command Center yayında.' yazın.
6. **Kaydet** ve **Sürümü İncelemeye Gönder** butonuna basın!
