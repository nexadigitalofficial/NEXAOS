# -*- coding: utf-8 -*-
r"""
NexaScout VIP SMTP Email Dispatcher Engine
Coldwell Banker VIP kurumsal e-posta altyapısı (yigit.narin@cb.com.tr) üzerinden
hedeflenen kurumlara kişiselleştirilmiş teklif mektuplarını tek tek veya kontrollü
olarak gönderir, ekine ilgili kurumun .docx dosyasını iliştirir ve gönderim loglarını tutar.
"""

import os
import json
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(CURRENT_DIR)
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.json")
LOG_PATH = os.path.join(PROJECT_DIR, "data", "SENT_EMAILS_LOG.json")

# cb.com.tr MX sunucuları Google Workspace (aspmx.l.google.com) üzerindedir.
DEFAULT_SMTP_CONFIG = {
    "sender_email": "yigit.narin@cb.com.tr",
    "sender_name": "Yiğit Narin | Coldwell Banker VIP",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": True,
    "smtp_password": ""
}

LISTING_URL = "https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/"

def load_smtp_config():
    """config.json veya ortam değişkenlerinden SMTP yapılandırmasını okur."""
    config = dict(DEFAULT_SMTP_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "smtp" in data:
                    config.update(data["smtp"])
        except Exception:
            pass

    # Ortam değişkenleri önceliklidir
    config["sender_email"] = os.environ.get("SMTP_SENDER_EMAIL", config["sender_email"])
    config["smtp_server"] = os.environ.get("SMTP_SERVER", config["smtp_server"])
    config["smtp_port"] = int(os.environ.get("SMTP_PORT", config["smtp_port"]))
    config["smtp_password"] = os.environ.get("SMTP_PASSWORD", config["smtp_password"])
    return config

def save_smtp_config(new_config):
    """SMTP yapılandırmasını config.json dosyasına kaydeder."""
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    
    current_smtp = data.get("smtp", dict(DEFAULT_SMTP_CONFIG))
    current_smtp.update({
        "sender_email": new_config.get("sender_email", current_smtp.get("sender_email")),
        "sender_name": new_config.get("sender_name", current_smtp.get("sender_name")),
        "smtp_server": new_config.get("smtp_server", current_smtp.get("smtp_server")),
        "smtp_port": int(new_config.get("smtp_port", current_smtp.get("smtp_port", 587))),
        "use_tls": bool(new_config.get("use_tls", True)),
    })
    
    # Parola verilmişse güncelle, boş bırakılmışsa eskisi kalsın
    if new_config.get("smtp_password"):
        current_smtp["smtp_password"] = new_config["smtp_password"]
        
    data["smtp"] = current_smtp
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return current_smtp

def test_smtp_connection(config=None):
    """SMTP sunucusu ile bağlantıyı ve kimlik doğrulamasını test eder."""
    cfg = config or load_smtp_config()
    server = cfg.get("smtp_server", "smtp.gmail.com")
    port = int(cfg.get("smtp_port", 587))
    user = cfg.get("sender_email", "yigit.narin@cb.com.tr")
    password = cfg.get("smtp_password", "")
    use_tls = cfg.get("use_tls", True)

    if not password:
        return {
            "success": False,
            "message": "SMTP parolası girilmemiş. Google Workspace (cb.com.tr) Uygulama Şifrenizi yapılandırın."
        }

    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(server, port, timeout=10)
        else:
            smtp = smtplib.SMTP(server, port, timeout=10)
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()

        smtp.login(user, password)
        smtp.quit()
        return {
            "success": True,
            "message": f"SMTP bağlantısı başarılı! ({user} @ {server}:{port})"
        }
    except smtplib.SMTPAuthenticationError as e:
        return {
            "success": False,
            "message": f"Kimlik doğrulama hatası (Kullanıcı adı veya şifre hatalı). Google 2FA 'Uygulama Şifresi' kullandığınızdan emin olun. ({str(e)})"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"SMTP Bağlantı hatası: {str(e)}"
        }

def load_sent_logs():
    """Gönderilen e-posta log geçmişini döndürür."""
    if not os.path.exists(LOG_PATH):
        return {}
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def log_sent_email(lead_name, recipient_email, subject, status="SUCCESS", error=None):
    """Gönderilen e-postayı yerel JSON kütüğüne işler."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logs = load_sent_logs()
    entry = {
        "lead_name": lead_name,
        "recipient_email": recipient_email,
        "subject": subject,
        "status": status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error
    }
    logs[lead_name] = entry
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return entry

def build_email_content(lead_data):
    """Kuruma özel VIP HTML ve metin e-posta şablonunu oluşturur."""
    kurum_adi = lead_data.get("kurum_adi", "Değerli Kurum")
    sektor = lead_data.get("is_kolu", "Kurumsal")
    mesafe = lead_data.get("mesafe_km", "")
    mesafe_metni = f"Mevcut yerleşkenize yaklaşık {mesafe} km mesafede" if mesafe else "İncek aksında"

    subject = f"Stratejik Gayrimenkul Yatırım Sunumu | {kurum_adi} — Ankara İncek LÖSANTE Karşısı Müstakil Ticari Mülk"

    text_body = f"""Sayın {kurum_adi} Yetkilileri ve Karar Vericileri,

{mesafe_metni}, Ankara İncek'in en değerli kurumsal ve sağlık koridorunda (LÖSANTE Hastanesi tam karşısı), kurumunuzun stratejik büyüme vizyonuna değer katacak müstesna bir ticari mülkiyeti portföyümüze almış bulunmaktayız.

MÜLKÜN ÖNE ÇIKAN TEMEL NİTELİKLERİ:
• Hukuki Statü: Çevre, Şehircilik ve İklim Değişikliği Bakanlığı onaylı 'TİCARİ' Yapı Kayıt Belgesi (No: C278DFHU). Bölgedeki konut kooperatifi dokusunda yasal faaliyet iznine sahip TEK müstakil köşe parseldir.
• Lokasyon & Büyüklük: LÖSANTE Hastanesi tam karşısı, 398 m² köşe arsa, ~420 m² brüt kapalı alan (4 katlı müstakil kullanım).
• Altyapı Standartları: Dikey asansör şaftı, çift bağımsız giriş, 10 ton su deposu, 15 araçlık otopark ve müstakil bahçe.

Resmi Sahibinden İlanı: {LISTING_URL}

Kurumunuza özel olarak hazırlanan detaylı VIP Yatırım Teklifi mektubumuz ekte bilgilerinize sunulmuştur. 
Mülkümüzü yerinde incelemek ve detaylı teknik şartname dosyasını değerlendirmek üzere uygunluğunuzu rica ederiz.

Saygılarımızla,

Yiğit Narin
Lüks Konut & Ticari Gayrimenkul Danışmanı
Coldwell Banker VIP Real Gayrimenkul
İletişim: 0532 451 40 08
E-Posta: yigit.narin@cb.com.tr
Adres: Santra Royal Rezidans Ofisleri No: 2C/4 Çayyolu / Ankara
"""

    html_body = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 20px; color: #1E293B; }}
    .container {{ max-width: 650px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #E2E8F0; }}
    .header {{ background: linear-gradient(135deg, #0A2540 0%, #1B365D 100%); color: #FFFFFF; padding: 28px 30px; text-align: center; border-bottom: 4px solid #C5A059; }}
    .header h2 {{ margin: 0 0 6px 0; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; }}
    .header .subtitle {{ margin: 0; font-size: 12px; color: #C5A059; text-transform: uppercase; font-weight: 600; letter-spacing: 1px; }}
    .content {{ padding: 30px; line-height: 1.6; font-size: 14px; }}
    .salutation {{ font-size: 16px; font-weight: 700; color: #0F172A; margin-bottom: 14px; }}
    .card-highlight {{ background-color: #F8FAFC; border-left: 4px solid #0284C7; border-radius: 6px; padding: 16px; margin: 20px 0; }}
    .spec-item {{ margin-bottom: 8px; font-size: 13px; }}
    .spec-item b {{ color: #1E3A8A; }}
    .cta-box {{ text-align: center; margin: 30px 0 20px 0; }}
    .btn-cta {{ display: inline-block; background-color: #C5A059; color: #0A2540; font-weight: 700; padding: 13px 26px; border-radius: 6px; text-decoration: none; font-size: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.12); }}
    .attachment-notice {{ background: #ECFDF5; border: 1px solid #A7F3D0; color: #065F46; padding: 12px 16px; border-radius: 6px; font-size: 13px; margin: 20px 0; }}
    .signature {{ border-top: 1px solid #E2E8F0; padding-top: 20px; margin-top: 30px; font-size: 13px; color: #475569; }}
    .signature-name {{ font-size: 15px; font-weight: 700; color: #0A2540; margin-bottom: 2px; }}
    .footer {{ background: #F1F5F9; padding: 14px; text-align: center; font-size: 11px; color: #94A3B8; border-top: 1px solid #E2E8F0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="subtitle">Coldwell Banker VIP Real Gayrimenkul Yatırım Direktörlüğü</div>
      <h2>STRATEJİK TİCARİ MÜLKİYET SUNUMU</h2>
    </div>
    
    <div class="content">
      <div class="salutation">Sayın {kurum_adi} Yetkilileri ve Karar Vericileri,</div>
      
      <p>
        <strong>{kurum_adi}</strong>'nin {sektor} alanındaki kurumsal vizyonu ve seçkin konumunu yakından takip etmekteyiz.
      </p>
      
      <p>
        {mesafe_metni}, Ankara İncek'in en değerli sağlık ve kurumsal aksında (LÖSANTE Hastanesi tam karşısı), 
        kurumunuzun prestijine ve büyüme hedeflerine değer katacak müstesna bir ticari gayrimenkulü portföyümüze almış bulunmaktayız.
      </p>

      <div class="card-highlight">
        <div style="font-weight: 700; color: #0A2540; margin-bottom: 10px; font-size: 14px;">MÜLKÜN ÖNE ÇIKAN STRATEJİK AYRICALIKLARI:</div>
        <div class="spec-item">⚖️ <b>Yasal Tekel & Ticari Ruhsat:</b> Çevre ve Şehircilik Bakanlığı onaylı 'TİCARİ Yapı Kayıt Belgesi' (No: C278DFHU). Bölgedeki konut kooperatifi dokusunda ticari faaliyet ve kurum açma iznine sahip <u>TEK</u> müstakil köşe parseldir.</div>
        <div class="spec-item">📍 <b>Konum Gücü:</b> LÖSANTE Çocuk & Yetişkin Hastanesi tam karşısı, köşe parsel, iki ana yola cepheli.</div>
        <div class="spec-item">📐 <b>Kullanım Hacmi:</b> 398 m² müstakil köşe arsa ve ~420 m² brüt kapalı alan (4 katlı komple bina).</div>
        <div class="spec-item">🏗️ <b>Teknik Donatılar:</b> Dikey asansör şaftı hazır, 10 ton su deposu ve hidrofor, çift bağımsız giriş, 15 araçlık otopark ve peyzajlı müstakil bahçe.</div>
      </div>

      <div class="cta-box">
        <a href="{LISTING_URL}" target="_blank" class="btn-cta">
          Sahibinden İlanını ve Detaylı Fotoğrafları İncele
        </a>
      </div>

      <div class="attachment-notice">
        📎 <strong>Ekli Dosya:</strong> Kurumunuza özel hazırlanan detaylı <strong>"{kurum_adi}_VIP_Yatirim_Teklifi.docx"</strong> şartname ve yatırım dosyamız e-posta ekinde yer almaktadır.
      </div>

      <p style="margin-top: 20px;">
        Mülkümüzü yerinde incelemek ve şahsınıza özel detaylı sunum gerçekleştirmek üzere uygunluk durumunuzu iletebilir misiniz?
      </p>

      <div class="signature">
        <div class="signature-name">Yiğit Narin</div>
        <div>Lüks Konut & Ticari Gayrimenkul Danışmanı</div>
        <div><strong>Coldwell Banker VIP Real Gayrimenkul</strong></div>
        <div style="margin-top: 8px;">
          📞 <strong>Telefon:</strong> 0532 451 40 08<br>
          ✉️ <strong>E-Posta:</strong> <a href="mailto:yigit.narin@cb.com.tr" style="color: #0284C7;">yigit.narin@cb.com.tr</a><br>
          🏢 <strong>Ofis:</strong> Santra Royal Rezidans Ofisleri No: 2C/4 Çayyolu / Ankara
        </div>
      </div>
    </div>

    <div class="footer">
      Bu bilgilendirme Coldwell Banker VIP münhasır yetkili portföyü kapsamında iletilmiştir. | İlan No: 1343884633
    </div>
  </div>
</body>
</html>
"""
    return {
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body
    }

def find_proposal_file(kurum_adi, proposals_dir):
    """Kurum adı ile eşleşen üretilmiş .docx dosyasını bulur."""
    import re
    def sanitize(name):
        return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")
        
    clean_name = sanitize(kurum_adi)[:40]
    expected_path = os.path.join(proposals_dir, f"{clean_name}_VIP_Yatirim_Teklifi.docx")
    if os.path.exists(expected_path):
        return expected_path
        
    # Kısmi eşleşme tara
    if os.path.exists(proposals_dir):
        for fname in os.listdir(proposals_dir):
            if fname.endswith(".docx") and clean_name[:15].lower() in fname.lower():
                return os.path.join(proposals_dir, fname)
    return None

def is_gmail_api_ready():
    """token.json dosyasının varlığını kontrol eder."""
    token_file = os.path.join(PROJECT_DIR, "token.json")
    return os.path.exists(token_file)

def send_via_gmail_api(msg, target_email):
    """Resmi Gmail API (OAuth2) üzerinden e-postayı iletir."""
    import base64
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_file = os.path.join(PROJECT_DIR, "token.json")
    if not os.path.exists(token_file):
        return False, "token.json bulunamadı. Lütfen önce GOOGLE_GMAIL_BAGLA.bat dosyasını çalıştırınız."

    creds = Credentials.from_authorized_user_file(token_file, ["https://www.googleapis.com/auth/gmail.send"])
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w", encoding="utf-8") as tf:
                tf.write(creds.to_json())
        else:
            return False, "Google yetkilendirme oturumunun süresi dolmuş. Lütfen GOOGLE_GMAIL_BAGLA.bat dosyasını çalıştırınız."

    service = build("gmail", "v1", credentials=creds)
    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    return True, None

def send_proposal_email(lead_data, proposals_dir, recipient_email=None, custom_subject=None, custom_html=None):
    """
    Tek bir kuruma Word ekli VIP teklif e-postasını resmi Gmail API veya SMTP üzerinden gönderir.
    """
    cfg = load_smtp_config()
    server = cfg.get("smtp_server", "smtp.gmail.com")
    port = int(cfg.get("smtp_port", 587))
    sender_email = cfg.get("sender_email", "yigit.narin@cb.com.tr")
    sender_name = cfg.get("sender_name", "Yiğit Narin | Coldwell Banker VIP")
    password = cfg.get("smtp_password", "")
    use_tls = cfg.get("use_tls", True)

    kurum_adi = lead_data.get("kurum_adi", "Değerli Kurum")
    target_email = recipient_email or lead_data.get("eposta")

    if not target_email or target_email == "N/A" or "@" not in target_email:
        err = f"'{kurum_adi}' için geçerli bir e-posta adresi bulunamadı."
        log_sent_email(kurum_adi, target_email or "N/A", "", "FAILED", err)
        return {"success": False, "message": err}

    content = build_email_content(lead_data)
    subject = custom_subject or content["subject"]
    html_body = custom_html or content["html_body"]
    text_body = content["text_body"]

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = target_email
    msg["Subject"] = subject

    # Body part (alternative text/html)
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt_part)

    # Attach proposal docx if found
    doc_path = find_proposal_file(kurum_adi, proposals_dir)
    if doc_path and os.path.exists(doc_path):
        try:
            with open(doc_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(doc_path))
                part["Content-Disposition"] = f'attachment; filename="{os.path.basename(doc_path)}"'
                msg.attach(part)
        except Exception:
            pass

    # 1. Önce resmi Gmail API (OAuth2) dene (En güvenilir yöntem)
    if is_gmail_api_ready():
        try:
            ok, err = send_via_gmail_api(msg, target_email)
            if ok:
                log_sent_email(kurum_adi, target_email, subject, "SUCCESS (Gmail API)")
                return {
                    "success": True,
                    "message": f"E-posta resmi Google Workspace (Gmail API) üzerinden '{target_email}' adresine başarıyla gönderildi! (Ekli dosya: {os.path.basename(doc_path) if doc_path else 'Yok'})",
                    "sent_at": datetime.now().strftime("%d.%m.%Y %H:%M")
                }
            elif not password:
                return {"success": False, "message": err}
        except Exception as e:
            if not password:
                log_sent_email(kurum_adi, target_email, subject, "FAILED (Gmail API)", str(e))
                return {"success": False, "message": f"Gmail API gönderim hatası: {str(e)}"}

    # 2. Gmail API bağlı değilse SMTP yedek kanalına geç
    if not password:
        err = "Google API henüz yetkilendirilmemiş ve SMTP parolası girilmemiş. Lütfen klasördeki GOOGLE_GMAIL_BAGLA.bat dosyasını çalıştırarak Google ile bağlanınız."
        return {"success": False, "message": err}

    # Send via SMTP
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(server, port, timeout=15)
        else:
            smtp = smtplib.SMTP(server, port, timeout=15)
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()

        smtp.login(sender_email, password)
        smtp.sendmail(sender_email, [target_email], msg.as_string())
        smtp.quit()

        log_sent_email(kurum_adi, target_email, subject, "SUCCESS (SMTP)")
        return {
            "success": True,
            "message": f"E-posta '{target_email}' adresine başarıyla gönderildi! (Ekli dosya: {os.path.basename(doc_path) if doc_path else 'Yok'})",
            "sent_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
    except Exception as e:
        err = f"E-posta gönderiminde hata: {str(e)}"
        log_sent_email(kurum_adi, target_email, subject, "FAILED", str(e))
        return {"success": False, "message": err}

def send_bulk_proposal_emails(leads, proposals_dir, delay_sec=2.5, skip_already_sent=True, status_callback=None):
    """
    Tüm kurumlara kontrollü, spam korumalı (gecikmeli) toplu e-posta gönderimi yapar.
    """
    import time
    results = {
        "total": len(leads),
        "sent_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "details": []
    }
    
    sent_logs = load_sent_logs()
    
    for idx, lead in enumerate(leads):
        name = lead.get("kurum_adi", f"Kurum #{idx+1}")
        email = lead.get("eposta")
        
        # 1. E-posta adresi geçerli mi?
        if not email or email == "N/A" or "@" not in email:
            results["skipped_count"] += 1
            results["details"].append({
                "kurum_adi": name,
                "email": "N/A",
                "status": "SKIPPED",
                "reason": "E-posta adresi yok"
            })
            if status_callback:
                status_callback(idx + 1, len(leads), name, "SKIPPED", "E-posta adresi yok")
            continue
            
        # 2. Önceden başarıyla gönderilmiş mi?
        if skip_already_sent and name in sent_logs and "SUCCESS" in sent_logs[name].get("status", ""):
            results["skipped_count"] += 1
            results["details"].append({
                "kurum_adi": name,
                "email": email,
                "status": "ALREADY_SENT",
                "reason": "Daha önce gönderildi"
            })
            if status_callback:
                status_callback(idx + 1, len(leads), name, "ALREADY_SENT", "Daha önce gönderildi")
            continue
            
        # 3. Gönder
        res = send_proposal_email(lead, proposals_dir)
        if res.get("success"):
            results["sent_count"] += 1
            results["details"].append({
                "kurum_adi": name,
                "email": email,
                "status": "SUCCESS",
                "message": res.get("message")
            })
            if status_callback:
                status_callback(idx + 1, len(leads), name, "SUCCESS", res.get("message"))
        else:
            results["failed_count"] += 1
            results["details"].append({
                "kurum_adi": name,
                "email": email,
                "status": "FAILED",
                "message": res.get("message")
            })
            if status_callback:
                status_callback(idx + 1, len(leads), name, "FAILED", res.get("message"))
                
        # Spam koruma gecikmesi
        if idx < len(leads) - 1:
            time.sleep(delay_sec)
            
    return results
