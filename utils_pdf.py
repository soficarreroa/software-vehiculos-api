from fpdf import FPDF
import datetime

AZUL_OSCURO   = (15,  55,  100)
AZUL_MEDIO    = (30,  90,  160)
AZUL_CLARO    = (220, 235, 255)
GRIS_OSCURO   = (60,  60,   70)
GRIS_MEDIO    = (130, 130, 140)
GRIS_CLARO    = (240, 242, 245)
BLANCO        = (255, 255, 255)
ACENTO_AZUL   = (0,  120, 215)


class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        self.margen_tabla_izq = 15
        self.margen_tabla_der = 15

    def header(self):
        self.set_fill_color(*AZUL_OSCURO)
        self.rect(0, 0, 210, 28, style="F")

        self.set_fill_color(*ACENTO_AZUL)
        self.rect(0, 27, 210, 2, style="F")  

        self.set_xy(10, 4)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*BLANCO)
        self.cell(130, 10, "AutoPerito", ln=False, align="L")

        fecha = datetime.date.today().strftime("%d / %m / %Y")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 210, 255)
        self.cell(0, 10, f"Fecha: {fecha}", ln=True, align="R")

        self.set_x(10)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(180, 210, 255)
        self.cell(0, 6, "Reporte Tecnico de Peritaje Automotriz", ln=True, align="L")

        self.ln(8)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*AZUL_MEDIO)
        self.set_line_width(0.4)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(1)

        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GRIS_MEDIO)
        self.cell(0, 5, "AutoPerito  |  Documento confidencial", align="L")
        self.cell(0, 5, f"Pagina {self.page_no()}", align="R")

    def _seccion_titulo(self, icono: str, titulo: str):
        self.ln(6)
        y = self.get_y()
        self.set_fill_color(*ACENTO_AZUL)
        self.rect(10, y, 3, 10, style="F")

        self.set_xy(15, y + 1)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*AZUL_MEDIO)
        self.cell(0, 8, f"  {icono}  {titulo}", ln=True)

        self.set_draw_color(*AZUL_CLARO)
        self.set_line_width(0.3)
        self.line(10, self.get_y() + 1, 200, self.get_y() + 1)
        self.ln(5)

    def _campo_info(self, etiqueta: str, valor: str):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*GRIS_OSCURO)
        self.cell(45, 7, etiqueta + ":", border=0)

        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GRIS_MEDIO)
        self.cell(0, 7, valor, border=0, ln=True)


def crear_pdf_binario(datos_vehiculo: dict, piezas: list) -> bytes:
    pdf = PDFReport()
    pdf.add_page()

    pdf._seccion_titulo("*", "Informacion del Vehiculo")

    card_y = pdf.get_y()
    pdf.set_fill_color(*GRIS_CLARO)
    pdf.rect(10, card_y, 190, 38, style="F")
    pdf.set_xy(14, card_y + 2)

    campos_izq = [
        ("Placa",     datos_vehiculo.get("placa",     "No disponible")),
        ("Marca",     datos_vehiculo.get("marca",     "No disponible")),
        ("Modelo",    datos_vehiculo.get("modelo",    "No disponible")),
    ]
    campos_der = [
        ("Año",      str(datos_vehiculo.get("año",      "No disponible"))),
        ("Color",     datos_vehiculo.get("color",     "No disponible")),
        ("VIN / Serie", datos_vehiculo.get("vin",     "No disponible")),
    ]

    for (etq_i, val_i), (etq_d, val_d) in zip(campos_izq, campos_der):
        y_actual = pdf.get_y()
        pdf.set_x(14)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*GRIS_OSCURO)
        pdf.cell(28, 6, etq_i + ":", border=0)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRIS_MEDIO)
        pdf.cell(67, 6, val_i, border=0)

        pdf.set_xy(14 + 95, y_actual)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*GRIS_OSCURO)
        pdf.cell(35, 6, etq_d + ":", border=0)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GRIS_MEDIO)
        pdf.cell(0, 6, val_d, border=0, ln=True)

    pdf.ln(5)

    pdf._seccion_titulo("#", "Detalle de Piezas y Costos")

    ancho_disponible = 210 - pdf.margen_tabla_izq - pdf.margen_tabla_der
    COL = [
        ancho_disponible * 0.45,
        ancho_disponible * 0.18,
        ancho_disponible * 0.18,
        ancho_disponible * 0.19
    ]
    
    ENCABEZADOS = ["Pieza / Componente", "Precio Repuesto", "Mano de Obra", "Subtotal"]

    pdf.set_fill_color(*AZUL_OSCURO)
    pdf.set_text_color(*BLANCO)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_draw_color(*AZUL_MEDIO)
    pdf.set_line_width(0)

    pdf.set_x(pdf.margen_tabla_izq)
    for w, enc in zip(COL, ENCABEZADOS):
        pdf.cell(w, 9, enc, border=0, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_draw_color(*AZUL_CLARO)
    pdf.set_line_width(0.1)

    total_repuestos = 0
    total_mano_obra = 0

    for i, p in enumerate(piezas):
        nombre  = str(p.get("nombre_pieza")              or "Repuesto")
        pr_rep  = float(p.get("precio_unit_repuesto")    or 0)
        pr_mo   = float(p.get("precio_unit_mano_obra")   or 0)
        subtotal = pr_rep + pr_mo
        total_repuestos += pr_rep
        total_mano_obra += pr_mo

        if i % 2 == 0:
            pdf.set_fill_color(*GRIS_CLARO)
        else:
            pdf.set_fill_color(*AZUL_CLARO)
        pdf.set_text_color(*GRIS_OSCURO)

        pdf.set_x(pdf.margen_tabla_izq)
        pdf.cell(COL[0], 8, nombre,                 border="B", fill=True, align="L")
        pdf.cell(COL[1], 8, f"$ {pr_rep:,.2f}",    border="B", fill=True, align="R")
        pdf.cell(COL[2], 8, f"$ {pr_mo:,.2f}",     border="B", fill=True, align="R")
        pdf.cell(COL[3], 8, f"$ {subtotal:,.2f}",  border="B", fill=True, align="R")
        pdf.ln()

    pdf.ln(3)
    total_general = total_repuestos + total_mano_obra
    pdf.set_fill_color(*AZUL_OSCURO)
    pdf.set_text_color(*BLANCO)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(pdf.margen_tabla_izq)
    pdf.cell(COL[0], 9, "TOTAL GENERAL",             border=0, fill=True, align="L")
    pdf.cell(COL[1], 9, f"$ {total_repuestos:,.2f}", border=0, fill=True, align="R")
    pdf.cell(COL[2], 9, f"$ {total_mano_obra:,.2f}", border=0, fill=True, align="R")
    pdf.cell(COL[3], 9, f"$ {total_general:,.2f}",  border=0, fill=True, align="R")
    pdf.ln(10)

    pdf._seccion_titulo("!", "Observaciones")

    observaciones = datos_vehiculo.get("observaciones", "Sin observaciones adicionales.")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRIS_OSCURO)
    pdf.set_x(14)
    pdf.multi_cell(186, 6, str(observaciones), border=0)
    pdf.ln(8)

    if pdf.get_y() > 230:
        pdf.add_page()
    else:
        pdf.ln(6)

    pdf._seccion_titulo("~", "Validacion y Firma")

    firma_y = pdf.get_y() + 2
    firma_ancho = 85

    pdf.set_fill_color(*GRIS_CLARO)
    pdf.rect(14, firma_y, firma_ancho, 38, style="F")
    pdf.set_draw_color(*AZUL_MEDIO)
    pdf.set_line_width(0.3)
    pdf.line(20, firma_y + 25, 14 + firma_ancho - 6, firma_y + 25)

    pdf.set_xy(14, firma_y + 27)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRIS_OSCURO)
    pdf.cell(firma_ancho, 5, "Perito Automotriz Certificado", align="C", ln=True)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRIS_MEDIO)
    pdf.cell(firma_ancho, 4,
             f"ID: {datos_vehiculo.get('id_perito', '_______________')}",
             align="C", ln=True)

    cx = 14 + firma_ancho + 16
    pdf.set_fill_color(*GRIS_CLARO)
    pdf.rect(cx, firma_y, firma_ancho, 38, style="F")
    pdf.line(cx + 6, firma_y + 25, cx + firma_ancho - 6, firma_y + 25)

    pdf.set_xy(cx, firma_y + 27)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*GRIS_OSCURO)
    pdf.cell(firma_ancho, 5, "Propietario del Vehiculo", align="C", ln=True)
    pdf.set_x(cx)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*GRIS_MEDIO)
    pdf.cell(firma_ancho, 4,
             f"C.C.: {datos_vehiculo.get('cedula_propietario', '_______________')}",
             align="C", ln=True)

    pdf.set_xy(14, firma_y + 42)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*GRIS_MEDIO)
    pdf.cell(0, 5,
             f"Documento generado electronicamente el "
             f"{datetime.datetime.now().strftime('%d/%m/%Y a las %H:%M')} hrs.",
             align="C")

    return bytes(pdf.output())