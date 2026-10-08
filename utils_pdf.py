from fpdf import FPDF
from io import BytesIO
import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN DE ESTILOS Y TEMA (BACKEND)
# ==========================================
COLOR_PRIMARY = (30, 41, 59)      # Azul Oscuro (#1e293b)
COLOR_SECONDARY = (226, 232, 240) # Gris Claro para Títulos
COLOR_ZEBRA = (248, 250, 252)     # Gris Fila Intercalada
COLOR_TEXT_MAIN = (15, 23, 42)    # Texto Principal
COLOR_TEXT_MUTED = (100, 116, 139) # Pie de página

FONT_FAMILY = "Helvetica"
SIZE_TITLE = 12
SIZE_SECTION = 10
SIZE_BODY = 9
SIZE_SMALL = 8

PAGE_MARGIN = 15
TOTAL_WIDTH = 180


class ModularPDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=PAGE_MARGIN)

    def header(self):
        self.set_fill_color(*COLOR_PRIMARY)
        self.set_text_color(255, 255, 255)
        self.set_font(FONT_FAMILY, "B", SIZE_TITLE)
        titulo = "  AUTOPERITO - REPORTE TÉCNICO DE COTIZACIÓN".encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 12, titulo, 0, 1, "L", fill=True)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font(FONT_FAMILY, "I", SIZE_SMALL)
        self.set_text_color(*COLOR_TEXT_MUTED)
        self.cell(0, 10, f"AutoPerito S.A.S. | Página {self.page_no()}", 0, 0, "C")

    def render_section_title(self, title: str):
        self.set_fill_color(*COLOR_SECONDARY)
        self.set_text_color(*COLOR_TEXT_MAIN)
        self.set_font(FONT_FAMILY, "B", SIZE_SECTION)
        texto = f"   {title.upper()}".encode('latin-1', 'replace').decode('latin-1')
        self.cell(TOTAL_WIDTH, 7, texto, 1, 1, "L", fill=True)

    def render_card_grid(self, fields: list[tuple[str, str]], cols: int = 3):
        self.set_font(FONT_FAMILY, "", SIZE_BODY)
        self.set_text_color(*COLOR_TEXT_MAIN)
        col_width = TOTAL_WIDTH / cols

        for i, (label, val) in enumerate(fields):
            border_flags = "L" if (i % cols == 0) else ("R" if ((i + 1) % cols == 0 or i == len(fields) - 1) else "")
            border_flags += "B"
            
            contenido = f" {label}: {val}".encode('latin-1', 'replace').decode('latin-1')
            self.cell(col_width, 7, contenido, border_flags, 0)
            
            if (i + 1) % cols == 0:
                self.ln()
                
        if len(fields) % cols != 0:
            self.ln()
        self.ln(4)


def formatear_fecha(fecha_str: str) -> str:
    if not fecha_str or fecha_str == 'N/A':
        return 'N/A'
    try:
        dt = datetime.datetime.fromisoformat(str(fecha_str).replace('Z', '+00:00'))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(fecha_str).split('T')[0]


def crear_pdf_binario(datos_vehiculo: dict, piezas: list, datos_cotizacion: dict = None) -> bytes:
    try:
        pdf = ModularPDFReport()
        pdf.add_page()
        
        # 1. INFORMACIÓN DE LA COTIZACIÓN
        pdf.render_section_title("Información de la Cotización")
        cotizacion_fields = [
            ("ID Cotización", str(datos_cotizacion.get('id', 'N/A')) if datos_cotizacion else 'N/A'),
            ("Fecha", formatear_fecha(datos_cotizacion.get('creado_en')) if datos_cotizacion else 'N/A'),
            ("Estado", str(datos_cotizacion.get('estado', 'En espera')).capitalize() if datos_cotizacion else 'N/A'),
            ("Observaciones", str(datos_cotizacion.get('observaciones', 'Ninguna')).capitalize() if datos_cotizacion else 'Ninguna'),
        ]
        pdf.render_card_grid(cotizacion_fields, cols=2)

        # 2. DATOS DEL VEHÍCULO
        pdf.render_section_title("Descripción del Vehículo Evaluado")
        vehiculo_fields = [
            ("Placa", str(datos_vehiculo.get('placa', 'N/A')).upper() if datos_vehiculo else 'N/A'),
            ("Marca", str(datos_vehiculo.get('marca', 'N/A')).capitalize() if datos_vehiculo else 'N/A'),
            ("Modelo", str(datos_vehiculo.get('modelo', 'N/A')).capitalize() if datos_vehiculo else 'N/A'),
            ("Color", str(datos_vehiculo.get('color', 'N/A')).capitalize() if datos_vehiculo else 'N/A'),
        ]
        pdf.render_card_grid(vehiculo_fields, cols=4)

        # 3. TABLA DE PIEZAS Y COSTOS
        pdf.render_section_title("Detalle de Piezas y Costos")
        
        pdf.set_fill_color(*COLOR_ZEBRA)
        pdf.set_font(FONT_FAMILY, "B", SIZE_SMALL)
        pdf.cell(75, 7, "  DESCRIPCIÓN DEL TRABAJO / PIEZA".encode('latin-1', 'replace').decode('latin-1'), 1, 0, "L", fill=True)
        pdf.cell(35, 7, "REPUESTO", 1, 0, "C", fill=True)
        pdf.cell(35, 7, "MANO DE OBRA", 1, 0, "C", fill=True)
        pdf.cell(35, 7, "SUBTOTAL", 1, 1, "C", fill=True)

        pdf.set_font(FONT_FAMILY, "", SIZE_SMALL)
        total_general = 0.0

        if piezas and len(piezas) > 0:
            for p in piezas:
                repuesto = float(p.get('precio_unit_repuesto') or 0)
                mano_obra = float(p.get('precio_unit_mano_obra') or 0)
                pintura = float(p.get('precio_unit_pintura') or 0)
                subtotal = repuesto + mano_obra + pintura
                total_general += subtotal

                desc = str(p.get('descripcion', 'Pieza sin descripción')).capitalize()[:40]
                desc_encoded = f"  {desc}".encode('latin-1', 'replace').decode('latin-1')

                pdf.cell(75, 6, desc_encoded, 1, 0, "L")
                pdf.cell(35, 6, f"${repuesto:,.0f}", 1, 0, "R")
                pdf.cell(35, 6, f"${mano_obra:,.0f}", 1, 0, "R")
                pdf.cell(35, 6, f"${subtotal:,.0f}", 1, 1, "R")
        else:
            msg = "Sin piezas o servicios registrados para esta cotización.".encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(TOTAL_WIDTH, 7, msg, 1, 1, "C")

        # Fila Total General
        pdf.set_font(FONT_FAMILY, "B", SIZE_BODY)
        pdf.set_fill_color(*COLOR_ZEBRA)
        lbl_total = "TOTAL GENERAL DE LA VALORACIÓN:  ".encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(145, 8, lbl_total, 1, 0, "R", fill=True)
        pdf.cell(35, 8, f"${total_general:,.0f}", 1, 1, "R", fill=True)

        # Generación de Bytes
        buffer = BytesIO()
        pdf.output(buffer)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    except Exception as e:
        logger.error(f"Error generando PDF: {str(e)}")
        raise RuntimeError(f"Error en PDF: {str(e)}")