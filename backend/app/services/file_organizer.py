"""File organization service for moving completed downloads."""
import os
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from app.config import settings
from app.models import ContentType, Language


class FileOrganizer:
    """Organize downloaded files into proper directory structure."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for filesystem.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # Replace multiple spaces with single
        filename = re.sub(r'\s+', ' ', filename)
        return filename.strip()
        
    @staticmethod
    def parse_episode_info(filename: str, url: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse season and episode number from filename or URL.
        
        Args:
            filename: File name
            url: Original URL
            
        Returns:
            Tuple of (season, episode) or (None, None)
        """
        # Try to extract from filename first
        # Match patterns like S02E05, S2E5, etc.
        match = re.search(r'[Ss](\d+)[Ee](\d+)', filename)
        if match:
            return int(match.group(1)), int(match.group(2))
            
        # Try Arabic URL patterns
        season_match = re.search(r'الموسم-(?:الاول|الثاني|الثالث|الرابع|الخامس|(\d+))', url)
        episode_match = re.search(r'الحلقة-(\d+)', url)
        
        if episode_match:
            season = 1
            if season_match:
                arabic_nums = {
                    'الاول': 1, 'الثاني': 2, 'الثالث': 3,
                    'الرابع': 4, 'الخامس': 5
                }
                for ar, num in arabic_nums.items():
                    if ar in url:
                        season = num
                        break
                if season_match.group(1):
                    season = int(season_match.group(1))
                    
            return season, int(episode_match.group(1))
            
        return None, None
        
    def organize_series(
        self,
        source_path: str,
        series_title: str,
        season: int,
        episode: int,
        language: Language,
        original_url: str = ""
    ) -> Optional[str]:
        """Organize series episode file.
        
        Args:
            source_path: Current file path
            series_title: Series title
            season: Season number
            episode: Episode number
            language: Content language
            original_url: Original ArabSeed URL (for parsing)
            
        Returns:
            New file path or None if failed
        """
        try:
            # Determine base directory
            base_dir = settings.english_series_dir if language == Language.ENGLISH else settings.arabic_series_dir
            
            # Sanitize series title
            safe_title = self.sanitize_filename(series_title)
            
            # Create directory structure
            series_dir = Path(base_dir) / safe_title
            season_dir = series_dir / f"Season {season:02d}"
            
            # Ensure base directory exists first
            if not self.ensure_directory_exists(base_dir):
                print(f"Failed to create or validate base directory: {base_dir}")
                return None
            
            # Ensure series directory exists
            if not self.ensure_directory_exists(str(series_dir)):
                print(f"Failed to create or validate series directory: {series_dir}")
                return None
            
            # Ensure season directory exists
            if not self.ensure_directory_exists(str(season_dir)):
                print(f"Failed to create or validate season directory: {season_dir}")
                return None
            
            # Get file extension
            ext = Path(source_path).suffix or '.mp4'
            
            # Create new filename
            new_filename = f"{safe_title} - S{season:02d}E{episode:02d}{ext}"
            new_path = season_dir / new_filename
            
            # Check if file already exists
            if new_path.exists():
                print(f"File already exists, skipping: {new_path}")
                return str(new_path)
            
            # Validate source file exists and is readable
            source_file = Path(source_path)
            if not source_file.exists():
                print(f"Source file does not exist: {source_path}")
                return None
            
            if not source_file.is_file():
                print(f"Source path is not a file: {source_path}")
                return None
            
            # Move file with atomic operation
            print(f"Moving file from {source_path} to {new_path}")
            shutil.move(source_path, str(new_path))
            
            # Verify file was moved successfully
            if new_path.exists() and new_path.stat().st_size > 0:
                print(f"Successfully organized series file: {new_path}")
                return str(new_path)
            else:
                print(f"File move failed or file is empty: {new_path}")
                return None
                
        except Exception as e:
            print(f"Error organizing series file: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def organize_movie(
        self,
        source_path: str,
        movie_title: str,
        language: Language,
        year: Optional[int] = None
    ) -> Optional[str]:
        """Organize movie file.
        
        Args:
            source_path: Current file path
            movie_title: Movie title
            language: Content language
            year: Release year (optional)
            
        Returns:
            New file path or None if failed
        """
        try:
            # Determine base directory based on language
            base_dir = settings.english_movies_dir if language == Language.ENGLISH else settings.arabic_movies_dir
            
            # Sanitize title
            safe_title = self.sanitize_filename(movie_title)
            
            # Get file extension
            ext = Path(source_path).suffix or '.mp4'
            
            # Create filename with year if available
            if year:
                new_filename = f"{safe_title} ({year}){ext}"
            else:
                new_filename = f"{safe_title}{ext}"
                
            # Create target directory
            target_dir = Path(base_dir)
            print(f"Creating movie directory: {target_dir}")
            
            # Ensure movie directory exists and is writable
            if not self.ensure_directory_exists(str(target_dir)):
                print(f"Failed to create or validate movie directory: {target_dir}")
                return None
            
            new_path = target_dir / new_filename
            
            # Check if file already exists
            if new_path.exists():
                print(f"Movie file already exists, skipping: {new_path}")
                return str(new_path)
            
            # Validate source file exists and is readable
            source_file = Path(source_path)
            if not source_file.exists():
                print(f"Source movie file does not exist: {source_path}")
                return None
            
            if not source_file.is_file():
                print(f"Source movie path is not a file: {source_path}")
                return None
            
            # Move file with atomic operation
            print(f"Moving movie file from {source_path} to {new_path}")
            shutil.move(source_path, str(new_path))
            
            # Verify file was moved successfully
            if new_path.exists() and new_path.stat().st_size > 0:
                print(f"Successfully organized movie file: {new_path}")
                return str(new_path)
            else:
                print(f"Movie file move failed or file is empty: {new_path}")
                return None
                
        except Exception as e:
            print(f"Error organizing movie file: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def verify_download_complete(self, file_path: str) -> bool:
        """Verify that download file exists and is complete.
        
        Args:
            file_path: Path to downloaded file
            
        Returns:
            True if file exists and appears complete
        """
        path = Path(file_path)
        
        # Check if exists
        if not path.exists():
            return False
            
        # Check if not empty
        if path.stat().st_size == 0:
            return False
            
        # Check for partial download extensions
        if path.suffix in ['.part', '.crdownload', '.tmp']:
            return False
            
        return True

    def validate_video_file(self, file_path: str) -> Dict[str, Any]:
        """Validate a video file for completeness and integrity.
        
        Args:
            file_path: Path to video file
            
        Returns:
            Dictionary with validation results
        """
        path = Path(file_path)
        result = {
            "valid": False,
            "file_path": str(path),
            "exists": False,
            "size": 0,
            "readable": False,
            "video_info": None,
            "errors": []
        }
        
        try:
            # Check if file exists
            if not path.exists():
                result["errors"].append("File does not exist")
                return result
            result["exists"] = True
            
            # Check file size
            file_size = path.stat().st_size
            result["size"] = file_size
            
            if file_size == 0:
                result["errors"].append("File is empty")
                return result
            
            # Check if file is readable
            try:
                with open(path, 'rb') as f:
                    # Try to read first few bytes
                    header = f.read(1024)
                    if not header:
                        result["errors"].append("File is not readable")
                        return result
                result["readable"] = True
            except Exception as e:
                result["errors"].append(f"Cannot read file: {str(e)}")
                return result
            
            # Basic video file validation
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']
            if path.suffix.lower() not in video_extensions:
                result["errors"].append(f"Not a recognized video format: {path.suffix}")
                return result
            
            # Check for common video file signatures
            video_signatures = {
                b'\x00\x00\x00\x18ftypmp42': 'MP4',
                b'\x00\x00\x00\x20ftypmp42': 'MP4',
                b'\x1a\x45\xdf\xa3': 'MKV',
                b'RIFF': 'AVI',
                b'\x00\x00\x00\x14ftypqt': 'MOV',
            }
            
            with open(path, 'rb') as f:
                header = f.read(32)
                file_type = None
                for sig, file_type in video_signatures.items():
                    if header.startswith(sig):
                        break
                
                if file_type:
                    result["video_info"] = {"format": file_type}
                else:
                    # Still consider it valid if it's a video extension and readable
                    result["video_info"] = {"format": "Unknown"}
            
            # If we get here, file is valid
            result["valid"] = True
            
        except Exception as e:
            result["errors"].append(f"Validation error: {str(e)}")
        
        return result

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get comprehensive file information.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        path = Path(file_path)
        info = {
            "path": str(path),
            "name": path.name,
            "size": 0,
            "modified": None,
            "extension": path.suffix,
            "exists": False
        }
        
        try:
            if path.exists():
                stat = path.stat()
                info.update({
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "exists": True
                })
        except Exception as e:
            info["error"] = str(e)
        
        return info

    def ensure_directory_exists(self, directory_path: str) -> bool:
        """Ensure directory exists and is writable.
        
        Args:
            directory_path: Path to directory
            
        Returns:
            True if directory exists and is writable
        """
        try:
            path = Path(directory_path)
            
            # Create directory if it doesn't exist
            if not path.exists():
                print(f"Creating directory: {path}")
                path.mkdir(parents=True, exist_ok=True)
            
            # Verify directory exists
            if not path.exists():
                print(f"Failed to create directory: {path}")
                return False
            
            # Check if it's actually a directory
            if not path.is_dir():
                print(f"Path exists but is not a directory: {path}")
                return False
            
            # Test if directory is writable
            test_file = path / ".test_write"
            try:
                test_file.touch()
                test_file.unlink()
                print(f"Directory is writable: {path}")
                return True
            except Exception as e:
                print(f"Directory is not writable: {path}, error: {e}")
                return False
                
        except Exception as e:
            print(f"Error ensuring directory exists: {path}, error: {e}")
            return False

    def validate_media_directories(self) -> Dict[str, Any]:
        """Validate all media directories are properly configured.
        
        Returns:
            Dictionary with validation results for each directory
        """
        results = {
            "overall_valid": True,
            "directories": {},
            "errors": []
        }
        
        directories = [
            ("english_series", settings.english_series_dir),
            ("arabic_series", settings.arabic_series_dir),
            ("english_movies", settings.english_movies_dir),
            ("arabic_movies", settings.arabic_movies_dir)
        ]
        
        for name, path in directories:
            dir_result = {
                "path": path,
                "exists": False,
                "writable": False,
                "valid": False
            }
            
            try:
                if self.ensure_directory_exists(path):
                    dir_result["exists"] = True
                    dir_result["writable"] = True
                    dir_result["valid"] = True
                    print(f"✓ {name} directory is valid: {path}")
                else:
                    results["errors"].append(f"{name} directory validation failed: {path}")
                    results["overall_valid"] = False
                    
            except Exception as e:
                error_msg = f"{name} directory error: {str(e)}"
                results["errors"].append(error_msg)
                results["overall_valid"] = False
                print(f"✗ {error_msg}")
            
            results["directories"][name] = dir_result
        
        return results

