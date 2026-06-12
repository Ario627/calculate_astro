from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import HTTPException

from config import context
from models.response import CelestialPosition, PredictInfo

logger = logging.getLogger(__name__)

RATE_INTERVAL_SECONDS = 5

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

BODY_TYPES: dict[str, Literal["moon", "sun"]] = {
    "moon": "moon",
    "sun": "sun",
}


def _wrap_angle(diff: float) -> float:
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff


def _calculate_topocentric(target: Any, t) -> tuple[float, float, float, float]:
    apparent = context.skyfield_observer.at(t).observe(target).apparent()
    alt, az, dist = apparent.altaz()
    return alt.degrees, az.degrees, dist.km, dist.au


def _calculate_rates(target: Any, t) -> tuple[float, float]:
    t_next = context.timescale.tt_jd(t.tt + RATE_INTERVAL_SECONDS / 86400)
    alt_now, az_now, _, _ = _calculate_topocentric(target, t)
    alt_next, az_next, _, _ = _calculate_topocentric(target, t_next)
    azimuth_rate = _wrap_angle(az_next - az_now) / RATE_INTERVAL_SECONDS
    altitude_rate = (alt_next - alt_now) / RATE_INTERVAL_SECONDS
    return azimuth_rate, altitude_rate


def _validate_and_get_target(body_name: str) -> tuple[Any, str, str]:
    name_lower = body_name.lower().strip()

    if name_lower == "earth":
        raise HTTPException(
            status_code=400,
            detail="You are observing from Earth.",
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

    if context.skyfield_observer is None:
        raise HTTPException(
            status_code=503,
            detail="Observer not initialized. Service is still starting.",
        )

    target = context.ephemeris[bsp_key]
    display_name = DISPLAY_NAMES.get(name_lower, name_lower.capitalize())
    body_type = BODY_TYPES.get(name_lower, "planet")

    return target, display_name, body_type


def get_solar_system_position(body_name: str) -> CelestialPosition:
    target, display_name, body_type = _validate_and_get_target(body_name)
    t = context.timescale.now()

    alt, az, dist_km, dist_au = _calculate_topocentric(target, t)
    azimuth_rate, altitude_rate = _calculate_rates(target, t)

    return CelestialPosition(
        name=display_name,
        type=body_type,
        azimuth=round(az, 4),
        altitude=round(alt, 4),
        distance_km=round(dist_km, 2),
        distance_au=round(dist_au, 6),
        azimuth_rate=round(azimuth_rate, 6),
        altitude_rate=round(altitude_rate, 6),
        is_visible=alt > 0,
        illuminated=None,
        timestamp=t.utc_iso(),
    )


def get_solar_system_predict(body_name: str, minutes: int) -> PredictInfo:
    if minutes < 1 or minutes > 1440:
        raise HTTPException(
            status_code=400,
            detail="predict_minutes must be between 1 and 1440.",
        )

    target, display_name, body_type = _validate_and_get_target(body_name)

    t_now = context.timescale.now()
    t_future = context.timescale.tt_jd(t_now.tt + minutes / 1440)

    alt_now, az_now, dist_km_now, dist_au_now = _calculate_topocentric(target, t_now)
    az_rate_now, alt_rate_now = _calculate_rates(target, t_now)

    alt_future, az_future, dist_km_future, dist_au_future = _calculate_topocentric(target, t_future)
    az_rate_future, alt_rate_future = _calculate_rates(target, t_future)

    current = CelestialPosition(
        name=display_name,
        type=body_type,
        azimuth=round(az_now, 4),
        altitude=round(alt_now, 4),
        distance_km=round(dist_km_now, 2),
        distance_au=round(dist_au_now, 6),
        azimuth_rate=round(az_rate_now, 6),
        altitude_rate=round(alt_rate_now, 6),
        is_visible=alt_now > 0,
        illuminated=None,
        timestamp=t_now.utc_iso(),
    )

    future = CelestialPosition(
        name=display_name,
        type=body_type,
        azimuth=round(az_future, 4),
        altitude=round(alt_future, 4),
        distance_km=round(dist_km_future, 2),
        distance_au=round(dist_au_future, 6),
        azimuth_rate=round(az_rate_future, 6),
        altitude_rate=round(alt_rate_future, 6),
        is_visible=alt_future > 0,
        illuminated=None,
        timestamp=t_future.utc_iso(),
    )

    return PredictInfo(
        name=display_name,
        current=current,
        future=future,
        predict_minutes=minutes,
    )