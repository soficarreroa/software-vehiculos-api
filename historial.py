from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from database import client
from dependencies import get_usuario_con_rol
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
async def get_historial(
    placa: Optional[str] = Query(None, description="Filtrar por placa"),
    usuario: dict = Depends(get_usuario_con_rol),
):
    try:
        usuario_id = usuario["id"]

        # El propietario se toma del token validado, nunca de un parámetro del cliente.
        cotizaciones_response = client.table("cotizaciones")\
            .select("id, creado_en, observaciones, estado, vehiculo_id")\
            .eq("usuario_id", usuario_id)\
            .order("creado_en", desc=True)\
            .execute()

        if not cotizaciones_response.data:
            return []
        
        history = []
        
        for cotizacion in cotizaciones_response.data:
            vehiculo_nombre = "Vehículo no especificado"
            placa_vehiculo = "---"
            
            # Paso 2: Obtener el vehículo si existe
            if cotizacion.get("vehiculo_id"):
                vehiculo_response = client.table("vehiculos")\
                    .select("marca, modelo, placa")\
                    .eq("id", cotizacion["vehiculo_id"])\
                    .eq("usuario_id", usuario_id)\
                    .execute()
                
                if vehiculo_response.data:
                    vehiculo = vehiculo_response.data[0]
                    marca = vehiculo.get("marca", "")
                    modelo = vehiculo.get("modelo", "")
                    placa_vehiculo = vehiculo.get("placa", "---")
                    vehiculo_nombre = f"{marca} {modelo}".strip()
                    if not vehiculo_nombre:
                        vehiculo_nombre = "Vehículo sin marca/modelo"
            
            # Paso 3: Calcular el total de la cotización
            items_response = client.table("items_cotizacion")\
                .select("precio_unit_repuesto, precio_unit_mano_obra, precio_unit_pintura")\
                .eq("cotizacion_id", cotizacion["id"])\
                .execute()
            
            total = 0
            for item in items_response.data:
                repuesto = item.get("precio_unit_repuesto") or 0
                mano_obra = item.get("precio_unit_mano_obra") or 0
                pintura = item.get("precio_unit_pintura") or 0
                total += repuesto + mano_obra + pintura
            
            # Paso 4: Mapear estado
            estado_original = cotizacion.get("estado") or "En espera"
            estado_map = {
                "En espera": "En espera",
                "Reparado": "Reparado",
                "Cancelado": "Cancelado",
                "Pendiente": "En espera",
                "Completado": "Reparado"
            }
            estado_final = estado_map.get(estado_original, "En espera")
            
            # Paso 5: Crear entrada de historial
            history.append({
                "id": cotizacion["id"],
                "fecha": cotizacion["creado_en"],
                "descripcion_siniestro": cotizacion.get("observaciones") or "Valoración de daños",
                "vehiculo_nombre": vehiculo_nombre,
                "placa": placa_vehiculo,
                "valor_total": float(cotizacion.get("monto_total") or total),
                "estado": estado_final
            })
        
        # Paso 6: Aplicar filtro por placa si es necesario
        if placa:
            history = [h for h in history if placa.lower() in h["placa"].lower()]
            print(f" Filtrado por placa '{placa}': {len(history)} resultados")
        
        return history
    except HTTPException:
        raise
    except Exception as e:
        print(f" Error en GET Historial: {e}")
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")


@router.get("/{cotizacion_id}/descargar-pdf")
async def descargar_reporte_pdf(
    cotizacion_id: int,
    usuario: dict = Depends(get_usuario_con_rol),
):
    try:
        usuario_id = usuario["id"]

        cotizacion_response = client.table("cotizaciones")\
            .select("*, vehiculo_id")\
            .eq("id", cotizacion_id)\
            .eq("usuario_id", usuario_id)\
            .execute()

        if not cotizacion_response.data:
            raise HTTPException(status_code=404, detail="Cotización no encontrada o acceso denegado")
        
        cotizacion = cotizacion_response.data[0]
        print(f" Cotización encontrada: ID {cotizacion['id']}, estado {cotizacion.get('estado')}")
        
        # Obtener el vehículo
        vehiculo = {}
        if cotizacion.get("vehiculo_id"):
            vehiculo_response = client.table("vehiculos")\
                .select("*")\
                .eq("id", cotizacion["vehiculo_id"])\
                .eq("usuario_id", usuario_id)\
                .execute()
            if vehiculo_response.data:
                vehiculo = vehiculo_response.data[0]
                print(f" Vehículo encontrado: {vehiculo.get('marca')} {vehiculo.get('modelo')} - Placa {vehiculo.get('placa')}")
            else:
                print(" No se encontraron datos del vehículo")
        else:
            print(" La cotización no tiene vehículo asociado")
        
        # Obtener las piezas asociadas
        piezas_response = client.table("items_cotizacion")\
            .select("*")\
            .eq("cotizacion_id", cotizacion_id)\
            .execute()
        
        piezas = piezas_response.data
        print(f" Piezas encontradas: {len(piezas)}")
        
        # Generar PDF (puede lanzar excepción)
        pdf_bytes = crear_pdf_binario(vehiculo, piezas, cotizacion)
        
        # Validar que el PDF no esté vacío
        if not pdf_bytes or len(pdf_bytes) < 100:  # Un PDF mínimo tiene más de 100 bytes
            print(f" El PDF generado tiene tamaño sospechoso: {len(pdf_bytes) if pdf_bytes else 0} bytes")
            raise HTTPException(status_code=500, detail="El PDF generado está vacío o es inválido")
        
        print(f" PDF generado correctamente. Tamaño: {len(pdf_bytes)} bytes")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=reporte_{cotizacion_id}.pdf"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f" ERROR en descargar_reporte_pdf: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno al generar el PDF: {str(e)}")

@router.patch("/{cotizacion_id}/estado")
async def actualizar_estado_reparacion(
    cotizacion_id: int,
    nuevo_estado: str,
    usuario: dict = Depends(get_usuario_con_rol),
):
    try:
        response = client.table("cotizaciones")\
            .update({"estado": nuevo_estado})\
            .eq("id", cotizacion_id)\
            .eq("usuario_id", usuario["id"])\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No se encontró el reporte")
        
        return {"status": "success", "message": f"Estado actualizado a: {nuevo_estado}"}
    except HTTPException:
        raise
    except Exception as e:
        print(f" Error PATCH: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar") from e