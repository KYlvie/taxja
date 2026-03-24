"""Tests for form eligibility service — maps user types to applicable tax forms."""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.models.user import User, UserType
from app.models.tax_form_template import TaxFormType
from app.services.form_eligibility_service import (
    get_eligible_forms,
    get_eligible_form_types,
)


def _make_user(user_type, family_info=None):
    user = Mock(spec=User)
    user.id = 1
    user.user_type = user_type
    user.family_info = family_info or {}
    return user


# ── Employee ──

class TestEmployeeForms:
    def test_employee_gets_e1_and_l1(self):
        user = _make_user(UserType.EMPLOYEE)
        forms = get_eligible_form_types(user)
        assert "E1" in forms
        assert "L1" in forms

    def test_employee_no_e1a(self):
        user = _make_user(UserType.EMPLOYEE)
        forms = get_eligible_form_types(user)
        assert "E1a" not in forms

    def test_employee_no_u1_uva(self):
        user = _make_user(UserType.EMPLOYEE)
        forms = get_eligible_form_types(user)
        assert "U1" not in forms
        assert "UVA" not in forms

    def test_employee_no_k1(self):
        user = _make_user(UserType.EMPLOYEE)
        forms = get_eligible_form_types(user)
        assert "K1" not in forms

    def test_employee_with_children_gets_l1k(self):
        user = _make_user(UserType.EMPLOYEE, family_info={
            "children": [{"name": "Anna", "birth_date": "2015-01-01"}]
        })
        forms = get_eligible_form_types(user)
        assert "L1k" in forms

    def test_employee_without_children_no_l1k(self):
        user = _make_user(UserType.EMPLOYEE, family_info={})
        forms = get_eligible_form_types(user)
        assert "L1k" not in forms


# ── Self-employed ──

class TestSelfEmployedForms:
    def test_self_employed_gets_e1_e1a(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_form_types(user)
        assert "E1" in forms
        assert "E1a" in forms

    def test_self_employed_gets_u1_uva(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_form_types(user)
        assert "U1" in forms
        assert "UVA" in forms

    def test_self_employed_no_e1b(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_form_types(user)
        assert "E1b" not in forms

    def test_self_employed_no_l1(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_form_types(user)
        assert "L1" not in forms

    def test_self_employed_no_k1(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_form_types(user)
        assert "K1" not in forms


# ── Landlord ──

class TestLandlordForms:
    def test_landlord_gets_e1_e1b(self):
        user = _make_user(UserType.LANDLORD)
        forms = get_eligible_form_types(user)
        assert "E1" in forms
        # E1b shown by default (no DB check without session)
        assert "E1b" in forms

    def test_landlord_no_e1a(self):
        user = _make_user(UserType.LANDLORD)
        forms = get_eligible_form_types(user)
        assert "E1a" not in forms

    def test_landlord_no_u1(self):
        user = _make_user(UserType.LANDLORD)
        forms = get_eligible_form_types(user)
        assert "U1" not in forms


# ── Mixed ──

class TestMixedForms:
    def test_mixed_gets_all_personal_forms(self):
        user = _make_user(UserType.MIXED, family_info={"num_children": 1})
        forms = get_eligible_form_types(user)
        assert "E1" in forms
        assert "E1a" in forms
        assert "E1b" in forms
        assert "L1" in forms
        assert "L1k" in forms
        assert "U1" in forms
        assert "UVA" in forms

    def test_mixed_no_k1(self):
        user = _make_user(UserType.MIXED)
        forms = get_eligible_form_types(user)
        assert "K1" not in forms


# ── GmbH ──

class TestGmbHForms:
    def test_gmbh_gets_k1_u1_uva(self):
        user = _make_user(UserType.GMBH)
        forms = get_eligible_form_types(user)
        assert "K1" in forms
        assert "U1" in forms
        assert "UVA" in forms

    def test_gmbh_no_personal_forms(self):
        user = _make_user(UserType.GMBH)
        forms = get_eligible_form_types(user)
        assert "E1" not in forms
        assert "E1a" not in forms
        assert "E1b" not in forms
        assert "L1" not in forms
        assert "L1k" not in forms


# ── Children logic ──

class TestChildrenLogic:
    def test_num_children_enables_l1k(self):
        user = _make_user(UserType.EMPLOYEE, family_info={"num_children": 2})
        forms = get_eligible_form_types(user)
        assert "L1k" in forms

    def test_children_list_enables_l1k(self):
        user = _make_user(UserType.SELF_EMPLOYED, family_info={
            "children": [{"name": "Max"}]
        })
        forms = get_eligible_form_types(user)
        assert "L1k" in forms

    def test_zero_num_children_no_l1k(self):
        user = _make_user(UserType.EMPLOYEE, family_info={"num_children": 0})
        forms = get_eligible_form_types(user)
        assert "L1k" not in forms

    def test_gmbh_never_gets_l1k_even_with_children(self):
        """GmbH is a company, not a person — no L1k."""
        user = _make_user(UserType.GMBH, family_info={"num_children": 3})
        forms = get_eligible_form_types(user)
        assert "L1k" not in forms


# ── Metadata ──

class TestFormMetadata:
    def test_forms_have_trilingual_names(self):
        user = _make_user(UserType.EMPLOYEE, family_info={"num_children": 1})
        forms = get_eligible_forms(user)
        for form in forms:
            assert "name_de" in form
            assert "name_en" in form
            assert "name_zh" in form
            assert form["name_de"]  # not empty
            assert form["name_en"]
            assert form["name_zh"]

    def test_forms_have_category(self):
        user = _make_user(UserType.SELF_EMPLOYED)
        forms = get_eligible_forms(user)
        categories = {f["category"] for f in forms}
        assert "income_tax" in categories or "vat" in categories

    def test_form_type_values_are_strings(self):
        user = _make_user(UserType.MIXED, family_info={"num_children": 1})
        forms = get_eligible_forms(user)
        for form in forms:
            assert isinstance(form["form_type"], str)
