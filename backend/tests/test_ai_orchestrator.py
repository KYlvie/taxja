"""
Tests for the AI Orchestrator — intent detection, tool dispatch, and response formatting.
"""
import pytest
import app.services.ai_orchestrator as ai_orchestrator
from app.services.ai_orchestrator import (
    detect_intent,
    UserIntent,
    IntentResult,
    _extract_numeric_params,
    _format_income_tax,
    _format_vat,
    _format_svs,
    _format_kest,
    _format_deductibility,
    _format_classification,
    _format_what_if,
    _get_suggestions,
)


# ===================================================================
# Intent detection tests
# ===================================================================

class TestIntentDetection:
    """Test intent detection from user messages."""

    # -- Income tax calculation --

    @pytest.mark.parametrize("message", [
        "Berechne meine Einkommensteuer für €50.000",
        "Calculate tax for €80,000",
        "计算€60000的所得税",
        "Wie viel Steuer muss ich zahlen bei €45.000?",
        "How much tax do I pay on €100,000?",
        "我要交多少税？收入€70000",
        "Rechne mir die Steuerlast aus",
    ])
    def test_detect_calculate_tax(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.CALCULATE_TAX
        assert result.confidence >= 0.8

    # -- VAT calculation --

    @pytest.mark.parametrize("message", [
        "Berechne USt für €40.000 Umsatz",
        "Calculate VAT for €30,000 revenue",
        "计算增值税 €40000",
        "Umsatzsteuer berechnen für €30.000",
        "Kleinunternehmerregelung — bin ich unter der Grenze?",
    ])
    def test_detect_calculate_vat(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.CALCULATE_VAT
        assert result.confidence >= 0.8

    # -- SVS calculation --

    @pytest.mark.parametrize("message", [
        "Berechne SVS-Beiträge für €60.000",
        "Calculate SVS contributions for €50,000",
        "计算SVS社保缴费",
        "Sozialversicherungsbeiträge berechnen für €40.000",
    ])
    def test_detect_calculate_svs(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.CALCULATE_SVS
        assert result.confidence >= 0.8

    # -- KESt --

    @pytest.mark.parametrize("message", [
        "Berechne KESt für €10.000 Dividenden",
        "How much KESt on €5,000 dividends?",
        "计算资本利得税 €10000",
        "Kapitalertragsteuer berechnen für €8.000",
        "Dividenden Steuer auf €10.000",
    ])
    def test_detect_calculate_kest(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.CALCULATE_KEST
        assert result.confidence >= 0.8

    # -- Deductibility --

    @pytest.mark.parametrize("message", [
        "Ist mein Laptop absetzbar?",
        "Can I deduct my home office expenses?",
        "这个能抵扣吗？可以抵扣",
        "Kann ich die Fahrtkosten absetzen?",
        "Is my gym membership deductible?",
    ])
    def test_detect_check_deductibility(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.CHECK_DEDUCTIBILITY
        assert result.confidence >= 0.8

    # -- Tax optimization --

    @pytest.mark.parametrize("message", [
        "Wie kann ich Steuern sparen?",
        "Tax optimization tips for my situation",
        "节税建议",
        "Steueroptimierung Vorschläge bitte",
    ])
    def test_detect_optimize_tax(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.OPTIMIZE_TAX
        assert result.confidence >= 0.8

    # -- What-if --

    @pytest.mark.parametrize("message", [
        "Was wäre wenn ich €80.000 verdiene statt €60.000?",
        "What if I earn €100,000?",
        "如果我收入多€20000会怎样？",
        "€50.000 vs €70.000 Vergleich",
    ])
    def test_detect_what_if(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.WHAT_IF
        assert result.confidence >= 0.8

    # -- Summary --

    @pytest.mark.parametrize("message", [
        "Gib mir einen Überblick meiner Steuersituation",
        "Summary of my tax situation",
        "总结我的税务情况",
        "Wie stehe ich steuerlich?",
    ])
    def test_detect_summarize(self, message):
        result = detect_intent(message)
        assert result.intent == UserIntent.SUMMARIZE_STATUS
        assert result.confidence >= 0.8

    # -- Fallback to TAX_QA --

    @pytest.mark.parametrize("message", [
        "Hallo",
        "Was ist der Unterschied zwischen E1 und L1?",
        "Tell me about Austrian tax system",
        "你好",
    ])
    def test_fallback_to_tax_qa(self, message, monkeypatch):
        monkeypatch.setattr(ai_orchestrator, "_llm_intent_fallback", lambda _: None)
        result = detect_intent(message)
        assert result.intent == UserIntent.TAX_QA
        assert result.confidence >= 0.4

    def test_llm_fallback_can_promote_document_explanation(self, monkeypatch):
        monkeypatch.setattr(
            ai_orchestrator,
            "_llm_intent_fallback",
            lambda _: IntentResult(intent=UserIntent.EXPLAIN_DOCUMENT, confidence=0.8),
        )
        result = detect_intent("Was ist der Unterschied zwischen E1 und L1?")
        assert result.intent == UserIntent.EXPLAIN_DOCUMENT
        assert result.confidence == 0.8


# ===================================================================
# Numeric parameter extraction tests
# ===================================================================

class TestNumericExtraction:
    """Test extraction of amounts and years from messages."""

    def test_extract_euro_prefix(self):
        params = _extract_numeric_params("berechne steuer für €50.000")
        assert params.get("amount") == 50000.0

    def test_extract_euro_suffix(self):
        params = _extract_numeric_params("einkommen 80.000€")
        assert params.get("amount") == 80000.0

    def test_extract_euro_word(self):
        params = _extract_numeric_params("income 60000 euro")
        assert params.get("amount") == 60000.0

    def test_extract_year(self):
        params = _extract_numeric_params("steuer für 2025 berechnen €50.000")
        assert params.get("year") == 2025
        assert params.get("amount") == 50000.0

    def test_extract_multiple_amounts(self):
        params = _extract_numeric_params("was wäre wenn €40.000 vs €60.000")
        assert params.get("amount") == 40000.0
        assert len(params.get("amounts", [])) == 2

    def test_no_amount(self):
        params = _extract_numeric_params("wie viel steuer muss ich zahlen")
        assert "amount" not in params

    def test_labeled_amount(self):
        params = _extract_numeric_params("einkommen: 75000")
        assert params.get("amount") == 75000.0


# ===================================================================
# Response formatter tests
# ===================================================================

class TestFormatters:
    """Test response formatting for each intent type."""

    def test_format_income_tax_de(self):
        data = {
            "gross_income": 50000,
            "total_tax": 8500,
            "net_income": 41500,
            "effective_rate": 17.0,
            "tax_year": 2026,
        }
        text = _format_income_tax(data, "de")
        assert "Einkommensteuerberechnung" in text
        assert "50,000" in text or "50.000" in text
        assert "8,500" in text or "8.500" in text

    def test_format_income_tax_en(self):
        data = {
            "gross_income": 50000,
            "total_tax": 8500,
            "net_income": 41500,
            "effective_rate": 17.0,
            "tax_year": 2026,
        }
        text = _format_income_tax(data, "en")
        assert "Income Tax Calculation" in text

    def test_format_income_tax_zh(self):
        data = {
            "gross_income": 50000,
            "total_tax": 8500,
            "net_income": 41500,
            "effective_rate": 17.0,
            "tax_year": 2026,
        }
        text = _format_income_tax(data, "zh")
        assert "所得税计算" in text

    def test_format_vat(self):
        data = {
            "revenue": 40000,
            "vat_rate": 20.0,
            "vat_amount": 8000,
            "total_with_vat": 48000,
            "is_small_business": True,
        }
        text = _format_vat(data, "de")
        assert "USt-Berechnung" in text
        assert "Ja ✅" in text

    def test_format_svs(self):
        data = {
            "annual_income": 60000,
            "health_insurance": 4080,
            "pension_insurance": 11100,
            "accident_insurance": 12.17,
            "self_employed_provision": 918,
            "total_contributions": 16110.17,
        }
        text = _format_svs(data, "en")
        assert "SVS Contributions" in text
        assert "Health insurance" in text

    def test_format_kest(self):
        data = {
            "total_gross": 10000,
            "total_tax": 2750,
            "total_already_withheld": 0,
            "remaining_tax_due": 2750,
        }
        text = _format_kest(data, "zh")
        assert "资本利得税" in text

    def test_format_deductibility_yes(self):
        data = {
            "is_deductible": True,
            "description": "Laptop",
            "explanation": "Work equipment is deductible",
        }
        text = _format_deductibility(data, "en")
        assert "✅ Deductible" in text

    def test_format_deductibility_no(self):
        data = {
            "is_deductible": False,
            "description": "Gym membership",
            "explanation": "Personal expenses are not deductible",
        }
        text = _format_deductibility(data, "de")
        assert "❌ Nicht absetzbar" in text

    def test_format_classification(self):
        data = {
            "predicted_category": "office_supplies",
            "confidence": 0.92,
            "method": "rule",
        }
        text = _format_classification(data, "de")
        assert "Klassifizierung" in text
        assert "office_supplies" in text

    def test_format_what_if(self):
        data = {
            "base_income": 40000,
            "scenario_income": 60000,
            "base_tax": 6000,
            "scenario_tax": 12000,
            "tax_difference": 6000,
        }
        text = _format_what_if(data, "en")
        assert "What-if Simulation" in text
        assert "Difference" in text


# ===================================================================
# Suggestions tests
# ===================================================================

class TestSuggestions:
    """Test follow-up suggestion generation."""

    def test_suggestions_for_tax_calc_de(self):
        suggestions = _get_suggestions(UserIntent.CALCULATE_TAX, "de")
        assert len(suggestions) > 0
        assert any("SVS" in s for s in suggestions)

    def test_suggestions_for_tax_calc_en(self):
        suggestions = _get_suggestions(UserIntent.CALCULATE_TAX, "en")
        assert len(suggestions) > 0

    def test_suggestions_for_tax_calc_zh(self):
        suggestions = _get_suggestions(UserIntent.CALCULATE_TAX, "zh")
        assert len(suggestions) > 0

    def test_suggestions_for_unknown_intent(self):
        suggestions = _get_suggestions(UserIntent.UNKNOWN, "de")
        assert suggestions == []  # no suggestions for unknown


# ===================================================================
# IntentResult dataclass tests
# ===================================================================

class TestIntentResult:
    """Test IntentResult dataclass."""

    def test_default_params(self):
        r = IntentResult(intent=UserIntent.TAX_QA, confidence=0.5)
        assert r.params == {}

    def test_with_params(self):
        r = IntentResult(
            intent=UserIntent.CALCULATE_TAX,
            confidence=0.95,
            params={"amount": 50000, "year": 2026},
        )
        assert r.params["amount"] == 50000
        assert r.params["year"] == 2026
