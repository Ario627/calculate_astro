from __future__ import annotations
import logging
import threading
from astropy import units as u
from astropy.coordinates import AltAz, SkyCoord
from astropy.coordinates.name_resolve import NameResolveError
from astropy.time import Time
from fastapi import HTTPException

from config import context
from models.response import CelestialPosition

logger = logging.getLogger(__name__)

_star_cache: dict[str, SkyCoord] = {}
_star_cache_lock = threading.Lock()

BRIGHT_STARS: dict[str, dict[str, float]] = {
    "sirius": {"ra": 101.287, "dec": -16.716},
    "canopus": {"ra": 95.988, "dec": -52.696},
    "arcturus": {"ra": 213.915, "dec": 19.182},
    "vega": {"ra": 279.234, "dec": 38.784},
    "capella": {"ra": 79.172, "dec": 45.998},
    "rigel": {"ra": 78.634, "dec": -8.202},
    "procyon": {"ra": 114.826, "dec": 5.225},
    "betelgeuse": {"ra": 88.793, "dec": 7.407},
    "altair": {"ra": 297.696, "dec": 8.868},
    "aldebaran": {"ra": 68.980, "dec": 16.509},
    "spica": {"ra": 201.298, "dec": -11.161},
    "antares": {"ra": 247.352, "dec": -26.432},
    "polaris": {"ra": 37.954, "dec": 89.264},
    "deneb": {"ra": 310.358, "dec": 45.280},
    "fomalhaut": {"ra": 344.413, "dec": -29.622},
    "regulus": {"ra": 152.093, "dec": 11.967},
}

def _get_star_coord(name: str) -> SkyCoord:
    name_lower  = name.lower().strip()

    with _star_cache_lock:
        if name_lower in _star_cache:
            return _star_cache[name_lower]

    if name_lower in BRIGHT_STARS:
        data = BRIGHT_STARS[name_lower]
        coord = SkyCoord(
            ra=data["ra"] * u.deg,
            dec=data["dec"] * u.deg,
            frame="icrs",
        )
        with _star_cache_lock:
            _star_cache[name_lower] = coord
        logger.info("Star '%s' resolved from hardcoded catalog", name)
        return coord

    try:
        coord = SkyCoord.from_name(name)
        with _star_cache_lock:
            _star_cache[name_lower] = coord
        logger.info("Star '%s' resolved from SIMBAD/Sesame", name)
        return coord
    except NameResolveError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Star '{name}' not found in catalog: {e}",
        )
    

def get_star_position(name: str) -> CelestialPosition:
    if context.astropy_observer is None:
        raise HTTPException(
            status_code=503,
            detail="Astropy not initialized. Service is still starting.",
        )

    star_coord = _get_star_coord(name)

    obstime = Time.now()
    altaz_frame = AltAz(obstime=obstime, location=context.astropy_observer)
    star_altaz = star_coord.transform_to(altaz_frame)

    return CelestialPosition(
        name=name.title(),
        type="star",
        azimuth=round(star_altaz.az.degree, 4),
        altitude=round(star_altaz.alt.degree, 4),
        distance_km=None,
        is_visible=star_altaz.alt.degree > 0,
        timestamp=obstime.isot,
    )