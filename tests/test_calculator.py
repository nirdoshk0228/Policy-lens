import pytest
from tools import calculate_claim


def test_proportionate_deduction():
    # SI 5L, limit 1% = 5000/day, took 8000/day for 4 days, bill 2.5L, medicines 50k
    r = calculate_claim(250000, 500000, 4, 8000, room_rent_limit_pct_of_si=1, non_proportionate_amount=50000)
    room = 5000 * 4                              # 20,000
    associated = 250000 - 8000 * 4 - 50000       # 168,000
    expected = room + associated * 5000 / 8000 + 50000
    assert r["estimated_payable"] == pytest.approx(expected)


def test_no_deduction_within_limit():
    r = calculate_claim(100000, 500000, 2, 4000, room_rent_limit_pct_of_si=1)
    assert r["estimated_payable"] == 100000


def test_copay_and_cap():
    r = calculate_claim(400000, 300000, 2, 3000, copay_pct=10, already_claimed_this_year=50000)
    assert r["estimated_payable"] == 250000  # 360k after copay, capped at 250k remaining


def test_waiting_period_rejects_but_accident_allowed():
    assert calculate_claim(100000, 500000, 2, 3000, months_since_policy_start=12,
                           waiting_period_months=24)["estimated_payable"] == 0
    assert calculate_claim(100000, 500000, 2, 3000, months_since_policy_start=12,
                           waiting_period_months=24, is_accident=True)["estimated_payable"] == 100000


def test_invalid_input():
    with pytest.raises(ValueError):
        calculate_claim(10000, 500000, 5, 4000)  # room rent > bill


def test_room_rent_uses_lower_of_pct_and_cap():
    # Arogya Sanjeevani style: 2% of SI, max 5,000/day. SI 5L -> 10,000 vs 5,000 -> 5,000
    r = calculate_claim(250000, 500000, 4, 8000, room_rent_limit_pct_of_si=2, room_rent_limit_per_day=5000,
                        non_proportionate_amount=50000, copay_pct=5)
    expected = (5000 * 4 + (250000 - 32000 - 50000) * 5000 / 8000 + 50000) * 0.95
    assert r["estimated_payable"] == pytest.approx(expected)  # 166,250


def test_cataract_sub_limit_then_copay():
    # SI 3L: 25% = 75,000 vs 40,000 -> 40,000 cap, then 5% co-pay -> 38,000
    r = calculate_claim(60000, 300000, 1, 3000, sub_limit_pct_of_si=25, sub_limit_amount=40000, copay_pct=5)
    assert r["estimated_payable"] == 38000
