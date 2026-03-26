# MediAssist Google Cloud Deployment Script (PowerShell)
# This script automates the deployment to Google Cloud Run

param(
    [string]$ProjectId = "",
    [string]$GeminiApiKey = "",
    [string]$Region = "us-central1"
)

if (-not $ProjectId) {
    Write-Host "Usage: .\deploy.ps1 -ProjectId <PROJECT_ID> -GeminiApiKey <API_KEY> [-Region <REGION>]" -ForegroundColor Red
    Write-Host "Example: .\deploy.ps1 -ProjectId my-project -GeminiApiKey abc123xyz -Region us-central1" -ForegroundColor Yellow
    exit 1
}

if (-not $GeminiApiKey) {
    Write-Host "Error: GeminiApiKey is required" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MediAssist Deployment to Google Cloud" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project ID: $ProjectId"
Write-Host "Region: $Region"
Write-Host ""

# Step 1: Set project
Write-Host "[1/7] Setting Google Cloud project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

# Step 2: Enable services
Write-Host "[2/7] Enabling required services..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Step 3: Create secret
Write-Host "[3/7] Creating secret for GEMINI_API_KEY..." -ForegroundColor Yellow
try {
    gcloud secrets describe GEMINI_API_KEY 2>$null | Out-Null
    Write-Host "  Secret already exists, updating..." -ForegroundColor Green
    $GeminiApiKey | gcloud secrets versions add GEMINI_API_KEY --data-file=-
} catch {
    Write-Host "  Creating new secret..." -ForegroundColor Green
    $GeminiApiKey | gcloud secrets create GEMINI_API_KEY --replication-policy="automatic" --data-file=-
}

# Step 4: Grant permissions
Write-Host "[4/7] Granting Cloud Run service account access to secret..." -ForegroundColor Yellow
$ServiceAccount = "$ProjectId@appspot.gserviceaccount.com"
gcloud secrets add-iam-policy-binding GEMINI_API_KEY `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/secretmanager.secretAccessor" `
    --quiet 2>$null | Out-Null

# Step 5: Build image
Write-Host "[5/7] Building Docker image with Cloud Build..." -ForegroundColor Yellow
gcloud builds submit --tag "gcr.io/$ProjectId/mediassist:latest"

# Step 6: Deploy to Cloud Run
Write-Host "[6/7] Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy mediassist `
    --image "gcr.io/$ProjectId/mediassist:latest" `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --set-env-vars "MODEL_NAME=gemini-2.5-flash-lite,CHROMA_DB_PATH=/app/chroma_db" `
    --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" `
    --memory 1Gi `
    --cpu 2 `
    --timeout 3600 `
    --max-instances 100

# Step 7: Get URL
Write-Host "[7/7] Getting service URL..." -ForegroundColor Yellow
$ServiceUrl = gcloud run services describe mediassist --region $Region --format="value(status.url)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service URL: $ServiceUrl"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  • Web UI: $ServiceUrl"
Write-Host "  • API Docs: $ServiceUrl/docs"
Write-Host "  • Health: $ServiceUrl/api/health"
Write-Host ""
Write-Host "View logs:" -ForegroundColor Cyan
Write-Host "  gcloud run logs read mediassist --region $Region --limit 50"
Write-Host ""
Write-Host "Update anytime with:" -ForegroundColor Cyan
Write-Host "  gcloud builds submit --tag gcr.io/$ProjectId/mediassist:latest"
Write-Host ""
