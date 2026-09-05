from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import client
from dependencies import requiere_rol

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(requiere_rol(["admin"]))],
)

ROLES_VALIDOS = {"cliente", "taller", "admin"}


class CambioRolRequest(BaseModel):
    rol: str


@router.get("/resumen")
def get_resumen():
    """Métricas generales para las tarjetas KPI del dashboard de administrador."""
    try:
        usuarios = client.table("usuarios").select("id, rol, activo").execute().data
        talleres = client.table("talleres").select("id, verificado").execute().data
        cotizaciones = client.table("cotizaciones").select("id, estado").execute().data
        vehiculos = client.table("vehiculos").select("id").execute().data

        cotizaciones_por_estado: dict[str, int] = {}
        for c in cotizaciones:
            estado = c.get("estado") or "sin_estado"
            cotizaciones_por_estado[estado] = cotizaciones_por_estado.get(estado, 0) + 1

        return {
            "total_usuarios": len(usuarios),
            "usuarios_por_rol": {
                rol: sum(1 for u in usuarios if u.get("rol") == rol)
                for rol in {u.get("rol") for u in usuarios}
            },
            "usuarios_inactivos": sum(1 for u in usuarios if not u.get("activo", True)),
            "total_talleres": len(talleres),
            "talleres_pendientes": sum(1 for t in talleres if not t.get("verificado")),
            "total_vehiculos": len(vehiculos),
            "total_cotizaciones": len(cotizaciones),
            "cotizaciones_por_estado": cotizaciones_por_estado,
        }
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/talleres")
def get_talleres_admin():
    """Lista completa de talleres, incluidos los pendientes de aprobación."""
    try:
        response = (
            client.table("talleres")
            .select(
                "id, nombre, propietario_id, direccion, telefono, email, "
                "categoria, verificado, certificado, creado_en"
            )
            .order("creado_en", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/talleres/{taller_id}/verificar")
def verificar_taller(taller_id: int, verificado: bool):
    """Aprueba o rechaza un taller aliado."""
    try:
        existing = client.table("talleres").select("id").eq("id", taller_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Taller no encontrado")

        response = (
            client.table("talleres")
            .update({"verificado": verificado})
            .eq("id", taller_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usuarios")
def get_usuarios_admin():
    """Lista completa de usuarios para la tabla de gestión de roles."""
    try:
        response = (
            client.table("usuarios")
            .select("id, correo, nombre_completo, rol, activo, creado_en")
            .order("creado_en", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/usuarios/{usuario_id}/rol")
def cambiar_rol_usuario(usuario_id: int, payload: CambioRolRequest):
    """Reasigna el rol de un usuario (cliente, taller o admin)."""
    if payload.rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol inválido")
    try:
        existing = client.table("usuarios").select("id").eq("id", usuario_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        response = (
            client.table("usuarios")
            .update({"rol": payload.rol})
            .eq("id", usuario_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class CambioEstadoRequest(BaseModel):
    activo: bool


@router.patch("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(usuario_id: int, payload: CambioEstadoRequest):
    """Activa o desactiva la cuenta de un usuario."""
    try:
        existing = client.table("usuarios").select("id").eq("id", usuario_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        response = (
            client.table("usuarios")
            .update({"activo": payload.activo})
            .eq("id", usuario_id)
            .execute()
        )
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))