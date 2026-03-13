# Official BMF Form Templates

Place official Austrian BMF tax form PDFs here for template-based filling.

## Supported Templates

- `E1_2024.pdf` - Einkommensteuererklärung 2024
- `E1.pdf` - Einkommensteuererklärung (any year)
- `L1_2024.pdf` - Arbeitnehmerveranlagung 2024
- `L1.pdf` - Arbeitnehmerveranlagung (any year)

## How to Download

1. Go to https://service.bmf.gv.at/service/anwend/formulare/show_mast.asp
2. Search for "E1" or "L1"
3. Download the PDF form
4. Save it here as `E1_2024.pdf` (or the appropriate year)

## How It Works

When a template is available, Taxja will:
1. Try to fill AcroForm fields (if the PDF has fillable fields)
2. Fall back to overlaying text at known KZ positions
3. If no template exists, generate a custom PDF that replicates the form layout

## Calibration

To calibrate KZ positions for a new template:

```bash
cd backend
python -c "from app.services.e1_template_filler import calibrate_template; calibrate_template('app/templates/E1_2024.pdf')"
```
