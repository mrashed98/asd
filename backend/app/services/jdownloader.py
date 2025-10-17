"""JDownloader client using My.JDownloader API (myjdapi)."""
import aiohttp
from typing import Optional, List, Dict, Any
import traceback

from app.config import settings

try:
    from myjdapi import Myjdapi
except Exception:  # fallback if not installed yet
    Myjdapi = None  # type: ignore


class JDownloaderClient:
    """Client for JDownloader via My.JDownloader API.

    Uses environment-configured My.JDownloader account to send links to the
    connected JDownloader instance.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.jdownloader_url
        self._api = None
        self._device = None
        self._device_info = None
        self._enabled = Myjdapi is not None and bool(getattr(settings, 'myjd_email', None))

    async def _ensure_login(self):
        if not self._enabled:
            print("[JD] My.JDownloader disabled or not configured. Falling back to local API.")
            return False
        if self._api and self._device and self._device_info:
            return True
        # myjdapi is sync; run in thread if needed, but quick ops are fine here
        try:
            print(f"[JD] Attempting My.JDownloader login: email={settings.myjd_email}, device_pref={getattr(settings,'myjd_device_name', None)}")
            pw_preview = None
            if settings.myjd_password is not None:
                pw = settings.myjd_password
                pw_preview = f"len={len(pw)}, head={pw[:2]}..., tail=...{pw[-2:]}"
            print(f"[JD] Password info: {pw_preview}")

            api = Myjdapi()
            api.connect(settings.myjd_email, settings.myjd_password)
            devices = api.list_devices()
            print(f"[JD] Devices found: {[d.get('name') for d in devices] if devices else devices}")
            if not devices:
                print("[JD] No devices visible in My.JDownloader account.")
                return False

            chosen = None
            preferred = getattr(settings, 'myjd_device_name', None)
            if preferred:
                for d in devices:
                    if d.get('name') == preferred:
                        chosen = d
                        break
            if not chosen:
                chosen = devices[0]
            self._api = api
            self._device_info = chosen
            device_name = chosen.get('name')
            print(f"[JD] Device info: {chosen}")
            print(f"[JD] Attempting to get device by name: {device_name}")
            self._device = api.get_device(device_name)
            print(f"[JD] Using device: {self._device_info.get('name')} ({self._device_info.get('id')})")
            return True
        except Exception as e:
            print("[JD] My.JDownloader login failed:", e)
            traceback.print_exc()
            return False
        
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to JDownloader.
        
        Returns:
            Dictionary with connection status
        """
        # Prefer My.JDownloader if configured
        try:
            print(f"[JD] test_connection: base_url={self.base_url}")
            if await self._ensure_login():
                return {"connected": True, "message": "Connected via My.JDownloader", "device": self._device_info.get('name') if self._device_info else None}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/system/getSystemInfos",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "connected": True,
                            "message": "Successfully connected to JDownloader",
                            "version": data.get("javaVersion", "Unknown")
                        }
                    else:
                        return {
                            "connected": False,
                            "message": f"JDownloader returned status {response.status}"
                        }
        except Exception as e:
            print("[JD] test_connection error:", e)
            traceback.print_exc()
            return {
                "connected": False,
                "message": f"Failed to connect: {str(e)}"
            }
            
    async def add_links(
        self,
        urls: List[str],
        destination: str,
        package_name: Optional[str] = None
    ) -> Optional[str]:
        """Add download links to JDownloader.
        
        Args:
            urls: List of URLs to download
            destination: Destination directory path
            package_name: Optional package name
            
        Returns:
            Package ID if successful, None otherwise
        """
        try:
            # Prefer local API to obtain a concrete package ID that we can track later
            payload = {
                "autostart": True,
                "links": "\n".join(urls),
                "packageName": package_name or "ArabSeed Download",
                "destinationFolder": destination,
                "overwritePackagizerRules": False,
                "priority": "DEFAULT",
                "downloadPassword": None,
                "extractPassword": None
            }
            
            print(f"[JD] add_links via local API: url={self.base_url}, pkg={payload['packageName']}, dest={destination}, urls={len(urls)}")
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/linkgrabberv2/addLinks",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Move to downloads
                        if data.get("id"):
                            await self._move_to_downloads(data["id"])
                        return data.get("id")
                    return None
        except Exception as e:
            print(f"[JD] Error adding links: {e}")
            traceback.print_exc()
            return None
            
    async def _move_to_downloads(self, link_ids: List[int]) -> bool:
        """Move links from linkgrabber to downloads.
        
        Args:
            link_ids: List of link IDs
            
        Returns:
            True if successful
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/linkgrabberv2/moveToDownloadlist",
                    json={"linkIds": link_ids, "packageIds": []},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200
        except:
            return False
            
    async def query_links(self, link_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Query download links status.
        
        Args:
            link_ids: Optional list of specific link IDs
            
        Returns:
            List of link information
        """
        try:
            payload = {
                "bytesLoaded": True,
                "bytesTotal": True,
                "enabled": True,
                "eta": True,
                "finished": True,
                "packageUUIDs": [],
                "speed": True,
                "status": True,
                "url": True
            }
            
            if link_ids:
                payload["linkIds"] = link_ids
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/downloadsV2/queryLinks",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return []
        except Exception as e:
            print(f"Error querying links: {e}")
            return []
            
    async def query_packages(self, package_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Query download packages status.
        
        Args:
            package_ids: Optional list of specific package IDs
            
        Returns:
            List of package information
        """
        try:
            payload = {
                "bytesLoaded": True,
                "bytesTotal": True,
                "childCount": True,
                "enabled": True,
                "eta": True,
                "finished": True,
                "hosts": True,
                "saveTo": True,
                "speed": True,
                "status": True
            }
            
            if package_ids:
                payload["packageUUIDs"] = package_ids
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/downloadsV2/queryPackages",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return []
        except Exception as e:
            print(f"Error querying packages: {e}")
            return []
            
    async def get_download_progress(self, link_id: int) -> Optional[float]:
        """Get download progress for a specific link.
        
        Args:
            link_id: Link ID
            
        Returns:
            Progress percentage (0-100) or None
        """
        links = await self.query_links([link_id])
        if links and len(links) > 0:
            link = links[0]
            bytes_total = link.get("bytesTotal", 0)
            bytes_loaded = link.get("bytesLoaded", 0)
            
            if bytes_total > 0:
                return (bytes_loaded / bytes_total) * 100
                
        return None
        
    async def is_download_finished(self, link_id: int) -> bool:
        """Check if download is finished.
        
        Args:
            link_id: Link ID
            
        Returns:
            True if finished
        """
        links = await self.query_links([link_id])
        if links and len(links) > 0:
            return links[0].get("finished", False)
        return False

    async def get_download_status(self, link_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive download status for a specific link.
        
        Args:
            link_id: Link ID
            
        Returns:
            Dictionary with download status information or None
        """
        try:
            if await self._ensure_login():
                # Use MyJDownloader API for detailed status
                links = await self.query_links([link_id])
                if links and len(links) > 0:
                    link = links[0]
                    return {
                        "link_id": link_id,
                        "finished": link.get("finished", False),
                        "enabled": link.get("enabled", True),
                        "status": link.get("status", "Unknown"),
                        "bytes_loaded": link.get("bytesLoaded", 0),
                        "bytes_total": link.get("bytesTotal", 0),
                        "progress": (link.get("bytesLoaded", 0) / link.get("bytesTotal", 1)) * 100 if link.get("bytesTotal", 0) > 0 else 0,
                        "speed": link.get("speed", 0),
                        "eta": link.get("eta", 0),
                        "url": link.get("url", ""),
                        "error": link.get("error", None)
                    }
            return None
        except Exception as e:
            print(f"Error getting download status: {e}")
            return None

    async def get_package_status(self, package_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive package status.
        
        Args:
            package_id: Package ID
            
        Returns:
            Dictionary with package status information or None
        """
        try:
            if await self._ensure_login():
                packages = await self.query_packages([package_id])
                if packages and len(packages) > 0:
                    package = packages[0]
                    return {
                        "package_id": package_id,
                        "finished": package.get("finished", False),
                        "enabled": package.get("enabled", True),
                        "status": package.get("status", "Unknown"),
                        "bytes_loaded": package.get("bytesLoaded", 0),
                        "bytes_total": package.get("bytesTotal", 0),
                        "progress": (package.get("bytesLoaded", 0) / package.get("bytesTotal", 1)) * 100 if package.get("bytesTotal", 0) > 0 else 0,
                        "speed": package.get("speed", 0),
                        "eta": package.get("eta", 0),
                        "save_to": package.get("saveTo", ""),
                        "hosts": package.get("hosts", []),
                        "child_count": package.get("childCount", 0)
                    }
            return None
        except Exception as e:
            print(f"Error getting package status: {e}")
            return None

    async def get_downloaded_files(self, package_id: int) -> List[Dict[str, Any]]:
        """Get list of downloaded files for a package.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of file information dictionaries
        """
        try:
            if await self._ensure_login():
                # Query for package details including file paths
                packages = await self.query_packages([package_id])
                if packages and len(packages) > 0:
                    package = packages[0]
                    save_to = package.get("saveTo", "")
                    
                    # Get links for this package to find individual files
                    links = await self.query_links()
                    package_links = [link for link in links if link.get("packageUUID") == package_id]
                    
                    files = []
                    for link in package_links:
                        if link.get("finished", False):
                            # Construct file path
                            file_name = link.get("name", "")
                            if file_name and save_to:
                                file_path = f"{save_to}/{file_name}"
                                files.append({
                                    "name": file_name,
                                    "path": file_path,
                                    "size": link.get("bytesTotal", 0),
                                    "url": link.get("url", ""),
                                    "finished": link.get("finished", False)
                                })
                    return files
            return []
        except Exception as e:
            print(f"Error getting downloaded files: {e}")
            return []

    async def validate_downloaded_files(self, package_id: int, expected_files: List[str] = None) -> Dict[str, Any]:
        """Validate that downloaded files exist and are complete.
        
        Args:
            package_id: Package ID
            expected_files: Optional list of expected file names
            
        Returns:
            Dictionary with validation results
        """
        try:
            downloaded_files = await self.get_downloaded_files(package_id)
            
            if not downloaded_files:
                return {
                    "valid": False,
                    "message": "No downloaded files found",
                    "files": []
                }
            
            # Check if files exist on disk
            import os
            valid_files = []
            invalid_files = []
            
            for file_info in downloaded_files:
                file_path = file_info["path"]
                if os.path.exists(file_path):
                    # Check file size
                    actual_size = os.path.getsize(file_path)
                    expected_size = file_info["size"]
                    
                    if actual_size == expected_size and actual_size > 0:
                        valid_files.append({
                            "name": file_info["name"],
                            "path": file_path,
                            "size": actual_size,
                            "valid": True
                        })
                    else:
                        invalid_files.append({
                            "name": file_info["name"],
                            "path": file_path,
                            "expected_size": expected_size,
                            "actual_size": actual_size,
                            "valid": False,
                            "reason": "Size mismatch or empty file"
                        })
                else:
                    invalid_files.append({
                        "name": file_info["name"],
                        "path": file_path,
                        "valid": False,
                        "reason": "File not found"
                    })
            
            # Check against expected files if provided
            missing_files = []
            if expected_files:
                downloaded_names = [f["name"] for f in downloaded_files]
                missing_files = [f for f in expected_files if f not in downloaded_names]
            
            return {
                "valid": len(invalid_files) == 0 and len(missing_files) == 0,
                "message": f"Found {len(valid_files)} valid files, {len(invalid_files)} invalid files",
                "valid_files": valid_files,
                "invalid_files": invalid_files,
                "missing_files": missing_files,
                "total_files": len(downloaded_files)
            }
            
        except Exception as e:
            print(f"Error validating downloaded files: {e}")
            return {
                "valid": False,
                "message": f"Validation error: {str(e)}",
                "files": []
            }

    async def get_all_active_downloads(self) -> List[Dict[str, Any]]:
        """Get all active downloads with comprehensive status.
        
        Returns:
            List of download information dictionaries
        """
        try:
            if await self._ensure_login():
                # Get all packages
                packages = await self.query_packages()
                active_downloads = []
                
                for package in packages:
                    if not package.get("finished", False):
                        package_info = await self.get_package_status(package.get("uuid"))
                        if package_info:
                            active_downloads.append(package_info)
                
                return active_downloads
            return []
        except Exception as e:
            print(f"Error getting active downloads: {e}")
            return []

    async def get_download_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get download history with file information.
        
        Args:
            limit: Maximum number of downloads to return
            
        Returns:
            List of completed download information
        """
        try:
            if await self._ensure_login():
                # Get all packages
                packages = await self.query_packages()
                completed_downloads = []
                
                for package in packages:
                    if package.get("finished", False):
                        package_info = await self.get_package_status(package.get("uuid"))
                        if package_info:
                            # Get files for this package
                            files = await self.get_downloaded_files(package.get("uuid"))
                            package_info["files"] = files
                            completed_downloads.append(package_info)
                            
                            if len(completed_downloads) >= limit:
                                break
                
                return completed_downloads
            return []
        except Exception as e:
            print(f"Error getting download history: {e}")
            return []

