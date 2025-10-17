# Testing and Validation Guide

This document outlines the testing procedures for the ArabSeed Downloader application.

## End-to-End Testing Checklist

### Prerequisites
- [ ] Docker and Docker Compose installed
- [ ] JDownloader installed and running with API enabled
- [ ] All containers running: `docker-compose ps`
- [ ] Backend health check passing: `curl http://localhost:8001/health`
- [ ] Frontend accessible at http://localhost:3001

## Test Scenarios

### 1. Search Functionality

**Test Case 1.1: Search for Series**
- Navigate to http://localhost:3001
- Enter "High Potential" in search box
- Click Search
- **Expected**: Results displayed with series badge
- **Validation**: Result cards show title, type badge, and optional poster

**Test Case 1.2: Search for Movie**
- Enter "Bad Man" in search box
- Click Search
- **Expected**: Results displayed with movie badge
- **Validation**: At least one result with type "movie"

**Test Case 1.3: Invalid Search**
- Enter "xyzabc123notfound"
- Click Search
- **Expected**: "No results found" message displayed

### 2. Tracking Functionality

**Test Case 2.1: Track a Series**
- Search for "High Potential"
- Click on first result
- Select language: English
- Click "Track" button
- **Expected**: Dialog closes, item added to tracked items
- **Validation**: Navigate to Tracked Items page, item should appear

**Test Case 2.2: Track a Movie**
- Search for "Bad Man"
- Click on first result
- Select language: Arabic
- Click "Track"
- **Expected**: Item added successfully
- **Validation**: Check Tracked Items page

**Test Case 2.3: Duplicate Tracking Prevention**
- Try to track the same item again
- **Expected**: Error message about item already tracked

**Test Case 2.4: View Episodes**
- Go to Tracked Items
- Click "Episodes" on a tracked series
- **Expected**: Episodes page displays with seasons grouped
- **Validation**: Episodes sorted by season and episode number

### 3. Download Functionality

**Test Case 3.1: Manual Episode Download**
- Navigate to Episodes page for tracked series
- Click "Download" on an episode
- **Expected**: Download button disabled, download initiated
- **Validation**: 
  - Check Downloads page for new entry
  - Download status shows "pending" or "in_progress"
  - JDownloader shows the download

**Test Case 3.2: Monitor Download Progress**
- Go to Downloads page
- **Expected**: Active downloads show progress bar
- **Validation**: Progress percentage updates (refreshes every 5 seconds)

**Test Case 3.3: Download Completion and Organization**
- Wait for a download to complete in JDownloader
- Wait up to 5 minutes for sync task
- **Expected**: 
  - Download status changes to "completed"
  - File moved to appropriate directory (English/Arabic series dir)
  - Proper naming: "Series Name - S01E05.mp4"
  - Season folder created if needed

**Test Case 3.4: Failed Download Retry**
- If a download fails, click "Retry" button
- **Expected**: Download re-initiated with pending status

### 4. Automatic Episode Checking

**Test Case 4.1: Manual Episode Check**
- Go to Tracked Items page
- Click "Check for Updates" button
- **Expected**: Task initiated successfully
- **Validation**: Check celery_worker logs for activity

**Test Case 4.2: Scheduled Episode Check**
- Wait for hourly check (or configure shorter interval for testing)
- **Expected**: Celery beat triggers check
- **Validation**: 
  - Check logs: `docker-compose logs celery_beat`
  - New episodes detected and added to database
  - Auto-downloads triggered

**Test Case 4.3: New Episode Auto-Download**
- When new episode detected:
- **Expected**: 
  - Episode appears in Episodes list
  - Download automatically initiated
  - Appears in Downloads queue

### 5. Settings and Configuration

**Test Case 5.1: JDownloader Connection Test**
- Go to Settings page
- Click "Test Connection"
- **Expected**: Green badge showing "Successfully connected"
- **Validation**: Version number displayed

**Test Case 5.2: Update Directory Settings**
- Go to Settings page
- Change "Download Folder" to custom path
- Click "Save Settings"
- **Expected**: Success message displayed
- **Validation**: Settings persisted (refresh page to verify)

**Test Case 5.3: Update Check Interval**
- Change "Check Interval (hours)" to 2
- Save settings
- **Expected**: Settings saved successfully
- **Validation**: Celery beat will use new interval on next restart

### 6. File Organization Validation

**Test Case 6.1: English Series Organization**
- Download an English series episode
- **Expected Directory Structure**:
  ```
  /media/english-series/
    └── Series Name/
        └── Season 01/
            └── Series Name - S01E05.mp4
  ```

**Test Case 6.2: Arabic Series Organization**
- Download an Arabic series episode
- **Expected Directory Structure**:
  ```
  /media/arabic-series/
    └── Series Name/
        └── Season 01/
            └── Series Name - S01E05.mp4
  ```

**Test Case 6.3: Movie Organization**
- Download a movie
- **Expected Directory Structure**:
  ```
  /media/movies/
    └── Movie Name (2024).mp4
  ```

### 7. Background Tasks

**Test Case 7.1: Celery Worker Health**
- Check worker is running:
  ```bash
  docker-compose logs celery_worker | tail -20
  ```
- **Expected**: No error messages, worker ready

**Test Case 7.2: Celery Beat Scheduler**
- Check beat is scheduling tasks:
  ```bash
  docker-compose logs celery_beat | tail -20
  ```
- **Expected**: Periodic task scheduling messages

**Test Case 7.3: Download Sync Task**
- Manually trigger sync:
  ```bash
  curl -X POST http://localhost:8001/api/tasks/sync-downloads
  ```
- **Expected**: Task ID returned, sync executed
- **Validation**: Check logs for sync activity

## API Testing

### Using cURL

**Search API**
```bash
curl "http://localhost:8001/api/search?query=High%20Potential"
```

**List Tracked Items**
```bash
curl "http://localhost:8001/api/tracked"
```

**Get Episodes**
```bash
curl "http://localhost:8001/api/tracked/1/episodes"
```

**List Downloads**
```bash
curl "http://localhost:8001/api/downloads"
```

**Test JDownloader**
```bash
curl -X POST "http://localhost:8001/api/settings/jdownloader/test"
```

### Using Swagger UI

Navigate to http://localhost:8001/docs for interactive API documentation.

## Performance Testing

### Load Test Search
```bash
for i in {1..10}; do
  curl "http://localhost:8001/api/search?query=test" &
done
wait
```

### Monitor Resource Usage
```bash
docker stats
```

**Expected**: 
- Backend: < 500MB RAM
- Frontend: < 200MB RAM
- Redis: < 50MB RAM
- Celery workers: < 300MB RAM each

## Common Issues and Solutions

### Issue: Search returns no results
**Solution**: 
- Check backend logs: `docker-compose logs backend`
- Verify Playwright can access ArabSeed: might be blocked or site structure changed
- Test manually by navigating to https://a.asd.homes/

### Issue: Downloads stuck in pending
**Solutions**:
- Check JDownloader is running: `curl http://host.docker.internal:3129/system/getSystemInfos`
- Verify JDownloader API enabled
- Check celery_worker logs for errors
- Manually trigger sync: `make sync-downloads`

### Issue: Files not organizing
**Solutions**:
- Check directory permissions: `ls -la media/`
- Verify paths in settings match Docker volumes
- Check celery_worker logs for organization errors
- Ensure JDownloader completed download (not still in queue)

### Issue: Episodes not auto-checking
**Solutions**:
- Verify celery_beat is running: `docker-compose ps celery_beat`
- Check series is marked as "monitored"
- View beat logs: `docker-compose logs celery_beat`
- Manually trigger: `make check-episodes`

## Debugging Tools

### View All Logs
```bash
docker-compose logs -f
```

### View Specific Service Logs
```bash
docker-compose logs -f backend
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
```

### Access Database
```bash
docker-compose exec backend sqlite3 /app/data/arabseed.db
```

### Redis CLI
```bash
docker-compose exec redis redis-cli
```

### Restart Specific Service
```bash
docker-compose restart celery_worker
```

## Test Data Cleanup

### Remove All Tracked Items
```bash
docker-compose exec backend sqlite3 /app/data/arabseed.db "DELETE FROM tracked_items;"
```

### Clear Downloads
```bash
docker-compose exec backend sqlite3 /app/data/arabseed.db "DELETE FROM downloads;"
```

### Full Reset
```bash
docker-compose down -v
rm -rf data/ downloads/* media/*
make init
docker-compose up -d
```

## Validation Checklist

Before considering the application production-ready:

- [ ] All test scenarios pass
- [ ] No errors in any service logs
- [ ] JDownloader connection successful
- [ ] Search returns expected results
- [ ] Tracking works for both movies and series
- [ ] Episodes are detected and listed correctly
- [ ] Manual downloads complete successfully
- [ ] Files organize to correct directories with proper naming
- [ ] Automatic episode checking works
- [ ] New episodes auto-download
- [ ] Download progress updates correctly
- [ ] Failed downloads can be retried
- [ ] Settings persist across restarts
- [ ] All background tasks execute on schedule
- [ ] Resource usage within acceptable limits

## Continuous Testing

For ongoing validation:

1. **Daily**: Monitor logs for errors
2. **Weekly**: Verify automatic downloads are working
3. **Monthly**: Check disk space and clean up old downloads
4. **After Updates**: Run full test suite

## Reporting Issues

When reporting issues, include:
1. Steps to reproduce
2. Expected behavior
3. Actual behavior
4. Relevant logs from `docker-compose logs`
5. Service status from `docker-compose ps`
6. Environment details (OS, Docker version)

---

**Last Updated**: 2025-01-16
**Test Coverage**: End-to-end functional testing
**Test Environment**: Docker Compose on macOS/Linux

