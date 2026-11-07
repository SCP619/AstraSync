"""Deny-by-default role capabilities (SECURITY_AND_ACCESS.md section 3).

A capability is necessary but never sufficient: tenant, classification, source entitlement and
case access are checked separately for each object. Roles come only from server-validated
identity, never from a client request.
"""

from enum import StrEnum


class Role(StrEnum):
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"
    ADMINISTRATOR = "ADMINISTRATOR"
    DEMO_VIEWER = "DEMO_VIEWER"


class Capability(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    CASE_READ = "CASE_READ"
    ISSUE_READ = "ISSUE_READ"
    ANALYSIS_READ = "ANALYSIS_READ"
    ANALYSIS_RUN = "ANALYSIS_RUN"
    DRAFT_CREATE = "DRAFT_CREATE"
    DRAFT_READ = "DRAFT_READ"
    REVIEW_DECIDE = "REVIEW_DECIDE"
    CASE_EXPORT = "CASE_EXPORT"
    UPLOAD_MANAGE = "UPLOAD_MANAGE"
    INGEST_TRIGGER = "INGEST_TRIGGER"
    JOB_READ = "JOB_READ"
    REFERENCE_READ = "REFERENCE_READ"
    SOURCE_HEALTH_READ = "SOURCE_HEALTH_READ"
    SOURCE_READ = "SOURCE_READ"
    SOURCE_DOWNLOAD = "SOURCE_DOWNLOAD"
    ALERT_READ = "ALERT_READ"
    ALERT_ACKNOWLEDGE = "ALERT_ACKNOWLEDGE"
    ALERT_PREFERENCES = "ALERT_PREFERENCES"
    DEVICE_MANAGE = "DEVICE_MANAGE"
    ADMIN_ALERT_RULES = "ADMIN_ALERT_RULES"
    ADMIN_SOURCE_CHECK = "ADMIN_SOURCE_CHECK"
    # Manage users, roles and source entitlements in the administrator's own tenant. It grants
    # no access to case or source content (DECISIONS G26).
    ADMIN_USERS = "ADMIN_USERS"


_READ_ONLY_WORKSPACE = frozenset(
    {
        Capability.AUTHENTICATED,
        Capability.CASE_READ,
        Capability.ISSUE_READ,
        Capability.ANALYSIS_READ,
        Capability.REFERENCE_READ,
        Capability.SOURCE_HEALTH_READ,
        Capability.SOURCE_READ,
        Capability.ALERT_READ,
        Capability.DRAFT_READ,
    }
)

_NOTIFICATIONS = frozenset(
    {Capability.ALERT_ACKNOWLEDGE, Capability.ALERT_PREFERENCES, Capability.DEVICE_MANAGE}
)

ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ANALYST: _READ_ONLY_WORKSPACE
    | _NOTIFICATIONS
    | {
        Capability.ANALYSIS_RUN,
        Capability.DRAFT_CREATE,
        Capability.UPLOAD_MANAGE,
        Capability.INGEST_TRIGGER,
        Capability.JOB_READ,
        Capability.SOURCE_DOWNLOAD,
    },
    # Reruns are "if granted" in the security matrix, so they need an explicit extra grant.
    Role.REVIEWER: _READ_ONLY_WORKSPACE
    | _NOTIFICATIONS
    | {
        Capability.REVIEW_DECIDE,
        Capability.CASE_EXPORT,
        Capability.JOB_READ,
        Capability.SOURCE_DOWNLOAD,
    },
    # Administrators manage configuration only. Case and source content needs another role.
    Role.ADMINISTRATOR: _NOTIFICATIONS
    | {
        Capability.AUTHENTICATED,
        Capability.JOB_READ,
        Capability.SOURCE_HEALTH_READ,
        Capability.ALERT_READ,
        Capability.ADMIN_ALERT_RULES,
        Capability.ADMIN_SOURCE_CHECK,
        Capability.ADMIN_USERS,
    },
    # Runs only against the separate demo environment with synthetic or redacted data.
    Role.DEMO_VIEWER: _READ_ONLY_WORKSPACE,
}


def capabilities_for(roles: frozenset[Role] | set[Role]) -> frozenset[Capability]:
    """Union of the given roles' capabilities. No roles means no capabilities."""
    granted: frozenset[Capability] = frozenset()
    for role in roles:
        granted |= ROLE_CAPABILITIES[role]
    return granted
