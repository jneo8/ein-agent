"""Implementation of the /refresh slash command."""
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand
from ein_agent_cli.temporal import get_workflow_status


class RefreshCommand(SlashCommand):
    """Gets the latest status of the current workflow."""

    @property
    def name(self) -> str:
        return "refresh"

    @property
    def description(self) -> str:
        return "Get the latest workflow status"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        if not session.current_workflow_id:
            console.print_warning("No active workflow to refresh.")
            return CommandResult()

        console.print_info("Refreshing workflow status...")
        try:
            status = await get_workflow_status(client, session.current_workflow_id)
            console.print_success(f"State: {status.state}")
            if status.current_question:
                console.print_newline()
                console.print_message(status.current_question)
            if status.suggested_mcp_tools:
                console.print_dim(
                    f"Suggested tools: {', '.join(status.suggested_mcp_tools)}"
                )
        except Exception as e:
            console.print_error(f"Failed to refresh status: {e}")
        return CommandResult()
