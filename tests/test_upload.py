"""Integration tests for file upload, retrieval, and measurement API endpoints."""

import io
import zipfile
import pytest
import shapefile
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_sample_kml_bytes() -> bytes:
    """Create a sample valid KML file with Polygon, LineString, and Point features."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Agricultural Field</name>
      <description>Corn field parcel 1</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.980,40.750,0
              -73.970,40.750,0
              -73.970,40.760,0
              -73.980,40.760,0
              -73.980,40.750,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Access Road</name>
      <LineString>
        <coordinates>
          -73.980,40.750,0
          -73.970,40.750,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Survey Marker</name>
      <Point>
        <coordinates>-73.975,40.755,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""
    return kml_content.encode('utf-8')


def create_sample_shapefile_zip_bytes() -> bytes:
    """Create an in-memory ZIP containing a valid Shapefile with PRJ, DBF, SHX."""
    shp_io = io.BytesIO()
    shx_io = io.BytesIO()
    dbf_io = io.BytesIO()

    with shapefile.Writer(shp=shp_io, shx=shx_io, dbf=dbf_io, shapeType=shapefile.POLYGON) as w:
        w.field('NAME', 'C', '50')
        w.field('CATEGORY', 'C', '50')
        # Add polygon 1 (clockwise for exterior ring)
        w.poly([[[-73.98, 40.75], [-73.98, 40.76], [-73.97, 40.76], [-73.97, 40.75], [-73.98, 40.75]]])
        w.record('Property Boundary A', 'Real Estate')
        # Add polygon 2 (clockwise for exterior ring)
        w.poly([[[-73.96, 40.75], [-73.96, 40.76], [-73.95, 40.76], [-73.95, 40.75], [-73.96, 40.75]]])
        w.record('Property Boundary B', 'Agriculture')

    prj_wkt = b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'

    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w') as zf:
        zf.writestr('property.shp', shp_io.getvalue())
        zf.writestr('property.shx', shx_io.getvalue())
        zf.writestr('property.dbf', dbf_io.getvalue())
        zf.writestr('property.prj', prj_wkt)
        
    return zip_io.getvalue()


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"


def test_upload_kml_file():
    kml_bytes = create_sample_kml_bytes()
    response = client.post(
        "/api/files/",
        files={"file": ("survey_field.kml", kml_bytes, "application/vnd.google-earth.kml+xml")}
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "survey_field.kml"
    assert data["feature_count"] == 3
    assert data["status"] == "COMPLETED"
    assert data["crs"] == "EPSG:4326"

    file_id = data["id"]

    # Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    assert info_data["id"] == file_id
    assert info_data["feature_count"] == 3

    # Test GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["file_id"] == file_id
    assert len(meas_data["features"]) == 3
    assert "EPSG:32618" in meas_data["projected_crs"] or "EPSG:" in meas_data["projected_crs"]

    # Verify Polygon measurement (Area)
    poly_feat = next(f for f in meas_data["features"] if f["geometry_type"] == "Polygon")
    assert poly_feat["measurement"]["type"] == "area"
    assert poly_feat["measurement"]["value"] > 0
    assert poly_feat["measurement"]["unit"] == "sq_meters"

    # Verify LineString measurement (Length)
    line_feat = next(f for f in meas_data["features"] if f["geometry_type"] == "LineString")
    assert line_feat["measurement"]["type"] == "length"
    assert line_feat["measurement"]["value"] > 0
    assert line_feat["measurement"]["unit"] == "meters"

    # Verify Point measurement is None
    point_feat = next(f for f in meas_data["features"] if f["geometry_type"] == "Point")
    assert point_feat["measurement"] is None


def test_upload_shapefile_zip():
    zip_bytes = create_sample_shapefile_zip_bytes()
    response = client.post(
        "/api/files/",
        files={"file": ("property_data.zip", zip_bytes, "application/zip")}
    )

    assert response.status_code == 201
    data = response.json()
    file_id = data["id"]
    assert data["filename"] == "property_data.zip"
    assert data["feature_count"] == 2
    assert data["status"] == "COMPLETED"

    # Fetch measurements
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert len(meas_data["features"]) == 2


def test_upload_invalid_extension():
    response = client.post(
        "/api/files/",
        files={"file": ("notes.txt", b"Hello World", "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_corrupt_zip():
    response = client.post(
        "/api/files/",
        files={"file": ("bad.zip", b"Not a zip file content", "application/zip")}
    )
    assert response.status_code == 400
    assert "not a valid ZIP archive" in response.json()["detail"] or "ZIP" in response.json()["detail"]


def test_get_non_existent_file():
    response = client.get("/api/files/non_existent_id_999/")
    assert response.status_code == 404
