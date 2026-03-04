"""Tests for the upload endpoint."""

import io
import uuid
import zipfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.upload import router, _validate_extension, _validate_magic_bytes
from app.db import get_session
from app.auth import get_current_user_id, get_current_user_id_upload
from tests.helpers import make_auth_override

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")

_app.dependency_overrides[get_current_user_id] = make_auth_override()
_app.dependency_overrides[get_current_user_id_upload] = make_auth_override()


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestValidateExtension:
    def test_valid_extensions(self):
        """All allowed extensions pass validation."""
        for ext in [".txt", ".csv", ".tsv", ".vcf", ".vcf.gz", ".vcf.zip", ".txt.gz", ".tsv.gz"]:
            _validate_extension(f"genome{ext}")  # should not raise

    def test_invalid_extension(self):
        """Invalid extensions raise HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_extension("genome.exe")
        assert exc_info.value.status_code == 400

    def test_case_insensitive(self):
        """Extension check is case-insensitive."""
        _validate_extension("genome.TXT")
        _validate_extension("genome.Vcf.Gz")


class TestValidateMagicBytes:
    def test_gzip_magic_bytes(self):
        """Gzip files pass validation."""
        _validate_magic_bytes(b"\x1f\x8b" + b"\x00" * 14)

    def test_utf8_text(self):
        """Plain text files pass validation."""
        _validate_magic_bytes(b"# rsid\tchromosome\tposition\tgenotype")

    def test_zip_magic_bytes(self):
        """ZIP files pass validation."""
        _validate_magic_bytes(b"PK\x03\x04" + b"\x00" * 12)

    def test_binary_rejected(self):
        """Non-gzip binary files are rejected."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_magic_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
        assert exc_info.value.status_code == 400


class TestUploadEndpoint:
    def test_upload_success(self, client):
        """Successful upload returns analysis ID and pending status."""
        analysis = MagicMock()
        analysis.id = uuid.uuid4()
        analysis.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)

        session = AsyncMock()
        # Rate limit check returns 0
        rate_result = MagicMock()
        rate_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=rate_result)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda a: setattr(a, 'id', analysis.id) or setattr(a, 'created_at', analysis.created_at))

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        file_content = b"# rsid\tchromosome\tposition\tgenotype\nrs1234\t1\t100\tAG\n"

        with patch("app.routes.upload.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            mock_task.return_value.add_done_callback = MagicMock()
            response = client.post(
                "/api/v1/upload/",
                files={"file": ("genome.txt", io.BytesIO(file_content), "text/plain")},
                data={"ancestry_group": "EUR"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "id" in data

    def test_upload_bad_extension(self, client):
        """Upload with bad extension returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/upload/",
            files={"file": ("genome.exe", io.BytesIO(b"content"), "application/octet-stream")},
            data={"ancestry_group": "EUR"},
        )
        assert response.status_code == 400

    def test_upload_invalid_ancestry(self, client):
        """Upload with invalid ancestry group returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/upload/",
            files={"file": ("genome.txt", io.BytesIO(b"content"), "text/plain")},
            data={"ancestry_group": "INVALID"},
        )
        assert response.status_code == 400

    def test_upload_auto_ancestry_rejected(self, client):
        """Upload with 'auto' ancestry is now rejected (no longer supported)."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/upload/",
            files={"file": ("genome.txt", io.BytesIO(b"content"), "text/plain")},
            data={"ancestry_group": "auto"},
        )
        assert response.status_code == 400

    def test_upload_empty_file(self, client):
        """Upload of empty file returns 400."""
        session = AsyncMock()
        rate_result = MagicMock()
        rate_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=rate_result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/upload/",
            files={"file": ("genome.txt", io.BytesIO(b""), "text/plain")},
            data={"ancestry_group": "EUR"},
        )
        assert response.status_code == 400

    def test_upload_default_ancestry(self, client):
        """Upload without ancestry_group defaults to EUR."""
        analysis = MagicMock()
        analysis.id = uuid.uuid4()
        analysis.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)

        session = AsyncMock()
        rate_result = MagicMock()
        rate_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=rate_result)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda a: setattr(a, 'id', analysis.id) or setattr(a, 'created_at', analysis.created_at))

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        file_content = b"# rsid\tchromosome\tposition\tgenotype\nrs1234\t1\t100\tAG\n"

        with patch("app.routes.upload.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            mock_task.return_value.add_done_callback = MagicMock()
            response = client.post(
                "/api/v1/upload/",
                files={"file": ("genome.txt", io.BytesIO(file_content), "text/plain")},
            )

        assert response.status_code == 200

    def test_all_valid_ancestry_groups(self, client):
        """All 5 valid ancestry groups are accepted."""
        for group in ["EUR", "AFR", "EAS", "SAS", "AMR"]:
            analysis = MagicMock()
            analysis.id = uuid.uuid4()
            analysis.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)

            session = AsyncMock()
            rate_result = MagicMock()
            rate_result.scalar.return_value = 0
            session.execute = AsyncMock(return_value=rate_result)
            session.add = MagicMock()
            session.commit = AsyncMock()
            session.refresh = AsyncMock(side_effect=lambda a: setattr(a, 'id', analysis.id) or setattr(a, 'created_at', analysis.created_at))

            async def override():
                return session

            _app.dependency_overrides[get_session] = override

            file_content = b"# rsid\tchromosome\tposition\tgenotype\nrs1234\t1\t100\tAG\n"

            with patch("app.routes.upload.asyncio.create_task") as mock_task:
                mock_task.return_value = MagicMock()
                mock_task.return_value.add_done_callback = MagicMock()
                response = client.post(
                    "/api/v1/upload/",
                    files={"file": ("genome.txt", io.BytesIO(file_content), "text/plain")},
                    data={"ancestry_group": group},
                )

            assert response.status_code == 200, f"Failed for ancestry group: {group}"

    def test_upload_vcf_zip(self, client):
        """Upload of a .vcf.zip file is accepted."""
        analysis = MagicMock()
        analysis.id = uuid.uuid4()
        analysis.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)

        session = AsyncMock()
        rate_result = MagicMock()
        rate_result.scalar.return_value = 0
        session.execute = AsyncMock(return_value=rate_result)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock(side_effect=lambda a: setattr(a, 'id', analysis.id) or setattr(a, 'created_at', analysis.created_at))

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        # Build a minimal ZIP containing a VCF
        vcf_content = b"##fileformat=VCFv4.1\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n1\t100\trs1234\tA\tG\t.\t.\t.\tGT\t0/1\n"
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("genome.vcf", vcf_content)
        zip_bytes = zip_buf.getvalue()

        with patch("app.routes.upload.asyncio.create_task") as mock_task:
            mock_task.return_value = MagicMock()
            mock_task.return_value.add_done_callback = MagicMock()
            response = client.post(
                "/api/v1/upload/",
                files={"file": ("genome.vcf.zip", io.BytesIO(zip_bytes), "application/zip")},
                data={"ancestry_group": "EUR"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
