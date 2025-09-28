import sys
import os
from pathlib import Path
from context_builder.acquisition import AcquisitionFactory
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))

# import logging
# logging.basicConfig(
#    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
# )
# logger = logging.getLogger(__name__)

# Check API key
if not os.getenv("OPENAI_API_KEY"):
    print("Error: Set OPENAI_API_KEY environment variable")
    print("export OPENAI_API_KEY='your-key-here'")
    sys.exit(1)

openai_vision = AcquisitionFactory.create("openai")

file_path = Path("tests/assets/Award-after-Intent-to-Sole-Source-HF-Group.pdf")

result = openai_vision.process(file_path)

console = Console()

console.print(result)
