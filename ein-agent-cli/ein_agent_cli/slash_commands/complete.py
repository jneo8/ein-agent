"""Implementation of the /complete slash command."""
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class CompleteCommand(SlashCommand):
    """Completes the current workflow."""

    @property
    def name(self) -> str:
        return "complete"

    @property
    def description(self) -> str:
        return "Complete the current workflow without exiting the CLI"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        if not session.current_workflow_id:
            console.print_warning("No active workflow to complete.")
            return CommandResult()

        return CommandResult(should_complete=True)
