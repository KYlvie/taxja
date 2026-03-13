# Tesseract OCR Setup Guide

This guide explains how to install and configure Tesseract 5.0+ with German and English language support for the Taxja OCR engine.

## Installation

### Windows

1. Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (tesseract-ocr-w64-setup-5.x.x.exe)
3. During installation, make sure to select:
   - German language pack (deu)
   - English language pack (eng)
4. Default installation path: `C:\Program Files\Tesseract-OCR\`
5. Add Tesseract to PATH or configure in `ocr_config.py`

### Linux (Ubuntu/Debian)

```bash
# Install Tesseract 5.0+
sudo apt update
sudo apt install tesseract-ocr

# Install German and English language packs
sudo apt install tesseract-ocr-deu tesseract-ocr-eng

# Verify installation
tesseract --version
tesseract --list-langs
```

### macOS

```bash
# Install via Homebrew
brew install tesseract
brew install tesseract-lang

# Verify installation
tesseract --version
tesseract --list-langs
```

### Docker

The Dockerfile already includes Tesseract installation:

```dockerfile
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
```

## Verification

After installation, verify that German and English language packs are available:

```bash
tesseract --list-langs
```

Expected output should include:
```
List of available languages (2):
deu
eng
```

## Configuration

The OCR engine is configured in `backend/app/core/ocr_config.py`:

- **OCR Engine Mode (OEM)**: 3 (Default, LSTM + Legacy)
- **Page Segmentation Mode (PSM)**: 6 (Uniform block of text)
- **Languages**: German (deu) + English (eng)
- **Confidence Threshold**: 0.6 (60%)

## Testing

Test Tesseract with a sample image:

```bash
# Test with German text
tesseract sample_receipt.jpg output -l deu+eng

# View output
cat output.txt
```

## Troubleshooting

### "Tesseract not found" error

- **Windows**: Ensure Tesseract is in PATH or set `TESSERACT_CMD` environment variable
- **Linux/Mac**: Install via package manager as shown above

### Language pack not found

```bash
# Check installed languages
tesseract --list-langs

# Install missing language packs
# Ubuntu/Debian:
sudo apt install tesseract-ocr-deu tesseract-ocr-eng

# macOS:
brew reinstall tesseract-lang
```

### Poor OCR accuracy

- Ensure image quality is good (300 DPI recommended)
- Use image preprocessing (contrast enhancement, deskewing)
- Check that correct language is specified

## Performance Optimization

For production environments:

1. **Use LSTM mode only** (OEM 1) for better accuracy on modern documents
2. **Adjust PSM** based on document type:
   - PSM 3: Fully automatic page segmentation
   - PSM 6: Uniform block of text (default for receipts)
   - PSM 11: Sparse text (for invoices with tables)
3. **Enable parallel processing** with Celery for batch operations

## Austrian Document Specifics

The OCR engine is optimized for Austrian documents:

- **Date format**: DD.MM.YYYY
- **Currency**: € (Euro symbol)
- **Decimal separator**: Comma (1.234,56)
- **Common terms**: Brutto, Netto, USt, Lohnsteuer, etc.
- **Merchants**: BILLA, SPAR, HOFER, LIDL, MERKUR, OBI

## References

- Tesseract Documentation: https://tesseract-ocr.github.io/
- Language Data: https://github.com/tesseract-ocr/tessdata
- Austrian Tax Terms: See `docs/austrian_tax_glossary.md`

