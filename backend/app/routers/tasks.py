"""Background tasks endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import TaskResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/check-new-episodes", response_model=TaskResponse)
async def trigger_episode_check(db: Session = Depends(get_db)):
    """Manually trigger episode check for all tracked series.
    
    Args:
        db: Database session
        
    Returns:
        Task info
    """
    from app.tasks.episode_checker import check_new_episodes
    
    # Trigger task
    task = check_new_episodes.delay()
    
    return TaskResponse(
        task_id=task.id,
        status="started",
        message="Episode check task started"
    )


@router.post("/sync-downloads", response_model=TaskResponse)
async def trigger_download_sync(db: Session = Depends(get_db)):
    """Manually trigger download sync with JDownloader.
    
    Args:
        db: Database session
        
    Returns:
        Task info
    """
    from app.tasks.download_monitor import sync_downloads
    
    # Trigger task
    task = sync_downloads.delay()
    
    return TaskResponse(
        task_id=task.id,
        status="started",
        message="Download sync task started"
    )


@router.post("/scan-download-directory", response_model=TaskResponse)
async def trigger_directory_scan(db: Session = Depends(get_db)):
    """Manually trigger download directory scan.
    
    Args:
        db: Database session
        
    Returns:
        Task info
    """
    from app.tasks.download_monitor import scan_download_directory
    
    # Trigger task
    task = scan_download_directory.delay()
    
    return TaskResponse(
        task_id=task.id,
        status="started",
        message="Download directory scan task started"
    )


@router.post("/validate-directories", response_model=TaskResponse)
async def trigger_directory_validation(db: Session = Depends(get_db)):
    """Manually trigger media directory validation and creation.
    
    Args:
        db: Database session
        
    Returns:
        Task info
    """
    from app.services.file_organizer import FileOrganizer
    
    try:
        organizer = FileOrganizer()
        validation_result = organizer.validate_media_directories()
        
        if validation_result["overall_valid"]:
            message = "All media directories are properly configured"
        else:
            message = f"Directory validation completed with {len(validation_result['errors'])} errors"
        
        return TaskResponse(
            task_id="directory_validation",
            status="completed",
            message=message
        )
    except Exception as e:
        return TaskResponse(
            task_id="directory_validation",
            status="failed",
            message=f"Directory validation failed: {str(e)}"
        )

