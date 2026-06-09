from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from skyfield.api import EarthSatellite

from config import context, settings
from models.response import CelestialPosition

logger = logging.getLogger(__name__)
_tle_cache: dict[int, tuple[str, str, str, datetime]] = {}
_cache_lock = threading.Lock()

class CelestrakError(Exception):
    pass

def  _fetch_tle_from_celestrak(norad_id: int) -> tuple[str, str, str]:
    url = f"{settings.celestrak_url}?CATNR={norad_id}&FORMAT=tle"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.RequestError as e:
        raise CelestrakError(f"Unable to reach Celestrak: {e}")
    
    lines = [line for line in response.text.strip().splitlines() if line.strip()]

    if len(lines) < 3:
        raise ValueError(f"Satellite with NORAD ID {norad_id} not found on Celestrak.")

    name = lines[0].strip()
    line1 = lines[1].strip()
    line2 = lines[2].strip()

    if not line1.startswith("1") or not line2.startswith("2"):
        raise ValueError(f"Invalid TLE format for NORAD ID {norad_id}.")

    return line1, line2, name


def _get_tle(norad_id: int) -> tuple[str, str, str]:
    now = datetime.now(timezone.utc)
    ttl = timedelta(hours=settings.tle_cache_ttl_hours)

    with _cache_lock:
        if norad_id in _tle_cache:
            line1, line2, name, fetched_at = _tle_cache[norad_id]
            if now - fetched_at < ttl:
                return line1, line2, name

    try:
        line1, line2, name = _fetch_tle_from_celestrak(norad_id)
        with _cache_lock:
            _tle_cache[norad_id] = (line1, line2, name, now)
        logger.info("TLE cache updated for NORAD %d", norad_id)
        return line1, line2, name
    except (CelestrakError, ValueError) as e:
        with _cache_lock:
            if norad_id in _tle_cache:
                line1, line2, name, fetched_at = _tle_cache[norad_id]
                logger.warning(
                    "Using stale TLE cache for NORAD %d (fetched %s): %s",
                    norad_id,
                    fetched_at.isoformat(),
                    e,
                )
                return line1, line2, name

        if isinstance(e, ValueError):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Celestrak unavailable and no cached data for NORAD ID {norad_id}: {e}",
        )
    


def get_satellite_position(
    norad_id: int,
    display_name: str | None = None,
) -> CelestialPosition:
    if context.timescale is None:
        raise HTTPException(
            status_code=503,
            detail="Service is still initializing.",
        )

    line1, line2, tle_name = _get_tle(norad_id)
    name = display_name or tle_name

    satellite = EarthSatellite(line1, line2, name, context.timescale)
    t = context.timescale.now()

    difference = satellite - context.skyfield_observer
    topocentric = difference.at(t)
    alt, az, distance = topocentric.altaz()

    return CelestialPosition(
        name=name,
        type="satellite",
        azimuth=round(az.degrees, 4),
        altitude=round(alt.degrees, 4),
        distance_km=round(distance.km, 2),
        is_visible=alt.degrees > 0,
        timestamp=t.utc_iso(),
    )