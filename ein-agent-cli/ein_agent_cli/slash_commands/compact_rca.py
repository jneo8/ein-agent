"""Implementation of the /compact-rca slash command."""
import json

from rich.prompt import Prompt
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class CompactRCACommand(SlashCommand):
    """Compact all completed RCA workflows into summary."""

    @property
    def name(self) -> str:
        return "compact-rca"

    @property
    def description(self) -> str:
        return "Compact all completed RCA workflows into summary"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        context = session.get_current_context()
        if not context:
            console.print_error("No active context.")
            return CommandResult()

        console.print_newline()
        console.print_info("Checking RCA workflows...")

        # Get all completed RCA workflows
        completed_rcas = context.local_context.get_completed_rca_workflows()

        if not completed_rcas:
            console.print_error("No completed RCA workflows found in context.")
            console.print_info(
                "Use /alerts to start RCA workflows for your alerts first."
            )
            return CommandResult()

        console.print_success(
            f"Found {len(completed_rcas)} completed RCA workflow(s):"
        )

        # Display list of RCA workflows
        for rca in completed_rcas:
            alert_fingerprint = rca.alert_fingerprint
            alert_name = "unknown"
            if alert_fingerprint:
                alert_item = context.local_context.get_item(alert_fingerprint)
                if alert_item:
                    alert_name = alert_item.data.get("alertname", alert_fingerprint)

            console.print_message(f"- {rca.workflow_id} ({alert_name})")

        console.print_newline()

        # Ask for confirmation
        confirm = Prompt.ask(
            f"Create compact RCA from {len(completed_rcas)} workflows?",
            choices=["y", "n"],
            default="y",
        )

        if confirm.lower() != "y":
            console.print_info("Cancelled.")
            return CommandResult()

        console.print_newline()
        console.print_info("Starting compact RCA workflow...")

        # Prepare compact context
        rca_results = []
        source_workflow_ids = []

        for rca in completed_rcas:
            source_workflow_ids.append(rca.workflow_id)
            if rca.result:
                rca_results.append(
                    {
                        "workflow_id": rca.workflow_id,
                        "alert_fingerprint": rca.alert_fingerprint,
                        "result": rca.result,
                    }
                )

        # Build prompt for compact RCA workflow
        rca_results_json = json.dumps(rca_results, indent=2)

        prompt = f"""You are a summarization analyst. Your task is to analyze multiple RCA (Root Cause Analysis) outputs and create a compact summary.

You will be analyzing {len(completed_rcas)} RCA workflows.

RCA Results:
{rca_results_json}

Your task:
1. Analyze all RCA outputs
2. Identify common patterns and themes
3. Group related issues
4. Create a compact summary that captures:
   - Key findings across all RCAs
   - Common root causes
   - Patterns in failures
   - Recommended remediation strategies

The compact summary should be concise but comprehensive, suitable for use as context in enrichment RCA workflows.
"""

        console.print_dim("This workflow will:")
        console.print_message(f"- Analyze all {len(completed_rcas)} RCA outputs")
        console.print_message("- Identify common patterns")
        console.print_message("- Create compact summary")
        console.print_message("- Store result in local context")
        console.print_newline()
        console.print_info("Use /workflows to monitor progress.")
        console.print_info(
            "Once completed, you can run /start-enrichment-rca-workflows"
        )
        console.print_newline()

        # Return command result to create the compact RCA workflow
        return CommandResult(
            should_create_new=True,
            new_workflow_prompt=prompt,
            workflow_type="CompactRCA",
            source_workflow_ids=source_workflow_ids,
        )
