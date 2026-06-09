from __future__ import annotations

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    observer_name: str = "Semarang"
    observer_lat: float = -6.9667
    observer_lon: float = 110.4167
    observer_alt: float = 6.0
    celestrak_url: str = "https://celestrak.org/NORAD/elements/gp.php"
    tle_cache_ttl_hours: int = 2
    ephemeris_file: str = "de421.bsp"
    server_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


class AstronomyContext:
    timescale = None
    ephemeris = None
    earth = None
    skyfield_observer = None      
    satellite_observer = None     
    astropy_observer = None


context = AstronomyContext()


def init_skyfield() -> None:
    from skyfield.api import load, wgs84

    logger.info("Loading Skyfield timescale...")
    context.timescale = load.timescale()

    logger.info(
        "Loading JPL ephemeris '%s' (may download ~17MB on first run)...",
        settings.ephemeris_file,
    )
    context.ephemeris = load(settings.ephemeris_file)
    context.earth = context.ephemeris["earth"]

    # Untuk planet/bulan/matahari
    context.skyfield_observer = context.earth + wgs84.latlon(
        settings.observer_lat,
        settings.observer_lon,
        elevation_m=settings.observer_alt,
    )

    # Untuk satelit
    context.satellite_observer = wgs84.latlon(
        settings.observer_lat,
        settings.observer_lon,
        elevation_m=settings.observer_alt,
    )

    logger.info(
        "Skyfield initialized — observer at %s (%.4f, %.4f, %.1fm)",
        settings.observer_name,
        settings.observer_lat,
        settings.observer_lon,
        settings.observer_alt,
    )


def init_astropy() -> None:
    from astropy import units as u
    from astropy.coordinates import EarthLocation

    context.astropy_observer = EarthLocation.from_geodetic(
        lon=settings.observer_lon * u.deg,
        lat=settings.observer_lat * u.deg,
        height=settings.observer_alt * u.m,
    )
    logger.info("Astropy initialized — EarthLocation ready")
