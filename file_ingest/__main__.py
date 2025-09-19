# file_ingest/__main__.py
# Entry point for running the file ingestion package as a module
# Allows execution via: python -m file_ingest

from .cli import main

if __name__ == '__main__':
    exit(main())