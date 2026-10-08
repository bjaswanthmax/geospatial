"""Storage service for persisting uploaded file metadata and measurement records."""

import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.models.schemas import FileInfoResponse, FileMeasurementsResponse

logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
DB_FILE = os.path.join(UPLOADS_DIR, "db.json")


class StorageRepository:
    """Thread-safe file and metadata storage repository backed by local disk storage."""

    def __init__(self, storage_dir: str = UPLOADS_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.db_path = os.path.join(self.storage_dir, "db.json")
        self._memory_db: Dict[str, Dict[str, str]] = {}
        self._load_db()

    def _load_db(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self._memory_db = json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata database: {e}")
                self._memory_db = {}

    def _save_db(self):
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._memory_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata database: {e}")

    def generate_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def save_file_record(
        self,
        file_id: str,
        filename: str,
        file_bytes: bytes,
        info: FileInfoResponse,
        measurements: FileMeasurementsResponse
    ) -> FileInfoResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        info.uploaded_at = now_iso
        
        # Save raw uploaded file
        saved_file_path = os.path.join(self.storage_dir, f"{file_id}_{filename}")
        with open(saved_file_path, "wb") as f:
            f.write(file_bytes)

        # Save measurement json file
        meas_path = os.path.join(self.storage_dir, f"{file_id}_measurements.json")
        with open(meas_path, "w", encoding="utf-8") as f:
            f.write(measurements.model_dump_json(indent=2))

        # Update DB index
        self._memory_db[file_id] = {
            "info": info.model_dump(),
            "file_path": saved_file_path,
            "measurements_path": meas_path
        }
        self._save_db()
        return info

    def get_file_info(self, file_id: str) -> Optional[FileInfoResponse]:
        record = self._memory_db.get(file_id)
        if not record:
            return None
        return FileInfoResponse(**record["info"])

    def get_file_measurements(self, file_id: str) -> Optional[FileMeasurementsResponse]:
        record = self._memory_db.get(file_id)
        if not record:
            return None
        meas_path = record.get("measurements_path")
        if meas_path and os.path.exists(meas_path):
            with open(meas_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return FileMeasurementsResponse(**data)
        return None

    def list_all_files(self) -> List[FileInfoResponse]:
        result = []
        for file_id, record in self._memory_db.items():
            result.append(FileInfoResponse(**record["info"]))
        return result

    def delete_file_record(self, file_id: str) -> bool:
        record = self._memory_db.pop(file_id, None)
        if not record:
            return False
        
        for path_key in ("file_path", "measurements_path"):
            p = record.get(path_key)
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as e:
                    logger.warning(f"Failed to delete {p}: {e}")

        self._save_db()
        return True


# Global singleton repository instance
storage_repo = StorageRepository()
