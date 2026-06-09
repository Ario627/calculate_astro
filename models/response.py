from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

class CelestialPosition(BaseModel):
    name: str = Field(..., description="Nama nama objek langit")
    type: Literal["satellite", "planet", "moon", "sun", "star"] = Field(..., description="Jenis objek langit")

    azimuth: float = Field(..., description="Azimuth dalam derajat (0-360, Utara=0)")
    altitude: float = Field(..., description="Altitude dalam derajat (-90 sampai +90)")

    distance_km: Optional[float] = Field(None, description="Jarak dalam kilometer (None untuk bintang)")
    is_visible: bool = Field(..., description="True jika altitude > 0 (di atas horizon)")
    timestamp: str = Field(..., description="Waktu observasi dalam ISO 8601 UTC")


class HealthResponse(BaseModel): 
    status: str = Field(..., description="Status service")
    timestamp: str = Field(..., description="Waktu cek dalam ISO 8601 UTC")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Pesan error")