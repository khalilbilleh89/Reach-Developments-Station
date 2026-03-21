"""
finance.revenue_recognition

Core revenue recognition engine.

Recognition model (v1 — cash-based):
  recognized_revenue = SUM(amount) for installments with status='paid'
  deferred_revenue   = contract_total − recognized_revenue
  recognition_percentage = recognized_revenue / contract_total * 100
                           (0.0 when contract_total is zero)

Rules:
  - Deferred revenue is clamped to zero; it cannot go negative even when
    paid amounts exceed the contract price (e.g. due to rounding).
  - Recognition percentage is clamped to [0, 100].
  - No SQL is embedded here; all data access is delegated to the caller.
"""

from dataclasses import dataclass

from app.modules.finance.schemas import RevenueRecognitionResponse


@dataclass(frozen=True)
class ContractRevenueData:
    """Raw contract data required by the recognition engine."""

    contract_id: str
    contract_total: float
    paid_amount: float


def calculate_contract_revenue_recognition(
    data: ContractRevenueData,
) -> RevenueRecognitionResponse:
    """Compute recognized and deferred revenue for a contract.

    Parameters
    ----------
    data:
        Immutable data transfer object carrying the contract total and the
        sum of all paid installment amounts.  Constructed by the service
        layer; no database access occurs here.

    Returns
    -------
    RevenueRecognitionResponse
        Pydantic schema ready to be returned from an API endpoint.
    """
    contract_total = round(data.contract_total, 2)
    recognized = round(min(data.paid_amount, contract_total), 2)
    deferred = round(max(contract_total - recognized, 0.0), 2)

    if contract_total > 0:
        percentage = round(min(recognized / contract_total * 100, 100.0), 4)
    else:
        percentage = 0.0

    return RevenueRecognitionResponse(
        contract_id=data.contract_id,
        contract_total=contract_total,
        recognized_revenue=recognized,
        deferred_revenue=deferred,
        recognition_percentage=percentage,
    )
