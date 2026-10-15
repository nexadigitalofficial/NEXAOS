# -*- coding: utf-8 -*-
"""
NexaScout Flask Blueprint / Routes
NexaCRM Pro Entegrasyonu (Faz 2)
Uçtan Uca Otonom Portföy Scraper + Vision/Hukuk/Kurum Analizi + Alıcı Eşleme + Docx Üretici
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify, send_file, current_app

logger = logging.getLogger("nexascout")

nexascout_bp = Blueprint("nexascout", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIOS_DIR = os.path.join(BASE_DIR, "data", "PORTFOYLER")

try:
    from nexascout.portfolio_buyer_pipeline import run_portfolio_buyer_pipeline, PORTFOLIOS_DIR as PIPELINE_DIR
    from nexascout.portfolio_scraper import scrape_any_listing
    from nexascout.property_analyzer import analyze_scraped_property
except ImportError:
    from .portfolio_buyer_pipeline import run_portfolio_buyer_pipeline, PORTFOLIOS_DIR as PIPELINE_DIR
    from .portfolio_scraper import scrape_any_listing
    from .property_analyzer import analyze_scraped_property


@nexascout_bp.route("/api/nexascout/status", methods=["GET"])
def nexascout_status():
    """NexaScout servis ve modül durumunu döndürür."""
    token_path = os.path.join(BASE_DIR, "token.json")
    client_secret_path = os.path.join(BASE_DIR, "client_secret.json")
    
    return jsonify({
        "status": "ready",
        "version": "2.0-Agentic",
        "gmail_api_authorized": os.path.exists(token_path),
        "client_secret_present": os.path.exists(client_secret_path),
        "has_gemini_key": bool(os.environ.get("GEMINI_API_KEY")),
        "portfolios_dir": PORTFOLIOS_DIR
    })


@nexascout_bp.route("/api/nexascout/pipeline", methods=["POST"])
@nexascout_bp.route("/api/portfolio_pipeline", methods=["POST"])
def run_pipeline():
    """
    Girilen portföy linkini otonom olarak scrape eder,
    multimodal görsel ve hukuki analiz yapar,
    8 kurumsal sektöre göre PropFit skorlarını hesaplar,
    4'lü pazarlama metinlerini ve resmi Word teklif dosyasını üretir.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify({"status": "error", "error": "Geçerli bir portföy URL'si gereklidir."}), 400

        broker_name = data.get("broker_name", "YİĞİT NARİN")
        broker_phone = data.get("broker_phone", "0532 451 40 08")
        broker_office = data.get("broker_office", "Coldwell Banker VIP Real Gayrimenkul")

        result = run_portfolio_buyer_pipeline(
            url=url,
            broker_name=broker_name,
            broker_phone=broker_phone,
            broker_office=broker_office
        )

        analysis = result.get("analysis", {})
        outputs = result.get("outputs", {})
        folder_path = result.get("folder_path", "")
        folder_name = os.path.basename(folder_path) if folder_path else result.get("folder_name", "")
        docx_download_url = f"/download/nexascout_docx/{folder_name}" if folder_name else ""

        return jsonify({
            "status": "success",
            "data": {
                "title": analysis.get("title") or result.get("title", ""),
                "price": analysis.get("price") or result.get("price", ""),
                "location": analysis.get("location") or result.get("location", ""),
                "kapali_m2": analysis.get("kapali_m2") or result.get("kapali_m2", ""),
                "asset_class": analysis.get("asset_class") or result.get("asset_class", ""),
                "advantages": analysis.get("advantages") or result.get("advantages", []),
                "vision_analysis": analysis.get("vision_analysis") or result.get("vision_analysis", {}),
                "matched_sectors": analysis.get("matched_sectors") or result.get("matched_sectors", []),
                "meslektas_metni": outputs.get("meslektas_metni") or result.get("meslektas_metni", ""),
                "wa_teaser": outputs.get("wa_teaser") or result.get("wa_teaser", ""),
                "email_subject": outputs.get("email_subject") or result.get("email_subject", ""),
                "email_body": outputs.get("email_body") or result.get("email_body", ""),
                "gorsel_metin": outputs.get("gorsel_metin") or result.get("gorsel_metin", ""),
                "folder_name": folder_name,
                "docx_url": docx_download_url,
                "scraped_summary": {
                    "listing_id": result.get("scraped", {}).get("listing_id"),
                    "photo_count": len(result.get("scraped", {}).get("photos", [])),
                    "specs": result.get("scraped", {}).get("specs", {})
                }
            }
        })
    except Exception as e:
        logger.exception("NexaScout pipeline execution failed")
        return jsonify({"status": "error", "error": str(e)}), 500


@nexascout_bp.route("/download/nexascout_docx/<path:folder_name>", methods=["GET"])
@nexascout_bp.route("/download/portfolio_docx/<path:folder_name>", methods=["GET"])
def download_docx(folder_name):
    """Oluşturulan resmi Word teklif dosyasını (.docx) indirir."""
    try:
        # data/PORTFOYLER altındaki klasörü bul
        candidate_paths = [
            os.path.join(PORTFOLIOS_DIR, folder_name, "PORTFOY_YATIRIM_VE_HEDEF_ALICI_DOSYASI.docx"),
            os.path.join(BASE_DIR, "data", "PORTFOYLER", folder_name, "PORTFOY_YATIRIM_VE_HEDEF_ALICI_DOSYASI.docx"),
        ]

        docx_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                docx_path = p
                break

        if not docx_path:
            return jsonify({"status": "error", "error": f"Word dosyası bulunamadı: {folder_name}"}), 404

        return send_file(
            docx_path,
            as_attachment=True,
            download_name=f"NEXASCOUT_YATIRIM_TEKLIFI_{folder_name[:25]}.docx",
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
