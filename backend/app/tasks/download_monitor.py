"""Download monitor task."""
import asyncio
from pathlib import Path
from datetime import datetime

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Download, Episode, TrackedItem, DownloadStatus
from app.scraper.arabseed import ArabSeedScraper
from app.config import settings
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

                    # Get detailed package status (package_id is UUID string, not int)
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


@celery_app.task(name="app.tasks.download_monitor.process_download_queue")
def process_download_queue(episode_ids: list[int]):
    """Process a queue of episode IDs sequentially, creating downloads and sending to JDownloader.
    Continues on individual failures.
    """
    db = SessionLocal()
    created = 0
    try:
        for episode_id in episode_ids:
            try:
                episode = db.query(Episode).filter(Episode.id == episode_id).first()
                if not episode:
                    continue
                # Skip if already downloaded
                if episode.downloaded:
                    continue
                # Skip if already pending/in-progress
                existing = db.query(Download).filter(
                    Download.episode_id == episode_id,
                    Download.status.in_([DownloadStatus.PENDING, DownloadStatus.IN_PROGRESS])
                ).first()
                if existing:
                    continue

                tracked_item = db.query(TrackedItem).filter(TrackedItem.id == episode.tracked_item_id).first()
                if not tracked_item:
                    continue

                # Extract URL
                download_url = None
                try:
                    # Use scraper in a small async loop
                    async def _extract(url: str):
                        async with ArabSeedScraper() as scraper:
                            return await scraper.get_download_url(url)
                    download_url = asyncio.run(_extract(episode.arabseed_url))
                except Exception:
                    download_url = None
                if not download_url:
                    continue

                download = Download(
                    tracked_item_id=episode.tracked_item_id,
                    episode_id=episode_id,
                    download_url=download_url,
                    destination_path=settings.download_folder,
                    status=DownloadStatus.PENDING,
                )
                db.add(download)
                db.commit()
                db.refresh(download)

                # Send to JDownloader
                jd_client = JDownloaderClient()
                package_name = f"{tracked_item.title} - S{episode.season:02d}E{episode.episode_number:02d}"
                package_id = asyncio.run(jd_client.add_links([
                    download_url
                ], settings.download_folder, package_name))

                if package_id:
                    download.jdownloader_package_id = str(package_id)
                    download.status = DownloadStatus.IN_PROGRESS
                    db.commit()
                    created += 1
            except Exception:
                # Continue with next episode on any failure
                db.rollback()
                continue
        return {"queued": len(episode_ids), "started": created}
    finally:
        db.close()


@celery_app.task(name="app.tasks.download_monitor.scan_existing_media_for_tracked_item")
def scan_existing_media_for_tracked_item(tracked_item_id: int):
    """Scan media and downloads directories for files matching a tracked item.
    For series, mark episodes as downloaded when matching SxxExx patterns.
    For movies, organize any matching file into the movies directory.
    """
    db = SessionLocal()
    try:
        from app.models import TrackedItem, Episode, ContentType
        from app.config import settings
        import re

        item = db.query(TrackedItem).filter(TrackedItem.id == tracked_item_id).first()
        if not item:
            return {"scanned": False, "reason": "tracked item not found"}

        video_exts = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v")
        title_norm = re.sub(r"\s+", " ", FileOrganizer.sanitize_filename(item.title)).strip().lower()

        organizer = FileOrganizer()

        found = 0

        # 1) Scan downloads recursively for matching files and organize
        downloads_root = Path(settings.download_folder)
        if downloads_root.exists():
            for p in downloads_root.rglob("*"):
                if p.is_file() and p.suffix.lower() in video_exts:
                    name_norm = p.stem.replace("-", " ").replace("_", " ").lower()
                    if title_norm and title_norm in name_norm:
                        if item.type.name == "SERIES":
                            # Try to extract SxxExx
                            season, episode_num = organizer.parse_episode_info(p.name, "")
                            if season and episode_num:
                                new_path = organizer.organize_series(str(p), item.title, season, episode_num, item.language, item.arabseed_url)
                                if new_path:
                                    ep = db.query(Episode).filter(Episode.tracked_item_id == item.id, Episode.season == season, Episode.episode_number == episode_num).first()
                                    if ep:
                                        ep.file_path = new_path
                                        ep.downloaded = True
                                        ep.file_size = Path(new_path).stat().st_size
                                        found += 1
                                        db.commit()
                        else:
                            new_path = organizer.organize_movie(str(p), item.title, item.language)
                            if new_path:
                                found += 1

        # 2) Scan series/movie library for already placed files
        if item.type.name == "SERIES":
            base = Path(settings.english_series_dir if item.language.name == "ENGLISH" else settings.arabic_series_dir)
            candidate = base / FileOrganizer.sanitize_filename(item.title)
            if candidate.exists():
                for f in candidate.rglob("*"):
                    if f.is_file() and f.suffix.lower() in video_exts:
                        season, episode_num = organizer.parse_episode_info(f.name, item.arabseed_url)
                        if season and episode_num:
                            ep = db.query(Episode).filter(Episode.tracked_item_id == item.id, Episode.season == season, Episode.episode_number == episode_num).first()
                            if ep and not ep.downloaded:
                                ep.file_path = str(f)
                                ep.downloaded = True
                                ep.file_size = f.stat().st_size
                                found += 1
                                db.commit()
        else:
            base = Path(settings.english_movies_dir if item.language.name == "ENGLISH" else settings.arabic_movies_dir)
            if base.exists():
                for f in base.glob(f"**/{FileOrganizer.sanitize_filename(item.title)}*"):
                    if f.is_file() and f.suffix.lower() in video_exts:
                        found += 1
                        break

        return {"tracked_item_id": tracked_item_id, "matched_files": found}
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

