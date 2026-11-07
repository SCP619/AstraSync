"""Test-only stand-ins for the Data/AI contributor's components.

NOT RF methods, regulatory rules or an AI. They hold no formula and no limit: the "method" echoes
a number placed in a synthetic scenario, the "resolver" echoes a made-up criterion from it, and
the "agent" fills a fixed sentence. They exist to exercise the workflow around real components.
"""

import hashlib
from collections.abc import Mapping
from typing import Any

DEMO_UNIT = "DEMO-UNIT"


class DemoEchoMethod:
    method_id = "DEMO_ECHO_NOT_RF"
    method_version = "demo/1"

    def assess_applicability(self, scenario: dict[str, Any]) -> dict[str, Any]:
        ready = "demo_value" in scenario
        return {
            "method_id": self.method_id,
            "method_version": self.method_version,
            "applicability": "APPLICABLE" if ready else "INSUFFICIENT_DATA",
            "reason_codes": [] if ready else ["MISSING_REQUIRED_INPUT"],
            "missing_fields": [] if ready else ["demo_value"],
            "metric_kind": scenario.get("demo_metric", "PFD"),
        }

    def calculate(self, scenario: dict[str, Any]) -> dict[str, Any]:
        value = scenario["demo_value"]
        return {
            "method_id": self.method_id,
            "method_version": self.method_version,
            "metric_kind": scenario.get("demo_metric", "PFD"),
            "numeric_value": value,
            "unit": DEMO_UNIT,
            "reference_bandwidth_hz": scenario.get("demo_bandwidth_hz"),
            "time_percentage": None,
            "location_percentage": None,
            "inputs": {"demo_value": value},
            "assumptions": ["Echoed from a synthetic scenario. This is not a calculation."],
            "diagnostics": {},
            "result_trace": {},
            "implementation_sha": "demo",
            "calculation_sha256": hashlib.sha256(str(value).encode()).hexdigest(),
        }


class DemoEchoResolver:
    """Returns ``demo_criteria`` from the synthetic scenario, unchanged."""

    def resolve(
        self, method_run: Mapping[str, Any], context: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        return list(context["scenario"].get("demo_criteria", []))


class DemoDraftAgent:
    model_id = "demo-template-not-ai"

    def create_draft(self, case_evidence: Mapping[str, Any], draft_type: str) -> dict[str, Any]:
        evidence = [item["evidence_id"] for item in case_evidence["evidence"]]
        return {
            "draft_type": draft_type,
            "analysis_run_id": case_evidence["analysis_run_id"],
            "explanation_markdown": "Fixed template used for testing.",
            "uncertainties": ["This text came from a test template, not an AI."],
            "cited_evidence_ids": evidence,
            "draft_markdown": (
                f"[Unapproved test template] Please provide further technical details for "
                f"notice {case_evidence['notice_id']}."
            ),
            "requires_human_review": True,
        }
