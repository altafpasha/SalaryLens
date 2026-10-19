"""
Unit tests for Document Processing: PDF validation, storage, and text/scanned extraction
"""
import io
import uuid
from pathlib import Path
import pytest

from app.services.document_processing.validator import DocumentValidator, DocumentValidationError
from app.services.document_processing.storage import StorageService
from app.services.document_processing.extractor import DocumentExtractor


def test_validate_clean_pdf():
    pdf_path = Path("fixtures/synthetic_statements/clean_text_statement.pdf")
    with open(pdf_path, "rb") as f:
        file_hash, size, page_count = DocumentValidator.validate_pdf_stream(f, "clean_text_statement.pdf")
        assert len(file_hash) == 64
        assert size > 0
        assert page_count >= 1


def test_validate_non_pdf_fails():
    fake_stream = io.BytesIO(b"This is just plain text, not a PDF header")
    with pytest.raises(DocumentValidationError, match="Invalid file signature"):
        DocumentValidator.validate_pdf_stream(fake_stream, "test.txt")


def test_validate_corrupt_pdf_fails():
    corrupt_stream = io.BytesIO(b"%PDF-1.4 completely corrupt garbage bytes 1234567890")
    with pytest.raises(DocumentValidationError, match="Corrupt or unreadable"):
        DocumentValidator.validate_pdf_stream(corrupt_stream, "corrupt.pdf")


def test_validate_oversized_page_count_fails():
    pdf_path = Path("fixtures/synthetic_statements/oversized_statement.pdf")
    with open(pdf_path, "rb") as f:
        with pytest.raises(DocumentValidationError, match="Document page count"):
            DocumentValidator.validate_pdf_stream(f, "oversized_statement.pdf")


def test_text_extraction_clean_statement():
    pdf_path = Path("fixtures/synthetic_statements/clean_text_statement.pdf")
    result = DocumentExtractor.extract_document(str(pdf_path))
    assert result.is_scanned is False
    assert result.total_pages >= 1
    assert "GLOBAL METRO BANK" in result.full_text
    assert "ACME TECH CORP SALARY" in result.full_text
    assert result.total_characters > 100


def test_scanned_detection_and_rendering(tmp_path: Path):
    pdf_path = Path("fixtures/synthetic_statements/scanned_image_statement.pdf")
    render_dir = tmp_path / "renders"
    result = DocumentExtractor.extract_document(str(pdf_path), render_dir=render_dir)
    assert result.is_scanned is True
    # Verify rendered PNG was generated
    assert len(result.pages) >= 1
    assert result.pages[0].rendered_image_path is not None
    assert Path(result.pages[0].rendered_image_path).exists()


def test_storage_service_save_and_cleanup(tmp_path: Path):
    org_id = uuid.uuid4()
    stmt_id = uuid.uuid4()
    dummy_stream = io.BytesIO(b"%PDF-1.4 dummy content")
    file_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

    saved_path = StorageService.save_upload_stream(org_id, stmt_id, dummy_stream, file_hash)
    assert Path(saved_path).exists()

    success, count = StorageService.delete_statement_files(org_id, stmt_id)
    assert success is True
    assert count >= 1
    assert not Path(saved_path).exists()
