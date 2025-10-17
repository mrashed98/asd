# Architecture Documentation

## System Overview

ArabSeed Downloader is a full-stack web application designed to automate the discovery, tracking, and downloading of content from ArabSeed. The system follows a microservices architecture with separate containers for frontend, backend, workers, and data storage.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           User Browser                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Next.js Frontend (Port 3000)                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Search Page  │  │ Tracked Page │  │  Downloads Page    │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │Episodes Page │  │Settings Page │                            │
│  └──────────────┘  └──────────────┘                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ REST API
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Port 8000)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ API Routers                                               │  │
│  │  • /api/search      • /api/downloads                     │  │
│  │  • /api/tracked     • /api/settings                      │  │
│  │  • /api/tasks                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Services                                                  │  │
│  │  • ArabSeedScraper  • FileOrganizer                      │  │
│  │  • JDownloaderClient                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Database (SQLAlchemy + SQLite)                           │  │
│  │  • tracked_items    • episodes    • downloads            │  │
│  │  • settings                                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────┬───────────────────────────────┬───────────────────┘
              │                               │
              │                               │
              ▼                               ▼
┌─────────────────────────┐   ┌──────────────────────────────────┐
│  Celery Worker          │   │    Celery Beat (Scheduler)       │
│                         │   │                                  │
│  Background Tasks:      │   │  Periodic Tasks:                 │
│  • Episode checking     │   │  • Hourly episode check          │
│  • Download monitoring  │   │  • 5-min download sync           │
│  • File organization    │   │                                  │
└────────┬────────────────┘   └────────────┬─────────────────────┘
         │                                 │
         │                                 │
         └────────┬────────────────────────┘
                  │
                  │ Task Queue
                  ▼
         ┌─────────────────┐
         │  Redis          │
         │  Message Broker │
         └─────────────────┘

External Integrations:
  • ArabSeed Website (via Playwright/Chromium)
  • JDownloader API (download client)
  • File System (media organization)
```

## Component Details

### 1. Frontend (Next.js 14)

**Technology Stack:**
- React 19 with App Router
- TypeScript for type safety
- Tailwind CSS for styling
- shadcn/ui for UI components
- React Query for data fetching
- Axios for HTTP requests

**Key Features:**
- Server-side rendering (SSR) for initial page loads
- Client-side navigation for SPA experience
- Real-time updates via polling (5s for downloads)
- Responsive design for mobile/tablet/desktop

**Pages:**
1. **Search Page** (`/`)
   - Search ArabSeed content
   - Display results with type classification
   - Add items to tracking

2. **Tracked Items** (`/tracked`)
   - List all tracked movies/series
   - Filter by type
   - Access episode management
   - Remove tracked items

3. **Episodes Page** (`/tracked/[id]/episodes`)
   - View episodes grouped by season
   - Trigger manual downloads
   - See download status

4. **Downloads Page** (`/downloads`)
   - Monitor active downloads
   - View completed/failed downloads
   - Retry failed downloads
   - Real-time progress updates

5. **Settings Page** (`/settings`)
   - Configure JDownloader connection
   - Set directory paths
   - Adjust check intervals
   - Test connections

### 2. Backend (FastAPI)

**Technology Stack:**
- FastAPI for REST API
- SQLAlchemy ORM
- SQLite database
- Pydantic for validation
- Uvicorn ASGI server

**Architecture Layers:**

1. **API Layer** (`app/routers/`)
   - Request validation
   - Response serialization
   - Error handling
   - CORS configuration

2. **Service Layer** (`app/services/`)
   - Business logic
   - External integrations
   - File operations

3. **Data Layer** (`app/models.py`)
   - ORM models
   - Database relationships
   - Schema definitions

**Database Schema:**

```sql
tracked_items
  ├── id (PK)
  ├── title
  ├── type (movie/series)
  ├── language (en/ar)
  ├── arabseed_url
  ├── monitored
  └── timestamps

episodes
  ├── id (PK)
  ├── tracked_item_id (FK)
  ├── season
  ├── episode_number
  ├── arabseed_url
  ├── file_path
  └── downloaded

downloads
  ├── id (PK)
  ├── tracked_item_id (FK)
  ├── episode_id (FK, nullable)
  ├── download_url
  ├── jdownloader_link_id
  ├── status
  ├── progress
  └── timestamps

settings
  ├── key (PK)
  ├── value
  └── description
```

### 3. ArabSeed Scraper

**Technology**: Playwright with Chromium

**Responsibilities:**
1. **Search**: Query ArabSeed and parse results
2. **Episode Detection**: Extract episodes from series pages
3. **Download URL Extraction**: Navigate complex download flow

**Download Flow Automation:**
```
1. Navigate to download page
2. Click 720p quality option
3. Select "ArabSeed Direct Server"
4. Handle 15-second timers (2 stages)
5. Close ad popups automatically
6. Extract final .mp4 URL
7. Return URL with referer headers
```

**Ad Handling:**
- Detect popup windows
- Check domain against blocklist
- Auto-close ad popups
- Retry clicks after ad closure

**Resilience Features:**
- Retry logic (3 attempts)
- Network request capture as fallback
- Timeout handling
- Error logging

### 4. JDownloader Integration

**API Endpoints Used:**
- `/linkgrabberv2/addLinks` - Submit downloads
- `/linkgrabberv2/moveToDownloadlist` - Start downloads
- `/downloadsV2/queryLinks` - Check status
- `/downloadsV2/queryPackages` - Monitor packages
- `/system/getSystemInfos` - Health check

**Download Workflow:**
```
1. Backend extracts download URL from ArabSeed
2. Submit URL to JDownloader with destination path
3. JDownloader adds to link grabber
4. Move from link grabber to download queue
5. Store JDownloader link ID in database
6. Periodic polling for status updates
7. Detect completion
8. Trigger file organization
```

### 5. Background Tasks (Celery)

**Celery Worker:**
- Processes asynchronous tasks
- Runs Playwright automation
- Monitors JDownloader status
- Organizes completed files

**Celery Beat (Scheduler):**
- Schedules periodic tasks
- Configurable intervals
- Task monitoring

**Task Definitions:**

1. **Episode Checker** (`check_new_episodes`)
   - Frequency: Hourly (configurable)
   - Process:
     ```
     For each monitored series:
       1. Fetch episodes from ArabSeed
       2. Compare with database
       3. Detect new episodes
       4. Auto-trigger downloads for new episodes
       5. Update last_check timestamp
     ```

2. **Download Monitor** (`sync_downloads`)
   - Frequency: Every 5 minutes
   - Process:
     ```
     For each active download:
       1. Query JDownloader status
       2. Update progress in database
       3. Detect completion
       4. Verify file exists
       5. Organize to final directory
       6. Update episode/download records
     ```

### 6. File Organizer

**Naming Conventions:**

**Series Episodes:**
```
/media/english-series/
  └── Breaking Bad/
      └── Season 01/
          ├── Breaking Bad - S01E01.mp4
          ├── Breaking Bad - S01E02.mp4
          └── ...
```

**Movies:**
```
/media/movies/
  ├── The Dark Knight (2008).mp4
  └── Inception (2010).mp4
```

**Organization Process:**
1. Verify download completion
2. Parse season/episode from filename/URL
3. Sanitize filenames (remove invalid chars)
4. Create directory structure
5. Move file with atomic operation
6. Update database with final path

### 7. Redis Message Broker

**Usage:**
- Celery task queue
- Task result backend
- Task state storage

**Configuration:**
- Persistence: AOF (Append-Only File)
- Max memory: 256MB
- Eviction policy: allkeys-lru

## Data Flow Examples

### Search Flow
```
User → Frontend → Backend API → ArabSeedScraper → Playwright
                                                     ↓
User ← Frontend ← Backend API ← Parse Results ← HTTP Response
```

### Track Series Flow
```
User clicks Track
  ↓
Frontend POST /api/tracked
  ↓
Backend creates tracked_item
  ↓
Backend triggers episode fetch
  ↓
ArabSeedScraper extracts episodes
  ↓
Backend creates episode records
  ↓
Response to frontend with episode count
```

### Auto-Download Flow
```
Celery Beat triggers check_new_episodes
  ↓
Worker fetches episodes for each series
  ↓
New episode detected
  ↓
Worker extracts download URL (Playwright)
  ↓
Worker submits to JDownloader
  ↓
Download record created with status: in_progress
  ↓
[5 minutes later]
  ↓
Celery Beat triggers sync_downloads
  ↓
Worker queries JDownloader
  ↓
Download complete detected
  ↓
Worker organizes file
  ↓
Episode marked as downloaded
```

## Scalability Considerations

### Current Architecture
- Single-user deployment
- SQLite database
- Shared file system

### Scaling Options

**For Multiple Users:**
1. Replace SQLite with PostgreSQL
2. Add authentication layer
3. Implement user isolation in database
4. Multi-tenant file organization

**For High Volume:**
1. Add more Celery workers
2. Implement task prioritization
3. Use distributed task queue (RabbitMQ)
4. Cache search results

**For Distributed Deployment:**
1. Separate scraper service
2. Use S3/MinIO for file storage
3. Add load balancer for backend
4. Implement session management

## Security Considerations

### Current Security
- No authentication (single-user)
- CORS restricted to configured origins
- Docker network isolation
- No sensitive data storage

### Production Recommendations
1. Add authentication (OAuth2/JWT)
2. Implement rate limiting
3. Add HTTPS/TLS
4. Encrypt sensitive settings
5. Implement API key for inter-service communication
6. Add request logging and monitoring

## Monitoring and Observability

### Health Checks
- Backend: `/health` endpoint
- Frontend: Port 3000 availability
- Redis: `redis-cli ping`
- Celery: Task heartbeat

### Logging
- Backend: Uvicorn access logs
- Celery: Task execution logs
- Frontend: Next.js server logs
- All accessible via `docker-compose logs`

### Metrics to Monitor
- Download success rate
- Episode detection accuracy
- File organization errors
- Task queue length
- API response times
- Disk usage

## Deployment Topology

### Docker Compose (Current)
```
┌─────────────────────────────────────┐
│         Docker Host                 │
│                                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ │
│  │Frontend│ │Backend │ │ Redis  │ │
│  └────────┘ └────────┘ └────────┘ │
│  ┌────────┐ ┌────────┐            │
│  │ Worker │ │  Beat  │            │
│  └────────┘ └────────┘            │
│                                     │
│  Volumes:                          │
│  • /data (SQLite)                  │
│  • /downloads                      │
│  • /media                          │
└─────────────────────────────────────┘
```

### Kubernetes (Future)
```
┌─────────────────────────────────────────┐
│          Kubernetes Cluster             │
│                                         │
│  Deployments:                          │
│  • Frontend (3 replicas)               │
│  • Backend (3 replicas)                │
│  • Celery Worker (2 replicas)          │
│  • Celery Beat (1 replica)             │
│                                         │
│  StatefulSets:                         │
│  • Redis (1 replica with PVC)          │
│  • PostgreSQL (1 replica with PVC)     │
│                                         │
│  Persistent Volumes:                   │
│  • Database storage                    │
│  • Media library (NFS/Ceph)            │
└─────────────────────────────────────────┘
```

## Technology Choices Rationale

**FastAPI**: Modern, fast, automatic OpenAPI docs
**Next.js**: SEO-friendly, great DX, SSR support
**SQLite**: Simple, no extra service for single-user
**Celery**: Mature, reliable, good monitoring tools
**Playwright**: Robust, good for complex automation
**Docker**: Consistent environment, easy deployment
**Redis**: Fast, reliable message broker

---

**Last Updated**: 2025-01-16
**Architecture Version**: 1.0
**Maintainer**: Development Team

