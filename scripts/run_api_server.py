"""
Launch FastAPI server for Extraction QA Console.

Usage:
    python scripts/run_api_server.py
    python scripts/run_api_server.py --port 8000 --data-dir output/claims-processed
    python scripts/run_api_server.py --reload  # Development mode with auto-reload
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Launch Extraction QA Console API server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run server on (default: 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("output/claims-processed"),
        help="Data directory with claim folders (default: output/claims-processed)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    args = parser.parse_args()

    # Validate data directory
    if not args.data_dir.exists():
        print(f"[!] Warning: Data directory not found: {args.data_dir}")
        print("    Server will start but no data will be available.")

    # Set data directory before importing app
    from context_builder.api.main import set_data_dir, app
    set_data_dir(args.data_dir)

    print(f"[OK] Data directory: {args.data_dir}")
    print(f"[OK] Starting server at http://{args.host}:{args.port}")
    print(f"[OK] API docs: http://{args.host}:{args.port}/docs")

    # Run server
    import uvicorn
    uvicorn.run(
        "context_builder.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
