"""
Azure Blob Storage service for document export.

Adapted from apps/mcp/services/azure_blob.py. Provides byte-level upload
with short-lived SAS links (30 minutes) for document downloads.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def _load_azure_deps():
    """Lazy-load azure-storage-blob to tolerate missing deps at import time."""
    from azure.storage.blob import (
        BlobSasPermissions,
        BlobServiceClient,
        ContentSettings,
        generate_blob_sas,
    )
    import pytz

    return BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings, pytz


class AzureBlobService:
    """Upload files to Azure Blob Storage and return time-limited download links."""

    _instance: Optional[AzureBlobService] = None

    def __init__(self, account_name: str, account_key: str):
        self.account_name = account_name
        self.account_key = account_key
        self._client = None
        self._deps = None

    def _get_deps(self):
        if self._deps is None:
            self._deps = _load_azure_deps()
        return self._deps

    @classmethod
    def get_instance(cls) -> Optional[AzureBlobService]:
        if cls._instance is not None:
            return cls._instance

        account_name = os.getenv("AZURE_BLOB_ACCOUNT_NAME", "").strip()
        account_key = os.getenv("AZURE_BLOB_ACCOUNT_KEY", "").strip()

        if not account_name or not account_key:
            logger.warning("Azure Blob env vars missing; blob service unavailable.")
            return None

        try:
            _load_azure_deps()
        except ImportError:
            logger.warning("azure-storage-blob not installed; blob uploads disabled.")
            return None

        cls._instance = cls(account_name=account_name, account_key=account_key)
        return cls._instance

    @property
    def client(self):
        if self._client is None:
            BlobServiceClient, *_ = self._get_deps()
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.account_name};"
                f"AccountKey={self.account_key};"
                f"EndpointSuffix=core.windows.net"
            )
            self._client = BlobServiceClient.from_connection_string(connection_string)
        return self._client

    def _generate_sas_link(
        self, container_name: str, file_name: str, expiry_minutes: int = 30
    ) -> str:
        _, generate_blob_sas, BlobSasPermissions, _, pytz = self._get_deps()
        expiry_time = datetime.now(pytz.utc) + timedelta(minutes=expiry_minutes)
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=container_name,
            blob_name=file_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time,
        )
        encoded_name = urllib.parse.quote(file_name)
        return f"https://{self.account_name}.blob.core.windows.net/{container_name}/{encoded_name}?{sas_token}"

    def upload_bytes(
        self,
        container_name: str,
        file_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        expiry_minutes: int = 30,
    ) -> str:
        """Upload raw bytes and return a time-limited download link."""
        _, _, _, ContentSettings, _ = self._get_deps()
        container_client = self.client.get_container_client(container_name)

        # Ensure container exists
        try:
            container_client.create_container()
        except Exception:
            pass  # Already exists

        container_client.upload_blob(
            file_name,
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )

        return self._generate_sas_link(container_name, file_name, expiry_minutes)
