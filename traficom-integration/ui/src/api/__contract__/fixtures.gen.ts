// GENERATED from traficom-integration/contract. Do not edit.

import type { components } from "../schema.gen";

// AlertRuleUpsert.verified_exceedance.json
export const fixture0 = {
  "trigger_kind": "POTENTIAL_EXCEEDANCE",
  "severity": "HIGH",
  "enabled": true,
  "evidence_requirement": "VERIFIED_CRITERION_AND_METHOD_RUN",
  "routing_roles": [
    "REVIEWER"
  ],
  "dedupe_window_seconds": 3600
} satisfies components["schemas"]["AlertRuleUpsert"];

// AlertSummary.review.json
export const fixture1 = {
  "alert_id": "DEMO-ALERT-001",
  "event_id": "DEMO-EVENT-001",
  "case_id": "DEMO-SPACE-001",
  "rule_id": "DEMO-RULE-001",
  "rule_version": 1,
  "severity": "REVIEW",
  "safe_title": "Case needs review",
  "safe_preview": "Open AstraSync to view details.",
  "status": "OPEN",
  "created_at_utc": "2026-11-07T12:00:00Z",
  "expires_at_utc": null,
  "is_synthetic": true
} satisfies components["schemas"]["AlertSummary"];

// AnalysisRun.mixed_method_states.json
export const fixture2 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "analysis_run_id": "DEMO-RUN-001",
  "case_id": "DEMO-SPACE-002",
  "scenario_id": "DEMO-SCENARIO-001",
  "is_synthetic": true,
  "run_created_at_utc": "2026-11-07T12:00:00Z",
  "input_snapshot_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "software_commit_sha": "DEMO-SHA",
  "method_registry_version": "DEMO",
  "reference_snapshot_sha256": null,
  "analysis_status": "READY",
  "created_by": "DEMO-USER-001",
  "method_runs": [
    {
      "analysis_run_id": "DEMO-RUN-001",
      "scenario_id": "DEMO-SCENARIO-001",
      "standard_ref_id": null,
      "role": "SCREENING",
      "reference_bandwidth_hz": null,
      "time_percentage": null,
      "location_percentage": null,
      "receiver_site_id": null,
      "satellite_epoch_utc": null,
      "inputs": {},
      "assumptions": [
        "Schema fixture only; not a calculation"
      ],
      "diagnostics": {},
      "result_trace": {},
      "method_run_id": "DEMO-MR-001",
      "method_id": "SPACE_EPFD_NGSO",
      "method_version": "DEMO-NOT-A-CALCULATION",
      "applicability": "INSUFFICIENT_DATA",
      "execution_status": "NOT_RUN",
      "reason_codes": [
        "MISSING_REQUIRED_INPUT"
      ],
      "missing_fields": [
        "constellation_definition"
      ],
      "metric_kind": "EPFD",
      "numeric_value": null,
      "unit": null,
      "implementation_sha": null,
      "calculation_sha256": null
    },
    {
      "analysis_run_id": "DEMO-RUN-001",
      "scenario_id": "DEMO-SCENARIO-001",
      "standard_ref_id": null,
      "role": "SCREENING",
      "reference_bandwidth_hz": 1000000.0,
      "time_percentage": null,
      "location_percentage": null,
      "receiver_site_id": null,
      "satellite_epoch_utc": null,
      "inputs": {},
      "assumptions": [
        "Schema fixture only; not a calculation"
      ],
      "diagnostics": {},
      "result_trace": {},
      "method_run_id": "DEMO-MR-002",
      "method_id": "SPACE_PFD_FREE_SPACE",
      "method_version": "DEMO-NOT-A-CALCULATION",
      "applicability": "APPLICABLE",
      "execution_status": "SUCCEEDED",
      "reason_codes": [],
      "missing_fields": [],
      "metric_kind": "PFD",
      "numeric_value": -102.3,
      "unit": "DEMO-UNIT",
      "implementation_sha": "DEMO-SHA",
      "calculation_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "criterion_checks": [
    {
      "criterion_check_id": "DEMO-CC-001",
      "method_run_id": "DEMO-MR-002",
      "criterion_ref_id": "DEMO-CRITERION-NOT-REAL",
      "regulatory_scope": "DEMO",
      "applicable": "VERIFIED",
      "matching_conditions": {},
      "limit_value": -100.0,
      "limit_unit": "DEMO-UNIT",
      "limit_reference_bandwidth_hz": 1000000.0,
      "comparison_operator": "UPPER_BOUND",
      "margin_db": -2.3,
      "comparison_status": "COMPARED",
      "review_note": null,
      "citation": {
        "reference_id": "DEMO-REF-001",
        "section_id": "DEMO-SECTION",
        "source_url": "https://example.invalid/demo"
      }
    }
  ]
} satisfies components["schemas"]["AnalysisRun"];

// CaseDetail.insufficient_data.json
export const fixture3 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "case_id": "DEMO-SPACE-001",
  "is_synthetic": true,
  "domain": "SPACE",
  "notice_id": "SYNTHETIC-NOTICE-001",
  "source_issue_id": "DEMO-IFIC-001",
  "administration": "DEMO",
  "change_type": "NEW",
  "frequency_start_mhz": 10700.0,
  "frequency_end_mhz": 10720.0,
  "relevance_label": "FREQUENCY_MATCH",
  "method_summary": {
    "succeeded": 0,
    "candidates": 3
  },
  "lead_metric": {
    "metric_kind": "PFD",
    "numeric_value": null,
    "unit": null
  },
  "margin_db": null,
  "criterion_status": null,
  "finding_status": "INSUFFICIENT_DATA",
  "review_status": "NEW",
  "relevance": {
    "label": "FREQUENCY_MATCH",
    "reason_codes": [
      "BAND_OVERLAP"
    ],
    "rule_version": "DEMO",
    "overlap_start_mhz": 10700.0,
    "overlap_end_mhz": 10720.0,
    "frequency_match": true,
    "service_match": null,
    "geometry_match": null,
    "technical_data_ready": false,
    "criterion_available": false
  },
  "evidence": [
    {
      "evidence_id": "DEMO-EVIDENCE-001",
      "label": "Synthetic source row",
      "entity_type": "source_record",
      "entity_id": "DEMO-RECORD-001",
      "source_issue_id": "DEMO-IFIC-001",
      "reference_id": null,
      "source_locator": "demo-sheet!row-1",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "verified_at_utc": null,
      "note": null
    }
  ],
  "latest_analysis_run_id": null,
  "priority": null,
  "priority_reason": null,
  "owner": null,
  "reviewer_decision": null,
  "created_at_utc": "2026-11-07T12:00:00Z",
  "updated_at_utc": "2026-11-07T12:00:00Z"
} satisfies components["schemas"]["CaseDetail"];

// CaseList.single_page.json
export const fixture4 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "items": [
    {
      "case_id": "DEMO-SPACE-001",
      "is_synthetic": true,
      "domain": "SPACE",
      "notice_id": "SYNTHETIC-NOTICE-001",
      "source_issue_id": "DEMO-IFIC-001",
      "administration": "DEMO",
      "change_type": "NEW",
      "frequency_start_mhz": 10700.0,
      "frequency_end_mhz": 10720.0,
      "relevance_label": "FREQUENCY_MATCH",
      "method_summary": {
        "succeeded": 0,
        "candidates": 3
      },
      "lead_metric": {
        "metric_kind": "PFD",
        "numeric_value": null,
        "unit": null
      },
      "margin_db": null,
      "criterion_status": null,
      "finding_status": "INSUFFICIENT_DATA",
      "review_status": "NEW"
    }
  ],
  "limit": 50,
  "next_cursor": null,
  "total_if_known": null
} satisfies components["schemas"]["CaseList"];

// CaseSummary.frequency_match_insufficient_data.json
export const fixture5 = {
  "case_id": "DEMO-SPACE-001",
  "is_synthetic": true,
  "domain": "SPACE",
  "notice_id": "SYNTHETIC-NOTICE-001",
  "source_issue_id": "DEMO-IFIC-001",
  "administration": "DEMO",
  "change_type": "NEW",
  "frequency_start_mhz": 10700.0,
  "frequency_end_mhz": 10720.0,
  "relevance_label": "FREQUENCY_MATCH",
  "method_summary": {
    "succeeded": 0,
    "candidates": 3
  },
  "lead_metric": {
    "metric_kind": "PFD",
    "numeric_value": null,
    "unit": null
  },
  "margin_db": null,
  "criterion_status": null,
  "finding_status": "INSUFFICIENT_DATA",
  "review_status": "NEW"
} satisfies components["schemas"]["CaseSummary"];

// CaseSummary.verified_negative_margin.json
export const fixture6 = {
  "case_id": "DEMO-SPACE-002",
  "is_synthetic": true,
  "domain": "SPACE",
  "notice_id": "SYNTHETIC-NOTICE-001",
  "source_issue_id": "DEMO-IFIC-001",
  "administration": "DEMO",
  "change_type": "NEW",
  "frequency_start_mhz": 10700.0,
  "frequency_end_mhz": 10720.0,
  "relevance_label": "FREQUENCY_MATCH",
  "method_summary": {
    "succeeded": 1,
    "candidates": 3
  },
  "lead_metric": {
    "metric_kind": "PFD",
    "numeric_value": -102.3,
    "unit": "DEMO-UNIT"
  },
  "margin_db": -2.3,
  "criterion_status": "VERIFIED",
  "finding_status": "POTENTIAL_LIMIT_EXCEEDANCE",
  "review_status": "NEW"
} satisfies components["schemas"]["CaseSummary"];

// CaseSummary.verified_positive_margin.json
export const fixture7 = {
  "case_id": "DEMO-SPACE-002",
  "is_synthetic": true,
  "domain": "SPACE",
  "notice_id": "SYNTHETIC-NOTICE-001",
  "source_issue_id": "DEMO-IFIC-001",
  "administration": "DEMO",
  "change_type": "NEW",
  "frequency_start_mhz": 10700.0,
  "frequency_end_mhz": 10720.0,
  "relevance_label": "FREQUENCY_MATCH",
  "method_summary": {
    "succeeded": 1,
    "candidates": 3
  },
  "lead_metric": {
    "metric_kind": "PFD",
    "numeric_value": -102.3,
    "unit": "DEMO-UNIT"
  },
  "margin_db": 2.3,
  "criterion_status": "VERIFIED",
  "finding_status": "POTENTIAL_LIMIT_EXCEEDANCE",
  "review_status": "NEW"
} satisfies components["schemas"]["CaseSummary"];

// DraftCreated.unapproved.json
export const fixture8 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "draft_id": "DEMO-DRAFT-001",
  "case_id": "DEMO-SPACE-001",
  "draft_type": "REQUEST_INFORMATION",
  "source_analysis_run_id": "DEMO-RUN-001",
  "content_markdown": "[Unapproved illustrative draft]",
  "citations": [
    "DEMO-EVIDENCE-001"
  ],
  "warnings": [],
  "ai_model_id": null,
  "generation_provenance": "DEMO",
  "status": "DRAFT",
  "requires_human_review": true,
  "created_at_utc": "2026-11-07T12:00:00Z"
} satisfies components["schemas"]["DraftCreated"];

// ErrorResponse.forbidden.json
export const fixture9 = {
  "error": {
    "code": "FORBIDDEN",
    "message": "Not permitted.",
    "details": {},
    "request_id": "demo-request"
  }
} satisfies components["schemas"]["ErrorResponse"];

// JobRun.unknown_total.json
export const fixture10 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "job_id": "DEMO-JOB-001",
  "job_type": "INGEST",
  "resource_id": "DEMO-UPLOAD-001",
  "status": "PARSING",
  "progress_stage": "PARSING",
  "processed_bytes": 1024,
  "processed_records": 10,
  "total_records_if_known": null,
  "attempt": 1,
  "max_attempts": 3,
  "started_at_utc": "2026-11-07T12:00:00Z",
  "finished_at_utc": null,
  "error_code": null
} satisfies components["schemas"]["JobRun"];

// Me.analyst.json
export const fixture11 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "user_id": "DEMO-USER-001",
  "tenant_id": "DEMO-TENANT-001",
  "environment": "DEMO",
  "roles": [
    "ANALYST"
  ],
  "capabilities": [
    "AUTHENTICATED",
    "CASE_READ"
  ]
} satisfies components["schemas"]["Me"];

// MethodAssessment.insufficient_data.json
export const fixture12 = {
  "method_id": "SPACE_PFD_FREE_SPACE",
  "method_version": "DEMO",
  "applicability": "INSUFFICIENT_DATA",
  "reason_codes": [],
  "missing_fields": [
    "slant_range_m"
  ],
  "metric_kind": "PFD"
} satisfies components["schemas"]["MethodAssessment"];

// MethodMatrix.commensurate_pfd_group.json
export const fixture13 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "analysis_run_id": "DEMO-RUN-001",
  "is_synthetic": true,
  "method_runs": [
    {
      "analysis_run_id": "DEMO-RUN-001",
      "scenario_id": "DEMO-SCENARIO-001",
      "standard_ref_id": null,
      "role": "SCREENING",
      "reference_bandwidth_hz": 1000000.0,
      "time_percentage": null,
      "location_percentage": null,
      "receiver_site_id": null,
      "satellite_epoch_utc": null,
      "inputs": {},
      "assumptions": [
        "Schema fixture only; not a calculation"
      ],
      "diagnostics": {},
      "result_trace": {},
      "method_run_id": "DEMO-MR-002",
      "method_id": "SPACE_PFD_FREE_SPACE",
      "method_version": "DEMO-NOT-A-CALCULATION",
      "applicability": "APPLICABLE",
      "execution_status": "SUCCEEDED",
      "reason_codes": [],
      "missing_fields": [],
      "metric_kind": "PFD",
      "numeric_value": -102.3,
      "unit": "DEMO-UNIT",
      "implementation_sha": "DEMO-SHA",
      "calculation_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    {
      "analysis_run_id": "DEMO-RUN-001",
      "scenario_id": "DEMO-SCENARIO-001",
      "standard_ref_id": null,
      "role": "SCREENING",
      "reference_bandwidth_hz": 1000000.0,
      "time_percentage": null,
      "location_percentage": null,
      "receiver_site_id": null,
      "satellite_epoch_utc": null,
      "inputs": {},
      "assumptions": [
        "Schema fixture only; not a calculation"
      ],
      "diagnostics": {},
      "result_trace": {},
      "method_run_id": "DEMO-MR-003",
      "method_id": "SPACE_PFD_DIRECTIONAL",
      "method_version": "DEMO-NOT-A-CALCULATION",
      "applicability": "APPLICABLE",
      "execution_status": "SUCCEEDED",
      "reason_codes": [],
      "missing_fields": [],
      "metric_kind": "PFD",
      "numeric_value": -104.0,
      "unit": "DEMO-UNIT",
      "implementation_sha": "DEMO-SHA",
      "calculation_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "comparison_groups": [
    {
      "group_id": "DEMO-GROUP-001",
      "metric_kind": "PFD",
      "method_run_ids": [
        "DEMO-MR-002",
        "DEMO-MR-003"
      ],
      "preferred_method_run_id": null,
      "preferred_reason": null
    }
  ]
} satisfies components["schemas"]["MethodMatrix"];

// PushPayload.minimal.json
export const fixture14 = {
  "alert_id": "DEMO-ALERT-001",
  "category": "CASE_UPDATE",
  "created_at_utc": "2026-11-07T12:00:00Z"
} satisfies components["schemas"]["PushPayload"];

// ReviewCreateRequest.approve_draft.json
export const fixture15 = {
  "action": "APPROVE_DRAFT",
  "decision_reason": "Evidence checked.",
  "draft_id": "DEMO-DRAFT-001"
} satisfies components["schemas"]["ReviewCreateRequest"];

// SourceArtifact.manifest_match_untrusted.json
export const fixture16 = {
  "artifact_id": "DEMO-ARTIFACT-001",
  "source_id": "DEMO-SOURCE-001",
  "publication_id": null,
  "filename_original": "demo-synthetic.xlsx",
  "artifact_type": "XLSX",
  "raw_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expected_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expected_digest_origin": "supplied-manifest",
  "publisher_auth_status": "HASH_MATCH_MANIFEST_UNTRUSTED",
  "byte_length": 1024,
  "revision": 1,
  "usage_classification": "UNVERIFIED",
  "status": "INDEXED_WITH_WARNINGS",
  "analysis_eligible": true,
  "published_at_utc": null,
  "first_seen_at_utc": "2026-11-07T12:00:00Z",
  "download_completed_at_utc": "2026-11-07T12:00:00Z",
  "indexed_at_utc": "2026-11-07T12:00:00Z",
  "parser_version": "DEMO",
  "is_synthetic": true
} satisfies components["schemas"]["SourceArtifact"];

// SourceRecordDetail.flagged_unit.json
export const fixture17 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "source_record_id": "DEMO-RECORD-001",
  "location": {
    "source_record_id": "DEMO-RECORD-001",
    "artifact_id": "DEMO-ARTIFACT-001",
    "raw_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_table_or_sheet": "demo-sheet",
    "source_row_or_key": "1",
    "source_page": null,
    "notice_id": null,
    "raw_record_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "parser_version": "DEMO",
    "schema_version": "DEMO",
    "is_synthetic": true
  },
  "record_status": "REVIEW_REQUIRED",
  "field_aliases": {
    "TX frequency": [
      "DEMO-ALIAS"
    ]
  },
  "raw_fields": {
    "TX frequency": "99",
    "Radiation power": null
  },
  "reference_station": {
    "source_record_id": "DEMO-RECORD-001",
    "station_number_raw": "DEMO-STATION-001",
    "licence_class_code": null,
    "longitude_deg": null,
    "latitude_deg": null,
    "ground_elevation_m": null,
    "mast_height_m": null,
    "antenna_height_agl_m": null,
    "antenna_height_asl_m": null,
    "antenna_gain_db": null,
    "tx_frequency_hz": null,
    "rx_frequency_hz": null,
    "channel_bandwidth_hz": null,
    "emission_bandwidth_hz": null,
    "polarization_code": null,
    "radiation_power_value": null,
    "radiation_power_unit": null,
    "radiation_power_itu_code_raw": null,
    "transmission_line_db": null,
    "directivity_code": null,
    "is_synthetic": true,
    "parse_status": "REVIEW_REQUIRED"
  },
  "quality_findings": [
    {
      "finding_id": "DEMO-FINDING-001",
      "source_record_id": "DEMO-RECORD-001",
      "field_key": "TX frequency",
      "raw_value": "99",
      "normalized_value": null,
      "rule_id": "UNIT_UNSPECIFIED",
      "severity": "BLOCKING",
      "status": "OPEN",
      "reviewer_override_id": null
    }
  ],
  "analysis_eligibility": {
    "TERR_P1546": "INSUFFICIENT_DATA"
  },
  "is_synthetic": true
} satisfies components["schemas"]["SourceRecordDetail"];

// UploadCreateRequest.large_file.json
export const fixture18 = {
  "source_type": "SPACE_IFIC",
  "usage_classification": "RESTRICTED",
  "filename_original": "demo.iso",
  "expected_size_bytes": 10737418240
} satisfies components["schemas"]["UploadCreateRequest"];

// UploadSession.resumable.json
export const fixture19 = {
  "schema_version": "1.0.0-draft.2",
  "generated_at_utc": "2026-11-07T12:00:00Z",
  "upload_id": "DEMO-UPLOAD-001",
  "status": "UPLOADING",
  "source_type": "CHALLENGE_SYNTHETIC_REFERENCE",
  "usage_classification": "UNVERIFIED",
  "filename_original": "demo-synthetic.xlsx",
  "expected_size_bytes": 134217728,
  "received_size_bytes": 67108864,
  "part_size_bytes": 67108864,
  "max_size_bytes": 10737418240,
  "parts": [
    {
      "part_number": 1,
      "size_bytes": 67108864,
      "etag": "demo-etag-1",
      "received": true
    }
  ],
  "content_sha256": null,
  "job_id": null,
  "failure_code": null,
  "created_at_utc": "2026-11-07T12:00:00Z",
  "expires_at_utc": "2026-11-08T12:00:00Z",
  "completed_at_utc": null
} satisfies components["schemas"]["UploadSession"];
