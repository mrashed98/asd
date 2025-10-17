# CasaOS Deployment Guide

This guide explains how to deploy the ArabSeed Downloader on CasaOS.

## Prerequisites

- CasaOS installed and running
- Docker and Docker Compose available
- JDownloader running with API enabled
- My.JDownloader account (optional, for remote access)

## Quick Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd arabseed_downloader
```

### 2. Run CasaOS Setup

```bash
chmod +x setup-casaos.sh
./setup-casaos.sh
```

### 3. Configure Environment

Edit the `.env` file with your settings:

```bash
nano .env
```

**Required Configuration:**
```env
# JDownloader Configuration
JDOWNLOADER_HOST=host.docker.internal
JDOWNLOADER_PORT=3129

# My.JDownloader Credentials (if using My.JDownloader)
MYJD_EMAIL=your_email@example.com
MYJD_PASSWORD=your_password
MYJD_DEVICE_NAME=your_device_name

# Directory Configuration (CasaOS paths)
DOWNLOAD_FOLDER=/DATA/AppData/arabseed_downloader/downloads
ENGLISH_SERIES_DIR=/DATA/Media/English-Series
ARABIC_SERIES_DIR=/DATA/Media/Arabic-Series
ENGLISH_MOVIES_DIR=/DATA/Media/English-Movies
ARABIC_MOVIES_DIR=/DATA/Media/Arabic-Movies

# CORS Configuration (update with your CasaOS IP/domain)
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost","http://casaos.local","http://192.168.1.100:3001"]
```

### 4. Start the Application

```bash
docker-compose -f docker-compose.casaos.yml up -d
```

### 5. Access the Application

- **Frontend**: `http://your-casaos-ip:3001`
- **API**: `http://your-casaos-ip:8001`

## Directory Structure

The application will create the following directory structure in CasaOS:

```
/DATA/
├── AppData/
│   └── arabseed_downloader/
│       ├── downloads/          # Temporary download location
│       └── data/               # Application database
└── Media/
    ├── English-Series/         # English TV series
    ├── Arabic-Series/          # Arabic TV series
    ├── English-Movies/         # English movies
    └── Arabic-Movies/          # Arabic movies
```

## CasaOS App Store Integration

To add this to CasaOS App Store, you can use the following configuration:

### App Store Configuration

```yaml
name: ArabSeed Downloader
description: Automated downloader for ArabSeed content with JDownloader integration
icon: https://raw.githubusercontent.com/your-repo/arabseed_downloader/main/icon.png
category: Media
developer: Your Name
version: 1.0.0
```

### Docker Compose for App Store

Use the `docker-compose.casaos.yml` file which includes:
- CasaOS-friendly directory paths
- Configurable environment variables
- Proper volume mounts for CasaOS structure

## Configuration Options

### Environment Variables

| Variable | Description | Default | CasaOS Example |
|----------|-------------|---------|----------------|
| `JDOWNLOADER_HOST` | JDownloader host | `host.docker.internal` | `host.docker.internal` |
| `JDOWNLOADER_PORT` | JDownloader port | `3129` | `3129` |
| `MYJD_EMAIL` | My.JDownloader email | - | `your@email.com` |
| `MYJD_PASSWORD` | My.JDownloader password | - | `password` |
| `MYJD_DEVICE_NAME` | My.JDownloader device name | - | `CasaOS` |
| `DOWNLOAD_FOLDER` | Download directory | `./downloads` | `/DATA/AppData/arabseed_downloader/downloads` |
| `ENGLISH_SERIES_DIR` | English series directory | `./media/english-series` | `/DATA/Media/English-Series` |
| `ARABIC_SERIES_DIR` | Arabic series directory | `./media/arabic-series` | `/DATA/Media/Arabic-Series` |
| `ENGLISH_MOVIES_DIR` | English movies directory | `./media/english-movies` | `/DATA/Media/English-Movies` |
| `ARABIC_MOVIES_DIR` | Arabic movies directory | `./media/arabic-movies` | `/DATA/Media/Arabic-Movies` |
| `CORS_ORIGINS` | CORS allowed origins | `["http://localhost:3000"]` | `["http://casaos.local:3001"]` |

### Volume Mounts

The CasaOS configuration mounts the following directories:

- **Application Data**: `/DATA/AppData/arabseed_downloader/` → Container data
- **Downloads**: `/DATA/AppData/arabseed_downloader/downloads` → Temporary downloads
- **Media**: `/DATA/Media/` → Organized media files

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   sudo chown -R 1000:1000 /DATA/AppData/arabseed_downloader/
   sudo chown -R 1000:1000 /DATA/Media/
   ```

2. **JDownloader Connection Failed**
   - Ensure JDownloader is running
   - Check if API is enabled in JDownloader settings
   - Verify `JDOWNLOADER_HOST` and `JDOWNLOADER_PORT`

3. **CORS Errors**
   - Update `CORS_ORIGINS` in `.env` with your CasaOS IP/domain
   - Restart the application after changes

4. **Directory Not Found**
   - Run the setup script: `./setup-casaos.sh`
   - Check if directories exist: `ls -la /DATA/AppData/arabseed_downloader/`

### Logs

View application logs:
```bash
# All services
docker-compose -f docker-compose.casaos.yml logs -f

# Specific service
docker-compose -f docker-compose.casaos.yml logs -f backend
docker-compose -f docker-compose.casaos.yml logs -f celery_worker
```

### Health Checks

Check service health:
```bash
# Backend health
curl http://localhost:8001/health

# Frontend health
curl http://localhost:3001

# Directory validation
curl http://localhost:8001/api/downloads/directories/validate
```

## Maintenance

### Updates

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.casaos.yml down
docker-compose -f docker-compose.casaos.yml build
docker-compose -f docker-compose.casaos.yml up -d
```

### Backup

```bash
# Backup database
cp /DATA/AppData/arabseed_downloader/data/arabseed.db /DATA/AppData/arabseed_downloader/data/arabseed.db.backup

# Backup configuration
cp .env .env.backup
```

### Cleanup

```bash
# Clean old downloads
find /DATA/AppData/arabseed_downloader/downloads -type f -mtime +7 -delete

# Clean Docker images
docker system prune -f
```

## Security Considerations

1. **Change Default Passwords**: Update My.JDownloader credentials
2. **Network Access**: Consider restricting CORS origins to your local network
3. **File Permissions**: Ensure proper file permissions for media directories
4. **Regular Updates**: Keep the application updated for security patches

## Support

For issues and support:
- Check the logs: `docker-compose -f docker-compose.casaos.yml logs`
- Validate directories: `curl http://localhost:8001/api/downloads/directories/validate`
- Check health status: `curl http://localhost:8001/api/downloads/tracking/health`
