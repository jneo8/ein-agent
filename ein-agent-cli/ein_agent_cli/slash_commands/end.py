"""Implementation of the /end slash command."""
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class EndCommand(SlashCommand):
    """Ends the current conversation and exits the CLI."""

    @property
    def name(self) -> str:
        return "end"

    @property
    def description(self) -> str:
        return "End the conversation and close the workflow"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        console.print_warning("Exiting.")
        return CommandResult(should_exit=True)
