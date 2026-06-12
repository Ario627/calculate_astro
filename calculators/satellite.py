from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import HTTPException
from skyfield.api import EarthSatellite

from config import context, settings
from models.response import CelestialPosition, PassInfo, PredictInfo

logger = logging.getLogger(__name__)


PASS_MIN_ALTITUDE = 10.0
PASS_SEARCH_STEPS = 20
MIN_PREDICT_MINUTES = 1
MAX_PREDICT_MINUTES = 1440

_tle_cache: dict[int, tuple[str, str, str, datetime]] = {}
_cache_lock = threading.Lock()

class CelestrakError(Exception):
    pass

def _wrap_angle(diff: float) -> float:
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff

def _calculate_topocentric(satellite: EarthSatellite, t) -> tuple[float, float, float]:
    difference = satellite - context.satellite_observer
    topo = difference.at(t)
    alt, az, dist = topo.altaz()
    return alt.degrees, az.degrees, dist.km
    

def _calculate_rates(satellite: EarthSatellite, t) -> tuple[float, float]:
    t_next = context.timescale.tt_jd(t.tt + 1 / 86400)
    alt_now, az_now, _ = _calculate_topocentric(satellite, t)
    alt_next, az_next, _ = _calculate_topocentric(satellite, t_next)
    azimuth_rate = _wrap_angle(az_next - az_now)
    altitude_rate = alt_next - alt_now
    return azimuth_rate, altitude_rate

def _fetch_tle_from_celestrak(norad_id: int) -> tuple[str, str, str]:
    url = f"{settings.celestrak_url}?CATNR={norad_id}&FORMAT=tle"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise CelestrakError(f"Celestrak returned HTTP {e.response.status_code}")
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


def _build_satellite(norad_id: int, display_name: str | None = None) -> tuple[EarthSatellite, str]:
    line1, line2, tle_name = _get_tle(norad_id)
    name = display_name or tle_name
    satellite = EarthSatellite(line1, line2, name, context.timescale)
    return satellite, name


def get_satellite_position(
    norad_id: int,
    display_name: str | None = None,
) -> CelestialPosition:
    if context.timescale is None:
        raise HTTPException(
            status_code=503,
            detail="Service is still initializing.",
        )

    satellite, name = _build_satellite(norad_id)
    t = context.timescale.now()

    alt, az, dist = _calculate_topocentric(satellite, t)
    azimuth_rate, altitude_rate = _calculate_rates(satellite, t)
    illuminated = satellite.at(t).is_sunlit(context.ephemeris)

    return CelestialPosition(
        name=name,
        type="satellite",
        azimuth=round(az, 4),
        altitude=round(alt, 4),
        distance_km=round(dist, 2),
        azimuth_rate=round(azimuth_rate, 6),
        altitude_rate=round(altitude_rate, 6),
        is_visible=alt > 0,
        illuminated=illuminated,
        timestamp=t.utc_iso(),
    )


def get_satellite_pass(
    norad_id: int,
    display_name: str | None = None,
) -> PassInfo:
    if context.timescale is None:
        raise HTTPException(
            status_code=503,
            detail="Service is still initializing.",
        )

    satellite, name = _build_satellite(norad_id)

    t0 = context.timescale.now()
    t1 = context.timescale.tt_jd(t0.tt + 1)

    times, events = satellite.find_events(
        context.satellite_observer, t0, t1, altitude_degrees=PASS_MIN_ALTITUDE
    )

    if len(times) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No pass found for '{name}' in the next 24 hours.",
        )

    aos_idx = None
    for i, event in enumerate(events):
        if event == 0:
            aos_idx = i
            break

    if aos_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"No upcoming AOS for '{name}' in the next 24 hours.",
        )

    t_aos = times[aos_idx]

    los_idx = None
    for i in range(aos_idx + 1, len(events)):
        if events[i] == 2:
            los_idx = i
            break

    if los_idx is None:
        raise HTTPException(
            status_code=404,
            detail=f"AOS found but no LOS for '{name}'.",
        )

    t_los = times[los_idx]

    max_alt = -90.0
    search_start = t_aos.tt
    search_end = t_los.tt
    step = (search_end - search_start) / PASS_SEARCH_STEPS

    for s in range(PASS_SEARCH_STEPS + 1):
        t_check = context.timescale.tt_jd(search_start + step * s)
        alt, _, _ = _calculate_topocentric(satellite, t_check)
        if alt > max_alt:
            max_alt = alt

    _, az_aos, _ = _calculate_topocentric(satellite, t_aos)
    _, az_los, _ = _calculate_topocentric(satellite, t_los)

    duration = (t_los.tt - t_aos.tt) * 86400

    return PassInfo(
        name=name,
        next_aos=t_aos.utc_iso(),
        next_los=t_los.utc_iso(),
        duration_seconds=int(round(duration)),
        max_altitude=round(max_alt, 2),
        aos_azimuth=round(az_aos, 2),
        los_azimuth=round(az_los, 2),
    )


def get_satellite_predict(
    norad_id: int,
    minutes: int,
    display_name: str | None = None,
) -> PredictInfo:
    if context.timescale is None:
        raise HTTPException(
            status_code=503,
            detail="Service is still initializing.",
        )

    if minutes < MIN_PREDICT_MINUTES or minutes > MAX_PREDICT_MINUTES:
        raise HTTPException(
            status_code=400,
            detail=f"predict_minutes must be between {MIN_PREDICT_MINUTES} and {MAX_PREDICT_MINUTES}.",
        )

    satellite, name = _build_satellite(norad_id)

    t_now = context.timescale.now()
    t_future = context.timescale.tt_jd(t_now.tt + minutes / 1440)

    alt_now, az_now, dist_now = _calculate_topocentric(satellite, t_now)
    az_rate_now, alt_rate_now = _calculate_rates(satellite, t_now)
    illuminated_now = satellite.at(t_now).is_sunlit(context.ephemeris)

    alt_future, az_future, dist_future = _calculate_topocentric(satellite, t_future)
    az_rate_future, alt_rate_future = _calculate_rates(satellite, t_future)
    illuminated_future = satellite.at(t_future).is_sunlit(context.ephemeris)

    current = CelestialPosition(
        name=name,
        type="satellite",
        azimuth=round(az_now, 4),
        altitude=round(alt_now, 4),
        distance_km=round(dist_now, 2),
        azimuth_rate=round(az_rate_now, 6),
        altitude_rate=round(alt_rate_now, 6),
        is_visible=alt_now > 0,
        illuminated=illuminated_now,
        timestamp=t_now.utc_iso(),
    )

    future = CelestialPosition(
        name=name,
        type="satellite",
        azimuth=round(az_future, 4),
        altitude=round(alt_future, 4),
        distance_km=round(dist_future, 2),
        azimuth_rate=round(az_rate_future, 6),
        altitude_rate=round(alt_rate_future, 6),
        is_visible=alt_future > 0,
        illuminated=illuminated_future,
        timestamp=t_future.utc_iso(),
    )

    return PredictInfo(
        name=name,
        current=current,
        future=future,
        predict_minutes=minutes,
    )