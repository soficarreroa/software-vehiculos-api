from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from database import client

load_dotenv()

router = APIRouter()


@router.get("/talleres")
def get_talleres():
    try:
        print("client:", client)
        response = client.table("talleres").select("*").execute()
        return response.data
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
