from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from database import client
from utils_pdf import crear_pdf_binario

# Configuración del Router con su prefijo y etiquetas
router = APIRouter(prefix="/api/v1/historial", tags=["History"])

# --- MODELOS DE DATOS (Pydantic) ---

class HistoryEntry(BaseModel):
    id: int
    fecha: datetime
    descripcion_siniestro: str
    vehiculo_nombre: str
    placa: str
    valor_total: float
    estado: str 

# --- ENDPOINTS ---

@router.get("/", response_model=List[HistoryEntry])
async def get_historial(user_id: str, placa: Optional[str] = None):
    """
    PUNTO 1 y 2: Obtiene la bitácora digital con Filtro de Seguridad.
    Solo muestra los vehículos y reportes que pertenecen al 'user_id' activo.
    """
    try:
        # Consulta con JOIN a vehículos y filtro de seguridad por user_id
        query = client.table("cotizaciones").select(
            "id, created_at, descripcion, estado, user_id, vehiculos(marca, modelo, placa)"
        ).eq("user_id", user_id) # Validación de regla de negocio

        # Filtro opcional por placa si el usuario busca un carro específico
        if placa:
            query = query.ilike("vehiculos.placa", f"%{placa}%")

        # Orden Cronológico: Lo más nuevo primero
        response = query.order("created_at", desc=True).execute()

        history = []
        for item in response.data:
            # Cálculo de costos desde la tabla articulos_cotización
            articulos = client.table("articulos_cotización").select(
                "precio_unit_repuesto, precio_unit_mano_obra"
            ).eq("cotizacion_id", item["id"]).execute()
            
            total = sum(
                (a.get("precio_unit_repuesto") or 0) + (a.get("precio_unit_mano_obra") or 0) 
                for a in articulos.data
            )

            history.append({
                "id": item["id"],
                "fecha": item["created_at"],
                "descripcion_siniestro": item.get("descripcion") or "Valoración de daños",
                "vehiculo_nombre": f"{item['vehiculos']['marca']} {item['vehiculos']['modelo']}",
                "placa": item['vehiculos']['placa'],
                "valor_total": total,
                "estado": item.get("estado") or "Pendiente"
            })
        
        return history
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar el historial seguro")


@router.get("/{cotizacion_id}/descargar-pdf")
async def descargar_reporte_pdf(cotizacion_id: int, user_id: str):
    """
    PUNTO 3: Generación del Reporte Técnico en PDF.
    Verifica que la cotización pertenezca al usuario antes de permitir la descarga.
    """
    try:
        # Validación de propiedad: evitamos que alguien descargue datos ajenos
        res_cot = client.table("cotizaciones")\
            .select(", vehiculos()")\
            .eq("id", cotizacion_id)\
            .eq("user_id", user_id)\
            .single().execute()

        if not res_cot.data:
            raise HTTPException(status_code=403, detail="Acceso denegado a este reporte")
        
        # Obtenemos las piezas para el desglose del PDF
        res_piezas = client.table("articulos_cotización").select("*").eq("cotizacion_id", cotizacion_id).execute()
        
        # Llamamos al motor de PDF (utils_pdf.py)
        pdf_content = crear_pdf_binario(res_cot.data["vehiculos"], res_piezas.data)

        nombre_archivo = f"Reporte_AutoPerito_{res_cot.data['vehiculos']['placa']}.pdf"
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={nombre_archivo}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generando documento legal")


@router.patch("/{cotizacion_id}/estado")
async def actualizar_estado_reparacion(cotizacion_id: int, nuevo_estado: str, user_id: str):
    """
    PUNTO 4: Seguimiento de Estado.
    Permite al usuario marcar un daño como 'Reparado' para evitar la devaluación.
    """
    try:
        # Actualizamos solo si el reporte pertenece al usuario
        response = client.table("cotizaciones")\
            .update({"estado": nuevo_estado})\
            .eq("id", cotizacion_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No se encontró el reporte para actualizar")
            
        return {"status": "success", "message": f"El vehículo ahora está: {nuevo_estado}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al actualizar estado")