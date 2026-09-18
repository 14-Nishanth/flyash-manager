import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Export Flask WSGI application for Vercel Serverless Function
from app import app

if __name__ == "__main__":
    app.run(debug=True)

