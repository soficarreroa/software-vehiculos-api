from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from typing import List
from database import supabase

# Creamos un router para organizar los endpoints
router = APIRouter(prefix="/api/v1/historial", tags=["History"])

class Report(BaseModel):
    id: int
    vehicle: str
    plate: str
    date: datetime
    damage: str
    value: float
    status: str  # Puede ser 'Waiting', 'Repaired' o 'Cancelled'

@router.get("/", response_model=List[Report])
async def get_history():
    try:
        response = supabase.table("reports").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error: {e}")
        return []
    
@router.post("/")
async def create_report(report: Report):
    try:
        result = await supabase.table("reports").insert({
            "vehicle": report.vehicle,
            "plate": report.plate,
            "damage": report.damage,
            "value": report.value,
            "status": report.status
        }).execute()
        return {"status": "success", "data": result.data}
    except Exception as e:
        print(f"Error detectado: {e}")
        return {"status": "error", "message": str(e)}