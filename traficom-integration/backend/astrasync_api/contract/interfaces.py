"""Seams between the backend and the Data/AI contributor's components.

These are structural protocols, so ``astrasync-core-lib`` and ``agent`` need no import from this
package. Implementations stay with their owner; the backend only orchestrates them and validates
what they return against ``MethodAssessment``, ``MethodCalculation`` and ``AgentDraftResponse``.
"""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RFMethod(Protocol):
    """BSD section 4. Domain, band and input eligibility is assessed before any calculation."""

    method_id: str
    method_version: str

    def assess_applicability(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Return eligibility, missing inputs, domain/metric and reasons."""
        ...

    def calculate(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Return validated result, metric, units, assumptions and trace."""
        ...


@runtime_checkable
class CriterionResolver(Protocol):
    """Selects verified criteria independently of the propagation models (BSD section 4)."""

    def resolve(
        self, method_run: Mapping[str, Any], context: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Return candidate criterion checks; unknown criteria produce a null margin."""
        ...


@runtime_checkable
class SourceAdapter(Protocol):
    """Read-only, format-specific parser run by ingest workers in bounded batches. PROPOSED."""

    source_type: str
    parser_version: str

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterable[list[dict[str, Any]]]:
        """Yield records carrying raw values, source locator and quality findings."""
        ...


@runtime_checkable
class EvidenceDraftAgent(Protocol):
    """Evidence-bound drafting. Receives only permission-checked, immutable case evidence."""

    def create_draft(
        self, case_evidence: Mapping[str, Any], draft_type: str
    ) -> dict[str, Any]:
        """Return a payload matching ``AgentDraftResponse``."""
        ...
