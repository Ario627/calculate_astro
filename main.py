from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config import init_astropy, init_skyfield, settings
from calculators.solar_system import PLANET_MAP
from calculators.stars import BRIGHT_STARS
from models.response import (
    CelestialPosition,
    ErrorResponse,
    HealthResponse,
    ObjectsResponse,
    RootResponse,
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
    description="Real-time celestial position calculator for Miniatur Observatorium Otomatis",
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
            {"name": "ISS", "norad_id": 25544, "endpoint": "/iss"},
        ],
    )


# Endpoint shortcut untuk ISS
@app.get(
    "/iss",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_iss():
    from calculators.satellite import get_satellite_position
    return await asyncio.to_thread(get_satellite_position, 25544, "ISS")


#bulan dan bintang
@app.get(
    "/moon",
    response_model=CelestialPosition,
    responses={503: {"model": ErrorResponse}},
)
async def get_moon():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "moon")


@app.get(
    "/sun",
    response_model=CelestialPosition,
    responses={503: {"model": ErrorResponse}},
)
async def get_sun():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "sun")


#planet
@app.get(
    "/mars",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_mars():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "mars")


@app.get(
    "/venus",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_venus():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "venus")


@app.get(
    "/jupiter",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_jupiter():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "jupiter")


@app.get(
    "/saturn",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_saturn():
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, "saturn")


#Dynamic 
@app.get(
    "/satellite/{norad_id}",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_satellite(norad_id: int):
    from calculators.satellite import get_satellite_position
    return await asyncio.to_thread(get_satellite_position, norad_id)


@app.get(
    "/planet/{name}",
    response_model=CelestialPosition,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_planet(name: str):
    from calculators.solar_system import get_solar_system_position
    return await asyncio.to_thread(get_solar_system_position, name)


@app.get(
    "/star/{name}",
    response_model=CelestialPosition,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def get_star(name: str):
    from calculators.stars import get_star_position
    return await asyncio.to_thread(get_star_position, name)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.server_port,
        reload=True,
    )