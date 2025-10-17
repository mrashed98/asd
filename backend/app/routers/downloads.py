"""Downloads endpoints."""
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Download, Episode, TrackedItem, DownloadStatus
from app.schemas import DownloadResponse
from app.services.jdownloader import JDownloaderClient
from app.scraper.arabseed import ArabSeedScraper
from app.config import settings

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


# Define queue endpoint BEFORE parameterized routes to avoid path conflicts
 


@router.get("", response_model=List[DownloadResponse])
async def list_downloads(
    status: DownloadStatus = None,
    tracked_item_id: int | None = None,
    db: Session = Depends(get_db)
):
    """List all downloads.
    
    Args:
        status: Optional filter by status
        db: Database session
        
    Returns:
        List of downloads
    """
    query = db.query(Download)
    
    if status:
        query = query.filter(Download.status == status)
        
    if tracked_item_id:
        query = query.filter(Download.tracked_item_id == tracked_item_id)
    
    downloads = query.order_by(Download.created_at.desc()).all()
    
    # Enrich with content info
    result = []
    for download in downloads:
        item = db.query(TrackedItem).filter(
            TrackedItem.id == download.tracked_item_id
        ).first()
        
        download_dict = DownloadResponse.model_validate(download).model_dump()
        download_dict['content_title'] = item.title if item else None
        
        if download.episode_id:
            episode = db.query(Episode).filter(
                Episode.id == download.episode_id
            ).first()
            if episode:
                download_dict['episode_info'] = f"S{episode.season:02d}E{episode.episode_number:02d}"
                
        result.append(DownloadResponse(**download_dict))
        
    return result


@router.post("/{episode_id}")
async def trigger_episode_download(
    episode_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger episode download.
    
    Args:
        episode_id: Episode ID
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Download info
    """
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    tracked_item = db.query(TrackedItem).filter(
        TrackedItem.id == episode.tracked_item_id
    ).first()
    
    # Check if already downloading
    existing = db.query(Download).filter(
        Download.episode_id == episode_id,
        Download.status.in_([DownloadStatus.PENDING, DownloadStatus.IN_PROGRESS])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Episode already downloading")
        
    # Get download URL
    async with ArabSeedScraper() as scraper:
        download_url = await scraper.get_download_url(episode.arabseed_url)
        
    if not download_url:
        raise HTTPException(status_code=500, detail="Failed to extract download URL")
        
    # Create download entry
    download = Download(
        tracked_item_id=episode.tracked_item_id,
        episode_id=episode_id,
        download_url=download_url,
        destination_path=settings.download_folder,
        status=DownloadStatus.PENDING
    )
    db.add(download)
    db.commit()
    db.refresh(download)
    
    # Send to JDownloader
    jd_client = JDownloaderClient()
    package_name = f"{tracked_item.title} - S{episode.season:02d}E{episode.episode_number:02d}"
    package_id = await jd_client.add_links(
        [download_url],
        settings.download_folder,
        package_name
    )
    
    if package_id:
        download.jdownloader_package_id = str(package_id)
        download.status = DownloadStatus.IN_PROGRESS
        db.commit()
        
    return {"message": "Download started", "download_id": download.id}


class QueueRequest(BaseModel):
    episode_ids: list[int]


@router.post("/queue")
async def enqueue_download_queue(payload: QueueRequest):
    """Enqueue a list of episode IDs to be processed sequentially by Celery.
    Returns task id for tracking.
    """
    from app.tasks.download_monitor import process_download_queue
    if not payload.episode_ids:
        raise HTTPException(status_code=400, detail="episode_ids is required")
    task = process_download_queue.delay(payload.episode_ids)
    return {"task_id": task.id, "queued": len(payload.episode_ids)}


@router.post("/{download_id}/retry")
async def retry_download(download_id: int, db: Session = Depends(get_db)):
    """Retry failed download.
    
    Args:
        download_id: Download ID
        db: Database session
        
    Returns:
        Updated download
    """
    download = db.query(Download).filter(Download.id == download_id).first()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
        
    if download.status != DownloadStatus.FAILED:
        raise HTTPException(status_code=400, detail="Can only retry failed downloads")
        
    # Reset download status
    download.status = DownloadStatus.PENDING
    download.error_message = None
    download.jdownloader_link_id = None
    download.jdownloader_package_id = None
    
    # Re-send to JDownloader
    jd_client = JDownloaderClient()
    tracked_item = db.query(TrackedItem).filter(
        TrackedItem.id == download.tracked_item_id
    ).first()
    
    package_name = tracked_item.title if tracked_item else "ArabSeed Download"
    if download.episode_id:
        episode = db.query(Episode).filter(Episode.id == download.episode_id).first()
        if episode:
            package_name = f"{package_name} - S{episode.season:02d}E{episode.episode_number:02d}"
            
    package_id = await jd_client.add_links(
        [download.download_url],
        download.destination_path,
        package_name
    )
    
    if package_id:
        download.jdownloader_package_id = str(package_id)
        download.status = DownloadStatus.IN_PROGRESS
        
    db.commit()
    return {"message": "Download retry initiated"}


@router.get("/movie/qualities")
async def get_movie_qualities(arabseed_url: str):
    """Get available quality options for a movie.
    
    Args:
        arabseed_url: ArabSeed movie URL
        
    Returns:
        List of available qualities
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Fetching available qualities from: {arabseed_url}")
        async with ArabSeedScraper() as scraper:
            qualities = await scraper.get_available_qualities(arabseed_url)
        
        if not qualities:
            logger.warning(f"No qualities found for: {arabseed_url}")
            # Return default qualities as fallback
            return {"qualities": ["1080", "720", "480"]}
            
        logger.info(f"Found qualities: {qualities}")
        return {"qualities": qualities}
        
    except Exception as e:
        logger.error(f"Error fetching qualities: {str(e)}", exc_info=True)
        # Return default qualities on error
        return {"qualities": ["1080", "720", "480"]}


@router.post("/movie/url")
async def get_movie_download_url(arabseed_url: str, quality: str = "1080"):
    """Get direct download URL for a movie without tracking it.
    
    Args:
        arabseed_url: ArabSeed movie URL
        quality: Preferred video quality (e.g., '1080', '720', '480')
        
    Returns:
        Direct download URL, JDownloader status, and extraction logs
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Collect logs for frontend display
    logs = []
    
    def sanitize_for_header(text: str) -> str:
        """Remove unicode characters that can't be encoded to latin-1 for HTTP headers."""
        return text.encode('ascii', errors='ignore').decode('ascii')
    
    def log_callback(message: str):
        logs.append(message)
    
    # Get download URL
    try:
        logger.info(f"Attempting to extract download URL from: {arabseed_url} with quality: {quality}p")
        logs.append(f"Starting download URL extraction with {quality}p quality...")
        
        async with ArabSeedScraper() as scraper:
            download_url = await scraper.get_download_url(
                arabseed_url, 
                quality=quality,
                log_callback=log_callback
            )
        
        if not download_url:
            logger.error(f"Failed to extract download URL from: {arabseed_url}")
            logs.append("Failed to extract download URL")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Failed to extract download URL. The scraper could not find a download link on the page.",
                    "logs": logs,
                },
            )
            
        logger.info(f"Successfully extracted download URL: {download_url[:100]}...")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting download URL: {str(e)}", exc_info=True)
        logs.append(f"Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Error extracting download URL: {str(e)}",
                "logs": logs,
            },
        )
    
    # Try to add to JDownloader
    jdownloader_connected = False
    jdownloader_error = None
    
    try:
        logs.append("Attempting to add to JDownloader...")
        
        # Extract movie title from URL for package name
        package_name = "ArabSeed Movie"  # Default fallback
        try:
            # Try to extract title from URL path
            from urllib.parse import unquote
            import re
            
            # Decode URL and extract title from path
            decoded_url = unquote(arabseed_url)
            # Look for patterns like /فيلم-روكي-الغلابة-2025/ or /movie-title/
            title_match = re.search(r'/(?:فيلم-|movie-|مسلسل-|series-)?([^/]+?)(?:-\d{4})?/?$', decoded_url)
            if title_match:
                title = title_match.group(1)
                # Clean up the title
                title = title.replace('-', ' ').replace('_', ' ')
                # Remove common suffixes
                title = re.sub(r'\s+\d{4}$', '', title)
                if title.strip():
                    package_name = f"ArabSeed - {title.strip()}"
        except Exception as e:
            logger.warning(f"Could not extract title from URL: {e}")
        
        jd_client = JDownloaderClient()
        package_id = await jd_client.add_links(
            [download_url],
            settings.download_folder,
            package_name
        )
        if package_id:
            jdownloader_connected = True
            logger.info("Successfully added to JDownloader")
            logs.append("✓ Successfully added to JDownloader")
    except Exception as e:
        jdownloader_error = str(e)
        logger.warning(f"Failed to add to JDownloader: {jdownloader_error}")
        logs.append(f"✗ JDownloader connection failed: {jdownloader_error}")
        
    return {
        "download_url": download_url,
        "jdownloader_connected": jdownloader_connected,
        "jdownloader_error": jdownloader_error,
        "logs": logs
    }


@router.get("/{download_id}/status")
async def get_download_status(download_id: int, db: Session = Depends(get_db)):
    """Get detailed download status from JDownloader.
    
    Args:
        download_id: Download ID
        db: Database session
        
    Returns:
        Detailed download status information
    """
    download = db.query(Download).filter(Download.id == download_id).first()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    
    jd_client = JDownloaderClient()
    status_info = {
        "download_id": download_id,
        "status": download.status,
        "progress": download.progress,
        "error_message": download.error_message,
        "created_at": download.created_at,
        "started_at": download.started_at,
        "completed_at": download.completed_at,
        "jdownloader_status": None,
        "files": []
    }
    
    try:
        # Get detailed status from JDownloader
        if download.jdownloader_package_id:
            package_status = await jd_client.get_package_status(download.jdownloader_package_id)
            if package_status:
                status_info["jdownloader_status"] = package_status
                
                # Get file information
                files = await jd_client.get_downloaded_files(download.jdownloader_package_id)
                status_info["files"] = files
                
        elif download.jdownloader_link_id:
            link_status = await jd_client.get_download_status(int(download.jdownloader_link_id))
            if link_status:
                status_info["jdownloader_status"] = link_status
                
    except Exception as e:
        status_info["jdownloader_error"] = str(e)
    
    return status_info


@router.get("/jdownloader/active")
async def get_active_downloads():
    """Get all active downloads from JDownloader.
    
    Returns:
        List of active downloads with detailed status
    """
    jd_client = JDownloaderClient()
    
    try:
        active_downloads = await jd_client.get_all_active_downloads()
        return {
            "active_downloads": active_downloads,
            "count": len(active_downloads)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active downloads: {str(e)}")


@router.get("/jdownloader/history")
async def get_download_history(limit: int = 50):
    """Get download history from JDownloader.
    
    Args:
        limit: Maximum number of downloads to return
        
    Returns:
        List of completed downloads with file information
    """
    jd_client = JDownloaderClient()
    
    try:
        history = await jd_client.get_download_history(limit)
        return {
            "download_history": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get download history: {str(e)}")


@router.post("/{download_id}/validate")
async def validate_download_files(download_id: int, db: Session = Depends(get_db)):
    """Validate downloaded files for a specific download.
    
    Args:
        download_id: Download ID
        db: Database session
        
    Returns:
        File validation results
    """
    download = db.query(Download).filter(Download.id == download_id).first()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    
    if not download.jdownloader_package_id:
        raise HTTPException(status_code=400, detail="No JDownloader package ID found")
    
    jd_client = JDownloaderClient()
    
    try:
        validation_result = await jd_client.validate_downloaded_files(download.jdownloader_package_id)
        return validation_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate files: {str(e)}")


@router.post("/scan-directory")
async def scan_download_directory():
    """Manually trigger download directory scan.
    
    Returns:
        Scan results
    """
    from app.tasks.download_monitor import scan_download_directory
    
    try:
        result = scan_download_directory.delay()
        return {"message": "Directory scan initiated", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start directory scan: {str(e)}")


@router.get("/tracking/overview")
async def get_download_tracking_overview(db: Session = Depends(get_db)):
    """Get comprehensive download tracking overview.
    
    Returns:
        Overview of download tracking status
    """
    try:
        # Get download statistics
        total_downloads = db.query(Download).count()
        pending_downloads = db.query(Download).filter(Download.status == DownloadStatus.PENDING).count()
        in_progress_downloads = db.query(Download).filter(Download.status == DownloadStatus.IN_PROGRESS).count()
        completed_downloads = db.query(Download).filter(Download.status == DownloadStatus.COMPLETED).count()
        failed_downloads = db.query(Download).filter(Download.status == DownloadStatus.FAILED).count()
        
        # Get JDownloader status
        jd_client = JDownloaderClient()
        jd_active_downloads = await jd_client.get_all_active_downloads()
        jd_history = await jd_client.get_download_history(10)  # Last 10 downloads
        
        # Get directory scan info
        from app.config import settings
        from pathlib import Path
        download_dir = Path(settings.download_folder)
        
        directory_info = {
            "exists": download_dir.exists(),
            "path": str(download_dir),
            "video_files_count": 0
        }
        
        if download_dir.exists():
            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
            video_files = []
            for ext in video_extensions:
                video_files.extend(download_dir.glob(f"**/*{ext}"))
            directory_info["video_files_count"] = len(video_files)
        
        return {
            "database_stats": {
                "total_downloads": total_downloads,
                "pending": pending_downloads,
                "in_progress": in_progress_downloads,
                "completed": completed_downloads,
                "failed": failed_downloads
            },
            "jdownloader_stats": {
                "active_downloads": len(jd_active_downloads),
                "recent_completed": len(jd_history)
            },
            "directory_info": directory_info,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tracking overview: {str(e)}")


@router.get("/tracking/health")
async def get_download_tracking_health():
    """Get download tracking system health status.
    
    Returns:
        Health status of download tracking components
    """
    health_status = {
        "overall": "healthy",
        "components": {},
        "issues": []
    }
    
    try:
        # Test JDownloader connection
        jd_client = JDownloaderClient()
        jd_test = await jd_client.test_connection()
        
        health_status["components"]["jdownloader"] = {
            "status": "healthy" if jd_test.get("connected", False) else "unhealthy",
            "message": jd_test.get("message", "Unknown"),
            "connected": jd_test.get("connected", False)
        }
        
        if not jd_test.get("connected", False):
            health_status["issues"].append("JDownloader connection failed")
            health_status["overall"] = "degraded"
        
        # Test download directory
        from app.config import settings
        from pathlib import Path
        download_dir = Path(settings.download_folder)
        
        health_status["components"]["download_directory"] = {
            "status": "healthy" if download_dir.exists() else "unhealthy",
            "path": str(download_dir),
            "exists": download_dir.exists(),
            "writable": False
        }
        
        if download_dir.exists():
            try:
                # Test if directory is writable
                test_file = download_dir / ".test_write"
                test_file.touch()
                test_file.unlink()
                health_status["components"]["download_directory"]["writable"] = True
            except Exception:
                health_status["components"]["download_directory"]["writable"] = False
                health_status["issues"].append("Download directory is not writable")
                health_status["overall"] = "degraded"
        else:
            health_status["issues"].append("Download directory does not exist")
            health_status["overall"] = "unhealthy"
        
        # Test media directories
        media_dirs = [
            ("english_series", settings.english_series_dir),
            ("arabic_series", settings.arabic_series_dir),
            ("english_movies", settings.english_movies_dir),
            ("arabic_movies", settings.arabic_movies_dir)
        ]
        
        health_status["components"]["media_directories"] = {}
        
        for name, path in media_dirs:
            media_path = Path(path)
            health_status["components"]["media_directories"][name] = {
                "status": "healthy" if media_path.exists() else "warning",
                "path": str(media_path),
                "exists": media_path.exists()
            }
            
            if not media_path.exists():
                health_status["issues"].append(f"Media directory {name} does not exist")
                if health_status["overall"] == "healthy":
                    health_status["overall"] = "degraded"
        
    except Exception as e:
        health_status["overall"] = "unhealthy"
        health_status["issues"].append(f"Health check error: {str(e)}")
    
    return health_status


@router.get("/directories/validate")
async def validate_media_directories():
    """Validate all media directories are properly configured.
    
    Returns:
        Directory validation results
    """
    from app.services.file_organizer import FileOrganizer
    
    try:
        organizer = FileOrganizer()
        validation_result = organizer.validate_media_directories()
        return validation_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate directories: {str(e)}")


@router.post("/directories/create")
async def create_media_directories():
    """Create all media directories if they don't exist.
    
    Returns:
        Directory creation results
    """
    from app.services.file_organizer import FileOrganizer
    
    try:
        organizer = FileOrganizer()
        validation_result = organizer.validate_media_directories()
        
        # If validation passed, directories are created
        if validation_result["overall_valid"]:
            return {
                "message": "All media directories are properly configured",
                "directories": validation_result["directories"]
            }
        else:
            return {
                "message": "Some directories failed validation",
                "directories": validation_result["directories"],
                "errors": validation_result["errors"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create directories: {str(e)}")

