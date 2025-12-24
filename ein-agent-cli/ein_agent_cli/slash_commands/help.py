"""Implementation of the /help slash command."""
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, SessionState
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class HelpCommand(SlashCommand):
    """Displays available commands."""
    def __init__(self, registry: 'CommandRegistry'):
        self._registry = registry

    @property
    def name(self) -> str:
        return "help"
    
    @property
    def description(self) -> str:
        return "Show this help message"

    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState) -> CommandResult:
        console.print_info("Available commands:")
        commands = sorted(self._registry.get_all(), key=lambda cmd: cmd.name)
        for cmd in commands:
            console.print_message(f"  /{cmd.name.ljust(25)}- {cmd.description}")
        return CommandResult()
