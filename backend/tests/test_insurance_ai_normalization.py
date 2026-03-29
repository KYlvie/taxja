from app.services.ocr_engine import OCREngine


def test_monthly_insurance_keeps_period_amount_and_derives_annual_total():
    payload = {
        "zahlungsfrequenz": "monthly",
        "praemie": 28.40,
    }

    OCREngine._normalize_insurance_amount_fields(payload)

    assert payload["praemie"] == 28.40
    assert payload["praemie_jaehrlich"] == 340.80


def test_monthly_insurance_recovers_period_amount_from_annual_total():
    payload = {
        "zahlungsfrequenz": "monthly",
        "praemie": 340.80,
        "praemie_jaehrlich": 340.80,
    }

    OCREngine._normalize_insurance_amount_fields(payload)

    assert payload["praemie"] == 28.40
    assert payload["praemie_jaehrlich"] == 340.80


def test_annual_insurance_overrides_date_like_period_amount():
    payload = {
        "zahlungsfrequenz": "annually",
        "praemie": 15.01,
        "praemie_jaehrlich": 363.12,
    }

    OCREngine._normalize_insurance_amount_fields(payload)

    assert payload["praemie"] == 363.12
    assert payload["praemie_jaehrlich"] == 363.12


def test_fact_first_fields_are_mapped_into_normalized_premium_fields():
    payload = {
        "zahlungsfrequenz": "monthly",
        "payment_amount": 138.53,
        "annual_total_amount": 1662.36,
        "payment_amount_label": "Abbuchungsbetrag",
        "annual_total_label": "Voraussichtl. Jahresgesamt",
    }

    OCREngine._normalize_insurance_amount_fields(payload)

    assert payload["praemie"] == 138.53
    assert payload["praemie_jaehrlich"] == 1662.36


def test_amount_paid_this_year_falls_back_to_annual_total():
    payload = {
        "zahlungsfrequenz": "annually",
        "amount_paid_this_year": 363.12,
    }

    OCREngine._normalize_insurance_amount_fields(payload)

    assert payload["praemie"] == 363.12
    assert payload["praemie_jaehrlich"] == 363.12
