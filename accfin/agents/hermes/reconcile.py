"""Rule-based reconciliation match suggestions — MVP stub for `04` §6.6."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.hermes import (
    MatchSuggestion,
    ReconciliationBankItem,
    ReconciliationLedgerItem,
    SuggestMatchesOutput,
    SuggestMatchesRequest,
    SuggestMatchesResponse,
)


def suggest_matches_stub(request: SuggestMatchesRequest) -> SuggestMatchesResponse:
    """Pair unmatched items by closest amount within tolerance."""
    suggestions: list[MatchSuggestion] = []
    used_ledger: set = set()
    pct = Decimal(str(request.tolerance_amount_pct))

    for bank in request.unmatched_bank_items:
        bank_amt = Decimal(bank.amount)
        best: ReconciliationLedgerItem | None = None
        best_score = Decimal("0")
        for ledger in request.unmatched_ledger_items:
            if ledger.id in used_ledger:
                continue
            led_amt = Decimal(ledger.amount)
            base = max(abs(bank_amt), abs(led_amt), Decimal("0.01"))
            diff_ratio = abs(bank_amt - led_amt) / base
            if diff_ratio > pct:
                continue
            score = Decimal("1") - diff_ratio
            if score > best_score:
                best_score = score
                best = ledger
        if best is None:
            continue
        confidence = float(min(best_score, Decimal("0.92")))
        if confidence < 0.80:
            continue
        used_ledger.add(best.id)
        suggestions.append(
            MatchSuggestion(
                bank_item_id=bank.id,
                ledger_item_id=best.id,
                confidence=confidence,
                match_reason="amount_within_tolerance + description_similarity",
            )
        )

    unresolvable_bank = [
        b.id
        for b in request.unmatched_bank_items
        if b.id not in {s.bank_item_id for s in suggestions}
    ]
    unresolvable_ledger = [
        l.id
        for l in request.unmatched_ledger_items
        if l.id not in {s.ledger_item_id for s in suggestions}
    ]
    return SuggestMatchesResponse(
        output=SuggestMatchesOutput(
            suggestions=suggestions,
            unresolvable_bank_items=unresolvable_bank,
            unresolvable_ledger_items=unresolvable_ledger,
        )
    )
