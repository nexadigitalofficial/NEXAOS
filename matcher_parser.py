#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 MATCHER PARSER MODULE
========================
WhatsApp chat parsing + Turkish NLP
Arayış (search requests) ve Portföy (listings) parsing
"""

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class PropertyType(Enum):
    """Emlak Türleri"""
    DAIRE = "Daire"
    VILLA = "Villa"
    OFIS = "Ofis"
    ARSA = "Arsa"
    KOMERCE = "Komerce"
    DEPO = "Depo"
    UNKNOWN = "Unknown"

class TransactionType(Enum):
    """İşlem Türü"""
    SATILIK = "Satılık"
    KIRALIK = "Kiralık"
    TAKASLI = "Takası"
    ARANIYOR = "Arıyor"
    UNKNOWN = "Unknown"

# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ArayisRecord:
    """
    ARAYIŞ (İstek / Search Request)
    Müşterinin ne aradığını temsil eder
    """
    
    arayis_id: str  # Unique identifier
    sender: Optional[str] = None  # Kimden geliyor
    phone: Optional[str] = None  # Telefon numarası
    message_text: str = ""  # Orijinal mesaj
    
    # Lokasyon
    districts: List[str] = field(default_factory=list)  # İlçeler (Çankaya, Keçiören, vb)
    neighborhoods: List[str] = field(default_factory=list)  # Mahalleler
    
    # Emlak özellikleri
    property_types: List[PropertyType] = field(default_factory=list)  # Daire, Villa, vb
    transaction_type: TransactionType = TransactionType.UNKNOWN  # Satılık/Kiralık
    
    # Finansal
    budget_min: Optional[float] = None  # Minimum bütçe
    budget_max: Optional[float] = None  # Maximum bütçe
    
    # Fizik özellikleri
    rooms: List[str] = field(default_factory=list)  # 2+1, 3+1, vb
    area_min: Optional[float] = None  # Minimum alan
    area_max: Optional[float] = None  # Maximum alan
    
    # Özellikler
    features_wanted: List[str] = field(default_factory=list)  # Balkon, Park, vb
    features_unwanted: List[str] = field(default_factory=list)  # İstenmeyen
    
    # Metadata
    urgency_level: int = 1  # 1-5 (aciliyet seviyesi)
    confidence: float = 0.0  # Parser güven puanı (0-1)
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "whatsapp"
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not self.arayis_id:
            self.arayis_id = f"arayis_{hash(self.message_text[:50])}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'arayis_id': self.arayis_id,
            'sender': self.sender,
            'phone': self.phone,
            'message_text': self.message_text,
            'districts': self.districts,
            'neighborhoods': self.neighborhoods,
            'property_types': [pt.value for pt in self.property_types],
            'transaction_type': self.transaction_type.value,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'rooms': self.rooms,
            'area_min': self.area_min,
            'area_max': self.area_max,
            'features_wanted': self.features_wanted,
            'features_unwanted': self.features_unwanted,
            'urgency_level': self.urgency_level,
            'confidence': self.confidence,
            'parsed_at': self.parsed_at,
            'source': self.source,
        }

@dataclass
class PortfoyRecord:
    """
    PORTFÖY (İlan / Property Listing)
    Satılık/Kiralık mülk temsil eder
    """
    
    portfoy_id: str  # Unique identifier
    title: str = ""  # İlan başlığı
    
    # Temel bilgiler
    property_type: PropertyType = PropertyType.UNKNOWN
    transaction_type: TransactionType = TransactionType.UNKNOWN
    
    # Lokasyon
    city: str = "ANKARA"
    district: str = ""
    neighborhood: str = ""
    location_confidence: float = 0.5
    
    # Finansal
    price: Optional[float] = None
    price_text: str = ""
    
    # Fizik özellikleri
    rooms: Optional[str] = None
    area: Optional[float] = None
    
    # Danışman bilgileri
    consultant_name: str = ""
    office: str = ""
    phone: Optional[str] = None
    
    # Kaynaklar
    source_url: str = ""
    source: str = "whatsapp"  # whatsapp, cb.com.tr, sahibinden, vb
    
    # Metadata
    confidence: float = 0.0  # Parser güven puanı
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    features: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization validation"""
        if not self.portfoy_id:
            self.portfoy_id = f"portfoy_{hash(self.title[:50])}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'portfoy_id': self.portfoy_id,
            'title': self.title,
            'property_type': self.property_type.value,
            'transaction_type': self.transaction_type.value,
            'city': self.city,
            'district': self.district,
            'neighborhood': self.neighborhood,
            'location_confidence': self.location_confidence,
            'price': self.price,
            'price_text': self.price_text,
            'rooms': self.rooms,
            'area': self.area,
            'consultant_name': self.consultant_name,
            'office': self.office,
            'phone': self.phone,
            'source_url': self.source_url,
            'source': self.source,
            'confidence': self.confidence,
            'parsed_at': self.parsed_at,
            'features': self.features,
        }

# ═══════════════════════════════════════════════════════════════════════════
# TURKISH NLP PATTERNS & KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════

class TurkishNLPPatterns:
    """Turkish language NLP patterns for real estate"""
    
    # Property types
    PROPERTY_TYPES = {
        r'\b(daire|flat|apartment|apt)\b': PropertyType.DAIRE,
        r'\b(villa|müstakil|ev|house)\b': PropertyType.VILLA,
        r'\b(ofis|office|büro|iş yeri)\b': PropertyType.OFIS,
        r'\b(arsa|land|arsası)\b': PropertyType.ARSA,
        r'\b(komerce|ticari|commercial)\b': PropertyType.KOMERCE,
        r'\b(depo|warehouse|depo|storage)\b': PropertyType.DEPO,
    }
    
    # Transaction types
    TRANSACTION_TYPES = {
        r'\b(satılık|satilik|sale|for sale|satış)\b': TransactionType.SATILIK,
        r'\b(kiralık|kiralik|rental|rent|kira)\b': TransactionType.KIRALIK,
        r'\b(takası|takasli|exchange|takas)\b': TransactionType.TAKASLI,
        r'\b(arıyor|arayan|ariyorum|arayış|searching|isteniyor)\b': TransactionType.ARANIYOR,
    }
    
    # Districts (Ankara focus)
    DISTRICTS = {
        'çankaya': r'(?:çankaya|cankaya)',
        'keçiören': r'(?:keçiören|kecior)',
        'yenimahalle': r'(?:yenimahalle|yeni mahalle)',
        'mamak': r'(?:mamak)',
        'altındağ': r'(?:altındağ|altindag)',
        'çubuk': r'(?:çubuk|cubuk)',
        'pursaklar': r'(?:pursaklar)',
        'sincan': r'(?:sincan)',
        'etimesgut': r'(?:etimesgut)',
        'gölbaşı': r'(?:gölbaşı|golbasi)',
        'elvankent': r'(?:elvankent)',
        'incek': r'(?:incek)',
        'oran': r'(?:oran|oran şehri)',
    }
    
    # Neighborhoods (common in Ankara)
    NEIGHBORHOODS = {
        'çıkrıkçı': r'(?:çıkrıkçı|cikrikci)',
        'kızılay': r'(?:kızılay|kizilay)',
        'tunalı': r'(?:tunalı|tunali)',
        'çayyolu': r'(?:çayyolu|cayyolu)',
        'bağlıca': r'(?:bağlıca|baglica)',
        'yıldız': r'(?:yıldız|yildiz)',
        'demetevler': r'(?:demetevler)',
        'elvankent': r'(?:elvankent)',
        'yaşamkent': r'(?:yaşamkent|yasamkent)',
        'alacaatlı': r'(?:alacaatlı|alacatli)',
    }
    
    # Features
    FEATURES = {
        'balkon': r'(?:balkon)',
        'teras': r'(?:teras|terrace)',
        'asansör': r'(?:asansör|asansor)',
        'garaj': r'(?:garaj|garage|kapalı garaj)',
        'park': r'(?:park|parking)',
        'havuz': r'(?:havuz|pool)',
        'evin bahçesi': r'(?:bahçe|bahcesi)',
        'jeneratör': r'(?:jeneratör|jenerator)',
        'doğalgaz': r'(?:doğalgaz|dogalgaz)',
        'kombi': r'(?:kombi)',
        'asansörlü': r'(?:asansörlü|asansorlu)',
        'site içinde': r'(?:site içinde|site icinde)',
    }

# ═══════════════════════════════════════════════════════════════════════════
# PARSER CLASS
# ═══════════════════════════════════════════════════════════════════════════

class WhatsAppCBParser:
    """
    Coldwell Banker WhatsApp grup mesajlarını parse et
    ARAYIŞ ve PORTFÖY kayıtlarını ayıkla
    """
    
    def __init__(self):
        """Initialize parser"""
        self.patterns = TurkishNLPPatterns()
        self.arayis_count = 0
        self.portfoy_count = 0
    
    def parse_file(self, filepath: str) -> Tuple[List[ArayisRecord], List[PortfoyRecord]]:
        """
        Parse WhatsApp TXT dosyasını oku ve arayış/portföy kayıtlarını ayıkla
        
        Args:
            filepath: WhatsApp TXT dosyasının yolu
            
        Returns:
            (arayis_list, portfoy_list)
        """
        
        logger.info(f"📂 Parsing WhatsApp file: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"❌ Error reading file: {e}")
            return [], []
        
        # Split by messages
        messages = self._extract_messages(content)
        logger.info(f"   Found {len(messages)} messages")
        
        arayislar = []
        portfoyler = []
        
        for msg in messages:
            # Check if this is ARAYIŞ (search request)
            if self._is_arayis(msg['text']):
                arayis = self._parse_arayis(msg)
                if arayis.confidence > 0.3:  # Minimum confidence
                    arayislar.append(arayis)
                    self.arayis_count += 1
            
            # Check if this is PORTFÖY (listing from group)
            else:
                portfoy = self._parse_portfoy(msg)
                if portfoy.confidence > 0.3:  # Minimum confidence
                    portfoyler.append(portfoy)
                    self.portfoy_count += 1
        
        logger.info(f"✅ Parsing complete:")
        logger.info(f"   - ARAYIŞ: {self.arayis_count}")
        logger.info(f"   - PORTFÖY: {self.portfoy_count}\n")
        
        return arayislar, portfoyler
    
    def _extract_messages(self, content: str) -> List[Dict]:
        """
        WhatsApp TXT içeriğinden mesajları ayıkla
        Format: "DATE TIME - SENDER: MESSAGE"
        """
        
        messages = []
        
        # WhatsApp message pattern: "date time - sender: text"
        # Handle both regular and system messages
        pattern = r'(\d+\.\d+\.\d+\s+\d+:\d+)\s*-\s*([^:]+?):\s*(.+?)(?=\d+\.\d+\.\d+\s+\d+:\d+\s*-|$)'
        
        matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            timestamp = match.group(1)
            sender = match.group(2).strip()
            text = match.group(3).strip()
            
            # Skip system messages (ekledi, silindi, vb)
            if any(skip in text.lower() for skip in ['ekledi', 'silindi', 'ayrıldı', 'media']):
                continue
            
            messages.append({
                'timestamp': timestamp,
                'sender': sender,
                'text': text,
            })
        
        return messages
    
    def _is_arayis(self, text: str) -> bool:
        """Mesajın ARAYIŞ (search request) olup olmadığını kontrol et"""
        
        arayis_keywords = [
            'arayış', 'arayiş', 'arayıyor', 'arayiyor', 'araniyor',
            'arıyor', 'aranıyor', 'searching', 'aranıyor', 'arayışımız',
            'arayışımız', 'arayışı var', 'arayışımız var', 'isteriz',
            'istiyoruz', 'ariyorum', 'krem arayiş'
        ]
        
        text_lower = text.lower()
        
        # Check for explicit ARAYIŞ marker
        if 'arayiş' in text_lower or 'arayış' in text_lower:
            return True
        
        # Check for arayış keywords
        for keyword in arayis_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def _parse_arayis(self, msg: Dict) -> ArayisRecord:
        """ARAYIŞ mesajını parse et"""
        
        text = msg['text']
        sender = msg.get('sender', '')
        
        arayis = ArayisRecord(
            arayis_id=f"arayis_{hash(text[:50])}",
            sender=sender,
            message_text=text,
        )
        
        # Extract phone number
        phone_match = re.search(r'(\+90\s?\d{10}|\+90\d{10}|0\d{10})', text)
        if phone_match:
            arayis.phone = phone_match.group(1)
        
        # Extract districts
        arayis.districts = self._extract_districts(text)
        
        # Extract property types
        arayis.property_types = self._extract_property_types(text)
        
        # Extract transaction type
        arayis.transaction_type = self._extract_transaction_type(text)
        
        # Extract budget
        arayis.budget_min, arayis.budget_max = self._extract_budget(text)
        
        # Extract rooms
        arayis.rooms = self._extract_rooms(text)
        
        # Extract features
        arayis.features_wanted = self._extract_features(text)
        
        # Detect urgency
        arayis.urgency_level = self._detect_urgency(text)
        
        # Calculate confidence
        arayis.confidence = self._calculate_arayis_confidence(arayis)
        
        return arayis
    
    def _parse_portfoy(self, msg: Dict) -> PortfoyRecord:
        """PORTFÖY mesajını parse et"""
        
        text = msg['text']
        sender = msg.get('sender', '')
        
        portfoy = PortfoyRecord(
            portfoy_id=f"portfoy_{hash(text[:50])}",
            title=text[:100],
            source='whatsapp',
            consultant_name=sender,
        )
        
        # Extract property type
        portfoy.property_type = self._extract_property_types(text)[0] if self._extract_property_types(text) else PropertyType.UNKNOWN
        
        # Extract transaction type
        portfoy.transaction_type = self._extract_transaction_type(text)
        
        # Extract location
        districts = self._extract_districts(text)
        if districts:
            portfoy.district = districts[0]
        
        # Extract price
        portfoy.price, portfoy.price_text = self._extract_price(text)
        
        # Extract rooms
        portfoy.rooms = self._extract_rooms(text)[0] if self._extract_rooms(text) else None
        
        # Extract area
        portfoy.area = self._extract_area(text)
        
        # Extract features
        portfoy.features = self._extract_features(text)
        
        # Extract URL if exists
        url_match = re.search(r'https?://[^\s]+', text)
        if url_match:
            portfoy.source_url = url_match.group(0)
        
        # Calculate confidence
        portfoy.confidence = self._calculate_portfoy_confidence(portfoy)
        
        return portfoy
    
    def _extract_districts(self, text: str) -> List[str]:
        """İlçeleri çıkart"""
        
        districts = []
        text_lower = text.lower()
        
        for district_name, pattern in self.patterns.DISTRICTS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                districts.append(district_name.upper())
        
        return districts
    
    def _extract_property_types(self, text: str) -> List[PropertyType]:
        """Emlak türlerini çıkart"""
        
        types = []
        text_lower = text.lower()
        
        for pattern, prop_type in self.patterns.PROPERTY_TYPES.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                if prop_type not in types:
                    types.append(prop_type)
        
        return types
    
    def _extract_transaction_type(self, text: str) -> TransactionType:
        """İşlem türünü çıkart (Satılık/Kiralık)"""
        
        text_lower = text.lower()
        
        for pattern, trans_type in self.patterns.TRANSACTION_TYPES.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return trans_type
        
        return TransactionType.UNKNOWN
    
    def _extract_budget(self, text: str) -> Tuple[Optional[float], Optional[float]]:
        """Bütçeyi çıkart"""
        
        # Look for price patterns: "5 milyon", "5.000.000", "5000000 ₺"
        prices = []
        
        # Pattern 1: "X milyon"
        milyon_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:milyon|million|m(?:\s|$))'
        matches = re.finditer(milyon_pattern, text, re.IGNORECASE)
        for match in matches:
            price_str = match.group(1).replace(',', '.')
            prices.append(float(price_str) * 1_000_000)
        
        # Pattern 2: "X.XXX.XXX" or "X,XXX,XXX"
        number_pattern = r'(\d+(?:[.,]\d{3})+)'
        matches = re.finditer(number_pattern, text)
        for match in matches:
            price_str = match.group(1).replace('.', '').replace(',', '')
            try:
                prices.append(float(price_str))
            except:
                pass
        
        # Pattern 3: "X₺" or "X TL"
        tl_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:₺|TL|tl)'
        matches = re.finditer(tl_pattern, text)
        for match in matches:
            price_str = match.group(1).replace(',', '.')
            prices.append(float(price_str))
        
        if prices:
            prices = sorted(set(prices))
            if len(prices) == 1:
                return prices[0], prices[0]
            else:
                return min(prices), max(prices)
        
        return None, None
    
    def _extract_rooms(self, text: str) -> List[str]:
        """Oda sayılarını çıkart (2+1, 3+1, vb)"""
        
        rooms = []
        pattern = r'(\d+\+\d+)'
        
        matches = re.finditer(pattern, text)
        for match in matches:
            rooms.append(match.group(1))
        
        return list(set(rooms))
    
    def _extract_area(self, text: str) -> Optional[float]:
        """Alanı çıkart (m²)"""
        
        # Pattern: "120 m²" or "120 m2" or "120 metrekare"
        area_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:m²|m2|metrekare|mt|mkare)'
        
        match = re.search(area_pattern, text, re.IGNORECASE)
        if match:
            area_str = match.group(1).replace(',', '.')
            try:
                return float(area_str)
            except:
                return None
        
        return None
    
    def _extract_features(self, text: str) -> List[str]:
        """Özellikleri çıkart"""
        
        features = []
        text_lower = text.lower()
        
        for feature_name, pattern in self.patterns.FEATURES.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                if feature_name not in features:
                    features.append(feature_name)
        
        return features
    
    def _detect_urgency(self, text: str) -> int:
        """Aciliyet seviyesini algıla (1-5)"""
        
        text_lower = text.lower()
        urgency = 1
        
        # High urgency keywords
        high_keywords = ['acil', 'urgent', 'çok acil', 'müsait', 'hemen', 'şimdi', 'bugün']
        medium_keywords = ['kısa sürede', 'yakında', 'ay sonuna']
        
        for keyword in high_keywords:
            if keyword in text_lower:
                urgency = max(urgency, 5)
        
        for keyword in medium_keywords:
            if keyword in text_lower:
                urgency = max(urgency, 3)
        
        return urgency
    
    def _calculate_arayis_confidence(self, arayis: ArayisRecord) -> float:
        """ARAYIŞ confidence puanını hesapla"""
        
        confidence = 0.0
        
        # Has districts
        if arayis.districts:
            confidence += 0.25
        
        # Has property types
        if arayis.property_types:
            confidence += 0.25
        
        # Has budget
        if arayis.budget_min or arayis.budget_max:
            confidence += 0.2
        
        # Has rooms
        if arayis.rooms:
            confidence += 0.15
        
        # Has features
        if arayis.features_wanted:
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _calculate_portfoy_confidence(self, portfoy: PortfoyRecord) -> float:
        """PORTFÖY confidence puanını hesapla"""
        
        confidence = 0.0
        
        # Has property type
        if portfoy.property_type != PropertyType.UNKNOWN:
            confidence += 0.25
        
        # Has price
        if portfoy.price:
            confidence += 0.25
        
        # Has rooms
        if portfoy.rooms:
            confidence += 0.2
        
        # Has district
        if portfoy.district:
            confidence += 0.15
        
        # Has features
        if portfoy.features:
            confidence += 0.15
        
        return min(confidence, 1.0)

# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def parse_scraper_json(json_data: Dict) -> List[PortfoyRecord]:
    """
    a.py scraper'ın JSON çıktısını parse et
    
    Args:
        json_data: Scraper JSON dictionary
        
    Returns:
        PortfoyRecord listesi
    """
    
    portfoyler = []
    
    for listing in json_data.get('listings', []):
        portfoy = PortfoyRecord(
            portfoy_id=f"scraper_{listing.get('id', 'unknown')}",
            title=listing.get('title', ''),
            property_type=_parse_property_type(listing.get('type', '')),
            transaction_type=(
                TransactionType.KIRALIK if any(
                    w in f"{listing.get('transaction_type', '')} {listing.get('type', '')} {listing.get('status', '')} {listing.get('title', '')} {listing.get('url', '')}".replace('İ', 'i').replace('I', 'ı').lower()
                    for w in ['kiralık', 'kiralik', 'kira', 'rent']
                ) else TransactionType.SATILIK
            ),
            city=listing.get('city', 'ANKARA'),
            district=listing.get('district', ''),
            neighborhood=listing.get('neighborhood', ''),
            price=_parse_price_from_str(listing.get('price', '')),
            price_text=listing.get('price', ''),
            rooms=listing.get('rooms', None),
            area=_parse_area_from_str(listing.get('area', '')),
            consultant_name=listing.get('consultant', ''),
            office=listing.get('office', ''),
            source_url=listing.get('url', ''),
            source='cb.com.tr',
            confidence=0.95,  # Scraper verileri yüksek güven
        )
        
        portfoyler.append(portfoy)
    
    return portfoyler

def _parse_property_type(type_str: str) -> PropertyType:
    """String'den PropertyType parse et"""
    
    type_lower = type_str.lower()
    
    if 'daire' in type_lower or 'apartment' in type_lower:
        return PropertyType.DAIRE
    elif 'villa' in type_lower:
        return PropertyType.VILLA
    elif 'ofis' in type_lower or 'office' in type_lower:
        return PropertyType.OFIS
    elif 'arsa' in type_lower:
        return PropertyType.ARSA
    else:
        return PropertyType.UNKNOWN

def _parse_price_from_str(price_str: str) -> Optional[float]:
    """Fiyat string'ini float'a çevir"""
    
    # Remove currency symbols
    price_clean = price_str.replace('₺', '').replace('TL', '').strip()
    
    # Remove dots (thousands separator in Turkish format)
    price_clean = price_clean.replace('.', '')
    
    try:
        return float(price_clean)
    except:
        return None

def _parse_area_from_str(area_str: str) -> Optional[float]:
    """Alan string'ini float'a çevir"""
    
    # Remove m² and similar
    area_clean = area_str.replace('m²', '').replace('m2', '').replace('brüt', '').strip()
    
    try:
        return float(area_clean)
    except:
        return None

# ═══════════════════════════════════════════════════════════════════════════
# MAIN / EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example usage
    parser = WhatsAppCBParser()
    
    # Parse WhatsApp
    arayislar, portfoyler = parser.parse_file(
        "_Coldwell_Banker_Ankara_ile_WhatsApp_Sohbeti.txt"
    )
    
    print(f"\n✅ Parsed {len(arayislar)} ARAYIŞ requests")
    print(f"✅ Parsed {len(portfoyler)} PORTFÖY listings\n")
    
    # Print sample
    if arayislar:
        print("📍 Sample ARAYIŞ:")
        print(f"   ID: {arayislar[0].arayis_id}")
        print(f"   Sender: {arayislar[0].sender}")
        print(f"   Districts: {arayislar[0].districts}")
        print(f"   Budget: {arayislar[0].budget_min} - {arayislar[0].budget_max}")
        print(f"   Confidence: {arayislar[0].confidence:.2f}\n")
    
    if portfoyler:
        print("📍 Sample PORTFÖY:")
        print(f"   ID: {portfoyler[0].portfoy_id}")
        print(f"   Title: {portfoyler[0].title[:50]}")
        print(f"   District: {portfoyler[0].district}")
        print(f"   Price: {portfoyler[0].price}")
        print(f"   Confidence: {portfoyler[0].confidence:.2f}\n")
