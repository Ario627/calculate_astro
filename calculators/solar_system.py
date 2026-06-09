from __future__ import annotations
import logging
from typing import Literal 
from fastapi import HTTPException
from config import context
from models.response import CelestialPosition

logger = logging.getLogger(__name__)

SolarSystemBody = Literal[
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
    "moon",
    "sun",
]

PLANET_MAP: dict[str, str] = {
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",
    "jupiter": "jupiter barycenter",
    "saturn": "saturn barycenter",
    "uranus": "uranus barycenter",
    "neptune": "neptune barycenter",
    "pluto": "pluto barycenter",
    "moon": "moon",
    "sun": "sun",
}

DISPLAY_NAMES: dict[str, str] = {
    "mercury": "Mercury",
    "venus": "Venus",
    "mars": "Mars",
    "jupiter": "Jupiter",
    "saturn": "Saturn",
    "uranus": "Uranus",
    "neptune": "Neptune",
    "pluto": "Pluto",
    "moon": "Moon",
    "sun": "Sun",
}


BODY_TYPES: dict[str, Literal["planet", "moon", "sun"]] = {
    "moon": "moon",
    "sun": "sun",
}

def get_solar_system_position(body_name: SolarSystemBody) -> CelestialPosition:
    name_lower = body_name.lower().strip()

    if name_lower == "earth":
        raise HTTPException(
            status_code=400,
            detail="you are observing from Earth.",
        )
    
    bsp_key = PLANET_MAP.get(name_lower)

    if bsp_key is None:
        available = ", ".join(sorted(PLANET_MAP.keys()))
        raise HTTPException(
            status_code=404,
            detail=f"Planet '{body_name}' not found. Available: {available}",
        )

    if context.ephemeris is None or context.timescale is None:
        raise HTTPException(
            status_code=503,
            detail="Ephemeris not loaded. Service is still initializing.",
        )
    
    t = context.timescale.now()
    target = context.ephemeris[bsp_key]
    apparent = context.skyfield_observer.at(t).observe(target).apparent()
    alt, az, distance = apparent.altaz()

    body_type = BODY_TYPES.get(name_lower, "planet")

    return CelestialPosition(
        name=DISPLAY_NAMES.get(name_lower, name_lower.capitalize()),
        type=body_type,
        azimuth=round(az.degrees, 4),
        altitude=round(alt.degrees, 4),
        distance_km=round(distance.km, 2),
        is_visible=alt.degrees > 0,
        timestamp=t.utc_iso(),
    )