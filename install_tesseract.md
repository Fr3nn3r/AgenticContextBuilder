# Installing Tesseract OCR on Windows

## Option 1: Using Chocolatey (Recommended if you have Chocolatey)

If you have Chocolatey package manager installed, run in an elevated PowerShell:
```powershell
choco install tesseract
```

## Option 2: Manual Installation

1. Download the Tesseract installer from the official GitHub releases:
   - Go to: https://github.com/UB-Mannheim/tesseract/wiki
   - Download the latest installer (e.g., `tesseract-ocr-w64-setup-5.3.3.20231005.exe`)

2. Run the installer:
   - During installation, note the installation path (usually `C:\Program Files\Tesseract-OCR`)
   - Make sure to install the language data files you need (at minimum, English)

3. Add Tesseract to your PATH:
   - Open System Properties → Advanced → Environment Variables
   - Add `C:\Program Files\Tesseract-OCR` to your PATH variable
   - OR set the path in your Python code:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

## Option 3: Using Scoop

If you have Scoop package manager:
```powershell
scoop install tesseract
```

## Verify Installation

After installation, restart your terminal and run:
```bash
tesseract --version
```

You should see version information if installed correctly.

## Test with Python

```python
import pytesseract
from PIL import Image

# If Tesseract is not in PATH, specify the path:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

try:
    # Simple test
    print(pytesseract.get_tesseract_version())
    print("Tesseract is working!")
except Exception as e:
    print(f"Error: {e}")
```

## Troubleshooting

1. **"TesseractNotFoundError"**: Tesseract is not installed or not in PATH
2. **Language errors**: Install additional language packs during Tesseract installation
3. **Permission errors**: Run installer as Administrator

## For AgenticContextBuilder

Once Tesseract is installed, the OCR extraction method will automatically become available in the content processor.