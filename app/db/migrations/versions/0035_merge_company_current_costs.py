"""Join the current-cost inputs with the Development company records.

Two heads came off ``0032_building_units`` independently: the contract-first
construction work added ``0033_contract_payments`` and then
``0034_unit_current_costs``, while ``0033_project_company`` reached main with
the company and bank-account records. Neither knew about the other, so a
database can be on either branch and both are correct histories.

This merges them and nothing else. It creates no table, alters no column and
moves no data, so there is nothing to undo: downgrading it only separates the
two heads again, and each parent keeps its own downgrade rules — including
``0033_contract_payments``, which still refuses to go back once direct-payment
history exists.
"""

revision = "0035_merge_company_current_costs"
down_revision = ("0034_unit_current_costs", "0033_project_company")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
