#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 AI-Based Matcher Engine (Ollama/Qwen2.5)
=============================================
Arayış ve Portföyleri Ollama/Qwen2.5 7b ile eşleştir
Natural language understanding + scoring algorithm
"""

import requests
import json
import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from matcher_parser import (
    ArayisRecord, PortfoyRecord, WhatsAppCBParser
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"  # Qwen 2.5 7B
REQUEST_TIMEOUT = 30

# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MatchReason:
    """Eşleştirme nedeni"""
    category: str  # price_match, rooms_match, location_match, etc
    score: float  # 0-1
    explanation: str  # İnsan tarafından okunabilir açıklama

@dataclass
class Match:
    """Arayış-Portföy Eşleştirmesi"""
    arayis_id: str
    portfoy_id: str
    overall_score: float  # 0-100
    confidence: float  # 0-1 (modelin ne kadar emin olduğu)
    
    # Scoring breakdown
    price_score: float
    rooms_score: float
    location_score: float
    type_score: float
    features_score: float
    urgency_score: float
    
    # Explanations
    reasons: List[MatchReason]
    
    # Metadata
    ai_analysis: str = ""  # Qwen2.5'den gelen detaylı analiz
    recommendation: str = ""  # Kime ulaştır (arayıştaki kişi)
    contact_info: Optional[str] = None  # İletişim
    
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'arayis_id': self.arayis_id,
            'portfoy_id': self.portfoy_id,
            'overall_score': self.overall_score,
            'confidence': self.confidence,
            'price_score': self.price_score,
            'rooms_score': self.rooms_score,
            'location_score': self.location_score,
            'type_score': self.type_score,
            'features_score': self.features_score,
            'urgency_score': self.urgency_score,
            'reasons': [asdict(r) for r in self.reasons],
            'ai_analysis': self.ai_analysis,
            'recommendation': self.recommendation,
            'contact_info': self.contact_info,
            'timestamp': self.timestamp,
        }

# ═══════════════════════════════════════════════════════════════════════════
# MATCHER ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class OllamaMatcher:
    """Ollama/Qwen2.5 tabanlı matcher"""
    
    def __init__(self):
        self.client = None
        self.matches: List[Match] = []
        self._check_ollama_connection()
    
    def _check_ollama_connection(self):
        """Ollama bağlantısını kontrol et"""
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama bağlantısı başarılı")
                return True
        except:
            pass
        
        logger.warning("⚠️  Ollama bağlantısı yok - fallback scoring kullanılacak")
        return False
    
    def match_arayis_portfoy(self, arayis: ArayisRecord, 
                            portfoy: PortfoyRecord) -> Optional[Match]:
        """Tek arayış-portföy eşleştirmesi yap"""
        
        # Basic scoring
        price_score = self._score_price(arayis, portfoy)
        rooms_score = self._score_rooms(arayis, portfoy)
        location_score = self._score_location(arayis, portfoy)
        type_score = self._score_type(arayis, portfoy)
        features_score = self._score_features(arayis, portfoy)
        urgency_score = self._score_urgency(arayis, portfoy)
        
        # Weighted overall score
        overall_score = (
            price_score * 0.25 +
            rooms_score * 0.25 +
            location_score * 0.20 +
            type_score * 0.15 +
            features_score * 0.10 +
            urgency_score * 0.05
        )
        
        # Skip if below threshold
        if overall_score < 0.3:
            return None
        
        # AI Analysis (Qwen2.5)
        ai_analysis = self._analyze_with_qwen(arayis, portfoy, overall_score)
        
        # Compile reasons
        reasons = self._compile_reasons(
            price_score, rooms_score, location_score, 
            type_score, features_score, urgency_score
        )
        
        # Recommendation
        recommendation = self._generate_recommendation(arayis, portfoy)
        
        match = Match(
            arayis_id=arayis.id,
            portfoy_id=portfoy.id,
            overall_score=overall_score * 100,  # 0-100
            confidence=self._calculate_confidence(arayis, portfoy),
            price_score=price_score,
            rooms_score=rooms_score,
            location_score=location_score,
            type_score=type_score,
            features_score=features_score,
            urgency_score=urgency_score,
            reasons=reasons,
            ai_analysis=ai_analysis,
            recommendation=recommendation,
            contact_info=arayis.phone or arayis.name,
        )
        
        return match
    
    def match_all(self, arayislar: List[ArayisRecord], 
                  portfoyler: List[PortfoyRecord]) -> List[Match]:
        """Tüm arayış-portföy kombinasyonlarını eşleştir"""
        
        logger.info(f"🔄 Matching başlatılıyor...")
        logger.info(f"   Arayış: {len(arayislar)}")
        logger.info(f"   Portföy: {len(portfoyler)}")
        
        matches = []
        
        for i, arayis in enumerate(arayislar):
            for j, portfoy in enumerate(portfoyler):
                match = self.match_arayis_portfoy(arayis, portfoy)
                
                if match:
                    matches.append(match)
                    logger.debug(f"   ✅ Match: {arayis.id} ← → {portfoy.id} "
                               f"({match.overall_score:.1f}%)")
            
            if (i + 1) % 5 == 0:
                logger.info(f"   {i + 1}/{len(arayislar)} arayış işlendi...")
        
        # Sort by score (highest first)
        matches.sort(key=lambda m: m.overall_score, reverse=True)
        self.matches = matches
        
        logger.info(f"✅ Matching tamamlandı: {len(matches)} eşleştirme bulundu")
        
        return matches
    
    # ─────────────────────────────────────────────────────────────────────
    # SCORING FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────
    
    def _score_price(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Fiyat uyumluluğunu puanla (0-1)"""
        
        # Arayış fiyat aralığı
        min_arayis = arayis.price_range.min_price
        max_arayis = arayis.price_range.max_price
        portfoy_price = portfoy.price
        
        # No price info
        if not min_arayis or not portfoy_price:
            return 0.5  # Neutral
        
        # Perfect match
        if min_arayis <= portfoy_price <= max_arayis:
            return 1.0
        
        # Slightly below/above
        if min_arayis * 0.8 <= portfoy_price <= max_arayis * 1.2:
            return 0.8
        
        # Way off
        return max(0.0, 1.0 - abs(portfoy_price - min_arayis) / min_arayis)
    
    def _score_rooms(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Oda sayısı uyumluluğunu puanla"""
        
        desired_rooms = arayis.property.rooms
        portfoy_rooms = portfoy.rooms
        
        if not desired_rooms or not portfoy_rooms:
            return 0.5  # Neutral
        
        # Exact match
        if portfoy_rooms in desired_rooms:
            return 1.0
        
        # Partial match (e.g., 3+1 matches 2+1 or 4+1)
        try:
            desired_nums = [int(x) for x in desired_rooms[0].split('+')]
            portfoy_nums = [int(x) for x in portfoy_rooms.split('+')]
            
            # Check if within 1 room
            if abs(portfoy_nums[0] - desired_nums[0]) <= 1:
                return 0.8
            
            return 0.3
        except:
            return 0.0
    
    def _score_location(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Lokasyon uyumluluğunu puanla"""
        
        # Arayış lokasyonu
        desired_district = arayis.location.district
        desired_neighborhoods = arayis.location.neighborhoods
        
        portfoy_district = portfoy.district
        
        # No preference
        if not desired_district and not desired_neighborhoods:
            return 0.5  # Neutral
        
        # Exact district match
        if desired_district and desired_district == portfoy_district:
            return 1.0
        
        # Neighborhood match
        if desired_neighborhoods and portfoy_district in desired_neighborhoods:
            return 0.9
        
        # No match
        return 0.0
    
    def _score_type(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Emlak türü uyumluluğunu puanla"""
        
        desired_types = arayis.property.property_type
        portfoy_type = portfoy.property_type
        
        if not desired_types or not portfoy_type:
            return 0.5  # Neutral
        
        # Exact match
        if portfoy_type in desired_types:
            return 1.0
        
        # Close match (Ev Ofis ~ Ofis)
        similar_types = {
            'Daire': ['Dubleks', 'Apartman'],
            'Ofis': ['Ev Ofis', 'Showroom'],
            'Villa': ['Müstakil', 'Komple Bina'],
        }
        
        for key, values in similar_types.items():
            if portfoy_type in values and key in desired_types:
                return 0.7
        
        return 0.0
    
    def _score_features(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Özelliklerin eşleşme puanı"""
        
        desired_features = set(arayis.property.features)
        portfoy_features = set(portfoy.features)
        
        if not desired_features:
            return 0.5  # Neutral
        
        if not portfoy_features:
            return 0.0  # No features listed
        
        # Intersection over union
        intersection = len(desired_features & portfoy_features)
        union = len(desired_features | portfoy_features)
        
        return intersection / union if union > 0 else 0.0
    
    def _score_urgency(self, arayis: ArayisRecord, portfoy: PortfoyRecord) -> float:
        """Aciliyet uyumluluğunu puanla"""
        
        # Acil arayış → acil satılık iyi, normal de OK
        if arayis.urgency == "acil":
            return 1.0  # Any listing helps
        
        # Hafif arayış → preferred normal listings
        return 0.8  # OK
    
    # ─────────────────────────────────────────────────────────────────────
    # AI ANALYSIS (QWEN2.5)
    # ─────────────────────────────────────────────────────────────────────
    
    def _analyze_with_qwen(self, arayis: ArayisRecord, 
                          portfoy: PortfoyRecord, score: float) -> str:
        """Qwen2.5 ile detaylı analiz yap"""
        
        try:
            # Prepare prompt
            prompt = self._build_analysis_prompt(arayis, portfoy, score)
            
            # Call Ollama
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    'model': OLLAMA_MODEL,
                    'prompt': prompt,
                    'stream': False,
                    'temperature': 0.3,  # Deterministic
                },
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                logger.warning(f"⚠️  Ollama API error: {response.status_code}")
                return ""
        
        except requests.exceptions.Timeout:
            logger.warning("⚠️  Ollama timeout - using fallback")
            return ""
        
        except Exception as e:
            logger.warning(f"⚠️  Ollama error: {e}")
            return ""
    
    def _build_analysis_prompt(self, arayis: ArayisRecord, 
                              portfoy: PortfoyRecord, score: float) -> str:
        """Analysis prompt'u oluştur"""
        
        prompt = f"""
EMLAK EŞLEŞTİRME ANALİZİ
========================

ARAYIŞ (Müşteri Talebı):
- Bütçe: ₺{arayis.price_range.min_price:,} - ₺{arayis.price_range.max_price:,}
- Lokasyon: {arayis.location.district or 'Herhangi'} / {', '.join(arayis.location.neighborhoods) or 'Herhangi'}
- Oda: {', '.join(arayis.property.rooms) or 'Herhangi'}
- Tür: {', '.join(arayis.property.property_type) or 'Herhangi'}
- İşlem: {arayis.transaction_type}
- Aciliyet: {arayis.urgency}

PORTFÖY (İlan):
- Fiyat: ₺{portfoy.price:,} (Portföy)
- Oda: {portfoy.rooms}
- Tür: {portfoy.property_type}
- İlçe: {portfoy.district}
- Özellikler: {', '.join(portfoy.features) or 'Yok'}
- İşlem: {portfoy.transaction_type}

MATCHING SKORU: {score*100:.1f}%

Lütfen şu sorulara kısa ve pratik yanıtlar ver (max 3 cümle):
1. Bu eşleştirme neden iyi bir eşleştirme? (Uygun yönler)
2. Var mı eksiklik veya endişe? (Uyumsuz yönler)
3. Müşteriye ne tavsiye edersin?

Sadece Türkçe ve pratik tavsiyeler.
"""
        
        return prompt
    
    # ─────────────────────────────────────────────────────────────────────
    # RESULT COMPILATION
    # ─────────────────────────────────────────────────────────────────────
    
    def _compile_reasons(self, price_score: float, rooms_score: float,
                        location_score: float, type_score: float,
                        features_score: float, urgency_score: float) -> List[MatchReason]:
        """Eşleştirme nedenlerini derle"""
        
        reasons = []
        
        if price_score > 0.7:
            reasons.append(MatchReason(
                category='price_match',
                score=price_score,
                explanation=f'Fiyat aralığı uygun ({price_score*100:.0f}%)'
            ))
        
        if rooms_score > 0.7:
            reasons.append(MatchReason(
                category='rooms_match',
                score=rooms_score,
                explanation=f'Oda sayısı tercihine uygun ({rooms_score*100:.0f}%)'
            ))
        
        if location_score > 0.7:
            reasons.append(MatchReason(
                category='location_match',
                score=location_score,
                explanation=f'Lokasyon tercihine uygun ({location_score*100:.0f}%)'
            ))
        
        if type_score > 0.7:
            reasons.append(MatchReason(
                category='type_match',
                score=type_score,
                explanation=f'Emlak türü uygun ({type_score*100:.0f}%)'
            ))
        
        if features_score > 0.5:
            reasons.append(MatchReason(
                category='features_match',
                score=features_score,
                explanation=f'İstenen özellikleri içeriyor ({features_score*100:.0f}%)'
            ))
        
        # Add concerns
        if price_score < 0.5:
            reasons.append(MatchReason(
                category='price_concern',
                score=price_score,
                explanation=f'⚠️ Fiyat bütçeden yüksek veya düşük'
            ))
        
        if location_score < 0.5:
            reasons.append(MatchReason(
                category='location_concern',
                score=location_score,
                explanation=f'⚠️ Lokasyon tercihten farklı'
            ))
        
        return reasons
    
    def _generate_recommendation(self, arayis: ArayisRecord, 
                                portfoy: PortfoyRecord) -> str:
        """Tavsiye oluştur"""
        
        if arayis.phone:
            return f"📞 {arayis.phone} numarasına ulaş"
        elif arayis.name:
            return f"👤 {arayis.name} ile iletişime geç"
        else:
            return "👥 Arayış sahibi ile iletişime geç"
    
    def _calculate_confidence(self, arayis: ArayisRecord, 
                             portfoy: PortfoyRecord) -> float:
        """Model güvenirliğini hesapla"""
        
        # Base confidence from parsing
        base_confidence = (arayis.confidence + portfoy.confidence) / 2
        
        return min(base_confidence, 0.95)
    
    # ─────────────────────────────────────────────────────────────────────
    # EXPORT & REPORTING
    # ─────────────────────────────────────────────────────────────────────
    
    def export_json(self, filepath: str):
        """Eşleştirmeleri JSON'a kaydet"""
        
        data = {
            'source': 'ollama_matcher',
            'model': OLLAMA_MODEL,
            'matched_at': datetime.now().isoformat(),
            'total_matches': len(self.matches),
            'matches': [m.to_dict() for m in self.matches],
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Matches kaydedildi: {filepath}")
    
    def generate_report(self, filepath: str):
        """Markdown rapor oluştur"""
        
        # Sort by score
        sorted_matches = sorted(self.matches, 
                               key=lambda m: m.overall_score, 
                               reverse=True)
        
        report = f"""# 🤖 AI MATCHER RAPORU

**Model:** {OLLAMA_MODEL}  
**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}  
**Toplam Eşleştirme:** {len(sorted_matches)}

---

## 📊 İSTATİSTİKLER

| Metrik | Değer |
|--------|-------|
| **Toplam Match** | {len(sorted_matches)} |
| **Ortalama Score** | {sum(m.overall_score for m in sorted_matches) / len(sorted_matches) if sorted_matches else 0:.1f}% |
| **Ortalama Confidence** | {sum(m.confidence for m in sorted_matches) / len(sorted_matches) if sorted_matches else 0:.1%} |
| **90+ Score** | {len([m for m in sorted_matches if m.overall_score >= 90])} |

---

## 🏆 TOP 10 EŞLEŞTIRMELER

"""
        
        for i, match in enumerate(sorted_matches[:10], 1):
            report += f"""
### {i}. Match: {match.overall_score:.1f}%

**Arayış ID:** {match.arayis_id}  
**Portföy ID:** {match.portfoy_id}  
**Güven:** {match.confidence:.1%}

**Puanlama Breakdown:**
- Fiyat: {match.price_score*100:.0f}%
- Oda: {match.rooms_score*100:.0f}%
- Lokasyon: {match.location_score*100:.0f}%
- Tür: {match.type_score*100:.0f}%
- Özellikler: {match.features_score*100:.0f}%

**Nedenler:**
"""
            
            for reason in match.reasons:
                report += f"\n- **{reason.category}** ({reason.score*100:.0f}%): {reason.explanation}"
            
            if match.ai_analysis:
                report += f"\n\n**AI Analizi:** {match.ai_analysis}"
            
            report += f"\n\n**Tavsiye:** {match.recommendation}\n"
        
        report += f"""

---

## 🔍 SCORİNG KRİTERLERİ

| Kriter | Ağırlık | Açıklama |
|--------|---------|----------|
| **Fiyat** | 25% | Bütçe uyumluluğu |
| **Oda** | 25% | Oda sayısı eşleşmesi |
| **Lokasyon** | 20% | Tercih edilen bölge |
| **Tür** | 15% | Emlak türü uyumu |
| **Özellikler** | 10% | İstenen özellikleri içerme |
| **Aciliyet** | 5% | Acil satılık tercihine uyum |

---

**Rapor Oluşturma Tarihi:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}  
**Status:** ✅ Hazır
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"✅ Rapor kaydedildi: {filepath}")
    
    def get_top_matches_for_arayis(self, arayis_id: str, 
                                   top_n: int = 5) -> List[Match]:
        """Belirli arayış için top N match'i döndür"""
        
        arayis_matches = [m for m in self.matches if m.arayis_id == arayis_id]
        arayis_matches.sort(key=lambda m: m.overall_score, reverse=True)
        
        return arayis_matches[:top_n]

# ═══════════════════════════════════════════════════════════════════════════
# MAIN (Testing)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    # Parse WhatsApp data
    parser = WhatsAppCBParser()
    arayislar, portfoyler = parser.parse_file(
        "Coldwell_Banker_Ankara_ile_WhatsApp_Sohbeti.txt"
    )
    
    print(f"\n{'='*70}")
    print(f"🤖 OLLAMA MATCHER TEST")
    print(f"{'='*70}\n")
    
    # Create matcher
    matcher = OllamaMatcher()
    
    # Run matching
    matches = matcher.match_all(arayislar, portfoyler)
    
    # Results
    print(f"\n{'='*70}")
    print(f"✅ MATCHING TAMAMLANDI")
    print(f"{'='*70}")
    print(f"📊 Toplam Match: {len(matches)}")
    
    if matches:
        top_match = matches[0]
        print(f"\n🏆 EN İYİ MATCH:")
        print(f"   Score: {top_match.overall_score:.1f}%")
        print(f"   Confidence: {top_match.confidence:.1%}")
        print(f"   Tavsiye: {top_match.recommendation}")
    
    # Export
    matcher.export_json("matches_results.json")
    matcher.generate_report("matches_report.md")
    
    print(f"\n✅ Sonuçlar kaydedildi!")
