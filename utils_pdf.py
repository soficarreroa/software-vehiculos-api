from fpdf import FPDF
import datetime

class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "AutoPerito - Reporte de Cotizacion", 0, 1, "C")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}", 0, 0, "C")


def crear_pdf_binario(datos_vehiculo: dict, piezas: list, datos_cotizacion: dict = None) -> bytes:
    pdf = PDFReport()
    pdf.add_page()
    
    # Informacion de la cotizacion
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Informacion de la Cotizacion", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    
    if datos_cotizacion:
        pdf.cell(0, 8, f"ID Cotizacion: {datos_cotizacion.get('id', 'N/A')}", 0, 1)
        pdf.cell(0, 8, f"Fecha: {datos_cotizacion.get('creado_en', 'N/A')}", 0, 1)
        pdf.cell(0, 8, f"Estado: {datos_cotizacion.get('estado', 'N/A')}", 0, 1)
        pdf.cell(0, 8, f"Observaciones: {datos_cotizacion.get('observaciones', 'Ninguna')}", 0, 1)
    
    pdf.ln(10)
    
    # Informacion del vehiculo
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Informacion del Vehiculo", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    
    pdf.cell(0, 8, f"Placa: {datos_vehiculo.get('placa', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Marca: {datos_vehiculo.get('marca', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Modelo: {datos_vehiculo.get('modelo', 'N/A')}", 0, 1)
    pdf.cell(0, 8, f"Color: {datos_vehiculo.get('color', 'N/A')}", 0, 1)
    
    pdf.ln(10)
    
    # Piezas
    if piezas:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Piezas y Costos", 0, 1)
        
        # Encabezados
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(80, 8, "Descripcion", 1)
        pdf.cell(40, 8, "Repuesto", 1)
        pdf.cell(40, 8, "Mano de Obra", 1)
        pdf.cell(30, 8, "Subtotal", 1)
        pdf.ln()
        
        # Datos
        pdf.set_font("Helvetica", "", 9)
        total = 0
        
        for p in piezas:
            repuesto = float(p.get('precio_unit_repuesto') or 0)
            mano_obra = float(p.get('precio_unit_mano_obra') or 0)
            pintura = float(p.get('precio_unit_pintura') or 0)
            subtotal = repuesto + mano_obra + pintura
            total += subtotal
            
            pdf.cell(80, 8, str(p.get('descripcion', 'Pieza'))[:40], 1)
            pdf.cell(40, 8, f"${repuesto:,.0f}", 1)
            pdf.cell(40, 8, f"${mano_obra:,.0f}", 1)
            pdf.cell(30, 8, f"${subtotal:,.0f}", 1)
            pdf.ln()
        
        # Total
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(160, 8, "TOTAL GENERAL:", 1, 0, "R")
        pdf.cell(30, 8, f"${total:,.0f}", 1)
    
    # En fpdf2, output(dest='S') devuelve bytes directamente
    return pdf.output(dest='S')