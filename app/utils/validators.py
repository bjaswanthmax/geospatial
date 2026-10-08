"""File upload validation utilities."""

import os
import zipfile
from typing import Tuple
from fastapi import HTTPException, status, UploadFile

ALLOWED_EXTENSIONS = {".kml", ".zip"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit


def validate_uploaded_file(file: UploadFile, content: bytes) -> str:
    """Validate uploaded geospatial file extension and structure.
    
    Returns normalized extension (e.g. '.kml' or '.zip').
    Raises HTTPException(400) if file is invalid.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty."
        )
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. API only accepts '.kml' or Shapefile inside '.zip'."
        )
        
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f}MB."
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if ext == ".zip":
        try:
            with zipfile.ZipFile(file.file if hasattr(file.file, 'read') else zipfile.io.BytesIO(content)) as zf:
                filenames = zf.namelist()
                shp_files = [f for f in filenames if f.lower().endswith(".shp")]
                if not shp_files:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Uploaded ZIP archive does not contain any .shp (Shapefile) file."
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded ZIP file is corrupted or not a valid ZIP archive."
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error inspecting ZIP archive: {str(e)}"
            )

    return ext
