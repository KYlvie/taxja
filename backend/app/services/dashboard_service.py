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
from app.models.transaction_line_item import LineItemPostingType
from app.models.document import Document, DocumentType
from app.models.user import User, UserType
from app.models.property import Property, PropertyStatus, PropertyType
from app.services.posting_line_utils import iter_posting_records, sum_postings, sum_postings_by_category


# ---------------------------------------------------------------------------
# Localized text tables for suggestions (de / en / zh)
# ---------------------------------------------------------------------------
_SUGGESTION_TEXTS: Dict[str, Dict[str, str]] = {
    "de": {
        "home_office_title": "Home-Office-Pauschale",
        "home_office_desc": (
            "Sie haben noch keine Home-Office-Ausgaben erfasst. "
            "Wenn Sie von zu Hause arbeiten, können Sie bis zu €300/Jahr absetzen. "
            "Laden Sie einen Beleg hoch (z.B. Internetrechnung, Büromaterial) "
            "oder erfassen Sie die Ausgabe manuell."
        ),
        "home_office_action": "Ausgabe erfassen",
        "pendler_title": "Pendlerpauschale",
        "pendler_desc": (
            "Keine Fahrtkosten erfasst. Wenn Ihr Arbeitsweg mindestens 2 km beträgt, "
            "steht Ihnen eine Pendlerpauschale zu. "
            "Erfassen Sie Ihre Fahrtkosten als Ausgabe mit Kategorie 'Pendlerpauschale'."
        ),
        "pendler_action": "Fahrtkosten erfassen",
        "insurance_title": "Versicherungsprämien",
        "insurance_desc": (
            "Keine Versicherungsausgaben erfasst. Wenn Sie private Versicherungen "
            "(z.B. Unfallversicherung, Lebensversicherung) bezahlen, können diese "
            "teilweise steuerlich absetzbar sein. Laden Sie Ihre Versicherungspolizze hoch."
        ),
        "insurance_action": "Versicherung erfassen",
        "review_title": "Nicht abzugsfähige Ausgaben prüfen",
        "review_desc": (
            "Sie haben {amount} an nicht abzugsfähigen Ausgaben. "
            "Einige davon könnten mit entsprechenden Belegen absetzbar sein. "
            "Prüfen Sie diese Ausgaben und laden Sie fehlende Belege hoch."
        ),
        "review_action": "Ausgaben prüfen",
        "ocr_title": "Erkennungsergebnisse prüfen",
        "ocr_desc": (
            "{count} Dokument(e) wurden nicht korrekt erkannt. "
            "Bitte überprüfen und korrigieren Sie die erkannten Daten manuell."
        ),
        "ocr_action": "Dokumente prüfen",
        "getting_started_title": "Erste Transaktion hinzufügen",
        "getting_started_desc": (
            "Laden Sie Belege, Rechnungen oder Lohnzettel hoch, um zu starten. "
            "Sie können auch manuell Einnahmen und Ausgaben erfassen."
        ),
        "getting_started_action": "Beleg hochladen",
    },
    "en": {
        "home_office_title": "Home Office Deduction",
        "home_office_desc": (
            "No home office expenses recorded yet. "
            "If you work from home, you may deduct up to €300/year. "
            "Upload a receipt (e.g. internet bill, office supplies) "
            "or add the expense manually."
        ),
        "home_office_action": "Add expense",
        "pendler_title": "Commuter Allowance (Pendlerpauschale)",
        "pendler_desc": (
            "No commuting expenses recorded. If your commute is at least 2 km, "
            "you may be eligible for a commuter allowance. "
            "Add your commuting costs as an expense under 'Commuting'."
        ),
        "pendler_action": "Add commuting costs",
        "insurance_title": "Insurance Premiums",
        "insurance_desc": (
            "No insurance expenses recorded. If you pay private insurance "
            "(e.g. accident, life insurance), these may be partially tax-deductible. "
            "Upload your insurance policy or add the expense."
        ),
        "insurance_action": "Add insurance",
        "review_title": "Review Non-Deductible Expenses",
        "review_desc": (
            "You have {amount} in non-deductible expenses. "
            "Some may qualify for deduction with proper documentation. "
            "Review these expenses and upload missing receipts."
        ),
        "review_action": "Review expenses",
        "ocr_title": "Review Recognition Results",
        "ocr_desc": (
            "{count} document(s) were not recognized correctly. "
            "Please review and correct the extracted data manually."
        ),
        "ocr_action": "Review documents",
        "getting_started_title": "Add Your First Transaction",
        "getting_started_desc": (
            "Upload receipts, invoices, or payslips to get started. "
            "You can also manually add income and expenses."
        ),
        "getting_started_action": "Upload receipt",
    },
    "zh": {
        "home_office_title": "居家办公扣除",
        "home_office_desc": (
            "您尚未记录居家办公费用。"
            "如果您在家工作，每年最多可扣除 €300。"
            "请上传相关凭证（如网费账单、办公用品发票）或手动添加支出。"
        ),
        "home_office_action": "记录支出",
        "pendler_title": "通勤补贴 (Pendlerpauschale)",
        "pendler_desc": (
            "未记录通勤费用。如果您的通勤距离至少 2 公里，"
            "可以申请通勤补贴。请在支出中添加通勤费用，类别选择「通勤」。"
        ),
        "pendler_action": "记录通勤费",
        "insurance_title": "保险费",
        "insurance_desc": (
            "未记录保险费用。如果您有私人保险（如意外险、人寿险），"
            "部分保费可以抵税。请上传保险单或手动添加保险支出。"
        ),
        "insurance_action": "记录保险费",
        "review_title": "检查不可扣除支出",
        "review_desc": (
            "您有 {amount} 的不可扣除支出。"
            "其中部分可能在上传凭证后可以扣除。请检查这些支出并补充凭证。"
        ),
        "review_action": "检查支出",
        "ocr_title": "检查文档识别结果",
        "ocr_desc": "{count} 份文档识别不准确，请手动检查并修正识别结果。",
        "ocr_action": "检查文档",
        "getting_started_title": "添加您的第一笔交易",
        "getting_started_desc": (
            "上传收据、发票或工资单即可开始。"
            "您也可以手动添加收入和支出。"
        ),
        "getting_started_action": "上传凭证",
    },
    "fr": {
        "home_office_title": "Déduction bureau à domicile",
        "home_office_desc": (
            "Aucune dépense de bureau à domicile enregistrée. "
            "Si vous travaillez depuis chez vous, vous pouvez déduire jusqu'à 300 €/an. "
            "Téléchargez un justificatif (ex. facture internet, fournitures de bureau) "
            "ou ajoutez la dépense manuellement."
        ),
        "home_office_action": "Ajouter une dépense",
        "pendler_title": "Indemnité de trajet (Pendlerpauschale)",
        "pendler_desc": (
            "Aucun frais de trajet enregistré. Si votre trajet domicile-travail fait au moins 2 km, "
            "vous pouvez bénéficier d'une indemnité de trajet. "
            "Ajoutez vos frais de déplacement dans la catégorie « Trajet »."
        ),
        "pendler_action": "Ajouter frais de trajet",
        "insurance_title": "Primes d'assurance",
        "insurance_desc": (
            "Aucune dépense d'assurance enregistrée. Si vous payez des assurances privées "
            "(ex. accident, vie), elles peuvent être partiellement déductibles. "
            "Téléchargez votre police d'assurance ou ajoutez la dépense."
        ),
        "insurance_action": "Ajouter une assurance",
        "review_title": "Vérifier les dépenses non déductibles",
        "review_desc": (
            "Vous avez {amount} de dépenses non déductibles. "
            "Certaines pourraient être déductibles avec les justificatifs appropriés. "
            "Vérifiez ces dépenses et téléchargez les justificatifs manquants."
        ),
        "review_action": "Vérifier les dépenses",
        "ocr_title": "Vérifier les résultats de reconnaissance",
        "ocr_desc": (
            "{count} document(s) n'ont pas été reconnus correctement. "
            "Veuillez vérifier et corriger les données extraites manuellement."
        ),
        "ocr_action": "Vérifier les documents",
        "getting_started_title": "Ajoutez votre première transaction",
        "getting_started_desc": (
            "Téléchargez des reçus, factures ou fiches de paie pour commencer. "
            "Vous pouvez aussi ajouter manuellement des revenus et dépenses."
        ),
        "getting_started_action": "Télécharger un reçu",
    },
    "ru": {
        "home_office_title": "Вычет за домашний офис",
        "home_office_desc": (
            "Расходы на домашний офис не записаны. "
            "Если вы работаете из дома, можно вычесть до 300 €/год. "
            "Загрузите чек (напр. счёт за интернет, канцтовары) "
            "или добавьте расход вручную."
        ),
        "home_office_action": "Добавить расход",
        "pendler_title": "Пособие на проезд (Pendlerpauschale)",
        "pendler_desc": (
            "Расходы на проезд не записаны. Если ваш путь на работу составляет не менее 2 км, "
            "вы можете получить пособие на проезд. "
            "Добавьте расходы на проезд в категории «Проезд»."
        ),
        "pendler_action": "Добавить расходы на проезд",
        "insurance_title": "Страховые взносы",
        "insurance_desc": (
            "Расходы на страхование не записаны. Если вы платите частную страховку "
            "(напр. от несчастных случаев, на жизнь), она может быть частично вычитаема. "
            "Загрузите страховой полис или добавьте расход."
        ),
        "insurance_action": "Добавить страховку",
        "review_title": "Проверьте невычитаемые расходы",
        "review_desc": (
            "У вас {amount} невычитаемых расходов. "
            "Некоторые могут быть вычтены при наличии документов. "
            "Проверьте эти расходы и загрузите недостающие чеки."
        ),
        "review_action": "Проверить расходы",
        "ocr_title": "Проверьте результаты распознавания",
        "ocr_desc": (
            "{count} документ(ов) не были распознаны правильно. "
            "Пожалуйста, проверьте и исправьте данные вручную."
        ),
        "ocr_action": "Проверить документы",
        "getting_started_title": "Добавьте первую транзакцию",
        "getting_started_desc": (
            "Загрузите чеки, счета или зарплатные квитанции, чтобы начать. "
            "Вы также можете добавить доходы и расходы вручную."
        ),
        "getting_started_action": "Загрузить чек",
    },
    "hu": {
        "home_office_title": "Otthoni iroda levonás",
        "home_office_desc": (
            "Még nem rögzített otthoni irodai kiadást. "
            "Ha otthonról dolgozik, évente akár €300-t is levonhat. "
            "Töltsön fel egy bizonylatot (pl. internetszámla, irodaszer) "
            "vagy adja hozzá a kiadást manuálisan."
        ),
        "home_office_action": "Kiadás rögzítése",
        "pendler_title": "Ingázási támogatás (Pendlerpauschale)",
        "pendler_desc": (
            "Nincs rögzített ingázási költség. Ha az ingázási távolsága legalább 2 km, "
            "ingázási támogatásra jogosult. "
            "Adja hozzá ingázási költségeit az 'Ingázás' kategóriában."
        ),
        "pendler_action": "Ingázási költség rögzítése",
        "insurance_title": "Biztosítási díjak",
        "insurance_desc": (
            "Nincs rögzített biztosítási kiadás. Ha magánbiztosítást fizet "
            "(pl. baleset-, életbiztosítás), ezek részben adóból levonhatók. "
            "Töltse fel biztosítási kötvényét vagy adja hozzá a kiadást."
        ),
        "insurance_action": "Biztosítás rögzítése",
        "review_title": "Nem levonható kiadások ellenőrzése",
        "review_desc": (
            "Önnek {amount} nem levonható kiadása van. "
            "Ezek egy része megfelelő dokumentációval levonható lehet. "
            "Ellenőrizze ezeket a kiadásokat és töltse fel a hiányzó bizonylatokat."
        ),
        "review_action": "Kiadások ellenőrzése",
        "ocr_title": "Felismerési eredmények ellenőrzése",
        "ocr_desc": (
            "{count} dokumentum nem lett megfelelően felismerve. "
            "Kérjük, ellenőrizze és javítsa a kinyert adatokat manuálisan."
        ),
        "ocr_action": "Dokumentumok ellenőrzése",
        "getting_started_title": "Első tranzakció hozzáadása",
        "getting_started_desc": (
            "Töltsön fel nyugtákat, számlákat vagy bérjegyeket a kezdéshez. "
            "Manuálisan is hozzáadhat bevételeket és kiadásokat."
        ),
        "getting_started_action": "Bizonylat feltöltése",
    },
    "pl": {
        "home_office_title": "Odliczenie za biuro domowe",
        "home_office_desc": (
            "Nie zarejestrowano jeszcze wydatków na biuro domowe. "
            "Jeśli pracujesz z domu, możesz odliczyć do 300 €/rok. "
            "Prześlij paragon (np. rachunek za internet, artykuły biurowe) "
            "lub dodaj wydatek ręcznie."
        ),
        "home_office_action": "Dodaj wydatek",
        "pendler_title": "Dodatek dojazdowy (Pendlerpauschale)",
        "pendler_desc": (
            "Nie zarejestrowano kosztów dojazdu. Jeśli Twój dojazd wynosi co najmniej 2 km, "
            "możesz ubiegać się o dodatek dojazdowy. "
            "Dodaj koszty dojazdu w kategorii 'Dojazdy'."
        ),
        "pendler_action": "Dodaj koszty dojazdu",
        "insurance_title": "Składki ubezpieczeniowe",
        "insurance_desc": (
            "Nie zarejestrowano wydatków na ubezpieczenie. Jeśli opłacasz prywatne ubezpieczenie "
            "(np. od wypadków, na życie), mogą one być częściowo odliczane od podatku. "
            "Prześlij polisę ubezpieczeniową lub dodaj wydatek."
        ),
        "insurance_action": "Dodaj ubezpieczenie",
        "review_title": "Sprawdź wydatki niepodlegające odliczeniu",
        "review_desc": (
            "Masz {amount} wydatków niepodlegających odliczeniu. "
            "Niektóre mogą kwalifikować się do odliczenia przy odpowiedniej dokumentacji. "
            "Sprawdź te wydatki i prześlij brakujące paragony."
        ),
        "review_action": "Sprawdź wydatki",
        "ocr_title": "Sprawdź wyniki rozpoznawania",
        "ocr_desc": (
            "{count} dokument(ów) nie zostało prawidłowo rozpoznanych. "
            "Proszę sprawdzić i poprawić wyodrębnione dane ręcznie."
        ),
        "ocr_action": "Sprawdź dokumenty",
        "getting_started_title": "Dodaj pierwszą transakcję",
        "getting_started_desc": (
            "Prześlij paragony, faktury lub paski wynagrodzeń, aby rozpocząć. "
            "Możesz również ręcznie dodać przychody i wydatki."
        ),
        "getting_started_action": "Prześlij paragon",
    },
    "tr": {
        "home_office_title": "Ev ofisi indirimi",
        "home_office_desc": (
            "Henuz ev ofisi gideri kaydedilmedi. "
            "Evden calisiyorsaniz yilda 300 EUR'ya kadar indirim yapabilirsiniz. "
            "Bir makbuz yukleyin (ornegin internet faturasi, ofis malzemesi) "
            "veya gideri manuel olarak ekleyin."
        ),
        "home_office_action": "Gider ekle",
        "pendler_title": "Ise gidis-gelis odenegi (Pendlerpauschale)",
        "pendler_desc": (
            "Ise gidis-gelis gideri kaydedilmedi. Ise gidis mesafeniz en az 2 km ise "
            "ise gidis-gelis odenegine hak kazanabilirsiniz. "
            "Ulasim giderlerinizi 'Ise gidis-gelis' kategorisinde ekleyin."
        ),
        "pendler_action": "Ulasim gideri ekle",
        "insurance_title": "Sigorta primleri",
        "insurance_desc": (
            "Sigorta gideri kaydedilmedi. Ozel sigorta oduyorsaniz "
            "(ornegin kaza, hayat sigortasi), bunlar kismen vergi indirimi olabilir. "
            "Sigorta policenizi yukleyin veya gideri ekleyin."
        ),
        "insurance_action": "Sigorta ekle",
        "review_title": "Indirilemez giderleri inceleyin",
        "review_desc": (
            "{amount} tutarinda indirilemez gideriniz var. "
            "Bunlarin bir kismi uygun belgelerle indirilebilir olabilir. "
            "Bu giderleri inceleyin ve eksik makbuzlari yukleyin."
        ),
        "review_action": "Giderleri incele",
        "ocr_title": "Tanima sonuclarini inceleyin",
        "ocr_desc": (
            "{count} belge dogru taninamadi. "
            "Lutfen cikarilan verileri manuel olarak kontrol edin ve duzeltin."
        ),
        "ocr_action": "Belgeleri incele",
        "getting_started_title": "Ilk isleminizi ekleyin",
        "getting_started_desc": (
            "Baslamak icin makbuzlari, faturalari veya maas bordrolari yukleyin. "
            "Ayrica gelir ve giderleri manuel olarak da ekleyebilirsiniz."
        ),
        "getting_started_action": "Makbuz yukle",
    },
    "bs": {
        "home_office_title": "Odbitak za kucni ured",
        "home_office_desc": (
            "Jos nema evidentiranih troskova kucnog ureda. "
            "Ako radite od kuce, mozete odbiti do 300 EUR godisnje. "
            "Ucitajte racun (npr. internet racun, kancelarijski materijal) "
            "ili rucno dodajte trosak."
        ),
        "home_office_action": "Dodaj trosak",
        "pendler_title": "Naknada za putovanje na posao (Pendlerpauschale)",
        "pendler_desc": (
            "Nema evidentiranih troskova putovanja na posao. Ako je vasa udaljenost do posla najmanje 2 km, "
            "mozete ostvariti pravo na naknadu za putovanje. "
            "Dodajte troskove putovanja u kategoriji 'Putovanje na posao'."
        ),
        "pendler_action": "Dodaj troskove putovanja",
        "insurance_title": "Premije osiguranja",
        "insurance_desc": (
            "Nema evidentiranih troskova osiguranja. Ako placate privatno osiguranje "
            "(npr. od nezgode, zivotno osiguranje), ono moze biti djelomicno porezno odbitno. "
            "Ucitajte polisu osiguranja ili dodajte trosak."
        ),
        "insurance_action": "Dodaj osiguranje",
        "review_title": "Pregledajte neodbitne troskove",
        "review_desc": (
            "Imate {amount} neodbitnih troskova. "
            "Neki od njih mogu biti odbitni uz odgovarajucu dokumentaciju. "
            "Pregledajte ove troskove i ucitajte nedostajuce racune."
        ),
        "review_action": "Pregledaj troskove",
        "ocr_title": "Pregledajte rezultate prepoznavanja",
        "ocr_desc": (
            "{count} dokument(a) nije pravilno prepoznato. "
            "Molimo pregledajte i ispravite izdvojene podatke rucno."
        ),
        "ocr_action": "Pregledaj dokumente",
        "getting_started_title": "Dodajte prvu transakciju",
        "getting_started_desc": (
            "Ucitajte racune, fakture ili platne listic da biste poceli. "
            "Takoder mozete rucno dodati prihode i rashode."
        ),
        "getting_started_action": "Ucitaj racun",
    },
}

# ---------------------------------------------------------------------------
# Document completeness: required docs per user_type
# Each entry: (DocumentType, i18n_key, priority, needs_history)
#   needs_history=True → only show if user already has transactions (not a new user)
# ---------------------------------------------------------------------------
_REQUIRED_DOCS: Dict[str, List[tuple]] = {
    "employee": [
        (DocumentType.LOHNZETTEL, "missing_lohnzettel", "high", False),
    ],
    "self_employed": [
        (DocumentType.E1_FORM, "missing_e1", "high", True),
        (DocumentType.SVS_NOTICE, "missing_svs", "high", False),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
    "landlord": [
        (DocumentType.PURCHASE_CONTRACT, "missing_kaufvertrag", "high", False),
        (DocumentType.RENTAL_CONTRACT, "missing_mietvertrag", "high", False),
    ],
    "mixed": [
        (DocumentType.LOHNZETTEL, "missing_lohnzettel", "high", False),
        (DocumentType.E1_FORM, "missing_e1", "medium", True),
        (DocumentType.SVS_NOTICE, "missing_svs", "medium", False),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
    "gmbh": [
        (DocumentType.E1_FORM, "missing_e1", "high", True),
        (DocumentType.EINKOMMENSTEUERBESCHEID, "missing_bescheid", "low", True),
    ],
}

# Localized texts for missing-document suggestions
_DOC_COMPLETENESS_TEXTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "de": {
        "missing_lohnzettel": {
            "title": "Lohnzettel fehlt",
            "desc": "Bitte laden Sie Ihren Lohnzettel (L16) hoch, damit wir Ihre Lohneinkünfte korrekt berechnen können.",
            "action": "Lohnzettel hochladen",
        },
        "missing_bescheid": {
            "title": "Einkommensteuerbescheid fehlt",
            "desc": "Laden Sie Ihren letzten Einkommensteuerbescheid hoch, um Verlustvorträge und historische Daten zu erfassen.",
            "action": "Bescheid hochladen",
        },
        "missing_e1": {
            "title": "E1-Erklärung fehlt",
            "desc": "Bitte laden Sie Ihre letzte E1-Steuererklärung hoch, damit wir Ihre Einkommenssituation vollständig erfassen.",
            "action": "E1 hochladen",
        },
        "missing_svs": {
            "title": "SVS-Bescheid fehlt",
            "desc": "Laden Sie Ihren SVS-Beitragsbescheid hoch, um Sozialversicherungsbeiträge korrekt zu berücksichtigen.",
            "action": "SVS hochladen",
        },
        "missing_kaufvertrag": {
            "title": "Kaufvertrag fehlt",
            "desc": "Bitte laden Sie den Kaufvertrag Ihrer Immobilie hoch, um AfA und Anschaffungskosten zu berechnen.",
            "action": "Kaufvertrag hochladen",
        },
        "missing_mietvertrag": {
            "title": "Mietvertrag fehlt",
            "desc": "Laden Sie Ihren Mietvertrag hoch, damit wir Mieteinnahmen und Werbungskosten korrekt zuordnen können.",
            "action": "Mietvertrag hochladen",
        },
        "conflict_title": "Datenabweichung erkannt",
        "conflict_desc": (
            "Der Einkommensteuerbescheid weist {bescheid_amount} aus, "
            "aber Ihre erfassten Transaktionen ergeben {txn_amount}. "
            "Bitte prüfen Sie die Daten — der Bescheid hat Vorrang."
        ),
    },
    "en": {
        "missing_lohnzettel": {
            "title": "Wage Tax Certificate Missing",
            "desc": "Please upload your Lohnzettel (L16) so we can accurately calculate your employment income.",
            "action": "Upload Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Tax Assessment Missing",
            "desc": "Upload your latest Einkommensteuerbescheid to capture loss carryforwards and historical data.",
            "action": "Upload Bescheid",
        },
        "missing_e1": {
            "title": "E1 Tax Return Missing",
            "desc": "Please upload your last E1 tax return so we can fully capture your income situation.",
            "action": "Upload E1",
        },
        "missing_svs": {
            "title": "SVS Notice Missing",
            "desc": "Upload your SVS contribution notice to correctly account for social insurance contributions.",
            "action": "Upload SVS",
        },
        "missing_kaufvertrag": {
            "title": "Purchase Contract Missing",
            "desc": "Please upload your property purchase contract to calculate depreciation and acquisition costs.",
            "action": "Upload contract",
        },
        "missing_mietvertrag": {
            "title": "Rental Contract Missing",
            "desc": "Upload your rental contract so we can correctly allocate rental income and deductible expenses.",
            "action": "Upload contract",
        },
        "conflict_title": "Data Discrepancy Detected",
        "conflict_desc": (
            "The tax assessment shows {bescheid_amount}, "
            "but your recorded transactions total {txn_amount}. "
            "Please review — the Bescheid takes priority."
        ),
    },
    "zh": {
        "missing_lohnzettel": {
            "title": "缺少工资单 (Lohnzettel)",
            "desc": "请上传您的工资单 (L16)，以便我们准确计算您的工资收入。",
            "action": "上传工资单",
        },
        "missing_bescheid": {
            "title": "缺少所得税评估通知",
            "desc": "请上传您最近的所得税评估通知 (Einkommensteuerbescheid)，以获取亏损结转和历史数据。",
            "action": "上传评估通知",
        },
        "missing_e1": {
            "title": "缺少 E1 税务申报表",
            "desc": "请上传您上一年的 E1 税务申报表，以便我们完整掌握您的收入情况。",
            "action": "上传 E1",
        },
        "missing_svs": {
            "title": "缺少 SVS 社保通知",
            "desc": "请上传您的 SVS 缴费通知，以便正确计算社会保险费用。",
            "action": "上传 SVS",
        },
        "missing_kaufvertrag": {
            "title": "缺少购房合同",
            "desc": "请上传您的房产购买合同 (Kaufvertrag)，以便计算折旧和购置成本。",
            "action": "上传购房合同",
        },
        "missing_mietvertrag": {
            "title": "缺少租赁合同",
            "desc": "请上传您的租赁合同 (Mietvertrag)，以便正确分配租金收入和可扣除费用。",
            "action": "上传租赁合同",
        },
        "conflict_title": "检测到数据差异",
        "conflict_desc": (
            "所得税评估通知显示收入为 {bescheid_amount}，"
            "但您已录入的交易合计为 {txn_amount}。"
            "请核实数据 — 以评估通知 (Bescheid) 为准。"
        ),
    },
    "fr": {
        "missing_lohnzettel": {
            "title": "Fiche de paie manquante",
            "desc": "Veuillez télécharger votre Lohnzettel (L16) pour que nous puissions calculer correctement vos revenus d'emploi.",
            "action": "Télécharger le Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Avis d'imposition manquant",
            "desc": "Téléchargez votre dernier Einkommensteuerbescheid pour capturer les reports de pertes et les données historiques.",
            "action": "Télécharger l'avis",
        },
        "missing_e1": {
            "title": "Déclaration E1 manquante",
            "desc": "Veuillez télécharger votre dernière déclaration E1 pour que nous puissions saisir votre situation de revenus complète.",
            "action": "Télécharger E1",
        },
        "missing_svs": {
            "title": "Avis SVS manquant",
            "desc": "Téléchargez votre avis de cotisation SVS pour tenir compte correctement des cotisations sociales.",
            "action": "Télécharger SVS",
        },
        "missing_kaufvertrag": {
            "title": "Contrat d'achat manquant",
            "desc": "Veuillez télécharger le contrat d'achat de votre bien pour calculer l'amortissement et les coûts d'acquisition.",
            "action": "Télécharger le contrat",
        },
        "missing_mietvertrag": {
            "title": "Contrat de location manquant",
            "desc": "Téléchargez votre contrat de location pour que nous puissions attribuer correctement les revenus locatifs et les charges déductibles.",
            "action": "Télécharger le contrat",
        },
        "conflict_title": "Écart de données détecté",
        "conflict_desc": (
            "L'avis d'imposition indique {bescheid_amount}, "
            "mais vos transactions enregistrées totalisent {txn_amount}. "
            "Veuillez vérifier — l'avis d'imposition (Bescheid) fait foi."
        ),
    },
    "ru": {
        "missing_lohnzettel": {
            "title": "Отсутствует зарплатная ведомость",
            "desc": "Пожалуйста, загрузите ваш Lohnzettel (L16), чтобы мы могли точно рассчитать ваш доход от работы.",
            "action": "Загрузить Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Отсутствует налоговое уведомление",
            "desc": "Загрузите ваш последний Einkommensteuerbescheid для учёта переноса убытков и исторических данных.",
            "action": "Загрузить уведомление",
        },
        "missing_e1": {
            "title": "Отсутствует декларация E1",
            "desc": "Пожалуйста, загрузите вашу последнюю декларацию E1 для полного учёта вашей доходной ситуации.",
            "action": "Загрузить E1",
        },
        "missing_svs": {
            "title": "Отсутствует уведомление SVS",
            "desc": "Загрузите уведомление о взносах SVS для корректного учёта социальных взносов.",
            "action": "Загрузить SVS",
        },
        "missing_kaufvertrag": {
            "title": "Отсутствует договор купли-продажи",
            "desc": "Пожалуйста, загрузите договор купли-продажи недвижимости для расчёта амортизации и стоимости приобретения.",
            "action": "Загрузить договор",
        },
        "missing_mietvertrag": {
            "title": "Отсутствует договор аренды",
            "desc": "Загрузите ваш договор аренды, чтобы мы могли правильно распределить доход от аренды и вычитаемые расходы.",
            "action": "Загрузить договор",
        },
        "conflict_title": "Обнаружено расхождение данных",
        "conflict_desc": (
            "Налоговое уведомление показывает {bescheid_amount}, "
            "но ваши записанные транзакции составляют {txn_amount}. "
            "Пожалуйста, проверьте — уведомление (Bescheid) имеет приоритет."
        ),
    },
    "hu": {
        "missing_lohnzettel": {
            "title": "Bérjegy hiányzik",
            "desc": "Kérjük, töltse fel a Lohnzettel (L16) dokumentumot, hogy pontosan kiszámíthassuk a munkaviszonyból származó jövedelmét.",
            "action": "Lohnzettel feltöltése",
        },
        "missing_bescheid": {
            "title": "Adómegállapítás hiányzik",
            "desc": "Töltse fel a legutóbbi Einkommensteuerbescheid-et a veszteségelhatárolások és korábbi adatok rögzítéséhez.",
            "action": "Határozat feltöltése",
        },
        "missing_e1": {
            "title": "E1 adóbevallás hiányzik",
            "desc": "Kérjük, töltse fel a legutóbbi E1 adóbevallását, hogy teljes képet kapjunk jövedelmi helyzetéről.",
            "action": "E1 feltöltése",
        },
        "missing_svs": {
            "title": "SVS értesítés hiányzik",
            "desc": "Töltse fel az SVS járulékértesítőt a társadalombiztosítási járulékok pontos elszámolásához.",
            "action": "SVS feltöltése",
        },
        "missing_kaufvertrag": {
            "title": "Adásvételi szerződés hiányzik",
            "desc": "Kérjük, töltse fel az ingatlan adásvételi szerződését az értékcsökkenés és a beszerzési költségek kiszámításához.",
            "action": "Szerződés feltöltése",
        },
        "missing_mietvertrag": {
            "title": "Bérleti szerződés hiányzik",
            "desc": "Töltse fel bérleti szerződését, hogy a bérleti bevételeket és levonható kiadásokat helyesen rendelhessük hozzá.",
            "action": "Szerződés feltöltése",
        },
        "conflict_title": "Adateltérés észlelve",
        "conflict_desc": (
            "Az adómegállapítás {bescheid_amount} összeget mutat, "
            "de a rögzített tranzakciók összege {txn_amount}. "
            "Kérjük, ellenőrizze — a határozat (Bescheid) az irányadó."
        ),
    },
    "pl": {
        "missing_lohnzettel": {
            "title": "Brak zaświadczenia o wynagrodzeniu",
            "desc": "Proszę przesłać Lohnzettel (L16), abyśmy mogli dokładnie obliczyć Twój dochód z zatrudnienia.",
            "action": "Prześlij Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Brak decyzji podatkowej",
            "desc": "Prześlij ostatnią decyzję podatkową (Einkommensteuerbescheid), aby uwzględnić przeniesienie strat i dane historyczne.",
            "action": "Prześlij decyzję",
        },
        "missing_e1": {
            "title": "Brak deklaracji E1",
            "desc": "Proszę przesłać ostatnią deklarację podatkową E1, abyśmy mogli w pełni uchwycić Twoją sytuację dochodową.",
            "action": "Prześlij E1",
        },
        "missing_svs": {
            "title": "Brak zawiadomienia SVS",
            "desc": "Prześlij zawiadomienie o składkach SVS, aby prawidłowo uwzględnić składki na ubezpieczenie społeczne.",
            "action": "Prześlij SVS",
        },
        "missing_kaufvertrag": {
            "title": "Brak umowy kupna",
            "desc": "Proszę przesłać umowę kupna nieruchomości, aby obliczyć amortyzację i koszty nabycia.",
            "action": "Prześlij umowę",
        },
        "missing_mietvertrag": {
            "title": "Brak umowy najmu",
            "desc": "Prześlij umowę najmu, abyśmy mogli prawidłowo przypisać dochód z najmu i koszty uzyskania przychodu.",
            "action": "Prześlij umowę",
        },
        "conflict_title": "Wykryto rozbieżność danych",
        "conflict_desc": (
            "Decyzja podatkowa wykazuje {bescheid_amount}, "
            "ale zarejestrowane transakcje wynoszą łącznie {txn_amount}. "
            "Proszę sprawdzić — decyzja podatkowa (Bescheid) ma pierwszeństwo."
        ),
    },
    "tr": {
        "missing_lohnzettel": {
            "title": "Maas bordrosu eksik",
            "desc": "Lutfen Lohnzettel (L16) belgenizi yukleyin, boylece maas gelirinizi dogru hesaplayabilelim.",
            "action": "Lohnzettel yukle",
        },
        "missing_bescheid": {
            "title": "Vergi degerlendirmesi eksik",
            "desc": "Zarar tasimasini ve gecmis verileri kaydetmek icin son Einkommensteuerbescheid belgenizi yukleyin.",
            "action": "Degerlendirme yukle",
        },
        "missing_e1": {
            "title": "E1 vergi beyannamesi eksik",
            "desc": "Lutfen son E1 vergi beyannamenizi yukleyin, boylece gelir durumunuzu eksiksiz kavrayabilelim.",
            "action": "E1 yukle",
        },
        "missing_svs": {
            "title": "SVS bildirimi eksik",
            "desc": "Sosyal sigorta katkilarini dogru hesaplamak icin SVS katki bildirimnizi yukleyin.",
            "action": "SVS yukle",
        },
        "missing_kaufvertrag": {
            "title": "Satin alma sozlesmesi eksik",
            "desc": "Lutfen gayrimenkul satin alma sozlesmenizi yukleyin, boylece amortisman ve edinme maliyetlerini hesaplayabilelim.",
            "action": "Sozlesme yukle",
        },
        "missing_mietvertrag": {
            "title": "Kira sozlesmesi eksik",
            "desc": "Kira gelirlerini ve indirilebilir giderleri dogru atayabilmemiz icin kira sozlesmenizi yukleyin.",
            "action": "Sozlesme yukle",
        },
        "conflict_title": "Veri uyumsuzlugu tespit edildi",
        "conflict_desc": (
            "Vergi degerlendirmesi {bescheid_amount} gosteriyor, "
            "ancak kayitli islemlerinizin toplami {txn_amount}. "
            "Lutfen kontrol edin - vergi degerlendirmesi (Bescheid) onceliklidir."
        ),
    },
    "bs": {
        "missing_lohnzettel": {
            "title": "Nedostaje platni listic",
            "desc": "Molimo ucitajte vas Lohnzettel (L16) kako bismo mogli tacno izracunati vas dohodak od zaposlenja.",
            "action": "Ucitaj Lohnzettel",
        },
        "missing_bescheid": {
            "title": "Nedostaje porezno rjesenje",
            "desc": "Ucitajte posljednji Einkommensteuerbescheid radi evidentiranja prenesenih gubitaka i historijskih podataka.",
            "action": "Ucitaj rjesenje",
        },
        "missing_e1": {
            "title": "Nedostaje E1 porezna prijava",
            "desc": "Molimo ucitajte posljednju E1 poreznu prijavu kako bismo u potpunosti obuhvatili vasu prihodovnu situaciju.",
            "action": "Ucitaj E1",
        },
        "missing_svs": {
            "title": "Nedostaje SVS obavijest",
            "desc": "Ucitajte SVS obavijest o doprinosima radi tacnog obracuna doprinosa za socijalno osiguranje.",
            "action": "Ucitaj SVS",
        },
        "missing_kaufvertrag": {
            "title": "Nedostaje kupoprodajni ugovor",
            "desc": "Molimo ucitajte kupoprodajni ugovor za nekretninu radi izracuna amortizacije i troskova sticanja.",
            "action": "Ucitaj ugovor",
        },
        "missing_mietvertrag": {
            "title": "Nedostaje ugovor o najmu",
            "desc": "Ucitajte ugovor o najmu kako bismo mogli pravilno rasporediti prihode od najma i odbitne troskove.",
            "action": "Ucitaj ugovor",
        },
        "conflict_title": "Otkriveno odstupanje podataka",
        "conflict_desc": (
            "Porezno rjesenje pokazuje {bescheid_amount}, "
            "ali vase evidentirane transakcije iznose ukupno {txn_amount}. "
            "Molimo provjerite - porezno rjesenje (Bescheid) ima prednost."
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
    "fr": [
        {
            "title": "Déclaration d'impôt sur le revenu (papier)",
            "description": "Date limite de dépôt de la déclaration papier",
        },
        {
            "title": "Déclaration d'impôt sur le revenu (FinanzOnline)",
            "description": "Date limite de déclaration électronique via FinanzOnline",
        },
        {
            "title": "Déclaration préalable de TVA (UVA) Janvier",
            "description": "Déclaration mensuelle de TVA pour janvier",
        },
        {
            "title": "Soumission des fiches de paie",
            "description": "L'employeur doit soumettre les fiches de paie annuelles",
        },
        {
            "title": "Base de cotisation SVS",
            "description": "Date limite de déclaration de la base de cotisation SVS",
        },
        {
            "title": "Évaluation fiscale des employés (prolongée)",
            "description": "Date limite prolongée pour l'évaluation fiscale des employés (avec conseiller fiscal)",
        },
    ],
    "ru": [
        {
            "title": "Декларация по подоходному налогу (бумажная)",
            "description": "Срок подачи бумажной налоговой декларации",
        },
        {
            "title": "Декларация по подоходному налогу (FinanzOnline)",
            "description": "Срок электронной подачи через FinanzOnline",
        },
        {
            "title": "Предварительная декларация НДС (UVA) Январь",
            "description": "Ежемесячная предварительная декларация НДС за январь",
        },
        {
            "title": "Подача зарплатных ведомостей",
            "description": "Работодатель должен подать годовые зарплатные ведомости",
        },
        {
            "title": "База взносов SVS",
            "description": "Срок подачи декларации о базе взносов SVS",
        },
        {
            "title": "Налоговая оценка сотрудников (продлённая)",
            "description": "Продлённый срок налоговой оценки сотрудников (с налоговым консультантом)",
        },
    ],
    "hu": [
        {
            "title": "Jövedelemadó bevallás (papír)",
            "description": "Papíralapú adóbevallás benyújtási határideje",
        },
        {
            "title": "Jövedelemadó bevallás (FinanzOnline)",
            "description": "Elektronikus adóbevallás határideje a FinanzOnline-on keresztül",
        },
        {
            "title": "ÁFA előzetes bevallás (UVA) január",
            "description": "Januári havi ÁFA előzetes bevallás",
        },
        {
            "title": "Bérjegy benyújtás",
            "description": "A munkáltatónak be kell nyújtania az éves bérjegyeket",
        },
        {
            "title": "SVS járulékalap",
            "description": "SVS járulékalap-bejelentés határideje",
        },
        {
            "title": "Munkavállalói adómegállapítás (meghosszabbított)",
            "description": "Meghosszabbított határidő a munkavállalói adómegállapításhoz (adótanácsadóval)",
        },
    ],
    "pl": [
        {
            "title": "Zeznanie podatkowe (papierowe)",
            "description": "Termin składania papierowego zeznania podatkowego",
        },
        {
            "title": "Zeznanie podatkowe (FinanzOnline)",
            "description": "Termin elektronicznego zeznania podatkowego przez FinanzOnline",
        },
        {
            "title": "Zaliczka na VAT (UVA) styczeń",
            "description": "Miesięczna zaliczka na VAT za styczeń",
        },
        {
            "title": "Przekazanie zaświadczeń o wynagrodzeniu",
            "description": "Pracodawca musi przekazać roczne zaświadczenia podatkowe o wynagrodzeniu",
        },
        {
            "title": "Podstawa składek SVS",
            "description": "Termin zgłoszenia podstawy składek SVS",
        },
        {
            "title": "Rozliczenie podatkowe pracowników (przedłużone)",
            "description": "Przedłużony termin rozliczenia podatkowego pracowników (z doradcą podatkowym)",
        },
    ],
    "tr": [
        {
            "title": "Gelir vergisi beyannamesi (kagit)",
            "description": "Kagit vergi beyannamesi gonderim son tarihi",
        },
        {
            "title": "Gelir vergisi beyannamesi (FinanzOnline)",
            "description": "FinanzOnline uzerinden elektronik vergi beyannamesi son tarihi",
        },
        {
            "title": "KDV on beyannamesi (UVA) Ocak",
            "description": "Ocak ayi icin aylik KDV on beyannamesi",
        },
        {
            "title": "Maas bordrosu gonderimi",
            "description": "Isverenin yillik maas bordrolari gondermesi gerekir",
        },
        {
            "title": "SVS katki matrah",
            "description": "SVS katki matrahi bildirimi son tarihi",
        },
        {
            "title": "Calisan vergi degerlendirmesi (uzatilmis)",
            "description": "Calisan vergi degerlendirmesi icin uzatilmis son tarih (vergi danismanli)",
        },
    ],
    "bs": [
        {
            "title": "Prijava poreza na dohodak (papirna)",
            "description": "Rok za podnasanje papirne porezne prijave",
        },
        {
            "title": "Prijava poreza na dohodak (FinanzOnline)",
            "description": "Rok za elektronsku poreznu prijavu putem FinanzOnline",
        },
        {
            "title": "Prethodna prijava PDV-a (UVA) januar",
            "description": "Mjesecna prethodna prijava PDV-a za januar",
        },
        {
            "title": "Dostava platnih listica",
            "description": "Poslodavac mora dostaviti godisnje potvrde o porezu na platu",
        },
        {
            "title": "SVS osnovica doprinosa",
            "description": "Rok za prijavu osnovice doprinosa SVS",
        },
        {
            "title": "Porezna procjena zaposlenika (produzena)",
            "description": "Produzeni rok za poreznu procjenu zaposlenika (uz poreznog savjetnika)",
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

        total_income = sum_postings(
            transactions,
            posting_types={LineItemPostingType.INCOME},
        )
        total_expenses = sum_postings(
            transactions,
            posting_types={LineItemPostingType.EXPENSE},
            include_private_use=False,
        )
        deductible_expenses = sum_postings(
            transactions,
            posting_types={LineItemPostingType.EXPENSE},
            deductible_only=True,
            include_private_use=False,
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
            # Load tax brackets from DB (TaxConfiguration table)
            from app.models.tax_configuration import TaxConfiguration
            tax_config = (
                self.db.query(TaxConfiguration)
                .filter(TaxConfiguration.tax_year == tax_year)
                .first()
            )

            if tax_config and tax_config.tax_brackets:
                # Brackets already include the 0% band (exemption).
                # Apply progressive brackets directly to net_income.
                gross = max(Decimal("0"), net_income)
                db_brackets = tax_config.tax_brackets
                estimated_tax = Decimal("0")
                for b in db_brackets:
                    lower = Decimal(str(b.get("lower", b.get("min", 0))))
                    upper_raw = b.get("upper", b.get("max"))
                    rate = Decimal(str(b["rate"]))
                    if rate > 1:
                        rate = rate / Decimal("100")
                    if gross <= lower:
                        break
                    if upper_raw is not None:
                        upper = Decimal(str(upper_raw))
                        taxable_in_bracket = min(gross, upper) - lower
                    else:
                        taxable_in_bracket = gross - lower
                    if taxable_in_bracket > 0:
                        estimated_tax += taxable_in_bracket * rate
            else:
                # Fallback: 2026 hardcoded brackets if no DB config
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

        # VAT threshold distance (Kleinunternehmerregelung)
        # Only relevant for self-employed / business / mixed users
        user_type_val = ""
        if user and user.user_type:
            user_type_val = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
        is_vat_relevant = user_type_val in ("self_employed", "mixed", "small_business")

        if is_vat_relevant:
            # Read threshold from DB TaxConfiguration
            from app.models.tax_configuration import TaxConfiguration as TC
            tc = (
                self.db.query(TC)
                .filter(TC.tax_year == tax_year)
                .first()
            )
            if tc and tc.vat_rates and isinstance(tc.vat_rates, dict):
                vat_threshold = Decimal(str(tc.vat_rates.get("small_business_threshold", 55000)))
            else:
                # Fallback
                vat_threshold = Decimal("55000") if tax_year >= 2025 else Decimal("35000")
            vat_distance = float(vat_threshold - total_income)
        else:
            vat_distance = None

        # Monthly trends
        monthly_income: Dict[int, float] = defaultdict(float)
        monthly_expenses: Dict[int, float] = defaultdict(float)
        for record in iter_posting_records(transactions, include_private_use=False):
            if not record.transaction_date:
                continue
            month = record.transaction_date.month
            if record.posting_type == LineItemPostingType.INCOME:
                monthly_income[month] += float(record.total_amount)
            elif record.posting_type == LineItemPostingType.EXPENSE:
                monthly_expenses[month] += float(record.total_amount)

        monthly_data = []
        for month in range(1, 13):
            monthly_data.append({
                "month": month,
                "income": monthly_income.get(month, 0.0),
                "expenses": monthly_expenses.get(month, 0.0),
            })

        # Category breakdowns for charts
        income_by_cat = sum_postings_by_category(
            transactions,
            posting_types={LineItemPostingType.INCOME},
            include_private_use=False,
        )
        expense_by_cat = sum_postings_by_category(
            transactions,
            posting_types={LineItemPostingType.EXPENSE},
            include_private_use=False,
        )

        income_category_data = [{"category": k, "amount": float(v)} for k, v in income_by_cat.items()]
        expense_category_data = [{"category": k, "amount": float(v)} for k, v in expense_by_cat.items()]

        # Count transactions needing review
        pending_review_count = sum(
            1 for t in transactions
            if getattr(t, 'needs_review', False) and not getattr(t, 'reviewed', False)
        )

        result = {
            "yearToDateIncome": float(total_income),
            "yearToDateExpenses": float(total_expenses),
            "deductibleExpenses": float(deductible_expenses),
            "estimatedTax": float(estimated_tax),
            "paidTax": float(paid_tax),
            "remainingTax": float(remaining_tax),
            "netIncome": float(net_income),
            "vatThresholdDistance": vat_distance,
            "pendingReviewCount": pending_review_count,
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
                "action_url": "/transactions?action=add&category=home_office&type=expense",
                "action_label": texts["home_office_action"],
            })

        if "commuting" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["pendler_title"],
                "description": texts["pendler_desc"],
                "potential_savings": 500.0,
                "priority": "high",
                "action_url": "/transactions?action=add&category=commuting&type=expense",
                "action_label": texts["pendler_action"],
            })

        if "insurance" not in expense_cats:
            suggestions.append({
                "type": "missing_deduction",
                "title": texts["insurance_title"],
                "description": texts["insurance_desc"],
                "potential_savings": 200.0,
                "priority": "medium",
                "action_url": "/transactions?action=add&category=insurance&type=expense",
                "action_label": texts["insurance_action"],
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
                "action_url": "/transactions?filter=non_deductible",
                "action_label": texts["review_action"],
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
                "action_url": "/documents?filter=needs_review",
                "action_label": texts["ocr_action"],
            })

        if not transactions:
            suggestions.append({
                "type": "getting_started",
                "title": texts["getting_started_title"],
                "description": texts["getting_started_desc"],
                "potential_savings": 0,
                "priority": "high",
                "action_url": "/documents",
                "action_label": texts["getting_started_action"],
            })

        # --- Document completeness check ---
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            ut = user.user_type.value if hasattr(user.user_type, "value") else str(user.user_type)
            required = _REQUIRED_DOCS.get(ut, [])
            doc_texts = _DOC_COMPLETENESS_TEXTS.get(language, _DOC_COMPLETENESS_TEXTS["de"])

            # Previous tax year docs (we need last year's data for this year's calc)
            prev_year = tax_year - 1
            uploaded_types = set(
                row[0]
                for row in self.db.query(Document.document_type)
                .filter(Document.user_id == user_id)
                .all()
            )

            # Check if user has any historical transactions (not a brand-new user)
            has_history = bool(transactions) or (
                self.db.query(Transaction.id)
                .filter(
                    Transaction.user_id == user_id,
                    extract("year", Transaction.transaction_date) == prev_year,
                )
                .first()
            )

            for doc_type, text_key, priority, needs_history in required:
                if needs_history and not has_history:
                    continue
                if doc_type not in uploaded_types:
                    entry = doc_texts.get(text_key, {})
                    if entry:
                        suggestions.append({
                            "type": "missing_document",
                            "title": entry["title"],
                            "description": entry["desc"],
                            "document_type": doc_type.value,
                            "potential_savings": 0,
                            "priority": priority,
                            "action_url": "/documents",
                            "action_label": entry.get("action", None),
                        })

            # --- Data conflict detection (Bescheid vs Lohnzettel transactions) ---
            bescheid_docs = (
                self.db.query(Document)
                .filter(
                    Document.user_id == user_id,
                    Document.document_type == DocumentType.EINKOMMENSTEUERBESCHEID,
                    Document.ocr_result.isnot(None),
                )
                .all()
            )
            for bdoc in bescheid_docs:
                ocr = bdoc.ocr_result or {}
                hist = ocr.get("historical_tax_data", {})
                bescheid_year = hist.get("tax_year")
                bescheid_income = hist.get("total_income") or hist.get("kz_245")
                if bescheid_year and bescheid_income is not None:
                    try:
                        bescheid_amt = float(bescheid_income)
                    except (ValueError, TypeError):
                        continue
                    # Sum employment income transactions for that year
                    txn_total = (
                        self.db.query(func.sum(Transaction.amount))
                        .filter(
                            Transaction.user_id == user_id,
                            Transaction.type == TransactionType.INCOME,
                            extract("year", Transaction.transaction_date) == int(bescheid_year),
                        )
                        .scalar()
                    )
                    txn_amt = float(txn_total) if txn_total else 0.0
                    # Flag if difference > 5%
                    if bescheid_amt > 0 and abs(txn_amt - bescheid_amt) / bescheid_amt > 0.05:
                        suggestions.append({
                            "type": "data_conflict",
                            "title": doc_texts["conflict_title"],
                            "description": doc_texts["conflict_desc"].format(
                                bescheid_amount=f"€{bescheid_amt:,.2f}",
                                txn_amount=f"€{txn_amt:,.2f}",
                            ),
                            "tax_year_affected": int(bescheid_year),
                            "bescheid_amount": bescheid_amt,
                            "transaction_amount": txn_amt,
                            "potential_savings": 0,
                            "priority": "high",
                            "action_url": "/transactions",
                            "action_label": None,
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
            "fr": {
                "agriculture": "Nous avons detecte des revenus agricoles/forestiers. Envisagez de mettre a jour votre profil en 'Independant' ou 'Mixte'.",
                "self_employment": "Nous avons detecte des revenus d'activite independante. Envisagez de mettre a jour votre profil en 'Independant' ou 'Mixte'.",
                "business": "Nous avons detecte des revenus commerciaux. Envisagez de mettre a jour votre profil en 'Independant' ou 'Mixte'.",
                "employment": "Nous avons detecte des revenus salaries. Envisagez de mettre a jour votre profil en 'Salarie' ou 'Mixte'.",
                "rental": "Nous avons detecte des revenus locatifs. Envisagez de mettre a jour votre profil en 'Bailleur' ou 'Mixte'.",
            },
            "ru": {
                "agriculture": "\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0434\u043e\u0445\u043e\u0434\u044b \u043e\u0442 \u0441\u0435\u043b\u044c\u0441\u043a\u043e\u0433\u043e/\u043b\u0435\u0441\u043d\u043e\u0433\u043e \u0445\u043e\u0437\u044f\u0439\u0441\u0442\u0432\u0430. \u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u043d\u0430 '\u0421\u0430\u043c\u043e\u0437\u0430\u043d\u044f\u0442\u044b\u0439' \u0438\u043b\u0438 '\u0421\u043c\u0435\u0448\u0430\u043d\u043d\u044b\u0439'.",
                "self_employment": "\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0434\u043e\u0445\u043e\u0434\u044b \u043e\u0442 \u0441\u0430\u043c\u043e\u0441\u0442\u043e\u044f\u0442\u0435\u043b\u044c\u043d\u043e\u0439 \u0434\u0435\u044f\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u0438. \u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u043d\u0430 '\u0421\u0430\u043c\u043e\u0437\u0430\u043d\u044f\u0442\u044b\u0439' \u0438\u043b\u0438 '\u0421\u043c\u0435\u0448\u0430\u043d\u043d\u044b\u0439'.",
                "business": "\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0434\u043e\u0445\u043e\u0434\u044b \u043e\u0442 \u043f\u0440\u0435\u0434\u043f\u0440\u0438\u043d\u0438\u043c\u0430\u0442\u0435\u043b\u044c\u0441\u043a\u043e\u0439 \u0434\u0435\u044f\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u0438. \u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u043d\u0430 '\u0421\u0430\u043c\u043e\u0437\u0430\u043d\u044f\u0442\u044b\u0439' \u0438\u043b\u0438 '\u0421\u043c\u0435\u0448\u0430\u043d\u043d\u044b\u0439'.",
                "employment": "\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0434\u043e\u0445\u043e\u0434\u044b \u043e\u0442 \u0442\u0440\u0443\u0434\u043e\u0432\u043e\u0439 \u0434\u0435\u044f\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u0438. \u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u043d\u0430 '\u0420\u0430\u0431\u043e\u0442\u043d\u0438\u043a' \u0438\u043b\u0438 '\u0421\u043c\u0435\u0448\u0430\u043d\u043d\u044b\u0439'.",
                "rental": "\u041e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u044b \u0434\u043e\u0445\u043e\u0434\u044b \u043e\u0442 \u0430\u0440\u0435\u043d\u0434\u044b. \u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u043d\u0430 '\u0410\u0440\u0435\u043d\u0434\u043e\u0434\u0430\u0442\u0435\u043b\u044c' \u0438\u043b\u0438 '\u0421\u043c\u0435\u0448\u0430\u043d\u043d\u044b\u0439'.",
            },
            "hu": {
                "agriculture": "Mezőgazdasági/erdészeti jövedelmet észleltünk. Fontolja meg profilja frissítését 'Egyéni vállalkozó' vagy 'Vegyes' típusra.",
                "self_employment": "Önálló tevékenységből származó jövedelmet észleltünk. Fontolja meg profilja frissítését 'Egyéni vállalkozó' vagy 'Vegyes' típusra.",
                "business": "Üzleti jövedelmet észleltünk. Fontolja meg profilja frissítését 'Egyéni vállalkozó' vagy 'Vegyes' típusra.",
                "employment": "Munkaviszonyból származó jövedelmet észleltünk. Fontolja meg profilja frissítését 'Alkalmazott' vagy 'Vegyes' típusra.",
                "rental": "Bérleti jövedelmet észleltünk. Fontolja meg profilja frissítését 'Bérbeadó' vagy 'Vegyes' típusra.",
            },
            "pl": {
                "agriculture": "Wykryliśmy dochody z rolnictwa/leśnictwa. Rozważ aktualizację profilu na 'Samozatrudniony' lub 'Mieszany'.",
                "self_employment": "Wykryliśmy dochody z działalności na własny rachunek. Rozważ aktualizację profilu na 'Samozatrudniony' lub 'Mieszany'.",
                "business": "Wykryliśmy dochody z działalności gospodarczej. Rozważ aktualizację profilu na 'Samozatrudniony' lub 'Mieszany'.",
                "employment": "Wykryliśmy dochody z zatrudnienia. Rozważ aktualizację profilu na 'Pracownik' lub 'Mieszany'.",
                "rental": "Wykryliśmy dochody z najmu. Rozważ aktualizację profilu na 'Wynajmujący' lub 'Mieszany'.",
            },
            "tr": {
                "agriculture": "Tarim/ormancilik geliri tespit ettik. Profilinizi 'Serbest calisan' veya 'Karisik' olarak guncellemeyi dusunun.",
                "self_employment": "Serbest meslek geliri tespit ettik. Profilinizi 'Serbest calisan' veya 'Karisik' olarak guncellemeyi dusunun.",
                "business": "Ticari gelir tespit ettik. Profilinizi 'Serbest calisan' veya 'Karisik' olarak guncellemeyi dusunun.",
                "employment": "Maas geliri tespit ettik. Profilinizi 'Calisan' veya 'Karisik' olarak guncellemeyi dusunun.",
                "rental": "Kira geliri tespit ettik. Profilinizi 'Ev sahibi' veya 'Karisik' olarak guncellemeyi dusunun.",
            },
            "bs": {
                "agriculture": "Otkrili smo prihode od poljoprivrede/sumarstva. Razmislite o azuriranju profila na 'Samostalna djelatnost' ili 'Mjesovito'.",
                "self_employment": "Otkrili smo prihode od samostalne djelatnosti. Razmislite o azuriranju profila na 'Samostalna djelatnost' ili 'Mjesovito'.",
                "business": "Otkrili smo poslovne prihode. Razmislite o azuriranju profila na 'Samostalna djelatnost' ili 'Mjesovito'.",
                "employment": "Otkrili smo prihode od zaposlenja. Razmislite o azuriranju profila na 'Zaposlenik' ili 'Mjesovito'.",
                "rental": "Otkrili smo prihode od najma. Razmislite o azuriranju profila na 'Najmodavac' ili 'Mjesovito'.",
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
