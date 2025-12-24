"""Implementation of the /new slash command."""
from rich.prompt import Prompt
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import (
    Context,
    HumanInLoopConfig,
    LocalContext,
    SessionState,
)
from ein_agent_cli.session_storage import generate_context_id
from ein_agent_cli.slash_commands.base import CommandResult, SlashCommand


class NewCommand(SlashCommand):
    """Create a new investigation context."""

    @property
    def name(self) -> str:
        return "new"

    @property
    def description(self) -> str:
        return "Create a new investigation context"

    async def execute(
        self, args: str, config: HumanInLoopConfig, client: TemporalClient, session: SessionState
    ) -> CommandResult:
        # Parse optional context name from args
        context_name = args.strip() if args.strip() else None

        # Prompt for context name if not provided
        if not context_name:
            context_name = Prompt.ask(
                "Context name (optional, press Enter to skip)", default=""
            )
            if not context_name:
                context_name = None

        # Generate new context
        new_context = Context(
            context_id=generate_context_id(),
            context_name=context_name,
            local_context=LocalContext(),
        )

        # Add to session and switch to it
        session.add_context(new_context)

        console.print_newline()
        console.print_success(f"Created new context: {new_context.context_id}")
        if context_name:
            console.print_info(f"Name: {context_name}")
        console.print_info(f"Total contexts: {len(session.contexts)}")
        console.print_newline()

        return CommandResult()
