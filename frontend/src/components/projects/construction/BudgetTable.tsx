"use client";
import { Badge, Button, Card, IdentityCell, TableScroll } from "@/components/ui";
import type { BudgetDetail, BudgetLine } from "@/lib/api";
import { businessDate, money } from "@/lib/format";
import { budgetLabel, budgetTone, headroomTone } from "./labels";

/** Amounts and headroom are supplied by the server, never recomputed here. */
export function BudgetTable({ detail, onEdit, editableCodes }: { detail: BudgetDetail; onEdit?: (line: BudgetLine) => void; editableCodes?: Set<string> }) {
  const code = detail.currency_code;

  return (
    <Card
      flush
      title={`Budget version ${detail.version_number}`}
      description={`Effective ${businessDate(detail.effective_date)}. ${detail.change_reason}`}
      actions={
        <Badge tone={budgetTone(detail.status)}>
          {budgetLabel(detail.status)}
        </Badge>
      }
    >
      <TableScroll label="Budget by cost code" fixedFirst>
        <thead>
          <tr>
            <th scope="col">Cost code</th>
            <th scope="col">Category</th>
            {onEdit ? <th scope="col">Action</th> : null}
            <th scope="col" className="num">
              Baseline
            </th>
            <th scope="col" className="num">
              Approved
            </th>
            <th scope="col" className="num">
              Contingency
            </th>
            <th scope="col" className="num">
              Control budget
            </th>
            <th scope="col" className="num">
              Committed
            </th>
            <th scope="col" className="num">
              Headroom
            </th>
          </tr>
        </thead>
        <tbody>
          {detail.lines.map((line) => (
            <tr key={line.cost_code_id}>
              <td>
                <IdentityCell
                  name={line.cost_code}
                  meta={[line.cost_code_name, line.funding_source, line.notes].filter(Boolean).join(" · ")}
                />
              </td>
              <td>{line.cost_category}</td>
              {onEdit ? <td><Button small disabled={!editableCodes?.has(line.cost_code_id)} title={!editableCodes?.has(line.cost_code_id) ? "Retired cost code: read-only" : undefined} onClick={() => onEdit(line)}>Edit {line.cost_code}</Button></td> : null}
              <td className="num">{money(line.baseline_amount, code)}</td>
              <td className="num">
                {money(line.approved_budget_amount, code)}
              </td>
              <td className="num">
                {money(line.contingency_amount, code)}
              </td>
              <td className="num">{money(line.control_budget, code)}</td>
              <td className="num">
                {money(line.revised_commitment, code)}
              </td>
              <td
                className={
                  headroomTone(line.headroom) === "danger"
                    ? "num figure-danger"
                    : "num"
                }
              >
                {money(line.headroom, code)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={onEdit ? 3 : 2}>
              Project
            </th>
            <td className="num">{money(detail.total_baseline, code)}</td>
            <td className="num">
              {money(detail.total_approved_budget, code)}
            </td>
            <td className="num">{money(detail.total_contingency, code)}</td>
            <td className="num">
              {money(detail.total_control_budget, code)}
            </td>
            <td className="num" />
            <td className="num" />
          </tr>
        </tfoot>
      </TableScroll>
    </Card>
  );
}
