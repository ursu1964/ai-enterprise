import gzip
import hashlib
import io
import json
import tarfile
from typing import Any


class AuditExporter:
    """Builds a deterministic, self-verifying tar archive without artifact bodies."""

    def build(self, files: dict[str, Any]) -> tuple[bytes, str]:
        rendered = {
            name: json.dumps(value, sort_keys=True, indent=2, default=str).encode()
            for name, value in files.items()
        }
        checksums = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in rendered.items()
        }
        rendered["SHA256SUMS.json"] = json.dumps(
            checksums, sort_keys=True, indent=2
        ).encode()
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(rendered):
                content = rendered[name]
                info = tarfile.TarInfo(name)
                info.size = len(content)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(content))
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(tar_buffer.getvalue())
        payload = buffer.getvalue()
        return payload, hashlib.sha256(payload).hexdigest()
