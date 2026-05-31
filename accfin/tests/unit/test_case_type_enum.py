"""CaseType enum matches PostgreSQL case_type and ORM ENUM."""

from app.models.case import CASE_TYPE_ENUM, CASE_TYPE_VALUES, CaseType


def test_expense_claim_in_case_type_enum() -> None:
    assert CaseType.EXPENSE_CLAIM.value == "expense_claim"
    assert "expense_claim" in CASE_TYPE_VALUES


def test_case_type_enum_includes_all_members() -> None:
    assert set(CASE_TYPE_VALUES) == {member.value for member in CaseType}


def test_sqlalchemy_case_type_enum_values() -> None:
    assert set(CASE_TYPE_ENUM.enums) == set(CASE_TYPE_VALUES)
