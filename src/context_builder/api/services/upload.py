"""Upload service for managing pending claims and document staging."""

import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile


# File validation constants
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB


@dataclass
class PendingDocument:
    """A document uploaded to a pending claim."""

    doc_id: str
    original_filename: str
    file_size: int
    content_type: str
    upload_time: str
    extension: str


@dataclass
class PendingClaim:
    """A claim in staging awaiting pipeline execution."""

    claim_id: str
    created_at: str
    documents: List[PendingDocument] = field(default_factory=list)


class UploadService:
    """Service for managing file uploads and pending claims staging area."""

    def __init__(self, staging_dir: Path, claims_dir: Path):
        """
        Initialize the upload service.

        Args:
            staging_dir: Directory for pending claims (e.g., output/.pending)
            claims_dir: Directory for finalized claims (e.g., output/claims)
        """
        self.staging_dir = staging_dir
        self.claims_dir = claims_dir
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _get_claim_staging_dir(self, claim_id: str) -> Path:
        """Get the staging directory for a specific claim."""
        return self.staging_dir / claim_id

    def _get_manifest_path(self, claim_id: str) -> Path:
        """Get the manifest file path for a pending claim."""
        return self._get_claim_staging_dir(claim_id) / "manifest.json"

    def _get_docs_dir(self, claim_id: str) -> Path:
        """Get the documents directory for a pending claim."""
        return self._get_claim_staging_dir(claim_id) / "docs"

    def _load_manifest(self, claim_id: str) -> Optional[PendingClaim]:
        """Load the manifest for a pending claim."""
        manifest_path = self._get_manifest_path(claim_id)
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return PendingClaim(
            claim_id=data["claim_id"],
            created_at=data["created_at"],
            documents=[PendingDocument(**doc) for doc in data.get("documents", [])],
        )

    def _save_manifest(self, claim: PendingClaim) -> None:
        """Save the manifest for a pending claim."""
        manifest_path = self._get_manifest_path(claim.claim_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "claim_id": claim.claim_id,
            "created_at": claim.created_at,
            "documents": [asdict(doc) for doc in claim.documents],
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def claim_exists_finalized(self, claim_id: str) -> bool:
        """Check if a claim already exists in the finalized claims directory."""
        return (self.claims_dir / claim_id).exists()

    def claim_exists_staging(self, claim_id: str) -> bool:
        """Check if a claim exists in the staging area."""
        return self._get_manifest_path(claim_id).exists()

    def validate_claim_id(self, claim_id: str) -> None:
        """
        Validate that a claim ID is acceptable.

        Raises HTTPException if:
        - claim_id is empty
        - claim_id already exists in finalized claims
        """
        if not claim_id or not claim_id.strip():
            raise HTTPException(status_code=400, detail="Claim ID cannot be empty")

        # Sanitize: only allow alphanumeric, dashes, underscores
        sanitized = "".join(c for c in claim_id if c.isalnum() or c in "-_")
        if sanitized != claim_id:
            raise HTTPException(
                status_code=400,
                detail="Claim ID can only contain alphanumeric characters, dashes, and underscores",
            )

        if self.claim_exists_finalized(claim_id):
            raise HTTPException(
                status_code=400,
                detail=f"Claim '{claim_id}' already exists. Please choose a different ID.",
            )

    def validate_file(self, file: UploadFile) -> str:
        """
        Validate an uploaded file.

        Returns the file extension if valid.
        Raises HTTPException if invalid.
        """
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPG, TXT",
            )

        return ALLOWED_CONTENT_TYPES[file.content_type]

    async def add_document(self, claim_id: str, file: UploadFile) -> PendingDocument:
        """
        Add a document to a pending claim.

        Creates the claim if it doesn't exist in staging.
        """
        # Validate claim ID (only check finalized, staging is OK)
        if not self.claim_exists_staging(claim_id):
            self.validate_claim_id(claim_id)

        # Validate file type
        extension = self.validate_file(file)

        # Read file content and validate size
        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {file_size / 1024 / 1024:.1f}MB. Maximum: 100MB",
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")

        # Generate document ID
        doc_id = str(uuid.uuid4())[:8]

        # Create document entry
        doc = PendingDocument(
            doc_id=doc_id,
            original_filename=file.filename or "unknown",
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            upload_time=datetime.utcnow().isoformat() + "Z",
            extension=extension,
        )

        # Save file to staging
        docs_dir = self._get_docs_dir(claim_id)
        docs_dir.mkdir(parents=True, exist_ok=True)
        file_path = docs_dir / f"{doc_id}{extension}"
        file_path.write_bytes(content)

        # Update manifest
        claim = self._load_manifest(claim_id)
        if claim is None:
            claim = PendingClaim(
                claim_id=claim_id,
                created_at=datetime.utcnow().isoformat() + "Z",
                documents=[],
            )

        claim.documents.append(doc)
        self._save_manifest(claim)

        return doc

    def remove_document(self, claim_id: str, doc_id: str) -> bool:
        """Remove a document from a pending claim."""
        claim = self._load_manifest(claim_id)
        if claim is None:
            return False

        # Find and remove document
        doc_to_remove = None
        for doc in claim.documents:
            if doc.doc_id == doc_id:
                doc_to_remove = doc
                break

        if doc_to_remove is None:
            return False

        # Remove file
        docs_dir = self._get_docs_dir(claim_id)
        file_path = docs_dir / f"{doc_id}{doc_to_remove.extension}"
        if file_path.exists():
            file_path.unlink()

        # Update manifest
        claim.documents = [d for d in claim.documents if d.doc_id != doc_id]
        self._save_manifest(claim)

        return True

    def reorder_documents(self, claim_id: str, doc_ids: List[str]) -> bool:
        """Reorder documents within a pending claim."""
        claim = self._load_manifest(claim_id)
        if claim is None:
            return False

        # Validate all doc_ids exist
        existing_ids = {d.doc_id for d in claim.documents}
        if set(doc_ids) != existing_ids:
            raise HTTPException(
                status_code=400,
                detail="Provided doc_ids don't match existing documents",
            )

        # Reorder
        doc_map = {d.doc_id: d for d in claim.documents}
        claim.documents = [doc_map[doc_id] for doc_id in doc_ids]
        self._save_manifest(claim)

        return True

    def remove_claim(self, claim_id: str) -> bool:
        """Remove a pending claim and all its documents."""
        claim_dir = self._get_claim_staging_dir(claim_id)
        if not claim_dir.exists():
            return False

        shutil.rmtree(claim_dir)
        return True

    def get_pending_claim(self, claim_id: str) -> Optional[PendingClaim]:
        """Get a single pending claim by ID."""
        return self._load_manifest(claim_id)

    def list_pending_claims(self) -> List[PendingClaim]:
        """List all pending claims in the staging area."""
        claims = []

        if not self.staging_dir.exists():
            return claims

        for claim_dir in self.staging_dir.iterdir():
            if not claim_dir.is_dir():
                continue
            if claim_dir.name.startswith("."):
                continue

            claim = self._load_manifest(claim_dir.name)
            if claim:
                claims.append(claim)

        # Sort by creation time, newest first
        claims.sort(key=lambda c: c.created_at, reverse=True)
        return claims

    def move_to_input(self, claim_id: str) -> Path:
        """
        Move a pending claim from staging to a temporary input location for pipeline.

        Returns the input path for pipeline discovery.
        """
        claim = self._load_manifest(claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")

        if not claim.documents:
            raise HTTPException(status_code=400, detail=f"Claim has no documents: {claim_id}")

        # Create input structure for pipeline
        # Pipeline expects: input/{claim_id}/*.{pdf,png,txt}
        input_dir = self.staging_dir.parent / ".input" / claim_id
        input_dir.mkdir(parents=True, exist_ok=True)

        # Copy files to input directory with original filenames
        docs_dir = self._get_docs_dir(claim_id)
        for doc in claim.documents:
            src = docs_dir / f"{doc.doc_id}{doc.extension}"
            # Use original filename to preserve context
            dst = input_dir / doc.original_filename
            if src.exists():
                shutil.copy2(src, dst)

        return input_dir

    def cleanup_staging(self, claim_id: str) -> None:
        """Clean up staging files after successful pipeline run."""
        self.remove_claim(claim_id)

    def cleanup_input(self, claim_id: str) -> None:
        """Clean up temporary input files after pipeline run."""
        input_dir = self.staging_dir.parent / ".input" / claim_id
        if input_dir.exists():
            shutil.rmtree(input_dir)
