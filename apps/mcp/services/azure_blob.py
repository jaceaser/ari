"""
Azure Blob Storage service ported from legacy/azure_blob.py.

Provides DataFrame-to-Excel upload and shareable link generation.
Lazily initialized to tolerate missing env vars at import time.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Lazy imports for optional deps
_BlobServiceClient = None
_generate_blob_sas = None
_BlobSasPermissions = None
_pytz = None


def _ensure_imports() -> bool:
    global _BlobServiceClient, _generate_blob_sas, _BlobSasPermissions, _pytz
    if _BlobServiceClient is not None:
        return True
    try:
        from azure.storage.blob import (
            BlobSasPermissions,
            BlobServiceClient,
            generate_blob_sas,
        )
        import pytz

        _BlobServiceClient = BlobServiceClient
        _generate_blob_sas = generate_blob_sas
        _BlobSasPermissions = BlobSasPermissions
        _pytz = pytz
        return True
    except ImportError:
        logger.warning("azure-storage-blob or pytz not installed; blob uploads disabled.")
        return False


class AzureBlobService:
    """Handles uploading DataFrames to Azure Blob Storage as Excel files."""

    _instance: Optional[AzureBlobService] = None

    def __init__(self, account_name: str, account_key: str):
        self.account_name = account_name
        self.account_key = account_key
        self._client = None

    @classmethod
    def get_instance(cls) -> Optional[AzureBlobService]:
        """Lazy singleton from env vars."""
        if cls._instance is not None:
            return cls._instance

        account_name = os.getenv("AZURE_BLOB_ACCOUNT_NAME", "").strip()
        account_key = os.getenv("AZURE_BLOB_ACCOUNT_KEY", "").strip()

        if not account_name or not account_key:
            logger.warning("Azure Blob env vars missing; blob service unavailable.")
            return None

        if not _ensure_imports():
            return None

        cls._instance = cls(account_name=account_name, account_key=account_key)
        return cls._instance

    @property
    def client(self):
        if self._client is None:
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.account_name};"
                f"AccountKey={self.account_key};"
                f"EndpointSuffix=core.windows.net"
            )
            self._client = _BlobServiceClient.from_connection_string(connection_string)
        return self._client

    def _generate_shareable_link(
        self, container_name: str, file_name: str, expiry_days: int = 9
    ) -> str:
        expiry_time = datetime.now(_pytz.utc) + timedelta(days=expiry_days)
        sas_blob = _generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=file_name,
            account_key=self.account_key,
            permission=_BlobSasPermissions(read=True),
            cache_control="max-age=86400",
            expiry=expiry_time,
        )
        return f"https://data.reilabs.ai/{container_name}/{urllib.parse.quote(file_name)}?{sas_blob}"

    def upload_dataframe(
        self,
        container_name: str,
        file_name: str,
        df: pd.DataFrame,
        sheet_name: str = "Leads",
        max_retries: int = 2,
    ) -> str:
        """Upload a DataFrame as Excel and return a shareable link.

        Retries on failure and verifies the blob exists before returning.
        Raises RuntimeError if the blob cannot be confirmed after upload.
        """
        import time

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        container_client = self.client.get_container_client(container_name)

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                excel_buffer.seek(0)
                container_client.upload_blob(file_name, excel_buffer, overwrite=True)
                break
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Blob upload attempt %d/%d failed for %s: %s",
                    attempt, max_retries, file_name, exc,
                )
                if attempt < max_retries:
                    time.sleep(1)
        else:
            raise RuntimeError(
                f"Blob upload failed after {max_retries} attempts: {last_exc}"
            ) from last_exc

        # Verify the blob actually exists before returning a link
        blob_client = container_client.get_blob_client(file_name)
        try:
            props = blob_client.get_blob_properties()
            logger.info(
                "Verified blob %s/%s exists (%d bytes)",
                container_name, file_name, props.size,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Blob upload appeared to succeed but blob not found: {file_name}"
            ) from exc

        return self._generate_shareable_link(container_name, file_name)

    @staticmethod
    def get_dataframe_preview(df: pd.DataFrame, rows: int = 10) -> str:
        """Return a string preview of the first N rows."""
        return df.head(rows).to_string(index=False)
