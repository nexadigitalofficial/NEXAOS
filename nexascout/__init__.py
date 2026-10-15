# -*- coding: utf-8 -*-
"""
NexaScout Core Modules
- enrichment: Web scraping, contact info, email and social media finder
- map_generator: Interactive Folium GIS map generation
- pitch_generator: AI-powered personalized investment proposal generation (DOCX)
"""

from .enrichment import clean_phone_for_whatsapp, generate_whatsapp_url, enrich_from_website
from .map_generator import generate_interactive_map
from .pitch_generator import generate_pitch_document
from .scoring import calculate_propfit_score
from .decision_maker_hunter import find_decision_makers, generate_confidential_teaser
from .portfolio_scraper import scrape_any_listing
from .property_analyzer import analyze_scraped_property
from .portfolio_buyer_pipeline import run_portfolio_buyer_pipeline

__all__ = [
    "clean_phone_for_whatsapp",
    "generate_whatsapp_url",
    "enrich_from_website",
    "generate_interactive_map",
    "generate_pitch_document",
    "calculate_propfit_score",
    "find_decision_makers",
    "generate_confidential_teaser",
    "scrape_any_listing",
    "analyze_scraped_property",
    "run_portfolio_buyer_pipeline"
]
