"""
Phase 2: 租赁文档子类型 + Kaution/Übergabeprotokoll 阻断

测试目标:
- document_classifier 正确检测 _rental_subtype
- Kaution 和 Übergabeprotokoll 不创建交易
- BK-Abrechnung 区分 nachzahlung/guthaben
- Mietvertrag 存储合同元数据
- 月租发票检测 _rental_subtype="miete"
- 角色识别: 识别用户为 tenant（不是 landlord）

涉及文件:
- backend/app/services/document_classifier.py
- backend/app/services/ocr_transaction_service.py
- backend/app/services/document_pipeline_orchestrator.py
"""
import pytest
from decimal import Decimal
from conftest import (
    KAUTION, MIETE_OLD, BK_NACHZAHLUNG, BK_GUTHABEN,
    build_ocr_result,
)


# ══════════════════════════════════════════════
# Stub: 子类型检测器（实现后替换为真实导入）
# ══════════════════════════════════════════════
def detect_rental_subtype(text: str, doc_type: str) -> str | None:
    """Stub — simulates document_classifier post-processing."""
    text_lower = text.lower()

    if doc_type == "RENTAL_CONTRACT":
        if any(kw in text_lower for kw in ["kautionsbestätigung", "kautionsbestaetigung", "kaution"
                                            if "bestät" in text_lower or "bestaet" in text_lower else ""]):
            # More precise: need "kaution" + "bestätigung" context
            pass
        if "kautionsbestätigung" in text_lower or "kautionsbestaetigung" in text_lower:
            return "kaution"
        if "kaution" in text_lower and ("bestätig" in text_lower or "bestaeti" in text_lower):
            return "kaution"
        if "übergabeprotokoll" in text_lower or "uebergabeprotokoll" in text_lower or "wohnungsübergabe" in text_lower:
            return "uebergabeprotokoll"
        if "mietvertrag" in text_lower:
            return "mietvertrag"
        if "indexanpassung" in text_lower or "mietzinserhöhung" in text_lower or "mietzinserhoehung" in text_lower:
            return "indexanpassung"

    if doc_type == "BETRIEBSKOSTENABRECHNUNG":
        if any(kw in text_lower for kw in ["guthaben", "rückerstattung", "rueckerstattung", "gutschrift"]):
            return "guthaben"
        if any(kw in text_lower for kw in ["nachzahlung", "nachforderung", "aufzahlung"]):
            return "nachzahlung"

    if doc_type == "INVOICE":
        if any(kw in text_lower for kw in ["miete", "monatsmiete", "vorschreibung",
                                            "mietvorschreibung", "mietzinsvorschreibung"]):
            return "miete"

    return None


def should_create_transaction(ocr_result: dict) -> bool:
    """Stub — checks if transaction creation should be blocked."""
    subtype = ocr_result.get("_rental_subtype")
    if subtype in ("kaution", "uebergabeprotokoll"):
        return False
    return True


# ══════════════════════════════════════════════
# Tests: 子类型检测
# ══════════════════════════════════════════════

class TestRentalSubtypeDetection:
    """document_classifier 正确识别 _rental_subtype。"""

    @pytest.mark.p0
    def test_kaution_detected(self):
        """Kautionsbestätigung → subtype="kaution"。"""
        assert detect_rental_subtype(
            "Kautionsbestaetigung EUR 1.860,00", "RENTAL_CONTRACT"
        ) == "kaution"

    @pytest.mark.p0
    def test_uebergabeprotokoll_detected(self):
        """Übergabeprotokoll → subtype="uebergabeprotokoll"。"""
        assert detect_rental_subtype(
            "UEBERGABEPROTOKOLL Einzug 01.04.2021", "RENTAL_CONTRACT"
        ) == "uebergabeprotokoll"

    @pytest.mark.p0
    def test_mietvertrag_detected(self):
        """Mietvertrag → subtype="mietvertrag"。"""
        assert detect_rental_subtype(
            "MIETVERTRAG abgeschlossen zwischen", "RENTAL_CONTRACT"
        ) == "mietvertrag"

    @pytest.mark.p0
    def test_miete_invoice_detected(self):
        """月租发票 → subtype="miete"。"""
        assert detect_rental_subtype(
            "Mietzinsvorschreibung Jaenner 2024", "INVOICE"
        ) == "miete"

    def test_miete_monatsmiete_variant(self):
        """Monatsmiete 变体也能识别。"""
        assert detect_rental_subtype(
            "Monatsmiete Februar 2024 Top 3", "INVOICE"
        ) == "miete"

    def test_miete_vorschreibung_variant(self):
        """纯 Vorschreibung 也能识别。"""
        assert detect_rental_subtype(
            "Vorschreibung Maerz 2024", "INVOICE"
        ) == "miete"

    @pytest.mark.p0
    def test_bk_nachzahlung_detected(self):
        """BK Nachzahlung → subtype="nachzahlung"。"""
        assert detect_rental_subtype(
            "Betriebskostenabrechnung 2023 Nachzahlung", "BETRIEBSKOSTENABRECHNUNG"
        ) == "nachzahlung"

    @pytest.mark.p0
    def test_bk_guthaben_detected(self):
        """BK Guthaben → subtype="guthaben"。"""
        assert detect_rental_subtype(
            "Betriebskostenabrechnung 2022 Guthaben EUR 87,60", "BETRIEBSKOSTENABRECHNUNG"
        ) == "guthaben"

    def test_bk_gutschrift_variant(self):
        """Gutschrift 变体也能识别。"""
        assert detect_rental_subtype(
            "BK-Abrechnung 2022 — Gutschrift", "BETRIEBSKOSTENABRECHNUNG"
        ) == "guthaben"

    def test_indexanpassung_detected(self):
        """Indexanpassung → subtype="indexanpassung"。"""
        assert detect_rental_subtype(
            "Anpassung des Hauptmietzinses Indexanpassung VPI", "RENTAL_CONTRACT"
        ) == "indexanpassung"

    def test_normal_invoice_no_subtype(self):
        """普通发票（非租赁）→ 无 subtype。"""
        assert detect_rental_subtype(
            "Rechnung Nr. 2024-1234 Büromaterial", "INVOICE"
        ) is None

    def test_normal_contract_no_subtype(self):
        """非租赁合同 → 无 subtype。"""
        assert detect_rental_subtype(
            "Kaufvertrag über eine Eigentumswohnung", "RENTAL_CONTRACT"
        ) is None


# ══════════════════════════════════════════════
# Tests: Kaution/Übergabe 阻断
# ══════════════════════════════════════════════

class TestKautionBlocking:
    """Kaution 和 Übergabeprotokoll 不创建交易。"""

    @pytest.mark.p0
    def test_kaution_no_transaction(self, ocr_kaution):
        """上传 Kautionsbestätigung → should_create_transaction 返回 False。"""
        assert should_create_transaction(ocr_kaution) is False

    @pytest.mark.p0
    def test_uebergabe_no_transaction(self, ocr_uebergabeprotokoll):
        """上传 Übergabeprotokoll → should_create_transaction 返回 False。"""
        assert should_create_transaction(ocr_uebergabeprotokoll) is False

    @pytest.mark.p0
    def test_miete_creates_transaction(self, ocr_miete_jan):
        """月租发票 → should_create_transaction 返回 True。"""
        assert should_create_transaction(ocr_miete_jan) is True

    def test_bk_creates_transaction(self, ocr_bk_nachzahlung):
        """BK Nachzahlung → should_create_transaction 返回 True。"""
        assert should_create_transaction(ocr_bk_nachzahlung) is True


# ══════════════════════════════════════════════
# Tests: 合同元数据
# ══════════════════════════════════════════════

class TestContractMetadata:
    """Mietvertrag 正确存储合同元数据。"""

    @pytest.mark.p0
    def test_mietvertrag_has_metadata(self, ocr_mietvertrag):
        """Mietvertrag ocr_result 包含 _contract_metadata。"""
        meta = ocr_mietvertrag.get("_contract_metadata")
        assert meta is not None
        assert meta["tenant_name"] == "DI Maria Steiner"
        assert meta["landlord_name"] == "Ing. Thomas Gruber"
        assert Decimal(meta["monthly_rent"]) == Decimal("867.00")
        assert Decimal(meta["kaution"]) == Decimal("1860.00")

    @pytest.mark.p0
    def test_role_is_tenant(self, ocr_mietvertrag):
        """合同识别用户为 tenant（不是 landlord）。"""
        meta = ocr_mietvertrag["_contract_metadata"]
        # tenant_name 应匹配用户，landlord_name 不匹配
        assert meta["tenant_name"] == "DI Maria Steiner"
        assert meta["landlord_name"] != "DI Maria Steiner"

    def test_property_address_extracted(self, ocr_mietvertrag):
        """提取 property_address。"""
        meta = ocr_mietvertrag["_contract_metadata"]
        assert "Landstrasser" in meta["property_address"]
        assert "1030" in meta["property_address"]
