"""
Phase 3: Arbeitszimmer 百分比拆分 + BK 提取器

测试目标:
- 月租 expense 按 AZ% 拆分为 deductible + private
- BK Nachzahlung 创建 expense 并按 AZ% 拆分
- BK Guthaben 只创建 AZ% 部分的 income
- Thermenwartung 靠 VLM category=MAINTENANCE 触发 AZ% 拆分
- 无 Arbeitszimmer 的用户 → 租赁费用不可抵扣
- get_arbeitszimmer_override 只对特定 category 生效

涉及文件:
- backend/app/services/business_deductibility_rules.py
- backend/app/services/transaction_rule_materializer.py
- backend/app/services/ocr_transaction_service.py
"""
import pytest
from decimal import Decimal
from conftest import (
    AZ_RATIO, MIETE_OLD, MIETE_NEW, BK_NACHZAHLUNG, BK_GUTHABEN,
    THERMEN_BRUTTO, TOLERANCE,
    assert_amount_close, assert_split_correct,
)


# ══════════════════════════════════════════════
# Stubs（实现后替换为真实导入）
# ══════════════════════════════════════════════
def get_arbeitszimmer_override(user, expense_category: str) -> dict | None:
    """Stub for business_deductibility_rules.get_arbeitszimmer_override."""
    if not user.arbeitszimmer_m2 or not user.nutzflaeche_m2:
        return None

    eligible = {"RENT", "HOME_OFFICE", "UTILITIES", "MAINTENANCE"}
    if expense_category not in eligible:
        return None

    ratio = (user.arbeitszimmer_m2 / user.nutzflaeche_m2).quantize(Decimal("0.0001"))
    return {
        "is_deductible": True,
        "deductible_pct": ratio,
        "reason": f"Arbeitszimmer anteilig ({ratio*100:.1f}%) §20 Abs.1 Z 2 lit.d EStG",
    }


def compute_expense_split(amount: Decimal, ratio: Decimal) -> dict:
    """Stub for what _build_split_line_items produces."""
    deductible = (amount * ratio).quantize(Decimal("0.01"))
    private = amount - deductible
    return {
        "total": amount,
        "deductible": deductible,
        "private": private,
        "posting_deductible": "EXPENSE",
        "posting_private": "PRIVATE_USE",
        "allocation_source": "PERCENTAGE_RULE",
    }


def extract_bk_guthaben_income(guthaben_total: Decimal, ratio: Decimal) -> dict:
    """Stub for BK Guthaben → income (方式 B: 只建 AZ% 部分)."""
    income_amount = (guthaben_total * ratio).quantize(Decimal("0.01"))
    return {
        "transaction_type": "income",
        "amount": income_amount,
        "category": "RENT",
        "description": f"BK-Guthaben Betriebseinnahme ({ratio*100:.1f}% Arbeitszimmer)",
        "is_deductible": True,
    }


# ══════════════════════════════════════════════
# Tests: AZ override 规则
# ══════════════════════════════════════════════

class TestArbeitszimmerOverride:
    """get_arbeitszimmer_override 只对租赁相关 category 生效。"""

    @pytest.mark.p0
    def test_rent_category_has_override(self, user_with_az):
        """category=RENT → 返回 override with deductible_pct。"""
        result = get_arbeitszimmer_override(user_with_az, "RENT")
        assert result is not None
        assert result["is_deductible"] is True
        assert_amount_close(result["deductible_pct"], AZ_RATIO)

    @pytest.mark.p0
    def test_maintenance_category_has_override(self, user_with_az):
        """category=MAINTENANCE → 返回 override（Thermenwartung 等）。"""
        result = get_arbeitszimmer_override(user_with_az, "MAINTENANCE")
        assert result is not None
        assert_amount_close(result["deductible_pct"], AZ_RATIO)

    def test_utilities_category_has_override(self, user_with_az):
        """category=UTILITIES → 返回 override（Strom/Heizung 等）。"""
        result = get_arbeitszimmer_override(user_with_az, "UTILITIES")
        assert result is not None

    def test_office_supplies_no_override(self, user_with_az):
        """category=OFFICE_SUPPLIES → 不适用 AZ%（不是房间费用）。"""
        result = get_arbeitszimmer_override(user_with_az, "OFFICE_SUPPLIES")
        assert result is None

    def test_travel_no_override(self, user_with_az):
        """category=TRAVEL → 不适用 AZ%。"""
        result = get_arbeitszimmer_override(user_with_az, "TRAVEL")
        assert result is None

    def test_no_az_no_override(self, user_without_az):
        """没有 Arbeitszimmer → 所有 category 返回 None。"""
        assert get_arbeitszimmer_override(user_without_az, "RENT") is None
        assert get_arbeitszimmer_override(user_without_az, "MAINTENANCE") is None


# ══════════════════════════════════════════════
# Tests: 月租拆分
# ══════════════════════════════════════════════

class TestMieteExpenseSplit:
    """月租按 AZ% 拆分为 deductible + private。"""

    @pytest.mark.p0
    def test_old_miete_split(self):
        """€867.00 × 23.08% = €200.19 deductible + €666.81 private。"""
        split = compute_expense_split(MIETE_OLD, AZ_RATIO)
        assert_split_correct(
            split["deductible"], split["private"],
            MIETE_OLD, AZ_RATIO, "old miete"
        )
        assert split["posting_deductible"] == "EXPENSE"
        assert split["posting_private"] == "PRIVATE_USE"
        assert split["allocation_source"] == "PERCENTAGE_RULE"

    @pytest.mark.p0
    def test_new_miete_split(self):
        """€945.42 × 23.08% = €218.20 deductible + €727.22 private（涨租后）。"""
        split = compute_expense_split(MIETE_NEW, AZ_RATIO)
        assert_split_correct(
            split["deductible"], split["private"],
            MIETE_NEW, AZ_RATIO, "new miete"
        )

    def test_split_sums_to_total(self):
        """deductible + private 必须精确等于 total（无 rounding loss）。"""
        split = compute_expense_split(MIETE_OLD, AZ_RATIO)
        assert split["deductible"] + split["private"] == MIETE_OLD

    @pytest.mark.p1
    def test_three_months_old_rate(self):
        """Jan-Mar: 3 × €867.00 → 总 deductible ≈ €600.57。"""
        total_ded = Decimal("0")
        for _ in range(3):
            split = compute_expense_split(MIETE_OLD, AZ_RATIO)
            total_ded += split["deductible"]
        expected = (MIETE_OLD * 3 * AZ_RATIO).quantize(Decimal("0.01"))
        assert_amount_close(total_ded, expected, "3 months old rate")


# ══════════════════════════════════════════════
# Tests: BK Abrechnung
# ══════════════════════════════════════════════

class TestBKAbrechnung:
    """BK Nachzahlung → expense 拆分; BK Guthaben → income (AZ% only)。"""

    @pytest.mark.p0
    def test_bk_nachzahlung_split(self):
        """BK NZ €142.35 × 23.08% = €32.86 deductible + €109.49 private。"""
        split = compute_expense_split(BK_NACHZAHLUNG, AZ_RATIO)
        assert_split_correct(
            split["deductible"], split["private"],
            BK_NACHZAHLUNG, AZ_RATIO, "BK NZ"
        )

    @pytest.mark.p0
    def test_bk_guthaben_income_amount(self):
        """BK GH €87.60 → income = €87.60 × 23.08% = €20.23。"""
        result = extract_bk_guthaben_income(BK_GUTHABEN, AZ_RATIO)
        assert result["transaction_type"] == "income"
        expected = (BK_GUTHABEN * AZ_RATIO).quantize(Decimal("0.01"))
        assert_amount_close(result["amount"], expected, "BK GH income")

    @pytest.mark.p0
    def test_bk_guthaben_not_full_amount(self):
        """BK GH income 不是全额 €87.60 — 只有 AZ% 部分。"""
        result = extract_bk_guthaben_income(BK_GUTHABEN, AZ_RATIO)
        assert result["amount"] < BK_GUTHABEN
        assert result["amount"] > Decimal("0")

    def test_bk_guthaben_is_betriebseinnahme(self):
        """BK GH income 标注为 Betriebseinnahme。"""
        result = extract_bk_guthaben_income(BK_GUTHABEN, AZ_RATIO)
        assert "Betriebseinnahme" in result["description"]
        assert result["is_deductible"] is True


# ══════════════════════════════════════════════
# Tests: Thermenwartung（靠 VLM category）
# ══════════════════════════════════════════════

class TestThermenwartung:
    """Thermenwartung 靠 category=MAINTENANCE 触发 AZ% 拆分。"""

    @pytest.mark.p0
    def test_thermen_split(self):
        """€198.00 × 23.08% = €45.70 deductible + €152.30 private。"""
        split = compute_expense_split(THERMEN_BRUTTO, AZ_RATIO)
        assert_split_correct(
            split["deductible"], split["private"],
            THERMEN_BRUTTO, AZ_RATIO, "Thermenwartung"
        )

    def test_maintenance_override_applies(self, user_with_az):
        """VLM 返回 category=MAINTENANCE → get_arbeitszimmer_override 生效。"""
        override = get_arbeitszimmer_override(user_with_az, "MAINTENANCE")
        assert override is not None
        assert override["is_deductible"] is True
        assert_amount_close(override["deductible_pct"], AZ_RATIO)

    def test_no_az_thermen_not_deductible(self, user_without_az):
        """没有 Arbeitszimmer → Thermenwartung 不可抵扣。"""
        override = get_arbeitszimmer_override(user_without_az, "MAINTENANCE")
        assert override is None


# ══════════════════════════════════════════════
# Tests: 月租路由（_rental_subtype="miete" → category=RENT）
# ══════════════════════════════════════════════

class TestMieteRouting:
    """_rental_subtype="miete" 的 INVOICE 应路由到 category=RENT。"""

    @pytest.mark.p0
    def test_miete_invoice_has_rent_category(self, ocr_miete_jan):
        """月租发票 ocr_result 带 expense_category=RENT。"""
        assert ocr_miete_jan["expense_category"] == "RENT"
        assert ocr_miete_jan["_rental_subtype"] == "miete"

    def test_miete_triggers_az_override(self, user_with_az, ocr_miete_jan):
        """miete + RENT category → AZ override 生效。"""
        override = get_arbeitszimmer_override(
            user_with_az, ocr_miete_jan["expense_category"]
        )
        assert override is not None
        assert_amount_close(override["deductible_pct"], AZ_RATIO)
