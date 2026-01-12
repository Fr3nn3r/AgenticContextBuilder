@echo off
setlocal
set PYTHONPATH=src
python -m pytest -v -p no:tmpdir -o cache_dir=output\.pytest_cache %*
endlocal
