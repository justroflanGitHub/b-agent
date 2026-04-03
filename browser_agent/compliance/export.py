"""Export audit events to standard SIEM formats."""

import csv
import io
import json
from datetime import datetime
from typing import List


class AuditExporter:
    """Export audit events to external formats."""

    @staticmethod
    def to_json(events: list) -> str:
        """Export as JSON array."""
        return json.dumps([e.to_dict() for e in events], indent=2, default=str)

    @staticmethod
    def to_csv(events: list) -> str:
        """Export as CSV."""
        if not events:
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "event_id", "timestamp", "event_type", "tenant_id", "user_id",
            "task_id", "step_index", "action_type", "target_url", "target_element",
            "outcome", "error_message", "data_sensitivity", "session_id", "agent_id",
        ])
        for e in events:
            writer.writerow([
                e.event_id,
                e.timestamp.isoformat(),
                e.event_type.value,
                e.tenant_id,
                e.user_id,
                e.task_id,
                e.step_index,
                e.action_type,
                e.target_url,
                e.target_element,
                e.outcome,
                e.error_message,
                e.data_sensitivity.value if e.data_sensitivity else "",
                e.session_id,
                e.agent_id,
            ])
        return output.getvalue()

    @staticmethod
    def to_cef(events: list) -> str:
        """Export in Common Event Format (for Splunk, ArcSight)."""
        lines = []
        for e in events:
            severity = "Low"
            if e.data_sensitivity:
                from .audit_log import SensitivityLevel
                mapping = {
                    SensitivityLevel.PUBLIC: "Low",
                    SensitivityLevel.INTERNAL: "Low",
                    SensitivityLevel.CONFIDENTIAL: "Medium",
                    SensitivityLevel.RESTRICTED: "High",
                    SensitivityLevel.TOP_SECRET: "Very-High",
                }
                severity = mapping.get(e.data_sensitivity, "Low")

            if e.outcome == "failure":
                severity = "High"

            cef = (
                f"CEF:0|BrowserAgent|b-agent|1.0|{e.event_type.value}|"
                f"{e.event_type.value}|{severity}|"
                f"tenant={e.tenant_id} user={e.user_id} task={e.task_id or ''} "
                f"action={e.action_type or ''} url={e.target_url or ''} "
                f"outcome={e.outcome} msg={e.error_message or ''}"
            )
            lines.append(cef)
        return "\n".join(lines)

    @staticmethod
    def to_syslog(events: list) -> str:
        """Export in syslog format."""
        lines = []
        for e in events:
            priority = 134  # local0.info
            if e.outcome == "failure":
                priority = 131  # local0.err

            timestamp = e.timestamp.strftime("%b %d %H:%M:%S")
            msg = (
                f"browser-agent {e.event_type.value}: "
                f"tenant={e.tenant_id} user={e.user_id} "
                f"task={e.task_id or '-'} action={e.action_type or '-'} "
                f"outcome={e.outcome}"
            )
            lines.append(f"<{priority}>{timestamp} browser-agent {msg}")
        return "\n".join(lines)
