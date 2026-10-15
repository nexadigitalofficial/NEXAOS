r"""
Interactive GIS Map Generator Module
Folium kullanarak mülk merkezli, yarıçap çemberli ve sektörel renk kodlu interaktif HTML harita üretir.
Çıktı: C:\Users\USER\Desktop\SATTIM\PAZARLAMA\INCEK_TICARI_HEDEF_HARITASI.html
"""

import os
import folium
from folium import plugins

# Default Anchor Coordinates (İncek LÖSANTE Karşısı Ticari Mülk)
ANCHOR_LAT = 39.8245
ANCHOR_LON = 32.7485

SECTOR_COLORS = {
    "Sağlık & Medikal": {"color": "red", "icon": "heart-pulse", "prefix": "fa"},
    "Ağız ve Diş Sağlığı": {"color": "blue", "icon": "tooth", "prefix": "fa"},
    "Plastik & Estetik Cerrahi": {"color": "purple", "icon": "wand-magic-sparkles", "prefix": "fa"},
    "Fizik Tedavi & Rehabilitasyon": {"color": "orange", "icon": "person-walking", "prefix": "fa"},
    "Özel Eğitim & Kolejler": {"color": "green", "icon": "graduation-cap", "prefix": "fa"},
    "Savunma Sanayii": {"color": "darkblue", "icon": "shield-halved", "prefix": "fa"},
    "Bilişim & Yazılım": {"color": "cadetblue", "icon": "laptop-code", "prefix": "fa"},
    "Prestij Hukuk": {"color": "darkred", "icon": "scale-balanced", "prefix": "fa"},
    "Bağımsız Denetim & YMM": {"color": "darkgreen", "icon": "file-invoice-dollar", "prefix": "fa"},
    "Diplomatik Misyon": {"color": "black", "icon": "landmark-flag", "prefix": "fa"},
    "Kurumsal Merkez": {"color": "gray", "icon": "building", "prefix": "fa"}
}

def generate_interactive_map(leads_data, output_html_path, anchor_lat=ANCHOR_LAT, anchor_lon=ANCHOR_LON):
    """Verilen kurum listesini zenginleştirilmiş interaktif haritaya döker."""
    os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)
    
    # 1. Base Map (OpenStreetMap clean public tiles)
    m = folium.Map(
        location=[anchor_lat, anchor_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True
    )
    
    # Add Google Hybrid Satellite as alternative tile
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        attr="Google Uydu",
        name="Google Hibrit Uydu"
    ).add_to(m)
    
    # 2. Concentric Distance Rings (1 km, 3 km, 5 km, 10 km)
    rings = [
        (1000, "#EF4444", "1 km - Yürüme Mesafesi Kuşağı", 1),
        (3000, "#F59E0B", "3 km - Doğrudan İncek Sağlık & Eğitim Aksı", 2),
        (5000, "#3B82F6", "5 km - Beytepe & Çayyolu Entegrasyon Kuşağı", 2),
        (10000, "#6B7280", "10 km - Çevre Yolu & Bölgesel Etki Alanı", 1)
    ]
    
    rings_group = folium.FeatureGroup(name="Mesafe Yarıçap Çemberleri", show=True)
    for radius, color, label, weight in rings:
        folium.Circle(
            location=[anchor_lat, anchor_lon],
            radius=radius,
            color=color,
            weight=weight,
            fill=True,
            fill_opacity=0.04,
            popup=label,
            tooltip=label
        ).add_to(rings_group)
    rings_group.add_to(m)
    
    # 3. Anchor Property Marker (Our Commercial Villa)
    anchor_html = """
    <div style="font-family: 'Segoe UI', Arial; width: 320px; padding: 12px; border-radius: 8px;">
        <div style="background-color: #1B365D; color: white; padding: 10px; border-radius: 6px; text-align: center;">
            <h4 style="margin: 0; font-size: 15px; font-weight: bold;">⭐ SATILIK TİCARİ MÜLKİYET</h4>
            <div style="font-size: 11px; margin-top: 3px; color: #C5A059;">Ada 119464 Parsel 13 | Köşe Parsel</div>
        </div>
        <div style="margin-top: 10px; font-size: 12px; line-height: 1.5; color: #1E293B;">
            <b>📍 Konum:</b> LÖSANTE Hastanesi Tam Karşısı (Kızılcaşar Mah. 2705. Cad. No:23)<br>
            <b>⚖️ Hukuki Statü:</b> <span style="background: #DCFCE7; color: #166534; padding: 2px 5px; border-radius: 4px; font-weight: bold;">Tescilli TİCARİ YKB (C278DFHU)</span><br>
            <b>📐 Alan:</b> 398 m² Arsa | ~420 m² Brüt Kapalı Alan (4 Kat)<br>
            <b>🏗️ Özellikler:</b> Dikey Asansör Şaftı, Çift Giriş, 10 Ton Su Deposu, Kapalı Garaj, Şömineler, Kış Bahçesi<br>
            <b>🔗 Resmi İlan:</b> <a href="https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/" target="_blank" style="color: #0284c7; font-weight: bold; text-decoration: underline;">Sahibinden İlanını İncele</a><br>
            <div style="margin-top: 8px; border-top: 1px solid #E2E8F0; padding-top: 6px; font-size: 11px; color: #64748B;">
                <b>Yetkili Danışman:</b> Yiğit Narin | Coldwell Banker VIP<br>
                <b>İletişim:</b> 0532 451 40 08
            </div>
        </div>
    </div>
    """
    
    folium.Marker(
        location=[anchor_lat, anchor_lon],
        popup=folium.Popup(anchor_html, max_width=350),
        tooltip="⭐ SATILIK MÜLK: İncek LÖSANTE Karşısı Tescilli Ticari Malikâne",
        icon=folium.Icon(color="red", icon="star", prefix="fa")
    ).add_to(m)
    
    # 4. Sector Feature Groups
    sector_groups = {}
    for s_name in SECTOR_COLORS.keys():
        sector_groups[s_name] = folium.FeatureGroup(name=f"{s_name}", show=True)
        
    other_group = folium.FeatureGroup(name="Diğer Kurumlar", show=True)
    
    # 5. Add Each Lead as a Marker
    marker_count = 0
    for lead in leads_data:
        coords_str = lead.get("koordinatlar", "")
        lat, lon = None, None
        if coords_str and coords_str != "N/A" and "," in coords_str:
            try:
                parts = coords_str.split(",")
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
            except Exception:
                continue
                
        if lat is None or lon is None:
            continue
            
        name = lead.get("kurum_adi", "İsimsiz Kurum")
        sector = lead.get("is_kolu", "Kurumsal Merkez")
        cat = lead.get("ana_kategori", "")
        phone = lead.get("telefon", "N/A")
        email = lead.get("eposta", "N/A")
        website = lead.get("web_sitesi", "")
        dist = lead.get("mesafe_km", "")
        dist_str = f"{dist} km" if dist else "N/A"
        prio = lead.get("oncelik", "B+")
        hbu = lead.get("hbu_model", "Ticari Yerleşke")
        maps_url = lead.get("maps_url", "#")
        
        # WhatsApp URL
        clean_phone = lead.get("telefon_wa", "")
        if not clean_phone:
            from modules.enrichment import clean_phone_for_whatsapp
            clean_phone = clean_phone_for_whatsapp(phone)
            
        wa_btn = ""
        if clean_phone:
            wa_url = f"https://wa.me/{clean_phone}?text=Merhaba%20{name}%20Yetkilisi,%20İncek%20LÖSANTE%20karşısındaki%20ticari%20mülkümüz%20hakkında%20bilgilendirme%20yapmak%20isteriz."
            wa_btn = f"""
            <a href="{wa_url}" target="_blank" style="display: inline-block; background-color: #25D366; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none; font-size: 11px; font-weight: bold; margin-top: 6px;">
                💬 WhatsApp Mesajı Başlat
            </a>
            """
            
        web_btn = ""
        if website and website != "N/A":
            web_btn = f"""
            <a href="{website}" target="_blank" style="display: inline-block; background-color: #0284C7; color: white; padding: 5px 10px; border-radius: 5px; text-decoration: none; font-size: 11px; margin-top: 6px; margin-right: 5px;">
                🌐 Web Sitesi
            </a>
            """
            
        prio_color = "#DC2626" if prio == "A+" else ("#D97706" if prio == "A" else "#2563EB")
        
        popup_content = f"""
        <div style="font-family: 'Segoe UI', Arial; width: 280px; padding: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #E2E8F0; padding-bottom: 6px;">
                <span style="font-size: 11px; font-weight: bold; color: #64748B;">{sector}</span>
                <span style="background: {prio_color}; color: white; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 4px;">{prio} Öncelik</span>
            </div>
            <h4 style="margin: 8px 0 4px 0; font-size: 14px; font-weight: bold; color: #1E293B;">{name}</h4>
            <div style="font-size: 11px; color: #475569; line-height: 1.4;">
                <b>📍 Mesafe:</b> <span style="color: #DC2626; font-weight: bold;">{dist_str}</span> (LÖSANTE Karşısına)<br>
                <b>📞 Telefon:</b> {phone}<br>
                <b>✉️ E-Posta:</b> {email}<br>
                <b>🏢 Hedef Model:</b> {hbu}<br>
            </div>
            <div style="margin-top: 8px;">
                {web_btn}
                {wa_btn}
            </div>
        </div>
        """
        
        # Color styling
        style_info = SECTOR_COLORS.get(sector, {"color": "blue", "icon": "building", "prefix": "fa"})
        
        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_content, max_width=320),
            tooltip=f"{name} ({dist_str} - {prio})",
            icon=folium.Icon(color=style_info["color"], icon=style_info["icon"], prefix=style_info["prefix"])
        )
        
        if sector in sector_groups:
            marker.add_to(sector_groups[sector])
        else:
            marker.add_to(other_group)
        marker_count += 1
        
    # Add non-empty sector groups to map
    for s_name, grp in sector_groups.items():
        grp.add_to(m)
    other_group.add_to(m)
    
    # 6. Map Enhancements
    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen(position="topright", title="Tam Ekran", force_separate_button=True).add_to(m)
    plugins.LocateControl(position="topright").add_to(m)
    
    # Floating Title Card
    title_html = """
    <div style="position: fixed; 
                bottom: 25px; left: 25px; width: 340px; height: auto; 
                background-color: white; border: 2px solid #1B365D; border-radius: 8px; z-index: 9999; 
                padding: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); font-family: 'Segoe UI', Arial;">
        <div style="font-weight: bold; font-size: 13px; color: #1B365D;">
            🏢 İNCEK TİCARİ MÜLK HEDEF MÜŞTERİ HARİTASI
        </div>
        <div style="font-size: 11px; color: #64748B; margin-top: 4px;">
            Merkez: LÖSANTE Karşısı Ticari Malikâne (398 m² - YKB TİCARİ)<br>
            Taranan Toplam Hedef Kurum: <b>""" + str(marker_count) + """ Adet</b><br>
            Çemberler: 1 km (Yürüme), 3 km (Doğrudan Aks), 5 km, 10 km
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    
    m.save(output_html_path)
    print(f"[HARITA URETILDI] Interaktif Harita: {output_html_path} ({marker_count} Kurum Islendi)")
    return output_html_path
