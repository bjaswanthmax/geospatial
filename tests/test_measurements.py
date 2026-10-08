"""Unit tests for measurement calculation and CRS projection transformation logic."""

import pytest
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from app.services.measurement import calculate_feature_measurement, format_area, format_length
from app.utils.crs import get_utm_epsg_for_bounds, is_geographic_crs, transform_geometry, normalize_crs


def test_normalize_crs():
    assert normalize_crs("EPSG:4326") == "EPSG:4326"
    assert normalize_crs("4326") == "EPSG:4326"
    assert normalize_crs(None) == "EPSG:4326"
    assert normalize_crs("") == "EPSG:4326"


def test_is_geographic_crs():
    assert is_geographic_crs("EPSG:4326") is True
    assert is_geographic_crs("EPSG:3857") is False
    assert is_geographic_crs("EPSG:32618") is False


def test_get_utm_epsg_for_bounds():
    # New York (approx -74.0, 40.7) -> UTM Zone 18 North -> EPSG:32618
    epsg_ny = get_utm_epsg_for_bounds(-74.0, 40.7)
    assert epsg_ny == "EPSG:32618"

    # Sydney Australia (approx 151.2, -33.8) -> UTM Zone 56 South -> EPSG:32756
    epsg_sydney = get_utm_epsg_for_bounds(151.2, -33.8)
    assert epsg_sydney == "EPSG:32756"

    # London UK (approx -0.1, 51.5) -> UTM Zone 30 North -> EPSG:32630
    epsg_london = get_utm_epsg_for_bounds(-0.1, 51.5)
    assert epsg_london == "EPSG:32630"


def test_polygon_area_measurement():
    # Square polygon (~100m x 100m) in UTM zone 18N (EPSG:32618)
    # Coordinates in meters
    poly_utm = Polygon([(500000, 4000000), (500100, 4000000), (500100, 4000100), (500000, 4000100)])
    
    result, proj_crs = calculate_feature_measurement(poly_utm, "EPSG:32618")
    
    assert result is not None
    assert result.type == "area"
    assert result.unit == "sq_meters"
    assert abs(result.value - 10000.0) < 1.0  # 100m x 100m = 10,000 m²
    assert "10,000" in result.formatted


def test_polygon_area_measurement_geographic():
    # Polygon in WGS84 (EPSG:4326) around NYC ~ ( -73.98, 40.75 )
    # Box ~0.001 deg lat x 0.001 deg lon
    poly_geo = Polygon([
        (-73.980, 40.750),
        (-73.970, 40.750),
        (-73.970, 40.760),
        (-73.980, 40.760)
    ])

    result, proj_crs = calculate_feature_measurement(poly_geo, "EPSG:4326")

    assert result is not None
    assert result.type == "area"
    assert result.unit == "sq_meters"
    assert result.value > 0
    assert proj_crs == "EPSG:32618"  # Computed UTM zone for NYC


def test_linestring_length_measurement():
    # 500 meter straight line in UTM EPSG:32618
    line_utm = LineString([(500000, 4000000), (500500, 4000000)])
    
    result, proj_crs = calculate_feature_measurement(line_utm, "EPSG:32618")

    assert result is not None
    assert result.type == "length"
    assert result.unit == "meters"
    assert abs(result.value - 500.0) < 0.1
    assert "500.00 m" in result.formatted


def test_point_measurement_returns_none():
    pt = Point(-73.98, 40.75)
    result, proj_crs = calculate_feature_measurement(pt, "EPSG:4326")
    
    # Requirement: Point geometry - no measurement required.
    assert result is None


def test_format_area_and_length():
    assert format_area(500.5) == "500.50 m²"
    assert "ha" in format_area(25000)
    assert "km²" in format_area(1500000)

    assert format_length(450) == "450.00 m"
    assert "km" in format_length(2500)
