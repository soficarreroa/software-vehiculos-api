from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_KEY")

client: Client = create_client(supabase_url, supabase_key)
