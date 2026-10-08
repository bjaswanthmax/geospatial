"""File processor service for parsing Shapefile (.zip) and KML (.kml) geospatial formats."""

import io
import os
import tempfile
import zipfile
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple, Optional

import shapefile  # pyshp
from shapely.geometry import shape, Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from shapely.geometry import mapping
import pyproj

from app.models.schemas import FeatureResponse, FileInfoResponse, FileMeasurementsResponse
from app.utils.crs import normalize_crs, DEFAULT_GEOGRAPHIC_CRS
from app.services.measurement import calculate_feature_measurement

logger = logging.getLogger(__name__)


def parse_kml_coordinates(coords_str: str) -> List[Tuple[float, float]]:
    """Parse KML coordinates string into a list of (longitude, latitude) tuples."""
    coords = []
    if not coords_str:
        return coords
        
    raw_tuples = coords_str.strip().split()
    for item in raw_tuples:
        parts = item.strip().split(',')
        if len(parts) >= 2:
            try:
                lon = float(parts[0])
                lat = float(parts[1])
                coords.append((lon, lat))
            except ValueError:
                continue
    return coords


def parse_kml_geometry(elem: ET.Element, ns: str) -> Optional[BaseGeometry]:
    """Recursively parse KML geometry XML element to Shapely geometry."""
    tag = elem.tag.replace(ns, "")
    
    if tag == "Point":
        coords_elem = elem.find(f"{ns}coordinates")
        if coords_elem is not None and coords_elem.text:
            coords = parse_kml_coordinates(coords_elem.text)
            if coords:
                return Point(coords[0])
                
    elif tag == "LineString":
        coords_elem = elem.find(f"{ns}coordinates")
        if coords_elem is not None and coords_elem.text:
            coords = parse_kml_coordinates(coords_elem.text)
            if len(coords) >= 2:
                return LineString(coords)
                
    elif tag == "Polygon":
        outer_elem = elem.find(f".//{ns}outerBoundaryIs/{ns}LinearRing/{ns}coordinates")
        if outer_elem is not None and outer_elem.text:
            outer_coords = parse_kml_coordinates(outer_elem.text)
            if len(outer_coords) >= 3:
                inner_rings = []
                for inner in elem.findall(f".//{ns}innerBoundaryIs/{ns}LinearRing/{ns}coordinates"):
                    if inner.text:
                        in_coords = parse_kml_coordinates(inner.text)
                        if len(in_coords) >= 3:
                            inner_rings.append(in_coords)
                return Polygon(shell=outer_coords, holes=inner_rings)
                
    elif tag == "MultiGeometry":
        sub_geoms = []
        for child in elem:
            child_geom = parse_kml_geometry(child, ns)
            if child_geom is not None:
                sub_geoms.append(child_geom)
        if sub_geoms:
            # Try combining sub geometries into standard Multi-types if homogeneous
            geom_types = set(g.geom_type for g in sub_geoms)
            if geom_types == {"Polygon"}:
                return MultiPolygon(sub_geoms)
            elif geom_types == {"LineString"}:
                return MultiLineString(sub_geoms)
            elif geom_types == {"Point"}:
                return MultiPoint(sub_geoms)
            else:
                return GeometryCollection(sub_geoms)

    return None


def extract_kml_placemarks(kml_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
    """Parse KML content and extract placemark features. Returns (features, crs)."""
    crs = DEFAULT_GEOGRAPHIC_CRS
    features = []
    
    try:
        tree = ET.ElementTree(ET.fromstring(kml_bytes))
        root = tree.getroot()
        
        # Extract XML namespace e.g. {http://www.opengis.net/kml/2.2}
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag[:root.tag.find("}") + 1]
            
        placemarks = root.findall(f".//{ns}Placemark")
        
        for idx, pm in enumerate(placemarks):
            feature_id = f"feature_{idx}"
            props = {}
            
            name_elem = pm.find(f"{ns}name")
            if name_elem is not None and name_elem.text:
                props["name"] = name_elem.text.strip()
                feature_id = props["name"]
                
            desc_elem = pm.find(f"{ns}description")
            if desc_elem is not None and desc_elem.text:
                props["description"] = desc_elem.text.strip()

            # ExtendedData extraction
            for data in pm.findall(f".//{ns}Data"):
                data_name = data.get("name")
                val_elem = data.find(f"{ns}value")
                if data_name and val_elem is not None and val_elem.text:
                    props[data_name] = val_elem.text.strip()

            for sdata in pm.findall(f".//{ns}SimpleData"):
                sdata_name = sdata.get("name")
                if sdata_name and sdata.text:
                    props[sdata_name] = sdata.text.strip()

            # Find geometry tag inside Placemark
            geom = None
            for child in pm:
                child_tag = child.tag.replace(ns, "")
                if child_tag in ("Point", "LineString", "Polygon", "MultiGeometry"):
                    geom = parse_kml_geometry(child, ns)
                    if geom is not None:
                        break

            if geom is not None:
                features.append({
                    "id": str(feature_id),
                    "geometry": geom,
                    "properties": props
                })

    except Exception as e:
        logger.error(f"Error parsing KML content: {e}")
        raise ValueError(f"Failed to parse KML file: {str(e)}")

    return features, crs


def extract_shapefile_features(zip_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
    """Parse Shapefile inside ZIP archive. Returns (features, crs)."""
    features = []
    crs = DEFAULT_GEOGRAPHIC_CRS

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "shapefile.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)

        # Locate .shp file
        shp_file = None
        prj_file = None
        for root_dir, _, files in os.walk(tmpdir):
            for file in files:
                if file.lower().endswith(".shp"):
                    shp_file = os.path.join(root_dir, file)
                elif file.lower().endswith(".prj"):
                    prj_file = os.path.join(root_dir, file)

        if not shp_file:
            raise ValueError("No .shp file found in ZIP archive.")

        # Read CRS from .prj if available
        if prj_file:
            try:
                with open(prj_file, 'r', encoding='utf-8', errors='ignore') as pf:
                    wkt = pf.read().strip()
                    if wkt:
                        parsed_crs = pyproj.CRS.from_wkt(wkt)
                        epsg = parsed_crs.to_epsg()
                        if epsg:
                            crs = f"EPSG:{epsg}"
                        else:
                            crs = parsed_crs.name or crs
            except Exception as e:
                logger.warning(f"Could not parse .prj file: {e}. Defaulting to EPSG:4326.")

        crs = normalize_crs(crs)

        # Read shapefile using pyshp
        try:
            with shapefile.Reader(shp_file) as reader:
                for idx, shape_rec in enumerate(reader.shapeRecords()):
                    shp_geom = shape_rec.shape
                    # Convert pyshp geo interface to Shapely geometry
                    if shp_geom and shp_geom.shapeType != shapefile.NULL:
                        try:
                            geo_dict = shp_geom.__geo_interface__
                            geom = shape(geo_dict)
                            rec_dict = shape_rec.record.as_dict() if hasattr(shape_rec.record, 'as_dict') else {}
                            
                            # Clean up rec_dict keys/values
                            clean_props = {str(k): (v if not isinstance(v, bytes) else v.decode('utf-8', errors='ignore'))
                                           for k, v in rec_dict.items()}

                            features.append({
                                "id": f"feature_{idx}",
                                "geometry": geom,
                                "properties": clean_props
                            })
                        except Exception as ge:
                            logger.warning(f"Skipping corrupt geometry index {idx}: {ge}")
        except Exception as e:
            logger.error(f"Error reading shapefile with pyshp: {e}")
            raise ValueError(f"Failed to read Shapefile: {str(e)}")

    return features, crs


def process_geospatial_file_data(
    file_id: str,
    filename: str,
    file_bytes: bytes,
    file_ext: str
) -> Tuple[FileInfoResponse, FileMeasurementsResponse]:
    """Process uploaded geospatial file and return FileInfo and FileMeasurements models."""
    if file_ext == ".kml":
        raw_features, dataset_crs = extract_kml_placemarks(file_bytes)
    elif file_ext == ".zip":
        raw_features, dataset_crs = extract_shapefile_features(file_bytes)
    else:
        raise ValueError(f"Unsupported extension '{file_ext}'")

    feature_responses: List[FeatureResponse] = []
    projected_crs_used: str = dataset_crs

    for idx, raw_feat in enumerate(raw_features):
        geom: BaseGeometry = raw_feat["geometry"]
        feat_id = raw_feat.get("id", f"feature_{idx}")
        props = raw_feat.get("properties", {})

        # Calculate measurement and get projected CRS
        measurement, proj_crs = calculate_feature_measurement(
            geom=geom,
            source_crs=dataset_crs,
            target_projected_crs=None if projected_crs_used == dataset_crs else projected_crs_used
        )
        if proj_crs and proj_crs != dataset_crs:
            projected_crs_used = proj_crs

        geo_json = mapping(geom)

        feature_responses.append(
            FeatureResponse(
                feature_id=str(feat_id),
                geometry_type=geom.geom_type,
                geometry=geo_json,
                crs=dataset_crs,
                properties=props,
                measurement=measurement
            )
        )

    file_info = FileInfoResponse(
        id=file_id,
        filename=filename,
        feature_count=len(feature_responses),
        crs=dataset_crs,
        status="COMPLETED",
        uploaded_at=""  # will be populated by caller/storage
    )

    file_measurements = FileMeasurementsResponse(
        file_id=file_id,
        filename=filename,
        total_features=len(feature_responses),
        crs=dataset_crs,
        projected_crs=projected_crs_used,
        features=feature_responses
    )

    return file_info, file_measurements
