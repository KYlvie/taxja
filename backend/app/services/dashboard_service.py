"""
Dashboard Data Aggregation Service

Aggregates tax data for dashboard display including refund estimates,
savings suggestions, and tax calendar deadlines.
"""

from decimal import Decimal
from typing import Dict, Any, List
from datetime import datetime, date
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.document import Document, DocumentType
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus, PropertyType


# ---------------------------------------------------------------------------
# Localized text tables for suggestions (de / en / zh)
# ---------------------------------------------------------------------------
_SUGGESTION_TEXTS: Dict[str, Dict[str, str]] = {
    "de": {
        "home_office_title": "Home-Office-Pauschale",
        "home_office_desc": (
            "Sie haben noch keine Home-Office-Ausgaben erfasst. "
            "Wenn Sie von zu Hause arbeiten, können Sie bis zu €300/Jahr absetzen. "
            "Laden Sie einen Beleg hoch (z.B. Internetrechnung, Büromaterial) "
            "oder erfassen Sie die Ausgabe manuell."
        ),
        "home_office_action": "Ausgabe erfassen",
        "pendler_title": "Pendlerpauschale",
        "pendler_desc": (
            "Keine Fahrtkosten erfasst. Wenn Ihr Arbeitsweg mindestens 2 km beträgt, "
            "steht Ihnen eine Pendlerpauschale zu. "
            "Erfassen Sie Ihre Fahrtkosten als Ausgabe mit Kategorie 'Pendlerpauschale'."
        ),
        "pendler_action": "Fahrtkosten erfassen",
        "insurance_title": "Versicherungsprämien",
        "insurance_desc": (
            "Keine Versicherungsausgaben erfasst. Wenn Sie private Versicherungen "
            "(z.B. Unfallversicherung, Lebensversicherung) bezahlen, können diese "
            "teilweise steuerlich absetzbar sein. Laden Sie Ihre Versicherungspolizze hoch."
        ),
        "insurance_action": "Versicherung erfassen",
        "review_title": "Nicht abzugsfähige Ausgaben prüfen",
        "review_desc": (
            "Sie haben {amount} an nicht abzugsfähigen Ausgaben. "
            "Einige davon könnten mit entsprechenden Belegen absetzbar sein. "
            "Prüfen Sie diese Ausgaben und laden Sie fehlende Belege hoch."
        ),
        "review_action": "Ausgaben prüfen",
        "ocr_title": "OCR-Ergebnisse prüfen",
        "ocr_desc": (
            "{count} Dokument(e) wurden nicht korrekt erkannt. "
            "Bitte überprüfen und korrigieren Sie die erkannten Daten manuell."
        ),
        "ocr_action": "Dokumente prüfen",
        "getting_started_title": "Erste Transaktion hinzufügen",
        "getting_started_desc": (
            "Laden Sie Belege, Rechnungen oder Lohnzettel hoch, um zu starten. "
            "Sie können auch manuell Einnahmen und Ausgaben erfassen."
        ),
        "getting_started_action": "Beleg hochladen",
    },
    "en": {
        "home_office_title": "Home Office Deduction",
        "home_office_desc": (
            "No home office expenses recorded yet. "
            "If you work from home, you may deduct up to €300/year. "
            "Upload a receipt (e.g. internet bill, office supplies) "
            "or add the expense manually."
        ),
        "home_office_action": "Add expense",
        "pendler_title": "Commuter Allowance (Pendlerpauschale)",
        "pendler_desc": (
            "No commuting expenses recorded. If your commute is at least 2 km, "
            "you may be eligible for a commuter allowance. "
            "Add your commuting costs as an expense under 'Commuting'."
        ),
        "pendler_action": "Add commuting costs",
        "insurance_title": "Insurance Premiums",
        "insurance_desc": (
            "No insurance expenses recorded. If you pay private insurance "
            "(e.g. accident, life insurance), these may be partially tax-deductible. "
            "Upload your insurance policy or add the expense."
        ),
        "insurance_action": "Add insurance",
        "review_title": "Review Non-Deductible Expenses",
        "review_desc": (
            "You have {amount} in non-deductible expenses. "
            "Some may qualify for deduction with proper documentation. "
            "Review these expenses and upload missing receipts."
        ),
        "review_action": "Review expenses",
        "ocr_title": "Review OCR Results",
        "ocr_desc": (
            "{count} document(s) were not recognized correctly. "
            "Please review and correct the extracted data manually."
        ),
        "ocr_action": "Review documents",
        "getting_started_title": "Add Your First Transaction",
        "getting_started_desc": (
            "Upload receipts, invoices, or payslips to get started. "
            "You can also manually add income and expenses."
        ),
        "getting_started_action": "Upload receipt",
    },
    "zh": {
        "home_office_title": "居家办公扣除",
        "home_office_desc": (
            "您尚未记录居家办公费用。"
            "如果您在家工作，每年最多可扣除 €300。"
            "请上传相关凭证（如网费账单、办公用品发票）或手动添加支出。"
        ),
        "home_office_action": "记录支出",
        "pendler_title": "通勤补贴 (Pendlerpauschale)",
        "pendler_desc": (
            "未记录通勤费用。如果您的通勤距离至少 2 公里，"
            "可以申请通勤补贴。请在支出中添加通勤费用，类别选择「通勤」。"
        ),
        "pendler_action": "记录通勤费",
        "insurance_title": "保险费",
        "insurance_desc": (
            "未记录保险费用。如果您有私人保险（如意外险、人寿险），"
            "部分保费可以抵税。请上传保险单或手动添加保险支出。"
        ),
        "insurance_action": "记录保险费",
        "review_title": "检查不可扣除支出",
        "review_desc": (
            "您有 {amount} 的不可扣除支出。"
            "其中部分可能在上传凭证后可以扣除。请检查这些支出并补充凭证。"
        ),
        "review_action": "检查支出",
        "ocr_title": "检查文档识别结果",
        "ocr_desc": "{count} 份文档识别不准确，请手动检查并修正识别结果。",
        "ocr_action": "检查文档",
        "getting_started_title": "添加您的第一笔交易",
        "getting_started_desc": (
            "上传收据、发票或工资单即可开始。"
            "您也可以手动添加收入和支出。"
        ),
        "getting_started_action": "上传凭证",
    },
}

# ---------------------------------------------------------------------------
# Document completeness: required docs per user_type
# Each entry: (DocumentType, i18n_key, priority, needs_history)
#   needs_history=True → only show if user already has transactions (not a new user)
# ---------------------------------------------------------------------------
_REQUIRED_DOCS: Dict[str, List[tuple]] = {
    "employee": [
        (DocumentType.LOHNZETTEL, "missing_lohnzettel", "high", False),
    ],
    "self_employed": [
        (DocumentType.E1_FORM, "missing_e1", "high", True),
        (DocumentType.SVS_NOTICE, "missing_svs", "high", False),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
    "landlord": [
        (DocumentType.PURCHASE_CONTRACT, "missing_kaufvertrag", "high", False),
        (DocumentType.RENTAL_CONTRACT, "missing_mietvertrag", "high", False),
    ],
    "mixed": [
        (DocumentType.LOHNZETTEL, "missing_lohnzettel", "high", False),
        (DocumentType.E1_FORM, "missing_e1", "medium", True),
        (DocumentType.SVS_NOTICE, "missing_svs", "medium", False),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
    "gmbh": [
        (DocumentType.E1_FORM, "missing_e1", "high", True),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
}

# Localized texts for missing-document suggestions
_DOC_COMPLETENESS_TEXTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "de": {
        "missing_lohnzettel": {
            "title": "Lohnzettel fehlt",
            "desc": "Bitte laden Sie Ihren Lohnzettel (L16) hoch, damit wir Ihre Lohneinkünfte korrekt berechnen können.",
            "action": "Lohnzettel hochladen",
        },
        "missing_bescheid": {
            "title": "Einkommensteuerbescheid fehlt",
            "desc": "Laden Sie Ihren letzten Einkommensteuerbescheid hoch, um Verlustvorträge und historische Daten zu erfassen.",
            "action": "Bescheid hochladen",
        },
        "missing_e1": {
            "title": "E1-Erklärung fehlt",
            "desc": "Bitte laden Sie Ihre letzte E1-Steuererklärung hoch, damit wir Ihre Einkommenssituation vollständig erfassen.",
            "action": "E1 hochladen",
        },
        "missing_svs": {
            "title": "SVS-Bescheid fehlt",
            "desc": "Laden Sie Ihren SVS-Beitragsbescheid hoch, um Sozialversicherungsbeiträge korrekt zu berücksichtigen.",
            "action": "SVS hochladen",
        },
        "missing_kaufvertrag": {
            "title": "Kaufvertrag fehlt",
            "desc": "Bitte laden Sie den Kaufvertrag Ihrer Immobilie hoch, um AfA und Anschaffungskosten zu berechnen.",
            "action": "Kaufvertrag hochladen",
        },
        "missing_mietvertrag": {
            "title": "Mietvertrag fehlt",
            "desc": "Laden Sie Ihren Mietvertrag hoch, damit wir Mieteinnahmen und Werbungskosten korrekt zuordnen können.",
            "action": "Mietvertrag hochladen",
        },
        "conflict_title": "Datenabweichung erkannt",
        "conflict_desc": (
            "Der Einkommensteuerbescheid weist {bescheid_amount} aus, "
            "aber Ihre erfassten Transaktionen ergeben {txn_amount}. "
            "Bitte prüfen Sie die Daten — der Bescheid hat Vorrang."
        ),
    },
    "en": {
        "missing_lohnzettel": {
            "title": "Wage Tax Certificate Missing",
            "desc": "Please upload your Lohnzettel (L16) so we can accurately calculate your employment income.",
            "action": "Upload Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Tax Assessment Missing",
            "desc": "Upload your latest Einkommensteuerbescheid to capture loss carryforwards and historical data.",
            "action": "Upload Bescheid",
        },
        "missing_e1": {
            "title": "E1 Tax Return Missing",
            "desc": "Please upload your last E1 tax return so we can fully capture your income situation.",
            "action": "Upload E1",
        },
        "missing_svs": {
            "title": "SVS Notice Missing",
            "desc": "Upload your SVS contribution notice to correctly account for social insurance contributions.",
            "action": "Upload SVS",
        },
        "missing_kaufvertrag": {
            "title": "Purchase Contract Missing",
            "desc": "Please upload your property purchase contract to calculate depreciation and acquisition costs.",
            "action": "Upload contract",
        },
        "missing_mietvertrag": {
            "title": "Rental Contract Missing",
            "desc": "Upload your rental contract so we can correctly allocate rental income and deductible expenses.",
            "action": "Upload contract",
        },
        "conflict_title": "Data Discrepancy Detected",
        "conflict_desc": (
            "The tax assessment shows {bescheid_amount}, "
            "but your recorded transactions total {txn_amount}. "
            "Please review — the Bescheid takes priority."
        ),
    },
    "zh": {
        "missing_lohnzettel": {
            "title": "缺少工资单 (Lohnzettel)",
            "desc": "请上传您的工资单 (L16)，以便我们准确计算您的工资收入。",
            "action": "上传工资单",
        },
        "missing_bescheid": {
            "title": "缺少所得税评估通知",
            "desc": "请上传您最近的所得税评估通知 (Einkommensteuerbescheid)，以获取亏损结转和历史数据。",
            "action": "上传评估通知",
        },
        "missing_e1": {
            "title": "缺少 E1 税务申报表",
            "desc": "请上传您上一年的 E1 税务申报表，以便我们完整掌握您的收入情况。",
            "action": "上传 E1",
        },
        "missing_svs": {
            "title": "缺少 SVS 社保通知",
            "desc": "请上传您的 SVS 缴费通知，以便正确计算社会保险费用。",
            "action": "上传 SVS",
        },
        "missing_kaufvertrag": {
            "title": "缺少购房合同",
            "desc": "请上传您的房产购买合同 (Kaufvertrag)，以便计算折旧和购置成本。",
            "action": "上传购房合同",
        },
        "missing_mietvertrag": {
            "title": "缺少租赁合同",
            "desc": "请上传您的租赁合同 (Mietvertrag)，以便正确分配租金收入和可扣除费用。",
            "action": "上传租赁合同",
        },
        "conflict_title": "检测到数据差异",
        "conflict_desc": (
            "所得税评估通知显示收入为 {bescheid_amount}，"
            "但您已录入的交易合计为 {txn_amount}。"
            "请核实数据 — 以评估通知 (Bescheid) 为准。"
        ),
    },
}

# ---------------------------------------------------------------------------
# Localized text tables for calendar deadlines (de / en / zh)
# ---------------------------------------------------------------------------
_CALENDAR_TEXTS: Dict[str, List[Dict[str, str]]] = {
    "de": [
        {
            "title": "Einkommensteuererklärung (Papier)",
            "description": "Frist für die Abgabe der Steuererklärung in Papierform",
        },
        {
            "title": "Einkommensteuererklärung (FinanzOnline)",
            "description": "Frist für die elektronische Steuererklärung über FinanzOnline",
        },
        {
            "title": "Umsatzsteuervoranmeldung (UVA) Januar",
            "description": "Monatliche USt-Voranmeldung für Januar",
        },
        {
            "title": "Lohnzettel Übermittlung",
            "description": "Arbeitgeber muss die jährlichen Lohnzettel übermitteln",
        },
        {
            "title": "SVS Beitragsgrundlage",
            "description": "Frist für die SVS-Beitragsgrundlagenmeldung",
        },
        {
            "title": "Arbeitnehmerveranlagung (Frist)",
            "description": "Verlängerte Frist für die Arbeitnehmerveranlagung (mit Steuerberater)",
        },
    ],
    "en": [
        {
            "title": "Income Tax Return (Paper)",
            "description": "Deadline for paper tax return submission",
        },
        {
            "title": "Income Tax Return (FinanzOnline)",
            "description": "Deadline for electronic tax return via FinanzOnline",
        },
        {
            "title": "VAT Advance Return (UVA) January",
            "description": "Monthly VAT advance return for January",
        },
        {
            "title": "Wage Tax Certificate Submission",
            "description": "Employer must submit annual wage tax certificates",
        },
        {
            "title": "SVS Contribution Base",
            "description": "SVS contribution base declaration deadline",
        },
        {
            "title": "Employee Tax Assessment (Extended)",
            "description": "Extended deadline for employee tax assessment (with tax advisor)",
        },
    ],
    "zh": [
        {
            "title": "所得税申报（纸质）",
            "description": "纸质税务申报截止日期",
        },
        {
            "title": "所得税申报（FinanzOnline）",
            "description": "通过 FinanzOnline 电子申报截止日期",
        },
        {
            "title": "增值税预申报 (UVA) 一月",
            "description": "一月份增值税月度预申报",
        },
        {
            "title": "工资单提交",
            "description": "雇主须提交年度工资税证明",
        },
        {
            "title": "SVS 缴费基数",
            "description": "SVS 社保缴费基数申报截止日期",
        },
        {
            "title": "雇员税务评估（延期）",
            "description": "雇员税务评估延期截止日期（需税务顾问）",
        },
    ],
}


class DashboardService:
    """Aggregates dashboard data"""

    def __init__(self, db: Session):
        self.db = db
        self._redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize synchronous Redis client for caching"""
        try:
            from app.core.config import settings
            import redis
            
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self._redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}. Caching disabled.")
            self._redis_client = None
    
    def _get_cached_portfolio_metrics(self, user_id: int, year: int):
        """Get cached portfolio metrics from Redis"""
        if not self._redis_client:
            return None
        
        try:
            import json
            cache_key = f"portfolio_metrics:{user_id}:{year}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                # Convert string values back to Decimal
                return {
                    "has_properties": data["has_properties"],
                    "active_properties_count": data["active_properties_count"],
                    "total_rental_income": Decimal(str(data["total_rental_income"])),
                    "total_property_expenses": Decimal(str(data["total_property_expenses"])),
                    "net_rental_income": Decimal(str(data["net_rental_income"])),
                    "total_building_value": Decimal(str(data["total_building_value"])),
                    "total_annual_depreciation": Decimal(str(data["total_annual_depreciation"]))
                }
            return None
        except Exception as e:
            print(f"Cache get error for portfolio metrics user {user_id}, year {year}: {e}")
            return None
    
    def _set_cached_portfolio_metrics(self, user_id: int, year: int, metrics: dict):
        """Set cached portfolio metrics in Redis with 1 hour TTL"""
        if not self._redis_client:
            return False
        
        try:
            import json
            cache_key = f"portfolio_metrics:{user_id}:{year}"
            # Convert Decimal to string for JSON serialization
            cache_data = {
                "has_properties": metrics["has_properties"],
                "active_properties_count": metrics["active_properties_count"],
                "total_rental_income": str(metrics["total_rental_income"]),
                "total_property_expenses": str(metrics["total_property_expenses"]),
                "net_rental_income": str(metrics["net_rental_income"]),
                "total_building_value": str(metrics["total_building_value"]),
                "total_annual_depreciation": str(metrics["total_annual_depreciation"])
            }
            
            # Cache for 1 hour (3600 seconds)
            self._redis_client.setex(cache_key, 3600, json.dumps(cache_data))
            return True
        except Exception as e:
            print(f"Cache set error for portfolio metrics user {user_id}, year {year}: {e}")
            return False

    def get_dashboard_data(self, user_id: int, tax_year: int, user: User = None) -> Dict[str, Any]:
        """Get comprehensive dashboard data matching frontend expectations."""
        transactions = (
            self.db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .all()
        )

        total_income = sum(
            (t.amount for t in transactions if t.type == TransactionType.INCOME),
            Decimal("0"),
        )
        total_expenses = sum(
            (t.amount for t in transactions if t.type == TransactionType.EXPENSE),
            Decimal("0"),
        )
        deductible_expenses = sum(
            (
                t.deductible_amount
                for t in transactions
                if t.type == TransactionType.EXPENSE
            ),
            Decimal("0"),
        )

        net_income = total_income - total_expenses

        # --- Determine if GmbH user ---
        is_gmbh = False
        if user and user.user_type:
            ut = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
            is_gmbh = ut == "gmbh"

        if is_gmbh:
            # GmbH: Körperschaftsteuer 23% flat rate
            from app.services.koest_calculator import KoEstCalculator
            koest_calc = KoEstCalculator()
            koest_result = koest_calc.calculate(profit=net_income)
            estimated_tax = koest_result.effective_koest
        else:
            # Load tax brackets from DB (TaxConfiguration table)
            from app.models.tax_configuration import TaxConfiguration
            tax_config = (
                self.db.query(TaxConfiguration)
                .filter(TaxConfiguration.tax_year == tax_year)
                .first()
            )

            if tax_config and tax_config.tax_brackets:
                # Brackets already include the 0% band (exemption).
                # Apply progressive brackets directly to net_income.
                gross = max(Decimal("0"), net_income)
                db_brackets = tax_config.tax_brackets
                estimated_tax = Decimal("0")
                for b in db_brackets:
                    lower = Decimal(str(b.get("lower", b.get("min", 0))))
                    upper_raw = b.get("upper", b.get("max"))
                    rate = Decimal(str(b["rate"]))
                    if rate > 1:
                        rate = rate / Decimal("100")
                    if gross <= lower:
                        break
                    if upper_raw is not None:
                        upper = Decimal(str(upper_raw))
                        taxable_in_bracket = min(gross, upper) - lower
                    else:
                        taxable_in_bracket = gross - lower
                    if taxable_in_bracket > 0:
                        estimated_tax += taxable_in_bracket * rate
            else:
                # Fallback: 2026 hardcoded brackets if no DB config
                taxable_income = max(Decimal("0"), net_income - Decimal("13539"))
                brackets = [
                    (Decimal("0"), Decimal("8453"), Decimal("0.20")),
                    (Decimal("8453"), Decimal("14466"), Decimal("0.30")),
                    (Decimal("14466"), Decimal("33907"), Decimal("0.40")),
                    (Decimal("33907"), Decimal("34494"), Decimal("0.48")),
                    (Decimal("34494"), Decimal("895141"), Decimal("0.50")),
                    (Decimal("895141"), None, Decimal("0.55")),
                ]
                estimated_tax = Decimal("0")
                remaining = taxable_income
                for lower, upper, rate in brackets:
                    if remaining <= 0:
                        break
                    width = (upper - lower) if upper else remaining
                    chunk = min(remaining, width)
                    estimated_tax += chunk * rate
                    remaining -= chunk

        # --- Employee refund estimate (not applicable for GmbH) ---
        if is_gmbh:
            has_lohnzettel = False
            withheld_tax = 0.0
            calculated_tax = float(estimated_tax)
            estimated_refund = None
        else:
            employment_income = sum(
                (t.amount for t in transactions
                 if t.type == TransactionType.INCOME
                 and t.income_category == IncomeCategory.EMPLOYMENT),
                Decimal("0"),
            )
            has_lohnzettel = employment_income > 0
            withheld_tax = float(employment_income * Decimal("0.30")) if has_lohnzettel else 0.0
            calculated_tax = float(estimated_tax)
            estimated_refund = withheld_tax - calculated_tax if has_lohnzettel else None

        # Estimate paid tax based on months elapsed
        now = datetime.now()
        if now.year == tax_year:
            months_elapsed = now.month
            paid_tax = (estimated_tax / 12) * months_elapsed
        else:
            paid_tax = estimated_tax

        remaining_tax = max(Decimal("0"), estimated_tax - paid_tax)

        # VAT threshold distance (Kleinunternehmerregelung)
        # Only relevant for self-employed / business / mixed users
        user_type_val = ""
        if user and user.user_type:
            user_type_val = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        is_vat_relevant = user_type_val in ("self_employed", "mixed", "small_business")

        if is_vat_relevant:
            # Read threshold from DB TaxConfiguration
            from app.models.tax_configuration import TaxConfiguration as TC
            tc = (
                self.db.query(TC)
                .filter(TC.tax_year == tax_year)
                .first()
            )
            if tc and tc.vat_rates and isinstance(tc.vat_rates, dict):
                vat_threshold = Decimal(str(tc.vat_rates.get("small_business_threshold", 55000)))
            else:
                # Fallback
                vat_threshold = Decimal("55000") if tax_year >= 2025 else Decimal("35000")
            vat_distance = float(vat_threshold - total_income)
        else:
            vat_distance = None

        # Monthly trends
        monthly_income: Dict[int, float] = defaultdict(float)
        monthly_expenses: Dict[int, float] = defaultdict(float)
        for t in transactions:
            month = t.transaction_date.month
            if t.type == TransactionType.INCOME:
                monthly_income[month] += float(t.amount)
            else:
                monthly_expenses[month] += float(t.amount)

        monthly_data = []
        for month in range(1, 13):
            monthly_data.append({
                "month": month,
                "income": monthly_income.get(month, 0.0),
                "expenses": monthly_expenses.get(month, 0.0),
            })

        # Category breakdowns for charts
        income_by_cat: Dict[str, float] = defaultdict(float)
        expense_by_cat: Dict[str, float] = defaultdict(float)
        for t in transactions:
            if t.type == TransactionType.INCOME and t.income_category:
                cat = (
                    t.income_category.value
                    if hasattr(t.income_category, "value")
                    else str(t.income_category)
                )
                income_by_cat[cat] += float(t.amount)
            elif t.type == TransactionType.EXPENSE:
                # Use line-item-aware aggregation for expenses
                if t.has_line_items:
                    for li in t.line_items:
                        cat = li.category or "other"
                        expense_by_cat[cat] += float(li.amount * li.quantity)
                elif t.expense_category:
                    cat = (
                        t.expense_category.value
                        if hasattr(t.expense_category, "value")
                        else str(t.expense_category)
                    )
                    expense_by_cat[cat] += float(t.amount)

        income_category_data = [{"category": k, "amount": v} for k, v in income_by_cat.items()]
        expense_category_data = [{"category": k, "amount": v} for k, v in expense_by_cat.items()]

        # Count transactions needing review
        pending_review_count = sum(
            1 for t in transactions
            if getattr(t, 'needs_review', False) and not getattr(t, 'reviewed', False)
        )

        result = {
            "yearToDateIncome": float(total_income),
            "yearToDateExpenses": float(total_expenses),
            "deductibleExpenses": float(deductible_expenses),
            "estimatedTax": float(estimated_tax),
            "paidTax": float(paid_tax),
            "remainingTax": float(remaining_tax),
            "netIncome": float(net_income),
            "vatThresholdDistance": vat_distance,
            "pendingReviewCount": pending_review_count,
            "monthlyData": monthly_data,
            "incomeCategoryData": income_category_data,
            "expenseCategoryData": expense_category_data,
            "taxYear": tax_year,
            # Refund estimate fields for RefundEstimate component
            "estimatedRefund": estimated_refund,
            "withheldTax": withheld_tax if has_lohnzettel else None,
            "calculatedTax": calculated_tax if has_lohnzettel else None,
            "hasLohnzettel": has_lohnzettel,
            # GmbH-specific fields
            "isGmbH": is_gmbh,
        }

        if is_gmbh:
            from app.services.koest_calculator import KoEstCalculator
            koest_calc = KoEstCalculator()
            koest_result = koest_calc.calculate(profit=net_income)
            result["gmbhTax"] = {
                "koest": float(koest_result.effective_koest),
                "koestRate": float(koest_result.koest_rate),
                "mindestKoest": float(koest_result.mindest_koest),
                "profitAfterKoest": float(koest_result.profit_after_koest),
                "kestOnDividend": float(koest_result.kest_on_dividend),
                "netDividend": float(koest_result.net_dividend),
                "totalTaxBurden": float(koest_result.total_tax_burden),
                "effectiveTotalRate": float(koest_result.effective_total_rate),
            }

        return result

    def get_suggestions(
        self, user_id: int, tax_year: int, language: str = "de"
    ) -> Dict[str, Any]:
        """Generate localized savings suggestions based on user's transaction data."""
        transactions = (
            self.db.query(Transaction)
            .filter(
                Transaction.user_id == user_id,
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .all()
        )

        suggestions: List[Dict[str, Any]] = []

        total_expenses = sum(
            float(t.amount) for t in transactions if t.type == TransactionType.EXPENSE
        )
        deductible = sum(
            float(t.amount)
            for t in transactions
            if t.type == TransactionType.EXPENSE and t.is_deductible
        )
        non_deductible = total_expenses - deductible

        expense_cats = {
            (
                t.expense_category.value
                if hasattr(t.expense_category, "value")
                else str(t.expense_category)
            )
            for t in transactions
            if t.type == TransactionType.EXPENSE and t.expense_category
        }

        texts = _SUGGESTION_TEXTS.get(language, _SUGGESTION_TEXTS["de"])

        if "home_office" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["home_office_title"],
                "description": texts["home_office_desc"],
                "potential_savings": 300.0,
                "priority": "high",
                "action_url": "/transactions?action=add&category=home_office&type=expense",
                "action_label": texts["home_office_action"],
            })

        if "commuting" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["pendler_title"],
                "description": texts["pendler_desc"],
                "potential_savings": 500.0,
                "priority": "high",
                "action_url": "/transactions?action=add&category=commuting&type=expense",
                "action_label": texts["pendler_action"],
            })

        if "insurance" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["insurance_title"],
                "description": texts["insurance_desc"],
                "potential_savings": 200.0,
                "priority": "medium",
                "action_url": "/transactions?action=add&category=insurance&type=expense",
                "action_label": texts["insurance_action"],
            })

        if non_deductible > 100:
            suggestions.append({
                "type": "review_needed",
                "title": texts["review_title"],
                "description": texts["review_desc"].format(
                    amount=f"€{non_deductible:,.2f}"
                ),
                "potential_savings": non_deductible * 0.1,
                "priority": "medium",
                "action_url": "/transactions?filter=non_deductible",
                "action_label": texts["review_action"],
            })

        # Check for documents needing review
        docs_needing_review = (
            self.db.query(Document)
            .filter(
                Document.user_id == user_id,
                Document.confidence_score < 0.7,
                Document.confidence_score > 0,
            )
            .count()
        )
        if docs_needing_review > 0:
            suggestions.append({
                "type": "action_needed",
                "title": texts["ocr_title"],
                "description": texts["ocr_desc"].format(count=docs_needing_review),
                "potential_savings": 0,
                "priority": "high",
                "action_url": "/documents?filter=needs_review",
                "action_label": texts["ocr_action"],
            })

        if not transactions:
            suggestions.append({
                "type": "getting_started",
                "title": texts["getting_started_title"],
                "description": texts["getting_started_desc"],
                "potential_savings": 0,
                "priority": "high",
                "action_url": "/documents",
                "action_label": texts["getting_started_action"],
            })

        # --- Document completeness check ---
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            ut = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
            required = _REQUIRED_DOCS.get(ut, [])
            doc_texts = _DOC_COMPLETENESS_TEXTS.get(language, _DOC_COMPLETENESS_TEXTS["de"])

            # Previous tax year docs (we need last year's data for this year's calc)
            prev_year = tax_year - 1
            uploaded_types = set(
                row[0]
                for row in self.db.query(Document.document_type)
                .filter(Document.user_id == user_id)
                .all()
            )

            # Check if user has any historical transactions (not a brand-new user)
            has_history = bool(transactions) or (
                self.db.query(Transaction.id)
                .filter(
                    Transaction.user_id == user_id,
                    extract("year", Transaction.transaction_date) == prev_year,
                )
                .first()
            )

            for doc_type, text_key, priority, needs_history in required:
                if needs_history and not has_history:
                    continue
                if doc_type not in uploaded_types:
                    entry = doc_texts.get(text_key, {})
                    if entry:
                        suggestions.append({
                            "type": "missing_document",
                            "title": entry["title"],
                            "description": entry["desc"],
                            "document_type": doc_type.value,
                            "potential_savings": 0,
                            "priority": priority,
                            "action_url": "/documents",
                            "action_label": entry.get("action", None),
                        })

            # --- Data conflict detection (Bescheid vs Lohnzettel transactions) ---
            bescheid_docs = (
                self.db.query(Document)
                .filter(
                    Document.user_id == user_id,
                    Document.document_type == DocumentType.EINKOMMENSTEUERBESCHEID,
                    Document.ocr_result.isnot(None),
                )
                .all()
            )
            for bdoc in bescheid_docs:
                ocr = bdoc.ocr_result or {}
                hist = ocr.get("historical_tax_data", {})
                bescheid_year = hist.get("tax_year")
                bescheid_income = hist.get("total_income") or hist.get("kz_245")
                if bescheid_year and bescheid_income is not None:
                    try:
                        bescheid_amt = float(bescheid_income)
                    except (ValueError, TypeError):
                        continue
                    # Sum employment income transactions for that year
                    txn_total = (
                        self.db.query(func.sum(Transaction.amount))
                        .filter(
                            Transaction.user_id == user_id,
                            Transaction.type == TransactionType.INCOME,
                            extract("year", Transaction.transaction_date) == int(bescheid_year),
                        )
                        .scalar()
                    )
                    txn_amt = float(txn_total) if txn_total else 0.0
                    # Flag if difference > 5%
                    if bescheid_amt > 0 and abs(txn_amt - bescheid_amt) / bescheid_amt > 0.05:
                        suggestions.append({
                            "type": "data_conflict",
                            "title": doc_texts["conflict_title"],
                            "description": doc_texts["conflict_desc"].format(
                                bescheid_amount=f"€{bescheid_amt:,.2f}",
                                txn_amount=f"€{txn_amt:,.2f}",
                            ),
                            "tax_year_affected": int(bescheid_year),
                            "bescheid_amount": bescheid_amt,
                            "transaction_amount": txn_amt,
                            "potential_savings": 0,
                            "priority": "high",
                            "action_url": "/transactions",
                            "action_label": None,
                        })

        total_potential = sum(s.get("potential_savings", 0) for s in suggestions)

        return {
            "tax_year": tax_year,
            "suggestions": suggestions,
            "total_potential_savings": total_potential,
        }

    def detect_active_income_types(
        self, user_id: int, tax_year: int, language: str = "de"
    ) -> Dict[str, Any]:
        """Detect income types from transactions and compare with user's declared user_type."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"detected": [], "suggestions": [], "user_type": None}

        ut = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)

        rows = (
            self.db.query(
                Transaction.income_category,
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.income_category.isnot(None),
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .group_by(Transaction.income_category)
            .all()
        )

        detected: List[Dict[str, Any]] = []
        for row in rows:
            cat = row[0].value if hasattr(row[0], "value") else str(row[0])
            detected.append({"category": cat, "amount": float(row[1])})

        _CAT_TO_TYPES: Dict[str, List[str]] = {
            "agriculture": ["self_employed", "mixed"],
            "self_employment": ["self_employed", "mixed"],
            "business": ["self_employed", "mixed", "gmbh"],
            "employment": ["employee", "mixed"],
            "rental": ["landlord", "mixed"],
        }

        _HINT_TEXTS: Dict[str, Dict[str, str]] = {
            "de": {
                "agriculture": 'Wir haben Eink\u00fcnfte aus Land- und Forstwirtschaft erkannt. Erw\u00e4gen Sie, Ihr Profil auf "Selbstst\u00e4ndig" oder "Gemischt" zu aktualisieren.',
                "self_employment": 'Wir haben Eink\u00fcnfte aus selbst\u00e4ndiger Arbeit erkannt. Erw\u00e4gen Sie, Ihr Profil auf "Selbstst\u00e4ndig" oder "Gemischt" zu aktualisieren.',
                "business": 'Wir haben gewerbliche Eink\u00fcnfte erkannt. Erw\u00e4gen Sie, Ihr Profil auf "Selbstst\u00e4ndig" oder "Gemischt" zu aktualisieren.',
                "employment": 'Wir haben Eink\u00fcnfte aus nichtselbst\u00e4ndiger Arbeit erkannt. Erw\u00e4gen Sie, Ihr Profil auf "Angestellt" oder "Gemischt" zu aktualisieren.',
                "rental": 'Wir haben Eink\u00fcnfte aus Vermietung und Verpachtung erkannt. Erw\u00e4gen Sie, Ihr Profil auf "Vermieter" oder "Gemischt" zu aktualisieren.',
            },
            "en": {
                "agriculture": "We detected agriculture/forestry income. Consider updating your profile to 'Self-Employed' or 'Mixed'.",
                "self_employment": "We detected self-employment income. Consider updating your profile to 'Self-Employed' or 'Mixed'.",
                "business": "We detected business income. Consider updating your profile to 'Self-Employed' or 'Mixed'.",
                "employment": "We detected employment income. Consider updating your profile to 'Employee' or 'Mixed'.",
                "rental": "We detected rental income. Consider updating your profile to 'Landlord' or 'Mixed'.",
            },
            "zh": {
                "agriculture": "\u6211\u4eec\u68c0\u6d4b\u5230\u60a8\u6709\u519c\u6797\u4e1a\u6536\u5165\u3002\u5efa\u8bae\u5c06\u8eab\u4efd\u66f4\u65b0\u4e3a\u300c\u4e2a\u4f53\u6237\u300d\u6216\u300c\u6df7\u5408\u8eab\u4efd\u300d\u3002",
                "self_employment": "\u6211\u4eec\u68c0\u6d4b\u5230\u60a8\u6709\u81ea\u7531\u804c\u4e1a\u6536\u5165\u3002\u5efa\u8bae\u5c06\u8eab\u4efd\u66f4\u65b0\u4e3a\u300c\u4e2a\u4f53\u6237\u300d\u6216\u300c\u6df7\u5408\u8eab\u4efd\u300d\u3002",
                "business": "\u6211\u4eec\u68c0\u6d4b\u5230\u60a8\u6709\u5de5\u5546\u8425\u4e1a\u6536\u5165\u3002\u5efa\u8bae\u5c06\u8eab\u4efd\u66f4\u65b0\u4e3a\u300c\u4e2a\u4f53\u6237\u300d\u6216\u300c\u6df7\u5408\u8eab\u4efd\u300d\u3002",
                "employment": "\u6211\u4eec\u68c0\u6d4b\u5230\u60a8\u6709\u5de5\u8d44\u6536\u5165\u3002\u5efa\u8bae\u5c06\u8eab\u4efd\u66f4\u65b0\u4e3a\u300c\u804c\u5458\u300d\u6216\u300c\u6df7\u5408\u8eab\u4efd\u300d\u3002",
                "rental": "\u6211\u4eec\u68c0\u6d4b\u5230\u60a8\u6709\u79df\u91d1\u6536\u5165\u3002\u5efa\u8bae\u5c06\u8eab\u4efd\u66f4\u65b0\u4e3a\u300c\u623f\u4e1c\u300d\u6216\u300c\u6df7\u5408\u8eab\u4efd\u300d\u3002",
            },
        }

        texts = _HINT_TEXTS.get(language, _HINT_TEXTS["de"])
        suggestions: List[Dict[str, str]] = []

        for d in detected:
            cat = d["category"]
            required_types = _CAT_TO_TYPES.get(cat)
            if required_types is None:
                continue
            if ut not in required_types:
                suggestions.append({
                    "category": cat,
                    "message": texts.get(cat, ""),
                    "suggested_types": required_types,
                })

        return {
            "user_type": ut,
            "tax_year": tax_year,
            "detected": detected,
            "suggestions": suggestions,
        }

    def get_calendar(
        self, tax_year: int, language: str = "de"
    ) -> Dict[str, Any]:
        """Return localized Austrian tax calendar deadlines."""
        year = tax_year or datetime.now().year

        cal_texts = _CALENDAR_TEXTS.get(language, _CALENDAR_TEXTS["de"])

        # Each entry maps to a fixed date + the localized title/description
        date_specs = [
            f"{year}-03-31",
            f"{year}-06-30",
            f"{year}-02-15",
            f"{year}-02-28",
            f"{year}-03-31",
            f"{year}-09-30",
        ]
        type_specs = ["deadline", "deadline", "vat", "info", "deadline", "deadline"]
        priority_specs = ["high", "high", "medium", "medium", "medium", "high"]

        deadlines = []
        for i, txt in enumerate(cal_texts):
            deadlines.append({
                "date": date_specs[i],
                "title": txt["title"],
                "description": txt["description"],
                "type": type_specs[i],
                "priority": priority_specs[i],
            })

        # Filter to upcoming deadlines
        today = date.today()
        upcoming = [d for d in deadlines if d["date"] >= today.isoformat()]
        if not upcoming:
            upcoming = deadlines

        return {
            "reference_date": today.isoformat(),
            "tax_year": year,
            "deadlines": upcoming,
        }

    def get_property_metrics(self, user_id: int, tax_year: int) -> Dict[str, Any]:
        """
        Get property portfolio metrics for landlord users.
        
        Returns summary metrics including:
        - Number of active properties
        - Total rental income (current year)
        - Total property expenses (current year)
        - Net rental income
        - Total building value
        - Total annual depreciation
        """
        # Try to get from cache
        cached_metrics = self._get_cached_portfolio_metrics(user_id, tax_year)
        if cached_metrics:
            return cached_metrics
        
        # Get active properties for user
        properties = (
            self.db.query(Property)
            .filter(
                Property.user_id == user_id,
                Property.status == PropertyStatus.ACTIVE
            )
            .all()
        )
        
        if not properties:
            result = {
                "has_properties": False,
                "active_properties_count": 0,
                "total_rental_income": Decimal("0.0"),
                "total_property_expenses": Decimal("0.0"),
                "net_rental_income": Decimal("0.0"),
                "total_building_value": Decimal("0.0"),
                "total_annual_depreciation": Decimal("0.0"),
            }
            # Cache the result
            self._set_cached_portfolio_metrics(user_id, tax_year, result)
            return result
        
        # Calculate total building value and annual depreciation
        total_building_value = sum(p.building_value for p in properties)
        total_annual_depreciation = sum(
            p.building_value * p.depreciation_rate for p in properties
        )
        
        # Get property IDs for transaction queries
        property_ids = [p.id for p in properties]
        
        # Get rental income for current year
        rental_income = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.income_category == IncomeCategory.RENTAL,
                Transaction.property_id.in_(property_ids),
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .scalar() or Decimal("0")
        )
        
        # Get property expenses for current year
        property_expenses = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.property_id.in_(property_ids),
                extract("year", Transaction.transaction_date) == tax_year,
            )
            .scalar() or Decimal("0")
        )
        
        net_rental_income = rental_income - property_expenses

        # Check if rental properties have recurring income set up
        rental_properties = [
            p for p in properties
            if p.property_type in (PropertyType.RENTAL, PropertyType.MIXED_USE)
        ]
        missing_rental_income = False
        if rental_properties and rental_income == 0:
            from app.models.recurring_transaction import RecurringTransaction
            recurring_count = (
                self.db.query(RecurringTransaction)
                .filter(
                    RecurringTransaction.user_id == user_id,
                    RecurringTransaction.property_id.in_(property_ids),
                    RecurringTransaction.is_active == True,
                )
                .count()
            )
            if recurring_count == 0:
                missing_rental_income = True

        result = {
            "has_properties": True,
            "active_properties_count": len(properties),
            "total_rental_income": rental_income,
            "total_property_expenses": property_expenses,
            "net_rental_income": net_rental_income,
            "total_building_value": total_building_value,
            "total_annual_depreciation": total_annual_depreciation,
            "missing_rental_income_setup": missing_rental_income,
        }
        
        # Cache the result
        self._set_cached_portfolio_metrics(user_id, tax_year, result)
        
        return result
