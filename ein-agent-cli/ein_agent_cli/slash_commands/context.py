"""Implementation of the /context slash command."""
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class ContextCommand(SlashCommand):
    """Show local context summary."""

    @property
    def name(self) -> str:
        return "context"

    @property
    def description(self) -> str:
        return "Show context summary"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        """Display summary of local context."""
        console.print_newline()
        console.print_header("Local Context Summary")
        console.print_newline()

        context = session.local_context

        # Count alerts
        alert_count = len(context.items)
        firing_count = sum(
            1 for item in context.items.values() if item.data.get("status") == "firing"
        )
        resolved_count = sum(
            1
            for item in context.items.values()
            if item.data.get("status") == "resolved"
        )

        # Count workflows by type and status
        rca_total = len(context.rca_workflows)
        rca_completed = sum(
            1 for w in context.rca_workflows.values() if w.status == "completed"
        )
        rca_running = sum(
            1 for w in context.rca_workflows.values() if w.status == "running"
        )

        enrichment_total = len(context.enrichment_rca_workflows)
        enrichment_completed = sum(
            1
            for w in context.enrichment_rca_workflows.values()
            if w.status == "completed"
        )
        enrichment_running = sum(
            1
            for w in context.enrichment_rca_workflows.values()
            if w.status == "running"
        )

        # Total workflows
        total_workflows = rca_total + enrichment_total
        if context.compact_rca:
            total_workflows += 1
        if context.compact_enrichment_rca:
            total_workflows += 1
        if context.incident_summary:
            total_workflows += 1

        # Display summary
        console.print_message(
            f"Alerts:               {alert_count} ({firing_count} firing, {resolved_count} resolved)"
        )
        console.print_message(f"Workflows:            {total_workflows} total")
        console.print_message(
            f"  - RCA:              {rca_total} ({rca_completed} completed, {rca_running} running)"
        )
        console.print_message(
            f"  - EnrichmentRCA:    {enrichment_total} ({enrichment_completed} completed, {enrichment_running} running)"
        )

        # Compact outputs
        compact_count = 0
        if context.compact_rca:
            compact_count += 1
        if context.compact_enrichment_rca:
            compact_count += 1
        if compact_count > 0:
            compact_types = []
            if context.compact_rca:
                compact_types.append("CompactRCA")
            if context.compact_enrichment_rca:
                compact_types.append("CompactEnrichmentRCA")
            console.print_message(
                f"Compact Outputs:      {compact_count} ({', '.join(compact_types)})"
            )

        console.print_newline()

        return CommandResult()
