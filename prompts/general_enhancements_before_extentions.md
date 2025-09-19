scripts/extract_datasets_metadata.py 

let's make improvements:

Refactor into a tiny package
file_ingest/
  __init__.py
  cli.py            # argument parsing + logging config
  ingest.py        # core funcs (hashing, metadata, processing)
  schemas.py        # JSON schemas (if you keep them here)
  utils.py
tests/


the goal is to make this tool extensible, we want the ability to add new processing functions, WITHOUT impacting the existing code, e.g. in the future I may want to add an enrichement processing that will add more information to the metadata depending on the file or the configuration. This must be supported by our code.

replace occurences of "extraction" by "ingestion" in the code and the output files since it is more accurate.



