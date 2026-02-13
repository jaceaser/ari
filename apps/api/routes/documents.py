"""
Document endpoints: export (markdown → DOCX) and file upload (to Azure Blob).

POST /documents/export
POST /documents/upload
"""

import logging
import re
import time
import uuid

from quart import jsonify, request

from . import documents_bp

logger = logging.getLogger("api.documents")

_ALLOWED_UPLOAD_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
}
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

_MAX_CONTENT_LEN = 200_000  # ~200KB of markdown


def _slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] or "document"


@documents_bp.post("/documents/export")
async def export_document():
    """Convert markdown content to DOCX and return a download URL."""
    from services.azure_blob import AzureBlobService
    from services.docx_export import markdown_to_docx

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    blob = AzureBlobService.get_instance()
    if not blob:
        return jsonify({"error": "Document export not configured (blob storage unavailable)"}), 503

    body = await request.get_json(silent=True) or {}
    content = body.get("content", "")
    title = body.get("title", "Document")

    if not isinstance(content, str) or not content.strip():
        return jsonify({"error": "content is required"}), 400

    if len(content) > _MAX_CONTENT_LEN:
        return jsonify({"error": f"Content too large (max {_MAX_CONTENT_LEN} chars)"}), 400

    if not isinstance(title, str):
        title = "Document"

    title = title.strip()[:200] or "Document"

    try:
        buffer = markdown_to_docx(content, title)
    except Exception:
        logger.exception("DOCX generation failed")
        return jsonify({"error": "Failed to generate document"}), 500

    slug = _slugify(title)
    timestamp = int(time.time())
    filename = f"{slug}_{timestamp}.docx"

    try:
        url = blob.upload_bytes(
            container_name="documents",
            file_name=filename,
            data=buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            expiry_minutes=30,
        )
    except Exception:
        logger.exception("Blob upload failed")
        return jsonify({"error": "Failed to upload document"}), 500

    return jsonify({"url": url, "filename": filename})


@documents_bp.post("/documents/upload")
async def upload_file():
    """Upload a file (image, PDF, Word doc) to Azure Blob and return a public URL."""
    from services.azure_blob import AzureBlobService

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    blob = AzureBlobService.get_instance()
    if not blob:
        return jsonify({"error": "File upload not configured (blob storage unavailable)"}), 503

    files = await request.files
    file = files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_UPLOAD_TYPES:
        return jsonify({
            "error": f"File type not allowed: {content_type}. Accepted: JPEG, PNG, WebP, GIF, PDF, Word"
        }), 400

    data = file.read()
    if len(data) > _MAX_UPLOAD_SIZE:
        return jsonify({"error": "File size exceeds 10MB limit"}), 400

    # Generate a unique filename preserving the original extension
    original_name = file.filename or "file"
    ext = original_name.rsplit(".", 1)[-1] if "." in original_name else "bin"
    unique_name = f"{uuid.uuid4().hex[:12]}_{int(time.time())}.{ext}"

    try:
        url = blob.upload_bytes(
            container_name="uploads",
            file_name=unique_name,
            data=data,
            content_type=content_type,
            expiry_minutes=60 * 24,  # 24-hour link for chat attachments
        )
    except Exception:
        logger.exception("File upload to blob failed")
        return jsonify({"error": "Upload failed"}), 500

    return jsonify({
        "url": url,
        "pathname": original_name,
        "contentType": content_type,
    })
