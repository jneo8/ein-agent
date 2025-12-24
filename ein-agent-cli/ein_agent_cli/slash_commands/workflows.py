"""Implementation of the /workflows slash command."""
import json
from typing import Any, Dict, List, Optional

from rich.prompt import Prompt, IntPrompt
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import (
    CommandResult,
    SlashCommand,
    WorkflowCompleter,
)
from ein_agent_cli.ui import InteractiveList


class WorkflowsCommand(SlashCommand):
    """Manage workflows in local context with interactive filtering."""

    @property
    def name(self) -> str:
        return "workflows"

    @property
    def description(self) -> str:
        return "Manage workflows in local context"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        context = session.get_current_context()
        if not context:
            console.print_error("No active context.")
            return CommandResult()

        workflows = context.local_context.get_all_workflows()
        if not workflows:
            console.print_info("No workflows in local context.")
            console.print_info("Use /alerts to start RCA workflows for your alerts.")
            return CommandResult()

        interactive_list = InteractiveList(
            items=workflows,
            item_name="workflow",
            table_title="Workflows in Local Context",
            column_definitions=[
                {"header": "#", "style": "dim"},
                {"header": "Workflow ID", "style": "cyan"},
                {"header": "Type", "style": "green"},
                {"header": "Alert", "style": "yellow"},
                {"header": "Status", "style": "blue"},
            ],
            row_renderer=self._render_row,
            completer_class=lambda items: WorkflowCompleter(
                items, session.current_workflow_id
            ),
            item_actions=[
                {"name": "View full result", "handler": self._view_result},
                {"name": "Start enrichment RCA", "handler": self._start_enrichment_rca},
                {"name": "Switch to this workflow", "handler": self._switch_to_workflow},
                {"name": "Remove workflow from context", "handler": self._remove_workflow},
            ],
            session_state={
                "session": session,
                "config": config,
                "client": client,
                "context": context,
            },
        )
        result = await interactive_list.run()
        return result or CommandResult()

    def _render_row(self, idx: int, wf: Dict, session_state: Dict) -> List[str]:
        context = session_state["context"]
        workflow_id = wf.get("workflow_id", "")
        workflow_type = wf.get("type", "")
        status = wf.get("status", "")
        alert_fingerprint = wf.get("alert_fingerprint")

        alert_name = "-"
        if alert_fingerprint:
            alert_item = context.local_context.get_item(alert_fingerprint)
            alert_name = (
                alert_item.data.get("alertname", alert_fingerprint[:12] + "...")
                if alert_item
                else alert_fingerprint[:12] + "..."
            )

        display_id = (
            workflow_id if len(workflow_id) <= 30 else workflow_id[:27] + "..."
        )
        return [str(idx), display_id, workflow_type, alert_name, status]

    async def _view_result(self, wf: Dict, session_state: Dict) -> Optional[CommandResult]:
        result = wf.get("result")
        if result:
            console.print_newline()
            result_json = json.dumps(result, indent=2)
            console.print_message(result_json)
            console.print_newline()
            Prompt.ask("Press Enter to continue")
        else:
            console.print_info("No result available.")
        return None

    async def _start_enrichment_rca(
        self, wf: Dict, session_state: Dict
    ) -> Optional[CommandResult]:
        if not (wf.get("type") == "RCA" and wf.get("status") == "completed"):
            console.print_warning("Enrichment RCA can only be started for completed RCA workflows.")
            return None

        context = session_state["context"]
        if not context.local_context.compact_rca:
            console.print_error("Compact RCA not found in context. Run /compact-rca first.")
            return None
        if context.local_context.compact_rca.status != "completed":
            console.print_error("Compact RCA is not yet completed.")
            return None
            
        alert_fingerprint = wf.get("alert_fingerprint")
        alert_item = context.local_context.get_item(alert_fingerprint)
        if not alert_item:
            console.print_error(f"Alert not found: {alert_fingerprint}")
            return None

        enrichment_context = {
            "compact_rca_id": context.local_context.compact_rca.workflow_id,
            "compact_summary": context.local_context.compact_rca.result,
            "source_workflows": context.local_context.compact_rca.source_workflow_ids,
        }
        alert_details = json.dumps(alert_item.data, indent=2)
        enrichment_context_str = json.dumps(enrichment_context, indent=2)

        prompt = f"Perform enrichment RCA for this alert using compact RCA context.\n\nAlert details:\n{alert_details}\n\nEnrichment context (from compact RCA):\n{enrichment_context_str}"
        
        return CommandResult(
            should_create_new=True,
            new_workflow_prompt=prompt,
            workflow_type="EnrichmentRCA",
            alert_fingerprint=alert_fingerprint,
            enrichment_context=enrichment_context,
        )

    async def _switch_to_workflow(
        self, wf: Dict, session_state: Dict
    ) -> Optional[CommandResult]:
        session = session_state["session"]
        workflow_id = wf.get("workflow_id")
        if workflow_id == session.current_workflow_id:
            console.print_info("Already on this workflow.")
            return None
        return CommandResult(should_switch=True, workflow_id=workflow_id)

    async def _remove_workflow(
        self, wf: Dict, session_state: Dict
    ) -> Optional[CommandResult]:
        context = session_state["context"]
        workflow_id = wf.get("workflow_id", "")
        confirm = Prompt.ask(
            f"Remove workflow '{workflow_id}'?", choices=["y", "n"], default="n"
        )
        if confirm.lower() == "y":
            context.local_context.remove_workflow(workflow_id)
            console.print_success("Workflow removed from context.")
        return None
