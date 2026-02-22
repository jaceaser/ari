from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import os
import pytz
import urllib.parse
from io import BytesIO
import pandas as pd
import logging
from typing import Union, Optional

class AzureBlobService:
    """Service for handling Azure Blob Storage operations"""
    
    def __init__(self, config: dict):
        """
        Initialize the Azure Blob Service.
        
        Args:
            config: Configuration dictionary containing Azure Blob settings
        """
        self.config = config
        self.blob_service_client = self._init_client()
        self.container_clients = {}

    def _init_client(self) -> BlobServiceClient:
        """Initialize the blob service client"""
        try:
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.config['ACCOUNT_NAME']};"
                f"AccountKey={self.config['ACCOUNT_KEY']};"
                f"EndpointSuffix=core.windows.net"
            )
            return BlobServiceClient.from_connection_string(connection_string)
        except Exception as e:
            logging.error(f"Failed to initialize Azure Blob client: {str(e)}")
            raise

    def _get_container_client(self, container_name: str):
        """Get or create a container client"""
        if container_name not in self.container_clients:
            self.container_clients[container_name] = self.blob_service_client.get_container_client(container_name)
        return self.container_clients[container_name]

    def _generate_shareable_link(self, container_name: str, file_name: str, expiry_days: int = 9) -> str:
        """
        Generate a shareable link for a blob.
        
        Args:
            container_name: Name of the container
            file_name: Name of the file
            expiry_days: Number of days until link expiry
            
        Returns:
            str: Shareable URL for the blob
        """
        try:
            expiry_time = datetime.now(pytz.utc) + timedelta(days=expiry_days)
            cache_control = 'max-age=86400'
            
            sas_blob = generate_blob_sas(
                account_name=self.config['ACCOUNT_NAME'],
                container_name=container_name,
                blob_name=file_name,
                account_key=self.config['ACCOUNT_KEY'],
                permission=BlobSasPermissions(read=True),
                cache_control=cache_control,
                expiry=expiry_time
            )

            return f"https://data.reilabs.ai/{container_name}/{urllib.parse.quote(file_name)}?{sas_blob}"
        except Exception as e:
            logging.error(f"Failed to generate shareable link: {str(e)}")
            raise

    def upload_file(self, 
                   container_name: str, 
                   file_name: str, 
                   file_data: Union[str, bytes, os.PathLike, BytesIO]) -> str:
        """
        Upload a file to Azure Blob Storage.
        
        Args:
            container_name: Name of the container
            file_name: Name to give the file in blob storage
            file_data: The file data to upload
            
        Returns:
            str: Shareable URL for the uploaded file
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            
            if isinstance(file_data, (str, bytes, os.PathLike)):
                with open(file_data, "rb") as data:
                    container_client.upload_blob(file_name, data, overwrite=True)
            elif isinstance(file_data, BytesIO):
                container_client.upload_blob(file_name, file_data, overwrite=True)
            else:
                raise TypeError("file_data must be a file path or a BytesIO object")

            # Generate SAS token
            expiry_time = datetime.now(pytz.utc) + timedelta(days=9)
            sas_blob = generate_blob_sas(
                account_name=self.config['ACCOUNT_NAME'],
                container_name=container_name,
                blob_name=file_name,
                account_key=self.config['ACCOUNT_KEY'],
                permission=BlobSasPermissions(read=True),
                expiry=expiry_time
            )

            return f"https://data.reilabs.ai/{container_name}/{urllib.parse.quote(file_name)}?{sas_blob}"
        
        except Exception as e:
            logging.error(f"Failed to upload file {file_name}: {str(e)}")
            raise

    def upload_dataframe(self, 
                        container_name: str,
                        file_name: str, 
                        df: pd.DataFrame,
                        sheet_name: str = 'Leads') -> str:
        """
        Upload a pandas DataFrame as an Excel file to Azure Blob Storage.
        
        Args:
            container_name: Name of the container
            file_name: Name to give the file in blob storage
            df: The DataFrame to upload
            sheet_name: Name of the Excel sheet
            
        Returns:
            str: Shareable URL for the uploaded file
        """
        try:
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            excel_buffer.seek(0)

            return self.upload_file(container_name, file_name, excel_buffer)
        
        except Exception as e:
            logging.error(f"Failed to upload DataFrame as Excel: {str(e)}")
            raise

    @staticmethod
    def get_dataframe_preview(df: pd.DataFrame, rows: int = 10) -> str:
        """
        Get a string preview of a DataFrame.
        
        Args:
            df: The DataFrame to preview
            rows: Number of rows to preview
            
        Returns:
            str: String representation of the DataFrame preview
        """
        try:
            preview_df = df.head(rows)
            return preview_df.to_string(index=False)
        except Exception as e:
            logging.error(f"Failed to generate DataFrame preview: {str(e)}")
            raise