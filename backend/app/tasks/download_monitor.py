"""Download monitor task."""
import asyncio
from pathlib import Path
from datetime import datetime

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Download, Episode, TrackedItem, DownloadStatus
from app.services.jdownloader import JDownloaderClient
from app.services.file_organizer import FileOrganizer


@celery_app.task(name="app.tasks.download_monitor.sync_downloads")
def sync_downloads():
    """Sync download status with JDownloader and organize completed files."""
    db = SessionLocal()
    
    try:
        # Get active downloads
        downloads = db.query(Download).filter(
            Download.status.in_([DownloadStatus.PENDING, DownloadStatus.IN_PROGRESS])
        ).all()
        
        if not downloads:
            return {"synced": 0}
            
        print(f"Syncing {len(downloads)} active downloads...")
        
        # Query JDownloader for status
        jd_client = JDownloaderClient()
        completed_count = 0
        
        for download in downloads:
            try:
                # Get comprehensive status from JDownloader
                if download.jdownloader_package_id:
                    package_id = download.jdownloader_package_id
                    
                    # Get detailed package status
                    package_status = asyncio.run(jd_client.get_package_status(package_id))
                    
                    if package_status:
                        # Update progress and status
                        download.progress = package_status.get("progress", 0)
                        download.status = DownloadStatus.IN_PROGRESS
                        
                        # Check if finished
                        if package_status.get("finished", False):
                            # Validate downloaded files
                            validation_result = asyncio.run(jd_client.validate_downloaded_files(package_id))
                            
                            if validation_result.get("valid", False):
                                # Find the main downloaded file
                                valid_files = validation_result.get("valid_files", [])
                                if valid_files:
                                    # Use the largest file (usually the main video file)
                                    main_file = max(valid_files, key=lambda x: x.get("size", 0))
                                    file_path = main_file["path"]
                                    
                                    # Additional video file validation
                                    organizer = FileOrganizer()
                                    video_validation = organizer.validate_video_file(file_path)
                                    
                                    if video_validation.get("valid", False):
                                        # Organize file
                                        asyncio.run(_organize_download(db, download, file_path))
                                        completed_count += 1
                                    else:
                                        print(f"Download {download.id} finished but video validation failed: {video_validation.get('errors', [])}")
                                        download.status = DownloadStatus.FAILED
                                        download.error_message = f"Video validation failed: {', '.join(video_validation.get('errors', []))}"
                                else:
                                    print(f"Download {download.id} finished but no valid files found")
                                    download.status = DownloadStatus.FAILED
                                    download.error_message = "No valid files found after download"
                            else:
                                print(f"Download {download.id} finished but file validation failed: {validation_result.get('message', 'Unknown error')}")
                                download.status = DownloadStatus.FAILED
                                download.error_message = f"File validation failed: {validation_result.get('message', 'Unknown error')}"
                        else:
                            # Check for errors
                            if package_status.get("status") == "ERROR":
                                download.status = DownloadStatus.FAILED
                                download.error_message = "Download failed in JDownloader"
                            else:
                                download.status = DownloadStatus.IN_PROGRESS
                                
                elif download.jdownloader_link_id:
                    # Fallback to link-based tracking for older downloads
                    link_id = int(download.jdownloader_link_id)
                    
                    # Get detailed link status
                    link_status = asyncio.run(jd_client.get_download_status(link_id))
                    
                    if link_status:
                        download.progress = link_status.get("progress", 0)
                        
                        if link_status.get("finished", False):
                            # Find downloaded file using old method
                            file_path = _find_downloaded_file(download)
                            
                            if file_path:
                                # Organize file
                                asyncio.run(_organize_download(db, download, file_path))
                                completed_count += 1
                            else:
                                print(f"Download {download.id} finished but file not found")
                                download.status = DownloadStatus.FAILED
                                download.error_message = "File not found after download"
                        else:
                            if link_status.get("status") == "ERROR":
                                download.status = DownloadStatus.FAILED
                                download.error_message = link_status.get("error", "Download failed")
                            else:
                                download.status = DownloadStatus.IN_PROGRESS
                            
            except Exception as e:
                print(f"Error syncing download {download.id}: {e}")
                download.status = DownloadStatus.FAILED
                download.error_message = f"Sync error: {str(e)}"
                continue
                
        db.commit()
        print(f"Completed {completed_count} downloads")
        
        return {"synced": len(downloads), "completed": completed_count}
        
    finally:
        db.close()


@celery_app.task(name="app.tasks.download_monitor.scan_download_directory")
def scan_download_directory():
    """Scan download directory for new files and validate existing downloads."""
    db = SessionLocal()
    
    try:
        from app.config import settings
        from pathlib import Path
        import os
        
        download_dir = Path(settings.download_folder)
        
        if not download_dir.exists():
            print(f"Download directory does not exist: {download_dir}")
            return {"scanned": 0, "found": 0}
            
        print(f"Scanning download directory: {download_dir}")
        
        # Get all video files in download directory
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(download_dir.glob(f"**/*{ext}"))
        
        print(f"Found {len(video_files)} video files in download directory")
        
        # Check which files are not tracked in our database
        tracked_files = set()
        downloads = db.query(Download).filter(
            Download.final_path.isnot(None)
        ).all()
        
        for download in downloads:
            if download.final_path:
                tracked_files.add(Path(download.final_path).resolve())
        
        # Find untracked files
        untracked_files = []
        for video_file in video_files:
            if video_file.resolve() not in tracked_files:
                untracked_files.append(video_file)
        
        print(f"Found {len(untracked_files)} untracked video files")
        
        # For now, just log untracked files
        # In the future, we could implement auto-detection and organization
        for file_path in untracked_files:
            print(f"Untracked file: {file_path}")
        
        return {
            "scanned": len(video_files),
            "tracked": len(tracked_files),
            "untracked": len(untracked_files)
        }
        
    except Exception as e:
        print(f"Error scanning download directory: {e}")
        return {"error": str(e)}
        
    finally:
        db.close()


def _find_downloaded_file(download: Download) -> str:
    """Find the downloaded file in download folder.
    
    Args:
        download: Download record
        
    Returns:
        File path if found, None otherwise
    """
    download_dir = Path(download.destination_path)
    
    if not download_dir.exists():
        return None
        
    # Search for .mp4 files (most recent)
    mp4_files = list(download_dir.glob("*.mp4"))
    
    if not mp4_files:
        return None
        
    # Return most recent file
    mp4_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return str(mp4_files[0])


async def _organize_download(db, download: Download, file_path: str):
    """Organize completed download.
    
    Args:
        db: Database session
        download: Download record
        file_path: Downloaded file path
    """
    organizer = FileOrganizer()
    
    print(f"Starting organization for download {download.id}: {file_path}")
    
    # Verify file is complete
    if not organizer.verify_download_complete(file_path):
        print(f"Download {download.id}: File verification failed")
        download.status = DownloadStatus.FAILED
        download.error_message = "File incomplete or corrupted"
        db.commit()
        return
        
    # Get tracked item
    tracked_item = db.query(TrackedItem).filter(
        TrackedItem.id == download.tracked_item_id
    ).first()
    
    if not tracked_item:
        print(f"Download {download.id}: Tracked item not found")
        download.status = DownloadStatus.FAILED
        download.error_message = "Tracked item not found"
        db.commit()
        return
        
    new_path = None
    
    # Organize based on content type
    if download.episode_id:
        # Series episode
        episode = db.query(Episode).filter(Episode.id == download.episode_id).first()
        
        if episode:
            print(f"Organizing series episode: {tracked_item.title} S{episode.season:02d}E{episode.episode_number:02d}")
            new_path = organizer.organize_series(
                file_path,
                tracked_item.title,
                episode.season,
                episode.episode_number,
                tracked_item.language,
                episode.arabseed_url
            )
            
            if new_path:
                # Mark episode as downloaded
                episode.file_path = new_path
                episode.downloaded = True
                episode.file_size = Path(new_path).stat().st_size
                print(f"Episode {episode.id} marked as downloaded: {new_path}")
            else:
                print(f"Failed to organize series episode for download {download.id}")
        else:
            print(f"Download {download.id}: Episode not found")
            download.status = DownloadStatus.FAILED
            download.error_message = "Episode not found"
            db.commit()
            return
                
    else:
        # Movie
        year = None
        if tracked_item.extra_metadata and 'year' in tracked_item.extra_metadata:
            year = tracked_item.extra_metadata['year']
            
        print(f"Organizing movie: {tracked_item.title}")
        new_path = organizer.organize_movie(
            file_path,
            tracked_item.title,
            tracked_item.language,
            year
        )
        
        if not new_path:
            print(f"Failed to organize movie for download {download.id}")
        
    # Update download status
    if new_path:
        download.final_path = new_path
        download.status = DownloadStatus.COMPLETED
        download.completed_at = datetime.utcnow()
        download.progress = 100.0
        print(f"Download {download.id} completed successfully: {new_path}")
    else:
        download.status = DownloadStatus.FAILED
        download.error_message = "Failed to organize file"
        print(f"Download {download.id} failed: Failed to organize file")
    
    # Commit all changes
    try:
        db.commit()
        print(f"Database updated for download {download.id}")
    except Exception as e:
        print(f"Error committing database changes for download {download.id}: {e}")
        db.rollback()

