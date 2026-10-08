"""CRS (Coordinate Reference System) utility functions for normalization, UTM detection, and transformation."""

import logging
from typing import Optional

from pyproj import CRS, Transformer
from shapely import transform as shapely_transform
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)

DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"


def normalize_crs(crs_input: Optional[str]) -> str:
    """Normalize input CRS string to standard representation (e.g., EPSG:4326).
    
    Defaults to EPSG:4326 if unparseable or None.
    """
    if not crs_input:
        return DEFAULT_GEOGRAPHIC_CRS
    
    crs_str = str(crs_input).strip()
    if not crs_str:
        return DEFAULT_GEOGRAPHIC_CRS
        
    try:
        parsed_crs = CRS.from_user_input(crs_str)
        epsg_code = parsed_crs.to_epsg()
        if epsg_code:
            return f"EPSG:{epsg_code}"
        return parsed_crs.name or crs_str
    except Exception as e:
        logger.warning(f"Could not parse CRS '{crs_input}': {e}. Defaulting to EPSG:4326.")
        return DEFAULT_GEOGRAPHIC_CRS


def is_geographic_crs(crs_str: str) -> bool:
    """Check if the given CRS string represents a geographic CRS (lat/lon in degrees)."""
    try:
        crs_obj = CRS.from_user_input(crs_str)
        return crs_obj.is_geographic
    except Exception:
        return True  # Assume geographic (degrees) if unknown for safety


def get_utm_epsg_for_bounds(centroid_lon: float, centroid_lat: float) -> str:
    """Calculate the optimal UTM EPSG code for a given longitude and latitude centroid.
    
    Formula:
        UTM Zone = floor((longitude + 180) / 6) + 1
        North Hemisphere (lat >= 0): EPSG = 32600 + zone
        South Hemisphere (lat < 0): EPSG = 32700 + zone
    """
    # Clamp longitude to [-180, 180]
    lon = max(-180.0, min(180.0, centroid_lon))
    lat = max(-80.0, min(84.0, centroid_lat))
    
    zone_number = int((lon + 180) / 6) + 1
    zone_number = max(1, min(60, zone_number))
    
    if lat >= 0:
        epsg_code = 32600 + zone_number
    else:
        epsg_code = 32700 + zone_number
        
    return f"EPSG:{epsg_code}"


def transform_geometry(
    geom: BaseGeometry,
    source_crs_str: str,
    target_crs_str: str
) -> BaseGeometry:
    """Transform a Shapely geometry from source CRS to target CRS.
    
    Returns the original geometry if source and target CRS match or if transformation fails.
    """
    if source_crs_str == target_crs_str:
        return geom
        
    try:
        source_crs = CRS.from_user_input(source_crs_str)
        target_crs = CRS.from_user_input(target_crs_str)

        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        return shapely_transform(geom, transformer.transform)
    except Exception as e:
        logger.error(f"Error transforming geometry from {source_crs_str} to {target_crs_str}: {e}")
        return geom
