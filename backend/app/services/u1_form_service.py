"""
U1 Form Service — Umsatzsteuererklaerung (Annual VAT Return)

Generates the annual U1 VAT return with complete Kennzahlen mapping.
Based on the UVA service's period-based data, aggregated for the full year.
Includes annual-specific fields: prepayments made, final settlement.

Reference: BMF FinanzOnline U1 form
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType
from app.models.user import User


# VAT rates
VAT_STANDARD = Decimal("0.20")    # 20%
VAT_REDUCED_10 = Decimal("0.10")  # 10%
VAT_REDUCED_13 = Decimal("0.13")  # 13%


def _classify_vat_rate(vat_amount: Decimal, net_amount: Decimal) -> str:
    """Classify the VAT rate bucket from amounts."""
    if net_amount <= 0:
        return "unknown"
    ratio = vat_amount / net_amount
    if ratio >= Decimal("0.18"):
        return "20"
    elif ratio >= Decimal("0.11"):
        return "13"
    elif ratio >= Decimal("0.08"):
        return "10"
    elif ratio <= Decimal("0.01"):
        return "exempt"
    return "unknown"


def generate_u1_form_data(
    db: Session,
    user: User,
    tax_year: int,
) -> Dict[str, Any]:
    """Generate U1 annual VAT return form data.

    Aggregates all income/expense transactions for the full year,
    classifies by VAT rate, and maps to official Kennzahlen.
    """
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .all()
    )

    # Revenue classification by VAT rate
    revenue_20 = Decimal("0")
    revenue_10 = Decimal("0")
    revenue_13 = Decimal("0")
    revenue_exempt = Decimal("0")
    vat_20 = Decimal("0")
    vat_10 = Decimal("0")
    vat_13 = Decimal("0")

    # Input VAT (Vorsteuer)
    vorsteuer = Decimal("0")

    for t in transactions:
        amount = t.amount or Decimal("0")
        vat = t.vat_amount or Decimal("0")

        if t.type == TransactionType.INCOME:
            net = amount - vat if vat > 0 else amount
            rate_bucket = _classify_vat_rate(vat, net) if vat > 0 else "exempt"

            if rate_bucket == "20":
                revenue_20 += net
                vat_20 += vat
            elif rate_bucket == "13":
                revenue_13 += net
                vat_13 += vat
            elif rate_bucket == "10":
                revenue_10 += net
                vat_10 += vat
            else:
                revenue_exempt += amount

        elif t.type == TransactionType.EXPENSE and vat > 0:
            vorsteuer += vat

    total_vat = vat_20 + vat_10 + vat_13
    zahllast = total_vat - vorsteuer  # positive = owe, negative = refund

    # Reverse charge / intra-community (placeholder — requires vat_type on transaction)
    reverse_charge_revenue = Decimal("0")
    ig_lieferungen = Decimal("0")

    fields = [
        # ═══ Lieferungen und Leistungen (Revenue) ═══
        {
            "kz": "000",
            "label_de": "Lieferungen/Leistungen 20% USt (Bemessungsgrundlage)",
            "label_en": "Revenue at 20% VAT (tax base)",
            "label_zh": "20%增值税收入（计税基础）",
            "value": float(revenue_20),
            "section": "lieferungen",
            "editable": True,
        },
        {
            "kz": "001",
            "label_de": "Lieferungen/Leistungen 10% USt (Bemessungsgrundlage)",
            "label_en": "Revenue at 10% VAT (tax base)",
            "label_zh": "10%增值税收入（计税基础）",
            "value": float(revenue_10),
            "section": "lieferungen",
            "editable": True,
        },
        {
            "kz": "006",
            "label_de": "Lieferungen/Leistungen 13% USt (Bemessungsgrundlage)",
            "label_en": "Revenue at 13% VAT (tax base)",
            "label_zh": "13%增值税收入（计税基础）",
            "value": float(revenue_13),
            "section": "lieferungen",
            "editable": True,
        },
        {
            "kz": "011",
            "label_de": "Steuerfreie Umsaetze (ohne Vorsteuerabzug)",
            "label_en": "Tax-exempt revenue (no input VAT deduction)",
            "label_zh": "免税收入（无进项税抵扣）",
            "value": float(revenue_exempt),
            "section": "lieferungen",
            "editable": True,
        },
        {
            "kz": "017",
            "label_de": "Innergemeinschaftliche Lieferungen (steuerfrei, §6 Abs.1 Z1)",
            "label_en": "Intra-community supplies (exempt)",
            "label_zh": "欧盟内供应（免税）",
            "value": float(ig_lieferungen),
            "section": "lieferungen",
            "editable": True,
        },
        {
            "kz": "021",
            "label_de": "Reverse Charge (§19 Abs.1 UStG)",
            "label_en": "Reverse charge services received",
            "label_zh": "反向征收（接收服务）",
            "value": float(reverse_charge_revenue),
            "section": "lieferungen",
            "editable": True,
        },
        # ═══ Steuer (VAT amounts) ═══
        {
            "kz": "022",
            "label_de": "Umsatzsteuer 20%",
            "label_en": "VAT 20%",
            "label_zh": "20%增值税",
            "value": float(vat_20),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": "029",
            "label_de": "Umsatzsteuer 10%",
            "label_en": "VAT 10%",
            "label_zh": "10%增值税",
            "value": float(vat_10),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": "008",
            "label_de": "Umsatzsteuer 13%",
            "label_en": "VAT 13%",
            "label_zh": "13%增值税",
            "value": float(vat_13),
            "section": "steuer",
            "editable": False,
        },
        {
            "kz": "056",
            "label_de": "Summe Umsatzsteuer",
            "label_en": "Total VAT",
            "label_zh": "增值税总额",
            "value": float(total_vat),
            "section": "steuer",
            "editable": False,
        },
        # ═══ Vorsteuer (Input VAT) ═══
        {
            "kz": "060",
            "label_de": "Vorsteuer (gesamt)",
            "label_en": "Input VAT total",
            "label_zh": "进项税总额",
            "value": float(vorsteuer),
            "section": "vorsteuer",
            "editable": True,
        },
        {
            "kz": "065",
            "label_de": "Vorsteuer aus IG Erwerb",
            "label_en": "Input VAT from intra-community acquisition",
            "label_zh": "欧盟内取得的进项税",
            "value": 0.0,
            "section": "vorsteuer",
            "editable": True,
        },
        {
            "kz": "067",
            "label_de": "Vorsteuerberichtigung (§12 Abs.10/11 UStG)",
            "label_en": "Input VAT correction",
            "label_zh": "进项税更正",
            "value": 0.0,
            "section": "vorsteuer",
            "editable": True,
        },
        # ═══ Zahllast / Gutschrift ═══
        {
            "kz": "095",
            "label_de": "Zahllast (+ Nachzahlung / - Gutschrift)",
            "label_en": "VAT payable (+ owed / - refund)",
            "label_zh": "应缴增值税（+应缴 / -退税）",
            "value": float(zahllast),
            "section": "zahllast",
            "editable": False,
        },
        # ═══ Annual-specific fields ═══
        {
            "kz": "096",
            "label_de": "Bereits geleistete Vorauszahlungen (UVA-Zahlungen)",
            "label_en": "Advance payments already made (UVA payments)",
            "label_zh": "已缴预付款（UVA付款）",
            "value": 0.0,
            "section": "jahresausgleich",
            "editable": True,
            "note_de": "Summe aller im Jahr geleisteten UVA-Zahlungen",
        },
        {
            "kz": "097",
            "label_de": "Nachzahlung / Gutschrift (Jahresausgleich)",
            "label_en": "Final settlement (owed / refund)",
            "label_zh": "年度结算（补缴/退税）",
            "value": float(zahllast),  # Before prepayments; user adjusts KZ 096
            "section": "jahresausgleich",
            "editable": False,
            "note_de": "KZ 095 abzueglich bereits geleisteter Vorauszahlungen (KZ 096)",
        },
    ]

    return {
        "form_type": "U1",
        "form_name_de": "Umsatzsteuererklaerung (Jahreserklaerung)",
        "form_name_en": "Annual VAT Return",
        "form_name_zh": "年度增值税申报表",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "vat_number": getattr(user, "vat_number", "") or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "total_revenue": float(revenue_20 + revenue_10 + revenue_13 + revenue_exempt),
            "revenue_20": float(revenue_20),
            "revenue_10": float(revenue_10),
            "revenue_13": float(revenue_13),
            "revenue_exempt": float(revenue_exempt),
            "vat_20": float(vat_20),
            "vat_10": float(vat_10),
            "vat_13": float(vat_13),
            "total_vat": float(total_vat),
            "vorsteuer": float(vorsteuer),
            "zahllast": float(zahllast),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer die Umsatzsteuererklaerung (U1). "
            "Bitte pruefen Sie alle Werte sorgfaeltig. Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the annual VAT return (U1). "
            "Please verify all values carefully. Not tax advice."
        ),
    }
