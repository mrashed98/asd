"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.models import ContentType, Language, DownloadStatus


# Search schemas
class SearchResult(BaseModel):
    """Search result item."""
    title: str
    type: ContentType
    arabseed_url: str
    poster_url: Optional[str] = None
    badge: Optional[str] = None
    # Tracking status fields
    is_tracked: Optional[bool] = False
    tracked_seasons: Optional[List[int]] = None
    available_seasons: Optional[List[int]] = None
    tracking_id: Optional[int] = None


class SearchResponse(BaseModel):
    """Search response."""
    results: List[SearchResult]
    query: str


# Tracked item schemas
class TrackedItemCreate(BaseModel):
    """Create tracked item."""
    title: str
    type: ContentType
    language: Language
    arabseed_url: str
    poster_url: Optional[str] = None
    description: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None


class TrackedItemUpdate(BaseModel):
    """Update tracked item."""
    monitored: Optional[bool] = None


class TrackedItemResponse(BaseModel):
    """Tracked item response."""
    id: int
    title: str
    type: ContentType
    language: Language
    arabseed_url: str
    poster_url: Optional[str] = None
    description: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    monitored: bool
    last_check: Optional[datetime] = None
    next_check: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    episode_count: Optional[int] = None
    downloaded_count: Optional[int] = None
    
    class Config:
        from_attributes = True


# Episode schemas
class EpisodeResponse(BaseModel):
    """Episode response."""
    id: int
    tracked_item_id: int
    season: int
    episode_number: int
    title: Optional[str] = None
    arabseed_url: str
    download_url: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    monitored: bool
    downloaded: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EpisodeUpdate(BaseModel):
    """Update episode."""
    monitored: Optional[bool] = None


# Download schemas
class DownloadResponse(BaseModel):
    """Download response."""
    id: int
    tracked_item_id: int
    episode_id: Optional[int] = None
    download_url: str
    destination_path: str
    final_path: Optional[str] = None
    status: DownloadStatus
    progress: float
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime
    
    # Include related info
    content_title: Optional[str] = None
    episode_info: Optional[str] = None
    
    class Config:
        from_attributes = True


# Settings schemas
class SettingUpdate(BaseModel):
    """Update setting."""
    value: str


class SettingResponse(BaseModel):
    """Setting response."""
    key: str
    value: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True


class SettingsBatch(BaseModel):
    """Batch update settings."""
    settings: Dict[str, str]


# Task schemas
class TaskResponse(BaseModel):
    """Background task response."""
    task_id: str
    status: str
    message: str


# JDownloader test response
class JDownloaderTestResponse(BaseModel):
    """JDownloader connection test response."""
    connected: bool
    message: str
    version: Optional[str] = None

