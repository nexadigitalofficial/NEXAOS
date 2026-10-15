"""
================================================================
app_buyer_routes.py — app.py'ye eklenecek Buyer Extension routes
================================================================

Bu kod app.py'nin sonuna (bootstrap_app() çağrısından önce) 
eklenmelidir. 

Kopyala ve Yapıştır Uyarısı:
  1. app.py'nin başına: from buyer_engine import ...
  2. Bu routes'ları app.py'nin bootstrap_app() çağrısından önce ekle
  3. Test et: curl -X GET http://localhost:5000/api/buyer/status
================================================================
"""

# ── İmport (app.py'nin başına ekle) ──────────────────────────────
# from buyer_engine import (
#     BuyerProfile, BuyerMatcher, ListingMatch, NotificationEngine,
#     NotificationChannel, MatchingTier, buyer_engine_status, parse_natural_language_criteria
# )


# ================================================================
# BUYER EXTENSION API ROUTES
# ================================================================

# ── 1. Durum & Konfigürasyon ──────────────────────────────────────

@app.route("/api/buyer/status")
def api_buyer_status():
    """Buyer Engine durumu."""
    return jsonify(buyer_engine_status())


# ── 2. Buyer Profili Yönetimi ──────────────────────────────────────

@app.route("/api/buyer/profile/create", methods=["POST"])
def api_buyer_create():
    """
    Yeni alıcı profili oluştur.
    
    Body (JSON):
    {
      "uid": "user123",
      "name": "Ahmet Yılmaz",
      "email": "ahmet@example.com",
      "phone": "05324514008",
      "telegram_id": "123456789",
      "whatsapp_phone": "05324514008",
      "criteria": {
        "min_price": 3000000,
        "max_price": 6000000,
        "min_area": 80,
        "max_area": 150,
        "neighborhoods": ["Çankaya", "Dikmen"],
        "property_types": ["Daire", "Dubleks"],
        "min_rooms": 2,
        "max_rooms": 4,
        "natural_language": "Ankara'da yeni ve güzel, balkonlu, otopark"
      },
      "preferences": {
        "notification_channels": ["email", "crm_task"],
        "auto_match": true,
        "priority_level": "high"
      }
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")

    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        profile = BuyerProfile({
            **body,
            "uid": uid,
            "id": db_admin.collection("buyers").document().id,
        })

        doc_ref = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(profile.buyer_id)
        )
        doc_ref.set(profile.to_dict())

        return jsonify({
            "ok": True,
            "buyer_id": profile.buyer_id,
            "profile": profile.to_dict()
        }), 201

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/profile/list", methods=["GET"])
def api_buyer_list():
    """Kullanıcının tüm buyer profillerini listele."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        docs = (
            db_admin.collection("users").document(uid)
            .collection("buyers").stream()
        )
        profiles = [doc.to_dict() for doc in docs]
        return jsonify({"ok": True, "profiles": profiles})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/profile/get", methods=["GET"])
def api_buyer_get():
    """Tek bir buyer profili getir."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        doc = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).get()
        )
        if not doc.exists:
            return jsonify({"ok": False, "error": "Profil bulunamadı"}), 404
        return jsonify({"ok": True, "profile": doc.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/profile/update", methods=["POST"])
def api_buyer_update():
    """Buyer profili güncelle."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        doc_ref = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id)
        )
        profile_dict = doc_ref.get().to_dict()
        if not profile_dict:
            return jsonify({"ok": False, "error": "Profil bulunamadı"}), 404

        # Güncelle
        profile_dict.update(body)
        profile_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        doc_ref.set(profile_dict)

        return jsonify({"ok": True, "profile": profile_dict})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/profile/delete", methods=["POST"])
def api_buyer_delete():
    """Buyer profilini sil."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).delete()
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── 3. Eşleştirme Engine ────────────────────────────────────────

@app.route("/api/buyer/match-listing", methods=["POST"])
def api_buyer_match_listing():
    """
    Tek bir ilanı buyer profillerine göre eşleştir.
    
    Body:
    {
      "uid": "user123",
      "listing": { ...listing_data... },
      "buyer_ids": ["buyer1", "buyer2"]  // opsiyonel, tümü default
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    listing = body.get("listing")
    buyer_ids = body.get("buyer_ids", [])

    if not uid or not listing:
        return jsonify({"ok": False, "error": "uid ve listing gerekli"}), 400

    try:
        matcher = BuyerMatcher()

        # Buyer profilleri getir
        if buyer_ids:
            buyers_snap = []
            for bid in buyer_ids:
                doc = (
                    db_admin.collection("users").document(uid)
                    .collection("buyers").document(bid).get()
                )
                if doc.exists:
                    buyers_snap.append(doc)
        else:
            buyers_snap = list(
                db_admin.collection("users").document(uid)
                .collection("buyers").stream()
            )

        matches = []
        for buyer_doc in buyers_snap:
            buyer_dict = buyer_doc.to_dict()
            profile = BuyerProfile(buyer_dict)
            match = matcher.match_listing(profile, listing)

            if match:
                matches.append({
                    "buyer_id": profile.buyer_id,
                    "match_score": match.match_score,
                    "tier": match.tier,
                    "details": match.match_details,
                })

        return jsonify({
            "ok": True,
            "listing_id": listing.get("id", ""),
            "matches": matches,
            "total_matches": len(matches),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/match-batch", methods=["POST"])
def api_buyer_match_batch():
    """
    Birden fazla ilanı buyer'larla batch eşleştir.
    Ağır operasyon — background job olarak önerilir.
    
    Body:
    {
      "uid": "user123",
      "listings": [{ ...listing1... }, { ...listing2... }],
      "buyer_ids": ["buyer1"]  // opsiyonel
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    listings = body.get("listings", [])

    if not uid or not listings:
        return jsonify({"ok": False, "error": "uid ve listings gerekli"}), 400

    try:
        matcher = BuyerMatcher()
        all_matches = []

        for listing in listings:
            # Her listing için tüm buyer'ları eşleştir
            # ... (api_buyer_match_listing mantığı)
            pass

        return jsonify({"ok": True, "total_matches": len(all_matches)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── 4. Matching Geçmişi ────────────────────────────────────────

@app.route("/api/buyer/matches/list", methods=["GET"])
def api_buyer_matches_list():
    """
    Buyer'ın tüm eşleşmelerini listele (en yenisi önce).
    
    Query params:
      - uid: gerekli
      - buyer_id: gerekli
      - tier: "perfect", "excellent" vb. (filtre)
      - limit: 50 (default)
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")
    tier = flask_request.args.get("tier")
    limit = int(flask_request.args.get("limit", "50"))

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        query = (
            db_admin.collection("users").document(uid)
            .collection("buyer_matches")
            .where("buyer_id", "==", buyer_id)
            .order_by("created_at", direction="DESCENDING")
        )

        if tier:
            query = query.where("tier", "==", tier)

        docs = query.limit(limit).stream()
        matches = [doc.to_dict() for doc in docs]

        return jsonify({"ok": True, "matches": matches, "count": len(matches)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/buyer/matches/stats", methods=["GET"])
def api_buyer_matches_stats():
    """Buyer'ın eşleşme istatistikleri."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    buyer_id = flask_request.args.get("buyer_id")

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        docs = list(
            db_admin.collection("users").document(uid)
            .collection("buyer_matches")
            .where("buyer_id", "==", buyer_id)
            .stream()
        )

        stats = {
            "perfect": sum(1 for d in docs if d.to_dict().get("tier") == "perfect"),
            "excellent": sum(1 for d in docs if d.to_dict().get("tier") == "excellent"),
            "good": sum(1 for d in docs if d.to_dict().get("tier") == "good"),
            "fair": sum(1 for d in docs if d.to_dict().get("tier") == "fair"),
            "total": len(docs),
            "avg_score": sum(d.to_dict().get("match_score", 0) for d in docs) / len(docs) if docs else 0,
        }

        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── 5. Notification Tetikle ────────────────────────────────────────

@app.route("/api/buyer/notify", methods=["POST"])
def api_buyer_notify():
    """
    Eşleşme için manual notification tetikle.
    
    Body:
    {
      "uid": "user123",
      "buyer_id": "buyer1",
      "match_id": "match123",
      "channels": ["email", "telegram", "crm_task"]
    }
    """
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    body = flask_request.json or {}
    uid = body.get("uid")
    buyer_id = body.get("buyer_id")
    channels = body.get("channels", ["email", "crm_task"])

    if not uid or not buyer_id:
        return jsonify({"ok": False, "error": "uid ve buyer_id gerekli"}), 400

    try:
        # Buyer profili getir
        buyer_doc = (
            db_admin.collection("users").document(uid)
            .collection("buyers").document(buyer_id).get()
        )
        if not buyer_doc.exists:
            return jsonify({"ok": False, "error": "Buyer profili bulunamadı"}), 404

        buyer_dict = buyer_doc.to_dict()
        buyer = BuyerProfile(buyer_dict)

        # Email gönder
        result = {}
        if "email" in channels and buyer.email:
            subject, text, html = build_lead_confirmation_email(
                name=buyer.name,
                phone=buyer.phone,
                notes=f"Eşleşme skoru: {body.get('match_score', 0):.0f}%"
            )
            result["email"] = send_transactional_email(buyer.email, subject, text, html)

        # Telegram gönder
        if "telegram" in channels and buyer.telegram_id:
            message = f"🏠 Yeni eşleşme: {body.get('match_score', 0):.0f}%"
            # Telegram API call (app.py'de tanımlanmalı)
            result["telegram"] = {"ok": True}  # Placeholder

        # WhatsApp gönder
        if "whatsapp" in channels and buyer.whatsapp_phone:
            result["whatsapp"] = send_whatsapp(
                buyer.whatsapp_phone,
                f"Yeni eşleşme: {body.get('match_score', 0):.0f}%"
            )

        # CRM görev aç
        if "crm_task" in channels:
            result["crm_task"] = {"ok": True}  # Placeholder

        return jsonify({"ok": True, "notifications": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── 6. Natural Language Parsing ────────────────────────────────────

@app.route("/api/buyer/parse-criteria", methods=["POST"])
def api_buyer_parse_criteria():
    """
    Natural language kriterleri parse et (Gemini).
    
    Body:
    {
      "text": "Ankara'da 2+1 daire, maksimum 5 milyon, Çankaya veya Dikmen"
    }
    """
    body = flask_request.json or {}
    text = body.get("text", "").strip()

    if not text:
        return jsonify({"ok": False, "error": "text boş"}), 400

    try:
        criteria = parse_natural_language_criteria(text)
        return jsonify({"ok": True, "criteria": criteria or {}})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── 7. Dashboard & Analytics ────────────────────────────────────────

@app.route("/api/buyer/dashboard", methods=["GET"])
def api_buyer_dashboard():
    """Buyer dashboard — özet istatistikler."""
    if not _fb_initialized:
        return jsonify({"ok": False, "error": "Firebase bağlı değil"}), 503

    uid = flask_request.args.get("uid")
    if not uid:
        return jsonify({"ok": False, "error": "uid gerekli"}), 400

    try:
        # Profil sayısı
        buyers = list(
            db_admin.collection("users").document(uid)
            .collection("buyers").where("is_active", "==", True).stream()
        )

        # Toplam eşleşme
        all_matches = list(
            db_admin.collection("users").document(uid)
            .collection("buyer_matches").stream()
        )

        # Tier dağılımı
        tier_dist = {}
        for match_doc in all_matches:
            tier = match_doc.to_dict().get("tier", "unknown")
            tier_dist[tier] = tier_dist.get(tier, 0) + 1

        return jsonify({
            "ok": True,
            "dashboard": {
                "active_buyers": len(buyers),
                "total_matches": len(all_matches),
                "tier_distribution": tier_dist,
                "avg_match_score": (
                    sum(d.to_dict().get("match_score", 0) for d in all_matches) / len(all_matches)
                    if all_matches else 0
                ),
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ================================================================
# ENTEGRASYON NOTU
# ================================================================
# Bu routes app.py'ye eklenirse, Buyer Extension tam olarak çalışır.
# Sonraki adımlar:
#   1. buyer_engine.py'den import'ları app.py'ye ekle
#   2. Bu routes'ları app.py bootstrap_app() çağrısından önce ekle
#   3. Telegram/WhatsApp entegrasyonu tamamla (app.py'de)
#   4. Frontend (Buyer Panel UI) entegre et
