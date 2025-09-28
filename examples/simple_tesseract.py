import sys
from pathlib import Path
from context_builder.acquisition import AcquisitionFactory
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))

# import logging
# logging.basicConfig(
#    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger(__name__)

tesseract = AcquisitionFactory.create("tesseract")

tesseract.languages = ["eng"]

file_path = Path("tests/assets/Award-after-Intent-to-Sole-Source-HF-Group.pdf")

result = tesseract.process(file_path)

console = Console()

console.print(result)
