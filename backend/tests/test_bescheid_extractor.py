"""Tests for Einkommensteuerbescheid extractor"""
import pytest
from decimal import Decimal
from app.services.bescheid_extractor import BescheidExtractor


# Sample OCR text based on the real Steuerberechnung document
SAMPLE_BESCHEID_TEXT = """
Steuerberechnung für 2023

Zhang Fenghong
FA:    Finanzamt Österreich
St.Nr.: 03 627/7572

Verkehrsabsetzbetrag           Ja      Anzahl der Kinder                    1
Pensionistenabsetzbetrag       Nein    Mehrkinderzuschlag                Nein
Alleinverdienerabsetzbetrag    Nein    Unterhaltsabsetzbetrag            Nein
Alleinerzieherabsetzbetrag     Nein

VORAUSSICHTLICHER EINKOMMENSTEUERBESCHEID
2023

Die Einkommensteuer wird für das Jahr 2023
voraussichtlich festgesetzt mit                                    -3.794,00
Bisher war vorgeschrieben                                              0,00
Voraussichtliche Abgabengutschrift in Höhe von                     3.794,00
Das Einkommen im Jahr 2023 beträgt                                10.513,51

Berechnung der Einkommensteuer:

Einkünfte aus nichtselbständiger Arbeit
  Bezugsauszahlende Stelle                    stpfl.Bezüge (245)

    MAGISTRAT DER STADT WIEN                    11.593,33
    Pauschbetrag für Werbungskosten                -132,00
    Telearbeitspauschale lt. Lohnzettel (26 Tage x 3,00 EUR)  -78,00     11.383,33
  Einkünfte aus Vermietung und Verpachtung
    E1b, Thenneberg 51, 2571 Altenmarkt an der Triesting      -869,82
    E1b, Angeligasse 86 14, 1100 Wien                            0,00      -869,82
  Gesamtbetrag der Einkünfte                                           10.513,51
  Einkommen                                                            10.513,51

  Steuer vor Abzug der Absetzbeträge                                       0,00

  Verkehrsabsetzbetrag                                                -1.105,00

  Durchschnittssteuersatz in % (-1.105,00 / 10.513,51 x 100)    0,00
  Grenzsteuersatz in %                                           0,00
  Steuer nach Abzug der Absetzbeträge                                 -1.105,00
  Erstattung gemäß § 33 (8) EStG 1988:
  Für SV-Beiträge                                                     -1.105,00
  Erstattungsfähige Negativsteuer                                     -1.105,00
  Steuer sonstige Bezüge wie z. B. 13. und 14. Bezug (220) unter
  Berücksichtigung der Einschleifregelung                                  0,00
  Einkommensteuer                                                     -1.105,00
  Anrechenbare Lohnsteuer (260)                                       -2.689,42
  Festgesetzte Einkommensteuer - gerundet gem. § 39 (3)               -3.794,00

Berechnung der Abgabennachforderung /
Abgabengutschrift
  Festgesetzte Einkommensteuer                                        -3.794,00
  Abgabengutschrift                                                    3.794,00
"""


@pytest.fixture
def extractor():
    return BescheidExtractor()


class TestBescheidExtractor:
    """Test extraction from Steuerberechnung document"""

    def test_extract_tax_year(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.tax_year == 2023

    def test_extract_taxpayer_name(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.taxpayer_name == "Zhang Fenghong"

    def test_extract_finanzamt(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert "Finanzamt" in data.finanzamt

    def test_extract_steuernummer(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.steuernummer is not None
        assert "627" in data.steuernummer

    def test_extract_anzahl_kinder(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.anzahl_kinder == 1

    def test_extract_header_flags(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.verkehrsabsetzbetrag is True
        assert data.alleinverdiener is False
        assert data.alleinerzieher is False

    def test_extract_einkommen(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.einkommen == Decimal("10513.51")

    def test_extract_festgesetzte_einkommensteuer(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.festgesetzte_einkommensteuer is not None
        assert data.festgesetzte_einkommensteuer == Decimal("3794.00") or \
               data.festgesetzte_einkommensteuer == Decimal("-3794.00")

    def test_extract_abgabengutschrift(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.abgabengutschrift == Decimal("3794.00")

    def test_extract_werbungskosten(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.werbungskosten_pauschale == Decimal("132.00")

    def test_extract_telearbeitspauschale(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.telearbeitspauschale is not None
        assert data.telearbeitspauschale == Decimal("78.00")

    def test_extract_vermietung_details(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert len(data.vermietung_details) >= 1
        # Thenneberg property should have negative amount (loss)
        thenneberg = [d for d in data.vermietung_details if "Thenneberg" in d.get("address", "")]
        assert len(thenneberg) == 1
        assert thenneberg[0]["amount"] == Decimal("-869.82")

    def test_extract_anrechenbare_lohnsteuer(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.anrechenbare_lohnsteuer is not None

    def test_extract_verkehrsabsetzbetrag_amount(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.verkehrsabsetzbetrag_betrag == Decimal("1105.00")

    def test_confidence_is_reasonable(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        assert data.confidence >= 0.7

    def test_to_dict(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        result = extractor.to_dict(data)
        assert isinstance(result, dict)
        assert result["tax_year"] == 2023
        assert isinstance(result.get("einkommen"), (float, int, type(None)))

    def test_empty_text_returns_low_confidence(self, extractor):
        data = extractor.extract("")
        assert data.confidence < 0.3
        assert data.tax_year is None

    def test_employer_extraction(self, extractor):
        data = extractor.extract(SAMPLE_BESCHEID_TEXT)
        # Should extract MAGISTRAT DER STADT WIEN
        assert data.employer_name is not None
        assert "MAGISTRAT" in data.employer_name.upper() or "WIEN" in data.employer_name.upper()
