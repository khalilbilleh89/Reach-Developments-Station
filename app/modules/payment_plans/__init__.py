"""Payment plans: how a frozen contract price is scheduled to be paid.

Scheduled is not collected. Nothing in this module records money arriving —
PR-MVP-07 owns receipts, allocation and settlement. A plan says what the buyer
contracted to pay, how much, when, and which event makes each amount due.
"""
