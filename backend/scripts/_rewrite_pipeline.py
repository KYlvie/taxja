"""Rewrite _extract_transaction_data and _classify_from_ocr with clean versions."""
import sys

with open('backend/app/services/ocr_transaction_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find boundaries
extract_start = None
extract_end = None
classify_start = None

for i, line in enumerate(lines):
    if '    def _extract_transaction_data(' in line and extract_start is None:
        extract_start = i
    if '    def _extract_from_receipt(' in line and extract_end is None:
        extract_end = i
    if '    def _classify_from_ocr(' in line:
        classify_start = i

assert extract_start is not None, "_extract_transaction_data not found"
assert extract_end is not None, "_extract_from_receipt not found"
assert classify_start is not None, "_classify_from_ocr not found"

print(f"_extract_transaction_data: lines {extract_start+1}-{extract_end} ({extract_end-extract_start} lines)")
print(f"_classify_from_ocr: lines {classify_start+1}-{len(lines)} ({len(lines)-classify_start} lines)")

NEW_EXTRACT = '''\
    def _extract_transaction_data(
        self, document, ocr_data
    ):
        """Extract transaction data from _ai_first.

        Clean pipeline: reads AI two-step classifier result directly.
        No legacy fallback. No VLM override. AI is the single source of truth.
        """
        ai_first = ocr_data.get("_ai_first")
        if not ai_first or ai_first.get("document_type") in (None, "unknown", "?", ""):
            logger.warning("No AI classification for doc %s, skipping", document.id)
            return None

        ai_type = ai_first.get("document_type", "")
        amounts = ai_first.get("amounts") or {}
        key_fields = ai_first.get("key_fields") or {}
        tax = ai_first.get("tax_treatment") or {}

        # Determine amount
        amount = (
            amounts.get("total_amount")
            or amounts.get("annual_amount")
            or amounts.get("monthly_amount")
            or amounts.get("settlement_amount")
        )

        # SVS: prefer quarterly_amount from key_fields
        if ai_type in ("svs_vorschreibung",) and key_fields.get("quarterly_amount"):
            amount = key_fields["quarterly_amount"]

        if not amount or float(amount) <= 0:
            logger.info("No amount for doc %s (type=%s)", document.id, ai_type)
            return None

        # Date
        date_str = key_fields.get("date") or key_fields.get("purchase_date") or ocr_data.get("date")

        # Description
        desc_parts = []
        for field in ["issuer", "employer_name", "lender_name", "insurer_name",
                       "recipient_org", "parish", "supplier"]:
            val = key_fields.get(field)
            if val:
                desc_parts.append(str(val))
                break
        desc_ai = key_fields.get("description") or ""
        if desc_ai and desc_ai not in desc_parts:
            desc_parts.append(desc_ai[:80])
        if not desc_parts:
            desc_parts.append(ocr_data.get("description") or ocr_data.get("merchant") or ai_type)

        description = " \\u2014 ".join(desc_parts)

        logger.info("AI extraction doc %s: type=%s amt=%.2f desc=%s",
                     document.id, ai_type, float(amount), description[:60])

        return {
            "amount": float(amount),
            "date": date_str,
            "description": description,
            "_ai_extracted": True,
            "_ai_doc_type": ai_type,
        }

'''

NEW_CLASSIFY = '''\
    def _classify_from_ocr(
        self, document, transaction_data, user_id,
        *, direction_resolution=None,
    ):
        """Classify transaction from _ai_first.

        Clean pipeline: reads AI results directly for transaction_type,
        category, and deductibility. No legacy fallback.
        """
        ocr_json = document.ocr_result if isinstance(document.ocr_result, dict) else {}
        ai_first = ocr_json.get("_ai_first", {})
        ai_type = ai_first.get("document_type", "unknown")
        tax = ai_first.get("tax_treatment") or {}
        creates = ai_first.get("creates", [])
        key_fields = ai_first.get("key_fields") or {}

        if isinstance(creates, str):
            creates = [creates]

        ai_direction = tax.get("expense_or_income", "expense")
        is_asset = "asset" in creates or ai_type == "asset_purchase"
        is_gwg = key_fields.get("is_gwg")

        # Transaction type
        if is_asset and not is_gwg:
            txn_type = TransactionType.ASSET_ACQUISITION.value
        elif ai_direction == "income":
            txn_type = TransactionType.INCOME.value
        else:
            txn_type = TransactionType.EXPENSE.value

        # Category
        ai_ded_cat = tax.get("deduction_category") or ""
        ai_form = tax.get("tax_form") or ""

        if txn_type == TransactionType.INCOME.value:
            if ai_type == "lohnzettel":
                category = IncomeCategory.EMPLOYMENT.value
            elif ai_type == "mietvorschreibung" or ai_form.upper() == "E1B":
                category = IncomeCategory.RENTAL.value
            else:
                category = IncomeCategory.SELF_EMPLOYMENT.value
        elif txn_type == TransactionType.ASSET_ACQUISITION.value:
            category = ExpenseCategory.EQUIPMENT.value
        else:
            cat_map = {
                "miete": ExpenseCategory.RENT.value,
                "versicherung": ExpenseCategory.INSURANCE.value,
                "zinsen": ExpenseCategory.LOAN_INTEREST.value,
                "svs": ExpenseCategory.SVS_CONTRIBUTIONS.value,
                "grundsteuer": ExpenseCategory.PROPERTY_TAX.value,
                "hausverwaltung": ExpenseCategory.PROPERTY_MANAGEMENT_FEES.value,
                "reparatur": ExpenseCategory.MAINTENANCE.value,
                "buero": ExpenseCategory.OFFICE_SUPPLIES.value,
                "reise": ExpenseCategory.TRAVEL.value,
            }
            category = ExpenseCategory.OTHER.value
            for key, val in cat_map.items():
                if key in ai_ded_cat.lower():
                    category = val
                    break

            # Type-specific overrides
            type_cat_map = {
                "grundsteuerbescheid": ExpenseCategory.PROPERTY_TAX.value,
                "zinsbescheinigung": ExpenseCategory.LOAN_INTEREST.value,
                "versicherungspolizze": ExpenseCategory.INSURANCE.value,
                "svs_vorschreibung": ExpenseCategory.SVS_CONTRIBUTIONS.value,
                "svs_nachbemessung": ExpenseCategory.SVS_CONTRIBUTIONS.value,
            }
            if ai_type in type_cat_map:
                category = type_cat_map[ai_type]

        is_deductible = tax.get("is_deductible", True) if txn_type != TransactionType.INCOME.value else False
        confidence = ai_first.get("confidence", 0.75)

        return {
            "transaction_type": txn_type,
            "category": category,
            "is_deductible": bool(is_deductible),
            "deduction_reason": ai_ded_cat or None,
            "confidence": confidence,
            "classification_method": "ai_two_step",
            "requires_review": confidence < 0.7,
        }
'''

# Build new file
new_lines = lines[:extract_start] + [NEW_EXTRACT] + lines[extract_end:classify_start] + [NEW_CLASSIFY]

with open('backend/app/services/ocr_transaction_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

new_total = sum(1 for _ in open('backend/app/services/ocr_transaction_service.py', encoding='utf-8'))
print(f"Done: {len(lines)} -> {new_total} lines (removed {len(lines)-new_total} lines)")
