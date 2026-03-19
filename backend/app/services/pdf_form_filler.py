"""PDF Form Filler Service — fills official BMF tax form PDFs with user data.

Reads a blank PDF template from DB (TaxFormTemplate), maps our computed
Kennzahl values to PDF AcroForm field names via the stored field_mapping,
and returns a filled PDF as bytes.

Dependencies: pdfrw (for AcroForm manipulation without Adobe)
Fallback: PyPDF2 (if pdfrw unavailable)

Usage:
    filled_pdf = fill_tax_form_pdf(db, form_type="E1", tax_year=2025, form_data=data)
    # form_data is the dict returned by e1_form_service.generate_tax_form_data() etc.
"""
import io
import logging
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.tax_form_template import TaxFormTemplate, TaxFormType

logger = logging.getLogger(__name__)


class PDFFillerError(Exception):
    """Raised when PDF filling fails."""
    pass


class TemplateNotFoundError(PDFFillerError):
    """No template in DB for the requested form_type + tax_year."""
    pass


class PDFLibraryNotAvailable(PDFFillerError):
    """Neither pdfrw nor PyPDF2 is installed."""
    pass


def _fill_with_pdfrw(template_bytes: bytes, field_values: Dict[str, str]) -> bytes:
    """Fill AcroForm fields using pdfrw."""
    from pdfrw import PdfReader, PdfWriter, PdfDict, PdfName

    reader = PdfReader(fdata=template_bytes)
    filled_count = 0

    for page in reader.pages:
        annotations = page.get("/Annots")
        if not annotations:
            continue
        for annot in annotations:
            if annot.get("/Subtype") != "/Widget":
                continue
            field_name = annot.get("/T")
            if field_name is None:
                continue
            # pdfrw returns field names wrapped in parentheses: "(FieldName)"
            clean_name = str(field_name).strip("()")
            if clean_name in field_values:
                value = str(field_values[clean_name])
                annot.update(PdfDict(
                    V=value,
                    AP="",  # Clear appearance to force reader to regenerate
                ))
                # Set field as read-only after filling (bit 1 of Ff = ReadOnly)
                existing_ff = int(annot.get("/Ff", 0))
                annot.update(PdfDict(Ff=existing_ff | 1))
                filled_count += 1

    logger.info("pdfrw: filled %d / %d fields", filled_count, len(field_values))

    output = io.BytesIO()
    writer = PdfWriter()
    writer.trailer = reader
    writer.write(output)
    return output.getvalue()


def _fill_with_pypdf2(template_bytes: bytes, field_values: Dict[str, str]) -> bytes:
    """Fill AcroForm fields using PyPDF2."""
    from PyPDF2 import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(template_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Copy AcroForm from reader
    if "/AcroForm" in reader.trailer.get("/Root", {}):
        writer._root_object.update({"/AcroForm": reader.trailer["/Root"]["/AcroForm"]})

    filled_count = 0
    for page_num in range(len(writer.pages)):
        try:
            writer.update_page_form_field_values(
                writer.pages[page_num],
                field_values,
            )
            filled_count += 1
        except Exception as e:
            logger.warning("PyPDF2: failed to fill page %d: %s", page_num, e)

    logger.info("PyPDF2: processed %d pages with %d field values", filled_count, len(field_values))

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _get_pdf_filler():
    """Return the best available PDF filling function."""
    try:
        import pdfrw  # noqa: F401
        return _fill_with_pdfrw
    except ImportError:
        pass

    try:
        import PyPDF2  # noqa: F401
        return _fill_with_pypdf2
    except ImportError:
        pass

    raise PDFLibraryNotAvailable(
        "PDF filling requires 'pdfrw' or 'PyPDF2'. "
        "Install with: pip install pdfrw"
    )


def get_template(
    db: Session,
    form_type: str,
    tax_year: int,
) -> TaxFormTemplate:
    """Load a PDF template from DB.

    Args:
        db: Database session
        form_type: Form type string (e.g., "E1", "E1a", "L1k")
        tax_year: Tax year (e.g., 2025)

    Returns:
        TaxFormTemplate row

    Raises:
        TemplateNotFoundError: if no template exists for this form+year
    """
    try:
        enum_type = TaxFormType(form_type)
    except ValueError:
        raise TemplateNotFoundError(
            f"Unknown form type: {form_type}. "
            f"Valid types: {[t.value for t in TaxFormType]}"
        )

    template = db.query(TaxFormTemplate).filter(
        TaxFormTemplate.tax_year == tax_year,
        TaxFormTemplate.form_type == enum_type,
    ).first()

    if not template:
        raise TemplateNotFoundError(
            f"No PDF template for {form_type} {tax_year}. "
            f"Upload via POST /admin/tax-form-templates"
        )

    return template


def _build_field_values(
    form_data: Dict[str, Any],
    field_mapping: Dict[str, str],
) -> Dict[str, str]:
    """Map our KZ-based form data to PDF AcroForm field names.

    Args:
        form_data: Output from a form service (has "fields" list with kz+value)
        field_mapping: DB-stored mapping {our_kz: pdf_field_name}

    Returns:
        Dict of {pdf_field_name: string_value} ready for PDF filling
    """
    result = {}

    # Map fields by KZ
    for field in form_data.get("fields", []):
        kz = str(field.get("kz", ""))
        if kz in field_mapping:
            pdf_field = field_mapping[kz]
            value = field.get("value", "")
            # Format numbers: remove trailing zeros for cleaner display
            if isinstance(value, (int, float)):
                if value == int(value):
                    result[pdf_field] = str(int(value))
                else:
                    result[pdf_field] = f"{value:.2f}"
            else:
                result[pdf_field] = str(value)

    # Also map common metadata fields if present in mapping
    meta_keys = {
        "_user_name": form_data.get("user_name", ""),
        "_tax_number": form_data.get("tax_number", ""),
        "_tax_year": str(form_data.get("tax_year", "")),
    }
    for meta_key, meta_value in meta_keys.items():
        if meta_key in field_mapping:
            result[field_mapping[meta_key]] = str(meta_value)

    return result


def fill_tax_form_pdf(
    db: Session,
    form_type: str,
    tax_year: int,
    form_data: Dict[str, Any],
) -> bytes:
    """Fill an official BMF tax form PDF with computed user data.

    Args:
        db: Database session
        form_type: Form type (e.g., "E1", "E1a", "L1k")
        tax_year: Tax year
        form_data: Output dict from the corresponding form service

    Returns:
        Filled PDF as bytes

    Raises:
        TemplateNotFoundError: No template in DB
        PDFLibraryNotAvailable: No PDF library installed
        PDFFillerError: Filling failed
    """
    # 1. Load template from DB
    template = get_template(db, form_type, tax_year)

    # 2. Build field value mapping
    field_values = _build_field_values(form_data, template.field_mapping or {})

    if not field_values:
        logger.warning(
            "No fields mapped for %s %d — returning unfilled template. "
            "Check field_mapping in tax_form_templates.",
            form_type, tax_year
        )
        return template.pdf_template

    # 3. Fill PDF
    filler = _get_pdf_filler()
    try:
        filled_pdf = filler(template.pdf_template, field_values)
    except Exception as e:
        raise PDFFillerError(f"Failed to fill {form_type} {tax_year}: {e}") from e

    logger.info(
        "Filled %s %d: %d fields mapped, output %d bytes",
        form_type, tax_year, len(field_values), len(filled_pdf)
    )
    return filled_pdf


def list_available_templates(
    db: Session,
    tax_year: Optional[int] = None,
) -> list:
    """List all uploaded form templates, optionally filtered by year.

    Returns list of dicts with metadata (no PDF blob).
    """
    query = db.query(TaxFormTemplate)
    if tax_year:
        query = query.filter(TaxFormTemplate.tax_year == tax_year)

    templates = query.order_by(
        TaxFormTemplate.tax_year.desc(),
        TaxFormTemplate.form_type,
    ).all()

    return [
        {
            "id": t.id,
            "tax_year": t.tax_year,
            "form_type": t.form_type.value,
            "display_name": t.display_name,
            "original_filename": t.original_filename,
            "file_size_bytes": t.file_size_bytes,
            "page_count": t.page_count,
            "field_count": len(t.field_mapping or {}),
            "source_url": t.source_url,
            "bmf_version": t.bmf_version,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in templates
    ]
