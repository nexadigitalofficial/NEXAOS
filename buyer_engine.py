"""
================================================================
buyer_engine.py — AI Buyer Extension / Alıcı Uzantısı
================================================================

Fonksiyonalite:
  1. Alıcı profili oluştur/güncelle (kriterleri, tercihler, iletişim)
  2. Yeni ilanları alıcı profileri ile eşleştir (benzerlik skoru)
  3. Matching: Telegram, Email, CRM görevleri ile otomasyonu tetikle
  4. Dashboard: Eşleşmeleri, başarı oranını, potansiyel değeri göster

Entegrasyon:
  - Firebase Firestore: /users/{uid}/buyers, /buyers_listings
  - mailer.py: send_transactional_email()
  - wa_cloud.py: send_whatsapp() + send_whatsapp_template()
  - app.py: /api/buyer/* routes

Özellikler:
  • Vektör benzerliği ile semantik matching
  • Gemini ile natural language filter parsing
  • Multi-channel notification (Email, Telegram, WhatsApp)
  • Matching pipeline: Filter → Score → Notify → Log
  • Fuzzy matching (lokasyon, fiyat aralığı, vb.)
================================================================
"""

import os
import json
import time
import math
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

# Opsiyonel: sentence-transformers (vektör benzerliği için)
try:
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMER = True
except ImportError:
    _SENTENCE_TRANSFORMER = False
    print("[!] sentence-transformers yuklu degil - pip install sentence-transformers")


class NotificationChannel(Enum):
    """Kullanıcıya bildirim gönderilecek kanallar."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    CRM_TASK = "crm_task"
    DASHBOARD = "dashboard"


class MatchingTier(Enum):
    """Eşleşme kalitesi seviyeleri."""
    PERFECT = "perfect"        # 90-100
    EXCELLENT = "excellent"    # 75-89
    GOOD = "good"              # 60-74
    FAIR = "fair"              # 45-59
    WEAK = "weak"              # 30-44
    POOR = "poor"              # <30


# ================================================================
# KONFIGÜRASYON
# ================================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MIN_MATCH_SCORE = 50  # İlan gösterilmesi için minimum skor
VECTOR_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Hızlı, hafif (80M)


# ================================================================
# VERİ MODELLERİ
# ================================================================

class BuyerProfile:
    """Alıcı profili — kriterleri ve tercihler."""

    def __init__(self, profile_dict: dict):
        self.buyer_id = profile_dict.get("id", "")
        self.uid = profile_dict.get("uid", "")
        self.name = profile_dict.get("name", "")
        self.email = profile_dict.get("email", "")
        self.phone = profile_dict.get("phone", "")
        self.telegram_id = profile_dict.get("telegram_id")
        self.whatsapp_phone = profile_dict.get("whatsapp_phone")

        # Kriterler
        self.criteria = profile_dict.get("criteria", {})
        self.min_price = self.criteria.get("min_price", 0)
        self.max_price = self.criteria.get("max_price", 10_000_000)
        self.min_area = self.criteria.get("min_area", 0)
        self.max_area = self.criteria.get("max_area", 1000)
        self.neighborhoods = self.criteria.get("neighborhoods", [])
        self.property_types = self.criteria.get("property_types", [])
        self.min_rooms = self.criteria.get("min_rooms")
        self.max_rooms = self.criteria.get("max_rooms")
        self.min_age = self.criteria.get("min_age")
        self.max_age = self.criteria.get("max_age")
        self.amenities_required = self.criteria.get("amenities_required", [])
        self.natural_language_criteria = self.criteria.get("natural_language", "")

        # Tercihler
        self.preferences = profile_dict.get("preferences", {})
        self.notification_channels = self.preferences.get("notification_channels", ["email", "crm_task"])
        self.auto_match = self.preferences.get("auto_match", True)
        self.weekly_summary = self.preferences.get("weekly_summary", False)
        self.priority_level = self.preferences.get("priority_level", "medium")  # low/medium/high

        # Durum
        self.is_active = profile_dict.get("is_active", True)
        self.created_at = profile_dict.get("created_at", datetime.now(timezone.utc).isoformat())
        self.updated_at = profile_dict.get("updated_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Firebase'e kaydetmek için dict'e dönüştür."""
        return {
            "id": self.buyer_id,
            "uid": self.uid,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "telegram_id": self.telegram_id,
            "whatsapp_phone": self.whatsapp_phone,
            "criteria": {
                "min_price": self.min_price,
                "max_price": self.max_price,
                "min_area": self.min_area,
                "max_area": self.max_area,
                "neighborhoods": self.neighborhoods,
                "property_types": self.property_types,
                "min_rooms": self.min_rooms,
                "max_rooms": self.max_rooms,
                "min_age": self.min_age,
                "max_age": self.max_age,
                "amenities_required": self.amenities_required,
                "natural_language": self.natural_language_criteria,
            },
            "preferences": {
                "notification_channels": self.notification_channels,
                "auto_match": self.auto_match,
                "weekly_summary": self.weekly_summary,
                "priority_level": self.priority_level,
            },
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class ListingMatch:
    """İlan-Alıcı eşleşmesi."""

    def __init__(
        self,
        buyer_id: str,
        listing_id: str,
        listing_data: dict,
        match_score: float,
        match_details: dict,
    ):
        self.buyer_id = buyer_id
        self.listing_id = listing_id
        self.listing_data = listing_data
        self.match_score = match_score
        self.match_details = match_details
        self.tier = self._determine_tier()
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.notification_sent = False
        self.user_interest = None  # "interested", "not_interested", "enquiry_sent", vb.

    def _determine_tier(self) -> str:
        """Skor'a göre tier belirle."""
        score = self.match_score
        if score >= 90:
            return MatchingTier.PERFECT.value
        elif score >= 75:
            return MatchingTier.EXCELLENT.value
        elif score >= 60:
            return MatchingTier.GOOD.value
        elif score >= 45:
            return MatchingTier.FAIR.value
        elif score >= 30:
            return MatchingTier.WEAK.value
        else:
            return MatchingTier.POOR.value

    def to_dict(self) -> dict:
        """Firebase'e kaydetmek için dict'e dönüştür."""
        return {
            "buyer_id": self.buyer_id,
            "listing_id": self.listing_id,
            "listing_data": self.listing_data,
            "match_score": self.match_score,
            "match_details": self.match_details,
            "tier": self.tier,
            "created_at": self.created_at,
            "notification_sent": self.notification_sent,
            "user_interest": self.user_interest,
        }


# ================================================================
# MATCHING ENGINE
# ================================================================

class BuyerMatcher:
    """Alıcı profili ile ilanları eşleştir."""

    def __init__(self):
        self.vector_model = None
        if _SENTENCE_TRANSFORMER:
            try:
                self.vector_model = SentenceTransformer(VECTOR_MODEL)
                print(f"✅ Vector model yüklendi: {VECTOR_MODEL}")
            except Exception as e:
                print(f"⚠️  Vector model yüklenemedi: {e}")

    def match_listing(self, buyer: BuyerProfile, listing: dict) -> Optional[ListingMatch]:
        """
        İlanı alıcı profili ile eşleştir.
        İlan: {"id", "price", "area", "location", "property_type", "rooms", "age", "amenities", ...}
        """
        match_details = {}
        scores = {}

        # 1. Fiyat eşleşmesi
        price = listing.get("price", 0)
        if price < buyer.min_price or price > buyer.max_price:
            return None  # Fiyat aralığı dışında
        price_score = self._score_price(price, buyer)
        scores["price"] = price_score
        match_details["price"] = f"{price:,} TL ({price_score:.0f}%)"

        # 2. Alan eşleşmesi
        area = listing.get("area", 0)
        if area < buyer.min_area or area > buyer.max_area:
            return None  # Alan aralığı dışında
        area_score = self._score_area(area, buyer)
        scores["area"] = area_score
        match_details["area"] = f"{area} m² ({area_score:.0f}%)"

        # 3. Lokasyon eşleşmesi
        location = listing.get("location", "").strip()
        location_score = self._score_location(location, buyer)
        if location_score == 0 and buyer.neighborhoods:
            return None  # Lokasyon kritik ve eşleşmiyor
        scores["location"] = location_score
        match_details["location"] = f"{location} ({location_score:.0f}%)"

        # 4. Mülk tipi eşleşmesi
        prop_type = listing.get("property_type", "").strip()
        prop_type_score = self._score_property_type(prop_type, buyer)
        if prop_type_score == 0 and buyer.property_types:
            return None
        scores["property_type"] = prop_type_score
        match_details["property_type"] = f"{prop_type} ({prop_type_score:.0f}%)"

        # 5. Oda sayısı eşleşmesi (opsiyonel)
        if buyer.min_rooms or buyer.max_rooms:
            rooms = listing.get("rooms", None)
            if rooms:
                rooms_score = self._score_rooms(rooms, buyer)
                scores["rooms"] = rooms_score
                match_details["rooms"] = f"{rooms} ({rooms_score:.0f}%)"

        # 6. Yaş eşleşmesi (opsiyonel)
        if buyer.min_age or buyer.max_age:
            age = listing.get("age", None)
            if age is not None:
                age_score = self._score_age(age, buyer)
                scores["age"] = age_score
                match_details["age"] = f"{age} yıl ({age_score:.0f}%)"

        # 7. Amenities eşleşmesi
        amenities = listing.get("amenities", [])
        if buyer.amenities_required:
            amenities_score = self._score_amenities(amenities, buyer)
            scores["amenities"] = amenities_score
            match_details["amenities"] = f"{amenities_score:.0f}% eşleşme"

        # 8. Natural language kriterleri (Gemini)
        if buyer.natural_language_criteria and GEMINI_API_KEY:
            nl_score = self._score_natural_language(listing, buyer)
            scores["natural_language"] = nl_score
            match_details["nl_criteria"] = f"{nl_score:.0f}%"

        # 9. Vectoral benzerlik (metafor + açıklama)
        if self.vector_model:
            vector_score = self._score_vector_similarity(listing, buyer)
            scores["vector"] = vector_score
            match_details["vector"] = f"{vector_score:.0f}%"

        # Ortalaması al (ağırlıklı)
        final_score = self._weighted_average(scores)

        if final_score < MIN_MATCH_SCORE:
            return None

        # Match nesnesi oluştur
        return ListingMatch(
            buyer_id=buyer.buyer_id,
            listing_id=listing.get("id", ""),
            listing_data=listing,
            match_score=final_score,
            match_details=match_details,
        )

    def _score_price(self, price: float, buyer: BuyerProfile) -> float:
        """Fiyat skoru (hedef için optimal)."""
        mid = (buyer.min_price + buyer.max_price) / 2
        range_width = buyer.max_price - buyer.min_price
        distance = abs(price - mid)
        # Merkeze ne kadar yakınsa o kadar yüksek skor
        return max(0, 100 - (distance / range_width) * 100)

    def _score_area(self, area: float, buyer: BuyerProfile) -> float:
        """Alan skoru."""
        mid = (buyer.min_area + buyer.max_area) / 2
        range_width = buyer.max_area - buyer.min_area
        if range_width == 0:
            return 100.0
        distance = abs(area - mid)
        return max(0, 100 - (distance / range_width) * 100)

    def _score_location(self, location: str, buyer: BuyerProfile) -> float:
        """Lokasyon skoru (kesin eşleşme veya 0)."""
        if not buyer.neighborhoods:
            return 100.0  # Lokasyon kriteri yoksa tam skor
        loc_lower = location.lower().strip()
        for nb in buyer.neighborhoods:
            if nb.lower() in loc_lower or loc_lower in nb.lower():
                return 100.0
        return 0.0  # Eşleşmedi

    def _score_property_type(self, prop_type: str, buyer: BuyerProfile) -> float:
        """Mülk tipi skoru."""
        if not buyer.property_types:
            return 100.0
        pt_lower = prop_type.lower().strip()
        for ptype in buyer.property_types:
            if ptype.lower() in pt_lower or pt_lower in ptype.lower():
                return 100.0
        return 0.0

    def _score_rooms(self, rooms: int, buyer: BuyerProfile) -> float:
        """Oda sayısı skoru."""
        if buyer.min_rooms and rooms < buyer.min_rooms:
            return 0.0
        if buyer.max_rooms and rooms > buyer.max_rooms:
            return 0.0
        return 100.0

    def _score_age(self, age: int, buyer: BuyerProfile) -> float:
        """Yaş skoru."""
        if buyer.min_age and age < buyer.min_age:
            return 0.0
        if buyer.max_age and age > buyer.max_age:
            return 0.0
        return 100.0

    def _score_amenities(self, amenities: List[str], buyer: BuyerProfile) -> float:
        """Amenities eşleşme oranı."""
        if not buyer.amenities_required:
            return 100.0
        if not amenities:
            return 0.0
        amenities_lower = [a.lower() for a in amenities]
        matches = sum(
            1 for req in buyer.amenities_required
            if any(req.lower() in am for am in amenities_lower)
        )
        return (matches / len(buyer.amenities_required)) * 100

    def _score_natural_language(self, listing: dict, buyer: BuyerProfile) -> float:
        """Gemini ile natural language kriterleri parse et ve skor ver."""
        if not GEMINI_API_KEY:
            return 50.0
        try:
            from google import genai
            genai.configure(api_key=GEMINI_API_KEY)
            client = genai.Client()
            prompt = f"""
İlan: {json.dumps(listing, ensure_ascii=False, indent=2)}

Alıcı Kriterleri (Türkçe): "{buyer.natural_language_criteria}"

Bu ilanın alıcı kriterlerine ne kadar uyduğunu 0-100 arası bir skor ver.
SADECE SAYI döndür, açıklama yapma. Örnek: 85
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=genai.GenerateContentConfig(max_output_tokens=10),
            )
            text = (response.text or "50").strip()
            score = float("".join(filter(str.isdigit, text.split("\n")[0]))) if any(c.isdigit() for c in text) else 50.0
            return min(100.0, max(0.0, score))
        except Exception as e:
            print(f"⚠️  NL scoring hatası: {e}")
            return 50.0

    def _score_vector_similarity(self, listing: dict, buyer: BuyerProfile) -> float:
        """Vector benzerliği (listing description vs buyer NL criteria)."""
        if not self.vector_model or not buyer.natural_language_criteria:
            return 50.0
        try:
            listing_text = f"{listing.get('property_type', '')} {listing.get('location', '')} {listing.get('description', '')}"
            emb_listing = self.vector_model.encode(listing_text, convert_to_tensor=True)
            emb_buyer = self.vector_model.encode(buyer.natural_language_criteria, convert_to_tensor=True)
            # Cosine similarity
            similarity = float((emb_listing @ emb_buyer.T).item())
            return max(0, min(100, similarity * 100))
        except Exception as e:
            print(f"⚠️  Vector similarity hatası: {e}")
            return 50.0

    def _weighted_average(self, scores: Dict[str, float]) -> float:
        """Ağırlıklı ortalama (kritik olanlar ağırlıklı)."""
        weights = {
            "price": 0.25,
            "area": 0.2,
            "location": 0.2,
            "property_type": 0.15,
            "rooms": 0.05,
            "age": 0.05,
            "amenities": 0.05,
            "natural_language": 0.03,
            "vector": 0.02,
        }
        total_weight = 0
        weighted_sum = 0
        for key, score in scores.items():
            weight = weights.get(key, 0.05)
            weighted_sum += score * weight
            total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 50.0


# ================================================================
# NOTIFICATION ENGINE (Placeholder)
# ================================================================

class NotificationEngine:
    """
    Eşleşmeleri alıcıya farklı kanallardan bildiri.
    Gerçek implementation: app.py'de çalışacak ve mailer.py, wa_cloud.py'yi kullanacak.
    """

    @staticmethod
    def notify_buyer(
        match: ListingMatch,
        buyer: BuyerProfile,
        channels: List[str],
    ) -> Dict[str, bool]:
        """Alıcıyı eşleşme hakkında bildir."""
        results = {}
        for channel in channels:
            try:
                if channel == "email" and buyer.email:
                    results["email"] = NotificationEngine._send_email_notification(match, buyer)
                elif channel == "telegram" and buyer.telegram_id:
                    results["telegram"] = NotificationEngine._send_telegram_notification(match, buyer)
                elif channel == "whatsapp" and buyer.whatsapp_phone:
                    results["whatsapp"] = NotificationEngine._send_whatsapp_notification(match, buyer)
                elif channel == "crm_task":
                    results["crm_task"] = NotificationEngine._create_crm_task(match, buyer)
            except Exception as e:
                print(f"❌ {channel} notification hatası: {e}")
                results[channel] = False
        return results

    @staticmethod
    def _send_email_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """Email gönder (mailer.py ile entegrasyon)."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _send_telegram_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """Telegram bildir."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _send_whatsapp_notification(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """WhatsApp gönder (wa_cloud.py ile entegrasyon)."""
        # Placeholder — app.py'de çalışacak
        return True

    @staticmethod
    def _create_crm_task(match: ListingMatch, buyer: BuyerProfile) -> bool:
        """CRM'e görev aç."""
        # Placeholder — app.py'de çalışacak
        return True


# ================================================================
# UTILITY FUNCTIONS
# ================================================================

def parse_natural_language_criteria(text: str, api_key: str = "") -> Optional[dict]:
    """
    Natural language filtreleri parse et (Gemini ile).
    "Ankara'da 2+1 daire, maksimum 4.5 milyon, Çankaya veya Dikmen"
    → {"price": 4500000, "neighborhoods": [...], "rooms": 3, ...}
    """
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai
        genai.configure(api_key=GEMINI_API_KEY)
        client = genai.Client()
        prompt = f"""
Türkçe gayrimenkul arama metnini parse et ve JSON döndür.

Metin: "{text}"

JSON formatı (istenen alanları fill et, yoksa null):
{{
  "min_price": null,
  "max_price": null,
  "min_area": null,
  "max_area": null,
  "neighborhoods": [],
  "property_types": [],
  "min_rooms": null,
  "max_rooms": null,
  "min_age": null,
  "max_age": null
}}

SADECE JSON döndür, açıklama yapma.
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.GenerateContentConfig(max_output_tokens=200),
        )
        text_out = response.text or ""
        import re
        json_match = re.search(r"\{.*\}", text_out, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"⚠️  NL parsing hatası: {e}")
    return None


# ================================================================
# STATUS
# ================================================================

def buyer_engine_status() -> dict:
    """Buyer engine durumunu döner."""
    return {
        "ok": True,
        "matcher": True,
        "vector_model": _SENTENCE_TRANSFORMER,
        "min_match_score": MIN_MATCH_SCORE,
    }
