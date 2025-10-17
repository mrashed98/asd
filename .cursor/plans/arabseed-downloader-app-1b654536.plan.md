<!-- 1b654536-0908-4fbb-9d81-5f593389b4b2 4091c6da-5f7b-4c83-b28e-9d8eeca853bc -->
# ArabSeed Downloader Web Application

## Architecture Overview

**Backend**: Python FastAPI + SQLite + Celery (for background tasks)

**Frontend**: Next.js 14 + Tailwind CSS + shadcn/ui

**Download Client**: JDownloader API integration

**Deployment**: Docker Compose with multi-container setup

## Project Structure

```
arabseed_downloader/
├── backend/               # FastAPI application
├── frontend/              # Next.js application
├── docs/                  # Documentation (existing)
├── docker-compose.yml     # Multi-container orchestration
└── README.md             # Updated documentation
```

## Core Features & Technical Flow

### 1. Search & Content Discovery

- **Search API**: Implement the search flow from `research.md` (lines 11-49)
- Use Playwright/Selenium to query `https://a.asd.homes/find/?word=<QUERY>&type=`
- Parse results with selectors: `a.movie__block`, `.movie__title`, `.mv__pro__type`
- Classify content as Movie/Series using badge text and URL patterns
- For series: detect episodes using heading "الحلقات" or "المواسم" (lines 183-208)

### 2. Series/Movie Tracking System

- **Database Schema**:
  - `tracked_items` table: id, title, type (series/movie), arabseed_url, language (en/ar), status, metadata
  - `episodes` table: id, tracked_item_id, season, episode_number, title, download_url, status, file_path
  - `downloads` table: id, episode_id/tracked_item_id, jdownloader_link_id, status, progress, created_at
  - `settings` table: key-value pairs for user configuration

### 3. Automated Episode Detection (Hourly)

- **Celery Beat** scheduled task every hour
- For each tracked series:

  1. Navigate to series page
  2. Extract all episode links using DOM selectors from research (lines 197-208)
  3. Compare against database to find new episodes
  4. Automatically trigger download flow for new episodes

### 4. Download Flow (Based on Research Lines 66-180)

- **Playwright automation** to navigate ArabSeed download flow:

  1. Click 720p quality accordion
  2. Select "سيرفر عرب سيد المباشر" (ArabSeed direct server)
  3. Handle 15-second timers with polling
  4. Close ad popups (track domains: `obqj2.com`, `68s8.com`, `cm65.com`)
  5. Extract final `.mp4` URL from "تحميل" link or network capture

- Send extracted URL to **JDownloader** via API with custom download path
- Store JDownloader link ID in database for status tracking

### 5. JDownloader Integration

- **Connection**: REST API to JDownloader (default: `http://localhost:3129`)
- **Operations**:
  - `addLinks`: Submit download URLs with destination folder
  - `queryLinks`: Check download progress/status
  - `queryPackages`: Monitor download packages
- **Configuration**: Allow users to set JDownloader host/port in settings

### 6. Download Monitoring & Organization

- **Celery task** (every 5 minutes) to poll JDownloader for completed downloads
- When download completes:

  1. Verify file exists in download folder
  2. Determine content type (English Series/Arabic Series/Movie) from tracked item
  3. **For Series**:

     - Create/verify directory structure: `{SERIES_DIR}/{Series Name}/Season {N}/`
     - Move file to: `{SERIES_DIR}/{Series Name}/Season {N}/{Series Name} - S{N}E{M}.mp4`

  1. **For Movies**:

     - Move to: `{MOVIES_DIR}/{Movie Name} ({Year}).mp4`

  1. Update database: `episodes.file_path`, `downloads.status = 'completed'`

### 7. Directory Settings & Management

- **Settings Page** allows users to configure:
  - Download folder (where JDownloader saves files)
  - English Series directory
  - Arabic Series directory  
  - Movies directory
  - JDownloader API endpoint
  - Polling interval (default: 1 hour)
- **Validation**: Check directory permissions and create if missing

### 8. Frontend Features

#### Search Page

- Search input with real-time results
- Display cards with poster, title, type badge (Movie/Series)
- Click result → show details modal with download/track options

#### Tracked Items Page

- Grid/list view of all tracked content
- Filter by type (Movie/Series), language (English/Arabic), status
- For series: show episode count, latest episode, next check time
- Actions: Remove tracking, Force check now, View episodes

#### Episodes Page (for series)

- Season-grouped episode list
- Status indicators: Not Downloaded / Downloading (progress%) / Downloaded
- Manual download trigger for specific episodes
- Mark as monitored/unmonitored

#### Downloads Queue Page

- Active downloads with progress bars (from JDownloader)
- Completed downloads with file paths
- Failed downloads with retry option
- Filter by status, content type

#### Settings Page

- Directory mappings with browse/validation
- JDownloader configuration
- Polling interval slider
- Test JDownloader connection button

### 9. API Endpoints (FastAPI)

**Content Management**:

- `POST /api/search` - Search ArabSeed
- `GET /api/tracked` - List tracked items
- `POST /api/track` - Add item to tracking
- `DELETE /api/track/{id}` - Remove tracking
- `GET /api/episodes/{series_id}` - Get episodes for series
- `POST /api/download/{episode_id}` - Manually trigger download

**Downloads**:

- `GET /api/downloads` - List downloads with status
- `POST /api/downloads/retry/{id}` - Retry failed download

**Settings**:

- `GET /api/settings` - Get all settings
- `PUT /api/settings` - Update settings
- `POST /api/jdownloader/test` - Test connection

**Background Tasks**:

- `POST /api/tasks/check-new-episodes` - Force episode check
- `POST /api/tasks/sync-downloads` - Force download sync

### 10. Docker Setup

**docker-compose.yml** services:

1. **backend**: FastAPI + Celery worker + Celery beat
2. **frontend**: Next.js production build
3. **redis**: Message broker for Celery
4. **playwright**: Separate service with browser installed

**Volume mappings**:

- `./downloads:/downloads` (JDownloader download folder)
- `./english-series:/media/english-series`
- `./arabic-series:/media/arabic-series`
- `./movies:/media/movies`
- `./data:/app/data` (SQLite database)

**Environment variables**:

- `JDOWNLOADER_HOST`, `JDOWNLOADER_PORT`
- `DOWNLOAD_FOLDER`, `ENGLISH_SERIES_DIR`, `ARABIC_SERIES_DIR`, `MOVIES_DIR`
- `CHECK_INTERVAL_HOURS`

## Technology Stack Details

**Backend**:

- FastAPI with `uvicorn`
- SQLAlchemy ORM with SQLite
- Celery + Redis for task queue
- Playwright for browser automation
- `aiohttp` for JDownloader API calls
- `uv` for dependency management

**Frontend**:

- Next.js 14 (App Router)
- React Query for API state management
- Tailwind CSS + shadcn/ui components
- Zustand for client state
- React Table for episode/download lists

## Key Implementation Considerations

1. **Resilient Download Flow**: Implement retry logic with exponential backoff for Playwright automation (handle timeouts, ad variations)
2. **Ad Domain Blocking**: Maintain configurable list of ad domains to auto-close
3. **Network Capture Fallback**: If DOM scraping fails, use Playwright network interception to capture `.mp4` URLs
4. **File Naming Convention**: Parse episode numbers from ArabSeed titles or filenames
5. **Duplicate Detection**: Check if episode already exists before downloading
6. **Error Notifications**: Log failures with context (series name, episode, error type) for debugging
7. **Resource Cleanup**: Close Playwright browser instances properly to avoid memory leaks
8. **Season Detection**: Parse season/episode from ArabSeed URL patterns (`الموسم-N-الحلقة-M`)

## Security & Production Readiness

- No authentication (single-user homeserver deployment)
- CORS configuration for frontend-backend communication
- Health check endpoints for monitoring
- Graceful shutdown handling for background tasks
- Database migrations with Alembic
- Comprehensive logging with structured format
- Docker healthchecks for all services

### To-dos

- [ ] Initialize project structure with backend/, frontend/, and docker-compose.yml
- [ ] Set up FastAPI backend with uv, SQLAlchemy, and database models
- [ ] Initialize Next.js frontend with Tailwind CSS and shadcn/ui
- [ ] Implement ArabSeed search and content scraping with Playwright
- [ ] Build automated download URL extraction flow with timer handling and ad blocking
- [ ] Implement JDownloader API client for adding downloads and monitoring status
- [ ] Create tracked items and episodes management API endpoints
- [ ] Set up Celery with Redis for hourly episode checks and download monitoring
- [ ] Implement automatic file moving and renaming logic for completed downloads
- [ ] Build search page with results display and add-to-tracking functionality
- [ ] Create tracked items page with filtering and episode management
- [ ] Build downloads queue page with progress tracking and retry options
- [ ] Implement settings page for directory configuration and JDownloader setup
- [ ] Create Dockerfiles and docker-compose.yml with all services and volume mappings
- [ ] Test end-to-end flow: search → track → auto-detect → download → organize
- [ ] Update README.md with setup instructions, configuration guide, and architecture overview