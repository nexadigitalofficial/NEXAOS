#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔗 Matcher Orchestrator
=======================
a.py Scraper + WhatsApp Parser + Ollama Engine entegrasyonu
Tüm matching pipeline'ı yönetir
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from matcher_parser import WhatsAppCBParser, ArayisRecord, PortfoyRecord
from matcher_engine import OllamaMatcher, Match

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handlers
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class MatcherOrchestrator:
    """
    Tüm matching pipeline'ı yönetir:
    1. Scraper output (JSON) → parse
    2. WhatsApp TXT → parse
    3. Match with AI
    4. Generate reports
    """
    
    def __init__(self, output_dir: str = "matcher_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.listings = []  # Scraped listings (from a.py)
        self.arayislar = []  # Parsed from WhatsApp
        self.portfoyler = []  # Parsed from WhatsApp
        self.matches = []  # Final matches
        
        logger.info(f"🔗 Matcher Orchestrator başlatıldı")
        logger.info(f"📁 Output: {self.output_dir.absolute()}")
    
    # ─────────────────────────────────────────────────────────────────────
    # PIPELINE METHODS
    # ─────────────────────────────────────────────────────────────────────
    
    def run_full_pipeline(self, 
                         listings_json: str,
                         whatsapp_txt: str) -> Tuple[List[Match], Dict]:
        """
        Tam matching pipeline'ını çalıştır
        
        Args:
            listings_json: a.py scraper output (listings_*.json)
            whatsapp_txt: WhatsApp grup mesajları (.txt)
        
        Returns:
            (matches, statistics)
        """
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 MATCHING PIPELINE BAŞLANIYOR")
        logger.info(f"{'='*70}\n")
        
        # Step 1: Load listings from scraper
        logger.info(f"📥 Step 1: Scraper output'u yükle...")
        self._load_listings(listings_json)
        
        # Step 2: Parse WhatsApp
        logger.info(f"\n📥 Step 2: WhatsApp mesajlarını parse et...")
        self._parse_whatsapp(whatsapp_txt)
        
        # Step 3: Create portföy from listings (CB.com.tr ilanları)
        logger.info(f"\n📥 Step 3: Scraped listings'i portföy'e dönüştür...")
        self._create_portfoy_from_listings()
        
        # Step 4: Combine with manually entered portföy
        logger.info(f"\n📊 Portföy kaynakları:")
        logger.info(f"   - Scraped (CB.com.tr): {len([p for p in self.portfoyler if p.source == 'cb_scraper'])}")
        logger.info(f"   - WhatsApp grup: {len([p for p in self.portfoyler if p.source == 'whatsapp'])}")
        
        # Step 5: Run matching
        logger.info(f"\n🤖 Step 4: AI matching'i çalıştır...")
        self.matches = self._run_matching()
        
        # Step 6: Generate outputs
        logger.info(f"\n📊 Step 5: Raporlar oluştur...")
        stats = self._generate_outputs()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ PIPELINE TAMAMLANDI")
        logger.info(f"{'='*70}")
        logger.info(f"📊 Toplam Match: {len(self.matches)}")
        logger.info(f"📁 Output: {self.output_dir}\n")
        
        return self.matches, stats
    
    def _load_listings(self, filepath: str):
        """Scraper output JSON'ını yükle"""
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.listings = data.get('listings', [])
            logger.info(f"✅ {len(self.listings)} ilan yüklendi")
            logger.info(f"   Kaynak: {data.get('source', 'unknown')}")
            logger.info(f"   Tarih: {data.get('scraped_at', 'unknown')}")
        
        except FileNotFoundError:
            logger.error(f"❌ Dosya bulunamadı: {filepath}")
            raise
        
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse hatası: {e}")
            raise
    
    def _parse_whatsapp(self, filepath: str):
        """WhatsApp mesajlarını parse et"""
        
        try:
            parser = WhatsAppCBParser()
            arayislar, portfoyler = parser.parse_file(filepath)
            
            self.arayislar = arayislar
            self.portfoyler = portfoyler
            
            logger.info(f"✅ {len(arayislar)} ARAYIŞ parsed")
            logger.info(f"✅ {len(portfoyler)} PORTFÖY (WhatsApp) parsed")
        
        except FileNotFoundError:
            logger.error(f"❌ Dosya bulunamadı: {filepath}")
            raise
    
    def _create_portfoy_from_listings(self):
        """Scraped listings'i PortfoyRecord'a dönüştür"""
        
        from matcher_parser import PortfoyRecord
        
        for listing in self.listings:
            try:
                # Extract data
                price_str = listing.get('price', '').replace('₺', '').replace('.', '')
                price = int(price_str) if price_str else None
                
                # Create record
                record = PortfoyRecord(
                    id=f"cb_scrape_{listing.get('id', 'unknown')}",
                    phone=None,
                    name=listing.get('consultant', 'CB VIP'),
                    text=listing.get('title', ''),
                    timestamp=listing.get('scraped_at', datetime.now().isoformat()),
                    listing_url=listing.get('url', None),
                    title=listing.get('title', ''),
                    price=price,
                    price_text=listing.get('price', ''),
                    rooms=listing.get('rooms', None),
                    property_type=listing.get('type', None),
                    district=listing.get('district', None),
                    features=[],  # Not available in scraper
                    transaction_type=(
                        'kiralık' if any(
                            w in f"{listing.get('transaction_type', '')} {listing.get('type', '')} {listing.get('status', '')} {listing.get('title', '')} {listing.get('url', '')}".replace('İ', 'i').replace('I', 'ı').lower()
                            for w in ['kiralık', 'kiralik', 'kira', 'rent']
                        ) else 'satılık'
                    ),
                    confidence=0.9,  # High confidence (structured data)
                    source='cb_scraper',
                )
                
                self.portfoyler.append(record)
            
            except Exception as e:
                logger.warning(f"⚠️  Listing dönüştürme hatası: {e}")
    
    def _run_matching(self) -> List[Match]:
        """AI matching'i çalıştır"""
        
        matcher = OllamaMatcher()
        matches = matcher.match_all(self.arayislar, self.portfoyler)
        
        # Also store matcher for later use
        self.matcher = matcher
        
        return matches
    
    def _generate_outputs(self) -> Dict:
        """Raporlar ve çıktılar oluştur"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON output
        json_path = self.output_dir / f"matches_{timestamp}.json"
        self.matcher.export_json(str(json_path))
        
        # Markdown report
        md_path = self.output_dir / f"report_{timestamp}.md"
        self.matcher.generate_report(str(md_path))
        
        # Summary report
        summary_path = self.output_dir / f"summary_{timestamp}.md"
        self._generate_summary_report(str(summary_path))
        
        # Statistics
        stats = self._calculate_statistics()
        
        return stats
    
    def _generate_summary_report(self, filepath: str):
        """Özet rapor oluştur"""
        
        report = f"""# 📋 MATCHER ÖZET RAPORU

**Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

---

## 📊 VERİ ÖZET

### Giriş Kaynakları

| Kaynak | Sayı | Not |
|--------|------|-----|
| **Scraped Listings** | {len(self.listings)} | CB.com.tr (a.py scraper) |
| **WhatsApp ARAYIŞ** | {len(self.arayislar)} | Müşteri talepleri |
| **WhatsApp PORTFÖY** | {len([p for p in self.portfoyler if p.source == 'whatsapp'])} | Grup paylaşımları |
| **Total PORTFÖY** | {len(self.portfoyler)} | Scraped + WhatsApp |

### Eşleştirme Sonuçları

| Metrik | Değer |
|--------|-------|
| **Toplam Match** | {len(self.matches)} |
| **Ortalama Score** | {sum(m.overall_score for m in self.matches) / len(self.matches) if self.matches else 0:.1f}% |
| **90+ Score** | {len([m for m in self.matches if m.overall_score >= 90])} |
| **70-89 Score** | {len([m for m in self.matches if 70 <= m.overall_score < 90])} |
| **50-69 Score** | {len([m for m in self.matches if 50 <= m.overall_score < 70])} |

---

## 🏆 TOP 5 MATCHES

"""
        
        top_matches = sorted(self.matches, 
                            key=lambda m: m.overall_score, 
                            reverse=True)[:5]
        
        for i, match in enumerate(top_matches, 1):
            report += f"""
### {i}. {match.overall_score:.1f}%

- **Arayış:** {match.arayis_id}
- **Portföy:** {match.portfoy_id}
- **Güven:** {match.confidence:.1%}
- **Tavsiye:** {match.recommendation}

"""
        
        report += f"""

---

## 📈 MATCHING KALITESI

### Oran Dağılımı

"""
        
        # Create histogram
        ranges = [
            (90, 100, "⭐⭐⭐⭐⭐ Çok İyi"),
            (70, 89, "⭐⭐⭐⭐ İyi"),
            (50, 69, "⭐⭐⭐ Orta"),
            (30, 49, "⭐⭐ Düşük"),
            (0, 29, "⭐ Çok Düşük"),
        ]
        
        for min_score, max_score, label in ranges:
            count = len([m for m in self.matches 
                        if min_score <= m.overall_score < max_score + 1])
            pct = (count / len(self.matches) * 100) if self.matches else 0
            bar = "█" * int(pct / 2)
            report += f"\n{label:25} {count:3d} ({pct:5.1f}%) {bar}"
        
        report += f"""

---

## 🎯 NEXT STEPS

### İçin Öneriler

1. **Top Matches'ı Gözden Geçir**
   - 90+ score olanlar hemen müşteriye ulaştır
   - Qwen2.5 AI analizini kontrol et

2. **Kontakt Yap**
   - ARAYIŞ sahibine (telefon/ad bilgisi ile)
   - PORTFÖY sahibi (emlakçı) ile
   - Tanıştırma yap

3. **Feedback**
   - Başarılı match'ler kaydet
   - Modeli fine-tune et
   - Matching accuracy'i geliştir

### Automation

```bash
# Scheduled matching (cron job)
0 * * * * cd /path/to && python matcher_orchestrator.py run --listings scraper_output/listings_*.json --whatsapp data/cb_group.txt
```

---

**Status:** ✅ Hazır  
**Generated:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"✅ Özet rapor: {Path(filepath).name}")
    
    def _calculate_statistics(self) -> Dict:
        """İstatistikleri hesapla"""
        
        if not self.matches:
            return {
                'total_matches': 0,
                'avg_score': 0,
                'avg_confidence': 0,
            }
        
        scores = [m.overall_score for m in self.matches]
        confidences = [m.confidence for m in self.matches]
        
        return {
            'total_matches': len(self.matches),
            'avg_score': sum(scores) / len(scores),
            'avg_confidence': sum(confidences) / len(confidences),
            'max_score': max(scores),
            'min_score': min(scores),
            'high_quality': len([s for s in scores if s >= 90]),
            'good_quality': len([s for s in scores if 70 <= s < 90]),
            'medium_quality': len([s for s in scores if 50 <= s < 70]),
        }
    
    # ─────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ─────────────────────────────────────────────────────────────────────
    
    def get_matches_for_arayis(self, arayis_id: str, 
                               top_n: int = 5) -> List[Match]:
        """Belirli arayış için matches'i getir"""
        
        arayis_matches = [m for m in self.matches 
                         if m.arayis_id == arayis_id]
        arayis_matches.sort(key=lambda m: m.overall_score, reverse=True)
        
        return arayis_matches[:top_n]
    
    def get_high_quality_matches(self, threshold: float = 90.0) -> List[Match]:
        """Yüksek kalite matches'i getir"""
        
        high_quality = [m for m in self.matches 
                       if m.overall_score >= threshold]
        high_quality.sort(key=lambda m: m.overall_score, reverse=True)
        
        return high_quality
    
    def export_for_whatsapp(self, filepath: str, top_n: int = 10):
        """WhatsApp gönderimi için format"""
        
        top_matches = sorted(self.matches, 
                            key=lambda m: m.overall_score, 
                            reverse=True)[:top_n]
        
        messages = []
        
        for i, match in enumerate(top_matches, 1):
            msg = f"""
🏆 #{i} MATCH

Arayış: {match.arayis_id}
Portföy: {match.portfoy_id}
Score: {match.overall_score:.1f}%

📍 Tavsiye: {match.recommendation}

✅ Güven: {match.confidence:.1%}
"""
            messages.append(msg)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(messages))
        
        logger.info(f"✅ WhatsApp formatı: {Path(filepath).name}")

# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION WITH a.py SCRAPER
# ═══════════════════════════════════════════════════════════════════════════

def run_scraper_and_matcher(scraper_output_json: str, 
                           whatsapp_txt: str,
                           output_dir: str = "matcher_output") -> Tuple[List[Match], Dict]:
    """
    a.py scraper'dan sonra çalıştır
    
    Example from a.py:
    ```python
    # In a.py main
    scraper = CBScraper()
    scraper.scrape_all()
    scraper.save_all()
    
    # Then run matcher
    from matcher_orchestrator import run_scraper_and_matcher
    matches, stats = run_scraper_and_matcher(
        scraper_output_json='scraper_output/listings_20260710_123456.json',
        whatsapp_txt='Coldwell_Banker_Ankara_ile_WhatsApp_Sohbeti.txt'
    )
    ```
    """
    
    orchestrator = MatcherOrchestrator(output_dir=output_dir)
    matches, stats = orchestrator.run_full_pipeline(
        listings_json=scraper_output_json,
        whatsapp_txt=whatsapp_txt
    )
    
    return matches, stats

# ═══════════════════════════════════════════════════════════════════════════
# MAIN (Testing)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    
    # Default paths
    listings_json = "listings_20260710_093535.json"
    whatsapp_txt = "_Coldwell_Banker_Ankara_ile_WhatsApp_Sohbeti.txt"
    
    # Check if files exist
    if not os.path.exists(listings_json):
        logger.error(f"❌ Dosya bulunamadı: {listings_json}")
        logger.info(f"   Usage: python matcher_orchestrator.py <listings.json> <whatsapp.txt>")
        sys.exit(1)
    
    if not os.path.exists(whatsapp_txt):
        logger.error(f"❌ Dosya bulunamadı: {whatsapp_txt}")
        sys.exit(1)
    
    # Run pipeline
    matches, stats = run_scraper_and_matcher(
        scraper_output_json=listings_json,
        whatsapp_txt=whatsapp_txt
    )
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Toplam Match: {stats['total_matches']}")
    print(f"Avg Score: {stats['avg_score']:.1f}%")
    print(f"High Quality (90+): {stats['high_quality']}")
    print(f"{'='*70}\n")
