from app.core.error_messages import get_error_message, get_ocr_field_label
from app.core.text_encoding import repair_mojibake


def test_repair_mojibake_repairs_common_control_characters():
    assert repair_mojibake("Valeur du b\u00e2timent (\x80)") == "Valeur du b\u00e2timent (\u20ac)"
    assert repair_mojibake("Symulator \x84Co je\u015bli\x94") == "Symulator \u201eCo je\u015bli\u201d"
    assert repair_mojibake("Fran\u00c3\u00a7ais") == "Fran\u00e7ais"


def test_error_messages_are_returned_with_clean_unicode():
    message = get_error_message("extraction_low_confidence", "de", confidence=65)
    assert "überprüfen" in message

    chinese_message = get_error_message("duplicate_transaction", "zh")
    assert "交易" in chinese_message


def test_ocr_field_labels_are_returned_with_clean_unicode():
    assert get_ocr_field_label("merchant", "fr") == "Commerçant"
    assert get_ocr_field_label("amount", "hu") == "Összeg"
