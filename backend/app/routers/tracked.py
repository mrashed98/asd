"""Series seasons helper endpoints and tracked CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import TrackedItem, Episode, ContentType
from app.schemas import (
    TrackedItemCreate,
    TrackedItemUpdate,
    TrackedItemResponse,
    EpisodeResponse,
    EpisodeUpdate,
)
from app.scraper.arabseed import ArabSeedScraper

# Two separate routers exported: series_router and tracked_router
series_router = APIRouter(prefix="/api/series", tags=["series"]) 


@series_router.get("/seasons")
async def get_series_seasons(series_url: str):
    """Return available seasons for a series or episode URL.
    Prefers explicit season links; falls back to deriving from episodes.
    """
    if not series_url:
        raise HTTPException(status_code=400, detail="series_url is required")
    async with ArabSeedScraper() as scraper:
        # Don't resolve the URL first - let get_seasons() work with the original URL
        # as it's designed to extract seasons from episode pages
        seasons = await scraper.get_seasons(series_url)
        if not seasons:
            # If no seasons found, try with the parent series URL as fallback
            parent_url = await scraper.get_series_url(series_url)
            seasons = await scraper.get_seasons(parent_url)
            if not seasons:
                episodes = await scraper.get_episodes(parent_url)
                numbers = sorted({int(e.get("season", 1)) for e in episodes}) if episodes else []
                seasons = [{"number": n, "url": None} for n in numbers]
            series_url = parent_url
    return {"seasons": seasons, "series_url": series_url}

tracked_router = APIRouter(prefix="/api/tracked", tags=["tracked"])


@tracked_router.post("/{tracked_item_id}/scan-existing-media")
async def trigger_scan_existing_media(tracked_item_id: int):
    """Trigger background scan for existing media matching a tracked item."""
    from app.tasks.download_monitor import scan_existing_media_for_tracked_item
    task = scan_existing_media_for_tracked_item.delay(tracked_item_id)
    return {"task_id": task.id, "status": "started"}


@tracked_router.get("", response_model=List[TrackedItemResponse])
async def list_tracked_items(
    type: Optional[ContentType] = None,
    db: Session = Depends(get_db)
):
    """List all tracked items.
    
    Args:
        type: Optional filter by content type
        db: Database session
        
    Returns:
        List of tracked items
    """
    query = db.query(TrackedItem)
    
    if type:
        query = query.filter(TrackedItem.type == type)
        
    items = query.all()
    
    # Add episode counts
    result = []
    for item in items:
        item_dict = TrackedItemResponse.model_validate(item).model_dump()
        if item.type == ContentType.SERIES:
            item_dict['episode_count'] = len(item.episodes)
            item_dict['downloaded_count'] = sum(1 for ep in item.episodes if ep.downloaded)
        result.append(TrackedItemResponse(**item_dict))
        
    return result


@tracked_router.post("", response_model=TrackedItemResponse)
async def create_tracked_item(
    item: TrackedItemCreate,
    db: Session = Depends(get_db)
):
    """Add item to tracking.

    Args:
        item: Item to track
        db: Database session

    Returns:
        Created tracked item
    """
    # For series, use the original URL directly (don't resolve to parent URL)
    # since the parent URL might not exist and episode extraction works with episode URLs
    series_url = item.arabseed_url

    # Check if already tracked (using the original URL)
    existing = db.query(TrackedItem).filter(
        TrackedItem.arabseed_url == series_url
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Item already tracked")

    # Create tracked item with the correct series URL
    item_data = item.model_dump()
    item_data['arabseed_url'] = series_url
    tracked = TrackedItem(**item_data)
    db.add(tracked)
    db.commit()
    db.refresh(tracked)

    # If series, fetch episodes (and honor selected seasons if provided)
    if item.type == ContentType.SERIES:
        try:
            async with ArabSeedScraper() as scraper:
                episodes = await scraper.get_episodes(series_url)
            
            print(f"📺 Fetched {len(episodes)} episodes for series: {tracked.title}")
            
            selected_seasons = []
            try:
                meta = (item.extra_metadata or {})
                ss = meta.get('seasons') if isinstance(meta, dict) else None
                if isinstance(ss, list):
                    selected_seasons = [int(x) for x in ss]
            except Exception:
                selected_seasons = []

            episodes_added = 0
            for ep_data in episodes:
                if selected_seasons and int(ep_data.get('season', 1)) not in selected_seasons:
                    continue
                episode = Episode(
                    tracked_item_id=tracked.id,
                    season=ep_data['season'],
                    episode_number=ep_data['episode_number'],
                    title=ep_data['title'],
                    arabseed_url=ep_data['url'],
                )
                db.add(episode)
                episodes_added += 1

            db.commit()
            print(f"✅ Added {episodes_added} episodes to database for series: {tracked.title}")
            
            # Episodes are now immediately tracked and available for monitoring
            if episodes_added > 0:
                print(f"📺 {episodes_added} episodes are now being tracked for: {tracked.title}")
            
        except Exception as e:
            print(f"❌ Error fetching episodes for series {tracked.title}: {e}")
            # Don't fail the entire request if episode fetching fails
            # The series will still be tracked, just without episodes initially
            pass

    return tracked


@tracked_router.get("/{item_id}", response_model=TrackedItemResponse)
async def get_tracked_item(item_id: int, db: Session = Depends(get_db)):
    """Get tracked item by ID.
    
    Args:
        item_id: Item ID
        db: Database session
        
    Returns:
        Tracked item
    """
    item = db.query(TrackedItem).filter(TrackedItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    return item


@tracked_router.patch("/{item_id}", response_model=TrackedItemResponse)
async def update_tracked_item(
    item_id: int,
    update: TrackedItemUpdate,
    db: Session = Depends(get_db)
):
    """Update tracked item.
    
    Args:
        item_id: Item ID
        update: Update data
        db: Database session
        
    Returns:
        Updated item
    """
    item = db.query(TrackedItem).filter(TrackedItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
        
    db.commit()
    db.refresh(item)
    return item


@tracked_router.delete("/{item_id}")
async def delete_tracked_item(item_id: int, db: Session = Depends(get_db)):
    """Remove item from tracking.
    
    Args:
        item_id: Item ID
        db: Database session
    """
    item = db.query(TrackedItem).filter(TrackedItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    db.delete(item)
    db.commit()
    return {"message": "Item removed from tracking"}


@tracked_router.get("/{item_id}/episodes", response_model=List[EpisodeResponse])
async def get_episodes(item_id: int, db: Session = Depends(get_db)):
    """Get episodes for a series.
    
    Args:
        item_id: Series ID
        db: Database session
        
    Returns:
        List of episodes
    """
    item = db.query(TrackedItem).filter(TrackedItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    if item.type != ContentType.SERIES:
        raise HTTPException(status_code=400, detail="Item is not a series")
        
    episodes = db.query(Episode).filter(
        Episode.tracked_item_id == item_id
    ).order_by(Episode.season, Episode.episode_number).all()
    
    return episodes


@tracked_router.patch("/{item_id}/episodes/{episode_id}", response_model=EpisodeResponse)
async def update_episode(
    item_id: int,
    episode_id: int,
    update: EpisodeUpdate,
    db: Session = Depends(get_db)
):
    """Update episode.
    
    Args:
        item_id: Series ID
        episode_id: Episode ID
        update: Update data
        db: Database session
        
    Returns:
        Updated episode
    """
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.tracked_item_id == item_id
    ).first()
    
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(episode, key, value)
        
    db.commit()
    db.refresh(episode)
    return episode

