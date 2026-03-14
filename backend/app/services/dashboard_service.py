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
from app.models.document import Document
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus, PropertyType


# ---------------------------------------------------------------------------
# Localized text tables for suggestions (de / en / zh)
# ---------------------------------------------------------------------------
_SUGGESTION_TEXTS: Dict[str, Dict[str, str]] = {
    "de": {
        "home_office_title": "Home-Office-Pauschale",
        "home_office_desc": (
            "Sie haben noch keine Home-Office-Ausgaben geltend gemacht. "
            "Wenn Sie von zu Hause arbeiten, können Sie bis zu €300/Jahr absetzen."
        ),
        "pendler_title": "Pendlerpauschale",
        "pendler_desc": (
            "Keine Fahrtkosten erfasst. Ab 2 km Arbeitsweg (Großes Pendlerpauschale) "
            "oder ab 20 km (Kleines Pendlerpauschale) steht Ihnen eine Pauschale zu."
        ),
        "insurance_title": "Versicherungsprämien",
        "insurance_desc": (
            "Keine Versicherungsausgaben erfasst. Private Versicherungsprämien "
            "können teilweise als Sonderausgaben absetzbar sein."
        ),
        "review_title": "Nicht abzugsfähige Ausgaben prüfen",
        "review_desc": (
            "Sie haben {amount} an nicht abzugsfähigen Ausgaben. "
            "Einige davon könnten mit entsprechenden Belegen absetzbar sein."
        ),
        "ocr_title": "OCR-Ergebnisse prüfen",
        "ocr_desc": (
            "{count} Dokument(e) haben eine niedrige OCR-Konfidenz "
            "und sollten manuell überprüft werden."
        ),
        "getting_started_title": "Erste Transaktion hinzufügen",
        "getting_started_desc": (
            "Laden Sie Belege, Rechnungen oder Lohnzettel hoch, um zu starten. "
            "Sie können auch manuell Einnahmen und Ausgaben erfassen."
        ),
    },
    "en": {
        "home_office_title": "Home Office Deduction",
        "home_office_desc": (
            "You haven't claimed home office expenses. "
            "If you work from home, you may deduct up to €300/year."
        ),
        "pendler_title": "Pendlerpauschale (Commuter Allowance)",
        "pendler_desc": (
            "No commuting expenses recorded. From 2 km (Großes Pendlerpauschale) "
            "or 20 km (Kleines Pendlerpauschale) you may be eligible for a commuter allowance."
        ),
        "insurance_title": "Insurance Premiums",
        "insurance_desc": (
            "No insurance expenses recorded. Private insurance premiums "
            "may be partially deductible as Sonderausgaben."
        ),
        "review_title": "Review Non-Deductible Expenses",
        "review_desc": (
            "You have {amount} in non-deductible expenses. "
            "Some may qualify for deduction with proper documentation."
        ),
        "ocr_title": "Review OCR Results",
        "ocr_desc": (
            "{count} document(s) have low OCR confidence "
            "and need manual review."
        ),
        "getting_started_title": "Add Your First Transaction",
        "getting_started_desc": (
            "Upload receipts, invoices, or payslips to get started. "
            "You can also manually add income and expenses."
        ),
    },
    "zh": {
        "home_office_title": "居家办公扣除",
        "home_office_desc": (
            "您尚未申报居家办公费用。"
            "如果您在家工作，每年最多可扣除 €300。"
        ),
        "pendler_title": "通勤补贴 (Pendlerpauschale)",
        "pendler_desc": (
            "未记录通勤费用。通勤距离 2 公里起（Großes Pendlerpauschale）"
            "或 20 公里起（Kleines Pendlerpauschale）可申请通勤补贴。"
        ),
        "insurance_title": "保险费",
        "insurance_desc": (
            "未记录保险费用。私人保险费可能部分作为特殊支出 (Sonderausgaben) 扣除。"
        ),
        "review_title": "检查不可扣除支出",
        "review_desc": (
            "您有 {amount} 的不可扣除支出。"
            "其中部分可能在提供适当凭证后可以扣除。"
        ),
        "ocr_title": "检查 OCR 识别结果",
        "ocr_desc": "{count} 份文档 OCR 置信度较低，需要人工审核。",
        "getting_started_title": "添加您的第一笔交易",
        "getting_started_desc": (
            "上传收据、发票或工资单即可开始。"
            "您也可以手动添加收入和支出。"
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
                t.amount
                for t in transactions
                if t.type == TransactionType.EXPENSE and t.is_deductible
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
            # ESt: progressive brackets (2026 USP / Steuerjahr 2025)
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

        # VAT threshold distance
        vat_threshold = Decimal("55000")
        vat_distance = float(vat_threshold - total_income)

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
            elif t.type == TransactionType.EXPENSE and t.expense_category:
                cat = (
                    t.expense_category.value
                    if hasattr(t.expense_category, "value")
                    else str(t.expense_category)
                )
                expense_by_cat[cat] += float(t.amount)

        income_category_data = [{"category": k, "amount": v} for k, v in income_by_cat.items()]
        expense_category_data = [{"category": k, "amount": v} for k, v in expense_by_cat.items()]

        return {
            "yearToDateIncome": float(total_income),
            "yearToDateExpenses": float(total_expenses),
            "deductibleExpenses": float(deductible_expenses),
            "estimatedTax": float(estimated_tax),
            "paidTax": float(paid_tax),
            "remainingTax": float(remaining_tax),
            "netIncome": float(net_income),
            "vatThresholdDistance": vat_distance,
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
            })

        if "commuting" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["pendler_title"],
                "description": texts["pendler_desc"],
                "potential_savings": 500.0,
                "priority": "high",
            })

        if "insurance" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["insurance_title"],
                "description": texts["insurance_desc"],
                "potential_savings": 200.0,
                "priority": "medium",
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
            })

        if not transactions:
            suggestions.append({
                "type": "getting_started",
                "title": texts["getting_started_title"],
                "description": texts["getting_started_desc"],
                "potential_savings": 0,
                "priority": "high",
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
