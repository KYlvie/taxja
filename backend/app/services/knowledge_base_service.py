"""
Knowledge base service for initializing and managing Austrian tax law documents.
"""
from typing import List, Dict, Any
from pathlib import Path
import json

from app.services.vector_db_service import get_vector_db_service


class KnowledgeBaseService:
    """Service for managing tax knowledge base"""
    
    def __init__(self):
        self.vector_db = get_vector_db_service()
    
    def initialize_tax_law_documents(self):
        """Initialize Austrian tax law documents in vector database"""
        
        # Austrian tax law documents (2026)
        tax_law_docs = [
            {
                "text": "Einkommensteuer (Income Tax) in Österreich 2026: Die Einkommensteuer wird progressiv berechnet mit folgenden Steuersätzen: 0% bis €13.539, 20% von €13.539 bis €21.992, 30% von €21.992 bis €36.458, 40% von €36.458 bis €70.365, 48% von €70.365 bis €104.859, 50% von €104.859 bis €1.000.000, und 55% über €1.000.000.",
                "metadata": {"source": "USP 2026", "category": "income_tax", "language": "de"}
            },
            {
                "text": "Income Tax in Austria 2026: Income tax is calculated progressively with the following rates: 0% up to €13,539, 20% from €13,539 to €21,992, 30% from €21,992 to €36,458, 40% from €36,458 to €70,365, 48% from €70,365 to €104,859, 50% from €104,859 to €1,000,000, and 55% above €1,000,000.",
                "metadata": {"source": "USP 2026", "category": "income_tax", "language": "en"}
            },
            {
                "text": "奥地利2026年所得税：所得税采用累进税率计算，税率如下：€13,539以下为0%，€13,539至€21,992为20%，€21,992至€36,458为30%，€36,458至€70,365为40%，€70,365至€104,859为48%，€104,859至€1,000,000为50%，€1,000,000以上为55%。",
                "metadata": {"source": "USP 2026", "category": "income_tax", "language": "zh"}
            },
            {
                "text": "Umsatzsteuer (VAT) in Österreich: Der Standardsatz beträgt 20%. Ermäßigter Satz 10% für Lebensmittel, Bücher, Wohnraumvermietung und Beherbergung (kurzfristige Vermietung/Hotels). Besonderer Satz 13% für Kulturveranstaltungen. Kleinunternehmerregelung (§6 Abs 1 Z 27 UStG): Jahresumsatz bis €55.000 netto = USt-befreit (seit 2025, davor €35.000). Toleranzgrenze: einmalig bis €60.500 (10%). Kurzfristige Beherbergung (Airbnb, Ferienwohnung, Hotel): immer 10% USt (§10 Abs 2 Z 4 UStG), unabhängig ob §23 oder §28 EStG.",
                "metadata": {"source": "Austrian Tax Law", "category": "vat", "language": "de"}
            },
            {
                "text": "Value Added Tax (VAT) in Austria: Standard rate 20%. Reduced rate 10% for food, books, residential rental, and accommodation (short-term rental/hotels, §10 Abs 2 Z 4 UStG). Special rate 13% for cultural events. Kleinunternehmerregelung (§6 Abs 1 Z 27 UStG): annual turnover up to €55,000 net = VAT exempt (since 2025, previously €35,000). Tolerance: one-time up to €60,500 (10%). Short-term accommodation (Airbnb, holiday apartment, hotel): always 10% VAT, regardless of whether classified as §23 or §28 EStG.",
                "metadata": {"source": "Austrian Tax Law", "category": "vat", "language": "en"}
            },
            {
                "text": "奥地利增值税(UStG)：标准税率20%。优惠税率10%适用于食品、书籍、住宅租赁和住宿服务（短租/酒店，§10 Abs 2 Z 4 UStG）。特殊税率13%适用于文化活动。小企业规则(Kleinunternehmerregelung，§6 Abs 1 Z 27 UStG)：年净营业额不超过€55,000可免征增值税（2025年起，之前为€35,000）。容忍限额：一次性可达€60,500（10%）。短期住宿（Airbnb、度假公寓、酒店）：始终适用10%增值税，无论所得税分类为§23还是§28 EStG。",
                "metadata": {"source": "Austrian Tax Law", "category": "vat", "language": "zh"}
            },
            {
                "text": "Sozialversicherung (SVS) für Selbständige (Steuerjahr 2025, Veranlagung 2026): GSVG-Beiträge umfassen Pensionsversicherung (18,5%), Krankenversicherung (6,8%), Unfallversicherung (€12,95/Monat fix), und Selbständigenvorsorge (1,53%). Mindestbeitragsgrundlage: €551,10/Monat. Höchstbeitragsgrundlage: €8.085/Monat. Quelle: SVS/WKO.",
                "metadata": {"source": "SVS/WKO Steuerjahr 2025", "category": "social_insurance", "language": "de"}
            },
            {
                "text": "Social Insurance (SVS) for Self-Employed (tax year 2025, filed 2026): GSVG contributions include pension insurance (18.5%), health insurance (6.8%), accident insurance (€12.95/month fixed), and self-employed pension provisions (1.53%). Minimum contribution base: €551.10/month. Maximum contribution base: €8,085/month. Source: SVS/WKO.",
                "metadata": {"source": "SVS/WKO Steuerjahr 2025", "category": "social_insurance", "language": "en"}
            },
            {
                "text": "自雇人员社会保险(SVS)(税务年度2025，2026年申报)：GSVG缴费包括养老保险(18.5%)、医疗保险(6.8%)、事故保险(每月€12.95固定)和自雇养老金(1.53%)。最低缴费基数：每月€551.10。最高缴费基数：每月€8,085。来源：SVS/WKO。",
                "metadata": {"source": "SVS/WKO Steuerjahr 2025", "category": "social_insurance", "language": "zh"}
            },
            # --- ÖGK vs SVS: Employee vs Self-Employed Social Insurance ---
            {
                "text": (
                    "Sozialversicherung in Österreich – ÖGK vs SVS: "
                    "Arbeitnehmer sind bei der ÖGK (Österreichische Gesundheitskasse) pflichtversichert. "
                    "Der Arbeitgeber meldet den Arbeitnehmer an und beide zahlen Beiträge: "
                    "Pensionsversicherung (Arbeitnehmer 10,25%, Arbeitgeber 12,55%), "
                    "Krankenversicherung (Arbeitnehmer 3,87%, Arbeitgeber 3,78%), "
                    "Arbeitslosenversicherung (Arbeitnehmer 3%, Arbeitgeber 3%), "
                    "Unfallversicherung (Arbeitgeber 1,1%). "
                    "Die SVS (Sozialversicherung der Selbständigen) ist ausschließlich für Selbständige "
                    "(Gewerbetreibende, Neue Selbständige nach GSVG). "
                    "Einkünfte aus Vermietung und Verpachtung (§28 EStG) sind KEINE selbständige Tätigkeit "
                    "und unterliegen NICHT der SVS-Pflicht. Nur wenn die Vermietung gewerblich betrieben wird "
                    "(z.B. Airbnb-ähnlich mit umfangreichen Zusatzleistungen), kann SVS-Pflicht entstehen."
                ),
                "metadata": {"source": "ÖGK/SVS/ASVG/GSVG", "category": "social_insurance", "language": "de"}
            },
            {
                "text": (
                    "Social Insurance in Austria – ÖGK vs SVS: "
                    "Employees are compulsorily insured with ÖGK (Austrian Health Insurance Fund). "
                    "The employer registers the employee and both pay contributions: "
                    "pension insurance (employee 10.25%, employer 12.55%), "
                    "health insurance (employee 3.87%, employer 3.78%), "
                    "unemployment insurance (employee 3%, employer 3%), "
                    "accident insurance (employer 1.1%). "
                    "SVS (Social Insurance for Self-Employed) is exclusively for self-employed persons "
                    "(trade license holders, new self-employed under GSVG). "
                    "Rental income (Einkünfte aus Vermietung und Verpachtung, §28 EStG) is NOT self-employment "
                    "and is NOT subject to SVS contributions. Only if rental activity is conducted commercially "
                    "(e.g. Airbnb-like with extensive additional services) may SVS obligation arise."
                ),
                "metadata": {"source": "ÖGK/SVS/ASVG/GSVG", "category": "social_insurance", "language": "en"}
            },
            {
                "text": (
                    "奥地利社会保险 – ÖGK vs SVS 的区别："
                    "雇员在ÖGK（奥地利健康保险基金）强制参保，由雇主登记，双方共同缴费："
                    "养老保险（雇员10.25%，雇主12.55%），"
                    "医疗保险（雇员3.87%，雇主3.78%），"
                    "失业保险（雇员3%，雇主3%），"
                    "意外保险（雇主1.1%）。"
                    "SVS（自雇人员社会保险）专门针对自雇人员（持营业执照者、GSVG下的新自雇人员）。"
                    "出租收入（Einkünfte aus Vermietung und Verpachtung，§28 EStG）不属于自雇活动，"
                    "不需要缴纳SVS。只有当出租活动达到商业经营级别（如类似Airbnb提供大量附加服务）时，"
                    "才可能产生SVS义务。"
                ),
                "metadata": {"source": "ÖGK/SVS/ASVG/GSVG", "category": "social_insurance", "language": "zh"}
            },
            # --- Rental Income Tax Treatment ---
            {
                "text": (
                    "Einkünfte aus Vermietung und Verpachtung (§28 EStG): "
                    "Mieteinnahmen werden als eigene Einkunftsart besteuert, NICHT als Einkünfte aus "
                    "selbständiger Arbeit oder Gewerbebetrieb. Es fallen keine SVS-Beiträge an. "
                    "Absetzbare Kosten: AfA (Absetzung für Abnutzung, 1,5% des Gebäudewerts), "
                    "Betriebskosten, Instandhaltung, Verwaltungskosten, Kreditzinsen. "
                    "Wohnraumvermietung: 10% USt oder USt-Befreiung (Kleinunternehmerregelung). "
                    "Gewerbliche Vermietung (z.B. Büro): 20% USt. "
                    "Wer gleichzeitig Arbeitnehmer und Vermieter ist: Lohneinkünfte werden über ÖGK "
                    "sozialversichert (Arbeitgeber zahlt), Mieteinnahmen unterliegen nur der Einkommensteuer."
                ),
                "metadata": {"source": "EStG §28", "category": "rental_income", "language": "de"}
            },
            {
                "text": (
                    "Rental Income (Einkünfte aus Vermietung und Verpachtung, §28 EStG): "
                    "Rental income is taxed as its own income category, NOT as self-employment or trade income. "
                    "No SVS contributions apply. "
                    "Deductible costs: depreciation (AfA, 1.5% of building value), "
                    "operating costs, maintenance, management costs, loan interest. "
                    "Residential rental: 10% VAT or VAT exemption (small business rule). "
                    "Commercial rental (e.g. office): 20% VAT. "
                    "If you are both an employee and a landlord: salary income is socially insured via ÖGK "
                    "(employer pays), rental income is subject only to income tax."
                ),
                "metadata": {"source": "EStG §28", "category": "rental_income", "language": "en"}
            },
            {
                "text": (
                    "出租收入（Einkünfte aus Vermietung und Verpachtung，§28 EStG）："
                    "租金收入作为独立的收入类别征税，不属于自雇收入或营业收入，不需要缴纳SVS社保。"
                    "可抵扣费用：折旧（AfA，建筑价值的1.5%）、运营成本、维修费、管理费、贷款利息。"
                    "住宅出租：10%增值税或免征增值税（小企业规则）。"
                    "商业出租（如办公室）：20%增值税。"
                    "如果您同时是雇员和房东：工资收入通过ÖGK参保（雇主缴纳），"
                    "租金收入仅需缴纳所得税，无需额外社保。"
                ),
                "metadata": {"source": "EStG §28", "category": "rental_income", "language": "zh"}
            },
            {
                "text": "Pendlerpauschale (Commuting Allowance): Kleines Pendlerpauschale (öffentliche Verkehrsmittel verfügbar): 20-40km €58/Monat, 40-60km €113/Monat, 60km+ €168/Monat. Großes Pendlerpauschale (keine öffentlichen Verkehrsmittel): 2-20km €31/Monat, 20-40km €123/Monat, 40-60km €214/Monat, 60km+ €306/Monat. Zusätzlich: Pendlereuro €6/km/Jahr.",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "de"}
            },
            {
                "text": "Commuting Allowance (Pendlerpauschale): Small allowance (public transport available): 20-40km €58/month, 40-60km €113/month, 60km+ €168/month. Large allowance (no public transport): 2-20km €31/month, 20-40km €123/month, 40-60km €214/month, 60km+ €306/month. Additionally: Pendlereuro €6/km/year.",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "en"}
            },
            {
                "text": "通勤补贴(Pendlerpauschale)：小通勤补贴(有公共交通)：20-40公里每月€58，40-60公里每月€113，60公里以上每月€168。大通勤补贴(无公共交通)：2-20公里每月€31，20-40公里每月€123，40-60公里每月€214，60公里以上每月€306。另外：Pendlereuro每公里每年€6。",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "zh"}
            },
            {
                "text": "Kinderabsetzbetrag (Child Tax Credit): €58,40 pro Monat pro Kind (€700,80 pro Jahr). Alleinerzieherabsetzbetrag (Single Parent Credit): €494 pro Jahr zusätzlich.",
                "metadata": {"source": "Austrian Tax Law", "category": "family_deductions", "language": "de"}
            },
            {
                "text": "Child Tax Credit (Kinderabsetzbetrag): €58.40 per month per child (€700.80 per year). Single Parent Credit (Alleinerzieherabsetzbetrag): €494 per year additional.",
                "metadata": {"source": "Austrian Tax Law", "category": "family_deductions", "language": "en"}
            },
            {
                "text": "子女扣除(Kinderabsetzbetrag)：每个孩子每月€58.40(每年€700.80)。单亲扣除(Alleinerzieherabsetzbetrag)：每年额外€494。",
                "metadata": {"source": "Austrian Tax Law", "category": "family_deductions", "language": "zh"}
            },
            {
                "text": "Home Office Deduction: Pauschalabzug von €300 pro Jahr für Homeoffice-Kosten ohne Nachweis.",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "de"}
            },
            {
                "text": "Home Office Deduction: Flat-rate deduction of €300 per year for home office costs without proof.",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "en"}
            },
            {
                "text": "家庭办公室扣除：每年€300的固定扣除，无需证明。",
                "metadata": {"source": "Austrian Tax Law", "category": "deductions", "language": "zh"}
            },
            {
                "text": "Verlustvortrag (Loss Carryforward): Verluste aus Vorjahren können unbegrenzt in die Zukunft vorgetragen werden und mindern das zu versteuernde Einkommen.",
                "metadata": {"source": "Austrian Tax Law", "category": "loss_carryforward", "language": "de"}
            },
            {
                "text": "Loss Carryforward (Verlustvortrag): Losses from previous years can be carried forward indefinitely and reduce taxable income.",
                "metadata": {"source": "Austrian Tax Law", "category": "loss_carryforward", "language": "en"}
            },
            {
                "text": "亏损结转(Verlustvortrag)：前几年的亏损可以无限期结转，并减少应税收入。",
                "metadata": {"source": "Austrian Tax Law", "category": "loss_carryforward", "language": "zh"}
            },
            {
                "text": "Basispauschalierung (Grundpauschalierung) 2025+: Selbständige mit einem Jahresumsatz bis €320.000 können pauschalierte Betriebsausgaben geltend machen: 13,5% des Umsatzes (allgemein) oder 6% für bestimmte Tätigkeiten (z.B. Vortragende, Schriftsteller). Zusätzlich: Grundfreibetrag 15% des Gewinns, max. €4.950. Gewinngrenze: €33.000.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "flat_rate", "language": "de"}
            },
            {
                "text": "Basic Flat-Rate Expenses (Basispauschalierung) 2025+: Self-employed with annual turnover up to €320,000 can claim flat-rate business expenses: 13.5% of turnover (general) or 6% for specific activities (e.g. lecturers, writers). Additionally: basic profit exemption of 15%, max €4,950. Profit limit: €33,000.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "flat_rate", "language": "en"}
            },
            {
                "text": "基本定额扣除(Basispauschalierung) 2025+：年营业额不超过€320,000的自雇人员可申请定额业务费用扣除：营业额的13.5%(一般)或6%(特定活动，如讲师、作家)。另外：基本利润免税额为利润的15%，最高€4,950。利润上限：€33,000。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "flat_rate", "language": "zh"}
            },
            # --- Werbungskostenpauschale (Employee Standard Deduction) ---
            {
                "text": "Werbungskostenpauschale (Arbeitnehmer-Pauschbetrag): Alle Arbeitnehmer erhalten automatisch einen Pauschbetrag von €132 pro Jahr für Werbungskosten. Dieser wird vom Einkommen abgezogen, sofern die tatsächlichen Werbungskosten diesen Betrag nicht übersteigen.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "de"}
            },
            {
                "text": "Employee Standard Deduction (Werbungskostenpauschale): All employees automatically receive a flat-rate deduction of €132 per year for work-related expenses. This is deducted from income unless actual work-related expenses exceed this amount.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "en"}
            },
            {
                "text": "雇员标准扣除(Werbungskostenpauschale)：所有雇员自动获得每年€132的工作相关费用定额扣除。此金额从收入中扣除，除非实际工作相关费用超过此金额。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "zh"}
            },
            # --- Verkehrsabsetzbetrag (Traffic Tax Credit) ---
            {
                "text": "Verkehrsabsetzbetrag: Alle Arbeitnehmer erhalten automatisch einen Verkehrsabsetzbetrag von €463 pro Jahr. Dieser wird direkt von der Steuerschuld abgezogen (Absetzbetrag, nicht vom Einkommen).",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "de"}
            },
            {
                "text": "Traffic Tax Credit (Verkehrsabsetzbetrag): All employees automatically receive a traffic tax credit of €463 per year. This is deducted directly from tax liability (tax credit, not from income).",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "en"}
            },
            {
                "text": "交通税收抵免(Verkehrsabsetzbetrag)：所有雇员自动获得每年€463的交通税收抵免。此金额直接从应纳税额中扣除（税收抵免，非从收入中扣除）。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "employee_deductions", "language": "zh"}
            },
            # --- Familienbonus Plus ---
            {
                "text": "Familienbonus Plus: Steuerabsetzbetrag für Familien mit Kindern. €2.000 pro Jahr für jedes Kind unter 18 Jahren, €700 pro Jahr für jedes Kind zwischen 18 und 24 Jahren (in Ausbildung). Wird direkt von der Steuerschuld abgezogen.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "de"}
            },
            {
                "text": "Familienbonus Plus: Tax credit for families with children. €2,000 per year for each child under 18, €700 per year for each child aged 18-24 (in education). Deducted directly from tax liability.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "en"}
            },
            {
                "text": "家庭奖金Plus(Familienbonus Plus)：家庭子女税收抵免。18岁以下每个孩子每年€2,000，18至24岁（在读）每个孩子每年€700。直接从应纳税额中扣除。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "zh"}
            },
            # --- Alleinverdienerabsetzbetrag / Alleinerzieherabsetzbetrag ---
            {
                "text": "Alleinverdienerabsetzbetrag / Alleinerzieherabsetzbetrag: Steuerabsetzbetrag für Alleinverdiener oder Alleinerziehende mit mindestens einem Kind. Grundbetrag: €520 pro Jahr. Zusätzlich: €704 pro Jahr für jedes weitere Kind ab dem zweiten. Wird direkt von der Steuerschuld abgezogen.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "de"}
            },
            {
                "text": "Sole Earner / Single Parent Tax Credit (Alleinverdiener-/Alleinerzieherabsetzbetrag): Tax credit for sole earners or single parents with at least one child. Base amount: €520 per year. Additional: €704 per year for each child beyond the first. Deducted directly from tax liability.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "en"}
            },
            {
                "text": "单收入者/单亲税收抵免(Alleinverdiener-/Alleinerzieherabsetzbetrag)：适用于至少有一个孩子的单收入者或单亲家庭。基础金额：每年€520。额外：从第二个孩子起每个孩子每年€704。直接从应纳税额中扣除。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "family_deductions", "language": "zh"}
            },
            # --- Grundfreibetrag (Basic Profit Exemption for Self-Employed) ---
            {
                "text": "Grundfreibetrag (Gewinnfreibetrag): Selbständige können einen Grundfreibetrag von 15% des Gewinns, maximal €4.950 pro Jahr, geltend machen. Dieser wird automatisch bei der Einkommensteuerberechnung berücksichtigt und reduziert das zu versteuernde Einkommen.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "self_employed_deductions", "language": "de"}
            },
            {
                "text": "Basic Profit Exemption (Grundfreibetrag): Self-employed persons can claim a basic profit exemption of 15% of profit, up to a maximum of €4,950 per year. This is automatically applied in income tax calculation and reduces taxable income.",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "self_employed_deductions", "language": "en"}
            },
            {
                "text": "基本利润免税额(Grundfreibetrag)：自雇人员可申请利润的15%作为基本免税额，每年最高€4,950。此金额在所得税计算中自动应用，减少应税收入。",
                "metadata": {"source": "BMF Steuerbuch 2026", "category": "self_employed_deductions", "language": "zh"}
            },
            # --- Short-term Rental / Airbnb Classification ---
            {
                "text": (
                    "Kurzfristige Vermietung (Airbnb, Ferienwohnung) – Einkommensteuer und USt: "
                    "1) Einkommensteuer-Klassifizierung: Wenn der Vermieter hotel-ähnliche Leistungen erbringt "
                    "(Reinigung, Bettwäsche, Frühstück, Check-in-Service, Gästebetreuung), handelt es sich um "
                    "§23 EStG Gewerbebetrieb. Ohne solche Zusatzleistungen (nur Schlüsselübergabe + Wohnung) "
                    "= §28 EStG Vermietung und Verpachtung. "
                    "2) Umsatzsteuer: Kurzfristige Beherbergung unterliegt IMMER 10% USt "
                    "(§10 Abs 2 Z 4 UStG – Beherbergung in eingerichteten Wohn- und Schlafräumen), "
                    "unabhängig davon ob es als §23 oder §28 klassifiziert wird. "
                    "NICHT 20% und NICHT 13%. "
                    "3) Kleinunternehmerregelung: Bei Jahresumsatz ≤ €55.000 netto entfällt die USt-Pflicht "
                    "(§6 Abs 1 Z 27 UStG, seit 2025 von €35.000 angehoben). "
                    "4) SVS: Nur bei §23 Gewerbebetrieb fallen SVS-Beiträge an. Bei §28 Vermietung keine SVS."
                ),
                "metadata": {"source": "EStG §23/§28, UStG §10 Abs 2 Z 4", "category": "rental_vat", "language": "de"}
            },
            {
                "text": (
                    "Short-term rental (Airbnb, holiday apartment) – Income tax and VAT classification: "
                    "1) Income tax: If the landlord provides hotel-like services (cleaning, linens, breakfast, "
                    "check-in service, guest care) = §23 EStG Gewerbebetrieb (trade/business). "
                    "Without such services (just keys + apartment) = §28 EStG Vermietung (rental). "
                    "2) VAT: Short-term accommodation is ALWAYS subject to 10% VAT "
                    "(§10 Abs 2 Z 4 UStG – accommodation in furnished rooms), "
                    "regardless of whether classified as §23 or §28. NOT 20% and NOT 13%. "
                    "3) Kleinunternehmerregelung: Annual turnover ≤ €55,000 net = VAT exempt "
                    "(§6 Abs 1 Z 27 UStG, raised from €35,000 since 2025). "
                    "4) SVS: Only §23 Gewerbebetrieb triggers SVS contributions. §28 rental = no SVS."
                ),
                "metadata": {"source": "EStG §23/§28, UStG §10 Abs 2 Z 4", "category": "rental_vat", "language": "en"}
            },
            {
                "text": (
                    "短期出租（Airbnb、度假公寓）— 所得税和增值税分类规则："
                    "1) 所得税分类：如果房东提供酒店式服务（清洁、床上用品、早餐、入住服务、客人接待），"
                    "属于§23 EStG 营业收入(Gewerbebetrieb)。"
                    "如果没有这些附加服务（只是交钥匙+公寓），属于§28 EStG 出租收入(Vermietung)。"
                    "2) 增值税：短期住宿始终适用10%增值税"
                    "（§10 Abs 2 Z 4 UStG — 配备家具的住宿房间），"
                    "无论所得税分类为§23还是§28。不是20%，也不是13%。"
                    "3) 小企业规则：年净营业额≤€55,000可免征增值税（§6 Abs 1 Z 27 UStG，2025年起从€35,000提高）。"
                    "4) SVS社保：只有§23营业收入需要缴纳SVS。§28出租收入不需要SVS。"
                ),
                "metadata": {"source": "EStG §23/§28, UStG §10 Abs 2 Z 4", "category": "rental_vat", "language": "zh"}
            },
            # --- UStG VAT Rate Summary ---
            {
                "text": (
                    "Österreichische USt-Sätze Übersicht (UStG): "
                    "20% Normalsteuersatz (§10 Abs 1): Dienstleistungen, Waren, gewerbliche Vermietung. "
                    "10% Ermäßigter Satz (§10 Abs 2): Lebensmittel, Bücher, Zeitungen, Personenbeförderung, "
                    "Wohnraumvermietung, Beherbergung (Hotels, Airbnb, Ferienwohnungen), Medikamente. "
                    "13% Besonderer Satz (§10 Abs 3): Kulturveranstaltungen, Tierhaltung, Blumen, "
                    "Jugendbeherbergung, Filmvorführungen. "
                    "0% Steuerbefreiung: Exporte, innergemeinschaftliche Lieferungen, "
                    "Kleinunternehmer (§6 Abs 1 Z 27, Umsatz ≤ €55.000/Jahr, seit 2025)."
                ),
                "metadata": {"source": "UStG §10", "category": "vat_rates", "language": "de"}
            },
            {
                "text": (
                    "Austrian VAT rates overview (UStG): "
                    "20% Standard rate (§10 Abs 1): Services, goods, commercial rental. "
                    "10% Reduced rate (§10 Abs 2): Food, books, newspapers, passenger transport, "
                    "residential rental, accommodation (hotels, Airbnb, holiday apartments), medicine. "
                    "13% Special rate (§10 Abs 3): Cultural events, animal husbandry, flowers, "
                    "youth hostels, film screenings. "
                    "0% Exempt: Exports, intra-community supplies, "
                    "small businesses (§6 Abs 1 Z 27, turnover ≤ €55,000/year since 2025)."
                ),
                "metadata": {"source": "UStG §10", "category": "vat_rates", "language": "en"}
            },
            {
                "text": (
                    "奥地利增值税税率总览(UStG)："
                    "20%标准税率(§10 Abs 1)：服务、商品、商业出租。"
                    "10%优惠税率(§10 Abs 2)：食品、书籍、报纸、客运、"
                    "住宅出租、住宿服务（酒店、Airbnb、度假公寓）、药品。"
                    "13%特殊税率(§10 Abs 3)：文化活动、畜牧业、花卉、青年旅舍、电影放映。"
                    "0%免税：出口、欧盟内部供应、"
                    "小企业（§6 Abs 1 Z 27，年营业额≤€55,000，2025年起）。"
                ),
                "metadata": {"source": "UStG §10", "category": "vat_rates", "language": "zh"}
            },
            # --- Einkunftsarten (7 Income Types) ---
            {
                "text": (
                    "Die 7 Einkunftsarten nach §2 EStG: "
                    "1. §21 Land- und Forstwirtschaft: Einkünfte aus land-/forstwirtschaftlichem Betrieb. "
                    "2. §22 Selbständige Arbeit: Freiberufler (Ärzte, Anwälte, Künstler, Wissenschaftler). "
                    "3. §23 Gewerbebetrieb: Gewerbliche Tätigkeit mit Gewinnerzielungsabsicht. "
                    "Dazu gehört auch kurzfristige Vermietung MIT hotel-ähnlichen Zusatzleistungen. "
                    "4. §25 Nichtselbständige Arbeit: Arbeitnehmer, Pensionisten. "
                    "5. §27 Kapitalvermögen: Zinsen, Dividenden, Kursgewinne (KESt 27,5%). "
                    "6. §28 Vermietung und Verpachtung: Langfristige Vermietung, kurzfristige Vermietung "
                    "OHNE hotel-ähnliche Leistungen. Keine SVS-Pflicht. "
                    "7. §29 Sonstige Einkünfte: Spekulationsgewinne, gelegentliche Vermittlung."
                ),
                "metadata": {"source": "EStG §2", "category": "income_types", "language": "de"}
            },
            {
                "text": (
                    "The 7 income types under §2 EStG: "
                    "1. §21 Agriculture/Forestry: Income from agricultural/forestry operations. "
                    "2. §22 Self-employment: Freelancers (doctors, lawyers, artists, scientists). "
                    "3. §23 Trade/Business (Gewerbebetrieb): Commercial activity with profit intent. "
                    "Includes short-term rental WITH hotel-like additional services. "
                    "4. §25 Employment: Employees, pensioners. "
                    "5. §27 Capital gains: Interest, dividends, capital gains (KESt 27.5%). "
                    "6. §28 Rental income (Vermietung): Long-term rental, short-term rental "
                    "WITHOUT hotel-like services. No SVS obligation. "
                    "7. §29 Other income: Speculative gains, occasional brokerage."
                ),
                "metadata": {"source": "EStG §2", "category": "income_types", "language": "en"}
            },
            {
                "text": (
                    "奥地利所得税法(EStG)§2规定的7种收入类型："
                    "1. §21 农林业收入：来自农业/林业经营的收入。"
                    "2. §22 自由职业收入：自由职业者（医生、律师、艺术家、科学家）。"
                    "3. §23 营业收入(Gewerbebetrieb)：以盈利为目的的商业活动。"
                    "包括提供酒店式附加服务的短期出租。"
                    "4. §25 雇佣收入：雇员、退休人员。"
                    "5. §27 资本收入：利息、股息、资本利得（KESt 27.5%）。"
                    "6. §28 出租收入(Vermietung)：长期出租、不提供酒店式服务的短期出租。无SVS义务。"
                    "7. §29 其他收入：投机收益、偶尔的中介活动。"
                ),
                "metadata": {"source": "EStG §2", "category": "income_types", "language": "zh"}
            },
            # --- Pauschalierung (Flat-Rate Taxation) ---
            {
                "text": (
                    "Pauschalierung in Österreich (§17 EStG): "
                    "Basispauschalierung: Betriebsausgaben pauschal 12% des Umsatzes (max Gewinn €220.000) oder 6% für bestimmte Tätigkeiten (Beratung, Vorträge, Schriftstellerei). "
                    "Voraussetzung: keine Buchführungspflicht, Umsatz unter €220.000. "
                    "Branchenpauschalierung: spezielle Pauschalierungen für Gastwirte (10% oder 5,5%), Lebensmittelhändler (3,8%), Drogisten (3,8%), Künstler/Schriftsteller (12%). "
                    "Gewinnfreibetrag (§10 EStG): zusätzlich 15% des Gewinns bis €33.000 (max €4.950). "
                    "Vergleich: Basispauschalierung lohnt sich wenn tatsächliche Betriebsausgaben unter 12% (bzw. 6%) des Umsatzes liegen."
                ),
                "metadata": {"source": "EStG §17", "category": "flat_rate_taxation", "language": "de"}
            },
            {
                "text": (
                    "Flat-Rate Taxation in Austria (§17 EStG): "
                    "Basic flat-rate (Basispauschalierung): business expenses deducted at 12% of turnover (max profit €220,000) or 6% for certain activities (consulting, lectures, writing). "
                    "Requirement: no mandatory bookkeeping, turnover below €220,000. "
                    "Industry-specific flat rates (Branchenpauschalierung): restaurants (10% or 5.5%), food retailers (3.8%), pharmacists (3.8%), artists/writers (12%). "
                    "Profit allowance (Gewinnfreibetrag §10 EStG): additional 15% of profit up to €33,000 (max €4,950). "
                    "Comparison: flat-rate is beneficial when actual business expenses are below 12% (or 6%) of turnover."
                ),
                "metadata": {"source": "EStG §17", "category": "flat_rate_taxation", "language": "en"}
            },
            {
                "text": (
                    "奥地利固定比例征税(Pauschalierung，§17 EStG)："
                    "基础固定比例(Basispauschalierung)：按营业额的12%扣除经营费用（利润上限€220,000），特定活动（咨询、演讲、写作）按6%。"
                    "前提条件：无强制记账义务，营业额低于€220,000。"
                    "行业特定比例(Branchenpauschalierung)：餐饮业(10%或5.5%)、食品零售(3.8%)、药店(3.8%)、艺术家/作家(12%)。"
                    "利润免税额(Gewinnfreibetrag §10 EStG)：利润的15%（上限€33,000，最高€4,950）。"
                    "比较：当实际经营费用低于营业额的12%(或6%)时，固定比例更有利。"
                ),
                "metadata": {"source": "EStG §17", "category": "flat_rate_taxation", "language": "zh"}
            },
            # --- EA-Rechnung vs Doppelte Buchhaltung ---
            {
                "text": (
                    "Gewinnermittlungsarten in Österreich: "
                    "1. Einnahmen-Ausgaben-Rechnung (§4 Abs 3 EStG): Standard für Selbständige und Gewerbetreibende unter der Buchführungsgrenze. Einfaches Zufluss-Abfluss-Prinzip. "
                    "2. Doppelte Buchhaltung (§4 Abs 1, §5 EStG): Pflicht ab €700.000 Umsatz in 2 aufeinanderfolgenden Jahren ODER ab €1.000.000 in einem Jahr. "
                    "Freiwilliger Wechsel jederzeit möglich. Rückwechsel erst nach 5 Jahren. "
                    "3. Pauschalierung (§17 EStG): Vereinfachte Gewinnermittlung für kleinere Betriebe."
                ),
                "metadata": {"source": "EStG §4, §5, UGB §189", "category": "bookkeeping", "language": "de"}
            },
            {
                "text": (
                    "Profit determination methods in Austria: "
                    "1. Cash-basis accounting (Einnahmen-Ausgaben-Rechnung, §4 Abs 3 EStG): Standard for self-employed and businesses below the bookkeeping threshold. Simple cash-in/cash-out principle. "
                    "2. Double-entry bookkeeping (§4 Abs 1, §5 EStG): Mandatory when turnover exceeds €700,000 in 2 consecutive years OR €1,000,000 in a single year. "
                    "Voluntary switch possible anytime. Switch back only after 5 years. "
                    "3. Flat-rate taxation (§17 EStG): Simplified profit determination for smaller businesses."
                ),
                "metadata": {"source": "EStG §4, §5, UGB §189", "category": "bookkeeping", "language": "en"}
            },
            {
                "text": (
                    "奥地利利润确定方式："
                    "1. 收支记账法(Einnahmen-Ausgaben-Rechnung，§4 Abs 3 EStG)：低于记账门槛的个体户和商户的标准方式。简单的收付实现制。"
                    "2. 复式记账(§4 Abs 1, §5 EStG)：连续2年营业额超过€700,000 或 单年超过€1,000,000时强制。可自愿提前切换，但切回至少等5年。"
                    "3. 固定比例征税(§17 EStG)：小型企业的简化利润确定方式。"
                ),
                "metadata": {"source": "EStG §4, §5, UGB §189", "category": "bookkeeping", "language": "zh"}
            },
            # --- GmbH Corporate Tax ---
            {
                "text": (
                    "GmbH-Besteuerung in Österreich (KStG): "
                    "Körperschaftsteuer (KöSt): 23% flat rate (seit 2024, davor 25% bis 2022, 24% in 2023). "
                    "Mindest-KöSt: seit 2024 €500/Jahr (GmbH, erste 10 Jahre); danach €1.750/Jahr; AG €3.500/Jahr (auch bei Verlust). "
                    "Gewinnausschüttung: Neben KöSt fällt 27,5% KESt auf ausgeschüttete Dividenden an. "
                    "Gesamtbelastung bei Ausschüttung: 23% KöSt + 27,5% KESt auf Rest = ca. 44,2% effektiv. "
                    "Geschäftsführerbezüge: Gesellschafter-Geschäftsführer mit >25% Beteiligung: GSVG-pflichtig, keine Lohnsteuer sondern EStG. "
                    "Unter 25%: wie Angestellter (Lohnsteuer, ÖGK)."
                ),
                "metadata": {"source": "KStG, EStG §22 Z 2", "category": "corporate_tax", "language": "de"}
            },
            {
                "text": (
                    "GmbH Taxation in Austria (KStG): "
                    "Corporate income tax (KöSt): 23% flat rate (since 2024, previously 25% until 2022, 24% in 2023). "
                    "Minimum KöSt: €500/quarter = €2,000/year (even with losses). "
                    "Dividend distribution: In addition to KöSt, 27.5% KESt on distributed dividends. "
                    "Total effective tax on distribution: 23% KöSt + 27.5% KESt on remainder ≈ 44.2%. "
                    "Managing director compensation: Shareholder-directors with >25% ownership: GSVG-insured, income tax (not payroll). "
                    "Below 25%: treated as employee (payroll tax, ÖGK)."
                ),
                "metadata": {"source": "KStG, EStG §22 Z 2", "category": "corporate_tax", "language": "en"}
            },
            {
                "text": (
                    "奥地利GmbH税务(KStG)："
                    "公司所得税(KöSt)：统一23%（2024年起，2022年前25%，2023年24%）。"
                    "最低KöSt：每季度€500 = 每年€2,000（即使亏损也需缴纳）。"
                    "利润分配：除KöSt外，分配的股息还需缴纳27.5% KESt。"
                    "分配总有效税率：23% KöSt + 剩余部分27.5% KESt ≈ 44.2%。"
                    "总经理薪酬：持股>25%的股东-总经理：GSVG社保，按个人所得税（非工资税）。"
                    "持股<25%：按雇员处理（工资税，ÖGK社保）。"
                ),
                "metadata": {"source": "KStG, EStG §22 Z 2", "category": "corporate_tax", "language": "zh"}
            },
            # --- Crypto Taxation ---
            {
                "text": (
                    "Kryptowährungsbesteuerung in Österreich (seit 2022): "
                    "Einkünfte aus Kryptowährungen unterliegen der KESt von 27,5% (§27a EStG). "
                    "Steuerpflichtig: Verkauf, Tausch Krypto→Krypto, Tausch gegen Waren/Dienstleistungen. "
                    "Mining: Einkünfte aus sonstigen Leistungen (§29 EStG) bis zur ersten Veräußerung, danach §27. "
                    "Staking/Lending: Zinserträge → 27,5% KESt. "
                    "Airdrops: steuerpflichtig als Einkünfte bei Zufluss. "
                    "Altbestand (vor 01.03.2021): steuerfrei bei Haltedauer >1 Jahr (alte Regelung). "
                    "Neubestand (ab 01.03.2021): keine Spekulationsfrist mehr, immer 27,5% KESt."
                ),
                "metadata": {"source": "EStG §27a, ÖkoStRefG 2022", "category": "crypto_tax", "language": "de"}
            },
            {
                "text": (
                    "Cryptocurrency Taxation in Austria (since 2022): "
                    "Crypto income is subject to 27.5% KESt capital gains tax (§27a EStG). "
                    "Taxable events: sale, crypto-to-crypto exchange, exchange for goods/services. "
                    "Mining: other income (§29 EStG) until first disposal, then §27. "
                    "Staking/Lending: interest income → 27.5% KESt. "
                    "Airdrops: taxable as income upon receipt. "
                    "Old holdings (before 01.03.2021): tax-free if held >1 year (old rule). "
                    "New holdings (from 01.03.2021): no speculation period, always 27.5% KESt."
                ),
                "metadata": {"source": "EStG §27a, ÖkoStRefG 2022", "category": "crypto_tax", "language": "en"}
            },
            {
                "text": (
                    "奥地利加密货币税务（2022年起）："
                    "加密货币收入适用27.5% KESt资本利得税（§27a EStG）。"
                    "应税事项：出售、加密货币间交换、用加密货币购买商品/服务。"
                    "挖矿(Mining)：首次出售前为其他收入(§29 EStG)，之后为§27。"
                    "质押/借贷(Staking/Lending)：利息收入 → 27.5% KESt。"
                    "空投(Airdrops)：收到时作为收入征税。"
                    "旧持仓（2021.03.01前）：持有超过1年免税（旧规则）。"
                    "新持仓（2021.03.01起）：无投机期限，始终27.5% KESt。"
                ),
                "metadata": {"source": "EStG §27a, ÖkoStRefG 2022", "category": "crypto_tax", "language": "zh"}
            },
            # --- Tax Deadlines ---
            {
                "text": (
                    "Wichtige Steuertermine in Österreich: "
                    "E1 Einkommensteuererklärung: 30. April (Papier), 30. Juni (FinanzOnline). "
                    "Steuerberater-Frist: bis 31. März des Folgejahres (mit Quotenregelung). "
                    "Einkommensteuer-Vorauszahlungen: vierteljährlich am 15. Februar, 15. Mai, 15. August, 15. November. "
                    "UVA (Umsatzsteuervoranmeldung): monatlich bis zum 15. des Folgemonats (bei Umsatz >€100.000), vierteljährlich (bei Umsatz ≤€100.000). "
                    "Jahres-USt-Erklärung: bis 30. April (Papier) oder 30. Juni (FinanzOnline). "
                    "Lohnzettel (L16): bis Ende Februar des Folgejahres. "
                    "SVS-Beiträge: vierteljährlich (Februar, Mai, August, November)."
                ),
                "metadata": {"source": "BAO, EStG, UStG", "category": "tax_deadlines", "language": "de"}
            },
            {
                "text": (
                    "Important Tax Deadlines in Austria: "
                    "E1 Income tax return: April 30 (paper), June 30 (FinanzOnline). "
                    "Tax advisor deadline: March 31 of the following year (with quota system). "
                    "Income tax prepayments: quarterly on February 15, May 15, August 15, November 15. "
                    "UVA (VAT pre-filing): monthly by the 15th of following month (turnover >€100,000), quarterly (turnover ≤€100,000). "
                    "Annual VAT return: by April 30 (paper) or June 30 (FinanzOnline). "
                    "Payroll statements (L16): by end of February of following year. "
                    "SVS contributions: quarterly (February, May, August, November)."
                ),
                "metadata": {"source": "BAO, EStG, UStG", "category": "tax_deadlines", "language": "en"}
            },
            {
                "text": (
                    "奥地利重要税务截止日期："
                    "E1所得税申报：4月30日（纸质）、6月30日（FinanzOnline）。"
                    "税务师代理截止日：次年3月31日（配额制度）。"
                    "所得税预缴：季度缴纳，2月15日、5月15日、8月15日、11月15日。"
                    "UVA增值税预申报：月度截止次月15日（营业额>€100,000），季度（营业额≤€100,000）。"
                    "年度增值税申报：4月30日（纸质）或6月30日（FinanzOnline）。"
                    "工资报表(L16)：次年2月底前。"
                    "SVS社保缴费：季度（2月、5月、8月、11月）。"
                ),
                "metadata": {"source": "BAO, EStG, UStG", "category": "tax_deadlines", "language": "zh"}
            },
            # --- Loss Carryforward Rules ---
            {
                "text": (
                    "Verlustverrechnung und Verlustvortrag in Österreich (§18 Abs 6-7 EStG): "
                    "Verlustausgleich: Verluste aus einer Einkunftsart können mit positiven Einkünften anderer Einkunftsarten ausgeglichen werden. "
                    "Ausnahme: §27 Kapitalverluste nur mit §27 Kapitalgewinnen verrechenbar. "
                    "Verlustvortrag: Nicht ausgeglichene Verluste können zeitlich unbegrenzt vorgetragen werden. "
                    "Verrechnungsgrenze: Vorgetragene Verluste können nur bis zu 75% des Gesamtbetrags der Einkünfte abgezogen werden. "
                    "Mindesteinkommen: €2.000 bleiben immer steuerfrei (verbleibende 25%). "
                    "Sonderregel COVID: Rücktrag von 2020-Verlusten in 2019 und 2018 war möglich (befristet)."
                ),
                "metadata": {"source": "EStG §18 Abs 6-7", "category": "loss_carryforward", "language": "de"}
            },
            {
                "text": (
                    "Loss Offsetting and Carryforward in Austria (§18 Abs 6-7 EStG): "
                    "Loss offsetting: Losses from one income type can offset positive income from other types. "
                    "Exception: §27 capital losses can only offset §27 capital gains. "
                    "Loss carryforward: Unoffset losses can be carried forward indefinitely. "
                    "Offset limit: Carried-forward losses can only be deducted up to 75% of total income. "
                    "Minimum income: €2,000 always remains tax-free (remaining 25%). "
                    "COVID special rule: Carry-back of 2020 losses to 2019 and 2018 was possible (temporary)."
                ),
                "metadata": {"source": "EStG §18 Abs 6-7", "category": "loss_carryforward", "language": "en"}
            },
            {
                "text": (
                    "奥地利亏损抵扣和结转（§18 Abs 6-7 EStG）："
                    "亏损抵扣：一种收入类型的亏损可以与其他收入类型的正收入相抵。"
                    "例外：§27资本损失只能与§27资本收益抵扣。"
                    "亏损结转：未抵扣的亏损可以无限期向前结转。"
                    "抵扣上限：结转亏损最多只能抵扣总收入的75%。"
                    "最低收入：€2,000始终免税（剩余25%）。"
                    "COVID特殊规则：2020年亏损可以回溯到2019年和2018年（临时措施）。"
                ),
                "metadata": {"source": "EStG §18 Abs 6-7", "category": "loss_carryforward", "language": "zh"}
            },
            # --- Cross-Border Tax ---
            {
                "text": (
                    "Grenzüberschreitende Besteuerung in Österreich: "
                    "Doppelbesteuerungsabkommen (DBA): Österreich hat über 90 DBA. Grundregel: Wohnsitzland besteuert Welteinkommen, Quellenland besteuert nur lokale Einkünfte. "
                    "Reverse Charge (§19 UStG): Bei B2B-Dienstleistungen aus dem EU-Ausland schuldet der Empfänger die USt (Umkehr der Steuerschuldnerschaft). "
                    "Zusammenfassende Meldung (ZM): Bei EU-Lieferungen/Leistungen monatliche Meldung an das Finanzamt erforderlich. "
                    "Ausländische Einkünfte: In der E1-Erklärung anzugeben, Progressionsvorbehalt kann gelten."
                ),
                "metadata": {"source": "DBA, UStG §19", "category": "cross_border", "language": "de"}
            },
            {
                "text": (
                    "Cross-Border Taxation in Austria: "
                    "Double Taxation Agreements (DBA): Austria has over 90 DTAs. Basic rule: country of residence taxes worldwide income, source country taxes only local income. "
                    "Reverse Charge (§19 UStG): For B2B services from other EU countries, the recipient owes the VAT (reverse charge mechanism). "
                    "EU Summary Report (Zusammenfassende Meldung): Monthly report to tax office required for EU deliveries/services. "
                    "Foreign income: Must be declared in E1 return, progression clause may apply."
                ),
                "metadata": {"source": "DBA, UStG §19", "category": "cross_border", "language": "en"}
            },
            {
                "text": (
                    "奥地利跨境税务："
                    "双重征税协定(DBA)：奥地利有90多个DBA。基本规则：居住国对全球收入征税，来源国仅对本地收入征税。"
                    "逆向征收(Reverse Charge，§19 UStG)：从其他EU国家获得B2B服务时，接收方承担增值税。"
                    "EU汇总报告(Zusammenfassende Meldung)：EU交付/服务需每月向税务局报告。"
                    "外国收入：必须在E1申报中申报，可能适用累进保留条款。"
                ),
                "metadata": {"source": "DBA, UStG §19", "category": "cross_border", "language": "zh"}
            }
        ]
        
        # Add documents to vector database
        documents = [doc["text"] for doc in tax_law_docs]
        metadatas = [doc["metadata"] for doc in tax_law_docs]
        ids = [f"tax_law_{i}" for i in range(len(tax_law_docs))]
        
        self.vector_db.add_documents(
            collection_name="austrian_tax_law",
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def initialize_tax_tables(self):
        """Initialize 2026 USP tax tables"""
        
        tax_tables = [
            {
                "text": "2026 Einkommensteuertabelle: Stufe 1: €0-€13.539 (0%), Stufe 2: €13.539-€21.992 (20%), Stufe 3: €21.992-€36.458 (30%), Stufe 4: €36.458-€70.365 (40%), Stufe 5: €70.365-€104.859 (48%), Stufe 6: €104.859-€1.000.000 (50%), Stufe 7: über €1.000.000 (55%)",
                "metadata": {"year": 2026, "type": "income_tax_brackets", "language": "de"}
            },
            {
                "text": "2026 Income Tax Table: Bracket 1: €0-€13,539 (0%), Bracket 2: €13,539-€21,992 (20%), Bracket 3: €21,992-€36,458 (30%), Bracket 4: €36,458-€70,365 (40%), Bracket 5: €70,365-€104,859 (48%), Bracket 6: €104,859-€1,000,000 (50%), Bracket 7: above €1,000,000 (55%)",
                "metadata": {"year": 2026, "type": "income_tax_brackets", "language": "en"}
            },
            {
                "text": "2026年所得税表：第1档：€0-€13,539(0%)，第2档：€13,539-€21,992(20%)，第3档：€21,992-€36,458(30%)，第4档：€36,458-€70,365(40%)，第5档：€70,365-€104,859(48%)，第6档：€104,859-€1,000,000(50%)，第7档：€1,000,000以上(55%)",
                "metadata": {"year": 2026, "type": "income_tax_brackets", "language": "zh"}
            }
        ]
        
        documents = [doc["text"] for doc in tax_tables]
        metadatas = [doc["metadata"] for doc in tax_tables]
        ids = [f"tax_table_{i}" for i in range(len(tax_tables))]
        
        self.vector_db.add_documents(
            collection_name="usp_2026_tax_tables",
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def initialize_faq(self):
        """Initialize common tax questions and answers"""
        
        faqs = [
            {
                "text": "Q: Wie berechne ich meine Einkommensteuer? A: Die Einkommensteuer wird progressiv berechnet. Zuerst wird das zu versteuernde Einkommen ermittelt (Bruttoeinkommen minus Sozialversicherung und Sonderausgaben). Dann wird die Steuer nach den Steuerstufen berechnet.",
                "metadata": {"category": "income_tax", "language": "de"}
            },
            {
                "text": "Q: How do I calculate my income tax? A: Income tax is calculated progressively. First, taxable income is determined (gross income minus social insurance and special expenses). Then tax is calculated according to tax brackets.",
                "metadata": {"category": "income_tax", "language": "en"}
            },
            {
                "text": "Q: 如何计算我的所得税？A: 所得税采用累进计算。首先确定应税收入(总收入减去社会保险和特殊支出)。然后根据税级计算税款。",
                "metadata": {"category": "income_tax", "language": "zh"}
            },
            {
                "text": "Q: Welche Ausgaben kann ich als Selbständiger absetzen? A: Als Selbständiger können Sie Betriebsausgaben absetzen: Büromaterial, Ausrüstung, Reisekosten, Marketingkosten, professionelle Dienstleistungen, Versicherungen, und Homeoffice-Kosten.",
                "metadata": {"category": "deductions", "language": "de"}
            },
            {
                "text": "Q: What expenses can I deduct as self-employed? A: As self-employed, you can deduct business expenses: office supplies, equipment, travel costs, marketing costs, professional services, insurance, and home office costs.",
                "metadata": {"category": "deductions", "language": "en"}
            },
            {
                "text": "Q: 作为自雇人员我可以扣除哪些费用？A: 作为自雇人员，您可以扣除业务费用：办公用品、设备、差旅费、营销费用、专业服务、保险和家庭办公室费用。",
                "metadata": {"category": "deductions", "language": "zh"}
            },
            {
                "text": "Q: Muss ich als Kleinunternehmer Umsatzsteuer zahlen? A: Nein, wenn Ihr Jahresumsatz unter €55.000 netto liegt (seit 2025, davor €35.000), sind Sie von der Umsatzsteuer befreit (§6 Abs 1 Z 27 UStG). Toleranzgrenze: einmalig bis €60.500 (10%). Achtung: Kurzfristige Beherbergung (Airbnb, Ferienwohnung) unterliegt 10% USt (§10 Abs 2 Z 4 UStG), nicht 20%.",
                "metadata": {"category": "vat", "language": "de"}
            },
            {
                "text": "Q: Do I have to pay VAT as a small business? A: No, if your annual net turnover is below €55,000 (since 2025, previously €35,000), you are exempt from VAT (§6 Abs 1 Z 27 UStG). Tolerance: one-time up to €60,500 (10%). Note: Short-term accommodation (Airbnb, holiday apartment) is subject to 10% VAT (§10 Abs 2 Z 4 UStG), not 20%.",
                "metadata": {"category": "vat", "language": "en"}
            },
            {
                "text": "Q: 作为小企业我需要缴纳增值税吗？A: 不需要，如果您的年净营业额低于€55,000（2025年起，之前为€35,000），您可以免征增值税（§6 Abs 1 Z 27 UStG）。容忍限额：一次性可达€60,500（10%）。注意：短期住宿（Airbnb、度假公寓）适用10%增值税（§10 Abs 2 Z 4 UStG），不是20%。",
                "metadata": {"category": "vat", "language": "zh"}
            }
        ]
        
        documents = [doc["text"] for doc in faqs]
        metadatas = [doc["metadata"] for doc in faqs]
        ids = [f"faq_{i}" for i in range(len(faqs))]
        
        self.vector_db.add_documents(
            collection_name="tax_faq",
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def initialize_all(self):
        """Initialize all knowledge base collections"""
        print("Initializing Austrian tax law documents...")
        self.initialize_tax_law_documents()
        
        print("Initializing 2026 USP tax tables...")
        self.initialize_tax_tables()
        
        print("Initializing FAQ...")
        self.initialize_faq()
        
        print("Knowledge base initialization complete!")
    
    def refresh_knowledge_base(self):
        """Refresh knowledge base (admin function)"""
        # Reset collections
        self.vector_db.reset_collection("austrian_tax_law")
        self.vector_db.reset_collection("usp_2026_tax_tables")
        self.vector_db.reset_collection("tax_faq")
        
        # Reinitialize
        self.initialize_all()


# Singleton instance
_knowledge_base_service = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Get singleton instance of KnowledgeBaseService"""
    global _knowledge_base_service
    if _knowledge_base_service is None:
        _knowledge_base_service = KnowledgeBaseService()
    return _knowledge_base_service
