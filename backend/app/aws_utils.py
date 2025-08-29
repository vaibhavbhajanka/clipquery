import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import tempfile
import subprocess

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
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.bucket_name = os.getenv('AWS_S3_BUCKET')
        
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
            print(f"Successfully uploaded {filename} to S3 with content type {content_type}")
            return True
        except ClientError as e:
            print(f"Error uploading {filename} to S3: {e}")
            return False
    
    def get_video_url(self, filename: str) -> str:
        """Get public S3 URL for direct video streaming"""
        region = os.getenv('AWS_REGION', 'us-east-1')
        public_url = f"https://{self.bucket_name}.s3.{region}.amazonaws.com/videos/{filename}"
        print(f"Using public S3 URL: {public_url}")
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
                print(f"Error checking video existence: {e}")
                return False
    
    def delete_video(self, filename: str) -> bool:
        """Delete video from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=f"videos/{filename}"
            )
            print(f"Successfully deleted {filename} from S3")
            return True
        except ClientError as e:
            print(f"Error deleting {filename} from S3: {e}")
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
            print(f"Error getting video duration: {e}")
            return None

# Global AWS manager instance - only initialized if all required credentials are available
aws_manager = AWSManager() if all([
    os.getenv('AWS_ACCESS_KEY_ID'),
    os.getenv('AWS_SECRET_ACCESS_KEY'),
    os.getenv('AWS_S3_BUCKET')
]) else None