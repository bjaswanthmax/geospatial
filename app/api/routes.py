import io
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.schemas import FileInfoResponse, FileMeasurementsResponse
from app.services.file_processor import process_geospatial_file_data
from app.services.storage import storage_repo

router = APIRouter(prefix="/api")

ALLOWED_EXTENSIONS = {".kml", ".zip"}


@router.post("/files/", response_model=FileInfoResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    if file.filename is None:
        raise HTTPException(status_code=400, detail="A file is required for upload.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Only .kml and .zip files are supported."
        )

    content = await file.read()

    if extension == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                archive.testzip()
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=400,
                detail="Uploaded ZIP file is not a valid ZIP archive."
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"ZIP archive validation failed: {exc}"
            )

    try:
        file_id = storage_repo.generate_id()
        file_info, measurements = process_geospatial_file_data(
            file_id=file_id,
            filename=file.filename,
            file_bytes=content,
            file_ext=extension,
        )
        saved_info = storage_repo.save_file_record(
            file_id=file_id,
            filename=file.filename,
            file_bytes=content,
            info=file_info,
            measurements=measurements,
        )
        return saved_info
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {exc}") from exc


@router.get("/files/", response_model=List[FileInfoResponse])
async def list_files():
    return storage_repo.list_all_files()


@router.get("/files/{file_id}/", response_model=FileInfoResponse)
async def get_file_info(file_id: str):
    info = storage_repo.get_file_info(file_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"File with id '{file_id}' was not found.")
    return info


@router.get("/files/{file_id}/measurements/", response_model=FileMeasurementsResponse)
async def get_file_measurements(file_id: str):
    measurements = storage_repo.get_file_measurements(file_id)
    if measurements is None:
        raise HTTPException(status_code=404, detail=f"Measurements for file id '{file_id}' were not found.")
    return measurements


@router.delete("/files/{file_id}/")
async def delete_file(file_id: str):
    deleted = storage_repo.delete_file_record(file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"File with id '{file_id}' was not found.")
    return {"detail": "File deleted successfully."}