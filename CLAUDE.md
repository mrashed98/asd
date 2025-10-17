# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ArabSeed Downloader is a web application for tracking and automatically downloading content from ArabSeed (a.asd.homes). It uses web scraping with Playwright to extract download URLs, integrates with JDownloader for download management, and automatically organizes completed downloads into proper directory structures.

**Tech Stack:**
- Backend: FastAPI (Python 3.11+) with SQLAlchemy ORM (SQLite)
- Frontend: Next.js 15 with React 19, Tailwind CSS, shadcn/ui
- Task Queue: Celery with Redis broker
- Web Scraping: Playwright (Chromium)
- Download Manager: JDownloader (via local API or My.JDownloader cloud API)

## Development Commands

### Local Development (Backend)
```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r pyproject.toml
playwright install chromium
uvicorn app.main:app --reload
```

### Local Development (Frontend)
```bash
cd frontend
npm install
npm run dev
```

### Local Celery Workers
```bash
# Terminal 1: Worker
celery -A app.celery_app worker --loglevel=info

# Terminal 2: Beat scheduler
celery -A app.celery_app beat --loglevel=info
```

### Docker Commands (Production)
```bash
make init              # Initialize project (create dirs and .env)
make build            # Build Docker images
make up               # Start all services
make down             # Stop all services
make logs             # View logs
make restart          # Restart services
make clean            # Stop and remove containers/volumes

# Service-specific
make backend-shell     # Shell into backend container
make frontend-shell    # Shell into frontend container
make redis-cli        # Open Redis CLI

# Task triggers
make check-episodes   # Manually trigger episode check
make sync-downloads   # Manually trigger download sync
make test-jdownloader # Test JDownloader connection

make status           # Show service status
```

## Architecture

### Backend Structure (`backend/app/`)

**Core Components:**
- `models.py` - SQLAlchemy models: TrackedItem, Episode, Download, Setting
- `schemas.py` - Pydantic schemas for API validation
- `database.py` - Database session management
- `config.py` - Pydantic Settings with environment variables
- `main.py` - FastAPI app initialization and CORS setup

**API Routers (`routers/`):**
- `search.py` - Search ArabSeed content
- `tracked.py` - Manage tracked items and episodes
- `downloads.py` - Download management and retry
- `settings.py` - App settings and JDownloader test
- `tasks.py` - Manual task triggers

**Services (`services/`):**
- `jdownloader.py` - JDownloader client (supports both local API and My.JDownloader cloud API)
- `file_organizer.py` - Organize completed downloads into media directories

**Scraper (`scraper/`):**
- `arabseed.py` - ArabSeedScraper class using Playwright
  - Uses async context manager pattern
  - Handles ad blocking and popup closing
  - Navigates multi-step download flow (quality selection → server selection → timer waits → final URL extraction)
  - Key methods: `search()`, `get_episodes()`, `get_seasons()`, `get_download_url()`

**Tasks (`tasks/`):**
- `episode_checker.py` - Celery task to check for new episodes (runs hourly)
- `download_monitor.py` - Celery task to sync JDownloader status (runs every 5 minutes)

### Database Models

- **TrackedItem**: Movies or series being tracked (has `monitored` flag)
- **Episode**: Individual episodes of a series (linked to TrackedItem)
- **Download**: Download records with JDownloader link/package IDs and status
- **Setting**: Key-value settings stored in database

### Scraping Flow

The ArabSeedScraper navigates through ArabSeed's complex download process:

1. **Search**: Query ArabSeed search endpoint, classify results as movie/series
2. **Episode Discovery**: Extract episode links from series pages (handles Arabic text patterns)
3. **Download URL Extraction** (most complex):
   - Navigate to content page
   - Click download button → navigate to download page
   - Select quality (1080p/720p/480p via `data-quality` attribute)
   - Click "ArabSeed Direct Server" link (`a.arabseed`)
   - Click first download button (`button#start`)
   - Wait 15 seconds for timer
   - Extract final download link (`.mp4` or `.mkv` URL)
   - Handle intermediate redirect pages with `asd7b=1` parameter

**Important**: The scraper uses JavaScript evaluation to bypass ad overlays and click through the multi-step process.

### Celery Background Tasks

**Episode Checker** (hourly):
1. Query all monitored series
2. Fetch episodes from ArabSeed
3. Detect new episodes (by `arabseed_url`)
4. Extract download URL and send to JDownloader
5. Update `last_check` and `next_check` timestamps

**Download Monitor** (every 5 minutes):
1. Query JDownloader for download status
2. Update Download records with progress/status
3. When complete, trigger file organization
4. Move files to appropriate directories (English/Arabic series, movies)

### JDownloader Integration

Supports two connection modes:
1. **Local API**: Direct HTTP connection to JDownloader's REST API
2. **My.JDownloader**: Cloud API using myjdapi library (requires email/password/device)

Configuration via environment variables:
- `JDOWNLOADER_HOST` / `JDOWNLOADER_PORT` - Local API
- `MYJD_EMAIL` / `MYJD_PASSWORD` / `MYJD_DEVICE_NAME` - My.JDownloader

### Frontend Structure (`frontend/`)

- Next.js 14 App Router pattern
- `app/` - Pages and layouts
- `components/` - React components (shadcn/ui)
- `lib/` - API client and utilities
- Uses React Query (@tanstack/react-query) for data fetching
- Zustand for state management

## Key Configuration

**Environment Variables** (`.env`):
```bash
# JDownloader
JDOWNLOADER_HOST=host.docker.internal  # Use this in Docker
JDOWNLOADER_PORT=3129
MYJD_EMAIL=             # Optional: My.JDownloader email
MYJD_PASSWORD=          # Optional: My.JDownloader password
MYJD_DEVICE_NAME=       # Optional: My.JDownloader device name

# Directories
DOWNLOAD_FOLDER=./downloads
ENGLISH_SERIES_DIR=./media/english-series
ARABIC_SERIES_DIR=./media/arabic-series
ENGLISH_MOVIES_DIR=./media/english-movies
ARABIC_MOVIES_DIR=./media/arabic-movies

# Task Intervals
CHECK_INTERVAL_HOURS=1
DOWNLOAD_SYNC_INTERVAL_MINUTES=5

# Database
DATABASE_URL=sqlite:///./data/arabseed.db

# Redis
REDIS_URL=redis://localhost:6379/0
```

**Docker Networking**:
- Backend runs on port 8001 (mapped from internal 8000)
- Frontend runs on port 3001 (mapped from internal 3000)
- Use `host.docker.internal` to access host machine's JDownloader from containers

## Testing

Run backend tests:
```bash
cd backend
pytest
```

Test JDownloader connection:
```bash
curl -X POST http://localhost:8001/api/settings/jdownloader/test
```

Test scraper locally:
```bash
python scripts/test_extraction_local.py
```

## Common Issues

**Playwright Browser Not Found**:
```bash
playwright install chromium
```

**JDownloader Connection Failed**:
- Verify JDownloader is running
- Enable "Remote API" and "Local API" in JDownloader settings
- In Docker, use `host.docker.internal` as `JDOWNLOADER_HOST`

**Episodes Not Auto-Downloading**:
- Check Celery Beat is running: `docker-compose logs celery_beat`
- Verify series is marked as `monitored=True`

**Download Extraction Fails**:
- Check scraper logs for specific step failures
- Debug screenshots saved to `/app/data/debug_final_page.png`
- ArabSeed may have changed their page structure

## Code Patterns

**Async/Await**: Backend uses async/await extensively (FastAPI, Playwright, aiohttp)

**Context Managers**:
```python
async with ArabSeedScraper() as scraper:
    results = await scraper.search(query)
```

**Celery Tasks**: Define with decorator, run sync code but can call async functions via `asyncio.run()`
```python
@celery_app.task(name="app.tasks.episode_checker.check_new_episodes")
def check_new_episodes():
    asyncio.run(_fetch_episodes(url))
```

**Database Sessions**: Use SessionLocal() and try/finally pattern
```python
db = SessionLocal()
try:
    # database operations
    db.commit()
except:
    db.rollback()
finally:
    db.close()
```

## Security Notes

- Designed for single-user home server deployment
- No authentication system (assumes trusted network)
- CORS configured for localhost only
- Should be deployed behind firewall/reverse proxy
