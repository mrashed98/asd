# Docker Deployment Guide

This guide explains how to build, push, and deploy the ArabSeed Downloader using Docker.

## 🐳 Docker Images

The project consists of two main Docker images:

- **Backend**: `mrashed98/asd-backend` - FastAPI backend with Celery workers
- **Frontend**: `mrashed98/asd-frontend` - Next.js frontend application

## 🚀 Building and Pushing Images

### Prerequisites

1. **Docker Hub Account**: You need a Docker Hub account (mrashed98)
2. **Docker Login**: Login to Docker Hub first:
   ```bash
   docker login
   ```

### Build and Push Script

Use the provided script to build and push both images:

```bash
# Build and push with v1.0.0 tag (default)
./build_and_push.sh

# Build and push with specific version
./build_and_push.sh v1.1.0
```

This script will:
- Build both backend and frontend images
- Tag them with both `latest` and the specified version
- Push them to Docker Hub under the `mrashed98` user account

### Manual Build and Push

If you prefer to build manually:

```bash
# Build backend
docker build -t mrashed98/asd-backend:v1.0.0 -t mrashed98/asd-backend:latest ./backend

# Build frontend
docker build -t mrashed98/asd-frontend:v1.0.0 -t mrashed98/asd-frontend:latest \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8001 \
  ./frontend

# Push backend
docker push mrashed98/asd-backend:v1.0.0
docker push mrashed98/asd-backend:latest

# Push frontend
docker push mrashed98/asd-frontend:v1.0.0
docker push mrashed98/asd-frontend:latest
```

## 🏗️ Deployment Options

### Option 1: Development (Local Build)

Use the original `docker-compose.yml` for development:

```bash
docker-compose up -d
```

### Option 2: Production (Published Images)

Use `docker-compose.prod.yml` for production deployment:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 📋 Environment Variables

Create a `.env` file with the following variables:

```env
# JDownloader Configuration
JDOWNLOADER_HOST=host.docker.internal
JDOWNLOADER_PORT=3129

# My.JDownloader Credentials
MYJD_EMAIL=your-email@example.com
MYJD_PASSWORD=your-password
MYJD_DEVICE_NAME=your-device-name

# Download Paths
DOWNLOAD_FOLDER=./downloads
ENGLISH_SERIES_DIR=./media/english-series
ARABIC_SERIES_DIR=./media/arabic-series
ENGLISH_MOVIES_DIR=./media/english-movies
ARABIC_MOVIES_DIR=./media/arabic-movies

# Monitoring Intervals
CHECK_INTERVAL_HOURS=1
DOWNLOAD_SYNC_INTERVAL_MINUTES=5

# CORS Origins
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost"]
```

## 🔧 Services

The deployment includes the following services:

1. **Redis** - Message broker for Celery
2. **Backend** - FastAPI application
3. **Celery Worker** - Background task processor
4. **Celery Beat** - Task scheduler
5. **Frontend** - Next.js web interface

## 📊 Health Checks

All services include health checks:

- **Backend**: `http://localhost:8000/health`
- **Redis**: `redis-cli ping`
- **Frontend**: Built-in Next.js health check

## 🌐 Access Points

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## 📁 Volume Mounts

The following directories are mounted:

- `./data` → `/app/data` (Database and application data)
- `./downloads` → `/downloads` (Download directory)
- `./media/*` → `/media/*` (Organized media directories)

## 🔄 Updates

To update to a new version:

1. Pull the latest images:
   ```bash
   docker-compose -f docker-compose.prod.yml pull
   ```

2. Restart the services:
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

## 🐛 Troubleshooting

### Check Service Status
```bash
docker-compose -f docker-compose.prod.yml ps
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.prod.yml logs

# Specific service
docker-compose -f docker-compose.prod.yml logs backend
```

### Restart Services
```bash
docker-compose -f docker-compose.prod.yml restart
```

## 📝 Notes

- The backend image includes Playwright with Chromium for web scraping
- All services are configured with automatic restart policies
- The frontend is built with Next.js standalone output for optimal Docker performance
- Health checks ensure proper service dependencies and startup order
