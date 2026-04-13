# MediAssist Deployment Guide

## Overview
This guide walks you through deploying MediAssist to Google Cloud Platform using Docker and Cloud Run.

## Prerequisites

Before you begin, ensure you have:

1. **Google Cloud Project** - Create one at [console.cloud.google.com](https://console.cloud.google.com)
2. **Google Cloud CLI** - Install from [cloud.google.com/sdk](https://cloud.google.com/sdk)
3. **Docker** - Install from [docker.com](https://www.docker.com)
4. **Gemini API Key** - Get from [Google AI Studio](https://aistudio.google.com/apikey)
5. **Billing Enabled** on your GCP project

## Step 1: Prepare Local Environment

### 1.1 Create `.env` file (local testing)

```bash
cp .env.example .env
```

Edit `.env` and add your values:
```env
GEMINI_API_KEY=your-actual-api-key
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
CHROMA_DB_PATH=./chroma_db
ENCRYPTION_KEY=your-secure-random-key-32-chars-min
```

> **Security Note**: Generate a secure encryption key using:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 1.2 Generate Encryption Key (Security)

```powershell
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_hex(32))" >> .env
```

## Step 2: Test Locally with Docker

### 2.1 Build and Run Locally

```bash
# Build the image
docker build -t mediassist:latest .

# Run the container
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your-key \
  -e MODEL_NAME=gemini-2.5-flash-lite \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -v $(pwd)/memory:/app/memory \
  mediassist:latest
```

Or use Docker Compose (recommended):

```bash
docker-compose up --build
```

### 2.2 Verify Local Deployment

- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Step 3: Deploy to Google Cloud Run

### 3.1 Authenticate with Google Cloud

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 3.2 Create Secret for Gemini API Key

```bash
gcloud secrets create GEMINI_API_KEY --replication-policy="automatic" --data-file=-
# Paste your API key and press Ctrl+D (or Cmd+D on Mac)

# Alternatively, create from environment variable
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --replication-policy="automatic" --data-file=-
```

### 3.3 Grant Cloud Run Permission to Access Secret

```bash
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
  --member="serviceAccount:YOUR_PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3.4 Build and Push to Container Registry

```bash
# Enable required services
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build using Cloud Build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mediassist:latest
```

### 3.5 Deploy to Cloud Run

```bash
gcloud run deploy mediassist \
  --image gcr.io/YOUR_PROJECT_ID/mediassist:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "MODEL_NAME=gemini-2.5-flash-lite,CHROMA_DB_PATH=/app/chroma_db" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --memory 1Gi \
  --cpu 2 \
  --timeout 3600 \
  --max-instances 100
```

### 3.6 Get Your Cloud Run URL

```bash
gcloud run services describe mediassist --region us-central1 --format="value(status.url)"
```

## Step 4: Setup Continuous Deployment (Optional but Recommended)

### 4.1 Enable Cloud Build Integration

```bash
# Connect your GitHub/GitLab repo to Cloud Build
gcloud builds connect --name mediassist
```

### 4.2 Create Build Trigger

In Google Cloud Console:
1. Go to **Cloud Build** → **Triggers**
2. Click **Create Trigger**
3. Connect your repository (GitHub, GitLab, or Bitbucket)
4. Configure:
   - **Name**: mediassist-deploy
   - **Event**: Push to branch
   - **Branch**: main
   - **Build Type**: Dockerfile
   - **Dockerfile location**: ./Dockerfile

### 4.3 Update Substitutions (for environment variables)

In **Build trigger settings**:
1. Add substitution variable:
   - **_GEMINI_API_KEY**: Your API key (or use Cloud Secrets)

## Step 5: Persist Data Volumes

Cloud Run has ephemeral storage. In the current codebase, `users.json`, `memory/`, `uploads/`, and `chroma_db/` are all local paths, so they will not be durable across instance restarts or scale-out events on Cloud Run.

For production use, move those paths to managed storage:

### 5.1 Use Cloud Storage (Recommended)

```bash
# Create a GCS bucket
gsutil mb gs://mediassist-data-${RANDOM}

# Enable Application Default Credentials in your app
# Update app.py to use Cloud Storage for chroma_db
```

### 5.2 Alternative: Use Cloud SQL for User Data

```bash
# Create Cloud SQL instance
gcloud sql instances create mediassist-db \
  --database-version MYSQL_8_0 \
  --tier db-f1-micro \
  --region us-central1
```

## Step 6: Monitor and Logs

### View Deployment Logs

```bash
gcloud run logs read mediassist --region us-central1 --limit 50
```

### Monitor in Real-time

```bash
gcloud run logs read mediassist --region us-central1 --follow
```

### Set Up Alerts (Optional)

In Google Cloud Console:
1. Go to **Monitoring** → **Create Policy**
2. Set conditions for error rates, CPU usage, etc.

## Step 7: Custom Domain (Optional)

```bash
# Add custom domain mapping
gcloud run domain-mappings create \
  --service=mediassist \
  --domain=yourapp.example.com \
  --region=us-central1

# Note: Update your DNS to point to the provided IP
```

## Troubleshooting

### Issue: Deployment fails with "Secret not found"

**Solution**: Ensure you created the secret and granted permissions:
```bash
gcloud secrets list
gcloud secrets get-iam-policy GEMINI_API_KEY
```

### Issue: Application crashes with API errors

**Solution**: Check logs:
```bash
gcloud run logs read mediassist --region us-central1 --limit 100
```

### Issue: Out of memory errors

**Solution**: Increase memory allocation:
```bash
gcloud run services update mediassist \
  --memory 2Gi \
  --region us-central1
```

### Issue: "403 Unauthenticated" errors

**Solution**: If you want to restrict access, remove `--allow-unauthenticated` and configure IAM.

## Cost Estimation

**Monthly costs (approximate)** with default settings:
- **Cloud Run**: $0.20-2.00 (depending on traffic)
- **Container Registry**: $0.10/GB (image storage)
- **Cloud Build**: Free tier covers 120 min/month
- **Cloud Storage** (if used): $0.02/GB

## Security Best Practices

1. ✅ Use Secret Manager for API keys
2. ✅ Enable VPC for private deployments
3. ✅ Set up IAM roles (least privilege)
4. ✅ Enable audit logging
5. ✅ Use HTTPS only (automatic with Cloud Run)
6. ✅ Rotate API keys periodically
7. ✅ Set resource limits (CPU, memory)
8. ✅ Monitor error rates and logs

## Quick Reference Commands

```bash
# Deploy latest version
gcloud builds submit --tag gcr.io/$PROJECT_ID/mediassist:latest

# See running service
gcloud run services list --region us-central1

# Check logs
gcloud run logs read mediassist --region us-central1 --limit 50

# Update environment variables
gcloud run services update mediassist --set-env-vars KEY=value --region us-central1

# Delete service
gcloud run services delete mediassist --region us-central1
```

## Support

For issues:
1. Check [Cloud Run Troubleshooting](https://cloud.google.com/run/docs/troubleshooting)
2. Review application logs: `gcloud run logs read mediassist --limit 100`
3. Test locally with docker-compose first

