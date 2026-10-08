"""Geospatial measurement engine for calculating areas, lengths, and handling CRS projections."""

import logging
from typing import Optional, Tuple
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, MultiPoint

from app.models.schemas import MeasurementResult
from app.utils.crs import is_geographic_crs, get_utm_epsg_for_bounds, transform_geometry

logger = logging.getLogger(__name__)


def format_area(sq_meters: float) -> str:
    """Format area into human-readable string with m² and hectares/km²."""
    if sq_meters >= 1_000_000:
        sq_km = sq_meters / 1_000_000
        return f"{sq_meters:,.2f} m² ({sq_km:,.2f} km²)"
    elif sq_meters >= 10_000:
        hectares = sq_meters / 10_000
        return f"{sq_meters:,.2f} m² ({hectares:,.2f} ha)"
    else:
        return f"{sq_meters:,.2f} m²"


def format_length(meters: float) -> str:
    """Format length into human-readable string with m and km."""
    if meters >= 1_000:
        km = meters / 1_000
        return f"{meters:,.2f} m ({km:,.2f} km)"
    else:
        return f"{meters:,.2f} m"


def calculate_feature_measurement(
    geom: Optional[BaseGeometry],
    source_crs: str,
    target_projected_crs: Optional[str] = None
) -> Tuple[Optional[MeasurementResult], Optional[str]]:
    """Calculate area or length for supported geometries.
    
    Transforms geographic coordinates to a projected CRS (UTM) prior to calculation.
    
    Returns:
        (MeasurementResult or None, target_projected_crs used)
    """
    if geom is None or geom.is_empty:
        return None, target_projected_crs

    geom_type = geom.geom_type

    # Determine projected CRS if not already passed
    projected_crs = target_projected_crs
    if not projected_crs:
        if is_geographic_crs(source_crs):
            try:
                centroid = geom.centroid
                projected_crs = get_utm_epsg_for_bounds(centroid.x, centroid.y)
            except Exception as e:
                logger.warning(f"Failed to calculate centroid for UTM selection: {e}. Defaulting to EPSG:3857")
                projected_crs = "EPSG:3857"
        else:
            projected_crs = source_crs

    # Transform geometry to projected CRS for accurate calculation in meters
    try:
        projected_geom = transform_geometry(geom, source_crs, projected_crs)
    except Exception as e:
        logger.error(f"Failed to transform geometry for measurement: {e}")
        projected_geom = geom

    try:
        if isinstance(geom, (Polygon, MultiPolygon)):
            area_val = float(projected_geom.area)
            result = MeasurementResult(
                type="area",
                value=round(area_val, 4),
                unit="sq_meters",
                formatted=format_area(area_val)
            )
            return result, projected_crs

        elif isinstance(geom, (LineString, MultiLineString)):
            length_val = float(projected_geom.length)
            result = MeasurementResult(
                type="length",
                value=round(length_val, 4),
                unit="meters",
                formatted=format_length(length_val)
            )
            return result, projected_crs

        elif isinstance(geom, (Point, MultiPoint)):
            # Requirement: Point geometry - no measurement required.
            return None, projected_crs

        else:
            # Graceful handling for unsupported geometry types (GeometryCollection, etc.)
            logger.info(f"Geometry type '{geom_type}' is not supported for area/length measurement.")
            return None, projected_crs

    except Exception as e:
        logger.error(f"Error calculating measurement for geometry {geom_type}: {e}")
        return None, projected_crs
