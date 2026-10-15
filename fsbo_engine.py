"""
================================================================
fsbo_engine.py — Nexa CRM FSBO Strateji Analiz Motoru
================================================================

Kullanım:
  from fsbo_engine import analyze_fsbo, fsbo_engine_status

Desteklenen girdiler:
  - contact_data  : Kişi profili (dict)
  - screenshots   : base64 görüntü listesi (sahibinden/WA ekran görüntüsü)
  - text_input    : Manuel metin (konuşma notu, ilan metni vb.)
  - audio_b64     : Ses kaydı base64 string
  - audio_mime    : "audio/webm" | "audio/mp4" | "audio/mpeg" | "audio/wav"
  - timeline      : Geçmiş aktivite listesi (aşama geçişleri, yorumlar)

Çıktı:
  {
    "ok": true,
    "strategy": {
      "owner_profile": {...},
      "property_assessment": {...},
      "fsbo_approach": {...},
      "key_questions": [...],
      "objection_handling": [...],
      "followup_schedule": {...},
      "talking_points": [...],
      "recommended_actions": [...],
      "swot": {...},
      "urgency_triggers": [...],
      "verdict": "...",
      "confidence_score": 0-10,
      "resistance_level": "düşük|orta|yüksek",
      "next_contact_timing": "...",
      "generated_at": "ISO"
    },
    "audio_transcript": "..." (eğer ses kaydı analiz edildiyse)
  }
================================================================
"""

import os
import json
import base64
import re
import time
from datetime import datetime, timezone

# Güncel model listesi: https://ai.google.dev/gemini-api/docs/models
# gemini-2.5-flash      → kararlı, fiyat/performans dengesi (ana model)
# gemini-2.5-flash-lite → en hızlı/ekonomik 2.5 ailesi (yedek)
# gemini-2.0-flash      → DEPRECATED — kullanılmaz!
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL       = "gemini-2.5-flash"
GEMINI_FALLBACK    = "gemini-2.5-flash-lite"  # 2.0-flash deprecated; lite en iyi yedek
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY = 8   # saniye; 503 yük hatalarında başlangıç bekleme


def _is_configured() -> bool:
    return bool(GEMINI_API_KEY)


def fsbo_engine_status() -> dict:
    configured = _is_configured()
    return {
        "ok":         configured,
        "configured": configured,
        "model":      GEMINI_MODEL,
        "error":      None if configured else "GEMINI_API_KEY tanımlanmamış",
    }


def _build_prompt(contact_data: dict, text_input: str, timeline: list) -> str:
    """Ana Gemini analiz promptunu oluşturur."""
    name     = contact_data.get("name", "Bilinmiyor")
    phone    = contact_data.get("phone", "")
    district = contact_data.get("district", "")
    price    = contact_data.get("price", "")
    stage    = contact_data.get("stage", "")
    notes    = contact_data.get("notes", "")
    category = contact_data.get("category", "fsbo")

    # Timeline özetini al (son 10 aktivite)
    timeline_text = ""
    if timeline:
        for ev in timeline[-10:]:
            t = ev.get("type", "")
            txt = ev.get("text", "")
            dt  = ev.get("createdAt", "")[:10] if ev.get("createdAt") else ""
            timeline_text += f"  [{dt}] {t.upper()}: {txt}\n"

    return f"""Sen Türkiye'nin en deneyimli gayrimenkul danışmanlarından birisin. 
Uzmanlık alanın: FSBO (For Sale By Owner / Sahibinden Satış) mülk sahiplerini portföye kazanmak.

## LEAD BİLGİLERİ
İsim: {name}
Telefon: {phone}
İlçe/Bölge: {district or 'Belirtilmemiş'}
Tahmini Değer: {price or 'Belirtilmemiş'} TL
Kategori: {category.upper()}
Mevcut Aşama: {stage}
Notlar: {notes or 'Yok'}

## AKTİVİTE GEÇMİŞİ
{timeline_text or 'Henüz aktivite yok'}

## EK BİLGİLER (Manuel Girdi)
{text_input or 'Ek bilgi girilmemiş'}

## GÖREV

Aşağıdaki JSON yapısını Türkçe olarak üret. SADECE JSON döndür, başka metin yok:

{{
  "owner_profile": {{
    "likely_situation": "Ev sahibinin tahmini durumu (zaman baskısı var mı, fiyat konusunda ne düşünüyor vb.)",
    "motivation_level": "yüksek|orta|düşük",
    "knowledge_level": "piyasayı biliyor|kısmen biliyor|bilmiyor",
    "decision_maker": "yalnız|aile ile birlikte karar veriyor|belirsiz",
    "timeline": "acil|1-3 ay|3-6 ay|belirsiz",
    "pain_points": ["Mevcut sorun 1", "Mevcut sorun 2", "Mevcut sorun 3"]
  }},
  "property_assessment": {{
    "estimated_price_range": "Ekran görüntülerine ve bölgeye göre tahmini fiyat aralığı",
    "listing_quality": "İlan kalitesi değerlendirmesi (fotoğraflar, açıklama vb.)",
    "time_on_market": "Piyasada ne kadar süredir olduğuna dair çıkarım",
    "price_positioning": "düşük|uygun|yüksek|çok yüksek",
    "key_observations": ["Önemli gözlem 1", "Önemli gözlem 2"]
  }},
  "fsbo_approach": {{
    "strategy_type": "değer_odaklı|sorun_çözücü|piyasa_uzmanı|güven_inşa_edici|aciliyet_yaratıcı",
    "primary_message": "Ana mesajın tek cümle özeti",
    "tone": "samimi|profesyonel|uzman|empatik|iddialı",
    "opening_script": "İlk temas için 2-3 cümlelik açılış scripti",
    "positioning": "Kendinizi nasıl konumlandırmalısınız"
  }},
  "key_questions": [
    {{
      "question": "Sorulacak soru",
      "purpose": "Bu soruyu neden sormak gerekiyor",
      "best_moment": "Ne zaman sormak gerekiyor",
      "ideal_answer": "İdeal yanıt ne olmalı",
      "priority": "yüksek|orta|düşük"
    }}
  ],
  "objection_handling": [
    {{
      "objection": "Olası itiraz",
      "response": "Profesyonel yanıt",
      "follow_up": "Yanıttan sonra yapılacak hareket",
      "probability": "yüksek|orta|düşük"
    }}
  ],
  "followup_schedule": {{
    "contact_1": {{
      "timing": "Hemen / 24 saat içinde",
      "channel": "whatsapp|telefon|email",
      "message": "İletişim mesajı veya konuşma notu",
      "goal": "Bu temasın hedefi"
    }},
    "contact_2": {{
      "timing": "3-5 gün sonra",
      "channel": "telefon|whatsapp",
      "message": "İkinci temas notu",
      "goal": "İkinci temasın hedefi"
    }},
    "contact_3": {{
      "timing": "2 hafta sonra",
      "channel": "yüz yüze|telefon",
      "message": "Üçüncü temas notu",
      "goal": "Üçüncü temasın hedefi"
    }},
    "contact_4": {{
      "timing": "1 ay sonra",
      "channel": "telefon|whatsapp",
      "message": "Dördüncü temas notu",
      "goal": "Dördüncü temasın hedefi"
    }}
  }},
  "talking_points": [
    {{
      "point": "Ana konuşma noktası",
      "supporting_data": "Destekleyici veri veya argüman",
      "delivery": "Nasıl sunulmalı"
    }}
  ],
  "recommended_actions": [
    {{
      "action": "Yapılacak eylem",
      "priority": "acil|yüksek|orta|düşük",
      "timeframe": "Ne zaman yapılmalı",
      "expected_outcome": "Beklenen sonuç"
    }}
  ],
  "swot": {{
    "strengths": ["Danışman olarak avantajınız 1", "Avantaj 2"],
    "weaknesses": ["Zayıf nokta 1", "Dikkat edilmesi gereken 2"],
    "opportunities": ["Fırsat 1", "Fırsat 2"],
    "threats": ["Risk 1", "Risk 2"]
  }},
  "urgency_triggers": [
    {{
      "trigger": "Aciliyet tetikleyicisi",
      "explanation": "Neden bu bir avantaj",
      "how_to_use": "Nasıl kullanılmalı"
    }}
  ],
  "verdict": "Bu lead hakkında 2-3 cümlelik genel değerlendirme ve öneri",
  "confidence_score": 7,
  "resistance_level": "orta",
  "next_contact_timing": "24 saat içinde WhatsApp ile başlayın",
  "estimated_conversion_probability": "yüksek|orta|düşük",
  "risk_flags": ["Dikkat edilmesi gereken önemli risk varsa buraya yazın"]
}}

JSON dışında hiçbir şey yazma. Tüm alanları doldur. Türkçe yaz."""


def _call_gemini_multimodal(
    prompt: str,
    images_b64: list,
    audio_b64: str | None,
    audio_mime: str,
    model: str | None = None,
) -> dict:
    """
    Gemini API'ye multimodal istek gönderir.

    Hata yönetimi (Google dokümantasyonu: https://ai.google.dev/gemini-api/docs/troubleshooting):
      503 "high demand"  → MAX_RETRIES kez exponential backoff ile yeniden dener
      429 rate-limit     → yanıttaki "retry in Xs" süresini bekler
      429 quota=0        → bu model ücretsiz katmanda yok; yedek modele geçer
      Deprecated modeller (gemini-2.0-*) hiçbir zaman kullanılmaz
    """
    import requests as req

    use_model = model or GEMINI_MODEL

    # Parts listesi
    parts: list = []
    for i, b64 in enumerate(images_b64[:8]):
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        parts.append({"text": f"[Görüntü {i+1}: Sahibinden ilan veya WhatsApp ekran görüntüsü]"})

    if audio_b64:
        ab = audio_b64.split(",", 1)[1] if "," in audio_b64 else audio_b64
        parts.append({"inline_data": {"mime_type": audio_mime or "audio/webm", "data": ab}})
        parts.append({"text": "[Ses kaydı: Danışman-ev sahibi görüşmesi]"})

    parts.append({"text": prompt})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature":      0.4,
            "maxOutputTokens":  8192,
            "responseMimeType": "application/json",
        },
    }

    # Sadece güncel 2.5 modelleri; 2.0-flash deprecated olduğu için eklenmez
    models_to_try = [use_model]
    if use_model != GEMINI_FALLBACK and "2.0" not in use_model:
        models_to_try.append(GEMINI_FALLBACK)

    last_error = "Bilinmeyen hata"

    for attempt_model in models_to_try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{attempt_model}:generateContent?key={GEMINI_API_KEY}"
        )
        delay = GEMINI_RETRY_DELAY

        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                resp = req.post(url, json=payload, timeout=120)
                data = resp.json()

                # ── Başarılı yanıt ───────────────────────────────────────
                if resp.ok:
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return {"ok": False, "error": "Gemini boş yanıt döndürdü"}
                    raw = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(p.get("text", "") for p in raw).strip()
                    text = re.sub(r"^```(?:json)?", "", text).strip()
                    text = re.sub(r"```$",          "", text).strip()
                    parsed = json.loads(text)
                    if attempt_model != use_model:
                        print(f"✅ Gemini yanıt verdi (yedek: {attempt_model})")
                    return {"ok": True, "strategy": parsed}

                # ── Hata yanıtı ──────────────────────────────────────────
                err     = data.get("error", {})
                err_msg = err.get("message", str(data))
                status  = resp.status_code
                last_error = err_msg

                # 503 — Geçici yüksek yük → yeniden dene
                if status == 503 or "high demand" in err_msg.lower() or "overloaded" in err_msg.lower():
                    print(f"⏳ {attempt_model} meşgul (deneme {attempt}/{GEMINI_MAX_RETRIES}), {delay}s bekleniyor...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue

                # 429 — Kota / hız sınırı
                if status == 429:
                    # "limit: 0" → bu model artık ücretsiz kotada yok, yedeke geç
                    if "limit: 0" in err_msg:
                        print(f"⛔ {attempt_model}: ücretsiz kota=0, yedek deneniyor...")
                        last_error = (
                            f"'{attempt_model}' ücretsiz katmanda kullanılamıyor "
                            "(kota=0). Google AI Studio'dan faturalandırmayı "
                            "etkinleştirin: https://aistudio.google.com/apikey"
                        )
                        break   # bu model için çık, bir sonraki modele geç

                    # "retry in Xs" → belirtilen süreyi bekle
                    m = re.search(r"retry in ([\d.]+)s", err_msg, re.IGNORECASE)
                    wait = float(m.group(1)) + 2 if m else delay
                    wait = min(wait, 65)
                    print(f"⏳ {attempt_model} hız sınırı (deneme {attempt}/{GEMINI_MAX_RETRIES}), {wait:.0f}s bekleniyor...")
                    time.sleep(wait)
                    delay = min(delay * 2, 60)
                    continue

                # Diğer hatalar (400, 403, 404…) → yeniden deneme olmaz
                return {"ok": False, "error": err_msg}

            except json.JSONDecodeError as e:
                return {"ok": False, "error": f"JSON parse hatası: {e}"}
            except req.exceptions.Timeout:
                last_error = "API timeout (120s)"
                print(f"⚠️  {attempt_model} timeout (deneme {attempt})")
                time.sleep(delay)
                delay = min(delay * 2, 60)
            except Exception as e:
                last_error = str(e)
                print(f"⚠️  {attempt_model} beklenmedik hata (deneme {attempt}): {e}")
                time.sleep(delay)
                delay = min(delay * 2, 60)

        lbl = "yedek model de başarısız." if attempt_model == GEMINI_FALLBACK else "yedek modele geçiliyor..."
        print(f"❌ {attempt_model} tüm denemeler başarısız — {lbl}")

    return {"ok": False, "error": last_error}


def _build_transcript_prompt(audio_mime: str) -> str:
    return """Bu ses kaydını tam olarak transkript et. Konuşma Türkçe olabilir.
Transkripti düz metin olarak ver, başka açıklama ekleme."""


def _transcribe_audio(audio_b64: str, audio_mime: str) -> str | None:
    """Ses kaydını Gemini ile metin olarak çıkarır."""
    import requests as req

    if not audio_b64 or not GEMINI_API_KEY:
        return None

    if "," in audio_b64:
        audio_b64 = audio_b64.split(",", 1)[1]

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": audio_mime or "audio/webm",
                        "data": audio_b64,
                    }
                },
                {"text": _build_transcript_prompt(audio_mime)},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
    }
    try:
        resp = req.post(url, json=payload, timeout=60)
        data = resp.json()
        if resp.ok:
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts).strip() or None
    except Exception as e:
        print(f"⚠️  Transkript hatası: {e}")
    return None


# ── Ana Fonksiyon ────────────────────────────────────────────────

def analyze_fsbo(
    contact_data: dict,
    screenshots: list | None      = None,   # [base64_str, ...]
    text_input:  str | None       = None,
    audio_b64:   str | None       = None,
    audio_mime:  str              = "audio/webm",
    timeline:    list | None      = None,
) -> dict:
    """
    FSBO stratejisini Gemini 2.5 Flash ile üretir.

    Returns:
        {"ok": True, "strategy": {...}, "audio_transcript": "..." | None}
        {"ok": False, "error": "..."}
    """
    if not _is_configured():
        return {"ok": False, "error": "GEMINI_API_KEY tanımlanmamış"}

    images  = screenshots or []
    tl      = timeline    or []

    # Ses transkripti
    transcript = None
    if audio_b64:
        print(f"🎙️  Ses kaydı transkript ediliyor...")
        transcript = _transcribe_audio(audio_b64, audio_mime)
        if transcript:
            print(f"✅ Transkript hazır ({len(transcript)} karakter)")
            # Transkrip'i text_input'a ekle
            extra = f"\n\n[SES KAYDI TRANSKRİPTİ]\n{transcript}"
            text_input = (text_input or "") + extra

    # Prompt oluştur
    prompt = _build_prompt(contact_data, text_input or "", tl)

    print(f"🤖 FSBO analizi başlatıldı: {contact_data.get('name','?')} | "
          f"{len(images)} görüntü | ses={'evet' if audio_b64 else 'hayır'}")

    result = _call_gemini_multimodal(
        prompt=prompt,
        images_b64=images,
        audio_b64=audio_b64,
        audio_mime=audio_mime,
    )

    if result.get("ok"):
        strategy = result["strategy"]
        strategy["generated_at"] = datetime.now(timezone.utc).isoformat()
        strategy["input_summary"] = {
            "images_count":   len(images),
            "has_audio":      bool(audio_b64),
            "has_text":       bool(text_input and text_input.strip()),
            "timeline_count": len(tl),
        }
        print(f"✅ FSBO analizi tamamlandı | skor: {strategy.get('confidence_score','?')}/10 | "
              f"direnç: {strategy.get('resistance_level','?')}")
        return {
            "ok":               True,
            "strategy":         strategy,
            "audio_transcript": transcript,
        }

    print(f"❌ FSBO analiz hatası: {result.get('error')}")
    return result
