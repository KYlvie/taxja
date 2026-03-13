"""
Localized error messages for historical data import feature.

This module provides comprehensive error messages in German, English, and Chinese
for all common failure scenarios in the historical data import workflow.

Error messages follow i18next format for consistency with frontend and support
parameter substitution using Python string formatting.

Usage:
    from app.core.error_messages import get_error_message
    
    # Get localized error message
    message = get_error_message("extraction_low_confidence", "de", confidence=65)
    # Returns: "Die Datenextraktion war unsicher (Konfidenz: 65%). Bitte überprüfen Sie die extrahierten Daten manuell."
    
    # Get error message with default language (German)
    message = get_error_message("duplicate_transaction")
    # Returns: "Diese Transaktion wurde bereits importiert. Duplikat verhindert."
"""

from typing import Dict, Any, Optional


# Error message dictionary with de, en, zh translations
ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
    # Extraction errors
    "extraction_low_confidence": {
        "de": "Die Datenextraktion war unsicher (Konfidenz: {confidence}%). Bitte überprüfen Sie die extrahierten Daten manuell.",
        "en": "Data extraction had low confidence ({confidence}%). Please review the extracted data manually.",
        "zh": "数据提取置信度较低（{confidence}%）。请手动检查提取的数据。",
    },
    "extraction_failed": {
        "de": "Die Datenextraktion ist fehlgeschlagen. Bitte überprüfen Sie die Dokumentqualität und versuchen Sie es erneut.",
        "en": "Data extraction failed. Please check the document quality and try again.",
        "zh": "数据提取失败。请检查文档质量并重试。",
    },
    "ocr_failed": {
        "de": "Die OCR-Verarbeitung ist fehlgeschlagen. Das Dokument konnte nicht gelesen werden.",
        "en": "OCR processing failed. The document could not be read.",
        "zh": "OCR处理失败。无法读取文档。",
    },
    "ocr_timeout": {
        "de": "Die OCR-Verarbeitung hat zu lange gedauert. Bitte versuchen Sie es mit einem kleineren Dokument.",
        "en": "OCR processing timed out. Please try with a smaller document.",
        "zh": "OCR处理超时。请尝试使用较小的文档。",
    },
    "parsing_error": {
        "de": "Fehler beim Parsen des Dokuments: {error}. Bitte überprüfen Sie das Dokumentformat.",
        "en": "Error parsing document: {error}. Please check the document format.",
        "zh": "解析文档时出错：{error}。请检查文档格式。",
    },
    "missing_required_field": {
        "de": "Erforderliches Feld fehlt: {field_name}. Bitte ergänzen Sie die Daten manuell.",
        "en": "Required field missing: {field_name}. Please add the data manually.",
        "zh": "缺少必填字段：{field_name}。请手动添加数据。",
    },
    "invalid_document_format": {
        "de": "Ungültiges Dokumentformat. Erwartetes Format: {expected_format}.",
        "en": "Invalid document format. Expected format: {expected_format}.",
        "zh": "无效的文档格式。预期格式：{expected_format}。",
    },
    
    # Validation errors
    "invalid_tax_year": {
        "de": "Ungültiges Steuerjahr: {year}. Muss zwischen {min_year} und {max_year} liegen.",
        "en": "Invalid tax year: {year}. Must be between {min_year} and {max_year}.",
        "zh": "无效的税务年度：{year}。必须在 {min_year} 和 {max_year} 之间。",
    },
    "tax_year_future": {
        "de": "Das Steuerjahr {year} liegt in der Zukunft. Bitte wählen Sie ein vergangenes Jahr.",
        "en": "Tax year {year} is in the future. Please select a past year.",
        "zh": "税务年度 {year} 在未来。请选择过去的年份。",
    },
    "tax_year_too_old": {
        "de": "Das Steuerjahr {year} ist zu alt (maximal {max_years} Jahre zurück).",
        "en": "Tax year {year} is too old (maximum {max_years} years back).",
        "zh": "税务年度 {year} 太旧（最多 {max_years} 年前）。",
    },
    "invalid_amount": {
        "de": "Ungültiger Betrag: {amount}. Betrag muss eine positive Zahl sein.",
        "en": "Invalid amount: {amount}. Amount must be a positive number.",
        "zh": "无效金额：{amount}。金额必须是正数。",
    },
    "invalid_date": {
        "de": "Ungültiges Datum: {date}. Bitte verwenden Sie das Format TT.MM.JJJJ.",
        "en": "Invalid date: {date}. Please use format DD.MM.YYYY.",
        "zh": "无效日期：{date}。请使用格式 DD.MM.YYYY。",
    },
    "invalid_category": {
        "de": "Ungültige Kategorie: {category}. Erlaubte Kategorien: {allowed_categories}.",
        "en": "Invalid category: {category}. Allowed categories: {allowed_categories}.",
        "zh": "无效类别：{category}。允许的类别：{allowed_categories}。",
    },
    "amount_exceeds_limit": {
        "de": "Betrag {amount} überschreitet das Limit von {limit} für {category}.",
        "en": "Amount {amount} exceeds the limit of {limit} for {category}.",
        "zh": "金额 {amount} 超过 {category} 的限制 {limit}。",
    },
    "negative_amount_not_allowed": {
        "de": "Negativer Betrag nicht erlaubt für {field_name}. Gefunden: {amount}.",
        "en": "Negative amount not allowed for {field_name}. Found: {amount}.",
        "zh": "{field_name} 不允许负数金额。发现：{amount}。",
    },
    
    # Duplicate and conflict errors
    "duplicate_transaction": {
        "de": "Diese Transaktion wurde bereits importiert. Duplikat verhindert.",
        "en": "This transaction was already imported. Duplicate prevented.",
        "zh": "此交易已导入。已防止重复。",
    },
    "duplicate_transaction_detected": {
        "de": "Mögliches Duplikat erkannt: {transaction_description}. Konfidenz: {confidence}%.",
        "en": "Possible duplicate detected: {transaction_description}. Confidence: {confidence}%.",
        "zh": "检测到可能的重复项：{transaction_description}。置信度：{confidence}%。",
    },
    "conflict_detected": {
        "de": "Konflikt erkannt zwischen {document_type_1} und {document_type_2} für {field_name}.",
        "en": "Conflict detected between {document_type_1} and {document_type_2} for {field_name}.",
        "zh": "在 {document_type_1} 和 {document_type_2} 之间检测到 {field_name} 的冲突。",
    },
    "conflicting_amounts": {
        "de": "Widersprüchliche Beträge: {amount_1} vs {amount_2} für {field_name}. Differenz: {difference}%.",
        "en": "Conflicting amounts: {amount_1} vs {amount_2} for {field_name}. Difference: {difference}%.",
        "zh": "金额冲突：{amount_1} 与 {amount_2}（{field_name}）。差异：{difference}%。",
    },
    "duplicate_property": {
        "de": "Eine Immobilie mit dieser Adresse existiert bereits: {address}.",
        "en": "A property with this address already exists: {address}.",
        "zh": "此地址的房产已存在：{address}。",
    },
    
    # Import errors
    "import_failed": {
        "de": "Import fehlgeschlagen: {error}. Bitte kontaktieren Sie den Support.",
        "en": "Import failed: {error}. Please contact support.",
        "zh": "导入失败：{error}。请联系支持。",
    },
    "transaction_creation_failed": {
        "de": "Fehler beim Erstellen der Transaktion: {error}.",
        "en": "Failed to create transaction: {error}.",
        "zh": "创建交易失败：{error}。",
    },
    "property_creation_failed": {
        "de": "Fehler beim Erstellen der Immobilie: {error}.",
        "en": "Failed to create property: {error}.",
        "zh": "创建房产失败：{error}。",
    },
    "property_linking_failed": {
        "de": "Fehler beim Verknüpfen der Immobilie: {error}.",
        "en": "Failed to link property: {error}.",
        "zh": "链接房产失败：{error}。",
    },
    "depreciation_schedule_failed": {
        "de": "Fehler beim Erstellen des Abschreibungsplans: {error}.",
        "en": "Failed to create depreciation schedule: {error}.",
        "zh": "创建折旧计划失败：{error}。",
    },
    
    # File errors
    "file_too_large": {
        "de": "Datei zu groß: {size} MB. Maximale Größe: {max_size} MB.",
        "en": "File too large: {size} MB. Maximum size: {max_size} MB.",
        "zh": "文件太大：{size} MB。最大大小：{max_size} MB。",
    },
    "file_type_not_supported": {
        "de": "Dateityp nicht unterstützt: {file_type}. Erlaubte Typen: {allowed_types}.",
        "en": "File type not supported: {file_type}. Allowed types: {allowed_types}.",
        "zh": "不支持的文件类型：{file_type}。允许的类型：{allowed_types}。",
    },
    "file_corrupted": {
        "de": "Die Datei ist beschädigt oder kann nicht gelesen werden.",
        "en": "The file is corrupted or cannot be read.",
        "zh": "文件已损坏或无法读取。",
    },
    "file_not_found": {
        "de": "Datei nicht gefunden: {file_path}.",
        "en": "File not found: {file_path}.",
        "zh": "找不到文件：{file_path}。",
    },
    
    # Database errors
    "user_not_found": {
        "de": "Benutzer nicht gefunden: {user_id}.",
        "en": "User not found: {user_id}.",
        "zh": "找不到用户：{user_id}。",
    },
    "upload_not_found": {
        "de": "Upload nicht gefunden: {upload_id}.",
        "en": "Upload not found: {upload_id}.",
        "zh": "找不到上传：{upload_id}。",
    },
    "session_not_found": {
        "de": "Sitzung nicht gefunden: {session_id}.",
        "en": "Session not found: {session_id}.",
        "zh": "找不到会话：{session_id}。",
    },
    "property_not_found": {
        "de": "Immobilie nicht gefunden: {property_id}.",
        "en": "Property not found: {property_id}.",
        "zh": "找不到房产：{property_id}。",
    },
    "database_error": {
        "de": "Datenbankfehler: {error}. Bitte versuchen Sie es später erneut.",
        "en": "Database error: {error}. Please try again later.",
        "zh": "数据库错误：{error}。请稍后重试。",
    },
    
    # Review and approval errors
    "invalid_review_state": {
        "de": "Upload kann nicht überprüft werden im Status: {status}. Erforderlicher Status: {required_status}.",
        "en": "Upload cannot be reviewed in status: {status}. Required status: {required_status}.",
        "zh": "无法在状态 {status} 中审核上传。所需状态：{required_status}。",
    },
    "approval_failed": {
        "de": "Genehmigung fehlgeschlagen: {error}.",
        "en": "Approval failed: {error}.",
        "zh": "批准失败：{error}。",
    },
    "rejection_failed": {
        "de": "Ablehnung fehlgeschlagen: {error}.",
        "en": "Rejection failed: {error}.",
        "zh": "拒绝失败：{error}。",
    },
    "finalization_failed": {
        "de": "Finalisierung fehlgeschlagen: {error}. Einige Daten wurden möglicherweise nicht gespeichert.",
        "en": "Finalization failed: {error}. Some data may not have been saved.",
        "zh": "完成失败：{error}。某些数据可能未保存。",
    },
    
    # Saldenliste specific errors
    "saldenliste_parse_error": {
        "de": "Fehler beim Parsen der Saldenliste: {error}. Bitte überprüfen Sie das Dateiformat.",
        "en": "Error parsing Saldenliste: {error}. Please check the file format.",
        "zh": "解析余额表时出错：{error}。请检查文件格式。",
    },
    "unmapped_accounts": {
        "de": "{count} Konten konnten nicht zugeordnet werden. Bitte überprüfen Sie die Kontenzuordnung.",
        "en": "{count} accounts could not be mapped. Please review the account mapping.",
        "zh": "{count} 个账户无法映射。请检查账户映射。",
    },
    "account_mapping_failed": {
        "de": "Kontenzuordnung fehlgeschlagen für Konto {account_number}: {account_name}.",
        "en": "Account mapping failed for account {account_number}: {account_name}.",
        "zh": "账户 {account_number} 的映射失败：{account_name}。",
    },
    "balance_mismatch": {
        "de": "Saldendifferenz erkannt: Soll {debit} vs Haben {credit}. Differenz: {difference}.",
        "en": "Balance mismatch detected: Debit {debit} vs Credit {credit}. Difference: {difference}.",
        "zh": "检测到余额不匹配：借方 {debit} 与贷方 {credit}。差异：{difference}。",
    },
    "continuity_check_failed": {
        "de": "Kontinuitätsprüfung fehlgeschlagen: Schlusssaldo {year} ({closing_balance}) ≠ Anfangssaldo {next_year} ({opening_balance}).",
        "en": "Continuity check failed: Closing balance {year} ({closing_balance}) ≠ Opening balance {next_year} ({opening_balance}).",
        "zh": "连续性检查失败：{year} 年期末余额 ({closing_balance}) ≠ {next_year} 年期初余额 ({opening_balance})。",
    },
    
    # Kaufvertrag specific errors
    "missing_purchase_price": {
        "de": "Kaufpreis fehlt im Kaufvertrag. Bitte ergänzen Sie den Kaufpreis manuell.",
        "en": "Purchase price missing in Kaufvertrag. Please add the purchase price manually.",
        "zh": "购买合同中缺少购买价格。请手动添加购买价格。",
    },
    "missing_purchase_date": {
        "de": "Kaufdatum fehlt im Kaufvertrag. Bitte ergänzen Sie das Kaufdatum manuell.",
        "en": "Purchase date missing in Kaufvertrag. Please add the purchase date manually.",
        "zh": "购买合同中缺少购买日期。请手动添加购买日期。",
    },
    "missing_property_address": {
        "de": "Immobilienadresse fehlt im Kaufvertrag. Bitte ergänzen Sie die Adresse manuell.",
        "en": "Property address missing in Kaufvertrag. Please add the address manually.",
        "zh": "购买合同中缺少房产地址。请手动添加地址。",
    },
    "invalid_building_value": {
        "de": "Ungültiger Gebäudewert: {value}. Gebäudewert muss positiv sein.",
        "en": "Invalid building value: {value}. Building value must be positive.",
        "zh": "无效的建筑价值：{value}。建筑价值必须为正数。",
    },
    
    # E1 Form specific errors
    "invalid_kz_code": {
        "de": "Ungültiger KZ-Code: {kz_code}. Bitte überprüfen Sie die E1-Formulardaten.",
        "en": "Invalid KZ code: {kz_code}. Please check the E1 form data.",
        "zh": "无效的 KZ 代码：{kz_code}。请检查 E1 表单数据。",
    },
    "kz_extraction_incomplete": {
        "de": "KZ-Extraktion unvollständig. {extracted_count} von {expected_count} Feldern extrahiert.",
        "en": "KZ extraction incomplete. {extracted_count} of {expected_count} fields extracted.",
        "zh": "KZ 提取不完整。已提取 {extracted_count} 个字段，共 {expected_count} 个。",
    },
    
    # Bescheid specific errors
    "address_matching_failed": {
        "de": "Adressabgleich fehlgeschlagen für: {address}. Keine passende Immobilie gefunden.",
        "en": "Address matching failed for: {address}. No matching property found.",
        "zh": "地址匹配失败：{address}。未找到匹配的房产。",
    },
    "multiple_address_matches": {
        "de": "Mehrere Immobilien gefunden für Adresse: {address}. Bitte wählen Sie manuell.",
        "en": "Multiple properties found for address: {address}. Please select manually.",
        "zh": "找到多个地址匹配的房产：{address}。请手动选择。",
    },
    
    # Session errors
    "session_already_completed": {
        "de": "Sitzung bereits abgeschlossen: {session_id}.",
        "en": "Session already completed: {session_id}.",
        "zh": "会话已完成：{session_id}。",
    },
    "session_failed": {
        "de": "Sitzung fehlgeschlagen: {session_id}. {failed_count} von {total_count} Uploads fehlgeschlagen.",
        "en": "Session failed: {session_id}. {failed_count} of {total_count} uploads failed.",
        "zh": "会话失败：{session_id}。{total_count} 个上传中有 {failed_count} 个失败。",
    },
    
    # Generic errors
    "unknown_error": {
        "de": "Ein unbekannter Fehler ist aufgetreten. Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.",
        "en": "An unknown error occurred. Please try again or contact support.",
        "zh": "发生未知错误。请重试或联系支持。",
    },
    "operation_timeout": {
        "de": "Die Operation hat zu lange gedauert und wurde abgebrochen. Bitte versuchen Sie es erneut.",
        "en": "The operation timed out and was cancelled. Please try again.",
        "zh": "操作超时并已取消。请重试。",
    },
    "permission_denied": {
        "de": "Zugriff verweigert. Sie haben keine Berechtigung für diese Operation.",
        "en": "Permission denied. You do not have permission for this operation.",
        "zh": "权限被拒绝。您没有此操作的权限。",
    },
}


def get_error_message(
    error_key: str,
    language: str = "de",
    **kwargs: Any
) -> str:
    """
    Get a localized error message with parameter substitution.
    
    Args:
        error_key: Key identifying the error message
        language: Language code (de, en, zh). Defaults to German.
        **kwargs: Parameters to substitute in the error message
    
    Returns:
        Formatted error message in the requested language
        
    Examples:
        >>> get_error_message("extraction_low_confidence", "de", confidence=65)
        'Die Datenextraktion war unsicher (Konfidenz: 65%). Bitte überprüfen Sie die extrahierten Daten manuell.'
        
        >>> get_error_message("invalid_tax_year", "en", year=2035, min_year=2015, max_year=2024)
        'Invalid tax year: 2035. Must be between 2015 and 2024.'
        
        >>> get_error_message("duplicate_transaction", "zh")
        '此交易已导入。已防止重复。'
    """
    # Validate language, default to German
    if language not in ["de", "en", "zh"]:
        language = "de"
    
    # Get error message template
    error_dict = ERROR_MESSAGES.get(error_key)
    if not error_dict:
        # Return generic error if key not found
        error_dict = ERROR_MESSAGES["unknown_error"]
    
    message_template = error_dict.get(language, error_dict.get("de", "Unknown error"))
    
    # Substitute parameters
    try:
        return message_template.format(**kwargs)
    except KeyError as e:
        # If parameter missing, return template with error note
        return f"{message_template} [Missing parameter: {e}]"


def get_all_error_keys() -> list[str]:
    """
    Get a list of all available error message keys.
    
    Returns:
        List of error message keys
    """
    return list(ERROR_MESSAGES.keys())


def get_error_dict(error_key: str) -> Optional[Dict[str, str]]:
    """
    Get the complete error dictionary for a given key (all languages).
    
    Args:
        error_key: Key identifying the error message
    
    Returns:
        Dictionary with all language translations, or None if key not found
        
    Example:
        >>> get_error_dict("duplicate_transaction")
        {
            'de': 'Diese Transaktion wurde bereits importiert. Duplikat verhindert.',
            'en': 'This transaction was already imported. Duplicate prevented.',
            'zh': '此交易已导入。已防止重复。'
        }
    """
    return ERROR_MESSAGES.get(error_key)
