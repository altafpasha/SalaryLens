"""
SalaryLens AI by CodeSec — Private Storage Service
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Tuple
from app.core.config import settings


class StorageService:
    """
    Manages private on-disk storage for bank statement PDFs and page renders
    with path sanitization and tenant isolation.
    """

    @classmethod
    def get_statement_upload_dir(cls, organization_id: uuid.UUID, statement_id: uuid.UUID) -> Path:
        path = Path(settings.UPLOAD_DIR) / str(organization_id) / str(statement_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_statement_render_dir(cls, organization_id: uuid.UUID, statement_id: uuid.UUID) -> Path:
        path = Path(settings.RENDER_DIR) / str(organization_id) / str(statement_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_statement_workbook_dir(cls, organization_id: uuid.UUID, statement_id: uuid.UUID) -> Path:
        path = Path(settings.STORAGE_ROOT) / "workbooks" / str(organization_id) / str(statement_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def get_statement_workbook_path(cls, organization_id: uuid.UUID, statement_id: uuid.UUID) -> Path:
        target_dir = cls.get_statement_workbook_dir(organization_id, statement_id)
        return target_dir / f"statement_{statement_id}_analysis.xlsx"

    @classmethod
    def save_upload_stream(
        cls,
        organization_id: uuid.UUID,
        statement_id: uuid.UUID,
        file_stream: BinaryIO,
        file_hash: str
    ) -> str:
        """
        Saves the uploaded PDF stream into isolated private storage.
        Returns the absolute filepath string.
        """
        target_dir = cls.get_statement_upload_dir(organization_id, statement_id)
        target_path = target_dir / f"{file_hash}.pdf"

        file_stream.seek(0)
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file_stream, f)

        # Make file read-only by user for security
        os.chmod(target_path, 0o600)
        return str(target_path.resolve())

    @classmethod
    def delete_statement_files(cls, organization_id: uuid.UUID, statement_id: uuid.UUID) -> Tuple[bool, int]:
        """
        Deletes upload, render, and workbook files for a statement during retention purge.
        Returns (success, deleted_file_count).
        """
        deleted_count = 0
        upload_dir = Path(settings.UPLOAD_DIR) / str(organization_id) / str(statement_id)
        render_dir = Path(settings.RENDER_DIR) / str(organization_id) / str(statement_id)
        workbook_dir = Path(settings.STORAGE_ROOT) / "workbooks" / str(organization_id) / str(statement_id)

        for dir_path in [upload_dir, render_dir, workbook_dir]:
            if dir_path.exists() and dir_path.is_dir():
                for item in dir_path.iterdir():
                    if item.is_file():
                        item.unlink()
                        deleted_count += 1
                try:
                    dir_path.rmdir()
                except OSError:
                    pass
        return True, deleted_count
