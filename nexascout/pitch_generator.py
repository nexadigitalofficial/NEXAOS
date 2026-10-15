r"""
AI-Powered Personalized Pitch & Investment Proposal Generator Module
Her hedef kuruma özel kişiselleştirilmiş Word (.docx) yatırım teklif mektubu üretir.
Çıktı: C:\Users\USER\Desktop\SATTIM\PAZARLAMA\TEKLIF_MEKTUPLARI\[Kurum_Adi]_VIP_Teklif.docx
"""

import os
import re
from datetime import datetime
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

OUTPUT_DIR = r"C:\Users\USER\Desktop\SATTIM\PAZARLAMA\TEKLIF_MEKTUPLARI"

def set_cell_background(cell, hex_color):
    """Tablo hücresinin arka plan rengini ayarlar."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def sanitize_filename(name):
    """Dosya adı için geçersiz karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def generate_pitch_document(lead_data, output_dir=OUTPUT_DIR):
    """Tek bir kurum için kişiselleştirilmiş Word (.docx) teklif dosyası oluşturur."""
    os.makedirs(output_dir, exist_ok=True)
    
    kurum_adi = lead_data.get("kurum_adi", "Değerli Kurum")
    sektor = lead_data.get("is_kolu", "Kurumsal")
    mesafe = lead_data.get("mesafe_km", "")
    mesafe_str = f"{mesafe} km" if mesafe else "birkaç dakika"
    hbu_model = lead_data.get("hbu_model", "Müstakil Şirket Genel Merkezi")
    
    doc = docx.Document()
    
    # Sayfa Kenar Boşlukları
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        
    # 1. Header Banner
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_conf = header_para.add_run("[KURUMA ÖZEL STRATEJİK YATIRIM TEKLİFİ]\n")
    run_conf.font.size = Pt(9)
    run_conf.font.bold = True
    run_conf.font.color.rgb = RGBColor(180, 0, 0)
    
    run_cb = header_para.add_run("COLDWELL BANKER VIP REAL GAYRİMENKUL DANIŞMANLIĞI")
    run_cb.font.size = Pt(9)
    run_cb.font.color.rgb = RGBColor(100, 116, 139)
    
    # 2. Document Title
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run_title = title_para.add_run("STRATEJİK GAYRİMENKUL YATIRIM VE BÜYÜME SUNUMU")
    run_title.font.name = "Segoe UI"
    run_title.font.size = Pt(16)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(27, 54, 93) # Navy Dark
    
    sub_para = doc.add_paragraph()
    run_sub = sub_para.add_run("Ankara İncek / LÖSANTE Hastanesi Karşısı Tescilli 'TİCARİ' Müstakil Malikâne")
    run_sub.font.name = "Segoe UI"
    run_sub.font.size = Pt(11)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(197, 160, 89) # Gold Accent
    
    # Divider
    p_div = doc.add_paragraph()
    run_div = p_div.add_run("—" * 55)
    run_div.font.color.rgb = RGBColor(209, 213, 219)
    
    # 3. Addressee Block
    addr_para = doc.add_paragraph()
    run_to = addr_para.add_run(f"Sayın {kurum_adi} Yönetim Kurulu Başkanlığı / Genel Müdürlüğü,\n")
    run_to.font.name = "Segoe UI"
    run_to.font.size = Pt(11)
    run_to.font.bold = True
    run_to.font.color.rgb = RGBColor(15, 23, 42)
    
    # 4. Personalized Body Text
    body_para = doc.add_paragraph()
    body_para.paragraph_format.line_spacing = 1.15
    body_para.paragraph_format.space_after = Pt(10)
    
    p1 = (
        f"Ankara'nın en yüksek alım gücüne ve sağlık-eğitim çekim gücüne sahip İncek bölgesinde faaliyet gösteren "
        f"saygın kurumunuz için, mevcut lokasyonunuza yalnızca {mesafe_str} mesafede yer alan, "
        f"bölgesel tekel niteliğindeki emsalsiz bir ticari mülkiyeti dikkatinize sunmaktan onur duyarız.\n\n"
        f"Bildiğiniz üzere İncek aksındaki villaların %95'i yalnızca 'Mesken' (Konut) ruhsatına sahip olup, "
        f"Kat Mülkiyeti Kanunu ve bölge imar plan notları gereği ticari işletmeye açılmaları yasal olarak imkansızdır. "
        f"Sunumunu gerçekleştirdiğimiz bu özel taşınmaz ise, Çevre ve Şehircilik Bakanlığı tarafından tescil edilmiş "
        f"resmi 'TİCARİ' Yapı Kayıt Belgesi'ne (C278DFHU) sahip bölgedeki TEK müstakil gayrimenkuldür."
    )
    r1 = body_para.add_run(p1)
    r1.font.name = "Segoe UI"
    r1.font.size = Pt(10)
    
    # 5. Tailored Synergy Section based on Sector
    doc.add_heading("Neden Kurumunuz İçin Kusursuz Bir Büyüme Fırsatı?", level=2)
    
    syn_para = doc.add_paragraph()
    syn_para.paragraph_format.line_spacing = 1.15
    
    if "Diş" in sektor or "Ağız" in sektor:
        syn_text = (
            "• Odaların Islak Hacim Dağılımı: 4 kata yayılan yaygın banyo ve sıhhi tesisat altyapısı sayesinde "
            "her odaya minimum kırma-dökme maliyetiyle diş üniti kurulabilir.\n"
            "• Hazır Asansör Şaftı: Bodrumdan çatıya kesintisiz asansör kovası hazır olup sedye/insan asansörü hemen takılabilir.\n"
            "• Çift Bağımsız Giriş: Hasta kabul girişi ile doktor/personel girişi mimari olarak birbirinden bağımsızdır.\n"
            "• Otopark ve Tabela Değeri: İki yola cepheli köşe parsel konumu ve bina önünde 15 araçlık açık otopark konforu."
        )
    elif "Sağlık" in sektor or "Tıp" in sektor or "Cerrahi" in sektor:
        syn_text = (
            "• LÖSANTE Karşısı Doğrudan Hasta Trafiği: Çocuk ve Yetişkin LÖSANTE Hastanesi ile eczaneler kümelenmesinin tam odağındadır.\n"
            "• Kesintisiz Altyapı: 10 tonluk hidroforlu su deposu ve LÖSANTE ile aynı şebekeden gelen kesintisiz elektrik hattı.\n"
            "• 8-11 Muayene Odası Kapasitesi: Hafif bölücü sistemlerle 11 bağımsız poliklinik odasına kolayca dönüştürülebilir.\n"
            "• Doğrudan Ruhsatlandırma: Sağlık Bakanlığı ve belediye nezdinde bürokratik engele takılmaksızın poliklinik ruhsatı almaya haizdir."
        )
    elif "Eğitim" in sektor or "Kolej" in sektor or "Okul" in sektor:
        syn_text = (
            "• Müstakil Kampüs ve Bahçe: 398 m² arsa üzerinde yüksek çevre duvarlarıyla korunaklı, güvenli bahçe alanı.\n"
            "• 4 Katlı Esnek Hacim: Sitedeki tek serbest mimari proje; geniş salonlar yemekhane ve kapalı oyun alanına tam uygundur.\n"
            "• Kış Bahçesi ve Botanik Bahçe: 21 yıllık yetişkin meyve ağaçları ve cam kaplı ısıtmalı kış bahçesi doğal atölye imkanı sunar.\n"
            "• Ulaşım ve Servis Rahatlığı: Geniş çift yönlü cadde sayesinde okul servislerinin yanaşması ve parklanması son derece rahattır."
        )
    else: # Savunma / Kurumsal
        syn_text = (
            "• Otoyol Entegrasyonu: Ankara Çevre Yolu'na (O-20) yalnızca 1 km mesafede; şehir merkezine ve havaalanına ışıksız hızlı ulaşım.\n"
            "• Yüksek Güvenlik ve Gizlilik: Yüksek istinat duvarları, dışarıdan görünmeyen bahçe ve bağımsız kot katı veri merkezi kurulumuna uygundur.\n"
            "• Zamansız Taş Mimari: Özel kahverengi doğal taş kaplamasıyla şirket genel merkezine ağırbaşlı ve kurumsal köşk kimliği kazandırır.\n"
            "• Çift Salon ve Şömineler: Üst düzey yönetim kurulu toplantıları ve uluslararası heyet ağırlamaları için prestijli yaşam hacmi."
        )
    r_syn = syn_para.add_run(syn_text)
    r_syn.font.name = "Segoe UI"
    r_syn.font.size = Pt(10)
    
    # 6. Technical Specifications Table
    doc.add_heading("Portföy Teknik ve Kurumsal Künyesi", level=2)
    
    specs = [
        ("Konum ve Adres", "Ankara / Gölbaşı / Kızılcaşar Mah. 2705. Cad. No:23 (LÖSANTE Karşısı)"),
        ("Kadastral Durum", "Ada 119464 Parsel 13 (Tam Köşe Parsel - İki Yola Cepheli)"),
        ("Arsa / Kapalı Alan", "398,00 m² Müstakil Arsa | ~420 m² Brüt Kapalı Alan (4 Kat)"),
        ("Resmi Hukuki Nitelik", "TİCARİ - T.C. Çevre ve Şehircilik Bakanlığı Yapı Kayıt Belgesi (C278DFHU)"),
        ("Teknik Donanım", "Dikey Asansör Şaftı, 10 Ton Su Deposu, 2 Şömine, Kış Bahçesi, Kapalı Garaj"),
        ("Resmi İlan Bağlantısı", "https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/")
    ]
    
    table = doc.add_table(rows=len(specs), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    for r_i, (lbl, val) in enumerate(specs):
        cell_lbl = table.cell(r_i, 0)
        cell_val = table.cell(r_i, 1)
        
        cell_lbl.width = Inches(2.2)
        cell_val.width = Inches(4.5)
        
        cell_lbl.text = lbl
        cell_val.text = val
        
        set_cell_background(cell_lbl, "F1F5F9")
        set_cell_background(cell_val, "FFFFFF")
        
        for p in cell_lbl.paragraphs:
            p.runs[0].font.name = "Segoe UI"
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.bold = True
            p.runs[0].font.color.rgb = RGBColor(30, 41, 59)
            
        for p in cell_val.paragraphs:
            p.runs[0].font.name = "Segoe UI"
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.color.rgb = RGBColor(15, 23, 42)
            
    # 7. Sign-off
    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(15)
    r_sign = p_sign.add_run(
        "Saygılarımızla,\n"
        "Yiğit Narin | Coldwell Banker VIP Real Gayrimenkul\n"
        "İletişim: 0532 451 40 08\n"
        "Ofis Adresi: Santra Royal Rezidans Ofisleri No: 2C/4 Çayyolu / Ankara\n"
        "İlan Detayı: https://www.sahibinden.com/ilan/emlak-is-yeri-satilik-kizilcasar-losante-karsisi-kose-parsel-ticari-satilik-bina-1343884633/detay/"
    )
    r_sign.font.name = "Segoe UI"
    r_sign.font.size = Pt(10)
    r_sign.font.bold = True
    r_sign.font.color.rgb = RGBColor(27, 54, 93)
    
    clean_name = sanitize_filename(kurum_adi)[:40]
    out_file = os.path.join(output_dir, f"{clean_name}_VIP_Yatirim_Teklifi.docx")
    try:
        doc.save(out_file)
    except PermissionError:
        import time
        time.sleep(0.5)
        doc.save(out_file)

    # Save TXT version as well
    txt_file = os.path.join(output_dir, f"{clean_name}_VIP_Yatirim_Teklifi.txt")
    try:
        lines = []
        for element in doc.element.body:
            if element.tag.endswith('p'):
                p = docx.text.paragraph.Paragraph(element, doc)
                txt = p.text.strip()
                if txt:
                    lines.append(txt)
            elif element.tag.endswith('tbl'):
                t = docx.table.Table(element, doc)
                lines.append("")
                lines.append("=" * 65)
                for row in t.rows:
                    if len(row.cells) >= 2:
                        lbl = row.cells[0].text.strip()
                        val = row.cells[1].text.strip()
                        lines.append(f"  • {lbl:<22}: {val}")
                lines.append("=" * 65)
                lines.append("")
        with open(txt_file, "w", encoding="utf-8") as f_txt:
            f_txt.write("\n".join(lines))
    except Exception:
        pass

    return out_file
