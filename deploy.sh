#!/bin/bash
# MediAssist Google Cloud Deployment Script
# This script automates the deployment to Google Cloud Run

set -e

PROJECT_ID="${1:-}"
GEMINI_API_KEY="${2:-}"
REGION="${3:-us-central1}"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: ./deploy.sh <PROJECT_ID> <GEMINI_API_KEY> [REGION]"
    echo "Example: ./deploy.sh my-project abc123xyz us-central1"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY is required"
    exit 1
fi

echo "========================================"
echo "MediAssist Deployment to Google Cloud"
echo "========================================"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Step 1: Set project
echo "[1/7] Setting Google Cloud project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable services
echo "[2/7] Enabling required services..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Step 3: Create secret
echo "[3/7] Creating secret for GEMINI_API_KEY..."
if gcloud secrets describe GEMINI_API_KEY &>/dev/null; then
    echo "  Secret already exists, updating..."
    echo -n "$GEMINI_API_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=-
else
    echo "  Creating new secret..."
    echo -n "$GEMINI_API_KEY" | gcloud secrets create GEMINI_API_KEY --replication-policy="automatic" --data-file=-
fi

# Step 4: Grant permissions
echo "[4/7] Granting Cloud Run service account access to secret..."
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet 2>/dev/null || true

# Step 5: Build image
echo "[5/7] Building Docker image with Cloud Build..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/mediassist:latest

# Step 6: Deploy to Cloud Run
echo "[6/7] Deploying to Cloud Run..."
gcloud run deploy mediassist \
    --image gcr.io/$PROJECT_ID/mediassist:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars "MODEL_NAME=gemini-2.5-flash-lite,CHROMA_DB_PATH=/app/chroma_db" \
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --memory 1Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 100

# Step 7: Get URL
echo "[7/7] Getting service URL..."
SERVICE_URL=$(gcloud run services describe mediassist --region $REGION --format="value(status.url)")

echo ""
echo "========================================"
echo "✅ Deployment Complete!"
echo "========================================"
echo ""
echo "Service URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "  • Web UI: $SERVICE_URL"
echo "  • API Docs: $SERVICE_URL/docs"
echo "  • Health: $SERVICE_URL/api/health"
echo ""
echo "View logs:"
echo "  gcloud run logs read mediassist --region $REGION --limit 50"
echo ""
echo "Update anytime with:"
echo "  gcloud builds submit --tag gcr.io/$PROJECT_ID/mediassist:latest"
echo ""
