"""SECURITY_AND_ACCESS.md section 3 role matrix."""

from astrasync_api.contract.interfaces import (
    CriterionResolver,
    EvidenceDraftAgent,
    RFMethod,
    SourceAdapter,
)
from astrasync_api.contract.permissions import ROLE_CAPABILITIES, Capability, Role, capabilities_for


def test_every_role_has_a_defined_policy() -> None:
    assert set(ROLE_CAPABILITIES) == set(Role)


def test_no_roles_grant_nothing() -> None:
    assert capabilities_for(set()) == frozenset()


def test_analyst_can_work_but_cannot_decide_or_administer() -> None:
    granted = capabilities_for({Role.ANALYST})
    assert {Capability.ANALYSIS_RUN, Capability.DRAFT_CREATE, Capability.UPLOAD_MANAGE} <= granted
    assert Capability.REVIEW_DECIDE not in granted
    assert Capability.ADMIN_ALERT_RULES not in granted


def test_reviewer_can_decide_but_rerun_needs_an_extra_grant() -> None:
    granted = capabilities_for({Role.REVIEWER})
    assert Capability.REVIEW_DECIDE in granted
    assert Capability.ANALYSIS_RUN not in granted
    assert Capability.UPLOAD_MANAGE not in granted


def test_administrator_does_not_implicitly_read_cases_sources_or_approve() -> None:
    granted = capabilities_for({Role.ADMINISTRATOR})
    assert {Capability.ADMIN_ALERT_RULES, Capability.ADMIN_SOURCE_CHECK} <= granted
    assert not {
        Capability.CASE_READ,
        Capability.SOURCE_READ,
        Capability.SOURCE_DOWNLOAD,
        Capability.REVIEW_DECIDE,
        Capability.CASE_EXPORT,
    } & granted


def test_demo_viewer_is_read_only() -> None:
    granted = capabilities_for({Role.DEMO_VIEWER})
    assert not {
        Capability.ANALYSIS_RUN,
        Capability.DRAFT_CREATE,
        Capability.REVIEW_DECIDE,
        Capability.UPLOAD_MANAGE,
        Capability.INGEST_TRIGGER,
        Capability.SOURCE_DOWNLOAD,
        Capability.ALERT_ACKNOWLEDGE,
    } & granted


def test_rf_method_protocol_is_satisfied_structurally_without_importing_the_backend() -> None:
    """A core-lib method needs only the BSD shape. No RF logic lives on this side."""

    class ExternalMethod:
        method_id = "DEMO_METHOD"
        method_version = "DEMO"

        def assess_applicability(self, scenario: dict) -> dict:
            return {}

        def calculate(self, scenario: dict) -> dict:
            return {}

    assert isinstance(ExternalMethod(), RFMethod)
    assert not isinstance(object(), RFMethod)
    assert not isinstance(object(), CriterionResolver)
    assert not isinstance(object(), SourceAdapter)
    assert not isinstance(object(), EvidenceDraftAgent)
