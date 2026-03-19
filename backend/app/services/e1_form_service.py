"""
E1 Einkommensteuererklaerung / L1 Arbeitnehmerveranlagung Form Service

Maps transaction data to official Austrian tax form fields (Kennzahlen/KZ).
E1 = for self-employed, landlords, mixed income
L1 = for employees (Arbeitnehmerveranlagung)

Reference: BMF FinanzOnline E1/L1 forms
"""
from decimal import Decimal
from datetime import date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus


def generate_tax_form_data(
    db: Session,
    user: User,
    tax_year: int,
) -> Dict[str, Any]:
    """Generate pre-filled tax form data based on user type.
    
    Employee -> L1 Arbeitnehmerveranlagung
    Self-employed/Landlord/Mixed -> E1 Einkommensteuererklaerung
    """
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            extract("year", Transaction.transaction_date) == tax_year,
        )
        .order_by(Transaction.transaction_date)
        .all()
    )

    user_type = user.user_type.value if user.user_type else "mixed"

    if user_type == "employee":
        return _generate_l1_form(user, transactions, tax_year)
    elif user_type == "gmbh":
        return _generate_k1_form(user, transactions, tax_year)
    else:
        return _generate_e1_form(db, user, transactions, tax_year)


def _sum_by_income_cat(transactions: list, cat: IncomeCategory) -> Decimal:
    return sum(
        (t.amount or Decimal("0"))
        for t in transactions
        if t.type == TransactionType.INCOME and t.income_category == cat
    )


def _sum_by_expense_cat(transactions: list, cats: list, deductible_only: bool = False) -> Decimal:
    """Sum expenses by category, using line-item-level amounts when available."""
    total = Decimal("0")
    for t in transactions:
        if t.type != TransactionType.EXPENSE:
            continue
        cat_values = {c.value if hasattr(c, "value") else str(c) for c in cats}
        if t.has_line_items:
            for li in t.line_items:
                li_cat = li.category or "other"
                if li_cat not in cat_values:
                    continue
                if deductible_only and not li.is_deductible:
                    continue
                total += li.amount * li.quantity
        else:
            if t.expense_category not in cats:
                continue
            if deductible_only and not t.is_deductible:
                continue
            total += t.amount or Decimal("0")
    return total


def _sum_deductible_expenses(transactions: list) -> Decimal:
    """Sum all deductible expenses using line-item-level deductibility."""
    return sum(
        (t.deductible_amount or Decimal("0"))
        for t in transactions
        if t.type == TransactionType.EXPENSE
    )


def _sum_vat(transactions: list, tx_type: TransactionType) -> Decimal:
    return sum(
        (t.vat_amount or Decimal("0"))
        for t in transactions
        if t.type == tx_type and t.vat_amount
    )


def _generate_l1_form(
    user: User, transactions: list, tax_year: int
) -> Dict[str, Any]:
    """Generate L1 Arbeitnehmerveranlagung form data."""
    employment_income = _sum_by_income_cat(transactions, IncomeCategory.EMPLOYMENT)

    # Werbungskosten (work-related expenses) for employees
    werbungskosten_cats = [
        ExpenseCategory.TRAVEL, ExpenseCategory.COMMUTING,
        ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.EQUIPMENT,
        ExpenseCategory.HOME_OFFICE, ExpenseCategory.PROFESSIONAL_SERVICES,
    ]
    werbungskosten = _sum_by_expense_cat(transactions, werbungskosten_cats, deductible_only=True)

    # Sonderausgaben (special deductions) - insurance, etc.
    sonderausgaben = _sum_by_expense_cat(
        transactions, [ExpenseCategory.INSURANCE], deductible_only=True
    )

    # Pendlerpauschale from user profile
    commuting_info = user.commuting_info or {}
    distance_km = commuting_info.get("distance_km", 0)
    public_transport = commuting_info.get("public_transport_available", True)

    # Calculate Pendlerpauschale (simplified)
    pendlerpauschale = Decimal("0")
    if distance_km >= 20:
        if public_transport:
            # Kleines Pendlerpauschale
            if distance_km >= 60:
                pendlerpauschale = Decimal("2016")
            elif distance_km >= 40:
                pendlerpauschale = Decimal("1356")
            elif distance_km >= 20:
                pendlerpauschale = Decimal("696")
        else:
            # Grosses Pendlerpauschale
            if distance_km >= 60:
                pendlerpauschale = Decimal("3672")
            elif distance_km >= 40:
                pendlerpauschale = Decimal("2568")
            elif distance_km >= 20:
                pendlerpauschale = Decimal("1476")
            elif distance_km >= 2:
                pendlerpauschale = Decimal("372")

    # Family info
    family_info = user.family_info or {}
    num_children = family_info.get("num_children", 0)
    single_parent = family_info.get("is_single_parent", False)

    # Alleinverdiener/Alleinerzieherabsetzbetrag
    alleinerzieher = Decimal("0")
    if single_parent and num_children > 0:
        alleinerzieher = Decimal("520")  # base
        if num_children >= 2:
            alleinerzieher += Decimal("704") * (num_children - 1)

    # Familienbonus Plus (per child, max 2000 per child under 18)
    familienbonus = Decimal("2000") * num_children if num_children > 0 else Decimal("0")

    fields = [
        {
            "kz": "210",
            "label_de": "Alleinverdienerabsetzbetrag / Alleinerzieherabsetzbetrag",
            "label_en": "Sole earner / single parent tax credit",
            "label_zh": "\u5355\u72ec\u8d5a\u94b1\u4eba/\u5355\u4eb2\u7a0e\u6536\u62b5\u514d",
            "value": float(alleinerzieher),
            "section": "absetzbetraege",
            "editable": True,
        },
        {
            "kz": "220",
            "label_de": "Anzahl der Kinder (Familienbonus Plus)",
            "label_en": "Number of children (Family Bonus Plus)",
            "label_zh": "\u5b50\u5973\u6570\u91cf\uff08\u5bb6\u5ead\u5956\u91d1Plus\uff09",
            "value": num_children,
            "section": "absetzbetraege",
            "editable": True,
        },
        {
            "kz": "225",
            "label_de": "Familienbonus Plus (je Kind max. EUR 2.000)",
            "label_en": "Family Bonus Plus (max EUR 2,000 per child)",
            "label_zh": "\u5bb6\u5ead\u5956\u91d1Plus\uff08\u6bcf\u5b50\u5973\u6700\u9ad82000\u6b27\u5143\uff09",
            "value": float(familienbonus),
            "section": "absetzbetraege",
            "editable": True,
        },
        {
            "kz": "718",
            "label_de": "Personenversicherungen, Wohnraumschaffung",
            "label_en": "Personal insurance, housing construction",
            "label_zh": "\u4e2a\u4eba\u4fdd\u9669\u3001\u4f4f\u623f\u5efa\u8bbe",
            "value": float(sonderausgaben),
            "section": "sonderausgaben",
            "editable": True,
        },
        {
            "kz": "724",
            "label_de": "Kirchenbeitrag (max. EUR 600)",
            "label_en": "Church tax (max EUR 600)",
            "label_zh": "\u6559\u4f1a\u7a0e\uff08\u6700\u9ad8600\u6b27\u5143\uff09",
            "value": 0.0,
            "section": "sonderausgaben",
            "editable": True,
        },
        {
            "kz": "775",
            "label_de": "Werbungskosten gesamt",
            "label_en": "Work-related expenses total",
            "label_zh": "\u4e0e\u5de5\u4f5c\u76f8\u5173\u7684\u8d39\u7528\u603b\u8ba1",
            "value": float(werbungskosten),
            "section": "werbungskosten",
            "editable": True,
        },
        {
            "kz": "718",
            "label_de": "Pendlerpauschale (jaehrlich)",
            "label_en": "Commuter allowance (annual)",
            "label_zh": "\u901a\u52e4\u8865\u8d34\uff08\u5e74\u5ea6\uff09",
            "value": float(pendlerpauschale),
            "section": "pendler",
            "editable": True,
        },
    ]

    return {
        "form_type": "L1",
        "form_name_de": "Arbeitnehmerveranlagung",
        "form_name_en": "Employee Tax Assessment",
        "form_name_zh": "Arbeitnehmerveranlagung (L1)",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "employment_income": float(employment_income),
            "werbungskosten": float(werbungskosten),
            "sonderausgaben": float(sonderausgaben),
            "pendlerpauschale": float(pendlerpauschale),
            "familienbonus": float(familienbonus),
            "alleinerzieher": float(alleinerzieher),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe. "
            "Bitte pruefen Sie alle Werte vor der Einreichung bei FinanzOnline. "
            "Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid. "
            "Please verify all values before submitting to FinanzOnline. "
            "Not tax advice."
        ),
        "disclaimer_zh": (
            "\u6b64\u6570\u636e\u4ec5\u4f5c\u4e3a\u586b\u5199\u8f85\u52a9\u3002"
            "\u8bf7\u5728\u63d0\u4ea4\u5230FinanzOnline\u4e4b\u524d\u6838\u5b9e\u6240\u6709\u6570\u503c\u3002"
            "\u975e\u7a0e\u52a1\u5efa\u8bae\u3002"
        ),
        "finanzonline_url": "https://finanzonline.bmf.gv.at",
        "form_download_url": "https://www.oesterreich.gv.at/en/formsearch/form/125",
    }


def _generate_e1_form(
    db: Session, user: User, transactions: list, tax_year: int
) -> Dict[str, Any]:
    """Generate E1 Einkommensteuererklaerung form data.

    Covers all 7 Austrian income types (Einkunftsarten) plus detailed
    Sonderausgaben, aussergewoehnliche Belastungen, SVS, and V+V breakdowns.
    """
    # ── Income by Einkunftsart ──
    agriculture_income = _sum_by_income_cat(transactions, IncomeCategory.AGRICULTURE)
    employment_income = _sum_by_income_cat(transactions, IncomeCategory.EMPLOYMENT)
    self_employment_income = _sum_by_income_cat(transactions, IncomeCategory.SELF_EMPLOYMENT)
    business_income = _sum_by_income_cat(transactions, IncomeCategory.BUSINESS)
    rental_income = _sum_by_income_cat(transactions, IncomeCategory.RENTAL)
    capital_gains = _sum_by_income_cat(transactions, IncomeCategory.CAPITAL_GAINS)
    other_income = _sum_by_income_cat(transactions, IncomeCategory.OTHER_INCOME)

    # ── Business / self-employment expenses ──
    business_expenses = _sum_by_expense_cat(
        transactions,
        [
            ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.EQUIPMENT,
            ExpenseCategory.MARKETING, ExpenseCategory.PROFESSIONAL_SERVICES,
            ExpenseCategory.DEPRECIATION, ExpenseCategory.HOME_OFFICE,
            ExpenseCategory.GROCERIES, ExpenseCategory.RENT,
            ExpenseCategory.TELECOM, ExpenseCategory.BANK_FEES,
        ],
        deductible_only=True,
    )
    travel_expenses = _sum_by_expense_cat(
        transactions,
        [ExpenseCategory.TRAVEL, ExpenseCategory.COMMUTING],
        deductible_only=True,
    )

    # ── SVS (Sozialversicherung der Selbstaendigen) ──
    svs_contributions = _sum_by_expense_cat(
        transactions, [ExpenseCategory.SVS_CONTRIBUTIONS], deductible_only=True
    )

    # ── V+V (Vermietung und Verpachtung) expense breakdown ──
    rental_maintenance = _sum_by_expense_cat(
        transactions, [ExpenseCategory.MAINTENANCE], deductible_only=True
    )
    # Building AfA: calculate from property data using AfACalculator
    rental_afa = Decimal("0")
    try:
        from app.services.afa_calculator import AfACalculator
        from app.models.property import Property, PropertyStatus
        afa_calc = AfACalculator(db)
        user_properties = db.query(Property).filter(
            Property.user_id == user.id,
            Property.status.in_([PropertyStatus.ACTIVE, PropertyStatus.SOLD]),
        ).all()
        for prop in user_properties:
            rental_afa += afa_calc.calculate_annual_depreciation(prop, tax_year)
    except Exception:
        pass  # Fallback: zero if calculation fails
    rental_financing = _sum_by_expense_cat(
        transactions, [ExpenseCategory.LOAN_INTEREST], deductible_only=True
    )
    rental_mgmt_fees = _sum_by_expense_cat(
        transactions, [ExpenseCategory.PROPERTY_MANAGEMENT_FEES], deductible_only=True
    )
    rental_insurance = _sum_by_expense_cat(
        transactions, [ExpenseCategory.PROPERTY_INSURANCE, ExpenseCategory.INSURANCE],
        deductible_only=True,
    )
    rental_utilities = _sum_by_expense_cat(
        transactions, [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
        deductible_only=True,
    )
    rental_expenses = (
        rental_maintenance + rental_afa + rental_financing
        + rental_mgmt_fees + rental_insurance + rental_utilities
    )

    # ── Werbungskosten (employee work-related expenses) ──
    werbungskosten = _sum_by_expense_cat(
        transactions,
        [
            ExpenseCategory.TRAVEL, ExpenseCategory.COMMUTING,
            ExpenseCategory.OFFICE_SUPPLIES, ExpenseCategory.EQUIPMENT,
            ExpenseCategory.HOME_OFFICE, ExpenseCategory.PROFESSIONAL_SERVICES,
        ],
        deductible_only=True,
    )

    # ── Sonderausgaben (special deductions) ──
    sonderausgaben_insurance = _sum_by_expense_cat(
        transactions, [ExpenseCategory.INSURANCE], deductible_only=True
    )

    total_deductible = _sum_deductible_expenses(transactions)

    # ── VAT ──
    vat_collected = _sum_vat(transactions, TransactionType.INCOME)
    vat_paid = _sum_vat(transactions, TransactionType.EXPENSE)

    # ── Calculated fields ──
    # Combine self_employment + business into Gewerbebetrieb
    combined_self_emp = self_employment_income + business_income
    gewerbebetrieb_gewinn = combined_self_emp - business_expenses - travel_expenses - svs_contributions
    vermietung_einkuenfte = rental_income - rental_expenses

    # ── Family info ──
    family_info = user.family_info or {}
    num_children = family_info.get("num_children", 0)
    single_parent = family_info.get("is_single_parent", False)
    familienbonus = Decimal("2000") * num_children if num_children > 0 else Decimal("0")

    alleinerzieher = Decimal("0")
    if single_parent and num_children > 0:
        alleinerzieher = Decimal("520")
        if num_children >= 2:
            alleinerzieher += Decimal("704") * (num_children - 1)

    # ── Pendlerpauschale ──
    commuting_info = user.commuting_info or {}
    distance_km = commuting_info.get("distance_km", 0)
    public_transport = commuting_info.get("public_transport_available", True)
    pendlerpauschale = Decimal("0")
    if distance_km >= 20:
        if public_transport:
            if distance_km >= 60:
                pendlerpauschale = Decimal("2016")
            elif distance_km >= 40:
                pendlerpauschale = Decimal("1356")
            else:
                pendlerpauschale = Decimal("696")
        else:
            if distance_km >= 60:
                pendlerpauschale = Decimal("3672")
            elif distance_km >= 40:
                pendlerpauschale = Decimal("2568")
            elif distance_km >= 20:
                pendlerpauschale = Decimal("1476")
    elif not public_transport and distance_km >= 2:
        pendlerpauschale = Decimal("372")

    # ── ImmoESt: sold properties in the tax year ──
    immoest_fields = []
    immoest_total = Decimal("0")
    immoest_gain_total = Decimal("0")
    try:
        sold_properties = (
            db.query(Property)
            .filter(
                Property.user_id == user.id,
                Property.status == PropertyStatus.SOLD,
                extract("year", Property.sale_date) == tax_year,
            )
            .all()
        )
        if sold_properties:
            from app.services.immoest_calculator import (
                calculate_immoest, ExemptionType,
            )
            for prop in sold_properties:
                if not prop.sale_price or not prop.purchase_price:
                    continue
                exemption = ExemptionType.NONE
                if getattr(prop, "hauptwohnsitz", False):
                    exemption = ExemptionType.HAUPTWOHNSITZ
                elif getattr(prop, "selbst_errichtet", False):
                    exemption = ExemptionType.HERSTELLER

                result = calculate_immoest(
                    sale_price=prop.sale_price,
                    acquisition_cost=prop.purchase_price,
                    acquisition_date=prop.purchase_date,
                    sale_date=prop.sale_date,
                    exemption=exemption,
                )
                immoest_total += result.total_tax
                immoest_gain_total += result.taxable_gain
    except Exception:
        pass  # ImmoESt integration is best-effort

    fields = [
        # ═══ Einkunftsart Nr.1: Land- und Forstwirtschaft ═══
        {
            "kz": "310",
            "label_de": "Einkuenfte aus Land- und Forstwirtschaft",
            "label_en": "Agriculture and forestry income",
            "label_zh": "农林业收入",
            "value": float(agriculture_income),
            "section": "einkuenfte_landwirtschaft",
            "editable": True,
            "note_de": "Pauschalierung moeglich bei Einheitswert bis EUR 150.000",
        },
        # ═══ Einkunftsart Nr.2/3: Selbstaendige Arbeit / Gewerbebetrieb ═══
        {
            "kz": "330",
            "label_de": "Einkuenfte aus Gewerbebetrieb",
            "label_en": "Business income (profit after expenses)",
            "label_zh": "工商业经营所得（扣除费用后）",
            "value": float(gewerbebetrieb_gewinn),
            "section": "einkuenfte_gewerbebetrieb",
            "editable": True,
            "note_de": "Einnahmen abzgl. Betriebsausgaben inkl. SVS",
        },
        {
            "kz": "370",
            "label_de": "Einkuenfte aus selbstaendiger Arbeit (Freiberufler)",
            "label_en": "Self-employment income (freelancer)",
            "label_zh": "自由职业收入",
            "value": float(self_employment_income),
            "section": "einkuenfte_selbstaendig",
            "editable": True,
        },
        {
            "kz": "9230",
            "label_de": "Betriebsausgaben gesamt",
            "label_en": "Total business expenses",
            "label_zh": "经营费用总计",
            "value": float(business_expenses + travel_expenses),
            "section": "einkuenfte_gewerbebetrieb",
            "editable": True,
            "note_de": "Summe aller abzugsfaehigen Betriebsausgaben",
        },
        {
            "kz": "9225",
            "label_de": "SVS-Beitraege (Pflichtversicherung Selbstaendige)",
            "label_en": "SVS contributions (mandatory social insurance)",
            "label_zh": "SVS社保缴费（自雇人员强制保险）",
            "value": float(svs_contributions),
            "section": "einkuenfte_gewerbebetrieb",
            "editable": True,
            "note_de": "Pflichtbeitraege an die SVS sind Betriebsausgaben (§4 Abs.4 EStG)",
        },
        # ═══ Einkunftsart Nr.4: Nichtselbstaendige Arbeit ═══
        {
            "kz": "245",
            "label_de": "Einkuenfte aus nichtselbstaendiger Arbeit (laut Lohnzettel)",
            "label_en": "Employment income (per payslip)",
            "label_zh": "非自雇就业收入（按工资单）",
            "value": float(employment_income),
            "section": "einkuenfte_nichtselbstaendig",
            "editable": False,
            "note_de": "Wird vom Arbeitgeber elektronisch uebermittelt",
        },
        # ═══ Einkunftsart Nr.5: Kapitalvermoegen ═══
        {
            "kz": "981",
            "label_de": "Einkuenfte aus Kapitalvermoegen (endbesteuert)",
            "label_en": "Capital income (final withholding tax)",
            "label_zh": "资本收益（最终征税）",
            "value": float(capital_gains),
            "section": "einkuenfte_kapital",
            "editable": True,
            "note_de": "KESt 27,5% bereits abgezogen; nur eintragen wenn Regelbesteuerung guenstiger",
        },
        # ═══ Einkunftsart Nr.6: Vermietung und Verpachtung ═══
        {
            "kz": "320",
            "label_de": "Einkuenfte aus Vermietung und Verpachtung (Ueberschuss)",
            "label_en": "Rental income (net of expenses)",
            "label_zh": "租赁所得（扣除费用后）",
            "value": float(vermietung_einkuenfte),
            "section": "einkuenfte_vermietung",
            "editable": True,
        },
        # V+V expense breakdown (Beilage E1b)
        {
            "kz": "9400",
            "label_de": "Absetzung fuer Abnutzung (AfA) — Gebaeude",
            "label_en": "Building depreciation (AfA)",
            "label_zh": "建筑折旧 (AfA)",
            "value": float(rental_afa),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
            "note_de": "1,5% p.a. des Gebaeudewertes (§16 Abs.1 Z8 EStG)",
        },
        {
            "kz": "9401",
            "label_de": "Finanzierungskosten (Kreditzinsen)",
            "label_en": "Financing costs (loan interest)",
            "label_zh": "融资成本（贷款利息）",
            "value": float(rental_financing),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
        },
        {
            "kz": "9402",
            "label_de": "Instandhaltung und Instandsetzung",
            "label_en": "Maintenance and repair costs",
            "label_zh": "维护修缮费用",
            "value": float(rental_maintenance),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
            "note_de": "Instandsetzung: Verteilung auf 15 Jahre moeglich (§28 Abs.2 EStG)",
        },
        {
            "kz": "9403",
            "label_de": "Hausverwaltung",
            "label_en": "Property management fees",
            "label_zh": "物业管理费",
            "value": float(rental_mgmt_fees),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
        },
        {
            "kz": "9404",
            "label_de": "Versicherungen (Gebaeude)",
            "label_en": "Building insurance",
            "label_zh": "建筑保险",
            "value": float(rental_insurance),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
        },
        {
            "kz": "9405",
            "label_de": "Betriebskosten (nicht umlegbar)",
            "label_en": "Operating costs (non-recoverable)",
            "label_zh": "运营成本（不可转嫁）",
            "value": float(rental_utilities),
            "section": "einkuenfte_vermietung_detail",
            "editable": True,
        },
        # ═══ Einkunftsart Nr.7: Sonstige Einkuenfte ═══
        {
            "kz": "350",
            "label_de": "Sonstige Einkuenfte (§29 EStG)",
            "label_en": "Other income (§29 EStG)",
            "label_zh": "其他收入（§29 EStG）",
            "value": float(other_income),
            "section": "einkuenfte_sonstige",
            "editable": True,
            "note_de": "z.B. Spekulationseinkuenfte, wiederkehrende Bezuege, Funktionsgebuehren",
        },
        # ═══ ImmoESt — Immobilienertragsteuer (§30 EStG) ═══
        {
            "kz": "985",
            "label_de": "Immobilienertragsteuer gesamt (§30 EStG)",
            "label_en": "Real estate capital gains tax total",
            "label_zh": "房产资本利得税总额",
            "value": float(immoest_total),
            "section": "einkuenfte_immoest",
            "editable": True,
            "note_de": "30% auf den Veraeusserungsgewinn; Hauptwohnsitz-/Herstellerbefreiung moeglich",
        },
        {
            "kz": "986",
            "label_de": "Veraeusserungsgewinn (Immobilien)",
            "label_en": "Capital gain from property sale",
            "label_zh": "房产出售收益",
            "value": float(immoest_gain_total),
            "section": "einkuenfte_immoest",
            "editable": True,
        },
        # ═══ Sonderausgaben (§18 EStG) ═══
        {
            "kz": "717",
            "label_de": "Spenden an beguestigte Einrichtungen (§18 Abs.1 Z7)",
            "label_en": "Donations to eligible organizations",
            "label_zh": "向符合条件的机构捐款",
            "value": 0.0,
            "section": "sonderausgaben",
            "editable": True,
            "note_de": "Max. 10% des Gesamtbetrags der Einkuenfte",
        },
        {
            "kz": "718",
            "label_de": "Personenversicherungen, Wohnraumschaffung (§18 Abs.1 Z2)",
            "label_en": "Personal insurance, housing construction",
            "label_zh": "个人保险、住房建设",
            "value": float(sonderausgaben_insurance),
            "section": "sonderausgaben",
            "editable": True,
        },
        {
            "kz": "724",
            "label_de": "Kirchenbeitrag (max. EUR 600, §18 Abs.1 Z5)",
            "label_en": "Church tax (max EUR 600)",
            "label_zh": "教会税（最高600欧元）",
            "value": 0.0,
            "section": "sonderausgaben",
            "editable": True,
        },
        {
            "kz": "450",
            "label_de": "Steuerberatungskosten",
            "label_en": "Tax advisory costs",
            "label_zh": "税务咨询费用",
            "value": 0.0,
            "section": "sonderausgaben",
            "editable": True,
            "note_de": "Unbeschraenkt absetzbar als Sonderausgabe oder Betriebsausgabe",
        },
        # ═══ Werbungskosten (§16 EStG) ═══
        {
            "kz": "721",
            "label_de": "Pendlerpauschale (jaehrlich)",
            "label_en": "Commuter allowance (annual)",
            "label_zh": "通勤补贴（年度）",
            "value": float(pendlerpauschale),
            "section": "werbungskosten",
            "editable": True,
            "note_de": "Abhaengig von Entfernung und Zumutbarkeit oeffentlicher Verkehrsmittel",
        },
        {
            "kz": "775",
            "label_de": "Werbungskosten gesamt (ohne Pendlerpauschale)",
            "label_en": "Work-related expenses (excl. commuter allowance)",
            "label_zh": "与工作相关的费用（不含通勤补贴）",
            "value": float(werbungskosten),
            "section": "werbungskosten",
            "editable": True,
            "note_de": "Werbungskostenpauschale EUR 132 wird automatisch beruecksichtigt",
        },
        # ═══ Aussergewoehnliche Belastungen (§34/§35 EStG) ═══
        {
            "kz": "730",
            "label_de": "Aussergewoehnliche Belastungen mit Selbstbehalt",
            "label_en": "Extraordinary expenses (with deductible threshold)",
            "label_zh": "特殊负担（含自付门槛）",
            "value": 0.0,
            "section": "aussergewoehnliche_belastungen",
            "editable": True,
            "note_de": "z.B. Krankheitskosten, Zahnersatz — Selbstbehalt 6-12% je nach Einkommen",
        },
        {
            "kz": "740",
            "label_de": "Aussergewoehnliche Belastungen ohne Selbstbehalt",
            "label_en": "Extraordinary expenses (no deductible threshold)",
            "label_zh": "特殊负担（无自付门槛）",
            "value": 0.0,
            "section": "aussergewoehnliche_belastungen",
            "editable": True,
            "note_de": "z.B. Behinderung, Katastrophenschaeden, Diaetkosten bei Krankheit",
        },
        # ═══ Absetzbetraege ═══
        {
            "kz": "210",
            "label_de": "Alleinverdiener-/Alleinerzieherabsetzbetrag",
            "label_en": "Sole earner / single parent tax credit",
            "label_zh": "单独赚钱人/单亲税收抵免",
            "value": float(alleinerzieher),
            "section": "absetzbetraege",
            "editable": True,
        },
        {
            "kz": "220",
            "label_de": "Anzahl der Kinder (Familienbonus Plus)",
            "label_en": "Number of children (Family Bonus Plus)",
            "label_zh": "子女数量（家庭奖金Plus）",
            "value": num_children,
            "section": "absetzbetraege",
            "editable": True,
        },
        {
            "kz": "225",
            "label_de": "Familienbonus Plus (je Kind max. EUR 2.000)",
            "label_en": "Family Bonus Plus (max EUR 2,000 per child)",
            "label_zh": "家庭奖金Plus（每子女最高2000欧元）",
            "value": float(familienbonus),
            "section": "absetzbetraege",
            "editable": True,
        },
    ]

    total_income = (
        agriculture_income + employment_income + combined_self_emp
        + rental_income + capital_gains + other_income
    )
    gesamtbetrag = total_income - total_deductible

    return {
        "form_type": "E1",
        "form_name_de": "Einkommensteuererklaerung",
        "form_name_en": "Income Tax Return",
        "form_name_zh": "Einkommensteuererklaerung (E1)",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "agriculture_income": float(agriculture_income),
            "employment_income": float(employment_income),
            "self_employment_income": float(self_employment_income),
            "business_income": float(business_income),
            "rental_income": float(rental_income),
            "capital_gains": float(capital_gains),
            "other_income": float(other_income),
            "total_income": float(total_income),
            "business_expenses": float(business_expenses),
            "travel_expenses": float(travel_expenses),
            "svs_contributions": float(svs_contributions),
            "rental_expenses": float(rental_expenses),
            "rental_afa": float(rental_afa),
            "rental_financing": float(rental_financing),
            "rental_maintenance": float(rental_maintenance),
            "werbungskosten": float(werbungskosten),
            "pendlerpauschale": float(pendlerpauschale),
            "sonderausgaben_insurance": float(sonderausgaben_insurance),
            "total_deductible": float(total_deductible),
            "gewerbebetrieb_gewinn": float(gewerbebetrieb_gewinn),
            "vermietung_einkuenfte": float(vermietung_einkuenfte),
            "gesamtbetrag_einkuenfte": float(gesamtbetrag),
            "familienbonus": float(familienbonus),
            "alleinerzieher": float(alleinerzieher),
            "immoest_total": float(immoest_total),
            "immoest_gain": float(immoest_gain_total),
            "vat_collected": float(vat_collected),
            "vat_paid": float(vat_paid),
            "vat_balance": float(vat_collected - vat_paid),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer das Formular E1. "
            "Bitte pruefen Sie alle Werte sorgfaeltig vor der Einreichung bei FinanzOnline. "
            "Bei komplexen Faellen konsultieren Sie einen Steuerberater. "
            "Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the E1 form. "
            "Please carefully verify all values before submitting to FinanzOnline. "
            "For complex cases, consult a tax advisor. "
            "Not tax advice."
        ),
        "disclaimer_zh": (
            "\u6b64\u6570\u636e\u4ec5\u4f5c\u4e3aE1\u8868\u683c\u7684\u586b\u5199\u8f85\u52a9\u3002"
            "\u8bf7\u5728\u63d0\u4ea4\u5230FinanzOnline\u4e4b\u524d\u4ed4\u7ec6\u6838\u5b9e\u6240\u6709\u6570\u503c\u3002"
            "\u590d\u6742\u60c5\u51b5\u8bf7\u54a8\u8be2\u7a0e\u52a1\u987e\u95ee\u3002"
            "\u975e\u7a0e\u52a1\u5efa\u8bae\u3002"
        ),
        "finanzonline_url": "https://finanzonline.bmf.gv.at",
        "form_download_url": "https://www.oesterreich.gv.at/en/formsearch/form/125",
    }



def _generate_k1_form(
    user: User, transactions: list, tax_year: int
) -> Dict[str, Any]:
    """Generate K1 Koerperschaftsteuererklaerung form data for GmbH."""
    from app.services.koest_calculator import KoEstCalculator

    # All income is corporate revenue for GmbH
    total_revenue = sum(
        (t.amount or Decimal("0"))
        for t in transactions
        if t.type == TransactionType.INCOME
    )
    total_expenses = _sum_deductible_expenses(transactions)

    # Expense breakdowns
    personnel = _sum_by_expense_cat(transactions, [], deductible_only=True)  # placeholder
    material = _sum_by_expense_cat(
        transactions, [ExpenseCategory.GROCERIES, ExpenseCategory.OFFICE_SUPPLIES],
        deductible_only=True,
    )
    depreciation = _sum_by_expense_cat(
        transactions, [ExpenseCategory.DEPRECIATION, ExpenseCategory.EQUIPMENT],
        deductible_only=True,
    )
    rent_costs = _sum_by_expense_cat(
        transactions, [ExpenseCategory.RENT], deductible_only=True,
    )
    vehicle_costs = _sum_by_expense_cat(
        transactions, [ExpenseCategory.VEHICLE, ExpenseCategory.TRAVEL, ExpenseCategory.COMMUTING],
        deductible_only=True,
    )
    telecom_costs = _sum_by_expense_cat(
        transactions, [ExpenseCategory.TELECOM], deductible_only=True,
    )
    insurance_costs = _sum_by_expense_cat(
        transactions, [ExpenseCategory.INSURANCE], deductible_only=True,
    )
    professional_fees = _sum_by_expense_cat(
        transactions, [ExpenseCategory.PROFESSIONAL_SERVICES], deductible_only=True,
    )
    bank_fees = _sum_by_expense_cat(
        transactions, [ExpenseCategory.BANK_FEES], deductible_only=True,
    )
    interest = _sum_by_expense_cat(
        transactions, [ExpenseCategory.LOAN_INTEREST], deductible_only=True,
    )
    svs = _sum_by_expense_cat(
        transactions, [ExpenseCategory.SVS_CONTRIBUTIONS], deductible_only=True,
    )
    utilities = _sum_by_expense_cat(
        transactions, [ExpenseCategory.UTILITIES, ExpenseCategory.PROPERTY_TAX],
        deductible_only=True,
    )
    marketing = _sum_by_expense_cat(
        transactions, [ExpenseCategory.MARKETING], deductible_only=True,
    )

    # Corporate profit
    corporate_profit = total_revenue - total_expenses

    # VAT
    vat_collected = _sum_vat(transactions, TransactionType.INCOME)
    vat_paid = _sum_vat(transactions, TransactionType.EXPENSE)

    # Calculate KoeSt
    koest_calc = KoEstCalculator()
    koest_result = koest_calc.calculate(profit=corporate_profit)

    fields = [
        {
            "kz": "K010",
            "label_de": "Umsatzerloese (Betriebseinnahmen)",
            "label_en": "Revenue (Operating Income)",
            "label_zh": "营业收入",
            "value": float(total_revenue),
            "section": "ertraege",
            "editable": True,
        },
        {
            "kz": "K100",
            "label_de": "Materialaufwand",
            "label_en": "Material Expenses",
            "label_zh": "材料费用",
            "value": float(material),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K110",
            "label_de": "Abschreibungen (AfA)",
            "label_en": "Depreciation",
            "label_zh": "折旧",
            "value": float(depreciation),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K120",
            "label_de": "Mietaufwand",
            "label_en": "Rent Expenses",
            "label_zh": "租赁费用",
            "value": float(rent_costs),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K130",
            "label_de": "KFZ-Aufwand und Reisekosten",
            "label_en": "Vehicle and Travel Expenses",
            "label_zh": "车辆及差旅费用",
            "value": float(vehicle_costs),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K140",
            "label_de": "Nachrichtenaufwand (Telefon, Internet)",
            "label_en": "Telecommunications",
            "label_zh": "通讯费用",
            "value": float(telecom_costs),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K150",
            "label_de": "Versicherungsaufwand",
            "label_en": "Insurance Expenses",
            "label_zh": "保险费用",
            "value": float(insurance_costs),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K160",
            "label_de": "Rechts- und Beratungsaufwand",
            "label_en": "Legal and Consulting Fees",
            "label_zh": "法律及咨询费用",
            "value": float(professional_fees),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K170",
            "label_de": "Werbeaufwand",
            "label_en": "Advertising Expenses",
            "label_zh": "广告费用",
            "value": float(marketing),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K180",
            "label_de": "Betriebsnebenkosten (Strom, Wasser, Gas)",
            "label_en": "Utilities",
            "label_zh": "水电气费用",
            "value": float(utilities),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K190",
            "label_de": "Spesen des Geldverkehrs",
            "label_en": "Bank Charges",
            "label_zh": "银行手续费",
            "value": float(bank_fees),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K200",
            "label_de": "Zinsaufwand",
            "label_en": "Interest Expenses",
            "label_zh": "利息费用",
            "value": float(interest),
            "section": "aufwendungen",
            "editable": True,
        },
        {
            "kz": "K210",
            "label_de": "Sozialversicherungsbeitraege",
            "label_en": "Social Insurance Contributions",
            "label_zh": "社会保险缴费",
            "value": float(svs),
            "section": "aufwendungen",
            "editable": True,
        },
        # Profit and tax
        {
            "kz": "K400",
            "label_de": "Gewinn / Verlust vor Steuern",
            "label_en": "Profit / Loss before Tax",
            "label_zh": "税前利润/亏损",
            "value": float(corporate_profit),
            "section": "ergebnis",
            "editable": False,
        },
        {
            "kz": "K410",
            "label_de": "Koerperschaftsteuer (23%)",
            "label_en": "Corporate Income Tax (23%)",
            "label_zh": "公司所得税 (23%)",
            "value": float(koest_result.effective_koest),
            "section": "ergebnis",
            "editable": False,
        },
        {
            "kz": "K420",
            "label_de": "Mindeskoerperschaftsteuer",
            "label_en": "Minimum Corporate Tax",
            "label_zh": "最低公司税",
            "value": float(koest_result.mindest_koest),
            "section": "ergebnis",
            "editable": False,
            "note_de": "EUR 500/Quartal ab dem 5. Jahr nach Gruendung",
        },
        {
            "kz": "K430",
            "label_de": "Jahresueberschuss nach KoeSt",
            "label_en": "Net Profit after KoeSt",
            "label_zh": "税后净利润",
            "value": float(koest_result.profit_after_koest),
            "section": "ergebnis",
            "editable": False,
        },
        {
            "kz": "K440",
            "label_de": "KESt auf Gewinnausschuettung (27,5%)",
            "label_en": "Withholding Tax on Dividends (27.5%)",
            "label_zh": "股息预扣税 (27.5%)",
            "value": float(koest_result.kest_on_dividend),
            "section": "ausschuettung",
            "editable": True,
            "note_de": "Nur bei Ausschuettung an Gesellschafter",
        },
        {
            "kz": "K450",
            "label_de": "Netto-Ausschuettung an Gesellschafter",
            "label_en": "Net Dividend to Shareholders",
            "label_zh": "股东净分红",
            "value": float(koest_result.net_dividend),
            "section": "ausschuettung",
            "editable": False,
        },
    ]

    return {
        "form_type": "K1",
        "form_name_de": "Koerperschaftsteuererklaerung",
        "form_name_en": "Corporate Income Tax Return",
        "form_name_zh": "公司所得税申报表 (K1)",
        "tax_year": tax_year,
        "user_name": user.name or "",
        "tax_number": user.tax_number or "",
        "vat_number": user.vat_number or "",
        "generated_at": date.today().isoformat(),
        "fields": fields,
        "summary": {
            "total_revenue": float(total_revenue),
            "total_expenses": float(total_expenses),
            "corporate_profit": float(corporate_profit),
            "koest": float(koest_result.effective_koest),
            "koest_rate": 23.0,
            "mindest_koest": float(koest_result.mindest_koest),
            "profit_after_koest": float(koest_result.profit_after_koest),
            "kest_on_dividend": float(koest_result.kest_on_dividend),
            "net_dividend": float(koest_result.net_dividend),
            "total_tax_burden": float(koest_result.total_tax_burden),
            "effective_total_rate": float(koest_result.effective_total_rate),
            "vat_collected": float(vat_collected),
            "vat_paid": float(vat_paid),
            "vat_balance": float(vat_collected - vat_paid),
        },
        "disclaimer_de": (
            "Diese Daten dienen als Ausfuellhilfe fuer die Koerperschaftsteuererklaerung (K1). "
            "GmbH-Buchhaltung erfordert doppelte Buchfuehrung (Bilanzierung). "
            "Bitte konsultieren Sie einen Steuerberater fuer die endgueltige Einreichung. "
            "Keine Steuerberatung."
        ),
        "disclaimer_en": (
            "This data is a filling aid for the Corporate Tax Return (K1). "
            "GmbH accounting requires double-entry bookkeeping (Bilanzierung). "
            "Please consult a tax advisor for final submission. "
            "Not tax advice."
        ),
        "disclaimer_zh": (
            "本数据为公司所得税申报表 (K1) 的填写辅助。"
            "GmbH 必须采用复式记账法。"
            "请咨询税务顾问进行最终申报。"
            "非税务建议。"
        ),
        "finanzonline_url": "https://finanzonline.bmf.gv.at",
        "form_download_url": "https://www.bmf.gv.at/services/formulare/koerperschaftsteuer.html",
    }
