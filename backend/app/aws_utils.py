import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import tempfile
import subprocess
from app.core.logging_config import get_logger

logger = get_logger("aws_utils")

class AWSManager:
    """
    AWS S3 manager for video storage with public access.
    
    Features:
    - Upload videos to S3 bucket with proper content types
    - Generate public S3 URLs for direct video streaming
    - Validate video duration using ffprobe
    - Support multiple video formats (MP4, MOV, AVI, MKV, WebM)
    """
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-west-1')
        # Use regional endpoint to ensure URLs include region
        self.s3_client = boto3.client(
            's3',
            region_name=self.region,
            endpoint_url=f'https://s3.{self.region}.amazonaws.com',
            config=boto3.session.Config(
                s3={'addressing_style': 'virtual'},
                signature_version='s3v4'
            )
        )
        self.bucket_name = os.getenv('AWS_S3_BUCKET')
        logger.info(f"AWS S3 client initialized", extra={"region": self.region, "bucket": self.bucket_name})
        
    def upload_video(self, file_content: bytes, filename: str) -> bool:
        """Upload video to S3 bucket with proper content type and metadata"""
        try:
            # Determine content type based on file extension
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.mp4': 'video/mp4',
                '.mov': 'video/quicktime',
                '.avi': 'video/x-msvideo',
                '.mkv': 'video/x-matroska',
                '.webm': 'video/webm',
            }
            content_type = content_type_map.get(ext, 'video/mp4')  # Default to mp4
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"videos/{filename}",
                Body=file_content,
                ContentType=content_type,
                CacheControl='max-age=3600',
                # Add metadata for better video streaming
                Metadata={
                    'original-filename': filename,
                    'upload-timestamp': str(int(__import__('time').time()))
                }
            )
            logger.info(f"Successfully uploaded to S3", extra={"video_filename": filename, "content_type": content_type})
            return True
        except ClientError as e:
            logger.error(f"Error uploading to S3", extra={"video_filename": filename}, exc_info=True)
            return False
    
    def get_video_url(self, filename: str) -> str:
        """Get public S3 URL for direct video streaming"""
        public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/videos/{filename}"
        logger.debug(f"Generated public S3 URL", extra={"video_filename": filename, "url": public_url})
        return public_url
    
    def video_exists(self, filename: str) -> bool:
        """Check if video exists in S3"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=f"videos/{filename}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking video existence", extra={"video_filename": filename}, exc_info=True)
                return False
    
    def delete_video(self, filename: str) -> bool:
        """Delete video from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=f"videos/{filename}"
            )
            logger.info(f"Successfully deleted from S3", extra={"video_filename": filename})
            return True
        except ClientError as e:
            logger.error(f"Error deleting from S3", extra={"video_filename": filename}, exc_info=True)
            return False
    
    def validate_video_duration_server(self, file_path: str) -> Optional[float]:
        """Server-side video duration validation using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            import json
            data = json.loads(result.stdout)
            
            # Get duration from format or video stream
            duration = None
            if 'format' in data and 'duration' in data['format']:
                duration = float(data['format']['duration'])
            else:
                # Look for video stream duration
                for stream in data.get('streams', []):
                    if stream.get('codec_type') == 'video' and 'duration' in stream:
                        duration = float(stream['duration'])
                        break
            
            return duration
        except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error getting video duration", extra={"video_path": video_path}, exc_info=True)
            return None
    
    def generate_presigned_upload_url(self, filename: str, content_type: str = 'video/mp4', expires_in: int = 3600) -> Optional[dict]:
        """Generate a presigned URL for uploading files directly to S3"""
        try:
            key = f"videos/{filename}"
            
            presigned_data = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=key,
                Fields={
                    'Content-Type': content_type
                },
                Conditions=[
                    {'Content-Type': content_type},
                    ['content-length-range', 1, 500 * 1024 * 1024]  # 1 byte to 500MB
                    # Removed cache-control restrictions to be more permissive
                ],
                ExpiresIn=expires_in
            )
            
            return {
                'url': presigned_data['url'],
                'fields': presigned_data['fields'],
                'filename': filename,
                'key': key
            }
        except ClientError as e:
            logger.error(f"Error generating presigned URL", extra={"video_filename": filename}, exc_info=True)
            return None

# Global AWS manager instance - only initialized if S3 bucket is configured
aws_manager = AWSManager() if os.getenv('AWS_S3_BUCKET') else None