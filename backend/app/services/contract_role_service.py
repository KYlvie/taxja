"""Sensitive-document role and direction resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select

from app.core.config import settings
from app.models.document import DocumentType
from app.models.user import User
from app.services.document_classifier import _normalize_umlauts


SENSITIVE_DOCUMENT_MODES = {"legacy", "shadow", "strict"}
RENTAL_ROLES = {"landlord", "tenant", "unknown"}
PURCHASE_ROLES = {"buyer", "seller", "unknown"}
LOAN_ROLES = {"borrower", "unknown"}
INSURANCE_ROLES = {"policy_holder", "unknown"}
DIRECTION_VALUES = {"expense", "income", "unknown"}
COMMERCIAL_DOCUMENT_SEMANTICS = {
    "receipt",
    "standard_invoice",
    "credit_note",
    "proforma",
    "delivery_note",
    "unknown",
}
BLOCKING_COMMERCIAL_SEMANTICS = {"proforma", "delivery_note"}


def _normalize_mode(raw_value: str | None, *, default: str) -> str:
    mode = (raw_value or default).strip().lower()
    return mode if mode in SENSITIVE_DOCUMENT_MODES else default


def get_sensitive_document_mode() -> str:
    configured = _normalize_mode(getattr(settings, "SENSITIVE_DOCUMENT_MODE", ""), default="")
    if configured:
        return configured
    return _normalize_mode(getattr(settings, "CONTRACT_ROLE_MODE", "legacy"), default="legacy")


def get_contract_role_mode() -> str:
    """Temporary alias while older call sites migrate."""
    return get_sensitive_document_mode()


@dataclass(slots=True)
class SensitiveUserContext:
    id: int
    name: str | None = None
    business_name: str | None = None
    email: str | None = None
    user_type: object | None = None
    business_type: str | None = None
    business_industry: str | None = None
    vat_status: object | None = None
    gewinnermittlungsart: object | None = None
    tax_number: str | None = None
    vat_number: str | None = None
    language: str | None = None

    @property
    def full_name(self) -> str | None:
        return self.name


def load_sensitive_user_context(db, user_id: int) -> SensitiveUserContext | None:
    row = db.execute(
        select(
            User.id,
            User.name,
            User.business_name,
            User.email,
            User.user_type,
            User.business_type,
            User.business_industry,
            User.vat_status,
            User.gewinnermittlungsart,
            User.tax_number,
            User.vat_number,
            User.language,
        ).where(User.id == user_id)
    ).first()
    if not row:
        return None

    values = row._mapping
    return SensitiveUserContext(
        id=values["id"],
        name=values["name"],
        business_name=values["business_name"],
        email=values["email"],
        user_type=values["user_type"],
        business_type=values["business_type"],
        business_industry=values["business_industry"],
        vat_status=values["vat_status"],
        gewinnermittlungsart=values["gewinnermittlungsart"],
        tax_number=values["tax_number"],
        vat_number=values["vat_number"],
        language=values["language"],
    )


@dataclass(slots=True)
class ContractRoleResolution:
    role_family: str
    candidate: str
    confidence: float
    source: str
    evidence: list[str]
    auto_action_role: str
    mode: str
    normalized_from: str | None = None

    @property
    def strict_would_block(self) -> bool:
        return self.candidate != self.auto_action_role

    def to_payload(self) -> dict:
        payload = {
            "role_family": self.role_family,
            "candidate": self.candidate,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "evidence": list(self.evidence),
            "auto_action_role": self.auto_action_role,
            "strict_would_block": self.strict_would_block,
            "mode": self.mode,
        }
        if self.normalized_from:
            payload["normalized_from"] = self.normalized_from
        return payload


@dataclass(slots=True)
class TransactionDirectionResolution:
    candidate: str
    confidence: float
    source: str
    evidence: list[str]
    semantics: str
    is_reversal: bool
    mode: str
    gate_enabled: bool = True
    normalized_from: str | None = None

    @property
    def strict_would_block(self) -> bool:
        if not self.gate_enabled:
            return False
        return self.candidate == "unknown" or self.semantics in BLOCKING_COMMERCIAL_SEMANTICS

    def to_payload(self) -> dict:
        payload = {
            "candidate": self.candidate,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "evidence": list(self.evidence),
            "semantics": self.semantics,
            "is_reversal": self.is_reversal,
            "strict_would_block": self.strict_would_block,
            "mode": self.mode,
            "gate_enabled": self.gate_enabled,
        }
        if self.normalized_from:
            payload["normalized_from"] = self.normalized_from
        return payload


def role_allows_expected_action(role_family: str, role: str | None) -> bool:
    expected_role_map = {
        "rental": "landlord",
        "purchase": "buyer",
        "loan": "borrower",
        "insurance": "policy_holder",
    }
    expected_role = expected_role_map.get(role_family, "unknown")
    return (role or "unknown") == expected_role


def direction_allows_auto_create(resolution: TransactionDirectionResolution | None) -> bool:
    if resolution is None:
        return True
    return not resolution.strict_would_block


_EVIDENCE_MESSAGES: dict[str, dict[str, str]] = {
    "manual_role_selected": {
        "de": "Benutzer hat die Rolle '{role}' in der Überprüfung explizit ausgewählt.",
        "en": "User explicitly selected role '{role}' in review.",
        "zh": "用户在审核中明确选择了角色 '{role}'。",
        "fr": "L'utilisateur a explicitement selectionne le role '{role}' lors de la verification.",
        "ru": "Пользователь явно выбрал роль '{role}' при проверке.",
        "hu": "A felhasznalo kifejezetten a(z) '{role}' szerepet valasztotta az ellenorzesnel.",
        "pl": "Uzytkownik jawnie wybral role '{role}' podczas przegladu.",
        "tr": "Kullanici inceleme sirasinda '{role}' rolunu acikca secti.",
        "bs": "Korisnik je izricito odabrao ulogu '{role}' prilikom pregleda.",
    },
    "property_context": {
        "de": "Dokument wurde aus einem bestehenden Immobilien-/Vermögenswert-Kontext hochgeladen.",
        "en": "Document was uploaded from an existing property/asset context.",
        "zh": "文档是从现有的房产/资产上下文中上传的。",
        "fr": "Le document a ete telecharge depuis un contexte de propriete/actif existant.",
        "ru": "Документ был загружен из существующего контекста недвижимости/актива.",
        "hu": "A dokumentumot egy meglevo ingatlan/eszkoz kontextusbol toltottek fel.",
        "pl": "Dokument zostal przeslany z istniejacego kontekstu nieruchomosci/aktywow.",
        "tr": "Belge mevcut bir mulk/varlik baglaminden yuklendi.",
        "bs": "Dokument je ucitan iz postojeceg konteksta nekretnine/imovine.",
    },
    "user_near_positive_wording": {
        "de": "Benutzer wurde in der Nähe von {role}-seitiger Formulierung im Vertragstext erkannt.",
        "en": "Detected the user near {role}-side wording in the contract text.",
        "zh": "在合同文本中检测到用户位于{role}方措辞附近。",
        "fr": "Utilisateur detecte pres du libelle cote {role} dans le texte du contrat.",
        "ru": "Обнаружен пользователь рядом с формулировкой на стороне {role} в тексте договора.",
        "hu": "A felhasznalo a szerzodes szovegeben a(z) {role}-oldali megfogalmazas kozeleben talalhato.",
        "pl": "Wykryto uzytkownika w poblizu sformulowania po stronie {role} w tekscie umowy.",
        "tr": "Sozlesme metninde {role} tarafli ifadenin yakininda kullanici tespit edildi.",
        "bs": "Korisnik detektovan u blizini formulacije na strani {role} u tekstu ugovora.",
    },
    "user_near_negative_wording": {
        "de": "Benutzer wurde in der Nähe von {role}-seitiger Formulierung im Vertragstext erkannt.",
        "en": "Detected the user near {role}-side wording in the contract text.",
        "zh": "在合同文本中检测到用户位于{role}方措辞附近。",
        "fr": "Utilisateur detecte pres du libelle cote {role} dans le texte du contrat.",
        "ru": "Обнаружен пользователь рядом с формулировкой на стороне {role} в тексте договора.",
        "hu": "A felhasznalo a szerzodes szovegeben a(z) {role}-oldali megfogalmazas kozeleben talalhato.",
        "pl": "Wykryto uzytkownika w poblizu sformulowania po stronie {role} w tekscie umowy.",
        "tr": "Sozlesme metninde {role} tarafli ifadenin yakininda kullanici tespit edildi.",
        "bs": "Korisnik detektovan u blizini formulacije na strani {role} u tekstu ugovora.",
    },
    "exact_party_match": {
        "de": "Vertragspartei '{party}' stimmt genau mit Benutzer {label} überein.",
        "en": "Matched document party '{party}' exactly with user {label}.",
        "zh": "文档当事人 '{party}' 与用户{label}完全匹配。",
        "fr": "La partie du document '{party}' correspond exactement a l'utilisateur {label}.",
        "ru": "Сторона документа '{party}' точно совпадает с {label} пользователя.",
        "hu": "A dokumentum felel '{party}' pontosan megegyezik a felhasznalo {label} adataval.",
        "pl": "Strona dokumentu '{party}' dokladnie pasuje do {label} uzytkownika.",
        "tr": "Belge tarafi '{party}' kullanicinin {label} bilgisiyle tam olarak eslesti.",
        "bs": "Stranka dokumenta '{party}' se tocno podudara sa {label} korisnika.",
    },
    "partial_party_match": {
        "de": "Vertragspartei '{party}' stimmt teilweise mit Benutzer {label} überein.",
        "en": "Matched document party '{party}' partially with user {label}.",
        "zh": "文档当事人 '{party}' 与用户{label}部分匹配。",
        "fr": "La partie du document '{party}' correspond partiellement a l'utilisateur {label}.",
        "ru": "Сторона документа '{party}' частично совпадает с {label} пользователя.",
        "hu": "A dokumentum felel '{party}' reszlegesen megegyezik a felhasznalo {label} adataval.",
        "pl": "Strona dokumentu '{party}' czesciowo pasuje do {label} uzytkownika.",
        "tr": "Belge tarafi '{party}' kullanicinin {label} bilgisiyle kismen eslesti.",
        "bs": "Stranka dokumenta '{party}' se djelimicno podudara sa {label} korisnika.",
    },
    "negative_side_kept_unknown": {
        "de": "Dies sieht eher nach der {role}-Seite aus, daher bleibt die Benutzerrolle unbekannt, bis sie manuell bestätigt wird.",
        "en": "This looks more like the {role} side, so the user-facing role is kept as unknown until manually confirmed.",
        "zh": "这看起来更像是{role}方，因此用户角色保持为未知，直到手动确认。",
        "fr": "Cela ressemble davantage au cote {role}, le role utilisateur reste donc inconnu jusqu'a confirmation manuelle.",
        "ru": "Это больше похоже на сторону {role}, поэтому роль пользователя остаётся неизвестной до ручного подтверждения.",
        "hu": "Ez inkabb a(z) {role} oldalra hasonlit, ezert a felhasznaloi szerep ismeretlen marad a manualis megerositesig.",
        "pl": "Wyglada to bardziej na strone {role}, wiec rola uzytkownika pozostaje nieznana do recznego potwierdzenia.",
        "tr": "Bu daha cok {role} tarafi gibi gorunuyor, bu nedenle kullanici rolu manuel olarak onaylanana kadar bilinmiyor olarak kaliyor.",
        "bs": "Ovo vise lici na stranu {role}, pa korisnicka uloga ostaje nepoznata dok se rucno ne potvrdi.",
    },
    "extracted_counterparty": {
        "de": "Extrahierte {role}-seitige Vertragspartei '{party}' aus dem Dokument.",
        "en": "Extracted {role}-side counterparty '{party}' from the document.",
        "zh": "从文档中提取了{role}方当事人 '{party}'。",
        "fr": "Contrepartie cote {role} '{party}' extraite du document.",
        "ru": "Извлечена контрагентская сторона {role} '{party}' из документа.",
        "hu": "A(z) {role}-oldali szerzodo fel '{party}' kinyerve a dokumentumbol.",
        "pl": "Wyodrebniono kontrahenta po stronie {role} '{party}' z dokumentu.",
        "tr": "Belgeden {role} tarafli karsi taraf '{party}' cikarildi.",
        "bs": "Izvucena ugovorna strana na strani {role} '{party}' iz dokumenta.",
    },
    "negative_side_wording_detected": {
        "de": "{role}-seitige Formulierung im Vertragstext erkannt.",
        "en": "Detected {role}-side wording in the contract text.",
        "zh": "在合同文本中检测到{role}方措辞。",
        "fr": "Libelle cote {role} detecte dans le texte du contrat.",
        "ru": "Обнаружена формулировка стороны {role} в тексте договора.",
        "hu": "A(z) {role}-oldali megfogalmazas eszlelve a szerzodes szovegeben.",
        "pl": "Wykryto sformulowanie po stronie {role} w tekscie umowy.",
        "tr": "Sozlesme metninde {role} tarafli ifade tespit edildi.",
        "bs": "Otkrivena formulacija na strani {role} u tekstu ugovora.",
    },
    "both_sides_matched": {
        "de": "Beide Vertragsseiten stimmen mit dem Benutzerprofil überein, daher bleibt die Seite mehrdeutig.",
        "en": "Matched both contract sides to the user profile, so the side remains ambiguous.",
        "zh": "合同双方均与用户资料匹配，因此角色仍然模糊。",
        "fr": "Les deux cotes du contrat correspondent au profil utilisateur, le cote reste donc ambigu.",
        "ru": "Обе стороны договора совпали с профилем пользователя, поэтому сторона остаётся неоднозначной.",
        "hu": "Mindket szerzodesi oldal megegyezik a felhasznaloi profillal, ezert az oldal ketseges marad.",
        "pl": "Obie strony umowy pasuja do profilu uzytkownika, wiec strona pozostaje niejednoznaczna.",
        "tr": "Sozlesmenin her iki tarafi da kullanici profiline eslesti, bu nedenle taraf belirsiz kaliyor.",
        "bs": "Obje ugovorne strane se podudaraju sa profilom korisnika, pa strana ostaje nejasna.",
    },
    "no_reliable_match": {
        "de": "Keine zuverlässige Zuordnung zwischen Vertragsparteien und Benutzerprofil gefunden.",
        "en": "No reliable contract-side match was found between document parties and the user profile.",
        "zh": "在文档当事人与用户资料之间未找到可靠的合同方匹配。",
        "fr": "Aucune correspondance fiable n'a ete trouvee entre les parties du document et le profil utilisateur.",
        "ru": "Надёжного соответствия между сторонами документа и профилем пользователя не найдено.",
        "hu": "Nem talalhato megbizhato egyezes a dokumentum felei es a felhasznaloi profil kozott.",
        "pl": "Nie znaleziono niezawodnego dopasowania miedzy stronami dokumentu a profilem uzytkownika.",
        "tr": "Belge taraflari ile kullanici profili arasinda guvenilir bir esleme bulunamadi.",
        "bs": "Nije pronadjeno pouzdano poklapanje izmedju stranaka dokumenta i profila korisnika.",
    },
    "no_party_names": {
        "de": "Keine Parteiennamen aus dem Vertrag extrahiert.",
        "en": "No party names were extracted from the contract.",
        "zh": "未从合同中提取到当事人姓名。",
        "fr": "Aucun nom de partie n'a ete extrait du contrat.",
        "ru": "Имена сторон не были извлечены из договора.",
        "hu": "A szerzodesobol nem sikerult felek nevet kinyerni.",
        "pl": "Nie wyodrebniono nazw stron z umowy.",
        "tr": "Sozlesmeden taraf isimleri cikarilamadi.",
        "bs": "Imena stranaka nisu izvucena iz ugovora.",
    },
    "manual_unknown": {
        "de": "Benutzer hat die Vertragsseite explizit als unbekannt markiert.",
        "en": "User explicitly marked the contract side as unknown.",
        "zh": "用户明确将合同方标记为未知。",
        "fr": "L'utilisateur a explicitement marque le cote du contrat comme inconnu.",
        "ru": "Пользователь явно отметил сторону договора как неизвестную.",
        "hu": "A felhasznalo kifejezetten ismeretlennek jelolte a szerzodesi oldalt.",
        "pl": "Uzytkownik jawnie oznaczyl strone umowy jako nieznana.",
        "tr": "Kullanici sozlesme tarafini acikca bilinmiyor olarak isaretledi.",
        "bs": "Korisnik je izricito oznacio ugovornu stranu kao nepoznatu.",
    },
    "user_in_text_match": {
        "de": "Benutzer {label} '{identifier}' im Vertrags-/Dokumenttext gefunden.",
        "en": "Matched user {label} '{identifier}' in the contract/document text.",
        "zh": "在合同/文档文本中匹配到用户{label} '{identifier}'。",
        "fr": "Utilisateur {label} '{identifier}' trouve dans le texte du contrat/document.",
        "ru": "Пользователь {label} '{identifier}' найден в тексте договора/документа.",
        "hu": "A felhasznalo {label} '{identifier}' megtalalhato a szerzodes/dokumentum szovegeben.",
        "pl": "Uzytkownik {label} '{identifier}' znaleziony w tekscie umowy/dokumentu.",
        "tr": "Kullanici {label} '{identifier}' sozlesme/belge metninde bulundu.",
        "bs": "Korisnik {label} '{identifier}' pronadjen u tekstu ugovora/dokumenta.",
    },
    "bank_statement_mixed": {
        "de": "Kontoauszüge können sowohl Eingangs- als auch Ausgangsbuchungen enthalten, daher bleibt die Dokumentrichtung nur informativ.",
        "en": "Bank statements can contain both inflow and outflow entries, so the document-level direction remains informational only.",
        "zh": "银行对账单可以包含收入和支出条目，因此文档级方向仅供参考。",
        "fr": "Les releves bancaires peuvent contenir des entrees et des sorties, la direction au niveau du document reste donc informative uniquement.",
        "ru": "Банковские выписки могут содержать как входящие, так и исходящие записи, поэтому направление на уровне документа остаётся только информационным.",
        "hu": "A bankszamlakivonatok bejovo es kimeno teteleket is tartalmazhatnak, ezert a dokumentumszintu irany csak tajekeztato jelleget.",
        "pl": "Wyciagi bankowe moga zawierac zarowno wplywy, jak i wyplaty, dlatego kierunek na poziomie dokumentu pozostaje wylacznie informacyjny.",
        "tr": "Banka ekstreler hem giris hem de cikis kayitlarini icerebilir, bu nedenle belge duzeyindeki yon yalnizca bilgilendirme amaclidir.",
        "bs": "Bankarski izvodi mogu sadrzavati i ulazne i izlazne stavke, pa smjer na nivou dokumenta ostaje samo informativan.",
    },
    "manual_direction_selected": {
        "de": "Benutzer hat die Transaktionsrichtung in der Überprüfung explizit ausgewählt.",
        "en": "User explicitly selected the transaction direction in review.",
        "zh": "用户在审核中明确选择了交易方向。",
        "fr": "L'utilisateur a explicitement selectionne la direction de la transaction lors de la verification.",
        "ru": "Пользователь явно выбрал направление транзакции при проверке.",
        "hu": "A felhasznalo kifejezetten kivalasztotta a tranzakcio iranyet az ellenorzesnel.",
        "pl": "Uzytkownik jawnie wybral kierunek transakcji podczas przegladu.",
        "tr": "Kullanici inceleme sirasinda islem yonunu acikca secti.",
        "bs": "Korisnik je izricito odabrao smjer transakcije prilikom pregleda.",
    },
    "issuer_side_stronger": {
        "de": "Die Aussteller-Zuordnung war wesentlich stärker als der gegenteilige Texthinweis, daher folgt die Richtung der Aussteller-Zuordnung.",
        "en": "Issuer-side party matching was materially stronger than the opposing text hint, so direction follows the issuer-side match.",
        "zh": "发行方匹配明显强于对方文本提示，因此方向遵循发行方匹配。",
        "fr": "La correspondance cote emetteur etait sensiblement plus forte que l'indice textuel oppose, la direction suit donc la correspondance cote emetteur.",
        "ru": "Сопоставление на стороне эмитента было существенно сильнее, чем противоположная текстовая подсказка, поэтому направление следует за сопоставлением на стороне эмитента.",
        "hu": "A kiallitoi oldali egyezes lenyegesen erosebb volt az ellentetes szovegutalasnal, ezert az irany a kiallitoi oldali egyezest koveti.",
        "pl": "Dopasowanie po stronie wystawcy bylo istotnie silniejsze niz przeciwna wskazowka tekstowa, dlatego kierunek podaza za dopasowaniem po stronie wystawcy.",
        "tr": "Duzenleme tarafi eslesmesi karsi metin ipucundan onemli olcude guclu oldugu icin yon duzenleme tarafi eslemesini takip ediyor.",
        "bs": "Poklapanje na strani izdavaca bilo je znacajno jace od suprotnog tekstualnog nagovjestaja, pa smjer prati poklapanje na strani izdavaca.",
    },
    "recipient_side_stronger": {
        "de": "Die Empfänger-Zuordnung war wesentlich stärker als der gegenteilige Texthinweis, daher folgt die Richtung der Empfänger-Zuordnung.",
        "en": "Recipient-side party matching was materially stronger than the opposing text hint, so direction follows the recipient-side match.",
        "zh": "接收方匹配明显强于对方文本提示，因此方向遵循接收方匹配。",
        "fr": "La correspondance cote destinataire etait sensiblement plus forte que l'indice textuel oppose, la direction suit donc la correspondance cote destinataire.",
        "ru": "Сопоставление на стороне получателя было существенно сильнее, чем противоположная текстовая подсказка, поэтому направление следует за сопоставлением на стороне получателя.",
        "hu": "A kedvezmenyezetti oldali egyezes lenyegesen erosebb volt az ellentetes szovegutalasnal, ezert az irany a kedvezmenyezetti oldali egyezest koveti.",
        "pl": "Dopasowanie po stronie odbiorcy bylo istotnie silniejsze niz przeciwna wskazowka tekstowa, dlatego kierunek podaza za dopasowaniem po stronie odbiorcy.",
        "tr": "Alici tarafi eslesmesi karsi metin ipucundan onemli olcude guclu oldugu icin yon alici tarafi eslemesini takip ediyor.",
        "bs": "Poklapanje na strani primaoca bilo je znacajno jace od suprotnog tekstualnog nagovjestaja, pa smjer prati poklapanje na strani primaoca.",
    },
    "receipt_merchant_default": {
        "de": "Beleggegenpartei '{party}' scheint der Händler zu sein, daher wird das Dokument standardmäßig als Kaufseite behandelt.",
        "en": "Receipt counterparty '{party}' appears to be the merchant, so the document is treated as purchase-side by default.",
        "zh": "收据对方 '{party}' 似乎是商家，因此该文档默认被视为购买方。",
        "fr": "La contrepartie du recu '{party}' semble etre le commercant, le document est donc traite comme un achat par defaut.",
        "ru": "Контрагент чека '{party}' похож на торговца, поэтому документ по умолчанию рассматривается как сторона покупки.",
        "hu": "A nyugta ugyfelel '{party}' kereskedonek tunik, ezert a dokumentum alapertelmezetten vasarlasi oldalnak minositett.",
        "pl": "Kontrahent paragonu '{party}' wydaje sie byc sprzedawca, dlatego dokument jest domyslnie traktowany jako strona zakupu.",
        "tr": "Fis karsi tarafi '{party}' satici gibi gorunuyor, bu nedenle belge varsayilan olarak satin alma tarafi olarak isleniyor.",
        "bs": "Suprotna strana racuna '{party}' izgleda kao trgovac, pa se dokument tretira kao strana kupovine prema zadanim postavkama.",
    },
    "both_direction_matched": {
        "de": "Sowohl Aussteller- als auch Empfänger-Signale stimmen mit dem Benutzerprofil überein, daher bleibt die Dokumentrichtung mehrdeutig.",
        "en": "Matched both issuer-side and recipient-side signals to the user profile, so the document direction remains ambiguous.",
        "zh": "发行方和接收方信号均与用户资料匹配，因此文档方向仍然模糊。",
        "fr": "Les signaux cote emetteur et cote destinataire correspondent tous deux au profil utilisateur, la direction du document reste donc ambigue.",
        "ru": "Сигналы как на стороне эмитента, так и на стороне получателя совпали с профилем пользователя, поэтому направление документа остаётся неоднозначным.",
        "hu": "Mind a kiallitoi, mind a kedvezmenyezetti oldali jelek megegyeznek a felhasznaloi profillal, ezert a dokumentum iranya ketseges marad.",
        "pl": "Sygnaly zarowno po stronie wystawcy, jak i po stronie odbiorcy pasuja do profilu uzytkownika, wiec kierunek dokumentu pozostaje niejednoznaczny.",
        "tr": "Hem duzenleyici tarafi hem de alici tarafi sinyalleri kullanici profiline eslesti, bu nedenle belge yonu belirsiz kaliyor.",
        "bs": "I signali na strani izdavaca i na strani primaoca se podudaraju sa profilom korisnika, pa smjer dokumenta ostaje nejasan.",
    },
    "no_reliable_direction_match": {
        "de": "Keine zuverlässige Aussteller-/Empfänger-Zuordnung zwischen den Dokumentparteien und dem Benutzerprofil gefunden.",
        "en": "No reliable issuer/recipient match was found between the document parties and the user profile.",
        "zh": "在文档当事人与用户资料之间未找到可靠的发行方/接收方匹配。",
        "fr": "Aucune correspondance fiable emetteur/destinataire n'a ete trouvee entre les parties du document et le profil utilisateur.",
        "ru": "Надёжного соответствия эмитент/получатель между сторонами документа и профилем пользователя не найдено.",
        "hu": "Nem talalhato megbizhato kiallito/kedvezmenyezett egyezes a dokumentum felei es a felhasznaloi profil kozott.",
        "pl": "Nie znaleziono niezawodnego dopasowania wystawca/odbiorca miedzy stronami dokumentu a profilem uzytkownika.",
        "tr": "Belge taraflari ile kullanici profili arasinda guvenilir bir duzenleyici/alici eslemesi bulunamadi.",
        "bs": "Nije pronadjeno pouzdano poklapanje izdavac/primalac izmedju stranaka dokumenta i profila korisnika.",
    },
    "manual_direction_unknown": {
        "de": "Benutzer hat die Transaktionsrichtung explizit als unbekannt markiert.",
        "en": "User explicitly marked the transaction direction as unknown.",
        "zh": "用户明确将交易方向标记为未知。",
        "fr": "L'utilisateur a explicitement marque la direction de la transaction comme inconnue.",
        "ru": "Пользователь явно отметил направление транзакции как неизвестное.",
        "hu": "A felhasznalo kifejezetten ismeretlennek jelolte a tranzakcio iranyet.",
        "pl": "Uzytkownik jawnie oznaczyl kierunek transakcji jako nieznany.",
        "tr": "Kullanici islem yonunu acikca bilinmiyor olarak isaretledi.",
        "bs": "Korisnik je izricito oznacio smjer transakcije kao nepoznat.",
    },
    "no_commercial_party_data": {
        "de": "Keine zuverlässigen Handelspartnerdaten aus dem Dokument extrahiert.",
        "en": "No reliable commercial-party data was extracted from the document.",
        "zh": "未从文档中提取到可靠的商业方数据。",
        "fr": "Aucune donnee fiable de partie commerciale n'a ete extraite du document.",
        "ru": "Надёжные данные о коммерческой стороне не были извлечены из документа.",
        "hu": "Nem sikerult megbizhato kereskedelmi felre vonatkozo adatot kinyerni a dokumentumbol.",
        "pl": "Nie wyodrebniono niezawodnych danych strony handlowej z dokumentu.",
        "tr": "Belgeden guvenilir ticari taraf verisi cikarilamadi.",
        "bs": "Pouzdani podaci o komercijalnoj strani nisu izvuceni iz dokumenta.",
    },
    "user_near_issuer_wording": {
        "de": "Benutzer wurde in der Nähe von Aussteller-Formulierung im Dokumenttext erkannt.",
        "en": "Detected the user near issuer-side wording in the document text.",
        "zh": "在文档文本中检测到用户位于发行方措辞附近。",
        "fr": "Utilisateur detecte pres du libelle cote emetteur dans le texte du document.",
        "ru": "Обнаружен пользователь рядом с формулировкой на стороне эмитента в тексте документа.",
        "hu": "A felhasznalo a dokumentum szovegeben a kiallitoi oldali megfogalmazas kozeleben talalhato.",
        "pl": "Wykryto uzytkownika w poblizu sformulowania po stronie wystawcy w tekscie dokumentu.",
        "tr": "Belge metninde duzenleyici tarafli ifadenin yakininda kullanici tespit edildi.",
        "bs": "Korisnik detektovan u blizini formulacije na strani izdavaca u tekstu dokumenta.",
    },
    "user_near_recipient_wording": {
        "de": "Benutzer wurde in der Nähe von Empfänger-Formulierung im Dokumenttext erkannt.",
        "en": "Detected the user near recipient-side wording in the document text.",
        "zh": "在文档文本中检测到用户位于接收方措辞附近。",
        "fr": "Utilisateur detecte pres du libelle cote destinataire dans le texte du document.",
        "ru": "Обнаружен пользователь рядом с формулировкой на стороне получателя в тексте документа.",
        "hu": "A felhasznalo a dokumentum szovegeben a kedvezmenyezetti oldali megfogalmazas kozeleben talalhato.",
        "pl": "Wykryto uzytkownika w poblizu sformulowania po stronie odbiorcy w tekscie dokumentu.",
        "tr": "Belge metninde alici tarafli ifadenin yakininda kullanici tespit edildi.",
        "bs": "Korisnik detektovan u blizini formulacije na strani primaoca u tekstu dokumenta.",
    },
    "credit_note_detected": {
        "de": "Gutschrift-/Storno-Formulierung im Geschäftsdokument erkannt.",
        "en": "Detected credit-note wording such as Gutschrift/Storno in the commercial document.",
        "zh": "在商业文档中检测到贷方通知/冲销措辞。",
        "fr": "Libelle d'avoir/annulation detecte dans le document commercial.",
        "ru": "Обнаружена формулировка кредитовой ноты/сторно в коммерческом документе.",
        "hu": "Jovairasi/sztorno megfogalmazas eszlelve a kereskedelmi dokumentumban.",
        "pl": "Wykryto sformulowanie noty kredytowej/storna w dokumencie handlowym.",
        "tr": "Ticari belgede alacak dekont/iptal ifadesi tespit edildi.",
        "bs": "Otkrivena formulacija knjiznog odobrenja/storna u komercijalnom dokumentu.",
    },
    "proforma_detected": {
        "de": "Proforma-/Angebotsformulierung im Geschäftsdokument erkannt.",
        "en": "Detected proforma/quotation wording in the commercial document.",
        "zh": "在商业文档中检测到形式发票/报价措辞。",
        "fr": "Libelle proforma/devis detecte dans le document commercial.",
        "ru": "Обнаружена формулировка проформы/предложения в коммерческом документе.",
        "hu": "Proforma/ajanlat megfogalmazas eszlelve a kereskedelmi dokumentumban.",
        "pl": "Wykryto sformulowanie pro forma/oferty w dokumencie handlowym.",
        "tr": "Ticari belgede proforma/teklif ifadesi tespit edildi.",
        "bs": "Otkrivena formulacija proforme/ponude u komercijalnom dokumentu.",
    },
    "delivery_note_detected": {
        "de": "Lieferschein-Formulierung im Geschäftsdokument erkannt.",
        "en": "Detected delivery-note wording in the commercial document.",
        "zh": "在商业文档中检测到送货单措辞。",
        "fr": "Libelle de bon de livraison detecte dans le document commercial.",
        "ru": "Обнаружена формулировка накладной в коммерческом документе.",
        "hu": "Szallitolevel-megfogalmazas eszlelve a kereskedelmi dokumentumban.",
        "pl": "Wykryto sformulowanie listu przewozowego w dokumencie handlowym.",
        "tr": "Ticari belgede irsaliye ifadesi tespit edildi.",
        "bs": "Otkrivena formulacija otpremnice u komercijalnom dokumentu.",
    },
    "receipt_layout": {
        "de": "Dokumenttyp und extrahiertes Layout deuten auf einen Kassenbon hin.",
        "en": "Document type and extracted layout indicate a point-of-sale receipt.",
        "zh": "文档类型和提取的布局表明这是销售点收据。",
        "fr": "Le type de document et la mise en page extraite indiquent un ticket de caisse.",
        "ru": "Тип документа и извлечённая компоновка указывают на кассовый чек.",
        "hu": "A dokumentum tipusa es a kinyert elrendezes penztari nyugtat jelez.",
        "pl": "Typ dokumentu i wyodrebniony uklad wskazuja na paragon kasowy.",
        "tr": "Belge turu ve cikarilan duzeni bir satis fisi oldugunu gosteriyor.",
        "bs": "Tip dokumenta i izdvojeni raspored ukazuju na blagajnicki racun.",
    },
    "invoice_layout": {
        "de": "Dokumenttyp und extrahiertes Layout deuten auf eine Standardrechnung hin.",
        "en": "Document type and extracted layout indicate a standard invoice.",
        "zh": "文档类型和提取的布局表明这是标准发票。",
        "fr": "Le type de document et la mise en page extraite indiquent une facture standard.",
        "ru": "Тип документа и извлечённая компоновка указывают на стандартный счёт-фактуру.",
        "hu": "A dokumentum tipusa es a kinyert elrendezes standard szamlat jelez.",
        "pl": "Typ dokumentu i wyodrebniony uklad wskazuja na standardowa fakture.",
        "tr": "Belge turu ve cikarilan duzeni standart bir fatura oldugunu gosteriyor.",
        "bs": "Tip dokumenta i izdvojeni raspored ukazuju na standardnu fakturu.",
    },
}


class ContractRoleService:
    """Infer the user's side in sensitive documents."""

    def __init__(self, mode: str | None = None, language: str | None = None):
        self.mode = mode or get_sensitive_document_mode()
        self._language = language or "en"

    def _evidence_msg(self, key: str, **kwargs: str) -> str:
        """Return a localized evidence message for the given key."""
        templates = _EVIDENCE_MESSAGES.get(key)
        if not templates:
            return key
        lang = self._language or "en"
        template = templates.get(lang) or templates.get("en", key)
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return templates.get("en", key).format(**kwargs)

    def resolve_rental_contract_role(
        self,
        user: SensitiveUserContext,
        ocr_data: dict | None,
        *,
        raw_text: str | None = None,
    ) -> ContractRoleResolution:
        ocr_data = ocr_data or {}
        return self._resolve_role(
            user=user,
            role_family="rental",
            ocr_data=ocr_data,
            raw_text=raw_text,
            valid_roles=RENTAL_ROLES,
            positive_role="landlord",
            negative_role="tenant",
            positive_party=ocr_data.get("landlord_name"),
            negative_party=ocr_data.get("tenant_name"),
            context_positive=bool((ocr_data or {}).get("_upload_context", {}).get("property_id")),
            positive_keywords=("vermieter", "landlord"),
            negative_keywords=("mieter", "tenant"),
        )

    def resolve_purchase_contract_role(
        self,
        user: SensitiveUserContext,
        ocr_data: dict | None,
        contract_kind: str | None = None,
        *,
        raw_text: str | None = None,
    ) -> ContractRoleResolution:
        ocr_data = ocr_data or {}
        context_positive = bool(
            ocr_data.get("_upload_context", {}).get("property_id")
            or ocr_data.get("existing_property_id")
        )
        resolution = self._resolve_role(
            user=user,
            role_family="purchase",
            ocr_data=ocr_data,
            raw_text=raw_text,
            valid_roles=PURCHASE_ROLES,
            positive_role="buyer",
            negative_role="seller",
            positive_party=ocr_data.get("buyer_name"),
            negative_party=ocr_data.get("seller_name"),
            context_positive=context_positive,
            positive_keywords=("kaeufer", "käufer", "buyer", "uebernehmer", "übernehmer"),
            negative_keywords=("verkaeufer", "verkäufer", "seller", "uebergeber", "übergeber"),
        )
        if contract_kind:
            resolution.evidence.append(f"purchase_contract_kind={contract_kind}")
        return resolution

    def resolve_loan_contract_role(
        self,
        user: SensitiveUserContext,
        ocr_data: dict | None,
        *,
        raw_text: str | None = None,
    ) -> ContractRoleResolution:
        ocr_data = ocr_data or {}
        return self._resolve_role(
            user=user,
            role_family="loan",
            ocr_data=ocr_data,
            raw_text=raw_text,
            valid_roles=LOAN_ROLES,
            positive_role="borrower",
            negative_role="lender",
            positive_party=self._first_non_empty(
                ocr_data.get("borrower_name"),
                ocr_data.get("kreditnehmer"),
                ocr_data.get("darlehensnehmer"),
                ocr_data.get("debtor_name"),
            ),
            negative_party=self._first_non_empty(
                ocr_data.get("lender_name"),
                ocr_data.get("bank_name"),
                ocr_data.get("darlehensgeber"),
                ocr_data.get("kreditgeber"),
            ),
            context_positive=bool(
                (ocr_data.get("_upload_context") or {}).get("property_id")
                or ocr_data.get("matched_property_id")
            ),
            positive_keywords=("kreditnehmer", "darlehensnehmer", "borrower", "schuldner"),
            negative_keywords=("darlehensgeber", "kreditgeber", "lender", "bank"),
            negative_maps_to_unknown=True,
        )

    def resolve_insurance_role(
        self,
        user: SensitiveUserContext,
        ocr_data: dict | None,
        *,
        raw_text: str | None = None,
    ) -> ContractRoleResolution:
        ocr_data = ocr_data or {}
        return self._resolve_role(
            user=user,
            role_family="insurance",
            ocr_data=ocr_data,
            raw_text=raw_text,
            valid_roles=INSURANCE_ROLES,
            positive_role="policy_holder",
            negative_role="provider",
            positive_party=self._first_non_empty(
                ocr_data.get("policy_holder_name"),
                ocr_data.get("versicherungsnehmer"),
                ocr_data.get("insured_party"),
            ),
            negative_party=self._first_non_empty(
                ocr_data.get("insurer_name"),
                ocr_data.get("versicherer"),
                ocr_data.get("company_name"),
            ),
            context_positive=bool(
                (ocr_data.get("_upload_context") or {}).get("property_id")
                or ocr_data.get("linked_asset_id")
                or ocr_data.get("linked_property_id")
            ),
            positive_keywords=("versicherungsnehmer", "policy holder", "insured"),
            negative_keywords=("versicherer", "insurer", "provider", "versicherung"),
            negative_maps_to_unknown=True,
        )

    def resolve_transaction_direction(
        self,
        user: SensitiveUserContext,
        document_type: DocumentType | str,
        ocr_data: dict | None,
        *,
        raw_text: str | None = None,
    ) -> TransactionDirectionResolution:
        ocr_data = ocr_data or {}
        doc_type = (
            document_type.value
            if isinstance(document_type, DocumentType)
            else str(document_type or "").strip().lower()
        )

        semantics, is_reversal, semantic_evidence = self._resolve_commercial_semantics(
            doc_type,
            ocr_data,
            raw_text=raw_text,
        )

        if doc_type == DocumentType.BANK_STATEMENT.value:
            return TransactionDirectionResolution(
                candidate="unknown",
                confidence=0.2,
                source="statement_mixed_flow",
                evidence=[
                    self._evidence_msg("bank_statement_mixed")
                ],
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
                gate_enabled=False,
            )

        manual_direction = self._normalize_direction(
            ocr_data.get("document_transaction_direction")
            or ocr_data.get("transaction_direction")
        )
        if manual_direction and manual_direction != "unknown":
            return TransactionDirectionResolution(
                candidate=manual_direction,
                confidence=1.0,
                source="manual_override",
                evidence=[self._evidence_msg("manual_direction_selected")],
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        issuer_side = self._first_non_empty(
            ocr_data.get("issuer_name"),
            ocr_data.get("supplier"),
            ocr_data.get("merchant"),
            ocr_data.get("vendor_name"),
            ocr_data.get("company_name"),
            ocr_data.get("seller_name"),
        )
        recipient_side = self._first_non_empty(
            ocr_data.get("recipient_name"),
            ocr_data.get("customer_name"),
            ocr_data.get("invoice_to"),
            ocr_data.get("billed_to"),
            ocr_data.get("leistungsempfaenger"),
            ocr_data.get("buyer_name"),
        )

        issuer_match = self._match_user_to_party(user, issuer_side)
        recipient_match = self._match_user_to_party(user, recipient_side)
        issuer_text_match = self._match_user_in_text_near_keywords(
            user,
            raw_text,
            ("rechnungssteller", "issuer", "supplier", "ausgestellt von", "vendor"),
            source="text_direction_hint",
            evidence_prefix=self._evidence_msg("user_near_issuer_wording"),
        )
        recipient_text_match = self._match_user_in_text_near_keywords(
            user,
            raw_text,
            ("rechnung an", "invoice to", "customer", "recipient", "leistungsempfaenger", "bill to"),
            source="text_direction_hint",
            evidence_prefix=self._evidence_msg("user_near_recipient_wording"),
        )

        best_issuer = self._pick_best_match(issuer_match, issuer_text_match)
        best_recipient = self._pick_best_match(recipient_match, recipient_text_match)
        preferred_side = self._prefer_direction_side(best_issuer, best_recipient)

        if preferred_side == "issuer" and best_issuer:
            evidence = self._merge_evidence(
                best_issuer["evidence"],
                [
                    self._evidence_msg("issuer_side_stronger")
                ],
            )
            return TransactionDirectionResolution(
                candidate="income",
                confidence=best_issuer["confidence"],
                source=best_issuer["source"],
                evidence=self._merge_evidence(evidence, semantic_evidence),
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        if preferred_side == "recipient" and best_recipient:
            evidence = self._merge_evidence(
                best_recipient["evidence"],
                [
                    self._evidence_msg("recipient_side_stronger")
                ],
            )
            return TransactionDirectionResolution(
                candidate="expense",
                confidence=best_recipient["confidence"],
                source=best_recipient["source"],
                evidence=self._merge_evidence(evidence, semantic_evidence),
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        if best_issuer and not best_recipient:
            return TransactionDirectionResolution(
                candidate="income",
                confidence=best_issuer["confidence"],
                source=best_issuer["source"],
                evidence=self._merge_evidence(best_issuer["evidence"], semantic_evidence),
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        if best_recipient and not best_issuer:
            return TransactionDirectionResolution(
                candidate="expense",
                confidence=best_recipient["confidence"],
                source=best_recipient["source"],
                evidence=self._merge_evidence(best_recipient["evidence"], semantic_evidence),
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        if doc_type == DocumentType.RECEIPT.value and issuer_side and not best_issuer:
            return TransactionDirectionResolution(
                candidate="expense",
                confidence=0.68,
                source="merchant_counterparty",
                evidence=self._merge_evidence(
                    [self._evidence_msg("receipt_merchant_default", party=issuer_side)],
                    semantic_evidence,
                ),
                semantics=semantics,
                is_reversal=is_reversal,
                mode=self.mode,
            )

        evidence: list[str] = list(semantic_evidence)
        if best_issuer and best_recipient:
            evidence.insert(
                0,
                self._evidence_msg("both_direction_matched"),
            )
        elif issuer_side or recipient_side:
            evidence.insert(
                0,
                self._evidence_msg("no_reliable_direction_match"),
            )
        elif manual_direction == "unknown":
            evidence.insert(0, self._evidence_msg("manual_direction_unknown"))
        else:
            evidence.insert(0, self._evidence_msg("no_commercial_party_data"))

        return TransactionDirectionResolution(
            candidate="unknown",
            confidence=0.3,
            source="unknown",
            evidence=evidence,
            semantics=semantics,
            is_reversal=is_reversal,
            mode=self.mode,
        )

    def _resolve_role(
        self,
        *,
        user: SensitiveUserContext,
        role_family: str,
        ocr_data: dict,
        raw_text: str | None,
        valid_roles: set[str],
        positive_role: str,
        negative_role: str,
        positive_party: str | None,
        negative_party: str | None,
        context_positive: bool,
        positive_keywords: tuple[str, ...],
        negative_keywords: tuple[str, ...],
        negative_maps_to_unknown: bool = False,
    ) -> ContractRoleResolution:
        manual_value = self._normalize_role(ocr_data.get("user_contract_role"), valid_roles)
        if manual_value and manual_value != "unknown":
            return ContractRoleResolution(
                role_family=role_family,
                candidate=manual_value,
                confidence=1.0,
                source="manual_override",
                evidence=[self._evidence_msg("manual_role_selected", role=manual_value)],
                auto_action_role=positive_role,
                mode=self.mode,
            )

        if context_positive:
            return ContractRoleResolution(
                role_family=role_family,
                candidate=positive_role,
                confidence=0.96,
                source="property_context",
                evidence=[self._evidence_msg("property_context")],
                auto_action_role=positive_role,
                mode=self.mode,
            )

        positive_match = self._pick_best_match(
            self._match_user_to_party(user, positive_party, source="party_name_match"),
            self._match_user_in_text_near_keywords(
                user,
                raw_text,
                positive_keywords,
                source="text_role_hint",
                evidence_prefix=self._evidence_msg("user_near_positive_wording", role=positive_role),
            ),
        )
        negative_match = self._pick_best_match(
            self._match_user_to_party(user, negative_party, source="party_name_match"),
            self._match_user_in_text_near_keywords(
                user,
                raw_text,
                negative_keywords,
                source="text_role_hint",
                evidence_prefix=self._evidence_msg("user_near_negative_wording", role=negative_role),
            ),
        )
        preferred_role_side = self._prefer_role_side(positive_match, negative_match)
        if preferred_role_side == "positive":
            negative_match = None
        elif preferred_role_side == "negative":
            positive_match = None
        positive_keywords_present = self._keywords_present(raw_text, positive_keywords)
        negative_keywords_present = self._keywords_present(raw_text, negative_keywords)

        if positive_match and not negative_match:
            return ContractRoleResolution(
                role_family=role_family,
                candidate=positive_role,
                confidence=positive_match["confidence"],
                source=positive_match["source"],
                evidence=list(positive_match["evidence"]),
                auto_action_role=positive_role,
                mode=self.mode,
            )

        if negative_match and not positive_match:
            if negative_maps_to_unknown:
                return ContractRoleResolution(
                    role_family=role_family,
                    candidate="unknown",
                    confidence=min(0.7, negative_match["confidence"]),
                    source=negative_match["source"],
                    evidence=[
                        *negative_match["evidence"],
                        self._evidence_msg("negative_side_kept_unknown", role=negative_role),
                    ],
                    auto_action_role=positive_role,
                    mode=self.mode,
                    normalized_from=negative_role,
                )

            return ContractRoleResolution(
                role_family=role_family,
                candidate=negative_role,
                confidence=negative_match["confidence"],
                source=negative_match["source"],
                evidence=list(negative_match["evidence"]),
                auto_action_role=positive_role,
                mode=self.mode,
            )

        if negative_maps_to_unknown and not positive_match and (negative_party or negative_keywords_present):
            evidence = []
            if negative_party:
                evidence.append(
                    self._evidence_msg("extracted_counterparty", role=negative_role, party=negative_party)
                )
            if negative_keywords_present:
                evidence.append(
                    self._evidence_msg("negative_side_wording_detected", role=negative_role)
                )
            evidence.append(
                self._evidence_msg("negative_side_kept_unknown", role=negative_role)
            )
            return ContractRoleResolution(
                role_family=role_family,
                candidate="unknown",
                confidence=0.48,
                source="document_counterparty" if negative_party else "text_role_hint",
                evidence=evidence,
                auto_action_role=positive_role,
                mode=self.mode,
                normalized_from=negative_role,
            )

        evidence: list[str] = []
        if positive_match and negative_match:
            evidence.append(
                self._evidence_msg("both_sides_matched")
            )
        elif positive_party or negative_party:
            evidence.append(
                self._evidence_msg("no_reliable_match")
            )
        else:
            evidence.append(self._evidence_msg("no_party_names"))

        if manual_value == "unknown":
            evidence.append(self._evidence_msg("manual_unknown"))

        return ContractRoleResolution(
            role_family=role_family,
            candidate="unknown",
            confidence=0.25,
            source="unknown",
            evidence=evidence,
            auto_action_role=positive_role,
            mode=self.mode,
        )

    def _resolve_commercial_semantics(
        self,
        document_type: str,
        ocr_data: dict,
        *,
        raw_text: str | None = None,
    ) -> tuple[str, bool, list[str]]:
        text_parts = [
            raw_text or "",
            str(ocr_data.get("description") or ""),
            str(ocr_data.get("product_summary") or ""),
            str(ocr_data.get("invoice_number") or ""),
            str(ocr_data.get("supplier") or ""),
            str(ocr_data.get("merchant") or ""),
        ]
        haystack = self._normalize_text(" ".join(part for part in text_parts if part))
        evidence: list[str] = []

        if any(keyword in haystack for keyword in ("gutschrift", "credit note", "storno", "stornorechnung", "refund note")):
            evidence.append(self._evidence_msg("credit_note_detected"))
            return "credit_note", True, evidence

        if any(keyword in haystack for keyword in ("proforma", "pro forma", "angebot", "quotation")):
            evidence.append(self._evidence_msg("proforma_detected"))
            return "proforma", False, evidence

        if any(keyword in haystack for keyword in ("lieferschein", "delivery note")):
            evidence.append(self._evidence_msg("delivery_note_detected"))
            return "delivery_note", False, evidence

        if document_type == DocumentType.RECEIPT.value:
            evidence.append(self._evidence_msg("receipt_layout"))
            return "receipt", False, evidence

        if document_type == DocumentType.INVOICE.value:
            evidence.append(self._evidence_msg("invoice_layout"))
            return "standard_invoice", False, evidence

        return "unknown", False, evidence

    @staticmethod
    def _normalize_role(raw_value: str | None, valid_roles: set[str]) -> str | None:
        if raw_value is None:
            return None
        normalized = str(raw_value).strip().lower()
        if not normalized:
            return None
        return normalized if normalized in valid_roles else "unknown"

    @staticmethod
    def _normalize_direction(raw_value: str | None) -> str | None:
        if raw_value is None:
            return None
        normalized = str(raw_value).strip().lower()
        if not normalized:
            return None
        return normalized if normalized in DIRECTION_VALUES else "unknown"

    def _match_user_to_party(
        self,
        user: SensitiveUserContext,
        party_name: str | None,
        *,
        source: str = "party_name_match",
    ) -> dict | None:
        normalized_party = self._normalize_text(party_name)
        if not normalized_party:
            return None

        identifiers = list(self._iter_user_identifiers(user))
        if not identifiers:
            return None

        best_match: dict | None = None
        for label, identifier in identifiers:
            normalized_identifier = self._normalize_text(identifier)
            if not normalized_identifier:
                continue

            if normalized_party == normalized_identifier:
                return {
                    "confidence": 0.94,
                    "source": source,
                    "evidence": [
                        self._evidence_msg("exact_party_match", party=party_name, label=label)
                    ],
                }

            if normalized_identifier in normalized_party or normalized_party in normalized_identifier:
                candidate = {
                    "confidence": 0.82,
                    "source": source,
                    "evidence": [
                        self._evidence_msg("partial_party_match", party=party_name, label=label)
                    ],
                }
                if best_match is None or candidate["confidence"] > best_match["confidence"]:
                    best_match = candidate

        return best_match

    def _match_user_in_text_near_keywords(
        self,
        user: SensitiveUserContext,
        raw_text: str | None,
        keywords: tuple[str, ...],
        *,
        source: str,
        evidence_prefix: str,
    ) -> dict | None:
        normalized_text = self._normalize_text(raw_text)
        if not normalized_text:
            return None

        normalized_keywords = [self._normalize_text(keyword) for keyword in keywords if keyword]
        if not any(keyword and keyword in normalized_text for keyword in normalized_keywords):
            return None

        for label, identifier in self._iter_user_identifiers(user):
            normalized_identifier = self._normalize_text(identifier)
            if not normalized_identifier:
                continue

            if normalized_identifier in normalized_text:
                return {
                    "confidence": 0.74,
                    "source": source,
                    "evidence": [
                        evidence_prefix,
                        self._evidence_msg("user_in_text_match", label=label, identifier=identifier),
                    ],
                }

        return None

    def _keywords_present(self, raw_text: str | None, keywords: tuple[str, ...]) -> bool:
        normalized_text = self._normalize_text(raw_text)
        if not normalized_text:
            return False
        return any(
            keyword and self._normalize_text(keyword) in normalized_text
            for keyword in keywords
        )

    @staticmethod
    def _pick_best_match(*matches: dict | None) -> dict | None:
        present = [match for match in matches if match]
        if not present:
            return None
        return max(present, key=lambda item: float(item.get("confidence", 0.0)))

    @staticmethod
    def _prefer_role_side(
        positive_match: dict | None,
        negative_match: dict | None,
    ) -> str | None:
        if not positive_match or not negative_match:
            return None

        positive_source = str(positive_match.get("source") or "")
        negative_source = str(negative_match.get("source") or "")
        positive_confidence = float(positive_match.get("confidence", 0.0))
        negative_confidence = float(negative_match.get("confidence", 0.0))

        positive_is_strong_party_match = positive_source == "party_name_match" and positive_confidence >= 0.8
        negative_is_strong_party_match = negative_source == "party_name_match" and negative_confidence >= 0.8
        positive_is_text_hint = positive_source.startswith("text_")
        negative_is_text_hint = negative_source.startswith("text_")

        if positive_is_strong_party_match and negative_is_text_hint and positive_confidence - negative_confidence >= 0.1:
            return "positive"
        if negative_is_strong_party_match and positive_is_text_hint and negative_confidence - positive_confidence >= 0.1:
            return "negative"

        if positive_confidence - negative_confidence >= 0.25:
            return "positive"
        if negative_confidence - positive_confidence >= 0.25:
            return "negative"
        return None

    @staticmethod
    def _prefer_direction_side(
        issuer_match: dict | None,
        recipient_match: dict | None,
    ) -> str | None:
        if not issuer_match or not recipient_match:
            return None

        issuer_source = str(issuer_match.get("source") or "")
        recipient_source = str(recipient_match.get("source") or "")
        issuer_confidence = float(issuer_match.get("confidence", 0.0))
        recipient_confidence = float(recipient_match.get("confidence", 0.0))

        issuer_is_strong_party_match = issuer_source == "party_name_match" and issuer_confidence >= 0.8
        recipient_is_strong_party_match = recipient_source == "party_name_match" and recipient_confidence >= 0.8
        issuer_is_text_hint = issuer_source.startswith("text_")
        recipient_is_text_hint = recipient_source.startswith("text_")

        if recipient_is_strong_party_match and issuer_is_text_hint and recipient_confidence - issuer_confidence >= 0.1:
            return "recipient"
        if issuer_is_strong_party_match and recipient_is_text_hint and issuer_confidence - recipient_confidence >= 0.1:
            return "issuer"

        if recipient_confidence - issuer_confidence >= 0.25:
            return "recipient"
        if issuer_confidence - recipient_confidence >= 0.25:
            return "issuer"
        return None

    @staticmethod
    def _merge_evidence(primary: list[str], secondary: list[str]) -> list[str]:
        merged: list[str] = []
        for item in [*(primary or []), *(secondary or [])]:
            if item and item not in merged:
                merged.append(item)
        return merged

    @staticmethod
    def _iter_user_identifiers(user: SensitiveUserContext) -> Iterable[tuple[str, str]]:
        if getattr(user, "full_name", None):
            yield ("full name", user.full_name)
        if getattr(user, "business_name", None):
            yield ("business name", user.business_name)
        if getattr(user, "name", None):
            yield ("name", user.name)

    @staticmethod
    def _first_non_empty(*values: str | None) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        if not value:
            return ""
        normalized = _normalize_umlauts(str(value).strip().lower())
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()
