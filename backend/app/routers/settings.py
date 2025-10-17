"""Settings endpoints."""
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.schemas import SettingResponse, SettingUpdate, SettingsBatch, JDownloaderTestResponse
from app.services.jdownloader import JDownloaderClient
from app.config import settings as config
import os
from pathlib import Path

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=List[SettingResponse])
async def get_all_settings(db: Session = Depends(get_db)):
    """Get all settings.
    
    Args:
        db: Database session
        
    Returns:
        List of settings
    """
    settings = db.query(Setting).all()
    return settings


@router.get("/directories")
async def list_tracked_directories():
    """List contents of configured tracked and download directories (one level deep).
    Returns names and basic metadata to render in Settings page.
    """
    def list_dir(dir_path: str):
        try:
            p = Path(dir_path)
            if not p.exists() or not p.is_dir():
                return {"path": dir_path, "exists": p.exists(), "items": []}
            entries = []
            for child in p.iterdir():
                try:
                    stat = child.stat()
                    entries.append({
                        "name": child.name,
                        "path": str(child),
                        "is_dir": child.is_dir(),
                        "size": 0 if child.is_dir() else stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except Exception:
                    continue
            # Sort: directories first, then files by name
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return {"path": dir_path, "exists": True, "items": entries}
        except Exception as e:
            return {"path": dir_path, "exists": False, "items": [], "error": str(e)}

    payload = {
        "download_folder": list_dir(config.download_folder),
        "english_series_dir": list_dir(config.english_series_dir),
        "arabic_series_dir": list_dir(config.arabic_series_dir),
        "english_movies_dir": list_dir(config.english_movies_dir),
        "arabic_movies_dir": list_dir(config.arabic_movies_dir),
    }
    from fastapi.responses import JSONResponse
    return JSONResponse(content=payload)


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(key: str, db: Session = Depends(get_db)):
    """Get specific setting.
    
    Args:
        key: Setting key
        db: Database session
        
    Returns:
        Setting
    """
    setting = db.query(Setting).filter(Setting.key == key).first()
    if not setting:
        # Return default values from config
        from app.config import settings as config
        default_values = {
            "jdownloader_host": config.jdownloader_host,
            "jdownloader_port": str(config.jdownloader_port),
            "download_folder": config.download_folder,
            "english_series_dir": config.english_series_dir,
            "arabic_series_dir": config.arabic_series_dir,
            "english_movies_dir": config.english_movies_dir,
            "arabic_movies_dir": config.arabic_movies_dir,
            "check_interval_hours": str(config.check_interval_hours),
        }
        
        if key in default_values:
            return SettingResponse(key=key, value=default_values[key])
            
    return setting


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    update: SettingUpdate,
    db: Session = Depends(get_db)
):
    """Update setting.
    
    Args:
        key: Setting key
        update: New value
        db: Database session
        
    Returns:
        Updated setting
    """
    setting = db.query(Setting).filter(Setting.key == key).first()
    
    if setting:
        setting.value = update.value
    else:
        setting = Setting(key=key, value=update.value)
        db.add(setting)
        
    db.commit()
    db.refresh(setting)
    return setting


@router.put("", response_model=Dict[str, str])
async def batch_update_settings(
    batch: SettingsBatch,
    db: Session = Depends(get_db)
):
    """Batch update multiple settings.
    
    Args:
        batch: Settings to update
        db: Database session
        
    Returns:
        Status message
    """
    for key, value in batch.settings.items():
        setting = db.query(Setting).filter(Setting.key == key).first()
        
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            db.add(setting)
            
    db.commit()
    return {"message": f"Updated {len(batch.settings)} settings"}


@router.post("/jdownloader/test", response_model=JDownloaderTestResponse)
async def test_jdownloader_connection():
    """Test JDownloader connection.
    
    Returns:
        Connection test result
    """
    client = JDownloaderClient()
    result = await client.test_connection()
    
    return JDownloaderTestResponse(**result)


@router.get("/directories")
async def list_tracked_directories():
    """List contents of configured tracked and download directories (one level deep).
    Returns names and basic metadata to render in Settings page.
    """
    def list_dir(dir_path: str):
        try:
            p = Path(dir_path)
            if not p.exists() or not p.is_dir():
                return {"path": dir_path, "exists": p.exists(), "items": []}
            entries = []
            for child in p.iterdir():
                try:
                    stat = child.stat()
                    entries.append({
                        "name": child.name,
                        "path": str(child),
                        "is_dir": child.is_dir(),
                        "size": 0 if child.is_dir() else stat.st_size,
                        "modified": stat.st_mtime,
                    })
                except Exception:
                    continue
            # Sort: directories first, then files by name
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return {"path": dir_path, "exists": True, "items": entries}
        except Exception as e:
            return {"path": dir_path, "exists": False, "items": [], "error": str(e)}

    payload = {
        "download_folder": list_dir(config.download_folder),
        "english_series_dir": list_dir(config.english_series_dir),
        "arabic_series_dir": list_dir(config.arabic_series_dir),
        "english_movies_dir": list_dir(config.english_movies_dir),
        "arabic_movies_dir": list_dir(config.arabic_movies_dir),
    }
    from fastapi.responses import JSONResponse
    return JSONResponse(content=payload)

