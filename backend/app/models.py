"""Database models."""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ContentType(str, Enum):
    """Content type enumeration."""
    MOVIE = "movie"
    SERIES = "series"


class Language(str, Enum):
    """Content language enumeration."""
    ENGLISH = "en"
    ARABIC = "ar"


class DownloadStatus(str, Enum):
    """Download status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TrackedItem(Base):
    """Tracked content item (movie or series)."""
    
    __tablename__ = "tracked_items"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    type = Column(SQLEnum(ContentType), nullable=False)
    language = Column(SQLEnum(Language), nullable=False)
    arabseed_url = Column(String, nullable=False, unique=True)
    poster_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)  # Extra metadata (year, genres, etc.)
    
    # Tracking settings
    monitored = Column(Boolean, default=True)
    last_check = Column(DateTime, nullable=True)
    next_check = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    episodes = relationship("Episode", back_populates="tracked_item", cascade="all, delete-orphan")
    downloads = relationship("Download", back_populates="tracked_item", cascade="all, delete-orphan")


class Episode(Base):
    """Episode information for tracked series."""
    
    __tablename__ = "episodes"
    
    id = Column(Integer, primary_key=True, index=True)
    tracked_item_id = Column(Integer, ForeignKey("tracked_items.id"), nullable=False)
    
    # Episode identification
    season = Column(Integer, nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    arabseed_url = Column(String, nullable=False, unique=True)
    
    # Download info
    download_url = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)  # In bytes
    
    # Status
    monitored = Column(Boolean, default=True)
    downloaded = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tracked_item = relationship("TrackedItem", back_populates="episodes")
    downloads = relationship("Download", back_populates="episode", cascade="all, delete-orphan")


class Download(Base):
    """Download tracking."""
    
    __tablename__ = "downloads"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to content
    tracked_item_id = Column(Integer, ForeignKey("tracked_items.id"), nullable=False)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=True)  # Null for movies
    
    # JDownloader info
    jdownloader_link_id = Column(String, nullable=True)
    jdownloader_package_id = Column(String, nullable=True)
    
    # Download details
    download_url = Column(String, nullable=False)
    destination_path = Column(String, nullable=False)
    final_path = Column(String, nullable=True)  # After organization
    
    # Status
    status = Column(SQLEnum(DownloadStatus), default=DownloadStatus.PENDING)
    progress = Column(Float, default=0.0)  # 0-100
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tracked_item = relationship("TrackedItem", back_populates="downloads")
    episode = relationship("Episode", back_populates="downloads")


class Setting(Base):
    """Application settings stored in database."""
    
    __tablename__ = "settings"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

