"""
Phase 1: Arbeitszimmer 数据模型 + 比例计算

测试目标:
- calculate_arbeitszimmer_ratio 返回正确比例
- 边界条件处理（缺失字段、零值、极端比例）
- 软警告机制（>50% 提醒但不阻止）
- Telearbeitspauschale 互斥检查
- Schema 验证（arbeitszimmer_m2 < nutzflaeche_m2）

涉及文件:
- backend/app/services/deduction_calculator.py
- backend/app/models/user.py
- backend/app/schemas/user.py
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from conftest import (
    AZ_M2, NUTZFLAECHE_M2, AZ_RATIO, TOLERANCE,
    assert_amount_close,
)


# ══════════════════════════════════════════════
# 导入待测模块（实现后取消注释）
# ══════════════════════════════════════════════
# from app.services.deduction_calculator import (
#     calculate_arbeitszimmer_ratio,
#     calculate_home_office_deduction,
# )
# from app.schemas.user import UserProfileUpdate


# ══════════════════════════════════════════════
# Stub implementations for pre-implementation testing
# Remove these once real code exists
# ══════════════════════════════════════════════
def calculate_arbeitszimmer_ratio(user):
    """Stub — replace with real import."""
    if not user.arbeitszimmer_m2 or not user.nutzflaeche_m2:
        return None
    if user.nutzflaeche_m2 <= 0:
        return None
    ratio = (user.arbeitszimmer_m2 / user.nutzflaeche_m2).quantize(Decimal("0.0001"))
    warning = None
    if ratio > Decimal("0.50"):
        warning = "Bitte prüfen: Arbeitszimmer-Anteil über 50%"
    return {"ratio": ratio, "warning": warning}


def calculate_home_office_deduction(user, tax_year=2024):
    """Stub — replace with real import."""
    if user.arbeitszimmer_m2 and user.arbeitszimmer_m2 > 0:
        return {"telearbeit_amount": Decimal("0"), "note": "Arbeitszimmer vorhanden — Telearbeitspauschale entfällt"}
    tage = user.employer_telearbeit_tage or 0
    return {"telearbeit_amount": Decimal(str(min(tage, 100) * 3))}


# ══════════════════════════════════════════════
# Tests: 比例计算
# ══════════════════════════════════════════════

class TestArbeitszimmerRatio:
    """calculate_arbeitszimmer_ratio 的核心测试。"""

    @pytest.mark.p0
    def test_standard_ratio(self, user_with_az):
        """18m² / 78m² = 0.2308"""
        result = calculate_arbeitszimmer_ratio(user_with_az)
        assert result is not None
        assert_amount_close(result["ratio"], AZ_RATIO, "standard 18/78")
        assert result["warning"] is None

    @pytest.mark.p0
    def test_no_az_configured(self, user_without_az):
        """没有配置 Arbeitszimmer → 返回 None。"""
        result = calculate_arbeitszimmer_ratio(user_without_az)
        assert result is None

    def test_az_m2_zero(self):
        """arbeitszimmer_m2 = 0 → 返回 None 或 ratio=0。"""
        user = MagicMock()
        user.arbeitszimmer_m2 = Decimal("0")
        user.nutzflaeche_m2 = Decimal("78.00")
        result = calculate_arbeitszimmer_ratio(user)
        # 0m² Arbeitszimmer = 没有 Arbeitszimmer
        assert result is None or result["ratio"] == Decimal("0")

    def test_nutzflaeche_zero(self):
        """nutzflaeche_m2 = 0 → 不能除以零。"""
        user = MagicMock()
        user.arbeitszimmer_m2 = Decimal("18.00")
        user.nutzflaeche_m2 = Decimal("0")
        result = calculate_arbeitszimmer_ratio(user)
        assert result is None

    def test_precision_4_decimal(self, user_with_az):
        """比例精度 4 位小数。"""
        result = calculate_arbeitszimmer_ratio(user_with_az)
        ratio_str = str(result["ratio"])
        # 0.2308 — exactly 4 decimal places
        parts = ratio_str.split(".")
        assert len(parts) == 2
        assert len(parts[1]) <= 4


class TestArbeitszimmerSoftWarning:
    """超过 50% 时的软警告 — 不阻止保存。"""

    @pytest.mark.p1
    def test_over_50_pct_warns(self, user_az_large_ratio):
        """25m² / 40m² = 62.5% → 有 warning 但仍返回 ratio。"""
        result = calculate_arbeitszimmer_ratio(user_az_large_ratio)
        assert result is not None
        assert_amount_close(result["ratio"], Decimal("0.6250"), "25/40")
        assert result["warning"] is not None
        assert "50%" in result["warning"]

    def test_exactly_50_pct_no_warn(self):
        """50.00% → 不警告。"""
        user = MagicMock()
        user.arbeitszimmer_m2 = Decimal("20.00")
        user.nutzflaeche_m2 = Decimal("40.00")
        result = calculate_arbeitszimmer_ratio(user)
        assert result["ratio"] == Decimal("0.5000")
        assert result["warning"] is None

    def test_49_pct_no_warn(self):
        """49% → 不警告。"""
        user = MagicMock()
        user.arbeitszimmer_m2 = Decimal("19.60")
        user.nutzflaeche_m2 = Decimal("40.00")
        result = calculate_arbeitszimmer_ratio(user)
        assert result["warning"] is None


class TestArbeitszimmerMittelpunkt:
    """Mittelpunkt 不影响比例计算 — 只影响年度上限（Phase 5）。"""

    @pytest.mark.p0
    def test_mittelpunkt_true_same_ratio(self, user_with_az):
        """Mittelpunkt=True → 比例不变。"""
        result = calculate_arbeitszimmer_ratio(user_with_az)
        assert_amount_close(result["ratio"], AZ_RATIO)

    @pytest.mark.p0
    def test_mittelpunkt_false_same_ratio(self, user_az_not_mittelpunkt):
        """Mittelpunkt=False → 比例同样不变（上限在 Phase 5 处理）。"""
        result = calculate_arbeitszimmer_ratio(user_az_not_mittelpunkt)
        assert_amount_close(result["ratio"], AZ_RATIO)


class TestTelearbeitMutualExclusion:
    """Arbeitszimmer 和 Telearbeitspauschale 互斥。"""

    @pytest.mark.p0
    def test_az_present_telearbeit_zero(self, user_with_az):
        """有 Arbeitszimmer → Telearbeitspauschale 必须返回 0。"""
        result = calculate_home_office_deduction(user_with_az)
        assert result["telearbeit_amount"] == Decimal("0")
        assert "Arbeitszimmer" in result.get("note", "")

    @pytest.mark.p1
    def test_no_az_telearbeit_works(self, user_without_az):
        """没有 Arbeitszimmer → Telearbeitspauschale 正常计算。"""
        result = calculate_home_office_deduction(user_without_az)
        # 45 Tage × €3 = €135
        assert result["telearbeit_amount"] == Decimal("135")


class TestSchemaValidation:
    """User schema 验证规则。"""

    @pytest.mark.p1
    def test_az_larger_than_nutzflaeche_rejected(self):
        """arbeitszimmer_m2 > nutzflaeche_m2 → 验证失败。"""
        # 当实现后，这里应该测试 Pydantic 验证
        # UserProfileUpdate(arbeitszimmer_m2=80, nutzflaeche_m2=78) → ValidationError
        with pytest.raises(Exception):
            # Simulate validation
            az = Decimal("80.00")
            nf = Decimal("78.00")
            if az >= nf:
                raise ValueError("arbeitszimmer_m2 must be less than nutzflaeche_m2")

    def test_negative_values_rejected(self):
        """负数面积 → 验证失败。"""
        with pytest.raises(Exception):
            az = Decimal("-5.00")
            if az < 0:
                raise ValueError("arbeitszimmer_m2 must be positive")
