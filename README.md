# Geospatial File Measurement API

A production-grade backend service built with FastAPI to accept, process, and calculate measurements from geospatial files such as KML and Shapefiles inside ZIP archives.

## Learning and Future Scope

This project was a practical exercise in building a geospatial backend with file ingestion, schema validation, CRS handling, and measurement calculations. The main learning came from combining Python geospatial libraries, API design, and defensive validation for real-world file inputs.

Future scope includes adding support for more geometry types, multi-file batch uploads, database-backed persistence, async background jobs for large files, and a richer front-end dashboard for visualizing feature measurements.

## GitHub Repository

This project is ready to be pushed to a public GitHub repository. The local repository is already initialized in the workspace, and the service can be published with a standard git push once credentials are configured.

---

## Features

- File upload for KML and zipped shapefiles
- Feature extraction with geometry, CRS, and properties
- Area calculation for polygons and length calculation for polylines
- Graceful handling for unsupported geometries
- Automatic geographic-to-projected CRS transformation before measurement
- File metadata storage and retrieval via API

---

## Setup

### Prerequisites
- Python 3.10+
- pip

### 1. Clone and open the project
```bash
git clone <your-repository-url>
cd geospatial-file-measurement-api
```

### 2. Create a virtual environment
On Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```
On Windows PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the API locally
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The app is available at:
- http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 5. Run the tests
```bash
pytest -q
```

---

## API

### Upload a file
POST /api/files/

Request:
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@survey_field.kml"
```

Successful response:
```json
{
  "id": "a1b2c3d4",
  "filename": "survey_field.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "uploaded_at": "2026-10-08T11:45:00.000Z"
}
```

### Get file metadata
GET /api/files/{id}/

Example:
```bash
curl "http://localhost:8000/api/files/a1b2c3d4/"
```

### Get measurements
GET /api/files/{id}/measurements/

Example:
```bash
curl "http://localhost:8000/api/files/a1b2c3d4/measurements/"
```

### List files
GET /api/files/

### Delete a file
DELETE /api/files/{id}/

---

## Architecture

### Application structure
```text
geospatial-file-measurement-api/
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── file_processor.py
│   │   ├── measurement.py
│   │   └── storage.py
│   ├── utils/
│   │   └── crs.py
│   └── main.py
├── tests/
├── uploads/
├── requirements.txt
├── README.md
└── Dockerfile
```

### File-processing flow
1. The API accepts an uploaded file.
2. The route validates the extension and archive integrity.
3. The file processor reads KML or zipped Shapefile contents.
4. Features are normalized into GeoJSON-like objects with geometry, properties, and CRS metadata.
5. The processed data is stored on disk and returned through the API.

### Measurement calculation flow
1. Each feature is inspected by geometry type.
2. Geographic coordinate systems are detected and transformed to an appropriate local UTM projection.
3. Polygon area and line length are calculated using projected coordinates in meters.
4. Point features are returned without a measurement, as required.
5. Unsupported geometries are ignored safely without crashing the request.

### CRS handling
The service treats latitude/longitude data in EPSG:4326 as geographic coordinates. To avoid invalid distance and area calculations in degrees, it selects a local UTM CRS based on the geometry centroid and reprojects the geometry before measuring. This keeps calculations in metric units and makes the output consistent for files created in different locations.

---

## Design Decisions

- FastAPI was chosen because it is lightweight, fast, and well suited to building clean REST APIs with Pydantic validation.
- Shapely and pyproj were used for geometry handling and coordinate transformation because they are widely adopted and reliable for geospatial processing.
- A local JSON-backed repository was chosen instead of a database for simplicity and easy deployment in a coding challenge environment.
- UTM projection was selected dynamically because it provides accurate metric calculations for local datasets without hardcoding a single global CRS.
- A graceful skip for unsupported geometries was preferred over hard failure so the API can still return usable results instead of crashing on a mixed dataset.

---

## Notes

This service intentionally focuses on robust processing of polygon and line features while keeping the architecture simple and readable. The implementation is suitable as a backend foundation for future expansion into geospatial dashboards, larger datasets, and external database storage.

│   ├── utils/
│   │   ├── crs.py            # CRS normalization, UTM selection & projection transformer
│   │   └── validators.py     # File extension, size, and zip structure validation
│   └── main.py               # FastAPI application entry point
├── tests/
│   ├── test_measurements.py  # Unit tests for measurements & CRS projections
│   └── test_upload.py        # Integration tests for upload endpoints
├── uploads/                  # Persistent store for uploaded files & db.json
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

### File Processing Flow
1. **Upload & Validation**: `UploadFile` is received. `validators.py` checks file size, extension (`.kml` or `.zip`), and verifies that ZIP archives contain a `.shp` file.
2. **Parsing & Feature Extraction**:
   - **KML**: Parsed using Python's `xml.etree.ElementTree`. Extracts `Placemark` tags, attributes (`name`, `description`, `ExtendedData`), and coordinate arrays for `Polygon`, `LineString`, `Point`, or `MultiGeometry`.
   - **Shapefile**: Unzipped into a temporary directory. Reads `.prj` (if present) to parse WKT CRS. Uses `pyshp` (`shapefile.Reader`) to extract DBF attribute tables and geometry objects.
3. **Geometry Standardization**: Features are converted into standard `shapely.geometry` objects (`Polygon`, `LineString`, `Point`).
4. **CRS Transformation & Measurement**: Features are passed to `measurement.py` to calculate area or length using a projected coordinate system.
5. **Persistence**: Extracted feature metadata and measurements are saved to `uploads/db.json` and returned via API responses.

---

## 🌍 CRS Handling & Projection Strategy

### Problem Statement
Geospatial files often supply coordinates in geographic coordinate reference systems like **WGS84 (EPSG:4326)**, where coordinates are specified in latitude and longitude degrees. Calculating area or distance directly on degree coordinates yields invalid units (e.g., square degrees).

### Transformation Strategy
To ensure accurate planar measurements in SI units (meters and square meters):
1. **Centroid Calculation**: Compute the geographic centroid $(\text{longitude}, \text{latitude})$ of the feature or dataset.
2. **Dynamic UTM Zone Selection**: Determine the optimal Universal Transverse Mercator (UTM) zone EPSG code based on longitude and hemisphere:
   $$\text{Zone} = \lfloor \frac{\text{longitude} + 180}{6} \rfloor + 1$$
   - Northern Hemisphere ($\text{lat} \ge 0^\circ$): $\text{EPSG} = 32600 + \text{Zone}$
   - Southern Hemisphere ($\text{lat} < 0^\circ$): $\text{EPSG} = 32700 + \text{Zone}$
3. **PyProj Coordinate Transformation**: Use `pyproj.Transformer.from_crs(source_crs, utm_epsg, always_xy=True)` with `shapely.transform` to project coordinates from degrees into linear meters.
4. **Measurement Calculation**: Compute `transformed_geom.area` ($m^2$) for polygons or `transformed_geom.length` ($m$) for lines.

---

## 📐 Design Decisions & Alternatives Considered

1. **FastAPI vs. Django**:
   - **Chosen**: **FastAPI**.
   - **Rationale**: Lightweight execution, high performance (built on Starlette & Pydantic), automatic interactive OpenAPI (Swagger) documentation, and asynchronous I/O support.

2. **Parser Selection: Pure-Python (`pyshp` & `xml.etree`) vs. `GDAL`/`Fiona`**:
   - **Chosen**: `pyshp` (`shapefile`) for Shapefiles and `xml.etree.ElementTree` for KML.
   - **Rationale**: `GDAL`/`fiona`/`geopandas` require C-extensions and system-level binaries (GDAL) which often fail to build or install across different environments (such as Windows or Python 3.14). Pure-Python parsers combined with `shapely` and `pyproj` provide 100% portable, lightweight, and robust geospatial operations anywhere.

3. **Storage Strategy**:
   - **Chosen**: File-backed JSON repository (`storage.py`) with persistent `uploads/` directory.
   - **Rationale**: Avoids external database setup overhead for local execution while ensuring uploaded files and metadata persist reliably across server restarts.

---

## 💡 Learnings & Future Scope

### Learnings
- **Coordinate Order Consistency**: `pyproj` transformers require `always_xy=True` to guarantee $(x, y) \rightarrow (\text{lon}, \text{lat})$ order across projection transformations regardless of standard axis ordering variations in EPSG definitions.
- **ESRI Shapefile Specifications**: ESRI Shapefiles enforce uniform shape types per file and require exterior polygon rings to be ordered in a clockwise direction.
- **File Lock Handling on Windows**: Python's `shapefile.Reader` requires explicit closure (`with shapefile.Reader(...) as reader:`) to avoid holding file locks on temporary directory cleanup on Windows OS.

### Future Scope
- 🗺️ **GeoJSON Support**: Expand file input endpoints to accept `.geojson` and `.gpkg` (GeoPackage) files.
- ⚡ **Asynchronous Background Processing**: Integrate Celery or Redis Queue (RQ) for async background processing of massive multi-gigabyte geospatial files.
- 🗄️ **PostGIS / SpatiaLite Integration**: Replace JSON file storage with a spatial database (PostGIS or SpatiaLite) to allow spatial SQL queries (e.g. bounding box intersection, spatial join).
- 🌐 **Web Map Preview**: Add a simple frontend leaf/mapbox map component to visualize uploaded geospatial features interactively.
