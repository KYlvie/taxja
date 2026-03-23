"""
Tax Calendar Service

Manages Austrian tax deadlines and reminders.
Validates Requirements 8.7, 34.6.
"""

from datetime import datetime, date
from typing import List, Dict, Any
from enum import Enum


class DeadlineType(str, Enum):
    """Tax deadline types"""

    INCOME_TAX = "income_tax"
    VAT_QUARTERLY = "vat_quarterly"
    VAT_ANNUAL = "vat_annual"
    SVS_QUARTERLY = "svs_quarterly"
    ARBEITNEHMERVERANLAGUNG = "arbeitnehmerveranlagung"


class TaxCalendarService:
    """Manages tax calendar and deadlines"""

    # Austrian tax deadlines (fixed dates)
    DEADLINES = {
        DeadlineType.INCOME_TAX: {
            "date": (6, 30),  # June 30
            "name": "Einkommensteuererklärung",
            "name_en": "Income Tax Return",
            "name_zh": "所得税申报",
            "name_fr": "Déclaration d'impôt sur le revenu",
            "name_ru": "Декларация о подоходном налоге",
            "name_hu": "Jövedelemadó-bevallás",
            "name_pl": "Zeznanie podatkowe",
            "name_tr": "Gelir vergisi beyannamesi",
            "name_bs": "Prijava poreza na dohodak",
            "description": "Annual income tax return deadline",
            "description_de": "Frist für die jährliche Einkommensteuererklärung",
            "description_zh": "年度所得税申报截止日期",
            "description_fr": "Date limite de la déclaration annuelle d'impôt sur le revenu",
            "description_ru": "Крайний срок подачи ежегодной декларации о подоходном налоге",
            "description_hu": "Az éves jövedelemadó-bevallás határideje",
            "description_pl": "Termin składania rocznego zeznania podatkowego",
            "description_tr": "Yillik gelir vergisi beyannamesi son tarihi",
            "description_bs": "Rok za godisnju prijavu poreza na dohodak",
        },
        DeadlineType.ARBEITNEHMERVERANLAGUNG: {
            "date": (6, 30),  # June 30
            "name": "Arbeitnehmerveranlagung",
            "name_en": "Employee Tax Assessment",
            "name_zh": "员工税务评估",
            "name_fr": "Régularisation fiscale des salariés",
            "name_ru": "Налоговая оценка работников",
            "name_hu": "Munkavállalói adóelszámolás",
            "name_pl": "Rozliczenie podatkowe pracownika",
            "name_tr": "Calisan vergi degerlendirmesi",
            "name_bs": "Porezno uskladjivanje zaposlenika",
            "description": "Employee tax refund application deadline",
            "description_de": "Frist für Arbeitnehmerveranlagung (Steuerausgleich)",
            "description_zh": "员工退税申请截止日期",
            "description_fr": "Date limite de demande de remboursement d'impôt pour les salariés",
            "description_ru": "Крайний срок подачи заявления на возврат налога для работников",
            "description_hu": "Munkavállalói adó-visszatérítési kérelem határideje",
            "description_pl": "Termin składania wniosku o zwrot podatku dla pracowników",
            "description_tr": "Calisan vergi iadesi basvuru son tarihi",
            "description_bs": "Rok za podnošenje zahtjeva za povrat poreza za zaposlenike",
        },
        DeadlineType.VAT_ANNUAL: {
            "date": (6, 30),  # June 30
            "name": "Umsatzsteuererklärung",
            "name_en": "Annual VAT Return",
            "name_zh": "年度增值税申报",
            "name_fr": "Déclaration annuelle de TVA",
            "name_ru": "Годовая декларация по НДС",
            "name_hu": "Éves ÁFA bevallás",
            "name_pl": "Roczna deklaracja VAT",
            "name_tr": "Yillik KDV beyannamesi",
            "name_bs": "Godisnja prijava PDV-a",
            "description": "Annual VAT return deadline",
            "description_de": "Frist für die jährliche Umsatzsteuererklärung",
            "description_zh": "年度增值税申报截止日期",
            "description_fr": "Date limite de la déclaration annuelle de TVA",
            "description_ru": "Крайний срок подачи ежегодной декларации по НДС",
            "description_hu": "Az éves ÁFA bevallás határideje",
            "description_pl": "Termin składania rocznej deklaracji VAT",
            "description_tr": "Yillik KDV beyannamesi son tarihi",
            "description_bs": "Rok za godisnju prijavu PDV-a",
        },
    }

    # Quarterly deadlines (calculated)
    QUARTERLY_DEADLINES = {
        DeadlineType.VAT_QUARTERLY: {
            "name": "Umsatzsteuer-Voranmeldung",
            "name_en": "Quarterly VAT Prepayment",
            "name_zh": "季度增值税预缴",
            "name_fr": "Acompte trimestriel de TVA",
            "name_ru": "Ежеквартальный авансовый платёж по НДС",
            "name_hu": "Negyedéves ÁFA előleg",
            "name_pl": "Kwartalna zaliczka VAT",
            "name_tr": "Uc aylik KDV on odemesi",
            "name_bs": "Tromjesecna akontacija PDV-a",
            "description": "Quarterly VAT prepayment",
            "description_de": "Vierteljährliche Umsatzsteuer-Voranmeldung",
            "description_zh": "季度增值税预缴",
            "description_fr": "Acompte trimestriel de taxe sur la valeur ajoutée",
            "description_ru": "Ежеквартальный авансовый платёж по налогу на добавленную стоимость",
            "description_hu": "Negyedéves általános forgalmi adó előleg befizetés",
            "description_pl": "Kwartalna zaliczka na podatek od towarów i usług",
            "description_tr": "Uc aylik katma deger vergisi on odemesi",
            "description_bs": "Tromjesecna akontacija poreza na dodanu vrijednost",
            "due_day": 15,  # 15th of month following quarter
        },
        DeadlineType.SVS_QUARTERLY: {
            "name": "SVS Beitragszahlung",
            "name_en": "Quarterly SVS Contribution",
            "name_zh": "季度社保缴费",
            "name_fr": "Cotisation trimestrielle SVS",
            "name_ru": "Ежеквартальный взнос SVS",
            "name_hu": "Negyedéves SVS hozzájárulás",
            "name_pl": "Kwartalna składka SVS",
            "name_tr": "Uc aylik SVS katkisi",
            "name_bs": "Tromjesecni SVS doprinos",
            "description": "Quarterly social insurance contribution",
            "description_de": "Vierteljährliche SVS-Beitragszahlung",
            "description_zh": "季度社会保险缴费",
            "description_fr": "Cotisation trimestrielle d'assurance sociale",
            "description_ru": "Ежеквартальный взнос социального страхования",
            "description_hu": "Negyedéves társadalombiztosítási hozzájárulás",
            "description_pl": "Kwartalna składka na ubezpieczenie społeczne",
            "description_tr": "Uc aylik sosyal sigorta katkisi",
            "description_bs": "Tromjesecni doprinos za socijalno osiguranje",
            "due_day": 15,  # 15th of month following quarter
        },
    }

    def get_upcoming_deadlines(
        self, reference_date: date = None, days_ahead: int = 90, language: str = "de"
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming tax deadlines.

        Args:
            reference_date: Reference date (default: today)
            days_ahead: Number of days to look ahead
            language: Language for labels (de, en, zh)

        Returns:
            List of upcoming deadlines
        """
        if reference_date is None:
            reference_date = date.today()

        deadlines = []

        # Add annual deadlines
        for deadline_type, info in self.DEADLINES.items():
            deadline_date = date(reference_date.year, info["date"][0], info["date"][1])

            # If deadline has passed this year, show next year's
            if deadline_date < reference_date:
                deadline_date = date(
                    reference_date.year + 1, info["date"][0], info["date"][1]
                )

            # Only include if within days_ahead
            days_until = (deadline_date - reference_date).days
            if 0 <= days_until <= days_ahead:
                deadlines.append(
                    {
                        "type": deadline_type,
                        "date": deadline_date.isoformat(),
                        "days_until": days_until,
                        "name": self._get_localized_field(info, "name", language),
                        "description": self._get_localized_field(
                            info, "description", language
                        ),
                        "urgency": self._calculate_urgency(days_until),
                    }
                )

        # Add quarterly deadlines
        quarterly_deadlines = self._get_quarterly_deadlines(
            reference_date, days_ahead, language
        )
        deadlines.extend(quarterly_deadlines)

        # Sort by date
        deadlines.sort(key=lambda x: x["date"])

        return deadlines

    def _get_quarterly_deadlines(
        self, reference_date: date, days_ahead: int, language: str
    ) -> List[Dict[str, Any]]:
        """Get quarterly deadlines (VAT, SVS)"""
        deadlines = []

        # Quarter end months: March (Q1), June (Q2), September (Q3), December (Q4)
        quarter_end_months = [3, 6, 9, 12]

        for deadline_type, info in self.QUARTERLY_DEADLINES.items():
            for quarter_end_month in quarter_end_months:
                # Deadline is 15th of month following quarter end
                if quarter_end_month == 12:
                    deadline_month = 1
                    deadline_year = reference_date.year + 1
                else:
                    deadline_month = quarter_end_month + 1
                    deadline_year = reference_date.year

                deadline_date = date(deadline_year, deadline_month, info["due_day"])

                # If deadline has passed, skip
                if deadline_date < reference_date:
                    continue

                # Only include if within days_ahead
                days_until = (deadline_date - reference_date).days
                if 0 <= days_until <= days_ahead:
                    quarter_name = self._get_quarter_name(quarter_end_month, language)

                    deadlines.append(
                        {
                            "type": deadline_type,
                            "date": deadline_date.isoformat(),
                            "days_until": days_until,
                            "name": f"{self._get_localized_field(info, 'name', language)} ({quarter_name})",
                            "description": self._get_localized_field(
                                info, "description", language
                            ),
                            "quarter": self._get_quarter_number(quarter_end_month),
                            "urgency": self._calculate_urgency(days_until),
                        }
                    )

        return deadlines

    def _get_quarter_name(self, quarter_end_month: int, language: str) -> str:
        """Get quarter name"""
        quarter_num = self._get_quarter_number(quarter_end_month)

        if language == "de":
            return f"Q{quarter_num}"
        elif language == "en":
            return f"Q{quarter_num}"
        elif language == "zh":
            return f"第{quarter_num}季度"
        else:
            return f"Q{quarter_num}"

    def _get_quarter_number(self, quarter_end_month: int) -> int:
        """Get quarter number from end month"""
        return {3: 1, 6: 2, 9: 3, 12: 4}[quarter_end_month]

    def _calculate_urgency(self, days_until: int) -> str:
        """Calculate urgency level"""
        if days_until <= 7:
            return "urgent"
        elif days_until <= 30:
            return "soon"
        else:
            return "upcoming"

    def _get_localized_field(
        self, info: Dict[str, Any], field: str, language: str
    ) -> str:
        """Get localized field value"""
        if language in ("en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
            return info.get(f"{field}_{language}", info.get(f"{field}_de", info.get(field, "")))
        else:
            # Default to German or base field
            return info.get(f"{field}_de", info.get(field, ""))

    def get_deadline_details(
        self, deadline_type: DeadlineType, tax_year: int, language: str = "de"
    ) -> Dict[str, Any]:
        """Get detailed information about a specific deadline"""
        if deadline_type in self.DEADLINES:
            info = self.DEADLINES[deadline_type]
            deadline_date = date(tax_year, info["date"][0], info["date"][1])

            return {
                "type": deadline_type,
                "date": deadline_date.isoformat(),
                "name": self._get_localized_field(info, "name", language),
                "description": self._get_localized_field(info, "description", language),
                "tax_year": tax_year,
            }

        return {}
