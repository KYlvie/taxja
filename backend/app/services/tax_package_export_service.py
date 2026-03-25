"""Background-prepared tax package export service."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, Optional
from zipfile import ZIP_DEFLATED, ZipFile

import reportlab
import redis as sync_redis
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementLine,
    BankStatementLineStatus,
)
from app.models.document import Document, DocumentType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

EXPORT_URL_EXPIRY_SECONDS = 48 * 60 * 60
EXPORT_STATE_PREFIX = "tax_package_export"
EXPORT_STORAGE_PREFIX = "tax-package-exports"
PART_TARGET_BYTES = 300 * 1024 * 1024
MAX_TOTAL_BYTES = 1800 * 1024 * 1024
MAX_PARTS = 6
MAX_DOCUMENTS = 2000

CORE_DOCUMENT_TYPES = {
    DocumentType.RECEIPT.value,
    DocumentType.INVOICE.value,
    DocumentType.BANK_STATEMENT.value,
    DocumentType.KONTOAUSZUG.value,
    DocumentType.PAYSLIP.value,
    DocumentType.LOHNZETTEL.value,
    DocumentType.SVS_NOTICE.value,
    DocumentType.EINKOMMENSTEUERBESCHEID.value,
    DocumentType.E1_FORM.value,
    DocumentType.L1_FORM.value,
    DocumentType.L1K_BEILAGE.value,
    DocumentType.L1AB_BEILAGE.value,
    DocumentType.E1A_BEILAGE.value,
    DocumentType.E1B_BEILAGE.value,
    DocumentType.E1KV_BEILAGE.value,
    DocumentType.U1_FORM.value,
    DocumentType.U30_FORM.value,
    DocumentType.PROPERTY_TAX.value,
    DocumentType.VERSICHERUNGSBESTAETIGUNG.value,
    DocumentType.SPENDENBESTAETIGUNG.value,
    DocumentType.KINDERBETREUUNGSKOSTEN.value,
    DocumentType.FORTBILDUNGSKOSTEN.value,
    DocumentType.PENDLERPAUSCHALE.value,
    DocumentType.KIRCHENBEITRAG.value,
    DocumentType.BETRIEBSKOSTENABRECHNUNG.value,
    DocumentType.JAHRESABSCHLUSS.value,
}

FOUNDATION_DOCUMENT_TYPES = {
    DocumentType.RENTAL_CONTRACT.value,
    DocumentType.LOAN_CONTRACT.value,
    DocumentType.PURCHASE_CONTRACT.value,
    DocumentType.GRUNDBUCHAUSZUG.value,
    DocumentType.GEWERBESCHEIN.value,
}

FAMILY_DIRECTORY_BY_TYPE = {
    DocumentType.RECEIPT.value: "receipts-invoices",
    DocumentType.INVOICE.value: "receipts-invoices",
    DocumentType.BANK_STATEMENT.value: "bank-statements",
    DocumentType.KONTOAUSZUG.value: "bank-statements",
    DocumentType.E1_FORM.value: "tax-forms-and-assessments",
    DocumentType.L1_FORM.value: "tax-forms-and-assessments",
    DocumentType.L1K_BEILAGE.value: "tax-forms-and-assessments",
    DocumentType.L1AB_BEILAGE.value: "tax-forms-and-assessments",
    DocumentType.E1A_BEILAGE.value: "tax-forms-and-assessments",
    DocumentType.E1B_BEILAGE.value: "tax-forms-and-assessments",
    DocumentType.E1KV_BEILAGE.value: "tax-forms-and-assessments",
    DocumentType.U1_FORM.value: "tax-forms-and-assessments",
    DocumentType.U30_FORM.value: "tax-forms-and-assessments",
    DocumentType.EINKOMMENSTEUERBESCHEID.value: "tax-forms-and-assessments",
    DocumentType.PAYSLIP.value: "payroll-social-insurance",
    DocumentType.LOHNZETTEL.value: "payroll-social-insurance",
    DocumentType.SVS_NOTICE.value: "payroll-social-insurance",
    DocumentType.VERSICHERUNGSBESTAETIGUNG.value: "deductions-and-supporting-proof",
    DocumentType.SPENDENBESTAETIGUNG.value: "deductions-and-supporting-proof",
    DocumentType.KINDERBETREUUNGSKOSTEN.value: "deductions-and-supporting-proof",
    DocumentType.FORTBILDUNGSKOSTEN.value: "deductions-and-supporting-proof",
    DocumentType.PENDLERPAUSCHALE.value: "deductions-and-supporting-proof",
    DocumentType.KIRCHENBEITRAG.value: "deductions-and-supporting-proof",
    DocumentType.PROPERTY_TAX.value: "property-and-financial-docs",
    DocumentType.BETRIEBSKOSTENABRECHNUNG.value: "property-and-financial-docs",
    DocumentType.JAHRESABSCHLUSS.value: "property-and-financial-docs",
}

FAMILY_LABELS_BY_LANGUAGE = {
    "en": {
        "receipts-invoices": "Receipts & invoices",
        "bank-statements": "Bank statements",
        "tax-forms-and-assessments": "Tax forms & assessments",
        "payroll-social-insurance": "Payroll & social insurance",
        "deductions-and-supporting-proof": "Deductions & supporting proof",
        "property-and-financial-docs": "Property & financial documents",
        "foundation-materials": "Foundation materials",
        "other-linked": "Other linked documents",
    },
    "de": {
        "receipts-invoices": "Belege & Rechnungen",
        "bank-statements": "Kontoauszüge",
        "tax-forms-and-assessments": "Steuerformulare & Bescheide",
        "payroll-social-insurance": "Lohn & Sozialversicherung",
        "deductions-and-supporting-proof": "Abzüge & Nachweise",
        "property-and-financial-docs": "Immobilien- & Finanzdokumente",
        "foundation-materials": "Langfristige Grundlagendokumente",
        "other-linked": "Verknüpfte Sonstige Dokumente",
    },
    "zh": {
        "receipts-invoices": "收据与发票",
        "bank-statements": "银行对账单",
        "tax-forms-and-assessments": "税表与税务决定",
        "payroll-social-insurance": "工资与社保材料",
        "deductions-and-supporting-proof": "抵扣与证明材料",
        "property-and-financial-docs": "房产与财务文件",
        "foundation-materials": "长期基础材料",
        "other-linked": "已关联的其他文档",
    },
}

TRANSACTION_EXPORT_LABELS = {
    "en": {
        "title": "Transactions",
        "generated": "Generated",
        "date": "Date",
        "type": "Type",
        "amount": "Amount",
        "description": "Description",
        "category": "Category",
        "deductible": "Deductible",
        "linked_docs": "Linked docs",
        "yes": "Yes",
        "no": "No",
        "income": "Income",
        "expense": "Expense",
    },
    "de": {
        "title": "Transaktionen",
        "generated": "Erstellt",
        "date": "Datum",
        "type": "Typ",
        "amount": "Betrag",
        "description": "Beschreibung",
        "category": "Kategorie",
        "deductible": "Absetzbar",
        "linked_docs": "Verknüpfte Dokumente",
        "yes": "Ja",
        "no": "Nein",
        "income": "Einnahme",
        "expense": "Ausgabe",
    },
    "zh": {
        "title": "交易明细",
        "generated": "生成时间",
        "date": "日期",
        "type": "类型",
        "amount": "金额",
        "description": "描述",
        "category": "类别",
        "deductible": "可抵扣",
        "linked_docs": "关联文档数",
        "yes": "是",
        "no": "否",
        "income": "收入",
        "expense": "支出",
    },
}

SUMMARY_TEXT = {
    "en": {
        "title": "Tax package summary",
        "tax_year": "Tax year",
        "generated_at": "Generated at",
        "language": "Language",
        "parts": "Parts",
        "foundation": "Includes foundation materials",
        "yes": "Yes",
        "no": "No",
        "included_heading": "Included and excluded content",
        "included": "Included",
        "excluded": "Not included",
        "included_list": "Summary PDF, transactions CSV, transactions PDF, tax-related source documents",
        "excluded_list": "Other report PDFs remain available separately on the reports page",
        "year_rule": "Document year rule",
        "year_rule_text": "document_date first, then document_year, then uploaded_at",
        "other_rule": "Other documents rule",
        "other_rule_text": "Other-type documents are only included if they are linked to exported-year transactions.",
        "transactions_heading": "Annual transaction overview",
        "tx_count": "Transaction count",
        "income_total": "Income total",
        "expense_total": "Expense total",
        "deductible_total": "Deductible total",
        "reconciled_count": "Reconciled count",
            "pending_tx_count": "Pending review transactions",
        "ignored_count": "Ignored count",
        "documents_heading": "Annual document overview",
        "included_docs": "Included documents",
        "family_counts": "Counts by family",
        "excluded_docs": "Excluded documents",
        "risks_heading": "Risks and reminders",
            "pending_docs": "Pending review documents included in this package",
            "uncertain_year_docs": "Documents assigned to this tax year by uploaded date fallback",
            "skipped_files": "Files excluded from export",
        "no_risks": "No open risks were detected for this package.",
        "all_parts_notice": "Keep every downloaded part together if the package was split.",
        "usage_heading": "How to use this package",
        "usage_text": "This package includes the summary PDF, the annual transaction CSV, the annual transaction PDF, and tax-related source documents for the selected tax year. Other report PDFs are not included and should be downloaded separately from the reports page. Document year attribution uses document_date first, then document_year, and finally uploaded_at as a fallback. Other-type documents are only included when they are linked to exported transactions from the selected tax year.",
        "reason_year_mismatch": "Document assigned to a different tax year",
        "reason_foundation_opt_out": "Foundation materials not requested",
        "reason_other_unlinked": "Other document not linked to an exported transaction from this tax year",
        "reason_storage_missing": "Stored file missing or unreadable",
        "reason_unsupported": "Unsupported document type for the tax package",
        "reason_limit": "Package exceeds export limits",
    },
    "de": {
        "title": "Steuerpaket Zusammenfassung",
        "tax_year": "Steuerjahr",
        "generated_at": "Erstellt am",
        "language": "Sprache",
        "parts": "Teile",
        "foundation": "Grundlagenmaterial enthalten",
        "yes": "Ja",
        "no": "Nein",
        "included_heading": "Enthaltene und ausgeschlossene Inhalte",
        "included": "Enthalten",
        "excluded": "Nicht enthalten",
        "included_list": "Zusammenfassungs-PDF, Transaktionen-CSV, Transaktionen-PDF, steuerrelevante Quelldokumente",
        "excluded_list": "Andere Report-PDFs stehen weiterhin separat auf der Berichte-Seite zur Verfügung",
        "year_rule": "Regel für das Dokumentjahr",
        "year_rule_text": "Zuerst document_date, dann document_year, zuletzt uploaded_at",
        "other_rule": "Regel für Sonstige Dokumente",
        "other_rule_text": "Dokumente vom Typ Other werden nur aufgenommen, wenn sie mit exportierten Transaktionen des Jahres verknüpft sind.",
        "transactions_heading": "Jahresüberblick Transaktionen",
        "tx_count": "Anzahl Transaktionen",
        "income_total": "Summe Einnahmen",
        "expense_total": "Summe Ausgaben",
        "deductible_total": "Summe absetzbar",
        "reconciled_count": "Anzahl abgeglichen",
            "pending_tx_count": "Noch zu prüfende Transaktionen",
        "ignored_count": "Anzahl ignoriert",
        "documents_heading": "Jahresüberblick Dokumente",
        "included_docs": "Enthaltene Dokumente",
        "family_counts": "Anzahl nach Familie",
        "excluded_docs": "Ausgeschlossene Dokumente",
        "risks_heading": "Risiken und Hinweise",
            "pending_docs": "Noch zu prüfende Dokumente im Steuerpaket",
            "uncertain_year_docs": "Dokumente, die über das Upload-Datum diesem Jahr zugeordnet wurden",
            "skipped_files": "Nicht exportierte Dateien",
        "no_risks": "Aktuell wurden keine offenen Risiken fuer dieses Paket erkannt.",
        "all_parts_notice": "Wenn das Paket aufgeteilt wurde, bewahren Sie alle Teile zusammen auf.",
        "usage_heading": "Verwendung dieses Pakets",
        "usage_text": "Dieses Paket enthaelt die Zusammenfassungs-PDF, die Jahres-CSV der Transaktionen, die Jahres-PDF der Transaktionen und steuerrelevante Quelldokumente fuer das ausgewaehlte Steuerjahr. Andere Berichts-PDFs sind nicht enthalten und koennen bei Bedarf separat auf der Berichte-Seite heruntergeladen werden. Fuer die Jahreszuordnung gilt: zuerst document_date, dann document_year und zuletzt uploaded_at als Rueckfall. Dokumente vom Typ Sonstige werden nur aufgenommen, wenn sie mit exportierten Transaktionen aus dem ausgewaehlten Steuerjahr verknuepft sind.",
        "reason_year_mismatch": "Dokument wurde einem anderen Steuerjahr zugeordnet",
        "reason_foundation_opt_out": "Grundlagenmaterial wurde nicht angefordert",
        "reason_other_unlinked": "Sonstiges Dokument ohne Verknuepfung zu exportierten Jahres-Transaktionen",
        "reason_storage_missing": "Gespeicherte Datei fehlt oder ist nicht lesbar",
        "reason_unsupported": "Nicht unterstützter Dokumenttyp für das Steuerpaket",
        "reason_limit": "Paket überschreitet die Exportgrenzen",
    },
    "zh": {
        "title": "税务包摘要",
        "tax_year": "税务年度",
        "generated_at": "生成时间",
        "language": "语言",
        "parts": "分卷数",
        "foundation": "包含长期基础材料",
        "yes": "是",
        "no": "否",
        "included_heading": "包含与不包含的内容",
        "included": "包含",
        "excluded": "不包含",
        "included_list": "总结 PDF、交易 CSV、交易 PDF、当年税务相关原始文档",
        "excluded_list": "其他报表 PDF 仍需在报表页面单独下载",
        "year_rule": "文档年份规则",
        "year_rule_text": "优先 document_date，其次 document_year，最后 uploaded_at",
        "other_rule": "other 类型规则",
        "other_rule_text": "other 类型文档只有在与该年度导出交易关联时才会被纳入。",
        "transactions_heading": "年度交易总览",
        "tx_count": "交易总数",
        "income_total": "收入总额",
        "expense_total": "支出总额",
        "deductible_total": "可抵扣总额",
        "reconciled_count": "已对账数量",
        "pending_tx_count": "仍待审核的交易",
        "ignored_count": "已忽略数量",
        "documents_heading": "年度文档总览",
        "included_docs": "已纳入文档",
        "family_counts": "按文档家族统计",
        "excluded_docs": "未纳入文档",
        "risks_heading": "风险与提醒",
        "pending_docs": "仍待审核的文档（会纳入税务包）",
        "uncertain_year_docs": "按上传日期归入本年度的文档",
        "skipped_files": "未纳入导出的文件",
        "no_risks": "当前未发现需要优先处理的风险项。",
        "all_parts_notice": "如果税务包被分卷，请务必同时保存所有分卷。",
        "usage_heading": "使用说明",
        "usage_text": "本税务包包含总结 PDF、年度交易 CSV、年度交易 PDF，以及所选税务年度的税务相关原始文档。其他报表 PDF 不包含在此包内，请在报表页面单独下载。文档归年规则依次为：优先 document_date，其次 document_year，最后才回退到 uploaded_at。其他类型文档只有在与当前税年导出交易关联时才会被纳入。",
        "reason_year_mismatch": "文档归属年份不在当前税年",
        "reason_foundation_opt_out": "未勾选长期基础材料",
        "reason_other_unlinked": "其他类型文档未关联到当前税年导出交易",
        "reason_storage_missing": "存储中的文件缺失或无法读取",
        "reason_unsupported": "该文档类型不属于税务包默认范围",
        "reason_limit": "税务包超过导出限制",
    },
}


@dataclass
class TaxPackageDocumentEntry:
    document_id: int
    document_type: str
    family: str
    file_name: str
    file_path: str
    archive_name: str
    approx_size: int
    year_basis: str
    needs_review: bool


@dataclass
class TaxPackagePartArtifact:
    part_number: int
    file_name: str
    size_bytes: int
    payload: bytes
    storage_path: str


def _language_payload(language: str) -> dict[str, str]:
    normalized = (language or "en").split("-")[0].lower()
    if normalized == "de":
        return {
            "title": "Steuerpaket Zusammenfassung",
            "tax_year": "Steuerjahr",
            "generated_at": "Erstellt am",
            "language": "Sprache",
            "parts": "Teile",
            "foundation": "Grundlagenmaterial enthalten",
            "yes": "Ja",
            "no": "Nein",
            "included_heading": "Enthaltene und ausgeschlossene Inhalte",
            "included": "Enthalten",
            "excluded": "Nicht enthalten",
            "included_list": "Zusammenfassungs-PDF, Transaktionen-CSV, Transaktionen-PDF und steuerrelevante Quelldokumente",
            "excluded_list": "Andere Report-PDFs stehen weiterhin separat auf der Berichte-Seite zur Verfuegung",
            "year_rule": "Regel fuer das Dokumentjahr",
            "year_rule_text": "Zuerst document_date, dann document_year, zuletzt uploaded_at",
            "other_rule": "Regel fuer Sonstige Dokumente",
            "other_rule_text": "Dokumente vom Typ other werden nur aufgenommen, wenn sie mit exportierten Jahres-Transaktionen verknuepft sind.",
            "transactions_heading": "Jahresueberblick Transaktionen",
            "tx_count": "Anzahl Transaktionen",
            "income_total": "Summe Einnahmen",
            "expense_total": "Summe Ausgaben",
            "deductible_total": "Summe absetzbar",
            "reconciled_count": "Anzahl abgeglichen",
            "pending_tx_count": "Noch zu pruefende Transaktionen",
            "ignored_count": "Anzahl ignoriert",
            "documents_heading": "Jahresueberblick Dokumente",
            "included_docs": "Enthaltene Dokumente",
            "family_counts": "Anzahl nach Familie",
            "excluded_docs": "Ausgeschlossene Dokumente",
            "risks_heading": "Risiken und Hinweise",
            "pending_docs": "Noch zu pruefende Dokumente",
            "uncertain_year_docs": "Dokumente mit Jahr aus Upload-Datum zugeordnet",
            "skipped_files": "Nicht exportierte Dateien",
            "all_parts_notice": "Wenn das Paket aufgeteilt wurde, bewahren Sie alle Teile zusammen auf.",
            "usage_heading": "Verwendung dieses Pakets",
            "usage_text": "Dieses Paket enthaelt die Zusammenfassungs-PDF, die Jahres-CSV der Transaktionen, die Jahres-PDF der Transaktionen und steuerrelevante Quelldokumente fuer das ausgewaehlte Steuerjahr. Andere Berichts-PDFs sind nicht enthalten und koennen bei Bedarf separat auf der Berichte-Seite heruntergeladen werden. Fuer die Jahreszuordnung gilt: zuerst document_date, dann document_year und zuletzt uploaded_at als Rueckfall. Dokumente vom Typ Sonstige werden nur aufgenommen, wenn sie mit exportierten Transaktionen aus dem ausgewaehlten Steuerjahr verknuepft sind.",
            "reason_year_mismatch": "Dokument wurde einem anderen Steuerjahr zugeordnet",
            "reason_foundation_opt_out": "Grundlagenmaterial wurde nicht angefordert",
            "reason_other_unlinked": "Sonstiges Dokument ohne Verknuepfung zu exportierten Jahres-Transaktionen",
            "reason_storage_missing": "Gespeicherte Datei fehlt oder ist nicht lesbar",
            "reason_unsupported": "Nicht unterstuetzter Dokumenttyp fuer das Steuerpaket",
            "reason_limit": "Paket ueberschreitet die Exportgrenzen",
        }
    if normalized == "zh":
        return {
            "title": "税务包摘要",
            "tax_year": "税务年度",
            "generated_at": "生成时间",
            "language": "语言",
            "parts": "分卷数",
            "foundation": "包含长期基础材料",
            "yes": "是",
            "no": "否",
            "included_heading": "包含与不包含的内容",
            "included": "包含",
            "excluded": "不包含",
            "included_list": "总结 PDF、交易 CSV、交易 PDF、当年税务相关原始文档",
            "excluded_list": "其他报表 PDF 仍需在报表页面单独下载",
            "year_rule": "文档年份规则",
            "year_rule_text": "优先 document_date，其次 document_year，最后 uploaded_at",
            "other_rule": "other 类型规则",
            "other_rule_text": "other 类型文档只有在与该年度导出交易关联时才会被纳入。",
            "transactions_heading": "年度交易总览",
            "tx_count": "交易总数",
            "income_total": "收入总额",
            "expense_total": "支出总额",
            "deductible_total": "可抵扣总额",
            "reconciled_count": "已对账数量",
            "pending_tx_count": "仍待审核的交易",
            "ignored_count": "已忽略数量",
            "documents_heading": "年度文档总览",
            "included_docs": "已纳入文档",
            "family_counts": "按文档家族统计",
            "excluded_docs": "未纳入文档",
            "risks_heading": "风险与提醒",
            "pending_docs": "仍待审核的文档",
            "uncertain_year_docs": "按上传日期归入本年度的文档",
            "skipped_files": "未纳入导出的文件",
            "all_parts_notice": "如果税务包被分卷，请务必同时保存所有分卷。",
            "usage_heading": "使用说明",
            "usage_text": "本税务包包含总结 PDF、年度交易 CSV、年度交易 PDF，以及所选税务年度的税务相关原始文档。其他报表 PDF 不包含在此包内，请在报表页面单独下载。文档归年规则依次为：优先 document_date，其次 document_year，最后才回退到 uploaded_at。其他类型文档只有在与当前税年导出交易关联时才会被纳入。",
            "reason_year_mismatch": "文档归属年份不在当前税年",
            "reason_foundation_opt_out": "未勾选长期基础材料",
            "reason_other_unlinked": "其他类型文档未关联到当前税年导出交易",
            "reason_storage_missing": "存储中的文件缺失或无法读取",
            "reason_unsupported": "该文档类型不属于税务包默认范围",
            "reason_limit": "税务包超过导出限制",
        }
    if normalized in SUMMARY_TEXT:
        return SUMMARY_TEXT[normalized]
    return SUMMARY_TEXT["en"]


def _family_label(language: str, family: str) -> str:
    normalized = (language or "en").split("-")[0].lower()
    labels = FAMILY_LABELS_BY_LANGUAGE.get(normalized) or FAMILY_LABELS_BY_LANGUAGE["en"]
    return labels.get(family, family)


def _transaction_labels(language: str) -> dict[str, str]:
    normalized = (language or "en").split("-")[0].lower()
    if normalized == "de":
        return {
            "title": "Transaktionen",
            "generated": "Erstellt",
            "date": "Datum",
            "type": "Typ",
            "amount": "Betrag",
            "description": "Beschreibung",
            "category": "Kategorie",
            "deductible": "Absetzbar",
            "linked_docs": "Verknuepfte Dokumente",
            "yes": "Ja",
            "no": "Nein",
            "income": "Einnahme",
            "expense": "Ausgabe",
            "no_transactions": "Keine Transaktionen fuer das ausgewaehlte Jahr.",
        }
    if normalized == "zh":
        return {
            "title": "交易明细",
            "generated": "生成时间",
            "date": "日期",
            "type": "类型",
            "amount": "金额",
            "description": "描述",
            "category": "分类",
            "deductible": "可抵扣",
            "linked_docs": "关联文档数",
            "yes": "是",
            "no": "否",
            "income": "收入",
            "expense": "支出",
            "no_transactions": "该年度没有可导出的交易。",
        }
    if normalized in TRANSACTION_EXPORT_LABELS:
        labels = dict(TRANSACTION_EXPORT_LABELS[normalized])
        labels.setdefault("no_transactions", "No transactions for the selected year.")
        return labels
    labels = dict(TRANSACTION_EXPORT_LABELS["en"])
    labels.setdefault("no_transactions", "No transactions for the selected year.")
    return labels


def _language_payload(language: str) -> dict[str, str]:
    normalized = (language or "en").split("-")[0].lower()
    if normalized == "de":
        return {
            "title": "Steuerpaket Zusammenfassung",
            "tax_year": "Steuerjahr",
            "generated_at": "Erstellt am",
            "language": "Sprache",
            "parts": "Teile",
            "foundation": "Grundlagenmaterial enthalten",
            "yes": "Ja",
            "no": "Nein",
            "included_heading": "Enthaltene und ausgeschlossene Inhalte",
            "included": "Enthalten",
            "excluded": "Nicht enthalten",
            "included_list": "Zusammenfassungs-PDF, Transaktionen-CSV, Transaktionen-PDF und steuerrelevante Quelldokumente",
            "excluded_list": "Andere Report-PDFs stehen weiterhin separat auf der Berichte-Seite zur Verfuegung",
            "year_rule": "Regel fuer das Dokumentjahr",
            "year_rule_text": "Zuerst document_date, dann document_year, zuletzt uploaded_at",
            "other_rule": "Regel fuer Sonstige Dokumente",
            "other_rule_text": "Dokumente vom Typ other werden nur aufgenommen, wenn sie mit exportierten Jahres-Transaktionen verknuepft sind.",
            "transactions_heading": "Jahresueberblick Transaktionen",
            "tx_count": "Anzahl Transaktionen",
            "income_total": "Summe Einnahmen",
            "expense_total": "Summe Ausgaben",
            "deductible_total": "Summe absetzbar",
            "reconciled_count": "Anzahl abgeglichen",
            "pending_tx_count": "Noch zu pruefende Transaktionen",
            "ignored_count": "Anzahl ignoriert",
            "documents_heading": "Jahresueberblick Dokumente",
            "included_docs": "Enthaltene Dokumente",
            "family_counts": "Anzahl nach Familie",
            "excluded_docs": "Ausgeschlossene Dokumente",
            "risks_heading": "Risiken und Hinweise",
            "pending_docs": "Noch zu pruefende Dokumente im Steuerpaket",
            "uncertain_year_docs": "Dokumente, die ueber das Upload-Datum diesem Jahr zugeordnet wurden",
            "skipped_files": "Nicht exportierte Dateien",
            "no_risks": "Aktuell wurden keine offenen Risiken fuer dieses Paket erkannt.",
            "all_parts_notice": "Wenn das Paket aufgeteilt wurde, bewahren Sie alle Teile zusammen auf.",
            "usage_heading": "Verwendung dieses Pakets",
            "usage_text": "Dieses Paket enthaelt die Zusammenfassungs-PDF, die Jahres-CSV der Transaktionen, die Jahres-PDF der Transaktionen und steuerrelevante Quelldokumente fuer das ausgewaehlte Steuerjahr. Andere Berichts-PDFs sind nicht enthalten und koennen bei Bedarf separat auf der Berichte-Seite heruntergeladen werden. Fuer die Jahreszuordnung gilt: zuerst document_date, dann document_year und zuletzt uploaded_at als Rueckfall. Dokumente vom Typ Sonstige werden nur aufgenommen, wenn sie mit exportierten Transaktionen aus dem ausgewaehlten Steuerjahr verknuepft sind.",
            "reason_year_mismatch": "Dokument wurde einem anderen Steuerjahr zugeordnet",
            "reason_foundation_opt_out": "Grundlagenmaterial wurde nicht angefordert",
            "reason_other_unlinked": "Sonstiges Dokument ohne Verknuepfung zu exportierten Jahres-Transaktionen",
            "reason_storage_missing": "Gespeicherte Datei fehlt oder ist nicht lesbar",
            "reason_unsupported": "Nicht unterstuetzter Dokumenttyp fuer das Steuerpaket",
            "reason_limit": "Paket ueberschreitet die Exportgrenzen",
        }
    if normalized == "zh":
        return {
            "title": "税务包摘要",
            "tax_year": "税务年度",
            "generated_at": "生成时间",
            "language": "语言",
            "parts": "分卷数",
            "foundation": "包含长期基础材料",
            "yes": "是",
            "no": "否",
            "included_heading": "包含与不包含的内容",
            "included": "包含",
            "excluded": "不包含",
            "included_list": "总结 PDF、交易 CSV、交易 PDF、当年税务相关原始文档",
            "excluded_list": "其他报表 PDF 仍需在报表页面单独下载",
            "year_rule": "文档年份规则",
            "year_rule_text": "优先 document_date，其次 document_year，最后 uploaded_at",
            "other_rule": "other 类型规则",
            "other_rule_text": "other 类型文档只有在与该年度导出交易关联时才会被纳入。",
            "transactions_heading": "年度交易总览",
            "tx_count": "交易总数",
            "income_total": "收入总额",
            "expense_total": "支出总额",
            "deductible_total": "可抵扣总额",
            "reconciled_count": "已对账数量",
            "pending_tx_count": "仍待审核的交易",
            "ignored_count": "已忽略数量",
            "documents_heading": "年度文档总览",
            "included_docs": "已纳入文档",
            "family_counts": "按文档家族统计",
            "excluded_docs": "未纳入文档",
            "risks_heading": "风险与提醒",
            "pending_docs": "仍待审核的文档（会纳入税务包）",
            "uncertain_year_docs": "按上传日期归入本年度的文档",
            "skipped_files": "未纳入导出的文件",
            "no_risks": "当前未发现需要优先处理的风险项。",
            "all_parts_notice": "如果税务包被分卷，请务必同时保存所有分卷。",
            "usage_heading": "使用说明",
            "usage_text": "本税务包包含总结 PDF、年度交易 CSV、年度交易 PDF，以及所选税务年度的税务相关原始文档。其他报表 PDF 不包含在此包内，请在报表页面单独下载。文档归年规则依次为：优先 document_date，其次 document_year，最后才回退到 uploaded_at。其他类型文档只有在与当前税年导出交易关联时才会被纳入。",
            "reason_year_mismatch": "文档归属年份不在当前税年",
            "reason_foundation_opt_out": "未勾选长期基础材料",
            "reason_other_unlinked": "其他类型文档未关联到当前税年导出交易",
            "reason_storage_missing": "存储中的文件缺失或无法读取",
            "reason_unsupported": "该文档类型不属于税务包默认范围",
            "reason_limit": "税务包超过导出限制",
        }
    if normalized in SUMMARY_TEXT:
        return SUMMARY_TEXT[normalized]
    payload = dict(SUMMARY_TEXT["en"])
    payload.setdefault("no_risks", "No open risks were detected for this package.")
    return payload


def _transaction_labels(language: str) -> dict[str, str]:
    normalized = (language or "en").split("-")[0].lower()
    if normalized == "de":
        return {
            "title": "Transaktionen",
            "generated": "Erstellt",
            "date": "Datum",
            "type": "Typ",
            "amount": "Betrag",
            "description": "Beschreibung",
            "category": "Kategorie",
            "deductible": "Absetzbar",
            "linked_docs": "Verknuepfte Dokumente",
            "yes": "Ja",
            "no": "Nein",
            "income": "Einnahme",
            "expense": "Ausgabe",
            "no_transactions": "Keine Transaktionen fuer das ausgewaehlte Jahr.",
        }
    if normalized == "zh":
        return {
            "title": "交易明细",
            "generated": "生成时间",
            "date": "日期",
            "type": "类型",
            "amount": "金额",
            "description": "描述",
            "category": "分类",
            "deductible": "可抵扣",
            "linked_docs": "关联文档数",
            "yes": "是",
            "no": "否",
            "income": "收入",
            "expense": "支出",
            "no_transactions": "该年度没有可导出的交易。",
        }
    if normalized in TRANSACTION_EXPORT_LABELS:
        labels = dict(TRANSACTION_EXPORT_LABELS[normalized])
        labels.setdefault("no_transactions", "No transactions for the selected year.")
        return labels
    labels = dict(TRANSACTION_EXPORT_LABELS["en"])
    labels.setdefault("no_transactions", "No transactions for the selected year.")
    return labels


def _redis_client() -> sync_redis.Redis:
    return sync_redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def _state_cache_key(export_id: str) -> str:
    return f"{EXPORT_STATE_PREFIX}:{export_id}"


def cache_tax_package_export_state(export_id: str, state: dict[str, Any]) -> None:
    try:
        client = _redis_client()
        client.setex(_state_cache_key(export_id), EXPORT_URL_EXPIRY_SECONDS, json.dumps(state, ensure_ascii=False))
        client.close()
    except Exception:
        logger.warning("Could not cache tax package export state for %s", export_id, exc_info=True)


def load_cached_tax_package_export_state(export_id: str) -> Optional[dict[str, Any]]:
    try:
        client = _redis_client()
        raw = client.get(_state_cache_key(export_id))
        client.close()
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Could not load cached tax package export state for %s", export_id, exc_info=True)
        return None


def delete_cached_tax_package_export_state(export_id: str) -> None:
    try:
        client = _redis_client()
        client.delete(_state_cache_key(export_id))
        client.close()
    except Exception:
        logger.warning("Could not delete cached tax package export state for %s", export_id, exc_info=True)


def sanitize_tax_package_export_state(state: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not state:
        return None
    sanitized = dict(state)
    sanitized.pop("storage_paths", None)
    sanitized.pop("user_id", None)
    return sanitized


class TaxPackageExportService:
    """Build and upload tax package archives."""

    def __init__(
        self,
        db: Session,
        user: User,
        tax_year: int,
        language: str = "de",
        include_foundation_materials: bool = False,
    ) -> None:
        self.db = db
        self.user = user
        self.tax_year = tax_year
        self.language = (language or getattr(user, "language", "de") or "de").split("-")[0].lower()
        self.include_foundation_materials = include_foundation_materials
        self.storage = StorageService()
        self._summary_text = _language_payload(self.language)

    def build_status_payload(self, export_id: str, status: str) -> dict[str, Any]:
        payload = {
            "export_id": export_id,
            "user_id": self.user.id,
            "status": status,
            "tax_year": self.tax_year,
            "language": self.language,
            "include_foundation_materials": self.include_foundation_materials,
            "expires_at": self._expires_at_iso(),
        }
        cache_tax_package_export_state(export_id, payload)
        return payload

    def build_preview(self) -> dict[str, Any]:
        transactions = self._get_transactions()
        document_collection = self._collect_document_entries(transactions)
        summary_stats = self._build_summary_stats(transactions, document_collection)

        warning_items = [
            {
                "key": "pending_tx_count",
                "label": self._summary_text["pending_tx_count"],
                "count": int(summary_stats["pending_tx_count"]),
            },
            {
                "key": "pending_docs",
                "label": self._summary_text["pending_docs"],
                "count": int(summary_stats["pending_document_count"]),
            },
            {
                "key": "uncertain_year_docs",
                "label": self._summary_text["uncertain_year_docs"],
                "count": int(summary_stats["uncertain_year_docs"]),
            },
            {
                "key": "skipped_files",
                "label": self._summary_text["skipped_files"],
                "count": len(summary_stats["skipped_files"]),
            },
        ]

        return {
            "tax_year": self.tax_year,
            "language": self.language,
            "include_foundation_materials": self.include_foundation_materials,
            "summary": summary_stats,
            "warnings": [item for item in warning_items if item["count"] > 0],
            "has_warnings": any(item["count"] > 0 for item in warning_items),
        }

    def export_to_storage(self, export_id: str) -> dict[str, Any]:
        prepared = self._build_prepared_package(export_id)
        if prepared["status"] != "ready":
            cache_tax_package_export_state(export_id, prepared)
            return prepared

        storage_paths: list[str] = []
        parts: list[dict[str, Any]] = []
        for artifact in prepared["artifacts"]:
            uploaded = self.storage.upload_file(
                artifact.payload,
                artifact.storage_path,
                content_type="application/zip",
            )
            if not uploaded:
                raise RuntimeError(f"Failed to upload tax package part {artifact.file_name}")
            download_url = self.storage.get_file_url(
                artifact.storage_path,
                expiration=EXPORT_URL_EXPIRY_SECONDS,
            )
            if not download_url:
                raise RuntimeError(f"Failed to create download URL for {artifact.file_name}")
            storage_paths.append(artifact.storage_path)
            parts.append(
                {
                    "part_number": artifact.part_number,
                    "file_name": artifact.file_name,
                    "download_url": download_url,
                    "size_bytes": artifact.size_bytes,
                }
            )

        result = {
            "export_id": export_id,
            "user_id": self.user.id,
            "status": "ready",
            "tax_year": self.tax_year,
            "language": self.language,
            "include_foundation_materials": self.include_foundation_materials,
            "expires_at": self._expires_at_iso(),
            "part_count": len(parts),
            "parts": parts,
            "summary": prepared["summary"],
            "storage_paths": storage_paths,
        }
        cache_tax_package_export_state(export_id, result)
        return result

    def _build_prepared_package(self, export_id: str) -> dict[str, Any]:
        transactions = self._get_transactions()
        linked_doc_counts = self._build_transaction_document_count_map(transactions)
        document_collection = self._collect_document_entries(transactions)

        summary_stats = self._build_summary_stats(transactions, document_collection)
        transaction_csv = self._build_transactions_csv(transactions)
        transaction_pdf = self._build_transactions_pdf(transactions, linked_doc_counts)

        fixed_part_one_estimate = len(transaction_csv) + len(transaction_pdf) + 100_000
        split_result = self._assign_document_parts(
            document_collection["included_entries"],
            fixed_part_one_estimate,
        )
        if split_result["failure"]:
            return {
                "export_id": export_id,
                "user_id": self.user.id,
                "status": "failed",
                "tax_year": self.tax_year,
                "language": self.language,
                "include_foundation_materials": self.include_foundation_materials,
                "expires_at": self._expires_at_iso(),
                "failure": split_result["failure"],
            }

        part_documents: list[list[TaxPackageDocumentEntry]] = split_result["parts"]
        summary_pdf = self._build_summary_pdf(
            summary_stats=summary_stats,
            part_count=len(part_documents),
        )

        artifacts: list[TaxPackagePartArtifact] = []
        actual_total_bytes = 0
        for index, entries in enumerate(part_documents, start=1):
            payload = self._build_zip_part(
                part_number=index,
                part_count=len(part_documents),
                entries=entries,
                summary_pdf=summary_pdf if index == 1 else None,
                transaction_csv=transaction_csv if index == 1 else None,
                transaction_pdf=transaction_pdf if index == 1 else None,
            )
            if len(payload) > PART_TARGET_BYTES:
                failure = self._build_limit_failure(
                    entries=document_collection["included_entries"],
                    reason_key="reason_limit",
                    estimated_total_size=sum(entry.approx_size for entry in document_collection["included_entries"]),
                    document_count=len(document_collection["included_entries"]),
                )
                return {
                    "export_id": export_id,
                    "user_id": self.user.id,
                    "status": "failed",
                    "tax_year": self.tax_year,
                    "language": self.language,
                    "include_foundation_materials": self.include_foundation_materials,
                    "expires_at": self._expires_at_iso(),
                    "failure": failure,
                }

            actual_total_bytes += len(payload)
            if actual_total_bytes > MAX_TOTAL_BYTES:
                failure = self._build_limit_failure(
                    entries=document_collection["included_entries"],
                    reason_key="reason_limit",
                    estimated_total_size=actual_total_bytes,
                    document_count=len(document_collection["included_entries"]),
                )
                return {
                    "export_id": export_id,
                    "user_id": self.user.id,
                    "status": "failed",
                    "tax_year": self.tax_year,
                    "language": self.language,
                    "include_foundation_materials": self.include_foundation_materials,
                    "expires_at": self._expires_at_iso(),
                    "failure": failure,
                }

            file_name = self._part_file_name(index, len(part_documents))
            storage_path = f"{EXPORT_STORAGE_PREFIX}/{self.user.id}/{export_id}/{file_name}"
            artifacts.append(
                TaxPackagePartArtifact(
                    part_number=index,
                    file_name=file_name,
                    size_bytes=len(payload),
                    payload=payload,
                    storage_path=storage_path,
                )
            )

        return {
            "export_id": export_id,
            "status": "ready",
            "artifacts": artifacts,
            "summary": summary_stats,
        }

    def _get_transactions(self) -> list[Transaction]:
        return (
            self.db.query(Transaction)
            .filter(
                Transaction.user_id == self.user.id,
                extract("year", Transaction.transaction_date) == self.tax_year,
            )
            .order_by(Transaction.transaction_date.asc(), Transaction.id.asc())
            .all()
        )

    def _collect_document_entries(self, transactions: list[Transaction]) -> dict[str, Any]:
        transaction_ids = [transaction.id for transaction in transactions]
        linked_document_ids = {
            transaction.document_id
            for transaction in transactions
            if transaction.document_id
        }
        tx_linked_document_ids = {
            row[0]
            for row in (
                self.db.query(Document.id)
                .filter(
                    Document.user_id == self.user.id,
                    Document.transaction_id.in_(transaction_ids) if transaction_ids else False,
                )
                .all()
            )
        }

        all_documents = (
            self.db.query(Document)
            .filter(Document.user_id == self.user.id)
            .order_by(Document.uploaded_at.asc(), Document.id.asc())
            .all()
        )

        included_entries: list[TaxPackageDocumentEntry] = []
        family_counts: Counter[str] = Counter()
        excluded_reasons: Counter[str] = Counter()
        skipped_files: list[dict[str, Any]] = []
        uncertain_year_docs = 0
        pending_documents = 0

        for document in all_documents:
            resolved_year, year_basis = self._resolve_document_year(document)
            if resolved_year != self.tax_year:
                excluded_reasons["reason_year_mismatch"] += 1
                continue

            document_type = self._document_type_value(document)
            if year_basis == "uploaded_at":
                uncertain_year_docs += 1
            if self._document_needs_review(document):
                pending_documents += 1

            include_document = False
            family = FAMILY_DIRECTORY_BY_TYPE.get(document_type)
            if document_type in CORE_DOCUMENT_TYPES:
                include_document = True
                family = family or "property-and-financial-docs"
            elif document_type in FOUNDATION_DOCUMENT_TYPES:
                if self.include_foundation_materials:
                    include_document = True
                    family = "foundation-materials"
                else:
                    excluded_reasons["reason_foundation_opt_out"] += 1
                    continue
            elif document_type == DocumentType.OTHER.value:
                if document.id in linked_document_ids or document.id in tx_linked_document_ids or document.transaction_id in transaction_ids:
                    include_document = True
                    family = "other-linked"
                else:
                    excluded_reasons["reason_other_unlinked"] += 1
                    continue
            else:
                excluded_reasons["reason_unsupported"] += 1
                continue

            if not include_document or not family:
                excluded_reasons["reason_unsupported"] += 1
                continue

            if not self.storage.file_exists(document.file_path):
                skipped_files.append(
                    {
                        "document_id": document.id,
                        "file_name": document.file_name,
                        "reason": self._summary_text["reason_storage_missing"],
                    }
                )
                excluded_reasons["reason_storage_missing"] += 1
                continue

            entry = TaxPackageDocumentEntry(
                document_id=document.id,
                document_type=document_type,
                family=family,
                file_name=document.file_name,
                file_path=document.file_path,
                archive_name=self._build_document_archive_name(document, document_type),
                approx_size=max(int(document.file_size or 0), 1),
                year_basis=year_basis,
                needs_review=self._document_needs_review(document),
            )
            included_entries.append(entry)
            family_counts[family] += 1

        return {
            "included_entries": included_entries,
            "family_counts": dict(family_counts),
            "excluded_reasons": dict(excluded_reasons),
            "skipped_files": skipped_files,
            "uncertain_year_docs": uncertain_year_docs,
            "pending_documents": pending_documents,
        }

    def _resolve_document_year(self, document: Document) -> tuple[Optional[int], str]:
        if document.document_date:
            return document.document_date.year, "document_date"
        if document.document_year:
            return int(document.document_year), str(document.year_basis or "document_year")
        if document.uploaded_at:
            return document.uploaded_at.year, "uploaded_at"
        return None, "unknown"

    def _document_needs_review(self, document: Document) -> bool:
        """Unified needs_review logic — must match DocumentDetail.from_orm and get_documents filter."""
        if not getattr(document, "processed_at", None):
            return False
        # Low confidence
        score = float(document.confidence_score) if document.confidence_score is not None else 0
        if score < 0.6:
            return True
        # OCR result exists but not confirmed
        ocr_result = document.ocr_result or {}
        if ocr_result and not ocr_result.get("confirmed"):
            return True
        return False

    def _document_type_value(self, document: Document) -> str:
        raw = getattr(document, "document_type", None)
        return getattr(raw, "value", raw) or DocumentType.OTHER.value

    def _build_document_archive_name(self, document: Document, document_type: str) -> str:
        original_name = Path(document.file_name or Path(document.file_path).name)
        suffix = "".join(original_name.suffixes) or Path(document.file_path).suffix or ""
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name.stem).strip("._-")
        safe_stem = safe_stem[:96] or f"document-{document.id}"
        if document.document_date:
            date_label = document.document_date.isoformat()
        elif document.uploaded_at:
            date_label = document.uploaded_at.date().isoformat()
        else:
            date_label = str(self.tax_year)
        return f"{document_type}_{date_label}_{safe_stem}{suffix.lower()}"

    def _assign_document_parts(
        self,
        entries: list[TaxPackageDocumentEntry],
        fixed_part_one_estimate: int,
    ) -> dict[str, Any]:
        document_count = len(entries)
        estimated_total_size = fixed_part_one_estimate + sum(entry.approx_size for entry in entries)

        if document_count > MAX_DOCUMENTS or estimated_total_size > MAX_TOTAL_BYTES:
            return {
                "parts": [],
                "failure": self._build_limit_failure(
                    entries=entries,
                    reason_key="reason_limit",
                    estimated_total_size=estimated_total_size,
                    document_count=document_count,
                ),
            }

        sorted_entries = sorted(entries, key=lambda item: (item.family, item.archive_name))
        parts: list[list[TaxPackageDocumentEntry]] = [[]]
        current_size = fixed_part_one_estimate

        for entry in sorted_entries:
            entry_size = max(entry.approx_size, 1)
            if parts[-1] and current_size + entry_size > PART_TARGET_BYTES:
                parts.append([])
                current_size = 0
            parts[-1].append(entry)
            current_size += entry_size

        if len(parts) > MAX_PARTS:
            return {
                "parts": [],
                "failure": self._build_limit_failure(
                    entries=entries,
                    reason_key="reason_limit",
                    estimated_total_size=estimated_total_size,
                    document_count=document_count,
                ),
            }

        return {"parts": parts, "failure": None}

    def _build_limit_failure(
        self,
        *,
        entries: list[TaxPackageDocumentEntry],
        reason_key: str,
        estimated_total_size: int,
        document_count: int,
    ) -> dict[str, Any]:
        family_totals: dict[str, int] = defaultdict(int)
        for entry in entries:
            family_totals[entry.family] += int(entry.approx_size or 0)

        largest_family = None
        if family_totals:
            family_name, family_size = max(family_totals.items(), key=lambda item: item[1])
            largest_family = {
                "family": family_name,
                "label": _family_label(self.language, family_name),
                "estimated_size_bytes": family_size,
            }

        largest_files = [
            {
                "document_id": entry.document_id,
                "file_name": entry.file_name,
                "family": entry.family,
                "estimated_size_bytes": entry.approx_size,
            }
            for entry in sorted(entries, key=lambda item: item.approx_size, reverse=True)[:20]
        ]

        return {
            "reason": self._summary_text[reason_key],
            "document_count": document_count,
            "estimated_total_size_bytes": estimated_total_size,
            "max_total_size_bytes": MAX_TOTAL_BYTES,
            "max_parts": MAX_PARTS,
            "max_documents": MAX_DOCUMENTS,
            "largest_family": largest_family,
            "largest_files": largest_files,
        }

    def _build_summary_stats(
        self,
        transactions: list[Transaction],
        document_collection: dict[str, Any],
    ) -> dict[str, Any]:
        income_total = sum(
            (Decimal(transaction.amount or 0) for transaction in transactions if transaction.type == TransactionType.INCOME),
            Decimal("0"),
        )
        expense_total = sum(
            (Decimal(transaction.amount or 0) for transaction in transactions if transaction.type == TransactionType.EXPENSE),
            Decimal("0"),
        )
        deductible_total = sum(
            (
                Decimal(transaction.amount or 0)
                for transaction in transactions
                if transaction.type == TransactionType.EXPENSE and transaction.is_deductible
            ),
            Decimal("0"),
        )
        reconciled_count = sum(1 for transaction in transactions if transaction.bank_reconciled)
        pending_tx_count = sum(1 for transaction in transactions if transaction.needs_review)
        ignored_count = self._count_ignored_bank_lines()

        excluded_reason_items = [
            {
                "key": key,
                "label": self._summary_text.get(key, key),
                "count": count,
            }
            for key, count in sorted(document_collection["excluded_reasons"].items())
            if count
        ]

        return {
            "tax_year": self.tax_year,
            "user_name": self.user.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "language": self.language,
            "include_foundation_materials": self.include_foundation_materials,
            "transaction_count": len(transactions),
            "income_total": float(income_total),
            "expense_total": float(expense_total),
            "deductible_total": float(deductible_total),
            "reconciled_count": reconciled_count,
            "pending_tx_count": pending_tx_count,
            "ignored_count": ignored_count,
            "included_document_count": len(document_collection["included_entries"]),
            "family_counts": document_collection["family_counts"],
            "excluded_document_count": sum(document_collection["excluded_reasons"].values()),
            "excluded_reasons": excluded_reason_items,
            "pending_document_count": document_collection["pending_documents"],
            "uncertain_year_docs": document_collection["uncertain_year_docs"],
            "skipped_files": document_collection["skipped_files"],
        }

    def _count_ignored_bank_lines(self) -> int:
        return (
            self.db.query(func.count(BankStatementLine.id))
            .join(BankStatementImport, BankStatementLine.import_id == BankStatementImport.id)
            .filter(
                BankStatementImport.user_id == self.user.id,
                BankStatementImport.tax_year == self.tax_year,
                BankStatementLine.review_status == BankStatementLineStatus.IGNORED_DUPLICATE,
            )
            .scalar()
            or 0
        )

    def _build_transaction_document_count_map(self, transactions: list[Transaction]) -> dict[int, int]:
        counts: dict[int, set[int]] = {transaction.id: set() for transaction in transactions}
        transaction_ids = [transaction.id for transaction in transactions]
        if not transaction_ids:
            return {}

        for transaction in transactions:
            if transaction.document_id:
                counts.setdefault(transaction.id, set()).add(transaction.document_id)

        linked_documents = (
            self.db.query(Document.id, Document.transaction_id)
            .filter(
                Document.user_id == self.user.id,
                Document.transaction_id.in_(transaction_ids),
            )
            .all()
        )
        for document_id, transaction_id in linked_documents:
            counts.setdefault(int(transaction_id), set()).add(int(document_id))

        return {transaction_id: len(document_ids) for transaction_id, document_ids in counts.items()}

    def _build_transactions_csv(self, transactions: list[Transaction]) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["date", "type", "amount", "description", "category", "is_deductible"])
        for transaction in transactions:
            writer.writerow(
                [
                    transaction.transaction_date.isoformat(),
                    transaction.type.value,
                    f"{Decimal(transaction.amount or 0):.2f}",
                    transaction.description or "",
                    self._transaction_category_label(transaction),
                    "true" if transaction.is_deductible else "false",
                ]
            )
        return output.getvalue().encode("utf-8-sig")

    def _build_transactions_pdf(
        self,
        transactions: list[Transaction],
        linked_doc_counts: dict[int, int],
    ) -> bytes:
        labels = _transaction_labels(self.language)
        font_regular, font_bold = self._ensure_pdf_fonts()
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TaxPackageTitle",
            parent=styles["Title"],
            fontName=font_bold,
            fontSize=18,
            leading=22,
        )
        normal_style = ParagraphStyle(
            "TaxPackageNormal",
            parent=styles["BodyText"],
            fontName=font_regular,
            fontSize=9,
            leading=11,
        )
        header_style = ParagraphStyle(
            "TaxPackageHeader",
            parent=normal_style,
            fontName=font_bold,
            textColor=colors.white,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
        )

        story: list[Any] = [
            Paragraph(escape(labels["title"]), title_style),
            Spacer(1, 4 * mm),
            Paragraph(
                escape(f"{labels['generated']}: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"),
                normal_style,
            ),
            Spacer(1, 4 * mm),
        ]

        table_data: list[list[Any]] = [[
            Paragraph(escape(labels["date"]), header_style),
            Paragraph(escape(labels["type"]), header_style),
            Paragraph(escape(labels["amount"]), header_style),
            Paragraph(escape(labels["description"]), header_style),
            Paragraph(escape(labels["category"]), header_style),
            Paragraph(escape(labels["deductible"]), header_style),
            Paragraph(escape(labels["linked_docs"]), header_style),
        ]]

        if transactions:
            for transaction in transactions:
                table_data.append(
                    [
                        Paragraph(escape(transaction.transaction_date.isoformat()), normal_style),
                        Paragraph(escape(self._transaction_type_label(transaction)), normal_style),
                        Paragraph(escape(f"{Decimal(transaction.amount or 0):.2f}"), normal_style),
                        Paragraph(escape(transaction.description or "-"), normal_style),
                        Paragraph(escape(self._transaction_category_label(transaction) or "-"), normal_style),
                        Paragraph(escape(labels["yes"] if transaction.is_deductible else labels["no"]), normal_style),
                        Paragraph(escape(str(linked_doc_counts.get(transaction.id, 0))), normal_style),
                    ]
                )
        else:
            table_data.append(
                [
                    Paragraph(escape(labels["no_transactions"]), normal_style),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

        table = Table(table_data, repeatRows=1, colWidths=[28 * mm, 24 * mm, 26 * mm, 86 * mm, 34 * mm, 24 * mm, 22 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), font_bold),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    def _build_summary_pdf(
        self,
        *,
        summary_stats: dict[str, Any],
        part_count: int,
    ) -> bytes:
        font_regular, font_bold = self._ensure_pdf_fonts()
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TaxPackageSummaryTitle",
            parent=styles["Title"],
            fontName=font_bold,
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#111827"),
        )
        heading_style = ParagraphStyle(
            "TaxPackageSummaryHeading",
            parent=styles["Heading2"],
            fontName=font_bold,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceBefore=6,
            spaceAfter=4,
        )
        normal_style = ParagraphStyle(
            "TaxPackageSummaryBody",
            parent=styles["BodyText"],
            fontName=font_regular,
            fontSize=10,
            leading=13,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )

        summary = self._summary_text
        story: list[Any] = [
            Paragraph(escape(summary["title"]), title_style),
            Spacer(1, 4 * mm),
            self._build_summary_table(
                [
                    (summary["tax_year"], str(self.tax_year)),
                    (summary["generated_at"], summary_stats["generated_at"].replace("T", " ").replace("+00:00", " UTC")),
                    (summary["language"], self.language),
                    (summary["parts"], str(part_count)),
                    (summary["foundation"], summary["yes"] if self.include_foundation_materials else summary["no"]),
                ],
                font_regular,
                font_bold,
            ),
            Spacer(1, 5 * mm),
            Paragraph(escape(summary["transactions_heading"]), heading_style),
            self._build_summary_table(
                [
                    (summary["tx_count"], str(summary_stats["transaction_count"])),
                    (summary["income_total"], f"{summary_stats['income_total']:.2f}"),
                    (summary["expense_total"], f"{summary_stats['expense_total']:.2f}"),
                    (summary["deductible_total"], f"{summary_stats['deductible_total']:.2f}"),
                    (summary["reconciled_count"], str(summary_stats["reconciled_count"])),
                    (summary["pending_tx_count"], str(summary_stats["pending_tx_count"])),
                    (summary["ignored_count"], str(summary_stats["ignored_count"])),
                ],
                font_regular,
                font_bold,
            ),
            Spacer(1, 5 * mm),
            Paragraph(escape(summary["documents_heading"]), heading_style),
        ]

        family_rows = [
            (_family_label(self.language, family), str(count))
            for family, count in sorted(summary_stats["family_counts"].items())
        ]
        document_rows = [
            (summary["included_docs"], str(summary_stats["included_document_count"])),
            (summary["excluded_docs"], str(summary_stats["excluded_document_count"])),
        ]
        document_rows += family_rows
        story.append(self._build_summary_table(document_rows, font_regular, font_bold))

        excluded_reasons = summary_stats["excluded_reasons"]
        if excluded_reasons:
            story.append(Spacer(1, 4 * mm))
            story.append(
                self._build_summary_table(
                    [(item["label"], str(item["count"])) for item in excluded_reasons],
                    font_regular,
                    font_bold,
                )
            )

        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(escape(summary["risks_heading"]), heading_style))
        risk_rows = []
        if summary_stats["pending_tx_count"] > 0:
            risk_rows.append((summary["pending_tx_count"], str(summary_stats["pending_tx_count"])))
        if summary_stats["pending_document_count"] > 0:
            risk_rows.append((summary["pending_docs"], str(summary_stats["pending_document_count"])))
        if summary_stats["uncertain_year_docs"] > 0:
            risk_rows.append((summary["uncertain_year_docs"], str(summary_stats["uncertain_year_docs"])))
        if summary_stats["skipped_files"]:
            risk_rows.append((summary["skipped_files"], str(len(summary_stats["skipped_files"]))))
        if not risk_rows:
            risk_rows.append((summary["risks_heading"], summary["no_risks"]))
        story.append(self._build_summary_table(risk_rows, font_regular, font_bold))

        if summary_stats["skipped_files"]:
            story.append(Spacer(1, 4 * mm))
            story.append(
                self._build_summary_table(
                    [
                        (item["file_name"], item["reason"])
                        for item in summary_stats["skipped_files"][:12]
                    ],
                    font_regular,
                    font_bold,
                )
            )

        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(escape(summary["usage_heading"]), heading_style))
        story.append(Paragraph(escape(summary["usage_text"]), normal_style))
        if part_count > 1:
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(escape(summary["all_parts_notice"]), normal_style))

        doc.build(story)
        return buffer.getvalue()

    def _build_summary_table(
        self,
        rows: list[tuple[str, str]],
        font_regular: str,
        font_bold: str,
    ) -> Table:
        table_data = []
        left_style = ParagraphStyle("SummaryLeft", fontName=font_bold, fontSize=9, leading=12)
        right_style = ParagraphStyle("SummaryRight", fontName=font_regular, fontSize=9, leading=12)
        for label, value in rows:
            table_data.append(
                [
                    Paragraph(escape(str(label)), left_style),
                    Paragraph(escape(str(value)), right_style),
                ]
            )
        table = Table(table_data, colWidths=[58 * mm, 110 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _build_zip_part(
        self,
        *,
        part_number: int,
        part_count: int,
        entries: list[TaxPackageDocumentEntry],
        summary_pdf: Optional[bytes],
        transaction_csv: Optional[bytes],
        transaction_pdf: Optional[bytes],
    ) -> bytes:
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            if summary_pdf is not None:
                archive.writestr(
                    f"SUMMARY/tax-package-summary_{self.tax_year}_{self.language}.pdf",
                    summary_pdf,
                )
            if transaction_csv is not None:
                archive.writestr(
                    f"TRANSACTIONS/transactions_{self.tax_year}.csv",
                    transaction_csv,
                )
            if transaction_pdf is not None:
                archive.writestr(
                    f"TRANSACTIONS/transactions_{self.tax_year}.pdf",
                    transaction_pdf,
                )

            for entry in entries:
                file_bytes = self.storage.download_file(entry.file_path)
                if file_bytes is None:
                    raise RuntimeError(f"Failed to download document {entry.file_path}")
                archive.writestr(
                    f"DOCUMENTS/{entry.family}/{entry.archive_name}",
                    file_bytes,
                )

        return buffer.getvalue()

    def _part_file_name(self, part_number: int, part_count: int) -> str:
        if part_count == 1:
            return f"tax-package_{self.tax_year}_{self.language}.zip"
        return f"tax-package_{self.tax_year}_{self.language}_part-{part_number}-of-{part_count}.zip"

    def _expires_at_iso(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=EXPORT_URL_EXPIRY_SECONDS)).isoformat()

    def _transaction_type_label(self, transaction: Transaction) -> str:
        labels = _transaction_labels(self.language)
        if transaction.type == TransactionType.INCOME:
            return labels["income"]
        if transaction.type == TransactionType.EXPENSE:
            return labels["expense"]
        return transaction.type.value.replace("_", " ")

    def _transaction_category_label(self, transaction: Transaction) -> str:
        if transaction.income_category:
            return transaction.income_category.value
        if transaction.expense_category:
            return transaction.expense_category.value
        return transaction.type.value

    def _ensure_pdf_fonts(self) -> tuple[str, str]:
        if self.language == "zh":
            if "TaxjaCJK" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
                pdfmetrics.registerFontFamily("TaxjaCJK", normal="STSong-Light", bold="STSong-Light")
            return "STSong-Light", "STSong-Light"

        if "TaxjaSans" not in pdfmetrics.getRegisteredFontNames():
            fonts_dir = Path(reportlab.__file__).resolve().parent / "fonts"
            regular = fonts_dir / "Vera.ttf"
            bold = fonts_dir / "VeraBd.ttf"
            if regular.exists() and bold.exists():
                pdfmetrics.registerFont(TTFont("TaxjaSans", str(regular)))
                pdfmetrics.registerFont(TTFont("TaxjaSansBold", str(bold)))
            else:
                return "Helvetica", "Helvetica-Bold"
        return "TaxjaSans", "TaxjaSansBold"
