# Quick Start Guide

This guide will get you up and running with ArabSeed Downloader in under 5 minutes.

## Prerequisites

1. **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
2. **JDownloader** - [Download JDownloader](https://jdownloader.org/download)

## Step 1: Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd arabseed_downloader

# Run setup script
chmod +x setup.sh
./setup.sh
```

## Step 2: Configure JDownloader

1. Open JDownloader
2. Go to **Settings** → **Advanced Settings**
3. Search for "API" in the filter
4. Enable these options:
   - `RemoteAPIEnabled` → ✓
   - `LocalAPIEnabled` → ✓
5. Note the API port (default: 3129)

## Step 3: Configure Environment

Edit the `.env` file:

```bash
# For JDownloader running on your host machine
JDOWNLOADER_HOST=host.docker.internal
JDOWNLOADER_PORT=3129

# Set your preferred directories
DOWNLOAD_FOLDER=./downloads
ENGLISH_SERIES_DIR=./media/english-series
ARABIC_SERIES_DIR=./media/arabic-series
ENGLISH_MOVIES_DIR=./media/english-movies
ARABIC_MOVIES_DIR=./media/arabic-movies
```

## Step 4: Start the Application

```bash
docker-compose up -d
```

Wait for all services to start (about 30 seconds).

## Step 5: Access the Application

Open your browser and navigate to:
- **Web App**: http://localhost:3001
- **API Docs**: http://localhost:8001/docs

## Step 6: First Use

### Test JDownloader Connection

1. Go to **Settings** page
2. Click **Test Connection**
3. You should see "Successfully connected to JDownloader"

### Search for Content

1. Go to **Search** page
2. Try searching for "High Potential" (series) or "Bad Man" (movie)
3. Click on a result
4. Select language (English/Arabic)
5. Click **Track**

### Monitor Downloads

1. For series, go to **Tracked Items** → Click **Episodes**
2. Click **Download** on any episode
3. Go to **Downloads** page to monitor progress
4. Downloads will automatically organize to the configured directories

## Useful Commands

```bash
# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Restart services
docker-compose restart

# Check service status
docker-compose ps

# Manually trigger episode check
make check-episodes

# Or use curl:
curl -X POST http://localhost:8001/api/tasks/check-new-episodes
```

## Troubleshooting

### "Cannot connect to JDownloader"

**Solution:**
1. Ensure JDownloader is running
2. Verify API is enabled in JDownloader settings
3. Check the port matches in `.env`
4. Use `host.docker.internal` as host in Docker environment

### Episodes not auto-downloading

**Solution:**
1. Check if series is monitored: **Tracked Items** page
2. View Celery logs: `docker-compose logs celery_worker`
3. Manually trigger check: `make check-episodes`

### Downloads not organizing

**Solution:**
1. Check directory permissions
2. Verify paths in **Settings** page
3. View Celery worker logs: `docker-compose logs celery_worker`

### Frontend can't connect to backend

**Solution:**
1. Check all services are running: `docker-compose ps`
2. Verify backend health: `curl http://localhost:8001/health`
3. Check CORS settings in backend

## Next Steps

- Configure automatic episode checking interval in **Settings**
- Track your favorite series
- Monitor the **Downloads** page for progress
- Check organized files in your configured media directories

## Need Help?

- Check the full [README.md](README.md) for detailed documentation
- Review logs: `docker-compose logs -f`
- Open an issue on GitHub

Enjoy your automated content management! 🎬

