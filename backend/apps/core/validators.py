"""Upload validation - extension, size and MIME sniffing (brief section 6)."""
import mimetypes
import os

from django.conf import settings
from django.core.exceptions import ValidationError

#: Extensions that must never be accepted regardless of configuration.
DANGEROUS_EXTENSIONS = {
    "exe", "com", "bat", "cmd", "sh", "ps1", "msi", "dll", "scr", "jar",
    "js", "vbs", "php", "phtml", "py", "pl", "cgi", "asp", "aspx", "htaccess",
}

EXTENSION_MIME_MAP = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "text/plain"},
    "txt": {"text/plain"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "webp": {"image/webp"},
    "mp4": {"video/mp4"},
    "zip": {"application/zip", "application/x-zip-compressed"},
}

#: Magic-number prefixes for the formats where sniffing is cheap and reliable.
MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "zip": [b"PK\x03\x04"],
    "docx": [b"PK\x03\x04"],
    "xlsx": [b"PK\x03\x04"],
    "pptx": [b"PK\x03\x04"],
}


def get_extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".")


def validate_upload(uploaded_file, allowed_extensions=None, max_size_mb=None):
    """Validate an uploaded file. Raises ``ValidationError`` when unsafe."""
    if uploaded_file is None:
        return uploaded_file

    allowed = {
        ext.lower().lstrip(".")
        for ext in (allowed_extensions or settings.ALLOWED_UPLOAD_EXTENSIONS)
    }
    limit_mb = max_size_mb or settings.MAX_UPLOAD_SIZE_MB
    extension = get_extension(uploaded_file.name)

    if not extension:
        raise ValidationError("Files must have an extension.")
    if extension in DANGEROUS_EXTENSIONS:
        raise ValidationError("Executable and script files cannot be uploaded.")
    if extension not in allowed:
        raise ValidationError(
            "'.%s' files are not allowed here. Permitted types: %s."
            % (extension, ", ".join(sorted(allowed)))
        )

    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > limit_mb:
        raise ValidationError(
            "File is %.1f MB - the maximum allowed size is %s MB." % (size_mb, limit_mb)
        )
    if uploaded_file.size == 0:
        raise ValidationError("The uploaded file is empty.")

    # Declared content type must be consistent with the extension.
    declared = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    expected = EXTENSION_MIME_MAP.get(extension)
    if declared and expected and declared not in expected:
        guessed, _ = mimetypes.guess_type(uploaded_file.name)
        if guessed not in expected:
            raise ValidationError(
                "The file content type (%s) does not match its '.%s' extension." % (declared, extension)
            )

    # Magic-number sniffing catches renamed files.
    signatures = MAGIC_SIGNATURES.get(extension)
    if signatures:
        pos = uploaded_file.tell() if hasattr(uploaded_file, "tell") else 0
        try:
            uploaded_file.seek(0)
            header = uploaded_file.read(16)
        finally:
            uploaded_file.seek(pos)
        if not any(header.startswith(sig) for sig in signatures):
            raise ValidationError(
                "The file contents do not match a valid '.%s' file." % extension
            )

    return uploaded_file


def safe_filename(filename: str) -> str:
    """Strip directory traversal and unsafe characters from a filename."""
    base = os.path.basename(filename or "file")
    keep = "-_. ()[]"
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in keep).strip()
    return cleaned or "file"
