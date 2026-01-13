"""Unit tests for UploadService."""

import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from context_builder.api.services.upload import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE_BYTES,
    PendingClaim,
    PendingDocument,
    UploadService,
)


@pytest.fixture
def upload_service(tmp_path):
    """Create an UploadService with temporary directories."""
    staging_dir = tmp_path / ".pending"
    claims_dir = tmp_path / "claims"
    return UploadService(staging_dir, claims_dir)


@pytest.fixture
def mock_upload_file():
    """Factory for creating mock UploadFile objects."""

    def _create(filename: str, content: bytes, content_type: str):
        file_obj = BytesIO(content)
        upload = MagicMock(spec=UploadFile)
        upload.filename = filename
        upload.content_type = content_type
        upload.read = MagicMock(return_value=content)
        # Make read async
        async def async_read():
            return content
        upload.read = async_read
        return upload

    return _create


class TestUploadServiceInit:
    """Tests for UploadService initialization."""

    def test_creates_staging_dir(self, tmp_path):
        """Staging directory is created on init."""
        staging_dir = tmp_path / ".pending"
        claims_dir = tmp_path / "claims"

        assert not staging_dir.exists()

        UploadService(staging_dir, claims_dir)

        assert staging_dir.exists()


class TestValidateClaimId:
    """Tests for claim ID validation."""

    def test_valid_claim_id(self, upload_service):
        """Valid claim IDs pass validation."""
        upload_service.validate_claim_id("CLAIM-001")
        upload_service.validate_claim_id("claim_123")
        upload_service.validate_claim_id("Test123")

    def test_empty_claim_id_raises(self, upload_service):
        """Empty claim IDs are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_claim_id("")
        assert exc_info.value.status_code == 400
        assert "empty" in str(exc_info.value.detail).lower()

    def test_whitespace_claim_id_raises(self, upload_service):
        """Whitespace-only claim IDs are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_claim_id("   ")
        assert exc_info.value.status_code == 400

    def test_invalid_characters_raises(self, upload_service):
        """Claim IDs with invalid characters are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_claim_id("claim/id")
        assert exc_info.value.status_code == 400
        assert "alphanumeric" in str(exc_info.value.detail).lower()

    def test_existing_claim_raises(self, upload_service, tmp_path):
        """Claim IDs that already exist in finalized claims are rejected."""
        # Create existing claim
        (tmp_path / "claims" / "EXISTING-001").mkdir(parents=True)

        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_claim_id("EXISTING-001")
        assert exc_info.value.status_code == 400
        assert "already exists" in str(exc_info.value.detail).lower()


class TestValidateFile:
    """Tests for file validation."""

    def test_valid_pdf(self, upload_service, mock_upload_file):
        """PDF files pass validation."""
        file = mock_upload_file("test.pdf", b"%PDF-1.4", "application/pdf")
        ext = upload_service.validate_file(file)
        assert ext == ".pdf"

    def test_valid_png(self, upload_service, mock_upload_file):
        """PNG files pass validation."""
        file = mock_upload_file("test.png", b"\x89PNG", "image/png")
        ext = upload_service.validate_file(file)
        assert ext == ".png"

    def test_valid_jpg(self, upload_service, mock_upload_file):
        """JPEG files pass validation."""
        file = mock_upload_file("test.jpg", b"\xff\xd8\xff", "image/jpeg")
        ext = upload_service.validate_file(file)
        assert ext == ".jpg"

    def test_valid_txt(self, upload_service, mock_upload_file):
        """Text files pass validation."""
        file = mock_upload_file("test.txt", b"Hello world", "text/plain")
        ext = upload_service.validate_file(file)
        assert ext == ".txt"

    def test_invalid_content_type_raises(self, upload_service, mock_upload_file):
        """Unsupported content types are rejected."""
        file = mock_upload_file("test.exe", b"MZ", "application/octet-stream")
        with pytest.raises(HTTPException) as exc_info:
            upload_service.validate_file(file)
        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value.detail)


class TestAddDocument:
    """Tests for adding documents to pending claims."""

    @pytest.mark.asyncio
    async def test_creates_claim_on_first_upload(self, upload_service, mock_upload_file):
        """A new claim is created when uploading to a non-existent claim."""
        file = mock_upload_file("document.pdf", b"%PDF-1.4 test content", "application/pdf")

        doc = await upload_service.add_document("NEW-CLAIM", file)

        assert doc.doc_id
        assert doc.original_filename == "document.pdf"
        assert doc.file_size == len(b"%PDF-1.4 test content")
        assert doc.content_type == "application/pdf"

        # Claim should exist in staging
        claim = upload_service.get_pending_claim("NEW-CLAIM")
        assert claim is not None
        assert len(claim.documents) == 1

    @pytest.mark.asyncio
    async def test_adds_to_existing_claim(self, upload_service, mock_upload_file):
        """Documents can be added to existing pending claims."""
        file1 = mock_upload_file("doc1.pdf", b"%PDF-1.4 first", "application/pdf")
        file2 = mock_upload_file("doc2.pdf", b"%PDF-1.4 second", "application/pdf")

        await upload_service.add_document("CLAIM-001", file1)
        await upload_service.add_document("CLAIM-001", file2)

        claim = upload_service.get_pending_claim("CLAIM-001")
        assert len(claim.documents) == 2

    @pytest.mark.asyncio
    async def test_file_saved_to_staging(self, upload_service, mock_upload_file, tmp_path):
        """Uploaded files are saved to the staging directory."""
        content = b"%PDF-1.4 test content"
        file = mock_upload_file("document.pdf", content, "application/pdf")

        doc = await upload_service.add_document("TEST-CLAIM", file)

        file_path = tmp_path / ".pending" / "TEST-CLAIM" / "docs" / f"{doc.doc_id}.pdf"
        assert file_path.exists()
        assert file_path.read_bytes() == content

    @pytest.mark.asyncio
    async def test_empty_file_raises(self, upload_service, mock_upload_file):
        """Empty files are rejected."""
        file = mock_upload_file("empty.pdf", b"", "application/pdf")

        with pytest.raises(HTTPException) as exc_info:
            await upload_service.add_document("CLAIM-001", file)
        assert exc_info.value.status_code == 400
        assert "empty" in str(exc_info.value.detail).lower()


class TestRemoveDocument:
    """Tests for removing documents from pending claims."""

    @pytest.mark.asyncio
    async def test_removes_document(self, upload_service, mock_upload_file):
        """Documents can be removed from pending claims."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        doc = await upload_service.add_document("CLAIM-001", file)

        result = upload_service.remove_document("CLAIM-001", doc.doc_id)

        assert result is True
        claim = upload_service.get_pending_claim("CLAIM-001")
        assert len(claim.documents) == 0

    def test_remove_nonexistent_document(self, upload_service):
        """Removing a nonexistent document returns False."""
        result = upload_service.remove_document("CLAIM-001", "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_removes_file_from_disk(self, upload_service, mock_upload_file, tmp_path):
        """Removing a document deletes the file from disk."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        doc = await upload_service.add_document("CLAIM-001", file)

        file_path = tmp_path / ".pending" / "CLAIM-001" / "docs" / f"{doc.doc_id}.pdf"
        assert file_path.exists()

        upload_service.remove_document("CLAIM-001", doc.doc_id)

        assert not file_path.exists()


class TestReorderDocuments:
    """Tests for reordering documents within a claim."""

    @pytest.mark.asyncio
    async def test_reorder_documents(self, upload_service, mock_upload_file):
        """Documents can be reordered within a claim."""
        file1 = mock_upload_file("doc1.pdf", b"%PDF-1.4 1", "application/pdf")
        file2 = mock_upload_file("doc2.pdf", b"%PDF-1.4 2", "application/pdf")
        file3 = mock_upload_file("doc3.pdf", b"%PDF-1.4 3", "application/pdf")

        doc1 = await upload_service.add_document("CLAIM-001", file1)
        doc2 = await upload_service.add_document("CLAIM-001", file2)
        doc3 = await upload_service.add_document("CLAIM-001", file3)

        # Reorder: 3, 1, 2
        new_order = [doc3.doc_id, doc1.doc_id, doc2.doc_id]
        result = upload_service.reorder_documents("CLAIM-001", new_order)

        assert result is True
        claim = upload_service.get_pending_claim("CLAIM-001")
        assert [d.doc_id for d in claim.documents] == new_order

    @pytest.mark.asyncio
    async def test_reorder_with_wrong_ids_raises(self, upload_service, mock_upload_file):
        """Reordering with wrong doc IDs raises an error."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)

        with pytest.raises(HTTPException) as exc_info:
            upload_service.reorder_documents("CLAIM-001", ["wrong-id"])
        assert exc_info.value.status_code == 400


class TestRemoveClaim:
    """Tests for removing entire pending claims."""

    @pytest.mark.asyncio
    async def test_removes_claim_and_files(self, upload_service, mock_upload_file, tmp_path):
        """Removing a claim deletes all files and directories."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)

        claim_dir = tmp_path / ".pending" / "CLAIM-001"
        assert claim_dir.exists()

        result = upload_service.remove_claim("CLAIM-001")

        assert result is True
        assert not claim_dir.exists()

    def test_remove_nonexistent_claim(self, upload_service):
        """Removing a nonexistent claim returns False."""
        result = upload_service.remove_claim("NONEXISTENT")
        assert result is False


class TestListPendingClaims:
    """Tests for listing pending claims."""

    @pytest.mark.asyncio
    async def test_lists_all_claims(self, upload_service, mock_upload_file):
        """All pending claims are listed."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)
        await upload_service.add_document("CLAIM-002", file)
        await upload_service.add_document("CLAIM-003", file)

        claims = upload_service.list_pending_claims()

        assert len(claims) == 3
        claim_ids = {c.claim_id for c in claims}
        assert claim_ids == {"CLAIM-001", "CLAIM-002", "CLAIM-003"}

    def test_empty_staging_returns_empty_list(self, upload_service):
        """Empty staging area returns empty list."""
        claims = upload_service.list_pending_claims()
        assert claims == []


class TestMoveToInput:
    """Tests for moving claims to input directory."""

    @pytest.mark.asyncio
    async def test_moves_files_to_input(self, upload_service, mock_upload_file, tmp_path):
        """Files are copied to input directory with original filenames."""
        file = mock_upload_file("original-name.pdf", b"%PDF-1.4 content", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)

        input_path = upload_service.move_to_input("CLAIM-001")

        assert input_path.exists()
        copied_file = input_path / "original-name.pdf"
        assert copied_file.exists()
        assert copied_file.read_bytes() == b"%PDF-1.4 content"

    def test_move_empty_claim_raises(self, upload_service, tmp_path):
        """Moving a claim with no documents raises an error."""
        # Create empty claim
        staging_dir = tmp_path / ".pending" / "EMPTY-CLAIM"
        staging_dir.mkdir(parents=True)
        manifest = {
            "claim_id": "EMPTY-CLAIM",
            "created_at": "2025-01-01T00:00:00Z",
            "documents": [],
        }
        (staging_dir / "manifest.json").write_text(json.dumps(manifest))

        with pytest.raises(HTTPException) as exc_info:
            upload_service.move_to_input("EMPTY-CLAIM")
        assert exc_info.value.status_code == 400
        assert "no documents" in str(exc_info.value.detail).lower()

    def test_move_nonexistent_claim_raises(self, upload_service):
        """Moving a nonexistent claim raises an error."""
        with pytest.raises(HTTPException) as exc_info:
            upload_service.move_to_input("NONEXISTENT")
        assert exc_info.value.status_code == 404


class TestCleanup:
    """Tests for cleanup functions."""

    @pytest.mark.asyncio
    async def test_cleanup_staging(self, upload_service, mock_upload_file, tmp_path):
        """Cleanup removes staging directory for a claim."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)

        staging_dir = tmp_path / ".pending" / "CLAIM-001"
        assert staging_dir.exists()

        upload_service.cleanup_staging("CLAIM-001")

        assert not staging_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_input(self, upload_service, mock_upload_file, tmp_path):
        """Cleanup removes input directory for a claim."""
        file = mock_upload_file("doc.pdf", b"%PDF-1.4", "application/pdf")
        await upload_service.add_document("CLAIM-001", file)
        input_path = upload_service.move_to_input("CLAIM-001")

        assert input_path.exists()

        upload_service.cleanup_input("CLAIM-001")

        assert not input_path.exists()
