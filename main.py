from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from calculators.satellite import (
    get_satellite_pass,
    get_satellite_position,
    get_satellite_predict,
)
from calculators.solar_system import PLANET_MAP, get_solar_system_position, get_solar_system_predict
from calculators.stars import BRIGHT_STARS, get_star_position
from config import init_astropy, init_skyfield, settings
from models.response import (
    CelestialPosition,
    ErrorResponse,
    HealthResponse,
    ObjectsResponse,
    PassInfo,
    PredictInfo,
    RootResponse,
    SatelliteEntry,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Skyfield (loading ephemeris)...")
    await asyncio.to_thread(init_skyfield)
    logger.info("Initializing Astropy...")
    await asyncio.to_thread(init_astropy)
    logger.info("Astro-service startup complete")
    yield
    logger.info("Astro-service shutting down")


app = FastAPI(
    title="Astro Service",
    description="Realtime celestial position calculator for Semarang observatory",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(detail="Internal server error").dict(),
    )


@app.get("/", response_model=RootResponse)
async def root():
    return RootResponse(
        service="astro-service",
        version="1.0.0",
        status="running",
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/objects", response_model=ObjectsResponse)
async def list_objects():
    return ObjectsResponse(
        planets=sorted(PLANET_MAP.keys()),
        stars=sorted(BRIGHT_STARS.keys()),
        satellites=[
            SatelliteEntry(name="ISS", norad_id=25544, endpoint="/iss"),
        ],
    )


@app.get(
    "/iss",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_iss():
    return await asyncio.to_thread(get_satellite_position, 25544, "ISS")


@app.get(
    "/iss/pass",
    response_model=PassInfo,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_iss_pass():
    return await asyncio.to_thread(get_satellite_pass, 25544, "ISS")


@app.get(
    "/satellite/{norad_id}",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_satellite(norad_id: int):
    return await asyncio.to_thread(get_satellite_position, norad_id)


@app.get(
    "/satellite/{norad_id}/pass",
    response_model=PassInfo,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_satellite_pass_endpoint(norad_id: int):
    return await asyncio.to_thread(get_satellite_pass, norad_id)


@app.get(
    "/satellite/{norad_id}/predict",
    response_model=PredictInfo,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_satellite_predict_endpoint(
    norad_id: int,
    minutes: int = Query(default=5, ge=1, le=1440),
):
    return await asyncio.to_thread(get_satellite_predict, norad_id, minutes)


@app.get(
    "/solar/{name}",
    response_model=CelestialPosition,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_solar(name: str):
    return await asyncio.to_thread(get_solar_system_position, name)


@app.get(
    "/solar/{name}/predict",
    response_model=PredictInfo,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_solar_predict(
    name: str,
    minutes: int = Query(default=5, ge=1, le=1440),
):
    return await asyncio.to_thread(get_solar_system_predict, name, minutes)


@app.get(
    "/star/{name}",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_star(name: str):
    return await asyncio.to_thread(get_star_position, name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=True,
    )