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

    @staticmethod
    def _get_attr(obj, *keys, default=None):
        """Get attribute from object or dict, trying multiple key formats.

        Args:
            obj: Object or dict to get attribute from
            *keys: Attribute names to try (camelCase, snake_case, etc.)
            default: Default value if not found

        Returns:
            Attribute value or default
        """
        for key in keys:
            # Try as dict first
            if isinstance(obj, dict):
                if key in obj:
                    return obj[key]
            # Try as object attribute
            else:
                if hasattr(obj, key):
                    return getattr(obj, key)
        return default

    async def _ensure_login(self, force_reconnect=False):
        """Ensure we have a valid My.JDownloader connection.

        Args:
            force_reconnect: Force a fresh connection even if we think we're connected

        Returns:
            True if connected, False otherwise
        """
        if not self._enabled:
            print("[JD] My.JDownloader disabled or not configured. Falling back to local API.")
            return False

        # If we have a connection and not forcing reconnect, assume it's still valid
        # The connection will be tested when actually used, and retry logic will handle failures
        if self._api and self._device and self._device_info and not force_reconnect:
            print("[JD] Reusing existing My.JDownloader connection")
            return True

        # Need to establish a new connection
        try:
            print(f"[JD] Attempting My.JDownloader login: email={settings.myjd_email}, device_pref={getattr(settings,'myjd_device_name', None)}")
            pw_preview = None
            if settings.myjd_password is not None:
                pw = settings.myjd_password
                pw_preview = f"len={len(pw)}, head={pw[:2]}..., tail=...{pw[-2:]}"
            print(f"[JD] Password info: {pw_preview}")

            api = Myjdapi()
            api.connect(settings.myjd_email, settings.myjd_password)
            api.update_devices()  # Refresh device list
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

            # Give the API a moment to establish the connection
            import asyncio
            import time
            time.sleep(0.5)  # Small delay to let connection establish

            print(f"[JD] Successfully connected to device: {self._device_info.get('name')} ({self._device_info.get('id')})")
            return True
        except Exception as e:
            print("[JD] My.JDownloader login failed:", e)
            traceback.print_exc()
            self._api = None
            self._device = None
            self._device_info = None
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
        package_name: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[str]:
        """Add download links to JDownloader with automatic retry on connection failure.

        Args:
            urls: List of URLs to download
            destination: Destination directory path
            package_name: Optional package name
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            Package ID if successful, None otherwise
        """
        pkg_name = package_name or "ArabSeed Download"

        for attempt in range(max_retries):
            try:
                # Ensure we have a valid connection (force reconnect on retry)
                force_reconnect = (attempt > 0)
                if not await self._ensure_login(force_reconnect=force_reconnect):
                    print(f"[JD] My.JDownloader not available (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return None

                print(f"[JD] add_links via My.JDownloader (attempt {attempt + 1}/{max_retries}): pkg={pkg_name}, dest={destination}, urls={len(urls)}")

                # Use the correct parameter format for myjdapi - expects a list with a dictionary
                self._device.linkgrabber.add_links([{
                    "autostart": True,
                    "links": "\n".join(urls),
                    "packageName": pkg_name,
                    "destinationFolder": "/output/",
                    "overwritePackagizerRules": False
                }])

                # Try to find the created package UUID
                packages = self._device.linkgrabber.query_packages()
                for pkg in packages or []:
                    name = pkg.get("name") if isinstance(pkg, dict) else getattr(pkg, "name", None)
                    uuid = pkg.get("uuid") if isinstance(pkg, dict) else getattr(pkg, "uuid", None)
                    if name == pkg_name and uuid is not None:
                        # With autostart=True, JD should move to downloads automatically
                        print(f"[JD] Successfully added links, package UUID: {uuid}")
                        return str(uuid)

                print(f"[JD] Links added but package not found in linkgrabber (may have auto-started)")
                return None

            except Exception as e:
                error_msg = str(e)
                print(f"[JD] Error adding links (attempt {attempt + 1}/{max_retries}): {error_msg}")

                # Check if it's a connection error
                if "No connection established" in error_msg or "Connection" in error_msg:
                    print(f"[JD] Connection error detected, will retry with fresh connection")
                    # Force reconnect on next attempt
                    self._api = None
                    self._device = None
                    self._device_info = None

                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                    else:
                        traceback.print_exc()
                        return None
                else:
                    # Non-connection error, fail immediately
                    traceback.print_exc()
                    return None

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
            
    async def query_links(self, link_ids: Optional[List[int]] = None, max_retries: int = 2) -> List[Dict[str, Any]]:
        """Query download links status with automatic retry on connection failure.

        Args:
            link_ids: Optional list of specific link IDs
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            List of link information
        """
        for attempt in range(max_retries):
            try:
                # Force reconnect on retry
                force_reconnect = (attempt > 0)
                if not await self._ensure_login(force_reconnect=force_reconnect):
                    return []

                # Use My.JDownloader API
                links = self._device.downloads.query_links()
                if link_ids:
                    # Filter by specific link IDs if provided
                    # Handle both dict and object formats
                    links = [link for link in links if self._get_attr(link, 'uuid') in link_ids]

                # Convert to dictionary format (handle both dict and object responses)
                result = []
                for link in links:
                    result.append({
                        "uuid": self._get_attr(link, 'uuid'),
                        "name": self._get_attr(link, 'name'),
                        "url": self._get_attr(link, 'url'),
                        "bytesLoaded": self._get_attr(link, 'bytesLoaded', 'bytes_loaded'),
                        "bytesTotal": self._get_attr(link, 'bytesTotal', 'bytes_total'),
                        "enabled": self._get_attr(link, 'enabled'),
                        "finished": self._get_attr(link, 'finished'),
                        "status": self._get_attr(link, 'status'),
                        "speed": self._get_attr(link, 'speed'),
                        "eta": self._get_attr(link, 'eta'),
                        "packageUUID": self._get_attr(link, 'packageUUID', 'package_uuid')
                    })
                return result

            except Exception as e:
                error_msg = str(e)
                print(f"Error querying links (attempt {attempt + 1}/{max_retries}): {error_msg}")

                # Retry on connection errors
                if ("No connection established" in error_msg or "Connection" in error_msg) and attempt < max_retries - 1:
                    self._api = None
                    self._device = None
                    self._device_info = None
                    import asyncio
                    await asyncio.sleep(1)
                    continue

                return []

        return []
            
    async def query_packages(self, package_ids: Optional[List[int]] = None, max_retries: int = 2) -> List[Dict[str, Any]]:
        """Query download packages status with automatic retry on connection failure.

        Args:
            package_ids: Optional list of specific package IDs
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            List of package information
        """
        for attempt in range(max_retries):
            try:
                # Force reconnect on retry
                force_reconnect = (attempt > 0)
                if not await self._ensure_login(force_reconnect=force_reconnect):
                    return []

                # Use My.JDownloader API
                packages = self._device.downloads.query_packages()
                if package_ids:
                    # Filter by specific package IDs if provided
                    # Handle both dict and object formats
                    packages = [pkg for pkg in packages if self._get_attr(pkg, 'uuid') in package_ids]

                # Convert to dictionary format (handle both dict and object responses)
                result = []
                for pkg in packages:
                    result.append({
                        "uuid": self._get_attr(pkg, 'uuid'),
                        "name": self._get_attr(pkg, 'name'),
                        "bytesLoaded": self._get_attr(pkg, 'bytesLoaded', 'bytes_loaded'),
                        "bytesTotal": self._get_attr(pkg, 'bytesTotal', 'bytes_total'),
                        "childCount": self._get_attr(pkg, 'childCount', 'child_count'),
                        "enabled": self._get_attr(pkg, 'enabled'),
                        "finished": self._get_attr(pkg, 'finished'),
                        "status": self._get_attr(pkg, 'status'),
                        "speed": self._get_attr(pkg, 'speed'),
                        "eta": self._get_attr(pkg, 'eta'),
                        "saveTo": self._get_attr(pkg, 'saveTo', 'save_to'),
                        "hosts": self._get_attr(pkg, 'hosts', default=[])
                    })
                return result

            except Exception as e:
                error_msg = str(e)
                print(f"Error querying packages (attempt {attempt + 1}/{max_retries}): {error_msg}")

                # Retry on connection errors
                if ("No connection established" in error_msg or "Connection" in error_msg) and attempt < max_retries - 1:
                    self._api = None
                    self._device = None
                    self._device_info = None
                    import asyncio
                    await asyncio.sleep(1)
                    continue

                return []

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

    async def get_package_status(self, package_id) -> Optional[Dict[str, Any]]:
        """Get comprehensive package status.

        Args:
            package_id: Package ID (UUID string)

        Returns:
            Dictionary with package status information or None
        """
        try:
            if await self._ensure_login():
                # Query all packages and find the matching one by UUID
                packages = await self.query_packages()

                # Find package with matching UUID
                matching_package = None
                for pkg in packages:
                    if str(pkg.get("uuid")) == str(package_id):
                        matching_package = pkg
                        break

                if matching_package:
                    return {
                        "package_id": package_id,
                        "finished": matching_package.get("finished", False),
                        "enabled": matching_package.get("enabled", True),
                        "status": matching_package.get("status", "Unknown"),
                        "bytes_loaded": matching_package.get("bytesLoaded", 0),
                        "bytes_total": matching_package.get("bytesTotal", 0),
                        "progress": (matching_package.get("bytesLoaded", 0) / matching_package.get("bytesTotal", 1)) * 100 if matching_package.get("bytesTotal", 0) > 0 else 0,
                        "speed": matching_package.get("speed", 0),
                        "eta": matching_package.get("eta", 0),
                        "save_to": matching_package.get("saveTo", ""),
                        "hosts": matching_package.get("hosts", []),
                        "child_count": matching_package.get("childCount", 0)
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

