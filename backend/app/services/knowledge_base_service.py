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
                "text": "Umsatzsteuer (VAT) in Österreich: Der Standardsatz beträgt 20%. Für Wohnraumvermietung gilt ein ermäßigter Satz von 10% oder Befreiung. Kleinunternehmer mit einem Jahresumsatz unter €55.000 sind von der Umsatzsteuer befreit. Bei Umsätzen zwischen €55.000 und €60.500 gilt die Toleranzregel.",
                "metadata": {"source": "Austrian Tax Law", "category": "vat", "language": "de"}
            },
            {
                "text": "Value Added Tax (VAT) in Austria: The standard rate is 20%. For residential rentals, a reduced rate of 10% or exemption applies. Small businesses with annual turnover below €55,000 are exempt from VAT. For turnover between €55,000 and €60,500, the tolerance rule applies.",
                "metadata": {"source": "Austrian Tax Law", "category": "vat", "language": "en"}
            },
            {
                "text": "奥地利增值税：标准税率为20%。住宅租赁适用10%的优惠税率或免税。年营业额低于€55,000的小企业免征增值税。营业额在€55,000至€60,500之间适用容忍规则。",
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
                "text": "Q: Muss ich als Kleinunternehmer Umsatzsteuer zahlen? A: Nein, wenn Ihr Jahresumsatz unter €55.000 liegt, sind Sie von der Umsatzsteuer befreit. Bei €55.000-€60.500 gilt die Toleranzregel (noch befreit, aber nächstes Jahr automatisch steuerpflichtig).",
                "metadata": {"category": "vat", "language": "de"}
            },
            {
                "text": "Q: Do I have to pay VAT as a small business? A: No, if your annual turnover is below €55,000, you are exempt from VAT. For €55,000-€60,500, the tolerance rule applies (still exempt, but automatically taxable next year).",
                "metadata": {"category": "vat", "language": "en"}
            },
            {
                "text": "Q: 作为小企业我需要缴纳增值税吗？A: 不需要，如果您的年营业额低于€55,000，您可以免征增值税。对于€55,000-€60,500，适用容忍规则(仍然免税，但明年自动纳税)。",
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
