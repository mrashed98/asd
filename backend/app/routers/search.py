"""Search endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import json

from app.scraper.arabseed import ArabSeedScraper
from app.schemas import SearchResponse, SearchResult
from app.models import ContentType, TrackedItem
from app.database import get_db
from app.cache import cache

router = APIRouter(prefix="/api/search", tags=["search"])

# Cache TTL settings
SEARCH_CACHE_TTL = 600  # 10 minutes for search results
SEASONS_CACHE_TTL = 3600  # 1 hour for seasons data

def get_cache_key(query: str, content_type: str = None) -> str:
    """Generate cache key for search query."""
    return f"search:{query.lower().strip()}:{content_type or 'all'}"

def invalidate_cache_for_url(arabseed_url: str):
    """Invalidate cache entries that might contain the given URL."""
    # Invalidate all search results (since we can't easily determine which ones contain this URL)
    # This is acceptable since search cache TTL is only 10 minutes
    deleted = cache.delete_pattern("search:*")
    if deleted > 0:
        print(f"🗑️ Invalidated {deleted} search cache entries for URL update")

    # Also invalidate seasons cache for this specific URL
    import urllib.parse
    from hashlib import md5
    url_hash = md5(arabseed_url.encode()).hexdigest()
    cache.delete(f"seasons:{url_hash}")
    print(f"🗑️ Invalidated seasons cache for: {arabseed_url}")


@router.get("", response_model=SearchResponse)
async def search_content(query: str, content_type: str = None, db: Session = Depends(get_db)):
    """Search ArabSeed for content with tracking status and seasons caching.
    
    Args:
        query: Search query string
        content_type: Filter by content type ('series' or 'movies')
        db: Database session
        
    Returns:
        Search results with tracking status and seasons data
    """
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    # Check Redis cache first
    cache_key = get_cache_key(query, content_type)
    cached_result = cache.get(cache_key)

    if cached_result:
        print(f"📦 [Cache HIT] Returning cached search results for: {query} ({content_type})")
        return SearchResponse(**cached_result)

    print(f"🔍 [Cache MISS] Making new search request for: {query} ({content_type})")
        
    async with ArabSeedScraper() as scraper:
        if content_type == "series":
            # Use series-specific search URL
            results = await scraper.search(query, content_type="series")
        elif content_type == "movies":
            # Use movies-specific search URL  
            results = await scraper.search(query, content_type="movies")
        else:
            # Default search (no type filter)
            results = await scraper.search(query)
        
        # Enhance results with tracking status and seasons data
        enhanced_results = []
        for result in results:
            # Check if this item is already tracked
            # Try both URL-encoded and non-URL-encoded versions for comparison
            import urllib.parse
            decoded_url = urllib.parse.unquote(result.arabseed_url)
            encoded_url = urllib.parse.quote(result.arabseed_url, safe=':/?#[]@!$&\'()*+,;=')
            
            tracked_item = db.query(TrackedItem).filter(
                (TrackedItem.arabseed_url == result.arabseed_url) |
                (TrackedItem.arabseed_url == decoded_url) |
                (TrackedItem.arabseed_url == encoded_url)
            ).first()
            
            enhanced_result = SearchResult(
                title=result.title,
                type=result.type,
                arabseed_url=result.arabseed_url,
                poster_url=result.poster_url,
                badge=result.badge,
                is_tracked=tracked_item is not None,
                tracking_id=tracked_item.id if tracked_item else None,
                tracked_seasons=[],
                available_seasons=[]
            )
            
            # For series, get seasons data and tracking status
            if result.type == ContentType.SERIES:
                try:
                    # Get available seasons
                    seasons_data = await scraper.get_seasons(result.arabseed_url)
                    available_seasons = [s.get('number', s) if isinstance(s, dict) else s for s in seasons_data]
                    enhanced_result.available_seasons = available_seasons
                    
                    # Get tracked seasons if item is tracked
                    if tracked_item and tracked_item.extra_metadata:
                        tracked_seasons = tracked_item.extra_metadata.get('seasons', [])
                        enhanced_result.tracked_seasons = tracked_seasons
                        
                except Exception as e:
                    # If seasons extraction fails, continue without seasons data
                    print(f"Failed to get seasons for {result.title}: {e}")
                    enhanced_result.available_seasons = []
            
            enhanced_results.append(enhanced_result)
        
        # Cache the results in Redis
        response_data = {
            "results": [result.dict() for result in enhanced_results],
            "query": query
        }
        cache.set(cache_key, response_data, ttl=SEARCH_CACHE_TTL)
        print(f"💾 Cached search results for: {query} ({content_type}) - TTL: {SEARCH_CACHE_TTL}s")

    return SearchResponse(results=enhanced_results, query=query)


@router.post("/track")
async def update_tracking_status(
    arabseed_url: str,
    seasons: str = None,  # Accept as string and parse
    action: str = "track",  # "track" or "untrack"
    title: str = None,  # Title from search results
    db: Session = Depends(get_db)
):
    """Update tracking status for a series or movie.
    
    Args:
        arabseed_url: URL of the content to track/untrack
        seasons: List of seasons to track (for series only)
        action: "track" or "untrack"
        db: Database session
        
    Returns:
        Updated tracking status
    """
    if action not in ["track", "untrack"]:
        raise HTTPException(status_code=400, detail="Action must be 'track' or 'untrack'")
    
    # Parse seasons string to list of integers
    seasons_list = []
    if seasons:
        try:
            seasons_list = [int(s.strip()) for s in seasons.split(',') if s.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid seasons format. Use comma-separated integers.")
    
    # Check if item is already tracked
    tracked_item = db.query(TrackedItem).filter(
        TrackedItem.arabseed_url == arabseed_url
    ).first()
    
    if action == "track":
        if tracked_item:
            # Update existing tracking with new seasons
            if seasons_list:
                if tracked_item.extra_metadata is None:
                    tracked_item.extra_metadata = {}
                tracked_item.extra_metadata['seasons'] = seasons_list
                db.commit()
            # Invalidate cache for this URL
            invalidate_cache_for_url(arabseed_url)
            
            return {
                "message": "Tracking updated",
                "tracking_id": tracked_item.id,
                "tracked_seasons": seasons_list
            }
        else:
            # Create new tracking entry
            # We need to get the correct content type from search results
            async with ArabSeedScraper() as scraper:
                # Search for the item to get the correct content type
                try:
                    # Extract a basic search query from the title or URL
                    search_query = title or "unknown"
                    search_results = await scraper.search(search_query)
                    
                    # Find the matching result by URL
                    matching_result = None
                    for result in search_results:
                        if result.arabseed_url == arabseed_url:
                            matching_result = result
                            break
                    
                    # Determine content type from search result or fallback logic
                    if matching_result:
                        content_type = matching_result.type
                    else:
                        # Fallback: determine from URL structure
                        if "/مسلسل-" in arabseed_url or "/selary/" in arabseed_url:
                            content_type = ContentType.SERIES
                        else:
                            content_type = ContentType.MOVIE
                    
                    new_item = TrackedItem(
                        title=title or "Unknown",  # Use provided title or fallback
                        type=content_type,
                        language="en",  # Default language
                        arabseed_url=arabseed_url,
                        extra_metadata={"seasons": seasons_list} if seasons_list else None
                    )
                    db.add(new_item)
                    db.commit()
                    db.refresh(new_item)
                    # Kick off background scan for existing media
                    try:
                        from app.tasks.download_monitor import scan_existing_media_for_tracked_item
                        scan_existing_media_for_tracked_item.delay(new_item.id)
                    except Exception:
                        pass
                    
                    # Invalidate cache for this URL
                    invalidate_cache_for_url(arabseed_url)
                    
                    return {
                        "message": "Tracking started",
                        "tracking_id": new_item.id,
                        "tracked_seasons": seasons_list
                    }
                    
                except Exception as e:
                    # Fallback if search fails
                    print(f"Failed to determine content type from search: {e}")
                    content_type = ContentType.SERIES if seasons_list else ContentType.MOVIE
                    
                    new_item = TrackedItem(
                        title=title or "Unknown",
                        type=content_type,
                        language="en",
                        arabseed_url=arabseed_url,
                        extra_metadata={"seasons": seasons_list} if seasons_list else None
                    )
                    db.add(new_item)
                    db.commit()
                    db.refresh(new_item)
                    # Kick off background scan for existing media
                    try:
                        from app.tasks.download_monitor import scan_existing_media_for_tracked_item
                        scan_existing_media_for_tracked_item.delay(new_item.id)
                    except Exception:
                        pass
                    
                    # Invalidate cache for this URL
                    invalidate_cache_for_url(arabseed_url)
                    
                    return {
                        "message": "Tracking started",
                        "tracking_id": new_item.id,
                        "tracked_seasons": seasons_list
                    }
    
    elif action == "untrack":
        if tracked_item:
            db.delete(tracked_item)
            db.commit()
            # Invalidate cache for this URL
            invalidate_cache_for_url(arabseed_url)
            return {"message": "Tracking stopped", "tracking_id": tracked_item.id}
        else:
            return {"message": "Item was not being tracked"}

