"""Trial balance formatting and report structure."""

from datetime import date
from decimal import Decimal

from app.schemas.trial_balance import TrialBalanceGroup, TrialBalanceResponse, TrialBalanceRow
from app.services.trial_balance import (
    format_trial_balance_amount,
    format_trial_balance_balance,
    format_trial_balance_total,
    trial_balance_to_csv,
)


def test_format_trial_balance_amount_zero_is_none():
    assert format_trial_balance_amount(Decimal("0")) is None
    assert format_trial_balance_amount(Decimal("0.00")) is None


def test_format_trial_balance_amount_nonzero():
    assert format_trial_balance_amount(Decimal("1.07")) == "1.07"
    assert format_trial_balance_amount(Decimal("12.9")) == "12.90"


def test_format_trial_balance_balance_positive_and_negative():
    assert format_trial_balance_balance(Decimal("1.07"), Decimal("0")) == "1.07"
    assert format_trial_balance_balance(Decimal("0"), Decimal("12.90")) == "(12.90)"
    assert format_trial_balance_balance(Decimal("0"), Decimal("0")) == "0.00"


def test_trial_balance_csv_structure():
    report = TrialBalanceResponse(
        as_at=date(2026, 5, 28),
        groups=[
            TrialBalanceGroup(
                account_type="asset",
                label="ASSET",
                rows=[
                    TrialBalanceRow(
                        account_code="2011",
                        account_name="GST Input Tax",
                        debit="1.07",
                        credit=None,
                        balance="1.07",
                    ),
                ],
                total_balance="1.07",
            ),
            TrialBalanceGroup(
                account_type="liability",
                label="LIABILITY",
                rows=[
                    TrialBalanceRow(
                        account_code="2040",
                        account_name="Due to Employee",
                        debit=None,
                        credit="12.90",
                        balance="(12.90)",
                    ),
                ],
                total_balance="(12.90)",
            ),
        ],
        grand_total_balance="0.00",
    )
    csv_text = trial_balance_to_csv(report)
    assert "Trial Balance — As at 28/05/2026" in csv_text
    assert "ASSET" in csv_text
    assert "Account Code,Account Name,Debit,Credit,Balance" in csv_text
    assert "2011,GST Input Tax,1.07,—,1.07" in csv_text
    assert ",,,Total,1.07" in csv_text
    assert "LIABILITY" in csv_text
    assert "2040,Due to Employee,—,12.90,(12.90)" in csv_text
    assert ",,,TOTAL,0.00" in csv_text
