# Deployment Guide

This guide helps you deploy the Medicine Recognition System and troubleshoot common deployment errors.

## Common Issues & Solutions

### Issue: Internal Server Error (500) After Deployment

**Root Cause:** Missing or misconfigured `GOOGLE_API_KEY` environment variable in production.

**Why it happens:**
- Local `.env` files are NOT automatically deployed to production
- The application cannot initialize the Gemini client without a valid API key
- Without proper error handling, this causes an unhandled exception and a 500 error

### Solution: Configure Environment Variables

The application needs the following environment variables set on your deployment platform:

#### Required Variables:
```
GOOGLE_API_KEY=your_actual_api_key_here
```

#### Optional Variables (with defaults):
```
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK=gemini-2.5-pro
HOST=0.0.0.0
PORT=5000
```

## Deployment Instructions by Platform

### Heroku

1. **Create a Heroku app** (if not already done)
   ```bash
   heroku create your-app-name
   ```

2. **Set environment variables**
   ```bash
   heroku config:set GOOGLE_API_KEY=your_actual_api_key_here
   heroku config:set GEMINI_MODEL=gemini-2.5-flash
   heroku config:set GEMINI_FALLBACK=gemini-2.5-pro
   ```

3. **Verify configuration**
   ```bash
   heroku config
   ```

4. **Deploy**
   ```bash
   git push heroku main
   ```

5. **View logs** (to check startup diagnostics)
   ```bash
   heroku logs --tail
   ```

### Railway

1. **Create a new project** from your GitHub repository

2. **Add environment variables:**
   - Go to the project settings
   - Add new variables:
     - `GOOGLE_API_KEY`: your_actual_api_key_here
     - `GEMINI_MODEL`: gemini-2.5-flash
     - `GEMINI_FALLBACK`: gemini-2.5-pro

3. **Deploy** - Railway auto-deploys from your GitHub repo

4. **View logs** - Check deployment logs to see startup diagnostics

### Render

1. **Create a new Web Service** from your GitHub repository

2. **Add environment variables** in the service settings:
   ```
   GOOGLE_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_FALLBACK=gemini-2.5-pro
   ```

3. **Deploy** - Render auto-deploys from your GitHub repo

4. **View logs** - Check deployment logs for startup diagnostics

### Docker / Local Server

For Docker or local server deployments, you MUST set environment variables before starting the app:

**Linux/Mac:**
```bash
export GOOGLE_API_KEY=your_actual_api_key_here
export GEMINI_MODEL=gemini-2.5-flash
export GEMINI_FALLBACK=gemini-2.5-pro
python app.py
```

**Windows (CMD):**
```cmd
set GOOGLE_API_KEY=your_actual_api_key_here
set GEMINI_MODEL=gemini-2.5-flash
set GEMINI_FALLBACK=gemini-2.5-pro
python app.py
```

**Windows (PowerShell):**
```powershell
$env:GOOGLE_API_KEY='your_actual_api_key_here'
$env:GEMINI_MODEL='gemini-2.5-flash'
$env:GEMINI_FALLBACK='gemini-2.5-pro'
python app.py
```

**Docker:**
```bash
docker build -t medicine-app .
docker run -e GOOGLE_API_KEY=your_actual_api_key_here \
           -e GEMINI_MODEL=gemini-2.5-flash \
           -e GEMINI_FALLBACK=gemini-2.5-pro \
           -p 5000:5000 medicine-app
```

## Troubleshooting

### Step 1: Check Startup Logs

When the app starts, it logs startup diagnostics. Look for lines like:

```
============================================================
STARTUP CONFIGURATION DIAGNOSTICS
============================================================
✓ Google API Key is configured (length: X)
✓ Primary model: gemini-2.5-flash
✓ Fallback model: gemini-2.5-pro
✓ Upload directory writable: /path/to/uploads
✓ google-genai package is available
============================================================
```

### Step 2: Verify API Key

If you see:
```
✗ Google API Key is NOT configured properly!
```

This means the environment variable is not set. Fix by:
1. Setting `GOOGLE_API_KEY` on your deployment platform
2. Redeploying or restarting the application

### Step 3: Check Dependencies

If you see:
```
✗ google-genai package NOT available
```

This means `requirements.txt` dependencies weren't installed. Ensure:
- Deployment platform runs `pip install -r requirements.txt`
- All packages are listed in `requirements.txt`

### Step 4: Verify Upload Directory

If you see:
```
✗ Upload directory not writable: /path/to/uploads
```

This might occur on read-only filesystems. Solutions:
- Use a temporary directory: `TMPDIR=/tmp python app.py`
- Use cloud storage (S3, Azure Blob) instead of local filesystem
- Ensure write permissions on the deploy platform

## Getting Your Google API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key (keep it private!)
4. Add it to your deployment platform's environment variables

## Testing Your Deployment

1. **Check app is running:**
   - Navigate to `https://your-app-url.com`
   - You should see the upload form

2. **Check logs for errors:**
   - Heroku: `heroku logs --tail`
   - Railway: Check logs in dashboard
   - Render: Check logs in dashboard

3. **Test image upload:**
   - Upload a medical image
   - Should see analysis or specific error messages (not generic 500)

4. **Common error messages and what they mean:**
   - "Gemini API is not configured" → Set `GOOGLE_API_KEY` env var
   - "Gemini model is unavailable" → Check model name in `GEMINI_MODEL`
   - "Quota or rate-limit exceeded" → Account needs higher usage tier
   - "Model temporarily unavailable" → Retry later (service issue)

## Need Help?

1. Check app logs for startup diagnostics
2. Verify `GOOGLE_API_KEY` is set on deployment platform
3. Ensure `requirements.txt` dependencies are installed
4. Test locally first with: `python app.py`
