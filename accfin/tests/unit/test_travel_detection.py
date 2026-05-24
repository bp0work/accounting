"""Travel category detection for expense claims."""

from workers.common.travel_detection import (
    claim_requires_travel_request,
    is_travel_related_line_item,
)


def test_home_office_not_travel():
    assert not claim_requires_travel_request(
        [{"category": "other", "description": "Home office expense reimbursement"}]
    )


def test_hotel_is_travel():
    assert is_travel_related_line_item(category="accommodation", description="Hotel stay")
    assert claim_requires_travel_request(
        [{"category": "accommodation", "description": "Hotel in Singapore"}]
    )


def test_grab_in_description():
    assert claim_requires_travel_request(
        [{"category": "other", "description": "Grab ride to airport"}]
    )


def test_meals_only_not_travel():
    assert not claim_requires_travel_request(
        [{"category": "meals", "description": "Team lunch"}]
    )
