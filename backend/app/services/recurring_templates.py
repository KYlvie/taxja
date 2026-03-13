"""Recurring transaction templates for common use cases"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from app.models.recurring_transaction import RecurrenceFrequency


@dataclass
class RecurringTemplate:
    """Template for common recurring transactions"""
    id: str
    name_de: str
    name_en: str
    name_zh: str
    description_de: str
    description_en: str
    description_zh: str
    transaction_type: str  # 'income' or 'expense'
    category: str
    frequency: RecurrenceFrequency
    default_day_of_month: int
    icon: str
    priority: int  # Higher = more important


# Template definitions
TEMPLATES: List[RecurringTemplate] = [
    # SVS Social Insurance - Most important for self-employed
    RecurringTemplate(
        id="svs",
        name_de="SVS Sozialversicherung",
        name_en="SVS Social Insurance",
        name_zh="SVS 社保预缴",
        description_de="Vierteljährliche Sozialversicherungsbeiträge für Selbständige",
        description_en="Quarterly social insurance payments for self-employed",
        description_zh="自雇人士季度社保缴纳（养老、健康、意外保险）",
        transaction_type="expense",
        category="Sozialversicherung",
        frequency=RecurrenceFrequency.QUARTERLY,
        default_day_of_month=15,
        icon="🏥",
        priority=100,
    ),
    
    # Chamber of Commerce Fee
    RecurringTemplate(
        id="wko",
        name_de="WKO Mitgliedsbeitrag",
        name_en="Chamber of Commerce Fee",
        name_zh="商会会费",
        description_de="Vierteljährlicher Beitrag zur Wirtschaftskammer",
        description_en="Quarterly chamber of commerce membership fee",
        description_zh="季度商会会费（强制性）",
        transaction_type="expense",
        category="Mitgliedsbeiträge",
        frequency=RecurrenceFrequency.QUARTERLY,
        default_day_of_month=15,
        icon="🏛️",
        priority=90,
    ),
    
    # Income Tax Prepayment
    RecurringTemplate(
        id="tax_prepayment",
        name_de="Einkommensteuervorauszahlung",
        name_en="Income Tax Prepayment",
        name_zh="所得税预缴",
        description_de="Vierteljährliche Einkommensteuervorauszahlung",
        description_en="Quarterly income tax prepayment",
        description_zh="季度所得税预缴（上年税额 > €2,000）",
        transaction_type="expense",
        category="Steuern",
        frequency=RecurrenceFrequency.QUARTERLY,
        default_day_of_month=15,
        icon="💰",
        priority=85,
    ),
    
    # Office Rent
    RecurringTemplate(
        id="office_rent",
        name_de="Büro-Miete",
        name_en="Office Rent",
        name_zh="办公室租金",
        description_de="Monatliche Miete für Büroräume",
        description_en="Monthly office rent payment",
        description_zh="月度办公室租金",
        transaction_type="expense",
        category="Raumkosten",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="🏢",
        priority=80,
    ),
    
    # Software Subscription
    RecurringTemplate(
        id="software_subscription",
        name_de="Software-Abonnement",
        name_en="Software Subscription",
        name_zh="软件订阅",
        description_de="Monatliches Software-Abonnement (z.B. Adobe, Microsoft 365)",
        description_en="Monthly software subscription (e.g., Adobe, Microsoft 365)",
        description_zh="月度软件订阅（如 Adobe、Microsoft 365）",
        transaction_type="expense",
        category="EDV-Kosten",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="💻",
        priority=70,
    ),
    
    # Professional Liability Insurance
    RecurringTemplate(
        id="liability_insurance",
        name_de="Berufshaftpflichtversicherung",
        name_en="Professional Liability Insurance",
        name_zh="职业责任保险",
        description_de="Jährliche Berufshaftpflichtversicherung",
        description_en="Annual professional liability insurance",
        description_zh="年度职业责任保险",
        transaction_type="expense",
        category="Versicherungen",
        frequency=RecurrenceFrequency.ANNUALLY,
        default_day_of_month=1,
        icon="🛡️",
        priority=65,
    ),
    
    # Accounting Service
    RecurringTemplate(
        id="accounting_service",
        name_de="Buchhaltungsservice",
        name_en="Accounting Service",
        name_zh="会计服务费",
        description_de="Monatliche Buchhaltungskosten",
        description_en="Monthly accounting service fee",
        description_zh="月度会计服务费",
        transaction_type="expense",
        category="Steuerberatungskosten",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="📊",
        priority=60,
    ),
    
    # Phone & Internet
    RecurringTemplate(
        id="phone_internet",
        name_de="Telefon & Internet",
        name_en="Phone & Internet",
        name_zh="电话和网络费",
        description_de="Monatliche Telefon- und Internetkosten",
        description_en="Monthly phone and internet costs",
        description_zh="月度电话和网络费用",
        transaction_type="expense",
        category="Kommunikationskosten",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="📞",
        priority=55,
    ),
    
    # Property Insurance
    RecurringTemplate(
        id="property_insurance",
        name_de="Gebäudeversicherung",
        name_en="Property Insurance",
        name_zh="房产保险",
        description_de="Jährliche Gebäudeversicherung",
        description_en="Annual property insurance",
        description_zh="年度房产保险",
        transaction_type="expense",
        category="Versicherungen",
        frequency=RecurrenceFrequency.ANNUALLY,
        default_day_of_month=1,
        icon="🏠",
        priority=50,
    ),
    
    # Property Management Fee
    RecurringTemplate(
        id="property_management",
        name_de="Hausverwaltung",
        name_en="Property Management",
        name_zh="物业管理费",
        description_de="Monatliche Hausverwaltungskosten",
        description_en="Monthly property management fee",
        description_zh="月度物业管理费",
        transaction_type="expense",
        category="Verwaltungskosten",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="🔑",
        priority=45,
    ),
    
    # Recurring Client Income
    RecurringTemplate(
        id="client_retainer",
        name_de="Kunden-Retainer",
        name_en="Client Retainer",
        name_zh="客户月度合同",
        description_de="Monatliche Einnahmen von Stammkunden",
        description_en="Monthly recurring income from client",
        description_zh="客户月度固定收入",
        transaction_type="income",
        category="Betriebseinnahmen",
        frequency=RecurrenceFrequency.MONTHLY,
        default_day_of_month=1,
        icon="💼",
        priority=40,
    ),
]


def get_all_templates() -> List[RecurringTemplate]:
    """Get all available templates sorted by priority"""
    return sorted(TEMPLATES, key=lambda t: t.priority, reverse=True)


def get_template_by_id(template_id: str) -> Optional[RecurringTemplate]:
    """Get a specific template by ID"""
    for template in TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_templates_by_type(transaction_type: str) -> List[RecurringTemplate]:
    """Get templates filtered by transaction type (income/expense)"""
    return [t for t in get_all_templates() if t.transaction_type == transaction_type]


def get_templates_for_user_type(user_type: str) -> List[RecurringTemplate]:
    """
    Get recommended templates based on user type.
    
    Args:
        user_type: One of 'employee', 'landlord', 'self_employed', 'small_business'
    
    Returns:
        List of recommended templates
    """
    if user_type == "self_employed":
        # Self-employed: SVS, WKO, tax prepayment, office costs
        priority_ids = ["svs", "wko", "tax_prepayment", "office_rent", 
                       "software_subscription", "accounting_service", "phone_internet"]
    elif user_type == "landlord":
        # Landlords: property-related expenses
        priority_ids = ["property_insurance", "property_management"]
    elif user_type == "small_business":
        # Small business: similar to self-employed
        priority_ids = ["svs", "wko", "tax_prepayment", "office_rent", 
                       "software_subscription", "accounting_service"]
    else:  # employee or unknown
        # Employees: minimal recurring expenses
        priority_ids = ["phone_internet"]
    
    # Return templates in priority order
    result = []
    for template_id in priority_ids:
        template = get_template_by_id(template_id)
        if template:
            result.append(template)
    
    # Add remaining templates
    for template in get_all_templates():
        if template.id not in priority_ids:
            result.append(template)
    
    return result
