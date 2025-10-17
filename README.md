# ArabSeed Downloader

A web application for tracking and automatically downloading content from ArabSeed. Built with FastAPI, Next.js, and integrated with JDownloader for download management.

## Features

- 🔍 **Search**: Search ArabSeed for movies and TV series
- 📺 **Series Tracking**: Track series and automatically download new episodes
- 📥 **Automated Downloads**: Hourly checks for new episodes with auto-download
- 🎬 **Movie Support**: Download and organize movies
- 📁 **Automatic Organization**: Organize downloads into proper directory structures
- 🌐 **JDownloader Integration**: Uses JDownloader as download client
- 🐳 **Dockerized**: Complete Docker Compose setup for easy deployment
- 🎯 **Quality Selection**: Always downloads highest quality (720p)
- 🌍 **Multi-language**: Separate organization for English and Arabic content

## Architecture

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM with SQLite database
- **Celery** - Background task processing
- **Playwright** - Web scraping and automation
- **Redis** - Message broker for Celery

### Frontend
- **Next.js 14** - React framework with App Router
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - Modern UI component library
- **React Query** - Data fetching and state management

### Download Management
- **JDownloader** - Download client integration
- **Automatic File Organization** - Moves completed downloads to appropriate directories
- **Season/Episode Structure** - Creates proper directory hierarchy for series

## Prerequisites

- Docker and Docker Compose
- JDownloader installed and running (with API enabled)

## Deployment Options

### Standard Deployment

For regular Docker deployment, follow the Quick Start guide below.

### CasaOS Deployment

For CasaOS users, we provide a specialized setup:

```bash
# Clone and setup for CasaOS
git clone <repository-url>
cd arabseed_downloader
chmod +x setup-casaos.sh
./setup-casaos.sh

# Configure and start
docker-compose -f docker-compose.casaos.yml up -d
```

See [CASAOS_DEPLOYMENT.md](CASAOS_DEPLOYMENT.md) for detailed CasaOS setup instructions.

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd arabseed_downloader
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and configure:
   - `JDOWNLOADER_HOST`: JDownloader API host (use `host.docker.internal` for local)
   - `JDOWNLOADER_PORT`: JDownloader API port (default: 3129)
   - Directory paths for downloads and media

3. **Create required directories**
   ```bash
   mkdir -p downloads media/english-series media/arabic-series media/movies data
   ```

4. **Start the application**
   ```bash
   docker-compose up -d
   ```

5. **Access the application**
  - Frontend: http://localhost:3001
  - Backend API: http://localhost:8001
  - API Documentation: http://localhost:8001/docs

## JDownloader Setup

1. Install JDownloader
2. Enable the API:
   - Settings → Advanced Settings
   - Search for "API"
   - Enable "Remote API" and "Local API"
   - Set API port (default: 3129)

3. Test connection from Settings page in the web UI

## Usage

### Search and Track Content

1. Navigate to the **Search** page
2. Enter a movie or series name
3. Click on a result to view details
4. Select language (English/Arabic)
5. Click **Track** to add to your tracked items

### Manage Tracked Series

1. Go to **Tracked Items** page
2. View all tracked content
3. For series, click **Episodes** to see all episodes
4. Episodes are automatically checked hourly for new releases

### Monitor Downloads

1. Visit the **Downloads** page
2. View active, completed, and failed downloads
3. Monitor download progress in real-time
4. Retry failed downloads if needed

### Configure Settings

1. Go to **Settings** page
2. Configure JDownloader connection
3. Set directory paths for:
   - Download folder (temporary)
   - English series directory
   - Arabic series directory
   - Movies directory
4. Adjust episode check interval

## Directory Structure

```
arabseed_downloader/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── models.py        # Database models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── routers/         # API endpoints
│   │   ├── scraper/         # ArabSeed scraper
│   │   ├── services/        # Business logic
│   │   ├── tasks/           # Celery tasks
│   │   └── main.py          # FastAPI app
│   ├── Dockerfile
│   └── pyproject.toml       # Dependencies
├── frontend/                 # Next.js application
│   ├── app/                 # Pages and layouts
│   ├── components/          # React components
│   ├── lib/                 # Utilities and API client
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── research.md          # ArabSeed API research
├── docker-compose.yml       # Multi-container setup
└── README.md
```

## How It Works

### Episode Tracking Flow

1. **Track Series**: Add a series to your tracked items
2. **Episode Detection**: System fetches all available episodes from ArabSeed
3. **Hourly Checks**: Celery Beat triggers episode checks every hour
4. **New Episode Found**: When a new episode is detected:
   - Episode is added to database
   - Download URL is extracted using Playwright
   - Download is sent to JDownloader
5. **Download Monitoring**: Every 5 minutes, system checks JDownloader status
6. **File Organization**: When download completes:
   - File is moved to appropriate directory
   - Renamed with proper format: `Series Name - S01E05.mp4`
   - Organized in season folders

### Download Flow Details

The scraper navigates through ArabSeed's download flow:
1. Clicks 720p quality option
2. Selects "ArabSeed Direct Server"
3. Handles 15-second timers
4. Closes ad popups automatically
5. Extracts final download URL
6. Sends to JDownloader with proper destination

## API Endpoints

### Content Management
- `GET /api/search?query={query}` - Search ArabSeed
- `GET /api/tracked` - List tracked items
- `POST /api/tracked` - Add item to tracking
- `DELETE /api/tracked/{id}` - Remove tracking
- `GET /api/tracked/{id}/episodes` - Get series episodes

### Downloads
- `GET /api/downloads` - List downloads
- `POST /api/downloads/{episode_id}` - Trigger download
- `POST /api/downloads/{id}/retry` - Retry failed download

### Settings
- `GET /api/settings` - Get all settings
- `PUT /api/settings/{key}` - Update setting
- `POST /api/settings/jdownloader/test` - Test JDownloader connection

### Background Tasks
- `POST /api/tasks/check-new-episodes` - Force episode check
- `POST /api/tasks/sync-downloads` - Force download sync

## Configuration

### Environment Variables

Backend:
- `DATABASE_URL`: SQLite database path
- `REDIS_URL`: Redis connection URL
- `JDOWNLOADER_HOST`: JDownloader API host
- `JDOWNLOADER_PORT`: JDownloader API port
- `DOWNLOAD_FOLDER`: Temporary download directory
- `ENGLISH_SERIES_DIR`: English series final directory
- `ARABIC_SERIES_DIR`: Arabic series final directory
- `ENGLISH_MOVIES_DIR`: English movies final directory
- `ARABIC_MOVIES_DIR`: Arabic movies final directory
- `CHECK_INTERVAL_HOURS`: Episode check frequency (default: 1)
- `DOWNLOAD_SYNC_INTERVAL_MINUTES`: Download sync frequency (default: 5)

Frontend:
- `NEXT_PUBLIC_API_URL`: Backend API URL

## Development

### Backend Development

```bash
cd backend
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r pyproject.toml
playwright install chromium
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Run Celery Locally

```bash
# Worker
celery -A app.celery_app worker --loglevel=info

# Beat (scheduler)
celery -A app.celery_app beat --loglevel=info
```

## Troubleshooting

### JDownloader Connection Failed
- Ensure JDownloader is running
- Verify API is enabled in JDownloader settings
- Check `JDOWNLOADER_HOST` and `JDOWNLOADER_PORT` in `.env`
- For Docker, use `host.docker.internal` as host

### Episodes Not Auto-Downloading
- Check Celery Beat is running: `docker-compose logs celery_beat`
- Verify series is marked as "monitored"
- Check episode check logs: `docker-compose logs celery_worker`

### Downloads Not Organizing
- Verify directory permissions
- Check paths in Settings page match Docker volumes
- Review Celery worker logs: `docker-compose logs celery_worker`

### Playwright Issues
- Chromium browser installed: `playwright install chromium`
- For Docker: browser is installed in Dockerfile

## Security Considerations

- **No Authentication**: Designed for single-user home server deployment
- **Local Network**: Should be deployed behind firewall
- **CORS**: Configure `CORS_ORIGINS` for production deployment

## License

This project is for personal use. Respect ArabSeed's terms of service.

## Contributing

Issues and pull requests are welcome!

## Support

For issues or questions, please open a GitHub issue.
