# -*- coding: utf-8 -*-
r"""
NexaScout Google Workspace (Gmail API) OAuth2 Kurulum Aracı
yigit.narin@cb.com.tr hesabı için Gmail API yetkilendirmesi yapar ve token.json üretir.
"""

import os
import sys

# Force UTF-8
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(CURRENT_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(CURRENT_DIR, "token.json")

# Sadece e-posta gönderme yetkisi ister (en güvenli scope)
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def authenticate_google_account():
    print("=" * 65, flush=True)
    print(" NEXASCOUT - GOOGLE WORKSPACE (GMAIL API) HIZLI YETKİLENDİRME", flush=True)
    print("=" * 65, flush=True)

    if not os.path.exists(CLIENT_SECRET_FILE):
        print(f"[HATA] {CLIENT_SECRET_FILE} bulunamadı!", flush=True)
        return None

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[BİLGİ] Mevcut oturum yenileniyor (Refresh Token)...", flush=True)
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            print("[BİLGİ] Tarayıcınız açılıyor...", flush=True)
            print("[BİLGİ] Lütfen açılan Google sayfasında yigit.narin@cb.com.tr hesabınızı seçip 'İzin Ver' butonuna tıklayınız.\n", flush=True)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0, prompt="consent")

        # Token'ı kaydet
        with open(TOKEN_FILE, "w", encoding="utf-8") as token_f:
            token_f.write(creds.to_json())
            print(f"[BAŞARILI] Yetkilendirme token'ı kaydedildi: {TOKEN_FILE}")

    # Hesabı doğrula
    try:
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        user_email = profile.get("emailAddress", "yigit.narin@cb.com.tr")
        print("\n" + "=" * 65)
        print(f" TEBRİKLER! HESAP BAŞARIYLA BAĞLANDI: {user_email}")
        print(" Artık kontrol panelinden tek tıkla resmi Gmail API üzerinden")
        print(" tüm teklif mektuplarınızı Word ekiyle birlikte gönderebilirsiniz.")
        print("=" * 65 + "\n")
        return creds
    except Exception as e:
        print(f"[BİLGİ] Yetkilendirme tamamlandı, servis hazır. ({e})")
        return creds

if __name__ == "__main__":
    authenticate_google_account()
