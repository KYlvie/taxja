"""
Phase 5: E1a KZ 9230 + 年度汇总 + Mittelpunkt 上限

测试目标:
- 年度 Raumkosten 正确汇总（混合新旧金额）
- BK Guthaben 冲减
- KZ 9230 映射
- Mittelpunkt=True → 无上限
- Mittelpunkt=False → €1,250 年度上限 (CAP_RULE)
- 年度摘要包含所有必要字段

涉及文件:
- backend/app/services/e1a_form_service.py
- frontend/src/pages/ProfilePage.tsx
"""
import pytest
from decimal import Decimal
from conftest import (
    AZ_RATIO, MIETE_OLD, MIETE_NEW,
    BK_NACHZAHLUNG, BK_GUTHABEN, THERMEN_BRUTTO,
    TOLERANCE, assert_amount_close,
)


# ══════════════════════════════════════════════
# Constants: 年度计算
# ══════════════════════════════════════════════
MONTHS_OLD_RATE = 3   # Jan-Mar
MONTHS_NEW_RATE = 9   # Apr-Dec
MITTELPUNKT_FALSE_CAP = Decimal("1250.00")


# ══════════════════════════════════════════════
# Stub
# ══════════════════════════════════════════════
def compute_annual_arbeitszimmer_summary(
    monthly_expenses: list,
    bk_items: list,
    other_expenses: list,
    ratio: Decimal,
    mittelpunkt: bool,
) -> dict:
    """
    Stub: 年度 Arbeitszimmer 费用汇总。

    monthly_expenses: [{"month": 1, "amount": Decimal("867.00")}, ...]
    bk_items: [{"type": "nachzahlung"/"guthaben", "amount": Decimal(...)}]
    other_expenses: [{"category": "MAINTENANCE", "amount": Decimal("198.00")}]
    """
    # Gross rental expenses
    gross_rent = sum(e["amount"] for e in monthly_expenses)

    # BK adjustments
    bk_nz = sum(b["amount"] for b in bk_items if b["type"] == "nachzahlung")
    bk_gh = sum(b["amount"] for b in bk_items if b["type"] == "guthaben")
    bk_gh_income = (bk_gh * ratio).quantize(Decimal("0.01"))

    # Other
    other_total = sum(e["amount"] for e in other_expenses)

    # Total gross expenses (excl. BK GH which is income)
    gross_total = gross_rent + bk_nz + other_total

    # Deductible (AZ%)
    deductible_rent = (gross_rent * ratio).quantize(Decimal("0.01"))
    deductible_bk_nz = (bk_nz * ratio).quantize(Decimal("0.01"))
    deductible_other = (other_total * ratio).quantize(Decimal("0.01"))

    total_deductible = deductible_rent + deductible_bk_nz + deductible_other

    # Mittelpunkt cap
    capped = False
    cap_reduction = Decimal("0")
    if not mittelpunkt and total_deductible > MITTELPUNKT_FALSE_CAP:
        cap_reduction = total_deductible - MITTELPUNKT_FALSE_CAP
        total_deductible = MITTELPUNKT_FALSE_CAP
        capped = True

    # KZ 9230 = deductible expenses - BK GH income offset
    kz_9230 = total_deductible - bk_gh_income

    return {
        "gross_rent": gross_rent,
        "gross_bk_nz": bk_nz,
        "gross_other": other_total,
        "gross_total": gross_total,
        "bk_guthaben_income": bk_gh_income,
        "deductible_rent": deductible_rent,
        "deductible_bk_nz": deductible_bk_nz,
        "deductible_other": deductible_other,
        "total_deductible_before_cap": deductible_rent + deductible_bk_nz + deductible_other,
        "total_deductible": total_deductible,
        "mittelpunkt": mittelpunkt,
        "capped": capped,
        "cap_reduction": cap_reduction,
        "kz_9230": kz_9230,
        "ratio": ratio,
    }


# ══════════════════════════════════════════════
# Fixtures: 2024 年度数据
# ══════════════════════════════════════════════
@pytest.fixture
def annual_2024_data():
    """DI Maria Steiner 的完整 2024 年度租赁数据。"""
    monthly = (
        [{"month": m, "amount": MIETE_OLD} for m in range(1, 4)]       # Jan-Mar old
        + [{"month": m, "amount": MIETE_NEW} for m in range(4, 13)]    # Apr-Dec new
    )
    bk = [
        {"type": "nachzahlung", "amount": BK_NACHZAHLUNG},  # BK 2023 NZ
        {"type": "guthaben", "amount": BK_GUTHABEN},         # BK 2022 GH
    ]
    other = [
        {"category": "MAINTENANCE", "amount": THERMEN_BRUTTO},  # Thermenwartung
    ]
    return monthly, bk, other


# ══════════════════════════════════════════════
# Tests: 年度汇总（Mittelpunkt=True, 无上限）
# ══════════════════════════════════════════════

class TestAnnualSummaryMittelpunkt:
    """Mittelpunkt=True → 年度费用无上限。"""

    @pytest.mark.p0
    def test_gross_rent_total(self, annual_2024_data):
        """3×€867 + 9×€945.42 = €11,109.78"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=True
        )
        expected_gross_rent = MIETE_OLD * 3 + MIETE_NEW * 9
        assert_amount_close(result["gross_rent"], expected_gross_rent, "gross rent")

    @pytest.mark.p0
    def test_no_cap_applied(self, annual_2024_data):
        """Mittelpunkt=True → capped=False。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=True
        )
        assert result["capped"] is False
        assert result["cap_reduction"] == Decimal("0")

    @pytest.mark.p0
    def test_kz_9230_value(self, annual_2024_data):
        """KZ 9230 = total_deductible - BK GH income。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=True
        )
        # KZ 9230 must be positive
        assert result["kz_9230"] > Decimal("0")
        # KZ 9230 = total_deductible - bk_gh_income
        assert_amount_close(
            result["kz_9230"],
            result["total_deductible"] - result["bk_guthaben_income"],
            "KZ 9230"
        )

    @pytest.mark.p1
    def test_bk_guthaben_reduces_total(self, annual_2024_data):
        """BK Guthaben income 从 KZ 9230 中冲减。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=True
        )
        assert result["bk_guthaben_income"] > Decimal("0")
        assert result["kz_9230"] < result["total_deductible"]

    def test_summary_has_all_fields(self, annual_2024_data):
        """汇总包含所有必要字段。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=True
        )
        required_fields = [
            "gross_rent", "gross_bk_nz", "gross_other", "gross_total",
            "bk_guthaben_income", "total_deductible", "kz_9230",
            "mittelpunkt", "capped", "ratio",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"


# ══════════════════════════════════════════════
# Tests: 年度汇总（Mittelpunkt=False, €1,250 上限）
# ══════════════════════════════════════════════

class TestAnnualSummaryNichtMittelpunkt:
    """Mittelpunkt=False → 所有 Raumkosten 合计上限 €1,250/年。"""

    @pytest.mark.p0
    def test_cap_applied(self, annual_2024_data):
        """年度 deductible > €1,250 → capped=True。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=False
        )
        assert result["capped"] is True
        assert result["total_deductible"] == MITTELPUNKT_FALSE_CAP

    @pytest.mark.p0
    def test_cap_value_exact(self, annual_2024_data):
        """上限后 total_deductible = €1,250.00 精确。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=False
        )
        assert result["total_deductible"] == Decimal("1250.00")

    def test_cap_reduction_tracked(self, annual_2024_data):
        """记录被 cap 掉的金额。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=False
        )
        assert result["cap_reduction"] > Decimal("0")
        # before_cap - reduction = 1250
        assert_amount_close(
            result["total_deductible_before_cap"] - result["cap_reduction"],
            MITTELPUNKT_FALSE_CAP,
            "cap reduction math"
        )

    @pytest.mark.p1
    def test_small_az_no_cap(self):
        """如果年度 deductible < €1,250 → 不触发 cap。"""
        # Very small apartment, low rent
        monthly = [{"month": m, "amount": Decimal("300.00")} for m in range(1, 13)]
        ratio = Decimal("0.1000")  # 10%
        result = compute_annual_arbeitszimmer_summary(
            monthly, [], [], ratio, mittelpunkt=False
        )
        # 12 × €300 × 10% = €360 < €1,250
        assert result["capped"] is False
        assert_amount_close(result["total_deductible"], Decimal("360.00"))

    def test_kz_9230_with_cap(self, annual_2024_data):
        """有 cap 时 KZ 9230 = capped_amount - BK GH income。"""
        monthly, bk, other = annual_2024_data
        result = compute_annual_arbeitszimmer_summary(
            monthly, bk, other, AZ_RATIO, mittelpunkt=False
        )
        expected_kz = MITTELPUNKT_FALSE_CAP - result["bk_guthaben_income"]
        assert_amount_close(result["kz_9230"], expected_kz, "KZ 9230 with cap")
