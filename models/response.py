from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field



class CelestialPosition(BaseModel):
    name: str = Field(..., description="Nama objek langit")
    type: Literal["satellite", "planet", "moon", "sun", "star"] = Field(
        ..., description="Jenis objek langit"
    )
    azimuth: float = Field(..., description="Azimuth dalam derajat (0-360, Utara=0)")
    altitude: float = Field(..., description="Altitude dalam derajat (-90 sampai +90)")
    distance_km: Optional[float] = Field(
        None, description="Jarak dalam kilometer (None untuk bintang)"
    )
    azimuth_rate: Optional[float] = Field(
        None, description="Kecepatan gerak horizontal °/detik (None untuk bintang)"
    )
    altitude_rate: Optional[float] = Field(
        None, description="Kecepatan gerak vertikal °/detik (None untuk bintang)"
    )
    is_visible: bool = Field(..., description="True jika altitude > 0 (di atas horizon)")
    illuminated: Optional[bool] = Field(
        None, description="True jika objek terkena sinar matahari (khusus satelit, None untuk non-satelit)"
    )
    timestamp: str = Field(..., description="Waktu observasi dalam ISO 8601 UTC")


class PassInfo(BaseModel):
    name: str
    next_aos: str = Field(..., description="Waktu Acquisition of Signal, ISO 8601 UTC")
    next_los: str = Field(..., description="Waktu Loss of Signal, ISO 8601 UTC")
    duration_seconds: int = Field(..., description="Durasi pass dalam detik")
    max_altitude: float = Field(..., description="Altitude maksimum saat culmination, derajat")
    aos_azimuth: float = Field(..., description="Azimuth saat AOS (arah datang), derajat")
    los_azimuth: float = Field(..., description="Azimuth saat LOS (arah pergi), derajat")


class PredictInfo(BaseModel):
    name: str
    current: CelestialPosition
    future: CelestialPosition
    predict_minutes: int = Field(..., description="Berapa menit ke depan prediksi dibuat")


class SatelliteEntry(BaseModel):
    name: str
    norad_id: int
    endpoint: str


class HealthResponse(BaseModel):
    status: str = Field(..., description="Status service")
    timestamp: str = Field(..., description="Waktu cek dalam ISO 8601 UTC")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Pesan error")


class RootResponse(BaseModel):
    service: str = Field(..., description="Nama service")
    version: str = Field(..., description="Versi service")
    status: str = Field(..., description="Status service")


class ObjectsResponse(BaseModel):
    planets: list[str] = Field(..., description="Daftar planet yang tersedia")
    stars: list[str] = Field(..., description="Daftar bintang yang tersedia (hardcoded catalog)")
    satellites: list[SatelliteEntry] = Field(
        ..., description="Satelit yang tersedia dengan shortcut endpoint"
    )