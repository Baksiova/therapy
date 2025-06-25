#!/bin/bash

echo "=== CUSTOM STARTUP SCRIPT ==="
echo "Installing packages manually..."

# Manuální instalace packages
pip install Flask==3.0.3
pip install gunicorn==22.0.0  
pip install google-generativeai==0.8.2
pip install Flask-Cors==4.0.1

echo "Packages installed successfully!"
echo "Starting Gunicorn..."

# Spuštění aplikace
cd /home/site/wwwroot
gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout=600 server:app
