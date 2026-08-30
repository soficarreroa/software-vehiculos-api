from supabase import create_client, Client

supabase_url = "https://umpkwpurnujoebzjglzs.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVtcGt3cHVybnVqb2ViempnbHpzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTY1NDk1MywiZXhwIjoyMDkxMjMwOTUzfQ.DVw0gZIjMQorTmL-saVypmGywS8NIqOFtGi2101i8zU"

client: Client = create_client(supabase_url, supabase_key)


def create_user_client(access_token: str, refresh_token: str) -> Client:
    """Crea un cliente Supabase aislado con la sesión del usuario autenticado.

    Usa la clave anon (respetando RLS) pero con la sesión del usuario ya
    cargada, de modo que las consultas se ejecuten con su identidad
    (auth.uid()) y no como anónimo. Se crea un cliente nuevo por request
    para evitar que la sesión compartida del cliente global se mezcle
    entre peticiones concurrentes.
    """
    user_client = create_client(supabase_url, supabase_key)
    user_client.auth.set_session(access_token, refresh_token)
    return user_client
