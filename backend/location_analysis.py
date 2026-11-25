import json
import math
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlsplit


BOUNDARY_PATH = Path(__file__).resolve().parent / "north_sulawesi_boundary.json"
GOOGLE_MAPS_HOSTS = {"google.com", "maps.app.goo.gl", "goo.gl"}
COORDINATE_PATTERNS = (
    re.compile(r"@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)"),
    re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)"),
    re.compile(r"(?:[?&](?:q|query|ll|center|destination)=)(-?\d+(?:\.\d+)?)(?:%2C|,|\s)+(-?\d+(?:\.\d+)?)", re.IGNORECASE),
)


def parse_google_maps_coordinates(maps_url: str) -> tuple[float, float]:
    value = maps_url.strip()
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    is_google_maps_host = (
        hostname in GOOGLE_MAPS_HOSTS
        or hostname.endswith(".google.com")
        or hostname.endswith(".goo.gl")
    )
    if parsed.scheme != "https" or not is_google_maps_host:
        raise ValueError("Gunakan tautan HTTPS Google Maps yang valid.")

    decoded_url = unquote(value)
    for pattern in COORDINATE_PATTERNS:
        match = pattern.search(decoded_url)
        if match:
            latitude, longitude = map(float, match.groups())
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return latitude, longitude

    raise ValueError(
        "Tautan Google Maps harus memuat koordinat. Gunakan tautan lengkap "
        "dengan pola @latitude,longitude atau !3dlatitude!4dlongitude; tautan pendek tidak didukung."
    )


def haversine_km(
    origin: tuple[float, float], destination: tuple[float, float]
) -> float:
    latitude1, longitude1 = map(math.radians, origin)
    latitude2, longitude2 = map(math.radians, destination)
    delta_latitude = latitude2 - latitude1
    delta_longitude = longitude2 - longitude1
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(latitude1)
        * math.cos(latitude2)
        * math.sin(delta_longitude / 2) ** 2
    )
    return round(
        6371.0088 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine)),
        3,
    )


@lru_cache(maxsize=1)
def north_sulawesi_polygons():
    with BOUNDARY_PATH.open(encoding="utf-8") as boundary_file:
        geometry = json.load(boundary_file)["geometry"]
    return geometry["coordinates"]


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    longitude, latitude = point
    start_longitude, start_latitude = start
    end_longitude, end_latitude = end
    cross = (latitude - start_latitude) * (end_longitude - start_longitude) - (
        longitude - start_longitude
    ) * (end_latitude - start_latitude)
    if abs(cross) > 1e-10:
        return False
    return (
        min(start_longitude, end_longitude) - 1e-10
        <= longitude
        <= max(start_longitude, end_longitude) + 1e-10
        and min(start_latitude, end_latitude) - 1e-10
        <= latitude
        <= max(start_latitude, end_latitude) + 1e-10
    )


def _point_in_ring(point: tuple[float, float], ring: list[list[float]]) -> bool:
    longitude, latitude = point
    inside = False
    previous = ring[-1]
    for current in ring:
        start = (float(previous[0]), float(previous[1]))
        end = (float(current[0]), float(current[1]))
        if _point_on_segment(point, start, end):
            return True
        if (end[1] > latitude) != (start[1] > latitude):
            crossing_longitude = (
                (start[0] - end[0]) * (latitude - end[1]) / (start[1] - end[1])
                + end[0]
            )
            if longitude < crossing_longitude:
                inside = not inside
        previous = current
    return inside


def is_in_north_sulawesi(latitude: float, longitude: float) -> bool:
    point = (longitude, latitude)
    for polygon in north_sulawesi_polygons():
        if not polygon or not _point_in_ring(point, polygon[0]):
            continue
        if not any(_point_in_ring(point, hole) for hole in polygon[1:]):
            return True
    return False
