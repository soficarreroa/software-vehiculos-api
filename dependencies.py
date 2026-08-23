from fastapi import Depends, Header, HTTPException, status

from database import client


def get_usuario_con_rol(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado",
        )

    token = authorization.split(" ", 1)[1]

    try:
        user_response = client.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    if not user_response or not getattr(user_response, "user", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )

    auth_id = str(user_response.user.id)

    usuario_result = (
        client.table("usuarios")
        .select("id, correo, rol, activo")
        .eq("auth_id", auth_id)
        .execute()
    )

    if not usuario_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario autenticado pero no encontrado en la base de datos",
        )

    usuario = usuario_result.data[0]

    if not usuario.get("activo", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva",
        )

    return usuario


def requiere_rol(roles_permitidos: list[str]):
    def verificador(usuario: dict = Depends(get_usuario_con_rol)) -> dict:
        if usuario.get("rol") not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        return usuario

    return verificador
