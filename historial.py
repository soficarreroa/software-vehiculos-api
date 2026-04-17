from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from database import client
from utils_pdf import crear_pdf_binario

router = APIRouter(prefix="/api/v1/historial", tags=["History"])


class HistoryEntry(BaseModel):
    id: int
    fecha: datetime
    descripcion_siniestro: str
    vehiculo_nombre: str
    placa: str
    valor_total: float
    estado: str 


@router.get("/", response_model=List[HistoryEntry])
async def get_historial(user_id: str, placa: Optional[str] = None):
    try:
        columns = (
            "id, fecha_incidente, estado, usuario_id, monto_total, moneda, "
            "ubicacion, observaciones, url_informe, acepto_legal, creado_en, actualizado_en, "
            "vehiculos(marca, modelo, placa)"
        )

        query = client.table("cotizaciones").select(columns).eq("usuario_id", user_id)

        if placa:
            query = query.ilike("vehiculos.placa", f"%{placa}%")

        response = query.order("creado_en", desc=True).execute()

        history = []
        for item in response.data:
            articulos = client.table("items_cotizacion").select(
                "precio_unit_repuesto, precio_unit_mano_obra"
            ).eq("cotizacion_id", item["id"]).execute()
            
            total = sum(
                (a.get("precio_unit_repuesto") or 0) + (a.get("precio_unit_mano_obra") or 0) 
                for a in articulos.data
            )

            history.append({
                "id": item["id"],
                "fecha": item["creado_en"],
                "descripcion_siniestro": item.get("observaciones") or "Valoración de daños",
                "vehiculo_nombre": f"{item['vehiculos']['marca']} {item['vehiculos']['modelo']}",
                "placa": item['vehiculos']['placa'],
                "valor_total": total,
                "estado": item.get("estado") or "Pendiente"
            })
        
        return history
    except Exception as e:
        print(f"Error en GET Historial: {e}")
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")


@router.get("/{cotizacion_id}/descargar-pdf")
async def descargar_reporte_pdf(cotizacion_id: int, user_id: str):
    try:
        res = client.table("cotizaciones").select(", vehiculos()").eq("id", cotizacion_id).eq("usuario_id", user_id).execute()
        
        if not res.data:
            return Response(content="Acceso denegado o no existe", status_code=403)

        datos = res.data[0]
        piezas = client.table("items_cotizacion").select("*").eq("cotizacion_id", cotizacion_id).execute()
        
        pdf_bytes = crear_pdf_binario(datos.get("vehiculos", {}), piezas.data)
        
        return Response(
            content=bytes(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=reporte_{cotizacion_id}.pdf"}
        )
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return Response(content="Error interno al generar el PDF", status_code=500)
    
@router.patch("/{cotizacion_id}/estado")
async def actualizar_estado_reparacion(cotizacion_id: int, nuevo_estado: str, user_id: str):
    try:
        response = client.table("cotizaciones")\
            .update({"estado": nuevo_estado})\
            .eq("id", cotizacion_id)\
            .eq("usuario_id", user_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No se encontró el reporte")
            
        return {"status": "success", "message": f"Estado actualizado a: {nuevo_estado}"}
    except Exception as e:
        print(f"Error PATCH: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar")