"""
Insurance module constants — needs_user_input mappings, deductibility rules,
and special-action subtypes for the Austrian tax domain.
"""

# Insurance subtypes that require user input for partial deductibility
INSURANCE_NEEDS_USER_INPUT = {
    "kfz": [{"field": "business_use_percentage", "type": "percentage", "label": "Geschäftlicher KFZ-Anteil (%)"}],
    "rechtsschutz": [{"field": "beruflicher_anteil", "type": "percentage", "label": "Beruflicher Anteil (%)"}],
    "haushaltsversicherung": [{"field": "arbeitszimmer_anteil", "type": "percentage", "label": "Arbeitszimmer-Anteil (%)"}],
}

# Insurance subtypes that are 100% deductible without user input
INSURANCE_NO_INPUT_100_PCT = {"berufshaftpflicht", "betriebsunterbrechung"}

# Insurance types no longer deductible as Sonderausgaben since 2021
INSURANCE_NOT_DEDUCTIBLE_2021 = {"private_krankenversicherung", "unfallversicherung", "lebensversicherung"}

# Action subtypes — trigger workflow actions, not financial transactions
INSURANCE_AUTO_ACTION_SUBTYPES = {"kuendigung", "praemienaenderung"}

# SEPA receipts — archive only, handled separately by payment matching
INSURANCE_ARCHIVE_ONLY_SUBTYPES = {"sepa_beleg"}
