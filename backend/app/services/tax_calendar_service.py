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
            "description": "Annual income tax return deadline",
            "description_de": "Frist für die jährliche Einkommensteuererklärung",
            "description_zh": "年度所得税申报截止日期",
        },
        DeadlineType.ARBEITNEHMERVERANLAGUNG: {
            "date": (6, 30),  # June 30
            "name": "Arbeitnehmerveranlagung",
            "name_en": "Employee Tax Assessment",
            "name_zh": "员工税务评估",
            "description": "Employee tax refund application deadline",
            "description_de": "Frist für Arbeitnehmerveranlagung (Steuerausgleich)",
            "description_zh": "员工退税申请截止日期",
        },
        DeadlineType.VAT_ANNUAL: {
            "date": (6, 30),  # June 30
            "name": "Umsatzsteuererklärung",
            "name_en": "Annual VAT Return",
            "name_zh": "年度增值税申报",
            "description": "Annual VAT return deadline",
            "description_de": "Frist für die jährliche Umsatzsteuererklärung",
            "description_zh": "年度增值税申报截止日期",
        },
    }

    # Quarterly deadlines (calculated)
    QUARTERLY_DEADLINES = {
        DeadlineType.VAT_QUARTERLY: {
            "name": "Umsatzsteuer-Voranmeldung",
            "name_en": "Quarterly VAT Prepayment",
            "name_zh": "季度增值税预缴",
            "description": "Quarterly VAT prepayment",
            "description_de": "Vierteljährliche Umsatzsteuer-Voranmeldung",
            "description_zh": "季度增值税预缴",
            "due_day": 15,  # 15th of month following quarter
        },
        DeadlineType.SVS_QUARTERLY: {
            "name": "SVS Beitragszahlung",
            "name_en": "Quarterly SVS Contribution",
            "name_zh": "季度社保缴费",
            "description": "Quarterly social insurance contribution",
            "description_de": "Vierteljährliche SVS-Beitragszahlung",
            "description_zh": "季度社会保险缴费",
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
        if language == "en":
            return info.get(f"{field}_en", info.get(field, ""))
        elif language == "zh":
            return info.get(f"{field}_zh", info.get(field, ""))
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
