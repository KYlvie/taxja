"""Document type classification for OCR"""
import re
from enum import Enum
from typing import Tuple, Dict, Optional
import numpy as np


class DocumentType(str, Enum):
    """Supported document types"""

    PAYSLIP = "payslip"  # Lohnzettel / Gehaltsabrechnung
    RECEIPT = "receipt"  # Supermarket receipt / Kassenbon
    INVOICE = "invoice"  # Rechnung
    RENTAL_CONTRACT = "rental_contract"  # Mietvertrag
    KAUFVERTRAG = "kaufvertrag"  # Property purchase contract
    MIETVERTRAG = "mietvertrag"  # Rental contract (detailed)
    BANK_STATEMENT = "bank_statement"  # Kontoauszug
    PROPERTY_TAX = "property_tax"  # Grundsteuer
    SVS_NOTICE = "svs_notice"  # SVS Beitragsmitteilung
    LOHNZETTEL = "lohnzettel"  # Official tax wage slip
    EINKOMMENSTEUERBESCHEID = "einkommensteuerbescheid"  # Income tax assessment
    E1_FORM = "e1_form"  # E1 tax declaration form
    UNKNOWN = "unknown"


class DocumentClassifier:
    """Classify document types based on content and patterns"""

    def __init__(self):
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[DocumentType, Dict]:
        """Load classification patterns for each document type"""
        return {
            DocumentType.LOHNZETTEL: {
                "keywords": [
                    "lohnzettel",
                    "gehaltszettel",
                    "gehaltsabrechnung",
                    "brutto",
                    "netto",
                    "lohnsteuer",
                    "sozialversicherung",
                    "arbeitgeber",
                    "arbeitnehmer",
                    "gehalt",
                    "auszahlungsbetrag",
                    "auszahlungsmonat",
                    "personalnummer",
                    "sv/kfa",
                    "summe abz",
                    "summe bez",
                    "pendlereuro",
                    "familienbonus",
                    "lst-basis",
                    "sv-basis",
                    "l16",
                    "finanzamt",
                    "steuernummer",
                    "versicherungsnummer",
                ],
                "required_keywords": [],
                "required_any": ["gehalt", "lohnsteuer", "auszahlungsbetrag",
                                 "gehaltszettel", "lohnzettel", "gehaltsabrechnung",
                                 "auszahlungsmonat", "personalnummer", "l16"],
                "weight": 1.3,
            },
            DocumentType.RECEIPT: {
                "keywords": [
                    "billa",
                    "spar",
                    "hofer",
                    "lidl",
                    "merkur",
                    "penny",
                    "kassenbon",
                    "bon-nr",
                    "kasse",
                    "summe",
                    "bar",
                    "karte",
                ],
                "required_keywords": [],
                "weight": 0.9,
            },
            DocumentType.INVOICE: {
                "keywords": [
                    "rechnung",
                    "rechnungsnummer",
                    "invoice",
                    "ust-id",
                    "uid",
                    "zahlbar",
                    "lieferant",
                    "kunde",
                    "gesamtpreis",
                    "zahlbetrag",
                    "rechnungsbetrag",
                    "total amount due",
                    "payment due",
                    "commission",
                ],
                "required_keywords": [],
                "weight": 1.0,
            },
            DocumentType.SVS_NOTICE: {
                "keywords": [
                    "svs",
                    "sozialversicherung",
                    "beitrag",
                    "versicherungsnummer",
                    "beitragsgrundlage",
                    "pensionsversicherung",
                    "krankenversicherung",
                    "unfallversicherung",
                ],
                "required_keywords": ["svs", "beitrag"],
                "weight": 1.0,
            },
            DocumentType.RENTAL_CONTRACT: {
                "keywords": [
                    "mietvertrag",
                    "miete",
                    "vermieter",
                    "mieter",
                    "wohnung",
                    "kaution",
                    "mietbeginn",
                    "mietdauer",
                    "lager",
                    "kontoeingang",
                    "pacht",
                ],
                "required_keywords": [],
                "required_any": ["mietvertrag", "miete", "vermieter", "pacht"],
                "weight": 1.0,
            },
            DocumentType.KAUFVERTRAG: {
                "keywords": [
                    "kaufvertrag",
                    "kaufpreis",
                    "käufer",
                    "kaufer",
                    "verkäufer",
                    "verkaufer",
                    "grundstück",
                    "grundstuck",
                    "liegenschaft",
                    "eigentum",
                    "notar",
                    "grundbuch",
                    "einlagezahl",
                    "katastralgemeinde",
                    "grunderwerbsteuer",
                    "übergabe",
                    "ubergabe",
                    "übernahme",
                    "ubernahme",
                    "immobilie",
                    "wohnungseigentum",
                    "kaufgegenstand",
                    "kaufobjekt",
                    "gebäude",
                    "gebaude",
                    "baujahr",
                    "nutzfläche",
                    "nutzflache",
                    "als kauferin",
                    "als käuferin",
                ],
                "required_keywords": [],
                "required_any": ["kaufvertrag", "kaufpreis", "käufer", "kaufer",
                                 "verkäufer", "verkaufer", "grundstück", "grundstuck"],
                "weight": 1.2,
            },
            DocumentType.MIETVERTRAG: {
                "keywords": [
                    "mietvertrag",
                    "mietzins",
                    "hauptmietzins",
                    "betriebskosten",
                    "vermieter",
                    "mieter",
                    "mietobjekt",
                    "mietgegenstand",
                    "wohnung",
                    "kaution",
                    "mietbeginn",
                    "mietdauer",
                    "kündigungsfrist",
                    "kundigungsfrist",
                    "befristung",
                    "unbefristet",
                    "indexanpassung",
                    "heizkosten",
                    "warmwasser",
                    "strom",
                    "gas",
                    "mietrechtsgesetz",
                    "kategorie",
                ],
                "required_keywords": [],
                "required_any": ["mietvertrag", "mietzins", "hauptmietzins", "mietobjekt", "mietgegenstand"],
                "weight": 1.2,
            },
            DocumentType.BANK_STATEMENT: {
                "keywords": [
                    "kontoauszug",
                    "iban",
                    "bic",
                    "saldo",
                    "buchung",
                    "lastschrift",
                    "gutschrift",
                    "kontoeingang",
                    "kontostand",
                ],
                "required_keywords": [],
                "required_any": ["kontoauszug", "saldo", "buchung", "kontostand"],
                "weight": 0.9,
            },
            DocumentType.PROPERTY_TAX: {
                "keywords": [
                    "grundsteuer",
                    "immobiliensteuer",
                    "liegenschaft",
                    "einheitswert",
                    "steuernummer",
                ],
                "required_keywords": ["grundsteuer"],
                "weight": 1.0,
            },
            DocumentType.EINKOMMENSTEUERBESCHEID: {
                "keywords": [
                    "einkommensteuerbescheid",
                    "steuerberechnung",
                    "einkommensteuer",
                    "abgabengutschrift",
                    "abgabennachforderung",
                    "festgesetzte einkommensteuer",
                    "gesamtbetrag der einkuenfte",
                    "gesamtbetrag der einkünfte",
                    "steuer vor abzug",
                    "steuer nach abzug",
                    "absetzbetraege",
                    "absetzbeträge",
                    "verkehrsabsetzbetrag",
                    "anrechenbare lohnsteuer",
                    "negativsteuer",
                    "finanzamt",
                    "einkommen im jahr",
                ],
                "required_keywords": [],
                "required_any": [
                    "einkommensteuerbescheid",
                    "steuerberechnung",
                    "festgesetzte einkommensteuer",
                    "abgabengutschrift",
                    "abgabennachforderung",
                ],
                "weight": 1.5,
            },
            DocumentType.E1_FORM: {
                "keywords": [
                    "einkommensteuererklärung",
                    "einkommensteuererklaerung",
                    "e 1-edv",
                    "e 1-pdf",
                    "e 1,",
                    "formular e1",
                    "steuererklärung",
                    "steuererklaerung",
                    "veranlagung",
                    "kennzahl",
                    "kz 245",
                    "kz 350",
                    "nichtselbständiger arbeit",
                    "vermietung und verpachtung",
                    "sonderausgaben",
                    "werbungskosten",
                    "außergewöhnliche belastungen",
                    "verlustvortrag",
                    "familienbonus",
                    "e 1b",
                    "e 1b-pdf",
                    "l 1k",
                    "beilage zur einkommensteuererklärung",
                ],
                "required_keywords": [],
                "required_any": [
                    "einkommensteuererklärung",
                    "einkommensteuererklaerung",
                    "e 1-edv",
                    "e 1-pdf",
                    "steuererklärung für",
                ],
                "weight": 1.8,
            },
        }

    def classify(self, image: np.ndarray, text: str) -> Tuple[DocumentType, float]:
        """
        Classify document type based on extracted text

        Args:
            image: Document image (for future ML-based classification)
            text: Extracted text from OCR

        Returns:
            Tuple of (document_type, confidence_score)
        """
        # Method 1: Pattern-based classification
        pattern_result = self._classify_by_patterns(text)

        # Method 2: ML-based classification (placeholder for future enhancement)
        # ml_result = self._classify_by_ml(image, text)

        # For now, use pattern-based classification
        return pattern_result["type"], pattern_result["confidence"]

    def _classify_by_patterns(self, text: str) -> Dict:
        """
        Classify document using keyword pattern matching

        Args:
            text: Extracted text from OCR

        Returns:
            Dictionary with type and confidence
        """
        text_lower = text.lower()

        # Early detection: E1 forms are multi-page and contain keywords that match
        # many other types (Lohnzettel, Bescheid, etc.). Check the first page for
        # definitive E1 markers to avoid misclassification.
        first_page = text_lower[:1500]
        if any(marker in first_page for marker in [
            "e 1-pdf", "e 1-edv", "e 1,",
            "einkommensteuererklärung für",
            "einkommensteuererklaerung fuer",
        ]):
            return {"type": DocumentType.E1_FORM, "confidence": 0.90}

        scores = {}

        for doc_type, pattern_info in self.patterns.items():
            score = 0.0
            keyword_matches = 0

            # Check required keywords first (ALL must match)
            required_keywords = pattern_info.get("required_keywords", [])
            if required_keywords:
                required_found = all(
                    keyword in text_lower for keyword in required_keywords
                )
                if not required_found:
                    scores[doc_type] = 0.0
                    continue

            # Check required_any keywords (at least ONE must match)
            required_any = pattern_info.get("required_any", [])
            if required_any:
                any_found = any(
                    keyword in text_lower for keyword in required_any
                )
                if not any_found:
                    scores[doc_type] = 0.0
                    continue

            # Count keyword matches
            for keyword in pattern_info["keywords"]:
                if keyword in text_lower:
                    keyword_matches += 1

            # Calculate score
            if keyword_matches > 0:
                match_ratio = keyword_matches / len(pattern_info["keywords"])
                score = match_ratio * pattern_info["weight"]

                # Boost score if required keywords are present
                if required_keywords and all(
                    keyword in text_lower for keyword in required_keywords
                ):
                    score *= 1.2

                # Boost score for required_any matches
                if required_any:
                    any_count = sum(1 for k in required_any if k in text_lower)
                    score *= (1.0 + 0.1 * any_count)

            scores[doc_type] = min(score, 1.0)

        # Find best match
        if not scores or max(scores.values()) == 0:
            return {"type": DocumentType.UNKNOWN, "confidence": 0.3}

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        return {"type": best_type, "confidence": confidence}

    def classify_austrian_merchant(self, text: str) -> Optional[str]:
        """
        Identify Austrian merchant from text

        Args:
            text: Extracted text

        Returns:
            Merchant name if found, None otherwise
        """
        text_lower = text.lower()

        # Common Austrian merchants
        merchants = {
            "billa": "BILLA AG",
            "spar": "SPAR ?sterreich",
            "hofer": "HOFER KG",
            "lidl": "Lidl ?sterreich",
            "merkur": "MERKUR",
            "penny": "PENNY",
            "obi": "OBI Bau- und Heimwerkerm?rkte",
            "baumax": "bauMax",
            "hornbach": "HORNBACH",
            "dm": "dm drogerie markt",
            "m?ller": "M?ller Drogerie",
            "interspar": "INTERSPAR",
        }

        for key, official_name in merchants.items():
            if key in text_lower:
                return official_name

        return None

    def get_document_characteristics(self, text: str) -> Dict:
        """
        Extract document characteristics for classification

        Args:
            text: Extracted text

        Returns:
            Dictionary of characteristics
        """
        text_lower = text.lower()

        characteristics = {
            "has_date": bool(re.search(r"\d{2}\.\d{2}\.\d{4}", text)),
            "has_amount": bool(re.search(r"?\s*\d+[,\.]\d{2}", text)),
            "has_vat": "ust" in text_lower or "mwst" in text_lower,
            "has_iban": bool(re.search(r"AT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}", text)),
            "has_tax_number": "steuernummer" in text_lower or "stnr" in text_lower,
            "has_merchant": self.classify_austrian_merchant(text) is not None,
            "language": self._detect_language(text),
            "line_count": len(text.split("\n")),
            "word_count": len(text.split()),
        }

        return characteristics

    def _detect_language(self, text: str) -> str:
        """
        Detect primary language of text

        Args:
            text: Input text

        Returns:
            Language code ('de' or 'en')
        """
        text_lower = text.lower()

        # German indicators
        german_words = ["und", "der", "die", "das", "mit", "f?r", "von", "zu", "auf"]
        german_count = sum(1 for word in german_words if word in text_lower)

        # English indicators
        english_words = ["and", "the", "with", "for", "from", "to", "on", "at"]
        english_count = sum(1 for word in english_words if word in text_lower)

        return "de" if german_count > english_count else "en"

    def suggest_document_type(self, characteristics: Dict) -> DocumentType:
        """
        Suggest document type based on characteristics

        Args:
            characteristics: Document characteristics

        Returns:
            Suggested document type
        """
        # Receipt indicators
        if characteristics["has_merchant"] and characteristics["has_amount"]:
            return DocumentType.RECEIPT

        # Invoice indicators
        if characteristics["has_vat"] and characteristics["has_amount"]:
            return DocumentType.INVOICE

        # Bank statement indicators
        if characteristics["has_iban"]:
            return DocumentType.BANK_STATEMENT

        # Payslip indicators
        if characteristics["has_tax_number"] and characteristics["has_amount"]:
            return DocumentType.PAYSLIP

        return DocumentType.UNKNOWN







