#!/bin/bash
# Quick deployment script for Medicine Recognition System

set -e

echo "========================================"
echo "Medicine Recognition System - Deployment Setup"
echo "========================================"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "1. Initializing Git repository..."
    git init
    git add .
    git commit -m "Initial commit: Medicine Recognition System"
    echo "   ✓ Git repository initialized"
else
    echo "✓ Git repository already initialized"
fi

echo ""
echo "2. Available deployment platforms:"
echo ""
echo "   A) Heroku (recommended for beginners)"
echo "   B) Railway (simpler setup, free tier)"
echo "   C) Render (easy GitHub integration)"
echo "   D) Manual (for your own server)"
echo ""
echo "Choose an option (A/B/C/D):"
read -r PLATFORM

case $PLATFORM in
    A|a)
        echo ""
        echo "=== Heroku Deployment Setup ==="
        echo ""
        echo "Prerequisites:"
        echo "  1. Create Heroku account at https://heroku.com"
        echo "  2. Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli"
        echo ""
        echo "Steps:"
        echo "  1. Login to Heroku:"
        echo "     heroku login"
        echo ""
        echo "  2. Create app:"
        echo "     heroku create your-app-name"
        echo ""
        echo "  3. Set environment variables:"
        echo "     heroku config:set GOOGLE_API_KEY=YOUR_API_KEY_HERE"
        echo "     heroku config:set GEMINI_MODEL=gemini-2.5-flash"
        echo "     heroku config:set GEMINI_FALLBACK=gemini-2.5-pro"
        echo ""
        echo "  4. Deploy:"
        echo "     git push heroku main"
        echo ""
        echo "  5. View logs:"
        echo "     heroku logs --tail"
        ;;
    B|b)
        echo ""
        echo "=== Railway Deployment Setup ==="
        echo ""
        echo "Steps:"
        echo "  1. Go to https://railway.app"
        echo "  2. Sign up with GitHub"
        echo "  3. Create new project from GitHub repository"
        echo "  4. Add environment variables:"
        echo "     - GOOGLE_API_KEY=YOUR_API_KEY_HERE"
        echo "     - GEMINI_MODEL=gemini-2.5-flash"
        echo "     - GEMINI_FALLBACK=gemini-2.5-pro"
        echo "  5. Railway auto-deploys on git push"
        ;;
    C|c)
        echo ""
        echo "=== Render Deployment Setup ==="
        echo ""
        echo "Steps:"
        echo "  1. Go to https://render.com"
        echo "  2. Sign up with GitHub"
        echo "  3. Create new Web Service from GitHub repo"
        echo "  4. Add environment variables:"
        echo "     - GOOGLE_API_KEY=YOUR_API_KEY_HERE"
        echo "     - GEMINI_MODEL=gemini-2.5-flash"
        echo "     - GEMINI_FALLBACK=gemini-2.5-pro"
        echo "  5. Deploy automatically"
        ;;
    D|d)
        echo ""
        echo "=== Manual Server Deployment ==="
        echo ""
        echo "Before running:"
        echo "  1. Copy the project to your server"
        echo "  2. Install dependencies:"
        echo "     pip install -r requirements.txt"
        echo ""
        echo "To run the app with environment variables:"
        echo ""
        echo "  Linux/Mac:"
        echo "    export GOOGLE_API_KEY=YOUR_API_KEY_HERE"
        echo "    export GEMINI_MODEL=gemini-2.5-flash"
        echo "    export GEMINI_FALLBACK=gemini-2.5-pro"
        echo "    python app.py"
        echo ""
        echo "  Windows CMD:"
        echo "    set GOOGLE_API_KEY=YOUR_API_KEY_HERE"
        echo "    set GEMINI_MODEL=gemini-2.5-flash"
        echo "    set GEMINI_FALLBACK=gemini-2.5-pro"
        echo "    python app.py"
        echo ""
        echo "  Windows PowerShell:"
        echo "    \$env:GOOGLE_API_KEY='YOUR_API_KEY_HERE'"
        echo "    \$env:GEMINI_MODEL='gemini-2.5-flash'"
        echo "    \$env:GEMINI_FALLBACK='gemini-2.5-pro'"
        echo "    python app.py"
        ;;
    *)
        echo "Invalid option. Please run again and choose A, B, C, or D."
        ;;
esac

echo ""
echo "========================================"
echo "For detailed instructions, see DEPLOYMENT.md"
echo "========================================"
