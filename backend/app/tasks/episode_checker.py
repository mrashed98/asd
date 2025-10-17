"""Episode checker task."""
import asyncio
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import TrackedItem, Episode, ContentType, Download, DownloadStatus
from app.scraper.arabseed import ArabSeedScraper
from app.services.jdownloader import JDownloaderClient
from app.config import settings


@celery_app.task(name="app.tasks.episode_checker.check_new_episodes")
def check_new_episodes():
    """Check for new episodes for all tracked series."""
    db = SessionLocal()
    
    try:
        # Get all monitored series
        series = db.query(TrackedItem).filter(
            TrackedItem.type == ContentType.SERIES,
            TrackedItem.monitored == True
        ).all()
        
        print(f"Checking {len(series)} series for new episodes...")
        
        for item in series:
            try:
                # Update check time
                item.last_check = datetime.utcnow()
                item.next_check = datetime.utcnow() + timedelta(hours=settings.check_interval_hours)
                
                # Get episodes from ArabSeed (pass full item with metadata)
                episodes_data = asyncio.run(_fetch_episodes(item))
                
                # Check for new episodes
                new_count = 0
                new_episodes = []
                
                for ep_data in episodes_data:
                    # Check if episode exists
                    existing = db.query(Episode).filter(
                        Episode.tracked_item_id == item.id,
                        Episode.arabseed_url == ep_data['url']
                    ).first()
                    
                    if not existing:
                        # Create new episode
                        episode = Episode(
                            tracked_item_id=item.id,
                            season=ep_data['season'],
                            episode_number=ep_data['episode_number'],
                            title=ep_data['title'],
                            arabseed_url=ep_data['url'],
                            monitored=True
                        )
                        db.add(episode)
                        new_episodes.append(episode)
                        new_count += 1
                
                # Save all episodes first
                if new_count > 0:
                    db.commit()
                    print(f"Found {new_count} new episodes for {item.title}")
                    
                    # Then try to download them (separate from database transaction)
                    for episode in new_episodes:
                        try:
                            asyncio.run(_download_episode(db, item, episode))
                        except Exception as e:
                            print(f"Failed to download episode {episode.title}: {e}")
                            # Continue with other episodes even if one fails
                else:
                    db.commit()
                
            except Exception as e:
                print(f"Error checking {item.title}: {e}")
                db.rollback()
                continue
                
    finally:
        db.close()
        
    return {"checked": len(series)}


async def _fetch_episodes(tracked_item: TrackedItem):
    """Fetch episodes from ArabSeed using tracked item metadata."""
    async with ArabSeedScraper() as scraper:
        # Extract seasons from extra_metadata if available
        seasons = None
        if tracked_item.extra_metadata and 'seasons' in tracked_item.extra_metadata:
            seasons = tracked_item.extra_metadata['seasons']

        # Use optimized method with cached metadata
        return await scraper.get_episodes_optimized(
            series_url=tracked_item.arabseed_url,
            series_title=tracked_item.title,
            seasons=seasons
        )


async def _download_episode(db, tracked_item: TrackedItem, episode: Episode):
    """Trigger download for new episode."""
    try:
        # Get download URL
        async with ArabSeedScraper() as scraper:
            download_url = await scraper.get_download_url(episode.arabseed_url)
            
        if not download_url:
            print(f"Failed to get download URL for {episode.title}")
            return
            
        # Create download entry
        download = Download(
            tracked_item_id=tracked_item.id,
            episode_id=episode.id,
            download_url=download_url,
            destination_path=settings.download_folder,
            status=DownloadStatus.PENDING
        )
        db.add(download)
        db.flush()
        
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
            print(f"Started download for {package_name}")
            
    except Exception as e:
        print(f"Error downloading episode: {e}")

