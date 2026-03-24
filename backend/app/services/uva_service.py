"""
USt-Voranmeldung (UVA) Service — VAT Advance Return for Austrian Tax Filing

Generates UVA data and FinanzOnline-compatible XML for periodic VAT reporting.

Filing obligations:
- Monthly UVA: if prior-year revenue > EUR 100,000
- Quarterly UVA: if prior-year revenue > EUR 55,000 (up to EUR 100,000)
- Annual only (no UVA): if revenue <= EUR 55,000 (Kleinunternehmer below EUR 42,000 exempt)

Deadlines: UVA due by 15th of second month after period end
  e.g. January UVA -> due March 15
       Q1 UVA -> due May 15
"""
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import extract, and_

from app.models.transaction import Transaction, TransactionType, VatType
from app.models.user import User
from app.services.posting_line_utils import recoverable_input_vat_for_transaction

logger = logging.getLogger(__name__)

# Austrian VAT rates
VAT_RATE_NORMAL = Decimal("0.20")       # 20% Normalsteuersatz
VAT_RATE_REDUCED_1 = Decimal("0.10")    # 10% ermaessigter Satz (Lebensmittel, etc.)
VAT_RATE_REDUCED_2 = Decimal("0.13")    # 13% ermaessigter Satz (Kultur, etc.)
VAT_RATE_ZERO = Decimal("0.00")         # 0% (Kleinunternehmer, steuerfreie Umsaetze)

# KZ mapping for UVA form (official FinanzOnline Kennzahlen)
UVA_KZ = {
    "revenue_20": "000",       # Lieferungen/Leistungen 20%
    "revenue_10": "001",       # Lieferungen/Leistungen 10%
    "revenue_13": "006",       # Lieferungen/Leistungen 13%
    "revenue_exempt": "011",   # Steuerfreie Umsaetze ohne Vorsteuerabzug
    "ig_lieferungen": "017",   # Innergemeinschaftliche Lieferungen (EU)
    "reverse_charge": "021",   # Reverse Charge (§19 UStG)
    "vat_20": "022",           # USt 20%
    "vat_10": "029",           # USt 10%
    "vat_13": "006",           # USt 13%
    "total_vat": "056",        # Gesamtbetrag der USt
    "vorsteuer": "060",        # Vorsteuer (input VAT)
    "ig_erwerb_vst": "065",    # Vorsteuer ig. Erwerbe
    "import_vst": "061",       # Einfuhrumsatzsteuer (import VAT)
    "vst_correction": "067",   # Vorsteuerberichtigung
    "zahllast": "095",         # Zahllast (net VAT payable) or Gutschrift
}


def determine_uva_period_type(
    annual_revenue: Decimal,
) -> Literal["monthly", "quarterly", "annual"]:
    """Determine UVA filing frequency based on prior-year revenue."""
    if annual_revenue > Decimal("100000"):
        return "monthly"
    elif annual_revenue > Decimal("55000"):
        return "quarterly"
    else:
        return "annual"


def get_period_date_range(
    year: int,
    period_type: Literal["monthly", "quarterly"],
    period: int,
) -> tuple:
    """Return (start_date, end_date) for a given UVA period.

    Args:
        year: Tax year
        period_type: 'monthly' or 'quarterly'
        period: 1-12 for monthly, 1-4 for quarterly
    """
    if period_type == "monthly":
        start_month = period
        end_month = period
    else:
        start_month = (period - 1) * 3 + 1
        end_month = period * 3

    start_date = date(year, start_month, 1)

    if end_month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, end_month + 1, 1)
        from datetime import timedelta
        end_date = end_date - timedelta(days=1)

    return start_date, end_date


def get_uva_deadline(
    year: int,
    period_type: Literal["monthly", "quarterly"],
    period: int,
) -> date:
    """Calculate UVA filing deadline (15th of 2nd month after period end)."""
    if period_type == "monthly":
        deadline_month = period + 2
    else:
        deadline_month = period * 3 + 2

    deadline_year = year
    if deadline_month > 12:
        deadline_month -= 12
        deadline_year += 1

    return date(deadline_year, deadline_month, 15)


def generate_uva_data(
    db: Session,
    user: User,
    tax_year: int,
    period_type: Literal["monthly", "quarterly"],
    period: int,
) -> Dict[str, Any]:
    """Generate UVA data for a specific period.

    Args:
        db: Database session
        user: Current user
        tax_year: Tax year
        period_type: 'monthly' or 'quarterly'
        period: Period number (1-12 for monthly, 1-4 for quarterly)

    Returns:
        Dict with UVA form fields, summary, and metadata
    """
    start_date, end_date = get_period_date_range(tax_year, period_type, period)
    deadline = get_uva_deadline(tax_year, period_type, period)

    # Fetch transactions for the period
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        .all()
    )

    # ── Aggregate revenue by VAT rate ──
    revenue_20 = Decimal("0")
    revenue_10 = Decimal("0")
    revenue_13 = Decimal("0")
    revenue_exempt = Decimal("0")
    vat_20 = Decimal("0")
    vat_10 = Decimal("0")
    vat_13 = Decimal("0")

    # Extended KZ: reverse charge, intra-community, import
    reverse_charge_revenue = Decimal("0")
    ig_lieferungen = Decimal("0")
    ig_erwerb = Decimal("0")
    ig_erwerb_vst = Decimal("0")
    import_vst = Decimal("0")

    for t in transactions:
        if t.type != TransactionType.INCOME:
            continue
        amt = t.amount or Decimal("0")
        rate = t.vat_rate or Decimal("0")
        vat_amt = t.vat_amount or Decimal("0")
        vat_type = getattr(t, "vat_type", None)
        if vat_type:
            vat_type = vat_type.upper()

        # Classify by vat_type first, then by rate
        if vat_type == "REVERSE_CHARGE":
            reverse_charge_revenue += amt
            continue
        if vat_type == "INTRA_COMMUNITY":
            ig_lieferungen += amt
            continue

        if rate == VAT_RATE_NORMAL:
            revenue_20 += amt
            vat_20 += vat_amt
        elif rate == VAT_RATE_REDUCED_1:
            revenue_10 += amt
            vat_10 += vat_amt
        elif rate == VAT_RATE_REDUCED_2:
            revenue_13 += amt
            vat_13 += vat_amt
        else:
            revenue_exempt += amt

    total_vat_collected = vat_20 + vat_10 + vat_13

    # ── Vorsteuer (input VAT from expenses) ──
    vorsteuer = Decimal("0")
    for t in transactions:
        if t.type not in {TransactionType.EXPENSE, TransactionType.ASSET_ACQUISITION}:
            continue
        vat_amt = recoverable_input_vat_for_transaction(t)
        vat_type = getattr(t, "vat_type", None)
        if vat_type:
            vat_type = vat_type.upper()

        if vat_type == "INTRA_COMMUNITY":
            ig_erwerb += (t.amount or Decimal("0"))
            ig_erwerb_vst += vat_amt
        elif vat_type == "IMPORT":
            import_vst += vat_amt
        elif vat_amt:
            vorsteuer += vat_amt

    # Total deductible input VAT (including IG + import)
    total_vorsteuer = vorsteuer + ig_erwerb_vst + import_vst

    # ── Zahllast (net VAT payable) ──
    zahllast = total_vat_collected - total_vorsteuer

    # ── Period label ──
    if period_type == "monthly":
        month_names_de = [
            "", "Jänner", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]
        period_label_de = month_names_de[period]
        period_label_en = start_date.strftime("%B")
        period_label_zh = f"{period}月"
    else:
        period_label_de = f"{period}. Quartal"
        period_label_en = f"Q{period}"
        period_label_zh = f"第{period}季度"

    fields = [
        {
            "kz": UVA_KZ["revenue_20"],
            "label_de": "Lieferungen und sonstige Leistungen (20%)",
            "label_en": "Supplies and services (20%)",
            "label_zh": "商品和服务供应（20%）",
            "value": float(revenue_20),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["revenue_10"],
            "label_de": "Lieferungen und sonstige Leistungen (10%)",
            "label_en": "Supplies and services (10%)",
            "label_zh": "商品和服务供应（10%）",
            "value": float(revenue_10),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["revenue_13"],
            "label_de": "Lieferungen und sonstige Leistungen (13%)",
            "label_en": "Supplies and services (13%)",
            "label_zh": "商品和服务供应（13%）",
            "value": float(revenue_13),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["revenue_exempt"],
            "label_de": "Steuerfreie Umsaetze ohne Vorsteuerabzug",
            "label_en": "Tax-exempt revenue (no input VAT deduction)",
            "label_zh": "免税营业额（无进项税抵扣）",
            "value": float(revenue_exempt),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["ig_lieferungen"],
            "label_de": "Innergemeinschaftliche Lieferungen (steuerfrei)",
            "label_en": "Intra-community supplies (exempt)",
            "label_zh": "欧盟内供应（免税）",
            "value": float(ig_lieferungen),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["reverse_charge"],
            "label_de": "Reverse Charge (§19 Abs.1 UStG)",
            "label_en": "Reverse charge services",
            "label_zh": "反向征收",
            "value": float(reverse_charge_revenue),
            "section": "umsaetze",
            "editable": True,
        },
        {
            "kz": UVA_KZ["vat_20"],
            "label_de": "Umsatzsteuer 20%",
            "label_en": "VAT 20%",
            "label_zh": "增值税 20%",
            "value": float(vat_20),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": UVA_KZ["vat_10"],
            "label_de": "Umsatzsteuer 10%",
            "label_en": "VAT 10%",
            "label_zh": "增值税 10%",
            "value": float(vat_10),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": UVA_KZ["total_vat"],
            "label_de": "Gesamtbetrag der Umsatzsteuer",
            "label_en": "Total VAT collected",
            "label_zh": "增值税总额",
            "value": float(total_vat_collected),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": UVA_KZ["vorsteuer"],
            "label_de": "Vorsteuer (abziehbar)",
            "label_en": "Input VAT (deductible)",
            "label_zh": "进项税（可抵扣）",
            "value": float(vorsteuer),
            "section": "vorsteuer",
            "editable": True,
        },
        {
            "kz": UVA_KZ["ig_erwerb_vst"],
            "label_de": "Vorsteuer aus innergemeinschaftlichem Erwerb",
            "label_en": "Input VAT from intra-community acquisition",
            "label_zh": "欧盟内取得的进项税",
            "value": float(ig_erwerb_vst),
            "section": "vorsteuer",
            "editable": True,
        },
        {
            "kz": UVA_KZ["import_vst"],
            "label_de": "Einfuhrumsatzsteuer (EUSt)",
            "label_en": "Import VAT",
            "label_zh": "进口增值税",
            "value": float(import_vst),
            "section": "vorsteuer",
            "editable": True,
        },
        {
            "kz": UVA_KZ["zahllast"],
            "label_de": "Zahllast (+) / Gutschrift (-)",
            "label_en": "VAT payable (+) / refund (-)",
            "label_zh": "应缴增值税(+) / 退税(-)",
            "value": float(zahllast),
            "section": "ergebnis",
            "editable": False,
        },
    ]

    return {
        "form_type": "UVA",
        "form_name_de": "Umsatzsteuervoranmeldung",
        "form_name_en": "VAT Advance Return",
        "form_name_zh": "增值税预申报 (UVA)",
        "tax_year": tax_year,
        "period_type": period_type,
        "period": period,
        "period_label_de": period_label_de,
        "period_label_en": period_label_en,
        "period_label_zh": period_label_zh,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "deadline": deadline.isoformat(),
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "vat_number": getattr(user, "vat_number", "") or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "revenue_20": float(revenue_20),
            "revenue_10": float(revenue_10),
            "revenue_13": float(revenue_13),
            "revenue_exempt": float(revenue_exempt),
            "total_revenue": float(revenue_20 + revenue_10 + revenue_13 + revenue_exempt),
            "vat_20": float(vat_20),
            "vat_10": float(vat_10),
            "vat_13": float(vat_13),
            "total_vat_collected": float(total_vat_collected),
            "reverse_charge": float(reverse_charge_revenue),
            "ig_lieferungen": float(ig_lieferungen),
            "ig_erwerb": float(ig_erwerb),
            "ig_erwerb_vst": float(ig_erwerb_vst),
            "import_vst": float(import_vst),
            "vorsteuer": float(vorsteuer),
            "total_vorsteuer": float(total_vorsteuer),
            "zahllast": float(zahllast),
            "transaction_count": len(transactions),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer die Umsatzsteuervoranmeldung (UVA). "
            "Bitte pruefen Sie alle Werte vor der Einreichung bei FinanzOnline. "
            f"Abgabefrist: {deadline.strftime('%d.%m.%Y')}. "
            "Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the VAT advance return (UVA). "
            "Please verify all values before submitting to FinanzOnline. "
            f"Filing deadline: {deadline.strftime('%d.%m.%Y')}. "
            "Not tax advice."
        ),
        "disclaimer_zh": (
            "此数据仅作为增值税预申报(UVA)的填写辅助。"
            "请在提交到FinanzOnline之前核实所有数值。"
            f"申报截止日：{deadline.strftime('%Y-%m-%d')}。"
            "非税务建议。"
        ),
        "finanzonline_url": "https://finanzonline.bmf.gv.at",
    }


def generate_uva_xml(uva_data: Dict[str, Any]) -> str:
    """Generate FinanzOnline-compatible XML for UVA submission.

    Args:
        uva_data: Output from generate_uva_data()

    Returns:
        Formatted XML string ready for FinanzOnline upload
    """
    root = ET.Element("Umsatzsteuervoranmeldung")
    root.set("Jahr", str(uva_data["tax_year"]))
    root.set("Zeitraum", _get_xml_period(uva_data))
    root.set("Version", "2026.1")
    root.set("xmlns", "http://www.bmf.gv.at/egovportal/finanzonline")

    # Taxpayer info
    taxpayer = ET.SubElement(root, "Steuerpflichtiger")
    if uva_data.get("tax_number"):
        stnr = ET.SubElement(taxpayer, "Steuernummer")
        stnr.text = str(uva_data["tax_number"])
    if uva_data.get("vat_number"):
        uid = ET.SubElement(taxpayer, "UID")
        uid.text = str(uva_data["vat_number"])
    if uva_data.get("user_name"):
        name = ET.SubElement(taxpayer, "Name")
        name.text = str(uva_data["user_name"])

    # Period info
    zeitraum = ET.SubElement(root, "Zeitraum")
    von = ET.SubElement(zeitraum, "Von")
    von.text = uva_data["period_start"]
    bis = ET.SubElement(zeitraum, "Bis")
    bis.text = uva_data["period_end"]

    # Kennzahlen
    kennzahlen = ET.SubElement(root, "Kennzahlen")
    for field in uva_data.get("fields", []):
        kz_elem = ET.SubElement(kennzahlen, "KZ")
        kz_elem.set("nr", field["kz"])
        kz_elem.text = f"{field['value']:.2f}"

    # Format output
    rough = ET.tostring(root, encoding="unicode", method="xml")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ")


def _get_xml_period(uva_data: Dict) -> str:
    """Format period for XML attribute (e.g. 'M01', 'Q1')."""
    period_type = uva_data.get("period_type", "quarterly")
    period = uva_data.get("period", 1)
    if period_type == "monthly":
        return f"M{period:02d}"
    else:
        return f"Q{period}"


def generate_annual_uva_summary(
    db: Session,
    user: User,
    tax_year: int,
) -> Dict[str, Any]:
    """Generate annual UVA summary (Jahres-UVA / U30).

    This aggregates all periods for the full year and is used for the
    annual VAT return (Umsatzsteuerjahreserklaerung).
    """
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    total_revenue = Decimal("0")
    total_vat_collected = Decimal("0")
    total_vorsteuer = Decimal("0")

    revenue_by_rate = {
        "20": Decimal("0"),
        "10": Decimal("0"),
        "13": Decimal("0"),
        "exempt": Decimal("0"),
    }
    vat_by_rate = {
        "20": Decimal("0"),
        "10": Decimal("0"),
        "13": Decimal("0"),
    }

    for t in transactions:
        amt = t.amount or Decimal("0")
        rate = t.vat_rate or Decimal("0")
        vat_amt = t.vat_amount or Decimal("0")

        if t.type == TransactionType.INCOME:
            total_revenue += amt
            if rate == VAT_RATE_NORMAL:
                revenue_by_rate["20"] += amt
                vat_by_rate["20"] += vat_amt
            elif rate == VAT_RATE_REDUCED_1:
                revenue_by_rate["10"] += amt
                vat_by_rate["10"] += vat_amt
            elif rate == VAT_RATE_REDUCED_2:
                revenue_by_rate["13"] += amt
                vat_by_rate["13"] += vat_amt
            else:
                revenue_by_rate["exempt"] += amt
            total_vat_collected += vat_amt

        elif t.type == TransactionType.EXPENSE and vat_amt:
            total_vorsteuer += vat_amt

    zahllast = total_vat_collected - total_vorsteuer

    # Build fields array for TaxFormPreview compatibility
    fields = [
        {"kz": "000", "label_de": "Gesamtumsatz", "label_en": "Total Revenue", "label_zh": "总营业额",
         "value": float(total_revenue), "section": "umsaetze", "editable": False},
        {"kz": "022", "label_de": "Umsätze 20%", "label_en": "Revenue 20%", "label_zh": "20%税率营业额",
         "value": float(revenue_by_rate["20"]), "section": "umsaetze", "editable": False},
        {"kz": "029", "label_de": "Umsätze 10%", "label_en": "Revenue 10%", "label_zh": "10%税率营业额",
         "value": float(revenue_by_rate["10"]), "section": "umsaetze", "editable": False},
        {"kz": "006", "label_de": "Umsätze 13%", "label_en": "Revenue 13%", "label_zh": "13%税率营业额",
         "value": float(revenue_by_rate["13"]), "section": "umsaetze", "editable": False},
        {"kz": "015", "label_de": "Steuerfreie Umsätze", "label_en": "Tax-exempt Revenue", "label_zh": "免税营业额",
         "value": float(revenue_by_rate["exempt"]), "section": "umsaetze", "editable": False},
        {"kz": "022S", "label_de": "USt 20%", "label_en": "VAT 20%", "label_zh": "20%增值税",
         "value": float(vat_by_rate["20"]), "section": "steuerbetraege", "editable": False},
        {"kz": "029S", "label_de": "USt 10%", "label_en": "VAT 10%", "label_zh": "10%增值税",
         "value": float(vat_by_rate["10"]), "section": "steuerbetraege", "editable": False},
        {"kz": "006S", "label_de": "USt 13%", "label_en": "VAT 13%", "label_zh": "13%增值税",
         "value": float(vat_by_rate["13"]), "section": "steuerbetraege", "editable": False},
        {"kz": "060", "label_de": "Vorsteuer gesamt", "label_en": "Total Input VAT", "label_zh": "进项税总额",
         "value": float(total_vorsteuer), "section": "vorsteuer", "editable": False},
        {"kz": "095", "label_de": "Zahllast / Gutschrift", "label_en": "VAT Payable / Credit", "label_zh": "应缴/退税额",
         "value": float(zahllast), "section": "zahllast", "editable": False},
    ]

    return {
        "form_type": "UVA",
        "form_name_de": "Umsatzsteuervoranmeldung — Jahresübersicht",
        "form_name_en": "VAT Pre-Return — Annual Summary",
        "form_name_zh": "增值税预申报 — 年度汇总",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "vat_number": getattr(user, "vat_number", "") or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "total_revenue": float(total_revenue),
            "revenue_20": float(revenue_by_rate["20"]),
            "revenue_10": float(revenue_by_rate["10"]),
            "revenue_13": float(revenue_by_rate["13"]),
            "revenue_exempt": float(revenue_by_rate["exempt"]),
            "vat_20": float(vat_by_rate["20"]),
            "vat_10": float(vat_by_rate["10"]),
            "vat_13": float(vat_by_rate["13"]),
            "total_vat_collected": float(total_vat_collected),
            "total_vorsteuer": float(total_vorsteuer),
            "zahllast": float(zahllast),
            "filing_frequency": determine_uva_period_type(total_revenue),
        },
        "finanzonline_url": "https://finanzonline.bmf.gv.at/fon/",
        "form_download_url": "https://formulare.bmf.gv.at/service/formulare/inter-Steuern/pdfs/9999/U30.pdf",
        "disclaimer_de": (
            "Zusammenfassung aller Umsatzsteuer-Voranmeldungen des Jahres. "
            "Bitte mit der Umsatzsteuerjahreserklaerung (U30) bei FinanzOnline abgleichen."
        ),
        "disclaimer_en": (
            "Summary of all VAT advance returns for the year. "
            "Please reconcile with the annual VAT return (U30) on FinanzOnline."
        ),
        "disclaimer_zh": (
            "全年增值税预申报汇总。"
            "请与FinanzOnline上的年度增值税申报表(U30)核对。"
        ),
    }
