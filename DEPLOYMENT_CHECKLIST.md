# MediAssist Deployment Checklist

## Pre-Deployment Setup

### Google Cloud Account Setup
- [ ] Create Google Cloud Project at [console.cloud.google.com](https://console.cloud.google.com)
- [ ] Enable billing for the project
- [ ] Note down your **Project ID** (you'll need this)

### Local Machine Setup
- [ ] Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
- [ ] Install Docker Desktop: https://www.docker.com/products/docker-desktop
- [ ] Get your Gemini API Key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- [ ] Authenticate with Google Cloud:
  ```bash
  gcloud auth login
  gcloud config set project YOUR_PROJECT_ID
  ```

### Repository Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Add your **GEMINI_API_KEY** to `.env`
- [ ] Generate **ENCRYPTION_KEY** (see DEPLOYMENT.md)
- [ ] Commit all files to your git repository (optional but recommended)

---

## Testing Phase

### Local Docker Testing
- [ ] Test locally with Docker Compose:
  ```bash
  docker-compose up --build
  ```
- [ ] Verify application at `http://localhost:8000`
- [ ] Test API docs at `http://localhost:8000/docs`
- [ ] Test health check at `http://localhost:8000/api/health`
- [ ] Test signup functionality
- [ ] Test at least one triage query
- [ ] Stop all local containers: `docker-compose down`

---

## Deployment Phase (Choose One)

### Option A: Automated Deployment (Recommended)

#### For Windows PowerShell:
```powershell
# First time: Set execution policy if needed
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run the deployment script
.\deploy.ps1 -ProjectId YOUR_PROJECT_ID -GeminiApiKey YOUR_API_KEY -Region us-central1
```

#### For Linux/Mac Bash:
```bash
chmod +x deploy.sh
./deploy.sh YOUR_PROJECT_ID YOUR_API_KEY us-central1
```

### Option B: Manual Deployment

Follow the steps in [DEPLOYMENT.md](DEPLOYMENT.md) - Section 3 onwards.

---

## Post-Deployment Verification

### Verify Deployment Success
- [ ] Get your service URL from deployment output
- [ ] Open the Web UI in browser: `https://your-service-url`
- [ ] Check health endpoint: `https://your-service-url/api/health`
- [ ] Verify API docs: `https://your-service-url/docs`

### Test Application Features
- [ ] Test user signup
- [ ] Test symptom triage
- [ ] Test emergency keyword detection
- [ ] Verify logs appear in Cloud Run console

### Check Cloud Run Status
```bash
gcloud run services describe mediassist --region us-central1
gcloud run logs read mediassist --region us-central1 --limit 20
```

---

## Environment Variables Configured

The following environment variables are automatically set during deployment:

- ✅ `GEMINI_API_KEY` - From Cloud Secret
- ✅ `MODEL_NAME=gemini-2.5-flash-lite`
- ✅ `CHROMA_DB_PATH=/app/chroma_db`
- ✅ `PORT=8000`

---

## Monitoring & Maintenance

### Daily Operations
- [ ] Monitor error rates in Cloud Run console
- [ ] Check logs for any errors: 
  ```bash
  gcloud run logs read mediassist --region us-central1 --limit 50
  ```

### Weekly Tasks
- [ ] Review cost estimates in Cloud Billing
- [ ] Check API quota usage
- [ ] Monitor application performance metrics

### Monthly Tasks
- [ ] Rotate API keys (update in Cloud Secrets)
- [ ] Review access logs and security
- [ ] Update dependencies in requirements.txt if needed

### Deployment Updates
To deploy updated code:
```bash
# Option 1: Using automated script
.\deploy.ps1 -ProjectId YOUR_PROJECT_ID -GeminiApiKey YOUR_API_KEY

# Option 2: Manual build and deploy
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mediassist:latest
gcloud run deploy mediassist --image gcr.io/YOUR_PROJECT_ID/mediassist:latest --region us-central1
```

---

## Cost Management

### Current Configuration Costs
| Service | Estimate | Notes |
|---------|----------|-------|
| Cloud Run | $0.20-2.00/mo | 1 vCPU, 1GB RAM, pay-per-use |
| Container Registry | $0.10/GB | Image storage |
| Cloud Build | Free | 120 min/month free tier |
| **Total** | **$0.30-2.10/mo** | Varies with traffic |

### Cost Optimization
- Cloud Run automatically scales to 0 when unused
- Consider setting `--max-instances` lower if needed
- Monitor metrics dashboard regularly
- Set up budget alerts:
  ```bash
  gcloud billing budgets create --billing-account=YOUR_ACCOUNT_ID
  ```

---

## Troubleshooting

### Common Issues & Solutions

**Issue**: Deployment fails with "Secret not found"
```bash
# Solution: Verify secret exists
gcloud secrets list
# If missing, create it:
echo "YOUR_API_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=-
```

**Issue**: Application returns 500 error
```bash
# Solution: Check logs
gcloud run logs read mediassist --region us-central1 --limit 100
```

**Issue**: Out of memory errors
```bash
# Solution: Increase memory
gcloud run services update mediassist --memory 2Gi --region us-central1
```

**Issue**: High latency or timeouts
```bash
# Solution: Check and increase CPU or instance count
gcloud run services update mediassist --cpu 4 --max-instances 50 --region us-central1
```

---

## Next Steps After Deployment

1. ✅ **Setup Custom Domain** (Optional)
   - Purchase domain from registrar
   - Follow Cloud Run custom domain guide

2. ✅ **Setup HTTPS/SSL** (Automatic)
   - Cloud Run automatically provides HTTPS

3. ✅ **Setup Monitoring Alerts** (Recommended)
   - Create alerts for high error rates
   - Set up notifications for deployment failures

4. ✅ **Enable CI/CD** (Optional)
   - Connect GitHub/GitLab to Cloud Build
   - Auto-deploy on push to main branch

5. ✅ **Backup Strategy** (Recommended)
   - Configure Cloud Storage for data backups
   - Setup Firestore for persistent user data

---

## Support & Documentation

- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Troubleshooting**: https://cloud.google.com/run/docs/troubleshooting
- **Pricing**: https://cloud.google.com/run/pricing
- **MediAssist README**: [README.md](README.md)
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Rollback Procedures

If something goes wrong after deployment:

```bash
# View previous versions
gcloud run revisions list

# Route traffic back to previous version
gcloud run services update-traffic mediassist --to-revisions REVISION_NAME=100

# Delete current version
gcloud run revisions delete REVISION_NAME --region us-central1
```

---

**Last Updated**: March 24, 2026
**MediAssist Version**: 3.0+
