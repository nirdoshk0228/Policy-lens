"""
Deterministic claim estimate.

The LLM is never trusted with arithmetic. It reads the policy clauses (via search),
pulls out the numbers (room rent limit, co-pay %, waiting period) and passes them
here. This function applies the rules in a fixed order and returns every step,
so the user can audit the result.

Order of rules (common pattern in Indian health policies):
  1. Waiting period check   -> if not served (and not an accident), payable = 0
  2. Room rent capping      -> excess room rent not paid
  3. Proportionate deduction on "associated" expenses if room is above limit
     (medicines, implants and consumables are usually exempt)
  4. Treatment sub-limit (e.g. cataract: 25% of SI or Rs 40,000 per eye)
  5. Co-payment %
  6. Cap at remaining sum insured
"""

from __future__ import annotations


def calculate_claim(
    total_bill: float,
    sum_insured: float,
    days_admitted: int,
    room_rent_per_day: float,
    room_rent_limit_per_day: float | None = None,
    room_rent_limit_pct_of_si: float | None = None,
    non_proportionate_amount: float = 0.0,
    sub_limit_pct_of_si: float | None = None,
    sub_limit_amount: float | None = None,
    copay_pct: float = 0.0,
    already_claimed_this_year: float = 0.0,
    months_since_policy_start: float | None = None,
    waiting_period_months: float | None = None,
    is_accident: bool = False,
) -> dict:
    steps: list[str] = []

    if min(total_bill, sum_insured, room_rent_per_day) < 0 or days_admitted < 0:
        raise ValueError("Amounts and days must be non-negative")

    # 1. Waiting period
    if waiting_period_months is not None and months_since_policy_start is not None:
        if months_since_policy_start < waiting_period_months and not is_accident:
            steps.append(
                f"Waiting period of {waiting_period_months:g} months not completed "
                f"(policy is {months_since_policy_start:g} months old) -> claim not payable."
            )
            return _result(total_bill, 0.0, steps, status="rejected_waiting_period")
        steps.append(f"Waiting period ({waiting_period_months:g} months) satisfied or accident -> continue.")

    # 2 & 3. Room rent limit and proportionate deduction
    # Policies often say "2% of SI, max Rs 5,000/day" -> the lower of the two applies
    rr_caps = []
    if room_rent_limit_pct_of_si is not None:
        pct_cap = sum_insured * room_rent_limit_pct_of_si / 100
        rr_caps.append(pct_cap)
        steps.append(f"{room_rent_limit_pct_of_si:g}% of ₹{_inr(sum_insured)} = ₹{_inr(pct_cap)}/day.")
    if room_rent_limit_per_day is not None:
        rr_caps.append(room_rent_limit_per_day)
    limit = min(rr_caps) if rr_caps else None
    if len(rr_caps) == 2:
        steps.append(f"Room rent limit = lower of the two = ₹{_inr(limit)}/day.")

    room_total = room_rent_per_day * days_admitted
    if room_total > total_bill:
        raise ValueError("Room rent total cannot exceed the total bill")
    payable = total_bill

    if limit is not None and room_rent_per_day > limit:
        ratio = limit / room_rent_per_day
        eligible_room = limit * days_admitted
        associated = total_bill - room_total - non_proportionate_amount
        if associated < 0:
            raise ValueError("non_proportionate_amount + room rent cannot exceed total bill")
        paid_associated = associated * ratio
        payable = eligible_room + paid_associated + non_proportionate_amount
        steps.append(
            f"Room taken ₹{_inr(room_rent_per_day)}/day > limit ₹{_inr(limit)}/day -> "
            f"room rent paid ₹{_inr(eligible_room)} of ₹{_inr(room_total)}."
        )
        steps.append(
            f"Proportionate ratio = {limit:,.0f}/{room_rent_per_day:,.0f} = {ratio:.2%}. "
            f"Associated expenses ₹{_inr(associated)} -> paid ₹{_inr(paid_associated)}."
        )
        if non_proportionate_amount:
            steps.append(f"Items exempt from proportionate deduction (e.g. medicines) ₹{_inr(non_proportionate_amount)} paid in full.")
    elif limit is not None:
        steps.append(f"Room rent ₹{_inr(room_rent_per_day)}/day within limit -> no deduction.")

    # 4. Treatment sub-limit: lower of "% of SI" and a rupee cap, whichever are given
    caps = []
    if sub_limit_pct_of_si is not None:
        caps.append(sum_insured * sub_limit_pct_of_si / 100)
    if sub_limit_amount is not None:
        caps.append(sub_limit_amount)
    if caps:
        cap = min(caps)
        steps.append(f"Treatment sub-limit = ₹{_inr(cap)}"
                     + (f" (lower of {sub_limit_pct_of_si:g}% of SI and ₹{_inr(sub_limit_amount)})" if len(caps) == 2 else "")
                     + ".")
        if payable > cap:
            steps.append(f"Admissible amount ₹{_inr(payable)} capped at ₹{_inr(cap)}.")
            payable = cap

    # 5. Co-payment
    if copay_pct:
        copay = payable * copay_pct / 100
        payable -= copay
        steps.append(f"Co-payment {copay_pct:g}% = ₹{_inr(copay)} borne by insured.")

    # 6. Sum insured cap
    remaining = max(sum_insured - already_claimed_this_year, 0)
    if payable > remaining:
        steps.append(f"Capped at remaining sum insured ₹{_inr(remaining)}.")
        payable = remaining

    return _result(total_bill, payable, steps, status="payable")


def _inr(x: float) -> str:
    """Indian digit grouping: 166250 -> '1,66,250'."""
    n = str(int(round(abs(x))))
    head, tail = n[:-3], n[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    out = (head + "," + tail) if head else tail
    return ("-" if x < 0 else "") + out


def _result(bill: float, payable: float, steps: list[str], status: str) -> dict:
    payable = round(payable, 2)
    return {
        "status": status,
        "total_bill": round(bill, 2),
        "estimated_payable": payable,
        "out_of_pocket": round(bill - payable, 2),
        "steps": steps,
        "disclaimer": "Estimate only; final amount depends on the insurer's assessment, sub-limits and non-payable items.",
    }
