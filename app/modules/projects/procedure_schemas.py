"""Bounded procedure maps; branches describe manual work, never execute code."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.projects.schemas import StrictRequest


class ProcedureText(StrictRequest):
    @field_validator("*", mode="after")
    @classmethod
    def safe_text(cls, value: object) -> object:
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text cannot contain null characters.")
        return value


class ProcedureStep(ProcedureText):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    kind: Literal["start", "action", "decision", "end"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    inputs: str = Field(default="", max_length=2000)
    outputs: str = Field(default="", max_length=2000)
    owner: str = Field(default="", max_length=200)
    next_id: str | None = Field(default=None, max_length=80)
    yes_id: str | None = Field(default=None, max_length=80)
    no_id: str | None = Field(default=None, max_length=80)

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a step title.")
        return value.strip()


class ProcedureFields(ProcedureText):
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(default="", max_length=4000)
    sop: str = Field(default="", max_length=20000)
    inputs: str = Field(default="", max_length=4000)
    outputs: str = Field(default="", max_length=4000)
    steps: list[ProcedureStep] = Field(min_length=2, max_length=100)

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a procedure title.")
        return value.strip()

    @model_validator(mode="after")
    def connected_map(self) -> "ProcedureFields":
        ids = {step.id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Step identifiers must be unique.")
        starts = [step for step in self.steps if step.kind == "start"]
        if len(starts) != 1 or not any(step.kind == "end" for step in self.steps):
            raise ValueError("Include exactly one Start and at least one End.")
        edges: dict[str, list[str]] = {}
        for step in self.steps:
            if step.kind == "decision":
                if not step.yes_id or not step.no_id or step.next_id:
                    raise ValueError("Decisions require Yes and No destinations only.")
                targets = [step.yes_id, step.no_id]
            elif step.kind == "end":
                if step.next_id or step.yes_id or step.no_id:
                    raise ValueError("End steps cannot have outgoing paths.")
                targets = []
            else:
                if not step.next_id or step.yes_id or step.no_id:
                    raise ValueError("Start and action steps require one Next destination.")
                targets = [step.next_id]
            if any(target not in ids for target in targets):
                raise ValueError("Every path must point to an existing step.")
            edges[step.id] = targets
        reached: set[str] = set()
        pending = [starts[0].id]
        while pending:
            current = pending.pop()
            if current not in reached:
                reached.add(current)
                pending.extend(edges[current])
        if reached != ids:
            raise ValueError("Every step must be reachable from Start.")
        ending = {step.id for step in self.steps if step.kind == "end"}
        while True:
            expanded = ending | {
                key for key, targets in edges.items() if any(t in ending for t in targets)
            }
            if expanded == ending:
                break
            ending = expanded
        if ending != ids:
            raise ValueError(
                "Every step needs a possible path to End; closed loops are not allowed."
            )
        return self


class ProcedureUpdate(ProcedureFields):
    version: int = Field(ge=1)


class ProcedureRemoval(ProcedureText):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class ProcedureRead(ProcedureFields):
    id: uuid.UUID
    project_id: uuid.UUID
    version: int


class ProcedureDirectory(BaseModel):
    procedures: list[ProcedureRead]
    can_manage: bool
