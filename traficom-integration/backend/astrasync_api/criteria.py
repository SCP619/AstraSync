"""A ``CriterionResolver`` that applies only cited, edition-dated and expert-approved criteria.

Criteria come from a JSON registry file named by ``ASTRASYNC_CRITERIA_REGISTRY``. This module
contains no limits: every number comes from that file, and an entry is loaded only if it names its
source document, edition and date, a citation (document, section, URL) and the approval of a
named reviewer. Entries that fail any of these are refused when the file is loaded, never
silently dropped at query time.

For each successful method run the resolver returns:

- ``VERIFIED`` when the metric kind and every declared applicability condition are matched by
  values that are present in the method run or its scenario, so ``analysis.resolve_criteria`` can
  compute the margin (it also checks unit and reference bandwidth itself);
- ``UNVERIFIED`` with the names of the missing values when a declared condition cannot be checked;
- nothing for a criterion whose metric, frequency range or a condition does not match.

Registry format (a list under ``criteria``)::

    {
      "criterion_ref_id": "...", "regulatory_scope": "...",
      "source": {"document": "...", "edition": "...", "edition_date": "YYYY-MM-DD"},
      "citation": {"reference_id": "...", "section_id": "...", "source_url": "https://..."},
      "metric_kind": "PFD", "comparison_operator": "UPPER_BOUND",
      "limit_value": ..., "limit_unit": "...", "limit_reference_bandwidth_hz": ...,
      "frequency_min_hz": ..., "frequency_max_hz": ...,
      "conditions": {"<scenario key>": <value> | [<values>] | {"min": .., "max": ..}},
      "approval": {"approved_by": "...", "approved_at": "YYYY-MM-DD", "review_reference": "..."}
    }
"""

import json
import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from .contract.enums import ComparisonOperator, CriterionApplicability, MetricKind


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceEdition(_Strict):
    document: str = Field(min_length=1)
    edition: str = Field(min_length=1)
    edition_date: date


class Citation(_Strict):
    reference_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    source_url: HttpUrl


class Approval(_Strict):
    approved_by: str = Field(min_length=1)
    approved_at: date
    review_reference: str = Field(min_length=1)


class Range(_Strict):
    min: float | None = None
    max: float | None = None

    def contains(self, value: float) -> bool:
        return (self.min is None or value >= self.min) and (self.max is None or value <= self.max)


Condition = str | float | bool | list[str | float] | Range


class RegisteredCriterion(_Strict):
    criterion_ref_id: str = Field(min_length=1)
    regulatory_scope: str = Field(min_length=1)
    source: SourceEdition
    citation: Citation
    metric_kind: MetricKind
    comparison_operator: ComparisonOperator
    limit_value: float
    limit_unit: str = Field(min_length=1)
    limit_reference_bandwidth_hz: float | None = Field(default=None, gt=0)
    frequency_min_hz: float = Field(ge=0)
    frequency_max_hz: float = Field(gt=0)
    # Where the case frequency is read: a method-run field, a method input or a scenario path
    # such as "space_pfd_free_space.frequency_hz".
    frequency_key: str = "frequency_hz"
    conditions: dict[str, Condition] = Field(default_factory=dict)
    approval: Approval

    @model_validator(mode="after")
    def _ordered_range(self) -> "RegisteredCriterion":
        if self.frequency_max_hz < self.frequency_min_hz:
            raise ValueError("frequency_max_hz is below frequency_min_hz")
        return self


class CriteriaRegistry(_Strict):
    criteria: list[RegisteredCriterion]

    @model_validator(mode="after")
    def _unique_ids(self) -> "CriteriaRegistry":
        ids = [c.criterion_ref_id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion_ref_id values must be unique")
        return self


def _lookup(key: str, method_run: Mapping[str, Any], scenario: Mapping[str, Any]) -> Any:
    """A method-run field, then a method input, then a dotted path in the scenario."""
    if method_run.get(key) is not None:
        return method_run[key]
    inputs = method_run.get("inputs") or {}
    if inputs.get(key) is not None:
        return inputs[key]
    value: Any = scenario
    for part in key.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _matches(condition: Condition, value: Any) -> bool:
    if isinstance(condition, Range):
        return isinstance(value, int | float) and condition.contains(float(value))
    if isinstance(condition, list):
        return value in condition
    return bool(value == condition)


class RegistryCriterionResolver:
    """Loaded from settings as ``astrasync_api.criteria:RegistryCriterionResolver``."""

    def __init__(self, registry: CriteriaRegistry | None = None) -> None:
        if registry is None:
            path = os.environ.get("ASTRASYNC_CRITERIA_REGISTRY")
            if not path:
                raise ValueError("ASTRASYNC_CRITERIA_REGISTRY names no criteria registry file")
            registry = load_registry(Path(path))
        self.registry = registry

    def resolve(
        self, method_run: Mapping[str, Any], context: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        scenario: Mapping[str, Any] = context.get("scenario") or {}
        checks = []
        for criterion in self.registry.criteria:
            if method_run.get("metric_kind") != criterion.metric_kind.value:
                continue
            found = _lookup(criterion.frequency_key, method_run, scenario)
            frequency = float(found) if isinstance(found, int | float) else None
            missing = [] if frequency is not None else [criterion.frequency_key]
            if frequency is not None and not (
                criterion.frequency_min_hz <= frequency <= criterion.frequency_max_hz
            ):
                continue
            mismatch = False
            for key, condition in criterion.conditions.items():
                value = _lookup(key, method_run, scenario)
                if value is None:
                    missing.append(key)
                elif not _matches(condition, value):
                    mismatch = True
            if mismatch:
                continue
            checks.append(_check(criterion, missing))
        return checks


def _check(criterion: RegisteredCriterion, missing: list[str]) -> dict[str, Any]:
    verified = not missing
    return {
        "criterion_ref_id": criterion.criterion_ref_id,
        "regulatory_scope": criterion.regulatory_scope,
        "applicable": (
            CriterionApplicability.VERIFIED if verified else CriterionApplicability.UNVERIFIED
        ).value,
        "matching_conditions": {
            "metric_kind": criterion.metric_kind.value,
            "frequency_min_hz": criterion.frequency_min_hz,
            "frequency_max_hz": criterion.frequency_max_hz,
            **{
                key: (c.model_dump() if isinstance(c, Range) else c)
                for key, c in criterion.conditions.items()
            },
        },
        "limit_value": criterion.limit_value,
        "limit_unit": criterion.limit_unit,
        "limit_reference_bandwidth_hz": criterion.limit_reference_bandwidth_hz,
        "comparison_operator": criterion.comparison_operator.value,
        "review_note": (
            f"{criterion.source.document}, {criterion.source.edition} "
            f"({criterion.source.edition_date.isoformat()}); approved by "
            f"{criterion.approval.approved_by} ({criterion.approval.review_reference})"
            if verified
            else "Applicability cannot be checked; missing: " + ", ".join(sorted(missing))
        ),
        "citation": {
            "reference_id": criterion.citation.reference_id,
            "section_id": criterion.citation.section_id,
            "source_url": str(criterion.citation.source_url),
        },
    }


def load_registry(path: Path) -> CriteriaRegistry:
    """Refuses the whole file if any entry is incomplete, rather than loading part of it."""
    return CriteriaRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))
