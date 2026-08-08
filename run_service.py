import sys
import os
from pathlib import Path

# Add project root directory to python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Force UTF-8 encoding for stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

if __name__ == "__main__":
    from backend.config import HOST, PORT
    import uvicorn

    print("==================================================")
    print("RoboticLive - Gemini 3.1 Live Service Starting")
    print(f"Server Running on: http://localhost:{PORT}")
    print("==================================================")

    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=True)
