"""Pydantic schemas for the Geospatial File Measurement API."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MeasurementResult(BaseModel):
    """Schema for feature measurement result."""
    type: str = Field(..., description="Type of measurement: 'area' or 'length'")
    value: float = Field(..., description="Calculated measurement value in standard units (m² for area, m for length)")
    unit: str = Field(..., description="Measurement unit (e.g., 'sq_meters', 'meters')")
    formatted: str = Field(..., description="Human-readable formatted string (e.g., '1,500.25 m² (0.15 ha)')")


class FeatureResponse(BaseModel):
    """Schema for an individual extracted feature from a geospatial file."""
    feature_id: str = Field(..., description="Unique index or identifier for the feature")
    geometry_type: str = Field(..., description="Type of geometry (Polygon, LineString, Point, etc.)")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON representation of geometry")
    crs: str = Field(..., description="Coordinate Reference System of feature")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Attributes/properties extracted from feature")
    measurement: Optional[MeasurementResult] = Field(None, description="Calculated measurement if supported")


class FileInfoResponse(BaseModel):
    """Schema for file upload metadata response."""
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original name of uploaded file")
    feature_count: int = Field(..., description="Number of extracted features")
    crs: str = Field(..., description="Primary CRS detected in file")
    status: str = Field(..., description="Processing status: COMPLETED, FAILED, PROCESSING")
    uploaded_at: str = Field(..., description="ISO timestamp of upload")


class FileMeasurementsResponse(BaseModel):
    """Schema for detailed file measurements response."""
    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original name of uploaded file")
    total_features: int = Field(..., description="Total feature count")
    crs: str = Field(..., description="Original CRS of file")
    projected_crs: str = Field(..., description="Projected CRS used for accurate measurement calculation")
    features: List[FeatureResponse] = Field(..., description="List of features with measurements")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str = Field(..., description="Error message detail")
