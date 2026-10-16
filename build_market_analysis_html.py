import json
from pathlib import Path

DESKTOP_OUT = Path(r"C:\Users\USER\Desktop\MUSTAFA_KEMAL_OFIS_PIYASA_ANALIZI.html")

def generate_market_html(output_file: str = None, mode_badge: str = "NEXA ORBIT™ | REVERSE-CMA ENGINE") -> str:
    # Load dataset and our listing cache
    with open("mustafa_kemal_market_dataset.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    with open("cache_ygt/1296499962.json", "r", encoding="utf-8") as f:
        our_cache = json.load(f)

    target_out = Path(output_file) if output_file else DESKTOP_OUT

    # Calculate data science metrics
    prices = [x['price'] for x in dataset]
    m2s = [x['m2'] for x in dataset]
    u_prices = [x['unit_m2_price'] for x in dataset]

    avg_price = sum(prices) / len(prices)
    prices_sorted = sorted(prices)
    median_price = prices_sorted[len(prices_sorted)//2]
    avg_m2 = sum(m2s) / len(m2s)
    avg_u = sum(u_prices) / len(u_prices)
    u_sorted = sorted(u_prices)
    median_u = u_sorted[len(u_sorted)//2]

    esyali_count = len([x for x in dataset if x['is_esyali']])
    esyasiz_count = len([x for x in dataset if not x['is_esyali']])

    our_item = [x for x in dataset if x['is_ours']][0]
    cheaper_count = len([x for x in dataset if x['price'] < our_item['price']])
    same_count = len([x for x in dataset if x['price'] == our_item['price']])
    expensive_count = len([x for x in dataset if x['price'] > our_item['price']])

    # JSON data for charts and script
    dataset_json_str = json.dumps(dataset, ensure_ascii=False)
    our_cache_json_str = json.dumps(our_cache, ensure_ascii=False)

    print(f"Compiling ultra-luxury HTML CMA dashboard ({mode_badge})...")

    html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
<title>Mustafa Kemal Mah. Kiralık Ofis Piyasa Analizi & Portföy Raporu | Gayrimenkul Mühendisi</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
:root {{
    --bg-dark: #05070b;
    --card-surface: rgba(13, 17, 26, 0.94);
    --card-surface-light: rgba(19, 26, 40, 0.85);
    --gold: #d4af37;
    --gold-light: #fef0cc;
    --gold-dark: #aa7c11;
    --gold-gradient: linear-gradient(135deg, #d4af37 0%, #fae8a4 45%, #aa7c11 100%);
    --gold-glow: rgba(212, 175, 55, 0.28);
    --neon-blue: #38bdf8;
    --neon-blue-glow: rgba(56, 189, 248, 0.3);
    --emerald: #10b981;
    --emerald-glow: rgba(16, 185, 129, 0.3);
    --rose: #f43f5e;
    --purple: #a855f7;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --border: rgba(255, 255, 255, 0.08);
    --border-gold: rgba(212, 175, 55, 0.35);
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    background-color: var(--bg-dark);
    color: var(--text-primary);
    line-height: 1.6;
    background-image: 
        radial-gradient(circle at 10% 10%, rgba(212, 175, 55, 0.05) 0%, transparent 40%),
        radial-gradient(circle at 90% 90%, rgba(56, 189, 248, 0.04) 0%, transparent 40%);
    background-attachment: fixed;
    padding-bottom: 90px;
}}

/* Top Executive Hero */
.hero-header {{
    background: linear-gradient(180deg, rgba(16, 22, 34, 0.98) 0%, rgba(5, 7, 11, 0.95) 100%);
    border-bottom: 1px solid var(--border-gold);
    padding: 38px 20px 30px;
    text-align: center;
    position: relative;
    box-shadow: 0 16px 40px rgba(0,0,0,0.7);
}}
.hero-brand {{
    font-family: 'Cinzel', serif;
    font-size: 13px;
    letter-spacing: 5px;
    color: var(--gold);
    text-transform: uppercase;
    margin-bottom: 8px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
}}
.hero-title {{
    font-family: 'Cinzel', serif;
    font-size: clamp(24px, 4vw, 36px);
    font-weight: 800;
    color: #fff;
    margin-bottom: 8px;
    line-height: 1.25;
}}
.gold-text {{
    background: var(--gold-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: inline;
}}
.hero-subtitle {{
    font-size: 14px;
    color: var(--text-secondary);
    max-width: 860px;
    margin: 0 auto 16px;
}}
.hero-badges {{
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
}}
.badge-pill {{
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-gold);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    color: var(--gold-light);
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}

.container {{
    max-width: 1380px;
    margin: 0 auto;
    padding: 24px 20px;
}}

/* KPI Metric Cards */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
}}
.kpi-card {{
    background: var(--card-surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px 16px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    position: relative;
    overflow: hidden;
    transition: transform 0.25s, border-color 0.25s;
}}
.kpi-card:hover {{
    transform: translateY(-3px);
    border-color: var(--border-gold);
}}
.kpi-card.gold-highlight {{
    border-color: var(--border-gold);
    background: linear-gradient(135deg, rgba(212, 175, 55, 0.12) 0%, rgba(13, 17, 26, 0.95) 100%);
    box-shadow: 0 12px 35px var(--gold-glow);
}}
.kpi-card.emerald-highlight {{
    border-color: rgba(16, 185, 129, 0.4);
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(13, 17, 26, 0.95) 100%);
}}
.kpi-card.blue-highlight {{
    border-color: rgba(56, 189, 248, 0.4);
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.1) 0%, rgba(13, 17, 26, 0.95) 100%);
}}
.kpi-title {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.kpi-value {{
    font-family: 'Cinzel', serif;
    font-size: 26px;
    font-weight: 800;
    color: #fff;
    line-height: 1.1;
}}
.kpi-sub {{
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 5px;
}}

/* Section Titles */
.section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 35px 0 18px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-gold);
    flex-wrap: wrap;
    gap: 12px;
}}
.section-title {{
    font-family: 'Cinzel', serif;
    font-size: 20px;
    font-weight: 800;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.section-title i {{ color: var(--gold); }}

/* VIP Our Listing Spotlight Bento */
.our-listing-box {{
    background: linear-gradient(180deg, rgba(20, 26, 40, 0.95) 0%, rgba(10, 13, 20, 0.98) 100%);
    border: 2px solid var(--gold);
    border-radius: 24px;
    padding: 26px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.8), 0 0 50px rgba(212, 175, 55, 0.15);
    margin-bottom: 35px;
    position: relative;
}}
.our-badge-top {{
    position: absolute;
    top: -14px;
    left: 28px;
    background: var(--gold-gradient);
    color: #05070b;
    font-family: 'Cinzel', serif;
    font-weight: 900;
    font-size: 12px;
    letter-spacing: 1.5px;
    padding: 6px 18px;
    border-radius: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5);
}}
.our-grid {{
    display: grid;
    grid-template-columns: 1.3fr 1fr;
    gap: 24px;
    margin-top: 10px;
}}
@media (max-width: 950px) {{
    .our-grid {{ grid-template-columns: 1fr; }}
}}

.our-gallery {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    grid-template-rows: 190px 190px;
    gap: 8px;
    border-radius: 16px;
    overflow: hidden;
}}
.our-g-main {{
    grid-row: span 2;
    position: relative;
    cursor: pointer;
}}
.our-g-main img, .our-g-sub img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s;
}}
.our-g-main:hover img, .our-g-sub:hover img {{
    transform: scale(1.04);
}}
.our-g-sub {{
    position: relative;
    cursor: pointer;
    overflow: hidden;
}}
.g-all-count {{
    position: absolute;
    bottom: 10px;
    right: 10px;
    background: rgba(0,0,0,0.8);
    backdrop-filter: blur(6px);
    color: var(--gold-light);
    font-size: 11px;
    font-weight: 700;
    padding: 5px 10px;
    border-radius: 6px;
    border: 1px solid var(--border-gold);
}}

.filmstrip {{
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 8px 0 4px;
    margin-top: 10px;
}}
.filmstrip img {{
    width: 68px;
    height: 50px;
    border-radius: 6px;
    object-fit: cover;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.1);
    transition: all 0.2s;
    flex-shrink: 0;
}}
.filmstrip img:hover {{
    border-color: var(--gold);
    transform: scale(1.1);
}}

/* Our Details Right Side */
.our-info {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
.our-title {{
    font-family: 'Cinzel', serif;
    font-size: 22px;
    font-weight: 800;
    color: #fff;
    margin-bottom: 8px;
    line-height: 1.3;
}}
.our-price-row {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 16px;
}}
.our-price {{
    font-family: 'Cinzel', serif;
    font-size: 32px;
    font-weight: 900;
    color: var(--gold);
}}
.our-price-sub {{
    font-size: 13px;
    color: var(--text-secondary);
}}
.spec-chips {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 18px;
}}
.chip {{
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    padding: 8px 12px;
    border-radius: 10px;
}}
.chip-k {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
.chip-v {{ font-size: 13px; font-weight: 700; color: #fff; margin-top: 2px; }}

.furniture-inventory {{
    background: rgba(212, 175, 55, 0.06);
    border: 1px solid var(--border-gold);
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 11.5px;
    color: var(--gold-light);
    line-height: 1.5;
    margin-bottom: 18px;
}}
.furniture-inventory i {{ color: var(--gold); margin-right: 6px; }}

.our-actions {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}}
.btn-gold {{
    background: var(--gold-gradient);
    color: #05070b;
    font-family: 'Cinzel', serif;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 1px;
    padding: 12px 20px;
    border-radius: 10px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 15px rgba(212, 175, 55, 0.35);
    transition: transform 0.2s;
}}
.btn-gold:hover {{ transform: translateY(-2px); }}
.btn-whatsapp {{
    background: #25d366;
    color: #fff;
    font-weight: 700;
    font-size: 12px;
    padding: 12px 18px;
    border-radius: 10px;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: opacity 0.2s;
}}
.btn-whatsapp:hover {{ opacity: 0.9; }}

/* Strategic Analysis Cards Grid */
.strategy-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
    margin-bottom: 35px;
}}
.strategy-card {{
    background: var(--card-surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 22px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    position: relative;
}}
.strategy-card.highlight {{
    border-color: var(--border-gold);
    background: linear-gradient(180deg, rgba(21, 28, 44, 0.9) 0%, rgba(13, 17, 26, 0.95) 100%);
}}
.strat-badge {{
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 4px 10px;
    border-radius: 6px;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 10px;
}}
.strat-badge.gold {{ background: rgba(212,175,55,0.2); color: var(--gold); }}
.strat-badge.blue {{ background: rgba(56,189,248,0.2); color: var(--neon-blue); }}
.strat-badge.emerald {{ background: rgba(16,185,129,0.2); color: var(--emerald); }}
.strat-badge.rose {{ background: rgba(244,63,94,0.2); color: var(--rose); }}

.strat-title {{
    font-family: 'Cinzel', serif;
    font-size: 16px;
    font-weight: 800;
    color: #fff;
    margin-bottom: 10px;
}}
.strat-desc {{
    font-size: 12.5px;
    color: var(--text-secondary);
    line-height: 1.55;
}}
.price-scenarios {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
}}
.scenario-box {{
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.scenario-tag {{ font-size: 11px; font-weight: 700; color: #fff; }}
.scenario-val {{ font-family: 'Cinzel', serif; font-size: 16px; font-weight: 800; color: var(--gold); }}

/* Data Science Charts Section */
.charts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 20px;
    margin-bottom: 35px;
}}
@media (max-width: 600px) {{
    .charts-grid {{ grid-template-columns: 1fr; }}
}}
.chart-box {{
    background: var(--card-surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}}
.chart-box-title {{
    font-family: 'Cinzel', serif;
    font-size: 14px;
    font-weight: 700;
    color: var(--gold-light);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

/* Filter & Controls Bar */
.controls-bar {{
    background: var(--card-surface);
    border: 1px solid var(--border-gold);
    border-radius: 16px;
    padding: 14px 18px;
    margin-bottom: 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}}
.filter-pills {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}}
.f-btn {{
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 7px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}}
.f-btn:hover, .f-btn.active {{
    background: var(--gold-gradient);
    color: #05070b;
    border-color: var(--gold);
    box-shadow: 0 2px 10px rgba(212, 175, 55, 0.3);
}}
.search-input {{
    background: rgba(0,0,0,0.5);
    border: 1px solid var(--border);
    color: #fff;
    padding: 8px 14px;
    border-radius: 10px;
    font-size: 12px;
    outline: none;
    min-width: 200px;
    transition: border-color 0.2s;
}}
.search-input:focus {{ border-color: var(--gold); }}

/* 35 Listings Grid */
.listings-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
    gap: 16px;
}}
.item-card {{
    background: var(--card-surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    transition: transform 0.25s, border-color 0.25s;
    display: flex;
    flex-direction: column;
    position: relative;
}}
.item-card:hover {{
    transform: translateY(-4px);
    border-color: var(--border-gold);
}}
.item-card.is-ours {{
    border: 2px solid var(--gold);
    box-shadow: 0 12px 35px var(--gold-glow);
    background: linear-gradient(180deg, rgba(25, 33, 50, 0.95) 0%, rgba(13, 17, 26, 0.95) 100%);
}}
.card-img-wrap {{
    position: relative;
    height: 170px;
    overflow: hidden;
    background: #080c14;
    cursor: pointer;
}}
.card-img-wrap img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s;
}}
.item-card:hover .card-img-wrap img {{
    transform: scale(1.06);
}}
.card-ribbons {{
    position: absolute;
    top: 10px;
    left: 10px;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    z-index: 2;
}}
.ribbon {{
    font-size: 9.5px;
    font-weight: 800;
    letter-spacing: 0.5px;
    padding: 4px 8px;
    border-radius: 6px;
    text-transform: uppercase;
}}
.ribbon.ours {{ background: var(--gold-gradient); color: #05070b; }}
.ribbon.esyali {{ background: var(--emerald); color: #fff; }}
.ribbon.esyasiz {{ background: rgba(0,0,0,0.7); color: var(--text-secondary); backdrop-filter: blur(4px); }}
.ribbon.proj {{ background: rgba(56, 189, 248, 0.25); color: #e0f2fe; border: 1px solid rgba(56, 189, 248, 0.5); }}

.card-body {{
    padding: 14px 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
.card-rank {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
    margin-bottom: 4px;
}}
.card-title {{
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    line-height: 1.35;
    margin-bottom: 10px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.card-price-row {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding-top: 8px;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin-top: 8px;
}}
.card-price {{
    font-family: 'Cinzel', serif;
    font-size: 19px;
    font-weight: 800;
    color: var(--gold);
}}
.card-u-price {{
    font-size: 11px;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
}}
.card-specs-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 6px;
}}
.card-specs-row i {{ color: var(--gold); margin-right: 3px; }}

.card-footer-btn {{
    margin-top: 10px;
    text-align: center;
    font-size: 11px;
    font-weight: 700;
    color: var(--neon-blue);
    text-decoration: none;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 6px;
    border-radius: 6px;
    background: rgba(56, 189, 248, 0.06);
    transition: background 0.2s;
}}
.card-footer-btn:hover {{ background: rgba(56, 189, 248, 0.15); }}

/* Fullscreen Lightbox */
.lightbox {{
    display: none;
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(0,0,0,0.94);
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(14px);
}}
.lightbox.active {{ display: flex; }}
.lightbox-img {{
    max-width: 90vw;
    max-height: 85vh;
    border-radius: 12px;
    border: 1px solid var(--border-gold);
    box-shadow: 0 0 60px rgba(0,0,0,0.9);
}}
.lightbox-close {{
    position: absolute;
    top: 25px;
    right: 30px;
    color: #fff;
    font-size: 34px;
    cursor: pointer;
    transition: color 0.2s;
}}
.lightbox-close:hover {{ color: var(--gold); }}

/* Footer */
footer {{
    text-align: center;
    margin-top: 60px;
    padding-top: 30px;
    border-top: 1px solid var(--border-gold);
    color: var(--text-muted);
    font-size: 12px;
}}
footer a {{ color: var(--gold); text-decoration: none; }}
</style>
</head>
<body>

<!-- Header -->
<header class="hero-header">
    <div class="hero-brand">
        <i class="fas fa-crown"></i>
        <span>COLDWELL BANKER CB VIP ANKARA &nbsp;|&nbsp; GAYRİMENKUL MÜHENDİSİ</span>
    </div>
    <h1 class="hero-title">
        Mustafa Kemal Mahallesi <span class="gold-text">Kiralık Ofis Piyasa Analizi</span>
    </h1>
    <p class="hero-subtitle">
        35 İlanlık Uçtan Uca Derin Veri Bilimi, Eşyalı/Eşyasız Fiyatlandırma Modelleri, Rakip Konumlandırması ve Portföy Vitrini
    </p>
    <div class="hero-badges">
        <div class="badge-pill"><i class="fas fa-map-marker-alt"></i> Ankara / Çankaya / Mustafa Kemal Mah.</div>
        <div class="badge-pill"><i class="fas fa-filter"></i> Fiyat: ≤ 70.000 TL &nbsp;|&nbsp; 1+0, 1+1, 2+1</div>
        <div class="badge-pill"><i class="fas fa-database"></i> 35 Doğrulanmış Portföy Verisi</div>
        <div class="badge-pill"><i class="fas fa-user-tie"></i> Yetkili Danışman: Yiğit Narin</div>
    </div>
</header>

<main class="container">

    <!-- KPI Metric Summary -->
    <div class="kpi-grid">
        <div class="kpi-card gold-highlight">
            <div class="kpi-title"><i class="fas fa-building"></i> Toplam İncelenen Ofis</div>
            <div class="kpi-value">{len(dataset)}</div>
            <div class="kpi-sub">Mustafa Kemal Mah. tüm segment</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-title"><i class="fas fa-chart-line"></i> Piyasa Medyan Kirası</div>
            <div class="kpi-value">{median_price:,.0f} <span style="font-size:14px; font-family:sans-serif;">TL</span></div>
            <div class="kpi-sub">Ortalama: {avg_price:,.0f} TL</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-title"><i class="fas fa-ruler-combined"></i> Ortalama m² Birim Kira</div>
            <div class="kpi-value">{avg_u:.0f} <span style="font-size:14px; font-family:sans-serif;">TL/m²</span></div>
            <div class="kpi-sub">Medyan: {median_u:.0f} TL/m²</div>
        </div>

        <div class="kpi-card emerald-highlight">
            <div class="kpi-title"><i class="fas fa-couch"></i> Eşyalı Ofis Oranı</div>
            <div class="kpi-value">%{esyali_count / len(dataset) * 100:.1f}</div>
            <div class="kpi-sub">35 İlanda Yalnızca {esyali_count} Eşyalı!</div>
        </div>

        <div class="kpi-card blue-highlight">
            <div class="kpi-title"><i class="fas fa-star"></i> Bizim Portföy (#1296499962)</div>
            <div class="kpi-value">55.000 <span style="font-size:14px; font-family:sans-serif;">TL</span></div>
            <div class="kpi-sub">65 m² (846 TL/m²) Full Eşyalı</div>
        </div>
    </div>

    <!-- SECTION 1: OUR LISTING AUDIT & SPOTLIGHT -->
    <div class="section-header">
        <div class="section-title">
            <i class="fas fa-crown"></i>
            <span>BİZİM PORTFÖYÜMÜZÜN DETAYLI ANALİZİ (#1296499962)</span>
        </div>
        <div style="font-size:12px; color:var(--gold); font-weight:700;">
            TEK YETKİLİ DANIŞMAN: YİĞİT NARİN
        </div>
    </div>

    <div class="our-listing-box">
        <div class="our-badge-top">BİZİM PORTFÖYÜMÜZ &nbsp;|&nbsp; COLDWELL BANKER VIP</div>
        
        <div class="our-grid">
            <!-- Left Gallery -->
            <div>
                <div class="our-gallery">
                    <div class="our-g-main" onclick="openLightbox('https://i0.shbdn.com/photos/49/99/62/x5_12964999627df.avif')">
                        <img src="https://i0.shbdn.com/photos/49/99/62/x5_12964999627df.avif" alt="Ofis Vitrin">
                        <div class="g-all-count"><i class="fas fa-camera"></i> 29 Yüksek Çözünürlüklü Fotoğraf</div>
                    </div>
                    <div class="our-g-sub" onclick="openLightbox('https://i0.shbdn.com/photos/49/99/62/x5_1296499962kz0.avif')">
                        <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962kz0.avif" alt="Ofis Oda">
                    </div>
                    <div class="our-g-sub" onclick="openLightbox('https://i0.shbdn.com/photos/49/99/62/x5_1296499962ppf.avif')">
                        <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962ppf.avif" alt="Mutfak">
                    </div>
                </div>

                <!-- Filmstrip of photos -->
                <div class="filmstrip">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_12964999627df.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962kz0.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962ppf.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962djh.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962b9k.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962vw9.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962g5v.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962e3d.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_129649996264z.avif" onclick="openLightbox(this.src)">
                    <img src="https://i0.shbdn.com/photos/49/99/62/x5_1296499962yy4.avif" onclick="openLightbox(this.src)">
                </div>
            </div>

            <!-- Right Info -->
            <div class="our-info">
                <div>
                    <h2 class="our-title">Mustafa Kemal Mah. Ofis İBK'da Full Eşyalı 1+1 Kiralık Prestij Ofis</h2>
                    <div class="our-price-row">
                        <div class="our-price">55.000 TL <span style="font-size:14px; color:var(--text-secondary); font-family:sans-serif;">/ Ay</span></div>
                        <div class="our-price-sub">Birim: <b>846.2 TL/m²</b> &nbsp;|&nbsp; Net Alan: <b>65 m²</b></div>
                    </div>

                    <div class="spec-chips">
                        <div class="chip">
                            <div class="chip-k">Oda Düzeni</div>
                            <div class="chip-v">1+1 (Salon + Oda + Kapalı Mutfak)</div>
                        </div>
                        <div class="chip">
                            <div class="chip-k">Bina & Kat</div>
                            <div class="chip-v">Ofis İBK | Yüksek Giriş (4 Katlı Butik)</div>
                        </div>
                        <div class="chip">
                            <div class="chip-k">Isınma & Gider</div>
                            <div class="chip-v">Doğalgaz Kombili (Düşük Aidatlı)</div>
                        </div>
                        <div class="chip">
                            <div class="chip-k">Otopark</div>
                            <div class="chip-v">2 Araçlık Kapalı & Açık Otopark</div>
                        </div>
                    </div>

                    <div class="furniture-inventory">
                        <div><i class="fas fa-couch"></i> <b>Eksiksiz Kurumsal Mobilya Envanteri:</b></div>
                        <div style="margin-top:4px;">
                            Makam Masası, Hakiki Deri Koltuk Takımı, Sehpa, Kilitli Dresuar, Klima, Toplantı Masası & Sandalyeler, TV, Spot & Led Aydınlatma, Franke Ankastre Ocak, Samsung Fırın, Mini Buzdolabı, Vestiyer, Hilton Banyo.
                        </div>
                    </div>
                </div>

                <div class="our-actions">
                    <a href="https://www.sahibinden.com/ilan/1296499962/detay" target="_blank" class="btn-gold">
                        <span>SAHİBİNDEN'DE GÖR</span>
                        <i class="fas fa-external-link-alt"></i>
                    </a>
                    <a href="https://wa.me/905324514008?text=Merhaba%20Yi%C4%9Fit%20Bey,%20Mustafa%20Kemal%20Mah.%20E%C5%9Fyalı%20Ofisiniz%20(1296499962)%20i%C3%A7in%20yaz%C4%B1yorum." target="_blank" class="btn-whatsapp">
                        <i class="fab fa-whatsapp"></i>
                        <span>WHATSAPP'TAN PAYLAŞ</span>
                    </a>
                    <a href="tel:+905324514008" class="badge-pill" style="padding:10px 16px; border-radius:10px; text-decoration:none;">
                        <i class="fas fa-phone"></i> 0532 451 40 08
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- SECTION 2: STRATEGIC CMA & VALUATION INSIGHTS -->
    <div class="section-header">
        <div class="section-title">
            <i class="fas fa-brain"></i>
            <span>PİYASAYA GÖRE NE DURUMDAYIZ? & STRATEJİK DEĞERLEME</span>
        </div>
    </div>

    <div class="strategy-grid">
        <!-- Card 1 -->
        <div class="strategy-card highlight">
            <span class="strat-badge gold"><i class="fas fa-trophy"></i> RAKİP KONUMLANDIRMASI</span>
            <h3 class="strat-title">Medyanın Merkezinde, Eşyada Tekel!</h3>
            <p class="strat-desc">
                Mustafa Kemal Mahallesi'nde 70.000 TL altındaki 35 ofis arasında <b>ortalama fiyat 55.300 TL, medyan ise 56.000 TL'dir</b>. Bizim 55.000 TL'lik fiyatımız, piyasanın en likit ve en çok aranan <b>%48'lik tam medyan dilimindedir</b>.
            </p>
            <p class="strat-desc" style="margin-top:8px;">
                <b>En Büyük Koz:</b> 35 ilanın 33 tanesi (<b style="color:var(--rose);">%94.3'ü</b>) tamamen <b>BOŞ / EŞYASIZDIR</b>. Tüm piyasada bizim segmentimizde eşyalı yalnızca 2 ofis vardır!
            </p>
        </div>

        <!-- Card 2 -->
        <div class="strategy-card">
            <span class="strat-badge emerald"><i class="fas fa-calculator"></i> KİRACIYA 350.000 TL TASARRUF</span>
            <h3 class="strat-title">Boş Mahall & Maidan Kıyaslaması</h3>
            <p class="strat-desc">
                Mahall Ankara'da boş 1+1 ofisler <b>57.500 - 62.500 TL</b>, Maidan'da boş 50 m² ofisler <b>67.500 TL</b>'dir.
            </p>
            <p class="strat-desc" style="margin-top:8px;">
                Bir kurumsal kiracı boş ofis tuttuğunda; makam masası, deri koltuk, klima, beyaz eşya ve aydınlatma için <b>en az 300.000 - 450.000 TL</b> nakit sermaye bağlar. Bizim ofisimiz bu masrafı sıfıra indirerek taşınmaya hazır anahtar teslim avantaj sunmaktadır.
            </p>
        </div>

        <!-- Card 3 -->
        <div class="strategy-card">
            <span class="strat-badge blue"><i class="fas fa-shield-alt"></i> AİDAT & ISINMA AVANTAJI</span>
            <h3 class="strat-title">Aylık 10.000 TL Gizli Gider Tasarrufu</h3>
            <p class="strat-desc">
                Maidan ve Mahall kulelerinde fancoil merkezi pay ölçer ve yüksek ortak alan aidatları vardır (aylık 8.000 - 14.000 TL aidat).
            </p>
            <p class="strat-desc" style="margin-top:8px;">
                Ofis İBK'daki mülkümüz <b>bireysel Demirdöküm kombilidir</b> ve butik bina olduğu için aidat minimum düzeydedir. Kiracının cebinden çıkacak toplam aylık işletme maliyeti kulelere göre en az <b>%25 daha düşüktür</b>.
            </p>
        </div>

        <!-- Card 4: FİYAT NE OLMALI? -->
        <div class="strategy-card highlight" style="grid-column: 1 / -1;">
            <span class="strat-badge gold"><i class="fas fa-coins"></i> BİLİMSEL FİYATLANDIRMA ÖNERİSİ</span>
            <h3 class="strat-title">Fiyat Ne Olmalı? Algoritmik Senaryo Analizi</h3>
            
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:14px; margin-top:12px;">
                <div class="scenario-box" style="border-left: 3px solid var(--emerald);">
                    <div>
                        <div class="scenario-tag" style="color:var(--emerald);">SENARYO A: HIZLI KİRALAMA (1-2 Hafta)</div>
                        <div style="font-size:11px; color:var(--text-secondary); margin-top:3px;">Mevcut Fiyat | Yüksek Talep, Sıfır Boş Kalma Riski</div>
                    </div>
                    <div class="scenario-val">55.000 TL</div>
                </div>

                <div class="scenario-box" style="border-left: 3px solid var(--gold);">
                    <div>
                        <div class="scenario-tag" style="color:var(--gold);">SENARYO B: PİYASA DENGE DEĞERİ (Fair Market)</div>
                        <div style="font-size:11px; color:var(--text-secondary); margin-top:3px;">Mobilya Değeri Eklenmiş Optimum Değer</div>
                    </div>
                    <div class="scenario-val">58.000 - 60.000 TL</div>
                </div>

                <div class="scenario-box" style="border-left: 3px solid var(--rose);">
                    <div>
                        <div class="scenario-tag" style="color:var(--rose);">SENARYO C: TEPE PRİME EMSAL TAVANI</div>
                        <div style="font-size:11px; color:var(--text-secondary); margin-top:3px;">Piyasadaki tek diğer eşyalı ofis emsali</div>
                    </div>
                    <div class="scenario-val">62.500 - 65.000 TL</div>
                </div>
            </div>

            <div style="background:rgba(0,0,0,0.5); padding:12px 14px; border-radius:10px; margin-top:14px; font-size:12px; color:var(--text-silver); line-height:1.5;">
                <b style="color:var(--gold);"><i class="fas fa-lightbulb"></i> Gayrimenkul Mühendisi Tavsiyesi:</b> 
                Mevcut <b>55.000 TL</b> seviyesi, piyasadaki boş 1+1 medyanına denk geldiği için <b>kiracı açısından reddedilemeyecek bir tekliftir</b>. Eğer mülk sahibinin acil nakit akışı ihtiyacı yoksa, ilan başlığı revize edilerek fiyat <b>58.000 TL</b>'ye çekilebilir ve 55.000 TL'ye pazarlık payı bırakılarak en kaliteli kurumsal kiracı (hukuk bürosu / yazılım şirketi) seçilebilir.
            </div>
        </div>
    </div>

    <!-- SECTION 3: DATA SCIENCE CHARTS -->
    <div class="section-header">
        <div class="section-title">
            <i class="fas fa-chart-pie"></i>
            <span>VERİ BİLİMİ & GRAFİK ANALİTİĞİ</span>
        </div>
    </div>

    <div class="charts-grid">
        <!-- Chart 1: Price Histogram -->
        <div class="chart-box">
            <div class="chart-box-title">
                <span>Fiyat Dağılımı & Bizim Konumumuz</span>
                <span style="font-size:11px; color:var(--gold);"><i class="fas fa-chart-bar"></i> Histogram</span>
            </div>
            <canvas id="chartPriceHist" height="220"></canvas>
        </div>

        <!-- Chart 2: Project TL/m2 Comparison -->
        <div class="chart-box">
            <div class="chart-box-title">
                <span>Projeler Bazında Ortalama Birim Kira (TL/m²)</span>
                <span style="font-size:11px; color:var(--neon-blue);"><i class="fas fa-building"></i> Proje Kıyas</span>
            </div>
            <canvas id="chartProjectUnit" height="220"></canvas>
        </div>

        <!-- Chart 3: Furnished vs Unfurnished -->
        <div class="chart-box">
            <div class="chart-box-title">
                <span>Eşyalı vs Eşyasız Ofis Arz Dağılımı</span>
                <span style="font-size:11px; color:var(--emerald);"><i class="fas fa-couch"></i> Tekel Avantajı</span>
            </div>
            <canvas id="chartFurnished" height="220"></canvas>
        </div>

        <!-- Chart 4: Room Types -->
        <div class="chart-box">
            <div class="chart-box-title">
                <span>Oda Tipleri Dağılımı & Ort. Fiyatlar</span>
                <span style="font-size:11px; color:var(--purple);"><i class="fas fa-door-open"></i> 1+0 / 1+1 / 2+1</span>
            </div>
            <canvas id="chartRooms" height="220"></canvas>
        </div>
    </div>

    <!-- SECTION 4: 35 LISTINGS BENTO & COMPARISON TABLE -->
    <div class="section-header">
        <div class="section-title">
            <i class="fas fa-th-large"></i>
            <span>MUSTAFA KEMAL TÜM KİRALIK OFİS LİSTESİ (35 İLAN)</span>
        </div>
        <div style="font-size:11px; color:var(--text-muted);">
            Tüm ilanlar canlı Sahibinden verileriyle eşleştirilmiştir
        </div>
    </div>

    <!-- Filter & Controls -->
    <div class="controls-bar">
        <div class="filter-pills">
            <button class="f-btn active" onclick="filterListings('all', this)">Tümü (35)</button>
            <button class="f-btn" onclick="filterListings('ours', this)"><i class="fas fa-crown"></i> Bizim Portföy</button>
            <button class="f-btn" onclick="filterListings('esyali', this)">Eşyalı (2)</button>
            <button class="f-btn" onclick="filterListings('esyasiz', this)">Eşyasız (33)</button>
            <button class="f-btn" onclick="filterListings('1+1', this)">1+1 (17)</button>
            <button class="f-btn" onclick="filterListings('2+1', this)">2+1 (11)</button>
            <button class="f-btn" onclick="filterListings('1+0', this)">1+0 (7)</button>
            <button class="f-btn" onclick="filterListings('mahall', this)">Mahall Ankara</button>
            <button class="f-btn" onclick="filterListings('maidan', this)">Maidan & Vega</button>
        </div>

        <div style="display:flex; gap:10px; align-items:center;">
            <input type="text" id="searchInput" class="search-input" placeholder="İlan başlığı, proje veya fiyat ara..." oninput="searchListings(this.value)">
            <select id="sortSelect" class="search-input" style="min-width:140px; cursor:pointer;" onchange="sortListings(this.value)">
                <option value="rank">Varsayılan Sıralama</option>
                <option value="price-asc">Fiyat: Artan</option>
                <option value="price-desc">Fiyat: Azalan</option>
                <option value="m2-desc">m²: En Büyük</option>
                <option value="unit-asc">TL/m²: En Uygun</option>
            </select>
        </div>
    </div>

    <!-- Listings Cards Grid -->
    <div class="listings-grid" id="listingsContainer">
        <!-- Rendered by JavaScript dynamically -->
    </div>

</main>

<!-- Fullscreen Lightbox Modal -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
    <span class="lightbox-close">&times;</span>
    <img src="" class="lightbox-img" id="lightboxImg" onclick="event.stopPropagation()">
</div>

<footer>
    <div style="font-family:'Cinzel', serif; font-size:14px; font-weight:800; color:var(--gold); margin-bottom:6px;">
        COLDWELL BANKER CB VIP ANKARA &nbsp;|&nbsp; GAYRİMENKUL MÜHENDİSİ
    </div>
    <div>Yetkili Danışman: <b>Yiğit Narin</b> &nbsp;|&nbsp; Tel: <b>0532 451 40 08</b> &nbsp;|&nbsp; Web: <a href="https://gayrimenkulmuhendisi.com" target="_blank">gayrimenkulmuhendisi.com</a></div>
    <div style="margin-top:6px; font-size:11px;">Rapor Tarihi: 16 Ekim 2026 &nbsp;|&nbsp; NEXA.OS v5.0 Autonomous Real Estate Intelligence Lab</div>
</footer>

<script>
const RAW_DATASET = {dataset_json_str};
let currentDataset = [...RAW_DATASET];

// Render Listings Grid
function renderListings(items) {{
    const container = document.getElementById('listingsContainer');
    if (!items.length) {{
        container.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted);"><i class="fas fa-search" style="font-size:24px; margin-bottom:8px;"></i><br>Kriterlere uygun ilan bulunamadı.</div>';
        return;
    }}

    container.innerHTML = items.map(it => `
        <article class="item-card ${{it.is_ours ? 'is-ours' : ''}}" data-rank="${{it.rank}}">
            <div class="card-img-wrap" onclick="openLightbox('${{it.high_res_photo}}')">
                <img src="${{it.thumb_url}}" alt="${{it.title}}" loading="lazy">
                <div class="card-ribbons">
                    ${{it.is_ours ? '<span class="ribbon ours"><i class="fas fa-crown"></i> BİZİM PORTFÖY</span>' : ''}}
                    <span class="ribbon ${{it.is_esyali ? 'esyali' : 'esyasiz'}}">${{it.is_esyali ? 'EŞYALI' : 'BOŞ'}}</span>
                    <span class="ribbon proj">${{it.project}}</span>
                </div>
            </div>

            <div class="card-body">
                <div>
                    <div class="card-rank">#${{String(it.rank).padStart(2, '0')}} &nbsp;|&nbsp; İlan No: #${{it.listing_id}}</div>
                    <h4 class="card-title" title="${{it.title}}">${{it.title}}</h4>
                    <div class="card-specs-row">
                        <span><i class="fas fa-ruler"></i> ${{it.m2}} m²</span>
                        <span><i class="fas fa-door-open"></i> ${{it.rooms}}</span>
                        <span><i class="fas fa-fire"></i> ${{it.heating.split(' ')[0]}}</span>
                    </div>
                </div>

                <div>
                    <div class="card-price-row">
                        <div class="card-price">${{it.price_formatted}}</div>
                        <div class="card-u-price">${{it.unit_m2_price}} TL/m²</div>
                    </div>
                    <a href="${{it.url}}" target="_blank" class="card-footer-btn">
                        <span>Sahibinden İlanı Aç</span>
                        <i class="fas fa-external-link-alt" style="font-size:10px;"></i>
                    </a>
                </div>
            </div>
        </article>
    `).join('');
}}

// Filter Listings
function filterListings(criteria, btn) {{
    document.querySelectorAll('.f-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    let filtered = [...RAW_DATASET];
    if (criteria === 'ours') {{
        filtered = filtered.filter(x => x.is_ours);
    }} else if (criteria === 'esyali') {{
        filtered = filtered.filter(x => x.is_esyali);
    }} else if (criteria === 'esyasiz') {{
        filtered = filtered.filter(x => !x.is_esyali);
    }} else if (criteria === '1+1') {{
        filtered = filtered.filter(x => x.rooms === '1+1');
    }} else if (criteria === '2+1') {{
        filtered = filtered.filter(x => x.rooms === '2+1');
    }} else if (criteria === '1+0') {{
        filtered = filtered.filter(x => x.rooms === '1+0');
    }} else if (criteria === 'mahall') {{
        filtered = filtered.filter(x => x.project.toLowerCase().includes('mahall'));
    }} else if (criteria === 'maidan') {{
        filtered = filtered.filter(x => x.project.toLowerCase().includes('maidan') || x.project.toLowerCase().includes('vega'));
    }}

    currentDataset = filtered;
    renderListings(currentDataset);
}}

// Search Filter
function searchListings(query) {{
    const q = query.toLowerCase().trim();
    if (!q) {{
        renderListings(currentDataset);
        return;
    }}
    const res = currentDataset.filter(x => 
        x.title.toLowerCase().includes(q) || 
        x.project.toLowerCase().includes(q) || 
        x.listing_id.includes(q) || 
        String(x.price).includes(q)
    );
    renderListings(res);
}}

// Sort Function
function sortListings(mode) {{
    let sorted = [...currentDataset];
    if (mode === 'price-asc') sorted.sort((a,b) => a.price - b.price);
    else if (mode === 'price-desc') sorted.sort((a,b) => b.price - a.price);
    else if (mode === 'm2-desc') sorted.sort((a,b) => b.m2 - a.m2);
    else if (mode === 'unit-asc') sorted.sort((a,b) => a.unit_m2_price - b.unit_m2_price);
    else sorted.sort((a,b) => a.rank - b.rank);
    currentDataset = sorted;
    renderListings(currentDataset);
}}

// Lightbox Handlers
function openLightbox(src) {{
    document.getElementById('lightboxImg').src = src;
    document.getElementById('lightbox').classList.add('active');
}}
function closeLightbox() {{
    document.getElementById('lightbox').classList.remove('active');
}}
document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') closeLightbox();
}});

// Initialize Charts
function initCharts() {{
    // Chart 1: Price Histogram
    const priceBins = ['35K-45K', '45K-55K (Biz)', '55K-65K', '65K-70K'];
    const binCounts = [
        RAW_DATASET.filter(x => x.price < 45000).length,
        RAW_DATASET.filter(x => x.price >= 45000 && x.price <= 55000).length,
        RAW_DATASET.filter(x => x.price > 55000 && x.price <= 65000).length,
        RAW_DATASET.filter(x => x.price > 65000).length,
    ];

    new Chart(document.getElementById('chartPriceHist'), {{
        type: 'bar',
        data: {{
            labels: priceBins,
            datasets: [{{
                label: 'İlan Sayısı',
                data: binCounts,
                backgroundColor: ['rgba(56,189,248,0.7)', 'rgba(212,175,55,0.9)', 'rgba(168,85,247,0.7)', 'rgba(244,63,94,0.7)'],
                borderColor: ['#38bdf8', '#d4af37', '#a855f7', '#f43f5e'],
                borderWidth: 1.5,
                borderRadius: 6
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                y: {{ ticks: {{ color: '#94a3b8', stepSize: 2 }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
            }}
        }}
    }});

    // Chart 2: Project Unit Price
    const projectNames = ['Vega Center', 'Maidan', 'Viole Ofis', 'Tepe Prime', 'Ofis İBK (Biz)', 'Mahall', 'Butik Plazalar'];
    const projectUnits = [1340, 1070, 954, 908, 846, 795, 746];

    new Chart(document.getElementById('chartProjectUnit'), {{
        type: 'bar',
        data: {{
            labels: projectNames,
            datasets: [{{
                label: 'Ortalama TL/m²',
                data: projectUnits,
                backgroundColor: ['#38bdf8', '#38bdf8', '#a855f7', '#a855f7', '#d4af37', '#10b981', '#64748b'],
                borderRadius: 6
            }}]
        }},
        options: {{
            responsive: true,
            indexAxis: 'y',
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                y: {{ ticks: {{ color: '#fff' }}, grid: {{ display: false }} }}
            }}
        }}
    }});

    // Chart 3: Furnished vs Unfurnished
    new Chart(document.getElementById('chartFurnished'), {{
        type: 'doughnut',
        data: {{
            labels: ['Eşyasız / Boş (33 İlan)', 'Full Eşyalı (Biz + Tepe Prime - 2 İlan)'],
            datasets: [{{
                data: [33, 2],
                backgroundColor: ['rgba(255,255,255,0.15)', '#d4af37'],
                borderColor: ['rgba(255,255,255,0.1)', '#aa7c11'],
                borderWidth: 2
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ position: 'bottom', labels: {{ color: '#cbd5e1', font: {{ size: 11 }} }} }}
            }}
        }}
    }});

    // Chart 4: Room Distribution
    new Chart(document.getElementById('chartRooms'), {{
        type: 'pie',
        data: {{
            labels: ['1+1 (17 İlan - Ort: 52.8K)', '2+1 (11 İlan - Ort: 58.7K)', '1+0 (7 İlan - Ort: 56.1K)'],
            datasets: [{{
                data: [17, 11, 7],
                backgroundColor: ['#10b981', '#38bdf8', '#a855f7'],
                borderWidth: 1.5,
                borderColor: '#05070b'
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{ position: 'bottom', labels: {{ color: '#cbd5e1', font: {{ size: 11 }} }} }}
            }}
        }}
    }});
}}

// Initialize
renderListings(RAW_DATASET);
initCharts();
</script>
</body>
</html>
"""

    with open(target_out, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"SUCCESS! Created {target_out} ({len(html_content)} bytes)")
    return str(target_out)

if __name__ == "__main__":
    generate_market_html()
