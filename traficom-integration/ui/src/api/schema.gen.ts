// GENERATED from traficom-integration/contract. Do not edit.
export interface paths {
    "/api/v1/admin/alert-rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Alert Rules */
        get: operations["list_alert_rules_api_v1_admin_alert_rules_get"];
        /** Save Alert Rule */
        put: operations["save_alert_rule_api_v1_admin_alert_rules_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/sources/{source_id}/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Check Source */
        post: operations["check_source_api_v1_admin_sources__source_id__check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Alerts */
        get: operations["list_alerts_api_v1_alerts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts/preferences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Alert Preferences */
        put: operations["update_alert_preferences_api_v1_alerts_preferences_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream Alerts */
        get: operations["stream_alerts_api_v1_alerts_stream_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts/{alert_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Alert */
        get: operations["get_alert_api_v1_alerts__alert_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts/{alert_id}/acknowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Acknowledge Alert */
        post: operations["acknowledge_alert_api_v1_alerts__alert_id__acknowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analyses/{analysis_run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Analysis */
        get: operations["get_analysis_api_v1_analyses__analysis_run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analyses/{analysis_run_id}/methods": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Analysis Methods */
        get: operations["get_analysis_methods_api_v1_analyses__analysis_run_id__methods_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Cases */
        get: operations["list_cases_api_v1_cases_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases/{case_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Case */
        get: operations["get_case_api_v1_cases__case_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases/{case_id}/analyse": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Analyse Case */
        post: operations["analyse_case_api_v1_cases__case_id__analyse_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases/{case_id}/drafts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Draft */
        post: operations["create_draft_api_v1_cases__case_id__drafts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases/{case_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export Case */
        get: operations["export_case_api_v1_cases__case_id__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cases/{case_id}/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Review */
        post: operations["create_review_api_v1_cases__case_id__reviews_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register Device */
        post: operations["register_device_api_v1_devices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/devices/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Device */
        delete: operations["revoke_device_api_v1_devices__device_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/ingest/ific": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ingest Ific */
        post: operations["ingest_ific_api_v1_ingest_ific_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/issues": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Issues */
        get: operations["list_issues_api_v1_issues_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/issues/{issue_id}/changes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Issue Changes */
        get: operations["list_issue_changes_api_v1_issues__issue_id__changes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_api_v1_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Me */
        get: operations["get_me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/references": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List References */
        get: operations["list_references_api_v1_references_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-artifacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Source Artifacts */
        get: operations["list_source_artifacts_api_v1_source_artifacts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-artifacts/{artifact_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Artifact */
        get: operations["get_source_artifact_api_v1_source_artifacts__artifact_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-artifacts/{artifact_id}/download-link": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Download Link */
        post: operations["create_download_link_api_v1_source_artifacts__artifact_id__download_link_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-artifacts/{artifact_id}/integrity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Artifact Integrity */
        get: operations["get_source_artifact_integrity_api_v1_source_artifacts__artifact_id__integrity_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-artifacts/{artifact_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Artifact Preview */
        get: operations["get_source_artifact_preview_api_v1_source_artifacts__artifact_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-publications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Source Publications */
        get: operations["list_source_publications_api_v1_source_publications_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Source Records */
        get: operations["search_source_records_api_v1_source_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-records/{source_record_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Record */
        get: operations["get_source_record_api_v1_source_records__source_record_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/source-records/{source_record_id}/source-location": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Record Location */
        get: operations["get_source_record_location_api_v1_source_records__source_record_id__source_location_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sources */
        get: operations["list_sources_api_v1_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/{source_id}/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source Health */
        get: operations["get_source_health_api_v1_sources__source_id__health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Upload */
        post: operations["create_upload_api_v1_uploads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/uploads/{upload_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Upload */
        get: operations["get_upload_api_v1_uploads__upload_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/uploads/{upload_id}/abort": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Abort Upload */
        post: operations["abort_upload_api_v1_uploads__upload_id__abort_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/uploads/{upload_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Complete Upload */
        post: operations["complete_upload_api_v1_uploads__upload_id__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/uploads/{upload_id}/parts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Upload Part Urls */
        post: operations["create_upload_part_urls_api_v1_uploads__upload_id__parts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AgentDraftResponse
         * @description Structured agent output. The server still validates citations before using it.
         */
        AgentDraftResponse: {
            /** Analysis Run Id */
            analysis_run_id: string;
            /** Cited Evidence Ids */
            cited_evidence_ids: string[];
            /** Draft Markdown */
            draft_markdown: string;
            draft_type: components["schemas"]["DraftType"];
            /** Explanation Markdown */
            explanation_markdown: string;
            /**
             * Requires Human Review
             * @constant
             */
            requires_human_review: true;
            /** Uncertainties */
            uncertainties: string[];
        };
        /** AlertAcknowledgeRequest */
        AlertAcknowledgeRequest: {
            /** Comment */
            comment?: string | null;
        };
        /** AlertAcknowledged */
        AlertAcknowledged: {
            /** Ack Id */
            ack_id: string;
            /**
             * Acknowledged At Utc
             * Format: date-time
             */
            acknowledged_at_utc: string;
            /** Actor Id */
            actor_id: string;
            /** Alert Id */
            alert_id: string;
            /** Comment */
            comment: string | null;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /** AlertAcknowledgment */
        AlertAcknowledgment: {
            /** Ack Id */
            ack_id: string;
            /**
             * Acknowledged At Utc
             * Format: date-time
             */
            acknowledged_at_utc: string;
            /** Actor Id */
            actor_id: string;
            /** Alert Id */
            alert_id: string;
            /** Comment */
            comment: string | null;
        };
        /**
         * AlertChannel
         * @enum {string}
         */
        AlertChannel: "IN_APP" | "WINDOWS" | "ANDROID" | "EMAIL";
        /** AlertDelivery */
        AlertDelivery: {
            /** Attempt */
            attempt: number;
            channel: components["schemas"]["AlertChannel"];
            /** Delivered At Utc */
            delivered_at_utc: string | null;
            /** Delivery Id */
            delivery_id: string;
            /** Failure Code */
            failure_code: string | null;
            /** Last Attempt At Utc */
            last_attempt_at_utc: string | null;
            state: components["schemas"]["AlertDeliveryState"];
        };
        /**
         * AlertDeliveryState
         * @description Sent, delivered and read are distinct; none of them implies acknowledgment.
         * @enum {string}
         */
        AlertDeliveryState: "PENDING" | "SENT" | "DELIVERED" | "READ" | "FAILED";
        /** AlertDetail */
        AlertDetail: {
            /** Acknowledgments */
            acknowledgments: components["schemas"]["AlertAcknowledgment"][];
            /** Alert Id */
            alert_id: string;
            /** Case Id */
            case_id: string | null;
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            /** Deliveries */
            deliveries: components["schemas"]["AlertDelivery"][];
            /** Event Id */
            event_id: string;
            /** Evidence Refs */
            evidence_refs: string[];
            /** Expires At Utc */
            expires_at_utc: string | null;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Rule Id */
            rule_id: string;
            /** Rule Version */
            rule_version: number;
            /** Safe Preview */
            safe_preview: string;
            /** Safe Title */
            safe_title: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            severity: components["schemas"]["AlertSeverity"];
            status: components["schemas"]["AlertStatus"];
        };
        /**
         * AlertEvidenceRequirement
         * @enum {string}
         */
        AlertEvidenceRequirement: "SOURCE_PROVENANCE" | "VERIFIED_CRITERION_AND_METHOD_RUN" | "REVIEWER_DECISION" | "OPERATIONAL_DIAGNOSTIC";
        /** AlertList */
        AlertList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["AlertSummary"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /** AlertPreferences */
        AlertPreferences: {
            /** Enabled Channels */
            enabled_channels: components["schemas"]["AlertChannel"][];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Quiet Hours End Utc */
            quiet_hours_end_utc: string | null;
            /** Quiet Hours Start Utc */
            quiet_hours_start_utc: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /** AlertPreferencesUpdate */
        AlertPreferencesUpdate: {
            /** Enabled Channels */
            enabled_channels: components["schemas"]["AlertChannel"][];
            /** Quiet Hours End Utc */
            quiet_hours_end_utc?: string | null;
            /** Quiet Hours Start Utc */
            quiet_hours_start_utc?: string | null;
        };
        /** AlertRule */
        AlertRule: {
            /** Ack Timeout Seconds */
            ack_timeout_seconds: number | null;
            /** Dedupe Window Seconds */
            dedupe_window_seconds: number;
            /** Enabled */
            enabled: boolean;
            /** Escalation Policy */
            escalation_policy: {
                [key: string]: unknown;
            };
            evidence_requirement: components["schemas"]["AlertEvidenceRequirement"];
            /** Routing Roles */
            routing_roles: components["schemas"]["Role"][];
            /** Rule Id */
            rule_id: string;
            severity: components["schemas"]["AlertSeverity"];
            trigger_kind: components["schemas"]["AlertTriggerKind"];
            /** Version */
            version: number;
        };
        /** AlertRuleList */
        AlertRuleList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["AlertRule"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /** AlertRuleSaved */
        AlertRuleSaved: {
            /** Ack Timeout Seconds */
            ack_timeout_seconds: number | null;
            /** Dedupe Window Seconds */
            dedupe_window_seconds: number;
            /** Enabled */
            enabled: boolean;
            /** Escalation Policy */
            escalation_policy: {
                [key: string]: unknown;
            };
            evidence_requirement: components["schemas"]["AlertEvidenceRequirement"];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Routing Roles */
            routing_roles: components["schemas"]["Role"][];
            /** Rule Id */
            rule_id: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            severity: components["schemas"]["AlertSeverity"];
            trigger_kind: components["schemas"]["AlertTriggerKind"];
            /** Version */
            version: number;
        };
        /** AlertRuleUpsert */
        AlertRuleUpsert: {
            /** Ack Timeout Seconds */
            ack_timeout_seconds?: number | null;
            /** Dedupe Window Seconds */
            dedupe_window_seconds: number;
            /** Enabled */
            enabled: boolean;
            /** Escalation Policy */
            escalation_policy?: {
                [key: string]: unknown;
            };
            evidence_requirement: components["schemas"]["AlertEvidenceRequirement"];
            /** Routing Roles */
            routing_roles: components["schemas"]["Role"][];
            /** Rule Id */
            rule_id?: string | null;
            severity: components["schemas"]["AlertSeverity"];
            trigger_kind: components["schemas"]["AlertTriggerKind"];
        };
        /**
         * AlertSeverity
         * @enum {string}
         */
        AlertSeverity: "INFO" | "REVIEW" | "HIGH" | "CRITICAL" | "OPERATIONS" | "SECURITY";
        /**
         * AlertStatus
         * @enum {string}
         */
        AlertStatus: "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "SUPPRESSED";
        /**
         * AlertSummary
         * @description Inbox item. Severity is an operational priority, not a legal status.
         */
        AlertSummary: {
            /** Alert Id */
            alert_id: string;
            /** Case Id */
            case_id: string | null;
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            /** Event Id */
            event_id: string;
            /** Expires At Utc */
            expires_at_utc: string | null;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Rule Id */
            rule_id: string;
            /** Rule Version */
            rule_version: number;
            /** Safe Preview */
            safe_preview: string;
            /** Safe Title */
            safe_title: string;
            severity: components["schemas"]["AlertSeverity"];
            status: components["schemas"]["AlertStatus"];
        };
        /**
         * AlertTriggerKind
         * @enum {string}
         */
        AlertTriggerKind: "RELEVANT_CANDIDATE" | "POTENTIAL_EXCEEDANCE" | "REVIEWER_ESCALATION" | "UNCERTAINTY_REVIEW" | "OPERATIONS_FAILURE" | "SECURITY_EVENT" | "SOURCE_NEW_RELEASE" | "SOURCE_REVISED" | "SOURCE_STALE" | "ARTIFACT_INTEGRITY_FAILURE" | "SCHEMA_DRIFT" | "INDEX_BACKLOG";
        /** AnalyseRequest */
        AnalyseRequest: {
            /** Scenario Id */
            scenario_id?: string | null;
        };
        /** AnalysisAccepted */
        AnalysisAccepted: {
            /** Analysis Run Id */
            analysis_run_id: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Job Id */
            job_id: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /**
         * AnalysisRun
         * @description Immutable: a rerun creates a new ``analysis_run_id``.
         */
        AnalysisRun: {
            /** Analysis Run Id */
            analysis_run_id: string;
            analysis_status: components["schemas"]["AnalysisStatus"];
            /** Case Id */
            case_id: string;
            /** Created By */
            created_by: string;
            /** Criterion Checks */
            criterion_checks: components["schemas"]["CriterionCheck"][];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Input Snapshot Sha256 */
            input_snapshot_sha256: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Method Registry Version */
            method_registry_version: string;
            /** Method Runs */
            method_runs: components["schemas"]["MethodRun"][];
            /** Reference Snapshot Sha256 */
            reference_snapshot_sha256: string | null;
            /**
             * Run Created At Utc
             * Format: date-time
             */
            run_created_at_utc: string;
            /** Scenario Id */
            scenario_id: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Software Commit Sha */
            software_commit_sha: string;
        };
        /**
         * AnalysisStatus
         * @enum {string}
         */
        AnalysisStatus: "QUEUED" | "RUNNING" | "READY" | "BLOCKED_BY_INPUTS" | "NOT_APPLICABLE" | "FAILED" | "VERIFIED_RESULT" | "INPUT_SUPERSEDED";
        /** ApiErrorBody */
        ApiErrorBody: {
            code: components["schemas"]["ErrorCode"];
            /** Details */
            details: {
                [key: string]: unknown;
            };
            /** Message */
            message: string;
            /** Request Id */
            request_id: string;
        };
        /** ArtifactIntegrityCheck */
        ArtifactIntegrityCheck: {
            /** Check Id */
            check_id: string;
            /** Check Type */
            check_type: string;
            /**
             * Checked At Utc
             * Format: date-time
             */
            checked_at_utc: string;
            /** Diagnostic */
            diagnostic: string | null;
            result: components["schemas"]["IntegrityCheckResult"];
            /** Tool Version */
            tool_version: string;
            trust_level: components["schemas"]["PublisherAuthStatus"] | null;
            /** Value Expected */
            value_expected: string | null;
            /** Value Observed */
            value_observed: string | null;
        };
        /** ArtifactIntegrityReport */
        ArtifactIntegrityReport: {
            /** Artifact Id */
            artifact_id: string;
            /** Byte Length */
            byte_length: number;
            /** Checks */
            checks: components["schemas"]["ArtifactIntegrityCheck"][];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            publisher_auth_status: components["schemas"]["PublisherAuthStatus"];
            /** Raw Sha256 */
            raw_sha256: string;
            row_reconciliation: components["schemas"]["RowReconciliation"] | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            status: components["schemas"]["ArtifactStatus"];
        };
        /**
         * ArtifactStatus
         * @enum {string}
         */
        ArtifactStatus: "DISCOVERED" | "QUEUED" | "DOWNLOADING" | "INTEGRITY_CHECKING" | "VERIFIED_BYTES" | "FORMAT_VALIDATED" | "PARSING" | "INDEXED" | "INDEXED_WITH_WARNINGS" | "QUARANTINED" | "FAILED" | "ACCESS_DENIED" | "MANUAL_REQUIRED" | "UNSUPPORTED_FORMAT";
        /**
         * Capability
         * @enum {string}
         */
        Capability: "AUTHENTICATED" | "CASE_READ" | "ISSUE_READ" | "ANALYSIS_READ" | "ANALYSIS_RUN" | "DRAFT_CREATE" | "REVIEW_DECIDE" | "CASE_EXPORT" | "UPLOAD_MANAGE" | "INGEST_TRIGGER" | "JOB_READ" | "REFERENCE_READ" | "SOURCE_HEALTH_READ" | "SOURCE_READ" | "SOURCE_DOWNLOAD" | "ALERT_READ" | "ALERT_ACKNOWLEDGE" | "ALERT_PREFERENCES" | "DEVICE_MANAGE" | "ADMIN_ALERT_RULES" | "ADMIN_SOURCE_CHECK";
        /**
         * CaseDetail
         * @description Method runs load from ``GET /analyses/{id}`` so values have one canonical source.
         */
        CaseDetail: {
            /** Administration */
            administration: string | null;
            /** Case Id */
            case_id: string;
            change_type: components["schemas"]["ChangeType"];
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            criterion_status: components["schemas"]["CriterionApplicability"] | null;
            domain: components["schemas"]["CaseDomain"];
            /** Evidence */
            evidence: components["schemas"]["EvidenceLink"][];
            finding_status: components["schemas"]["FindingStatus"];
            /** Frequency End Mhz */
            frequency_end_mhz: number;
            /** Frequency Start Mhz */
            frequency_start_mhz: number;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Latest Analysis Run Id */
            latest_analysis_run_id: string | null;
            lead_metric: components["schemas"]["LeadMetric"];
            /** Margin Db */
            margin_db: number | null;
            method_summary: components["schemas"]["MethodSummary"];
            /** Notice Id */
            notice_id: string;
            /** Owner */
            owner: string | null;
            /** Priority */
            priority: string | null;
            /** Priority Reason */
            priority_reason: string | null;
            relevance: components["schemas"]["RelevanceGates"];
            /** Relevance Label */
            relevance_label: string;
            review_status: components["schemas"]["ReviewStatus"];
            reviewer_decision: components["schemas"]["ReviewAction"] | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Issue Id */
            source_issue_id: string;
            /**
             * Updated At Utc
             * Format: date-time
             */
            updated_at_utc: string;
        };
        /**
         * CaseDomain
         * @enum {string}
         */
        CaseDomain: "SPACE" | "TERRESTRIAL";
        /** CaseList */
        CaseList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["CaseSummary"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * CaseSort
         * @enum {string}
         */
        CaseSort: "case_id" | "frequency_start_mhz" | "updated_at_utc" | "priority";
        /** CaseSummary */
        CaseSummary: {
            /** Administration */
            administration: string | null;
            /** Case Id */
            case_id: string;
            change_type: components["schemas"]["ChangeType"];
            criterion_status: components["schemas"]["CriterionApplicability"] | null;
            domain: components["schemas"]["CaseDomain"];
            finding_status: components["schemas"]["FindingStatus"];
            /** Frequency End Mhz */
            frequency_end_mhz: number;
            /** Frequency Start Mhz */
            frequency_start_mhz: number;
            /** Is Synthetic */
            is_synthetic: boolean;
            lead_metric: components["schemas"]["LeadMetric"];
            /** Margin Db */
            margin_db: number | null;
            method_summary: components["schemas"]["MethodSummary"];
            /** Notice Id */
            notice_id: string;
            /** Relevance Label */
            relevance_label: string;
            review_status: components["schemas"]["ReviewStatus"];
            /** Source Issue Id */
            source_issue_id: string;
        };
        /**
         * ChangeType
         * @enum {string}
         */
        ChangeType: "NEW" | "MODIFIED" | "WITHDRAWN" | "UNCHANGED" | "UNRESOLVED";
        /** ComparisonGroup */
        ComparisonGroup: {
            /** Group Id */
            group_id: string;
            /** Method Run Ids */
            method_run_ids: string[];
            metric_kind: components["schemas"]["MetricKind"];
            /** Preferred Method Run Id */
            preferred_method_run_id: string | null;
            /** Preferred Reason */
            preferred_reason: string | null;
        };
        /**
         * ComparisonOperator
         * @enum {string}
         */
        ComparisonOperator: "UPPER_BOUND" | "LOWER_BOUND";
        /**
         * ComparisonStatus
         * @enum {string}
         */
        ComparisonStatus: "COMPARED" | "NOT_COMPARABLE" | "CRITERION_UNVERIFIED" | "REVIEW_REQUIRED";
        /**
         * CriterionApplicability
         * @enum {string}
         */
        CriterionApplicability: "VERIFIED" | "UNVERIFIED" | "NOT_APPLICABLE";
        /**
         * CriterionCheck
         * @description Separate from the method run. Positive upper-bound margins are potential exceedances only.
         */
        CriterionCheck: {
            applicable: components["schemas"]["CriterionApplicability"];
            citation: components["schemas"]["CriterionCitation"] | null;
            comparison_operator: components["schemas"]["ComparisonOperator"] | null;
            comparison_status: components["schemas"]["ComparisonStatus"];
            /** Criterion Check Id */
            criterion_check_id: string;
            /** Criterion Ref Id */
            criterion_ref_id: string | null;
            /** Limit Reference Bandwidth Hz */
            limit_reference_bandwidth_hz: number | null;
            /** Limit Unit */
            limit_unit: string | null;
            /** Limit Value */
            limit_value: number | null;
            /** Margin Db */
            margin_db: number | null;
            /** Matching Conditions */
            matching_conditions: {
                [key: string]: unknown;
            };
            /** Method Run Id */
            method_run_id: string;
            /** Regulatory Scope */
            regulatory_scope: string | null;
            /** Review Note */
            review_note: string | null;
        };
        /** CriterionCitation */
        CriterionCitation: {
            /** Reference Id */
            reference_id: string;
            /** Section Id */
            section_id: string;
            /** Source Url */
            source_url: string;
        };
        /** Device */
        Device: {
            /** Device Id */
            device_id: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Last Seen At Utc */
            last_seen_at_utc: string | null;
            platform: components["schemas"]["DevicePlatform"];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            status: components["schemas"]["DeviceStatus"];
        };
        /**
         * DevicePlatform
         * @enum {string}
         */
        DevicePlatform: "WINDOWS" | "ANDROID";
        /**
         * DeviceRegistrationRequest
         * @description The push token is write-only: it never appears in a response.
         */
        DeviceRegistrationRequest: {
            platform: components["schemas"]["DevicePlatform"];
            /** Push Token */
            push_token: string;
        };
        /**
         * DeviceStatus
         * @enum {string}
         */
        DeviceStatus: "ACTIVE" | "REVOKED";
        /**
         * DiscoveryMode
         * @enum {string}
         */
        DiscoveryMode: "WEBHOOK" | "API_POLL" | "DOCUMENTED_FEED" | "MANUAL_TRANSFER";
        /**
         * DomainEvent
         * @description Immutable event written to the outbox and consumed by the versioned alert rules.
         */
        DomainEvent: {
            /** Correlation Id */
            correlation_id: string;
            /** Dedupe Key */
            dedupe_key: string;
            /** Event Id */
            event_id: string;
            event_kind: components["schemas"]["DomainEventKind"];
            /**
             * Occurred At Utc
             * Format: date-time
             */
            occurred_at_utc: string;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /** Resource Id */
            resource_id: string;
            /** Resource Type */
            resource_type: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Tenant Id */
            tenant_id: string;
        };
        /**
         * DomainEventKind
         * @enum {string}
         */
        DomainEventKind: "SOURCE_PUBLISHED" | "SOURCE_REVISED" | "SOURCE_FAILED" | "SOURCE_STALE" | "ARTIFACT_QUARANTINED" | "ARTIFACT_INDEXED" | "CANDIDATE_SCREENED" | "METHOD_COMPLETED" | "CRITERION_CHECKED" | "CASE_REVIEWED" | "ALERT_CREATED" | "ALERT_ACKNOWLEDGED" | "SECURITY_EVENT";
        /** DownloadLink */
        DownloadLink: {
            /** Artifact Id */
            artifact_id: string;
            /** Byte Length */
            byte_length: number;
            /**
             * Expires At Utc
             * Format: date-time
             */
            expires_at_utc: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Raw Sha256 */
            raw_sha256: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Url */
            url: string;
        };
        /**
         * DownloadLinkRequest
         * @description The client must confirm it warned the user about a potentially multi-GB transfer.
         */
        DownloadLinkRequest: {
            /**
             * Acknowledge Transfer Size
             * @constant
             */
            acknowledge_transfer_size: true;
        };
        /** Draft */
        Draft: {
            /** Ai Model Id */
            ai_model_id: string | null;
            /** Case Id */
            case_id: string;
            /** Citations */
            citations: string[];
            /** Content Markdown */
            content_markdown: string;
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            /** Draft Id */
            draft_id: string;
            draft_type: components["schemas"]["DraftType"];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Generation Provenance */
            generation_provenance: string;
            /**
             * Requires Human Review
             * @constant
             */
            requires_human_review: true;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Analysis Run Id */
            source_analysis_run_id: string;
            status: components["schemas"]["DraftStatus"];
            /** Warnings */
            warnings: string[];
        };
        /** DraftCreateRequest */
        DraftCreateRequest: {
            /** Analysis Run Id */
            analysis_run_id: string;
            draft_type: components["schemas"]["DraftType"];
        };
        /**
         * DraftCreated
         * @description A new draft is always unapproved. Only a review event can change that.
         */
        DraftCreated: {
            /** Ai Model Id */
            ai_model_id: string | null;
            /** Case Id */
            case_id: string;
            /** Citations */
            citations: string[];
            /** Content Markdown */
            content_markdown: string;
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            /** Draft Id */
            draft_id: string;
            draft_type: components["schemas"]["DraftType"];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Generation Provenance */
            generation_provenance: string;
            /**
             * Requires Human Review
             * @constant
             */
            requires_human_review: true;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Analysis Run Id */
            source_analysis_run_id: string;
            /**
             * Status
             * @constant
             */
            status: "DRAFT";
            /** Warnings */
            warnings: string[];
        };
        /**
         * DraftStatus
         * @enum {string}
         */
        DraftStatus: "DRAFT" | "EDITED" | "APPROVED" | "REJECTED";
        /**
         * DraftType
         * @enum {string}
         */
        DraftType: "REQUEST_INFORMATION" | "TECHNICAL_INQUIRY" | "COORDINATION_COMMENT" | "DRAFT_OBJECTION";
        /**
         * Environment
         * @enum {string}
         */
        Environment: "DEMO" | "STAGING" | "PRODUCTION";
        /**
         * ErrorCode
         * @enum {string}
         */
        ErrorCode: "UNAUTHENTICATED" | "FORBIDDEN" | "REVOKED_DEVICE" | "NOT_FOUND" | "ALERT_NOT_FOUND" | "CONFLICT" | "VALIDATION_ERROR" | "INSUFFICIENT_DATA" | "UPLOAD_CHECKSUM_MISMATCH" | "JOB_QUOTA_EXCEEDED" | "RATE_LIMITED" | "SOURCE_RESTRICTED" | "NOT_IMPLEMENTED" | "INTERNAL_ERROR";
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ApiErrorBody"];
        };
        /** EvidenceLink */
        EvidenceLink: {
            /** Entity Id */
            entity_id: string;
            /** Entity Type */
            entity_type: string;
            /** Evidence Id */
            evidence_id: string;
            /** Label */
            label: string;
            /** Note */
            note: string | null;
            /** Reference Id */
            reference_id: string | null;
            /** Sha256 */
            sha256: string;
            /** Source Issue Id */
            source_issue_id: string | null;
            /** Source Locator */
            source_locator: string;
            /** Verified At Utc */
            verified_at_utc: string | null;
        };
        /** EvidencePack */
        EvidencePack: {
            /** Analysis Runs */
            analysis_runs: components["schemas"]["AnalysisRun"][];
            /** Case Id */
            case_id: string;
            /** Drafts */
            drafts: components["schemas"]["Draft"][];
            /** Evidence */
            evidence: components["schemas"]["EvidenceLink"][];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Review Events */
            review_events: components["schemas"]["ReviewEvent"][];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /**
         * FindingStatus
         * @enum {string}
         */
        FindingStatus: "NO_IDENTIFIED_CONCERN" | "POTENTIAL_CONCERN" | "POTENTIAL_LIMIT_EXCEEDANCE" | "INSUFFICIENT_DATA" | "METHOD_DISAGREEMENT" | "EXPERT_REVIEW_REQUIRED";
        /**
         * IngestRequest
         * @description Refers to an already staged artifact. Arbitrary URLs and paths are not accepted.
         */
        IngestRequest: {
            /** Artifact Id */
            artifact_id: string;
            source_type: components["schemas"]["SourceType"];
        };
        /**
         * IntegrityCheckResult
         * @enum {string}
         */
        IntegrityCheckResult: "PASS" | "FAIL" | "WARN" | "NOT_AVAILABLE";
        /**
         * IssueDomain
         * @enum {string}
         */
        IssueDomain: "SPACE" | "TERRESTRIAL" | "FINNISH_REFERENCE" | "REGULATORY_REFERENCE";
        /** IssueList */
        IssueList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["SourceIssue"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /** JobAccepted */
        JobAccepted: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Job Id */
            job_id: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            status: components["schemas"]["PipelineStatus"];
        };
        /**
         * JobRun
         * @description Progress is bytes, records and stage. There is no percent field to invent.
         */
        JobRun: {
            /** Attempt */
            attempt: number;
            error_code: components["schemas"]["ErrorCode"] | null;
            /** Finished At Utc */
            finished_at_utc: string | null;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Job Id */
            job_id: string;
            job_type: components["schemas"]["JobType"];
            /** Max Attempts */
            max_attempts: number;
            /** Processed Bytes */
            processed_bytes: number | null;
            /** Processed Records */
            processed_records: number | null;
            /** Progress Stage */
            progress_stage: string | null;
            /** Resource Id */
            resource_id: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Started At Utc */
            started_at_utc: string | null;
            status: components["schemas"]["PipelineStatus"];
            /** Total Records If Known */
            total_records_if_known: number | null;
        };
        /**
         * JobType
         * @enum {string}
         */
        JobType: "INGEST" | "DIFF" | "RELEVANCE" | "RF" | "AI_DRAFT" | "ALERT_DELIVERY" | "SOURCE_DISCOVERY";
        /** LeadMetric */
        LeadMetric: {
            metric_kind: components["schemas"]["MetricKind"] | null;
            /** Numeric Value */
            numeric_value: number | null;
            /** Unit */
            unit: string | null;
        };
        /** Me */
        Me: {
            /** Capabilities */
            capabilities: components["schemas"]["Capability"][];
            environment: components["schemas"]["Environment"];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Roles */
            roles: components["schemas"]["Role"][];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Tenant Id */
            tenant_id: string;
            /** User Id */
            user_id: string;
        };
        /**
         * MethodApplicability
         * @enum {string}
         */
        MethodApplicability: "APPLICABLE" | "NOT_APPLICABLE" | "INSUFFICIENT_DATA" | "NOT_IMPLEMENTED";
        /**
         * MethodAssessment
         * @description What ``RFMethod.assess_applicability`` must return, validated at the worker boundary.
         */
        MethodAssessment: {
            applicability: components["schemas"]["MethodApplicability"];
            /** Method Id */
            method_id: string;
            /** Method Version */
            method_version: string;
            metric_kind: components["schemas"]["MetricKind"] | null;
            /** Missing Fields */
            missing_fields: string[];
            /** Reason Codes */
            reason_codes: string[];
        };
        /**
         * MethodCalculation
         * @description What ``RFMethod.calculate`` must return, validated at the worker boundary.
         */
        MethodCalculation: {
            /** Assumptions */
            assumptions: string[];
            /** Calculation Sha256 */
            calculation_sha256: string;
            /** Diagnostics */
            diagnostics: {
                [key: string]: unknown;
            };
            /** Implementation Sha */
            implementation_sha: string;
            /** Inputs */
            inputs: {
                [key: string]: unknown;
            };
            /** Location Percentage */
            location_percentage: number | null;
            /** Method Id */
            method_id: string;
            /** Method Version */
            method_version: string;
            metric_kind: components["schemas"]["MetricKind"];
            /** Numeric Value */
            numeric_value: number;
            /** Reference Bandwidth Hz */
            reference_bandwidth_hz: number | null;
            /** Result Trace */
            result_trace: {
                [key: string]: unknown;
            };
            /** Time Percentage */
            time_percentage: number | null;
            /** Unit */
            unit: string;
        };
        /**
         * MethodExecution
         * @enum {string}
         */
        MethodExecution: "NOT_RUN" | "SUCCEEDED" | "FAILED" | "SKIPPED";
        /** MethodMatrix */
        MethodMatrix: {
            /** Analysis Run Id */
            analysis_run_id: string;
            /** Comparison Groups */
            comparison_groups: components["schemas"]["ComparisonGroup"][];
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Method Runs */
            method_runs: components["schemas"]["MethodRun"][];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /**
         * MethodRole
         * @enum {string}
         */
        MethodRole: "SCREENING" | "ENGINEERING" | "REGULATORY" | "VERIFICATION";
        /**
         * MethodRun
         * @description One row per candidate method per scenario, even when the method did not run (BSD 3.7).
         */
        MethodRun: {
            /** Analysis Run Id */
            analysis_run_id: string;
            applicability: components["schemas"]["MethodApplicability"];
            /** Assumptions */
            assumptions: string[];
            /** Calculation Sha256 */
            calculation_sha256: string | null;
            /** Diagnostics */
            diagnostics: {
                [key: string]: unknown;
            };
            execution_status: components["schemas"]["MethodExecution"];
            /** Implementation Sha */
            implementation_sha: string | null;
            /** Inputs */
            inputs: {
                [key: string]: unknown;
            };
            /** Location Percentage */
            location_percentage: number | null;
            /** Method Id */
            method_id: string;
            /** Method Run Id */
            method_run_id: string;
            /** Method Version */
            method_version: string;
            metric_kind: components["schemas"]["MetricKind"] | null;
            /** Missing Fields */
            missing_fields: string[];
            /** Numeric Value */
            numeric_value: number | null;
            /** Reason Codes */
            reason_codes: string[];
            /** Receiver Site Id */
            receiver_site_id: string | null;
            /** Reference Bandwidth Hz */
            reference_bandwidth_hz: number | null;
            /** Result Trace */
            result_trace: {
                [key: string]: unknown;
            };
            role: components["schemas"]["MethodRole"];
            /** Satellite Epoch Utc */
            satellite_epoch_utc: string | null;
            /** Scenario Id */
            scenario_id: string;
            /** Standard Ref Id */
            standard_ref_id: string | null;
            /** Time Percentage */
            time_percentage: number | null;
            /** Unit */
            unit: string | null;
        };
        /** MethodSummary */
        MethodSummary: {
            /** Candidates */
            candidates: number;
            /** Succeeded */
            succeeded: number;
        };
        /**
         * MetricKind
         * @enum {string}
         */
        MetricKind: "PFD" | "EPFD" | "FIELD_STRENGTH" | "BASIC_TRANSMISSION_LOSS" | "RECEIVED_INTERFERENCE_POWER";
        /** NoticeChange */
        NoticeChange: {
            /** Change Id */
            change_id: string;
            change_type: components["schemas"]["ChangeType"];
            /** Changed Fields */
            changed_fields: {
                [key: string]: unknown;
            };
            /** Comparison Run Id */
            comparison_run_id: string;
            /** Current Issue Id */
            current_issue_id: string;
            /** Current Notice Uid */
            current_notice_uid: string | null;
            /** Identity Confidence */
            identity_confidence: number | null;
            /** Matching Strategy */
            matching_strategy: string;
            /** Previous Issue Id */
            previous_issue_id: string | null;
            /** Previous Notice Uid */
            previous_notice_uid: string | null;
        };
        /** NoticeChangeList */
        NoticeChangeList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["NoticeChange"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * ObservationStatus
         * @enum {string}
         */
        ObservationStatus: "NEW" | "REVISED" | "UNCHANGED" | "RETRACTED" | "UNKNOWN";
        /**
         * PipelineStatus
         * @description Upload and job lifecycle (DATA_PIPELINE_AND_SCALABILITY.md section 3).
         * @enum {string}
         */
        PipelineStatus: "CREATED" | "UPLOADING" | "VERIFYING" | "QUEUED" | "PARSING" | "NORMALIZING" | "INDEXING" | "SCREENING" | "READY" | "PARTIAL" | "RETRYING" | "FAILED" | "CANCELLED" | "QUARANTINED";
        /**
         * PublisherAuthStatus
         * @description Origin trust, deliberately separate from byte integrity and parse status.
         * @enum {string}
         */
        PublisherAuthStatus: "VERIFIED_PUBLISHER" | "HASH_MATCH_MANIFEST_UNTRUSTED" | "NO_PUBLISHER_DIGEST" | "MISMATCH";
        /**
         * PushCategory
         * @description Generic lock-screen safe categories. Never carries case or source content.
         * @enum {string}
         */
        PushCategory: "CASE_UPDATE" | "OPERATIONS" | "SECURITY";
        /**
         * PushPayload
         * @description All an OS notification may carry. Details are fetched only after re-authorization.
         */
        PushPayload: {
            /** Alert Id */
            alert_id: string;
            category: components["schemas"]["PushCategory"];
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
        };
        /**
         * QualitySeverity
         * @enum {string}
         */
        QualitySeverity: "INFO" | "WARNING" | "BLOCKING";
        /** RecordQualityFinding */
        RecordQualityFinding: {
            /** Field Key */
            field_key: string;
            /** Finding Id */
            finding_id: string;
            /** Normalized Value */
            normalized_value: string | null;
            /** Raw Value */
            raw_value: string | null;
            /** Reviewer Override Id */
            reviewer_override_id: string | null;
            /** Rule Id */
            rule_id: string;
            severity: components["schemas"]["QualitySeverity"];
            /** Source Record Id */
            source_record_id: string;
            /** Status */
            status: string;
        };
        /**
         * RecordStatus
         * @enum {string}
         */
        RecordStatus: "VALID" | "VALID_WITH_WARNINGS" | "INVALID" | "INSUFFICIENT_DATA" | "REVIEW_REQUIRED";
        /** ReferenceDocument */
        ReferenceDocument: {
            /** Authority */
            authority: string;
            /** Document Title */
            document_title: string;
            /** Edition */
            edition: string | null;
            /** Effective Date */
            effective_date: string | null;
            /** Last Verified At Utc */
            last_verified_at_utc: string | null;
            /** Publication Date */
            publication_date: string | null;
            /** Reference Id */
            reference_id: string;
            /** Reviewed By */
            reviewed_by: string | null;
            /** Section Id */
            section_id: string | null;
            /** Snapshot Sha256 */
            snapshot_sha256: string | null;
            /** Source Url */
            source_url: string | null;
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /** ReferenceList */
        ReferenceList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["ReferenceDocument"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * ReferenceStationRecord
         * @description Normalized national reference row. Unknown values are null, never zero or a guessed unit.
         */
        ReferenceStationRecord: {
            /** Antenna Gain Db */
            antenna_gain_db: number | null;
            /** Antenna Height Agl M */
            antenna_height_agl_m: number | null;
            /** Antenna Height Asl M */
            antenna_height_asl_m: number | null;
            /** Channel Bandwidth Hz */
            channel_bandwidth_hz: number | null;
            /** Directivity Code */
            directivity_code: string | null;
            /** Emission Bandwidth Hz */
            emission_bandwidth_hz: number | null;
            /** Ground Elevation M */
            ground_elevation_m: number | null;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Latitude Deg */
            latitude_deg: number | null;
            /** Licence Class Code */
            licence_class_code: string | null;
            /** Longitude Deg */
            longitude_deg: number | null;
            /** Mast Height M */
            mast_height_m: number | null;
            parse_status: components["schemas"]["RecordStatus"];
            /** Polarization Code */
            polarization_code: string | null;
            /** Radiation Power Itu Code Raw */
            radiation_power_itu_code_raw: string | null;
            /** Radiation Power Unit */
            radiation_power_unit: string | null;
            /** Radiation Power Value */
            radiation_power_value: number | null;
            /** Rx Frequency Hz */
            rx_frequency_hz: number | null;
            /** Source Record Id */
            source_record_id: string;
            /** Station Number Raw */
            station_number_raw: string | null;
            /** Transmission Line Db */
            transmission_line_db: number | null;
            /** Tx Frequency Hz */
            tx_frequency_hz: number | null;
        };
        /**
         * RelevanceGates
         * @description Separate gates. A frequency match alone never implies interference.
         */
        RelevanceGates: {
            /** Criterion Available */
            criterion_available: boolean | null;
            /** Frequency Match */
            frequency_match: boolean;
            /** Geometry Match */
            geometry_match: boolean | null;
            /** Label */
            label: string;
            /** Overlap End Mhz */
            overlap_end_mhz: number | null;
            /** Overlap Start Mhz */
            overlap_start_mhz: number | null;
            /** Reason Codes */
            reason_codes: string[];
            /** Rule Version */
            rule_version: string | null;
            /** Service Match */
            service_match: boolean | null;
            /** Technical Data Ready */
            technical_data_ready: boolean | null;
        };
        /**
         * ReviewAction
         * @enum {string}
         */
        ReviewAction: "ACCEPT_FINDING" | "REJECT_FINDING" | "NEEDS_MORE_DATA" | "FOLLOW_UP" | "CLOSE_NO_CONCERN" | "APPROVE_DRAFT" | "REJECT_DRAFT";
        /** ReviewCreateRequest */
        ReviewCreateRequest: {
            action: components["schemas"]["ReviewAction"];
            /** Analysis Run Id */
            analysis_run_id?: string | null;
            /** Decision Reason */
            decision_reason: string;
            /** Draft Id */
            draft_id?: string | null;
        };
        /**
         * ReviewEvent
         * @description Append-only. The actor comes from the validated identity, never the request.
         */
        ReviewEvent: {
            action: components["schemas"]["ReviewAction"];
            /** Actor Id */
            actor_id: string;
            /** Analysis Run Id */
            analysis_run_id: string | null;
            /** Case Id */
            case_id: string;
            /** Decision Reason */
            decision_reason: string;
            /** Draft Id */
            draft_id: string | null;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /**
             * Occurred At Utc
             * Format: date-time
             */
            occurred_at_utc: string;
            /** Review Event Id */
            review_event_id: string;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /**
         * ReviewStatus
         * @enum {string}
         */
        ReviewStatus: "NEW" | "IN_REVIEW" | "NEEDS_MORE_DATA" | "ACCEPTED" | "REJECTED" | "CLOSED";
        /**
         * Role
         * @enum {string}
         */
        Role: "ANALYST" | "REVIEWER" | "ADMINISTRATOR" | "DEMO_VIEWER";
        /** RowReconciliation */
        RowReconciliation: {
            /** Accepted */
            accepted: number;
            /** Flagged */
            flagged: number;
            /** Parsed */
            parsed: number;
            /** Rejected */
            rejected: number;
        };
        /** SourceArtifact */
        SourceArtifact: {
            /** Analysis Eligible */
            analysis_eligible: boolean;
            /** Artifact Id */
            artifact_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Byte Length */
            byte_length: number;
            /** Download Completed At Utc */
            download_completed_at_utc: string | null;
            /** Expected Digest */
            expected_digest: string | null;
            /** Expected Digest Origin */
            expected_digest_origin: string | null;
            /** Filename Original */
            filename_original: string;
            /**
             * First Seen At Utc
             * Format: date-time
             */
            first_seen_at_utc: string;
            /** Indexed At Utc */
            indexed_at_utc: string | null;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Parser Version */
            parser_version: string | null;
            /** Publication Id */
            publication_id: string | null;
            /** Published At Utc */
            published_at_utc: string | null;
            publisher_auth_status: components["schemas"]["PublisherAuthStatus"];
            /** Raw Sha256 */
            raw_sha256: string;
            /** Revision */
            revision: number;
            /** Source Id */
            source_id: string;
            status: components["schemas"]["ArtifactStatus"];
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /** SourceArtifactDetail */
        SourceArtifactDetail: {
            /** Analysis Eligible */
            analysis_eligible: boolean;
            /** Artifact Id */
            artifact_id: string;
            /** Artifact Type */
            artifact_type: string;
            /** Byte Length */
            byte_length: number;
            /** Download Completed At Utc */
            download_completed_at_utc: string | null;
            /** Expected Digest */
            expected_digest: string | null;
            /** Expected Digest Origin */
            expected_digest_origin: string | null;
            /** Filename Original */
            filename_original: string;
            /**
             * First Seen At Utc
             * Format: date-time
             */
            first_seen_at_utc: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Indexed At Utc */
            indexed_at_utc: string | null;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Parser Version */
            parser_version: string | null;
            /** Publication Id */
            publication_id: string | null;
            /** Published At Utc */
            published_at_utc: string | null;
            publisher_auth_status: components["schemas"]["PublisherAuthStatus"];
            /** Raw Sha256 */
            raw_sha256: string;
            /** Revision */
            revision: number;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Id */
            source_id: string;
            status: components["schemas"]["ArtifactStatus"];
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /** SourceArtifactList */
        SourceArtifactList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["SourceArtifact"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * SourceConnector
         * @description Connector status for clients. Endpoint and credential references stay server-side.
         */
        SourceConnector: {
            discovery_mode: components["schemas"]["DiscoveryMode"];
            domain: components["schemas"]["IssueDomain"];
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Last Checked At Utc */
            last_checked_at_utc: string | null;
            /** Last Success At Utc */
            last_success_at_utc: string | null;
            /** Poll Interval Seconds */
            poll_interval_seconds: number | null;
            /** Publisher */
            publisher: string;
            /** Rights Basis */
            rights_basis: string;
            /** Source Id */
            source_id: string;
            status: components["schemas"]["SourceHealthStatus"];
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /** SourceConnectorList */
        SourceConnectorList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["SourceConnector"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /** SourceHealth */
        SourceHealth: {
            discovery_mode: components["schemas"]["DiscoveryMode"];
            /** Expected Cadence Seconds */
            expected_cadence_seconds: number | null;
            failure_code: components["schemas"]["ErrorCode"] | null;
            /** Failure Summary */
            failure_summary: string | null;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Last Checked At Utc */
            last_checked_at_utc: string | null;
            /** Last Success At Utc */
            last_success_at_utc: string | null;
            /** Latest Known Issue Key */
            latest_known_issue_key: string | null;
            /** Pending Index Jobs */
            pending_index_jobs: number;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Id */
            source_id: string;
            status: components["schemas"]["SourceHealthStatus"];
        };
        /**
         * SourceHealthStatus
         * @enum {string}
         */
        SourceHealthStatus: "HEALTHY" | "SOURCE_STALE" | "SOURCE_UNAVAILABLE" | "ACCESS_DENIED" | "MANUAL_REQUIRED" | "DISABLED";
        /** SourceIssue */
        SourceIssue: {
            /** Content Sha256 */
            content_sha256: string;
            domain: components["schemas"]["IssueDomain"];
            /** Effective From */
            effective_from: string | null;
            /**
             * Ingested At Utc
             * Format: date-time
             */
            ingested_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Issue Number */
            issue_number: string | null;
            /** Parser Version */
            parser_version: string | null;
            /** Published On */
            published_on: string | null;
            /** Publisher */
            publisher: string;
            /** Source Issue Id */
            source_issue_id: string;
            source_type: components["schemas"]["SourceType"];
            usage_classification: components["schemas"]["UsageClassification"];
            validation_status: components["schemas"]["ValidationStatus"];
        };
        /** SourceLocation */
        SourceLocation: {
            /** Artifact Id */
            artifact_id: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Notice Id */
            notice_id: string | null;
            /** Parser Version */
            parser_version: string | null;
            /** Raw Record Sha256 */
            raw_record_sha256: string | null;
            /** Raw Sha256 */
            raw_sha256: string;
            /** Schema Version */
            schema_version: string | null;
            /** Source Page */
            source_page: number | null;
            /** Source Record Id */
            source_record_id: string | null;
            /** Source Row Or Key */
            source_row_or_key: string | null;
            /** Source Table Or Sheet */
            source_table_or_sheet: string | null;
        };
        /** SourceLocationDetail */
        SourceLocationDetail: {
            /** Artifact Id */
            artifact_id: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Notice Id */
            notice_id: string | null;
            /** Parser Version */
            parser_version: string | null;
            /** Raw Record Sha256 */
            raw_record_sha256: string | null;
            /** Raw Sha256 */
            raw_sha256: string;
            /** Schema Version */
            schema_version: string | null;
            /** Source Page */
            source_page: number | null;
            /** Source Record Id */
            source_record_id: string | null;
            /** Source Row Or Key */
            source_row_or_key: string | null;
            /** Source Table Or Sheet */
            source_table_or_sheet: string | null;
        };
        /**
         * SourcePreview
         * @description A bounded read-only slice of the original. It never carries the whole archive.
         */
        SourcePreview: {
            /** Artifact Id */
            artifact_id: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Next Cursor */
            next_cursor: string | null;
            /** Rows */
            rows: components["schemas"]["SourcePreviewRow"][];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
        };
        /** SourcePreviewRow */
        SourcePreviewRow: {
            /** Cells */
            cells: {
                [key: string]: string | null;
            };
            location: components["schemas"]["SourceLocation"];
        };
        /** SourcePublication */
        SourcePublication: {
            /**
             * First Seen At Utc
             * Format: date-time
             */
            first_seen_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            /**
             * Last Seen At Utc
             * Format: date-time
             */
            last_seen_at_utc: string;
            observation_status: components["schemas"]["ObservationStatus"];
            /** Provider Issue Key */
            provider_issue_key: string;
            /** Provider Version */
            provider_version: string | null;
            /** Publication Id */
            publication_id: string;
            /** Published At Utc */
            published_at_utc: string | null;
            /** Remote Size Bytes */
            remote_size_bytes: number | null;
            /** Source Id */
            source_id: string;
        };
        /** SourcePublicationList */
        SourcePublicationList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["SourcePublication"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * SourceRecordDetail
         * @description Original values beside their interpretation, for the indexed-record view.
         */
        SourceRecordDetail: {
            /** Analysis Eligibility */
            analysis_eligibility: {
                [key: string]: components["schemas"]["RecordStatus"];
            };
            /** Field Aliases */
            field_aliases: {
                [key: string]: string[];
            };
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Is Synthetic */
            is_synthetic: boolean;
            location: components["schemas"]["SourceLocation"];
            /** Quality Findings */
            quality_findings: components["schemas"]["RecordQualityFinding"][];
            /** Raw Fields */
            raw_fields: {
                [key: string]: string | null;
            };
            record_status: components["schemas"]["RecordStatus"];
            reference_station: components["schemas"]["ReferenceStationRecord"] | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Source Record Id */
            source_record_id: string;
        };
        /** SourceRecordHit */
        SourceRecordHit: {
            /** Administration */
            administration: string | null;
            /** Artifact Id */
            artifact_id: string;
            classification: components["schemas"]["UsageClassification"];
            /** Filename Original */
            filename_original: string;
            /** Frequency End Mhz */
            frequency_end_mhz: number | null;
            /** Frequency Start Mhz */
            frequency_start_mhz: number | null;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Issue Key */
            issue_key: string | null;
            /** Network Id */
            network_id: string | null;
            /** Publisher */
            publisher: string;
            record_status: components["schemas"]["RecordStatus"];
            /** Source Id */
            source_id: string;
            /** Source Record Id */
            source_record_id: string;
            /** Station Number */
            station_number: string | null;
        };
        /** SourceRecordList */
        SourceRecordList: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Items */
            items: components["schemas"]["SourceRecordHit"][];
            /** Limit */
            limit: number;
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Total If Known */
            total_if_known: number | null;
        };
        /**
         * SourceType
         * @enum {string}
         */
        SourceType: "SPACE_IFIC" | "TERRESTRIAL_IFIC" | "M4_ALLOCATION" | "FINLAND_FREQUENCY_INTEREST" | "CHALLENGE_SYNTHETIC_REFERENCE" | "REGULATORY_REFERENCE";
        /**
         * UploadCompleteRequest
         * @description The server hashes the final assembled bytes; the client digest is only compared to it.
         */
        UploadCompleteRequest: {
            /** Content Sha256 */
            content_sha256: string;
            /** Parts */
            parts: components["schemas"]["UploadCompletedPart"][];
        };
        /** UploadCompletedPart */
        UploadCompletedPart: {
            /** Etag */
            etag: string;
            /** Part Number */
            part_number: number;
        };
        /** UploadCreateRequest */
        UploadCreateRequest: {
            /** Content Sha256 */
            content_sha256?: string | null;
            /** Expected Size Bytes */
            expected_size_bytes: number;
            /** Filename Original */
            filename_original: string;
            source_type: components["schemas"]["SourceType"];
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /** UploadPartState */
        UploadPartState: {
            /** Etag */
            etag: string | null;
            /** Part Number */
            part_number: number;
            /** Received */
            received: boolean;
            /** Size Bytes */
            size_bytes: number;
        };
        /** UploadPartUrl */
        UploadPartUrl: {
            /**
             * Expires At Utc
             * Format: date-time
             */
            expires_at_utc: string;
            /** Part Number */
            part_number: number;
            /** Url */
            url: string;
        };
        /** UploadPartUrls */
        UploadPartUrls: {
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Parts */
            parts: components["schemas"]["UploadPartUrl"][];
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            /** Upload Id */
            upload_id: string;
        };
        /** UploadPartUrlsRequest */
        UploadPartUrlsRequest: {
            /** Part Numbers */
            part_numbers: number[];
        };
        /** UploadSession */
        UploadSession: {
            /** Completed At Utc */
            completed_at_utc: string | null;
            /** Content Sha256 */
            content_sha256: string | null;
            /**
             * Created At Utc
             * Format: date-time
             */
            created_at_utc: string;
            /** Expected Size Bytes */
            expected_size_bytes: number;
            /**
             * Expires At Utc
             * Format: date-time
             */
            expires_at_utc: string;
            failure_code: components["schemas"]["ErrorCode"] | null;
            /** Filename Original */
            filename_original: string;
            /**
             * Generated At Utc
             * Format: date-time
             */
            generated_at_utc: string;
            /** Job Id */
            job_id: string | null;
            /** Max Size Bytes */
            max_size_bytes: number;
            /** Part Size Bytes */
            part_size_bytes: number;
            /** Parts */
            parts: components["schemas"]["UploadPartState"][];
            /** Received Size Bytes */
            received_size_bytes: number;
            /**
             * Schema Version
             * @constant
             */
            schema_version: "1.0.0-draft.1";
            source_type: components["schemas"]["SourceType"];
            status: components["schemas"]["PipelineStatus"];
            /** Upload Id */
            upload_id: string;
            usage_classification: components["schemas"]["UsageClassification"];
        };
        /**
         * UsageClassification
         * @enum {string}
         */
        UsageClassification: "PUBLIC" | "INTERNAL" | "RESTRICTED" | "CONFIDENTIAL_PARTNER" | "UNVERIFIED";
        /**
         * ValidationStatus
         * @enum {string}
         */
        ValidationStatus: "VALID" | "VALID_WITH_WARNINGS" | "INVALID" | "PENDING";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_alert_rules_api_v1_admin_alert_rules_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRuleList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    save_alert_rule_api_v1_admin_alert_rules_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AlertRuleUpsert"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertRuleSaved"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    check_source_api_v1_admin_sources__source_id__check_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_alerts_api_v1_alerts_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["AlertStatus"] | null;
                severity?: components["schemas"]["AlertSeverity"] | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    update_alert_preferences_api_v1_alerts_preferences_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AlertPreferencesUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertPreferences"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    stream_alerts_api_v1_alerts_stream_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_alert_api_v1_alerts__alert_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                alert_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    acknowledge_alert_api_v1_alerts__alert_id__acknowledge_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                alert_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AlertAcknowledgeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AlertAcknowledged"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_analysis_api_v1_analyses__analysis_run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                analysis_run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_analysis_methods_api_v1_analyses__analysis_run_id__methods_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                analysis_run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MethodMatrix"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_cases_api_v1_cases_get: {
        parameters: {
            query?: {
                domain?: components["schemas"]["CaseDomain"] | null;
                source_issue_id?: string | null;
                change_type?: components["schemas"]["ChangeType"] | null;
                finding_status?: components["schemas"]["FindingStatus"] | null;
                review_status?: components["schemas"]["ReviewStatus"] | null;
                query?: string | null;
                sort?: components["schemas"]["CaseSort"];
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_case_api_v1_cases__case_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CaseDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    analyse_case_api_v1_cases__case_id__analyse_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalyseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_draft_api_v1_cases__case_id__drafts_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DraftCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftCreated"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    export_case_api_v1_cases__case_id__export_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidencePack"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_review_api_v1_cases__case_id__reviews_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewEvent"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    register_device_api_v1_devices_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeviceRegistrationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Device"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    revoke_device_api_v1_devices__device_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                device_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    ingest_ific_api_v1_ingest_ific_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IngestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobAccepted"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_issues_api_v1_issues_get: {
        parameters: {
            query?: {
                domain?: components["schemas"]["IssueDomain"] | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IssueList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_issue_changes_api_v1_issues__issue_id__changes_get: {
        parameters: {
            query?: {
                change_type?: components["schemas"]["ChangeType"] | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                issue_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NoticeChangeList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_job_api_v1_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobRun"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_me_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Me"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_references_api_v1_references_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReferenceList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_source_artifacts_api_v1_source_artifacts_get: {
        parameters: {
            query?: {
                source_id?: string | null;
                filename?: string | null;
                sha256?: string | null;
                status?: components["schemas"]["ArtifactStatus"] | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceArtifactList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_artifact_api_v1_source_artifacts__artifact_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artifact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceArtifactDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_download_link_api_v1_source_artifacts__artifact_id__download_link_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artifact_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DownloadLinkRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadLink"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_artifact_integrity_api_v1_source_artifacts__artifact_id__integrity_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artifact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArtifactIntegrityReport"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_artifact_preview_api_v1_source_artifacts__artifact_id__preview_get: {
        parameters: {
            query?: {
                page?: number | null;
                table?: string | null;
                row?: number | null;
                cursor?: string | null;
            };
            header?: never;
            path: {
                artifact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourcePreview"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_source_publications_api_v1_source_publications_get: {
        parameters: {
            query?: {
                source_id?: string | null;
                issue?: string | null;
                status?: components["schemas"]["ObservationStatus"] | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourcePublicationList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    search_source_records_api_v1_source_records_get: {
        parameters: {
            query?: {
                query?: string | null;
                station_number?: string | null;
                frequency_start_mhz?: number | null;
                frequency_end_mhz?: number | null;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceRecordList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_record_api_v1_source_records__source_record_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceRecordDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_record_location_api_v1_source_records__source_record_id__source_location_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_record_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceLocationDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_sources_api_v1_sources_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceConnectorList"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_source_health_api_v1_sources__source_id__health_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceHealth"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_upload_api_v1_uploads_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadSession"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_upload_api_v1_uploads__upload_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadSession"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    abort_upload_api_v1_uploads__upload_id__abort_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadSession"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    complete_upload_api_v1_uploads__upload_id__complete_post: {
        parameters: {
            query?: never;
            header: {
                "Idempotency-Key": string;
            };
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadCompleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadSession"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_upload_part_urls_api_v1_uploads__upload_id__parts_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UploadPartUrlsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UploadPartUrls"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Implemented */
            501: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
