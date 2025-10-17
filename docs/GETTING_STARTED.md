# Getting Started with ArabSeed Downloader

Welcome to ArabSeed Downloader! This guide will help you get up and running quickly.

## Table of Contents
- [What is ArabSeed Downloader?](#what-is-arabseed-downloader)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [First Run](#first-run)
- [Using the Application](#using-the-application)
- [Next Steps](#next-steps)

## What is ArabSeed Downloader?

ArabSeed Downloader is an automated content management system that:
- Searches ArabSeed for movies and TV series
- Tracks your favorite series and monitors for new episodes
- Automatically downloads new episodes when they're released
- Organizes your media library with proper naming and folder structure
- Works like Sonarr/Radarr but specifically for ArabSeed content

### Key Benefits
✅ **Automated** - Set it and forget it. New episodes download automatically  
✅ **Organized** - Files are automatically renamed and organized  
✅ **Simple** - Clean web interface, no complex configuration  
✅ **Reliable** - Built-in retry logic and error handling  
✅ **Fast** - Uses JDownloader for efficient downloading  

## Prerequisites

Before you begin, you need:

### 1. Docker Desktop
- **macOS**: [Download Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- **Windows**: [Download Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- **Linux**: [Install Docker Engine](https://docs.docker.com/engine/install/)

### 2. JDownloader
- Download from [jdownloader.org](https://jdownloader.org/download/index)
- Install and run JDownloader
- Keep it running in the background

## Installation

### Step 1: Get the Code

```bash
# Clone the repository
git clone <repository-url>
cd arabseed_downloader
```

### Step 2: Run Setup

```bash
# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

This will:
- Create necessary directories
- Copy environment template
- Build Docker images

### Step 3: Configure JDownloader API

1. Open JDownloader
2. Click **Settings** (gear icon)
3. Go to **Settings** → **Advanced Settings**
4. In the filter box, type: `API`
5. Enable these settings:
   - ✅ `RemoteAPIEnabled`
   - ✅ `LocalAPIEnabled`
6. Note the API port (default: 3129)

### Step 4: Edit Configuration

Edit the `.env` file in your project directory:

```bash
# For JDownloader running on the same machine
JDOWNLOADER_HOST=host.docker.internal
JDOWNLOADER_PORT=3129

# Your media directories (will be created if they don't exist)
DOWNLOAD_FOLDER=./downloads
ENGLISH_SERIES_DIR=./media/english-series
ARABIC_SERIES_DIR=./media/arabic-series
ENGLISH_MOVIES_DIR=./media/english-movies
ARABIC_MOVIES_DIR=./media/arabic-movies

# How often to check for new episodes (in hours)
CHECK_INTERVAL_HOURS=1
```

### Step 5: Start the Application

```bash
docker-compose up -d
```

Wait about 30 seconds for all services to start.

### Step 6: Verify Installation

Open your web browser and go to:
- **Main App**: http://localhost:3001
- **API Documentation**: http://localhost:8001/docs

You should see the ArabSeed Downloader interface.

## First Run

### 1. Test JDownloader Connection

1. Navigate to **Settings** page (top navigation)
2. Click **Test Connection** button
3. You should see: ✅ "Successfully connected to JDownloader"

**If connection fails:**
- Ensure JDownloader is running
- Verify API is enabled (see Step 3 above)
- Check the port matches in `.env` file

### 2. Search for Content

Let's try searching for a series:

1. Go to **Search** page (home)
2. Type "High Potential" in the search box
3. Click **Search**
4. You should see search results

### 3. Track Your First Series

1. Click on a series from the search results
2. A dialog appears with details
3. Select **Language**: English or Arabic
4. Click **Track**

The series is now being monitored!

### 4. View Episodes

1. Go to **Tracked Items** page
2. Find your series and click **Episodes**
3. You'll see all available episodes grouped by season

### 5. Download an Episode

1. On the Episodes page, find an episode
2. Click **Download** button
3. The download will be sent to JDownloader
4. Go to **Downloads** page to monitor progress

### 6. Check Automatic Organization

Once the download completes (after a few minutes):
1. Check your media directory:
   ```bash
   ls -la media/english-series/
   ```
2. You should see the series folder with proper structure:
   ```
   High Potential/
   └── Season 01/
       └── High Potential - S01E05.mp4
   ```

## Using the Application

### Search Page (/)
**Purpose**: Find content on ArabSeed

**How to use**:
1. Enter movie or series name
2. Click Search
3. Click on results to view details
4. Track items you want to monitor

### Tracked Items (/tracked)
**Purpose**: Manage your tracked content

**Features**:
- View all tracked movies and series
- See episode counts
- Access episode lists
- Remove items from tracking
- Force check for updates

### Episodes (/tracked/[id]/episodes)
**Purpose**: View and download specific episodes

**Features**:
- Episodes grouped by season
- Download status indicators
- Manual download buttons
- Season-by-season organization

### Downloads (/downloads)
**Purpose**: Monitor download progress

**Features**:
- Real-time progress updates
- Download status (pending/in progress/completed/failed)
- Retry failed downloads
- Filter by status

**Note**: This page auto-refreshes every 5 seconds

### Settings (/settings)
**Purpose**: Configure the application

**Settings**:
- **JDownloader**: Connection details
- **Directories**: Where to save files
- **Check Interval**: How often to check for new episodes

## Understanding Automatic Downloads

### How It Works

1. **You track a series** → All episodes are detected and stored
2. **Every hour** (configurable) → System checks for new episodes
3. **New episode found** → Download automatically starts
4. **Download completes** → File is moved and organized
5. **Database updated** → Episode marked as downloaded

### Checking Logs

To see what's happening:
```bash
# All services
docker-compose logs -f

# Just the worker (handles downloads)
docker-compose logs -f celery_worker

# Just the scheduler (triggers checks)
docker-compose logs -f celery_beat
```

### Manual Triggers

Don't want to wait for automatic checks?

**Check for new episodes now**:
```bash
make check-episodes
# or
curl -X POST http://localhost:8001/api/tasks/check-new-episodes
```

**Sync downloads now**:
```bash
make sync-downloads
# or
curl -X POST http://localhost:8001/api/tasks/sync-downloads
```

## File Organization

The system organizes your files automatically:

### Series (English)
```
./media/english-series/
├── Breaking Bad/
│   ├── Season 01/
│   │   ├── Breaking Bad - S01E01.mp4
│   │   ├── Breaking Bad - S01E02.mp4
│   │   └── ...
│   └── Season 02/
│       └── ...
└── Game of Thrones/
    └── ...
```

### Series (Arabic)
```
./media/arabic-series/
└── [Same structure as English]
```

### Movies (English)
```
./media/english-movies/
├── The Dark Knight (2008).mp4
├── Inception (2010).mp4
└── ...
```

### Movies (Arabic)
```
./media/arabic-movies/
├── [Arabic Movie Title] (2023).mp4
├── [Another Arabic Movie] (2022).mp4
└── ...
```

## Tips and Best Practices

### 1. Start Small
- Track 1-2 series first
- Ensure everything works
- Then add more content

### 2. Monitor Disk Space
- Downloads can be large (1-2GB per episode)
- Check available space regularly
- Clean up old downloads

### 3. Regular Maintenance
```bash
# Check status
docker-compose ps

# View logs if issues occur
docker-compose logs -f

# Restart if needed
docker-compose restart
```

### 4. Backup Your Database
```bash
# Backup database
cp data/arabseed.db data/arabseed.db.backup
```

### 5. Update Check Interval

For testing, use shorter intervals:
```env
CHECK_INTERVAL_HOURS=1  # Check every hour
```

For production with many series:
```env
CHECK_INTERVAL_HOURS=6  # Check every 6 hours
```

## Common Commands

```bash
# Start application
docker-compose up -d

# Stop application
docker-compose down

# View logs
docker-compose logs -f

# Restart services
docker-compose restart

# Check service status
docker-compose ps

# Clean up everything (WARNING: Deletes data!)
docker-compose down -v
rm -rf data/ downloads/* media/*
```

## Troubleshooting

### Application Not Starting
```bash
# Check Docker is running
docker --version

# Check service status
docker-compose ps

# View error logs
docker-compose logs
```

### Can't Access Web Interface
- Ensure you're using http://localhost:3001
- Check if port 3000 is already in use
- Try restarting: `docker-compose restart frontend`

### JDownloader Not Connecting
1. Verify JDownloader is running
2. Check API is enabled in settings
3. Test manually:
   ```bash
   curl http://localhost:3129/system/getSystemInfos
   ```

### Downloads Not Starting
1. Check JDownloader connection in Settings
2. View worker logs: `docker-compose logs celery_worker`
3. Ensure episode is marked as "monitored"
4. Try manual download first

### Files Not Organizing
1. Check directory permissions
2. Verify paths in Settings match Docker volumes
3. View worker logs for errors
4. Ensure download completed in JDownloader

## Next Steps

Now that you're set up:

1. **Track some series** - Add your favorite shows
2. **Configure settings** - Adjust check intervals
3. **Monitor downloads** - Watch the Downloads page
4. **Check your media** - Verify files are organizing correctly
5. **Read the docs** - Explore TESTING.md and ARCHITECTURE.md

## Getting Help

- **Documentation**: See README.md for full details
- **Testing Guide**: See TESTING.md for troubleshooting
- **Architecture**: See ARCHITECTURE.md for technical details
- **Logs**: Always check logs first: `docker-compose logs -f`

## Stopping the Application

To stop all services:
```bash
docker-compose down
```

To stop and remove all data (WARNING: This deletes everything!):
```bash
docker-compose down -v
rm -rf data/ downloads/* media/*
```

---

**Welcome aboard!** 🚀

You're now ready to use ArabSeed Downloader. Happy downloading!

If you run into any issues, check the logs first, then consult the TESTING.md guide for detailed troubleshooting steps.

