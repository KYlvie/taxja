"""
Phase 4: 月度租赁去重 + link-to-existing

测试目标:
- 同月同地址同金额重复上传 → link_to_existing
- 不同月份 → 不触发 dedup
- 涨租后新金额（€945.42 vs €867.00） → 不触发 dedup
- 不同地址（两套房） → 不触发 dedup
- BK 去重: 同 objekt + 同 abrechnungsjahr + 同类型 → link_to_existing
- BK 不同年份 → 不触发 dedup

涉及文件:
- backend/app/services/document_pipeline_orchestrator.py
"""
import pytest
from decimal import Decimal
from conftest import (
    MIETE_OLD, MIETE_NEW, BK_NACHZAHLUNG, BK_GUTHABEN, TOLERANCE,
    build_ocr_result,
)


# ══════════════════════════════════════════════
# Stubs
# ══════════════════════════════════════════════
def check_rental_dedup(
    user_id: int,
    objekt_address: str,
    month: int,
    year: int,
    amount: Decimal,
    existing_transactions: list,
    tolerance_pct: Decimal = Decimal("0.02"),
) -> dict | None:
    """
    Stub: 检查同月同地址同金额的已有交易。
    返回匹配的交易 dict，或 None。
    """
    for tx in existing_transactions:
        if (tx["user_id"] == user_id
            and tx["objekt_address"] == objekt_address
            and tx["month"] == month
            and tx["year"] == year):
            # Amount within tolerance
            diff_ratio = abs(tx["amount"] - amount) / amount if amount else Decimal("1")
            if diff_ratio <= tolerance_pct:
                return tx
    return None


def check_bk_dedup(
    user_id: int,
    objekt_address: str,
    abrechnungsjahr: int,
    bk_type: str,  # "nachzahlung" or "guthaben"
    existing_transactions: list,
) -> dict | None:
    """Stub: BK 文档去重。"""
    for tx in existing_transactions:
        if (tx["user_id"] == user_id
            and tx["objekt_address"] == objekt_address
            and tx.get("abrechnungsjahr") == abrechnungsjahr
            and tx.get("bk_type") == bk_type):
            return tx
    return None


def should_allow_link_to_existing(doc_type: str, ocr_result: dict) -> bool:
    """Stub: 判断是否允许 link_to_existing。"""
    always_allow = {"BANK_STATEMENT", "KONTOAUSZUG"}
    if doc_type in always_allow:
        return True
    if doc_type == "INVOICE" and ocr_result.get("_rental_subtype"):
        return True
    if doc_type == "BETRIEBSKOSTENABRECHNUNG" and ocr_result.get("_rental_subtype"):
        return True
    return False


# ══════════════════════════════════════════════
# Fixtures: 已有交易
# ══════════════════════════════════════════════
@pytest.fixture
def existing_jan_miete():
    """模拟系统中已有的 1 月月租交易。"""
    return [{
        "id": 100,
        "user_id": 1,
        "objekt_address": "Landstrasser Hauptstrasse 98/3, 1030 Wien",
        "month": 1,
        "year": 2024,
        "amount": MIETE_OLD,
        "category": "RENT",
        "description": "Mietzinsvorschreibung Jaenner 2024",
    }]


@pytest.fixture
def existing_bk_nz_2023():
    """模拟系统中已有的 BK 2023 Nachzahlung。"""
    return [{
        "id": 200,
        "user_id": 1,
        "objekt_address": "Landstrasser Hauptstrasse 98/3, 1030 Wien",
        "abrechnungsjahr": 2023,
        "bk_type": "nachzahlung",
        "amount": BK_NACHZAHLUNG,
    }]


# ══════════════════════════════════════════════
# Tests: 月度去重
# ══════════════════════════════════════════════

class TestMonthlyMieteDedup:
    """同月同地址同金额 → link_to_existing。"""

    @pytest.mark.p0
    def test_same_month_duplicate(self, existing_jan_miete):
        """重复上传 1 月月租 → 匹配到已有交易。"""
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=1, year=2024,
            amount=MIETE_OLD,
            existing_transactions=existing_jan_miete,
        )
        assert match is not None
        assert match["id"] == 100

    @pytest.mark.p0
    def test_different_month_no_dedup(self, existing_jan_miete):
        """上传 2 月月租 → 不匹配（不同月份）。"""
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=2, year=2024,
            amount=MIETE_OLD,
            existing_transactions=existing_jan_miete,
        )
        assert match is None

    @pytest.mark.p0
    def test_index_new_amount_no_dedup(self, existing_jan_miete):
        """涨租后 4 月金额 €945.42 vs 1 月 €867.00 → 不匹配（不同月份+不同金额）。"""
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=4, year=2024,
            amount=MIETE_NEW,
            existing_transactions=existing_jan_miete,
        )
        assert match is None

    @pytest.mark.p1
    def test_different_address_no_dedup(self, existing_jan_miete):
        """不同地址（第二套房） → 不匹配。"""
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Mariahilfer Strasse 45/2, 1060 Wien",
            month=1, year=2024,
            amount=MIETE_OLD,
            existing_transactions=existing_jan_miete,
        )
        assert match is None

    def test_different_user_no_dedup(self, existing_jan_miete):
        """不同用户 → 不匹配。"""
        match = check_rental_dedup(
            user_id=999,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=1, year=2024,
            amount=MIETE_OLD,
            existing_transactions=existing_jan_miete,
        )
        assert match is None

    def test_amount_within_2pct_tolerance(self, existing_jan_miete):
        """金额在 ±2% 容差内 → 仍然匹配。"""
        slightly_different = MIETE_OLD + Decimal("5.00")  # €872, ~0.6% off
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=1, year=2024,
            amount=slightly_different,
            existing_transactions=existing_jan_miete,
        )
        assert match is not None

    def test_amount_beyond_tolerance_no_dedup(self, existing_jan_miete):
        """金额超过 ±2% → 不匹配。"""
        very_different = MIETE_OLD + Decimal("50.00")  # €917, ~5.8% off
        match = check_rental_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            month=1, year=2024,
            amount=very_different,
            existing_transactions=existing_jan_miete,
        )
        assert match is None


# ══════════════════════════════════════════════
# Tests: BK 去重
# ══════════════════════════════════════════════

class TestBKDedup:
    """BK 文档按 objekt + abrechnungsjahr + type 去重。"""

    @pytest.mark.p0
    def test_same_bk_nz_duplicate(self, existing_bk_nz_2023):
        """重复上传 BK 2023 NZ → 匹配。"""
        match = check_bk_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            abrechnungsjahr=2023,
            bk_type="nachzahlung",
            existing_transactions=existing_bk_nz_2023,
        )
        assert match is not None

    @pytest.mark.p0
    def test_different_year_no_dedup(self, existing_bk_nz_2023):
        """BK 2022 NZ vs 已有 BK 2023 NZ → 不匹配。"""
        match = check_bk_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            abrechnungsjahr=2022,
            bk_type="nachzahlung",
            existing_transactions=existing_bk_nz_2023,
        )
        assert match is None

    def test_guthaben_vs_nachzahlung_no_dedup(self, existing_bk_nz_2023):
        """BK 2023 Guthaben vs 已有 BK 2023 NZ → 不匹配（不同类型）。"""
        match = check_bk_dedup(
            user_id=1,
            objekt_address="Landstrasser Hauptstrasse 98/3, 1030 Wien",
            abrechnungsjahr=2023,
            bk_type="guthaben",
            existing_transactions=existing_bk_nz_2023,
        )
        assert match is None


# ══════════════════════════════════════════════
# Tests: link-to-existing 开关
# ══════════════════════════════════════════════

class TestLinkToExistingAllowed:
    """只有特定文档类型允许 link_to_existing。"""

    @pytest.mark.p1
    def test_miete_invoice_allowed(self, ocr_miete_jan):
        """INVOICE + _rental_subtype="miete" → 允许 link。"""
        assert should_allow_link_to_existing("INVOICE", ocr_miete_jan) is True

    def test_bk_allowed(self, ocr_bk_nachzahlung):
        """BETRIEBSKOSTENABRECHNUNG + _rental_subtype → 允许 link。"""
        assert should_allow_link_to_existing("BETRIEBSKOSTENABRECHNUNG", ocr_bk_nachzahlung) is True

    def test_normal_invoice_not_allowed(self):
        """普通 INVOICE（无 _rental_subtype） → 不允许 link。"""
        ocr = build_ocr_result(doc_type="INVOICE", amount=Decimal("100"))
        assert should_allow_link_to_existing("INVOICE", ocr) is False

    def test_bank_statement_always_allowed(self):
        """BANK_STATEMENT → 始终允许 link。"""
        ocr = build_ocr_result(doc_type="BANK_STATEMENT")
        assert should_allow_link_to_existing("BANK_STATEMENT", ocr) is True
