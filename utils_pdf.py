from fpdf import FPDF

class PDFReport(FPDF):
    def header(self):
        # Configuración del encabezado profesional
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "AutoPerito - Reporte Técnico de Valoración", ln=True, align="C")
        self.set_font("Arial", "I", 10)
        self.cell(0, 10, "Evidencia técnica para conciliación y seguros", ln=True, align="C")
        self.ln(5)

    def footer(self):
        # Pie de página con marco legal
        self.set_y(-25)
        self.set_font("Arial", "I", 8)
        self.multi_cell(0, 5, "Basado en la Ley 2251 de 2022 (Choques Simples) y el Código Civil Colombiano. "
                             "Este documento es una estimación técnica basada en los daños visuales reportados.", align="C")
        self.set_y(-10)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

def crear_pdf_binario(datos_vehiculo, piezas):
    pdf = PDFReport()
    pdf.add_page()
    
    # Sección del Vehículo
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "1. Información del Vehículo", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 7, f"Placa: {datos_vehiculo['placa']}", ln=True)
    pdf.cell(0, 7, f"Marca y Modelo: {datos_vehiculo['marca']} {datos_vehiculo['modelo']}", ln=True)
    pdf.ln(5)

    # Sección de Daños
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "2. Detalle de Daños y Presupuesto", ln=True)
    
    # Encabezados de tabla
    pdf.set_fill_color(200, 200, 200)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(80, 10, "Pieza/Descripción", 1, 0, "C", True)
    pdf.cell(50, 10, "Repuesto (Est.)", 1, 0, "C", True)
    pdf.cell(50, 10, "Mano de Obra", 1, 1, "C", True)

    # Filas de piezas (usando los datos de tu tabla articulos_cotización)
    pdf.set_font("Arial", "", 10)
    total_general = 0
    for pieza in piezas:
        repuesto = pieza.get('precio_unit_repuesto') or 0
        obra = pieza.get('precio_unit_mano_obra') or 0
        total_general += (repuesto + obra)
        
        pdf.cell(80, 10, pieza['descripcion'], 1)
        pdf.cell(50, 10, f"${repuesto:,.2f}", 1, 0, "R")
        pdf.cell(50, 10, f"${obra:,.2f}", 1, 1, "R")

    # Total
    pdf.set_font("Arial", "B", 11)
    pdf.cell(130, 10, "TOTAL ESTIMADO DE REPARACIÓN:", 1, 0, "R")
    pdf.cell(50, 10, f"${total_general:,.2f}", 1, 1, "R")

    return pdf.output()