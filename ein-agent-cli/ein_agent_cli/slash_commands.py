"""Implementation of interactive slash commands."""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any

from rich.prompt import Prompt, IntPrompt
from rich.table import Table
from temporalio.client import Client as TemporalClient

from ein_agent_cli import console
from ein_agent_cli.models import HumanInLoopConfig, WorkflowStatus
from ein_agent_cli.temporal import get_workflow_status, list_workflows


class CommandResult:
    """Result of a command execution, signaling how the main loop should proceed."""
    def __init__(self, should_continue: bool = True, should_exit: bool = False, workflow_id: Optional[str] = None):
        self.should_continue = should_continue
        self.should_exit = should_exit
        self.workflow_id = workflow_id


class SlashCommand(ABC):
    """Abstract base class for an interactive slash command."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the command (e.g., 'help')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A short description of the command."""
        pass
    
    @abstractmethod
    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        """
        Executes the command.

        Args:
            args: The arguments string passed to the command.
            config: The active human-in-the-loop configuration.
            client: The connected Temporal client.
            workflow_id: The current workflow ID, if any.
        
        Returns:
            A CommandResult indicating the desired next state of the interactive loop.
        """
        pass


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

    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        console.print_info("Available commands:")
        commands = sorted(self._registry.get_all(), key=lambda cmd: cmd.name)
        for cmd in commands:
            console.print_message(f"  /{cmd.name.ljust(25)}- {cmd.description}")
        return CommandResult()


class WorkflowsCommand(SlashCommand):
    """Lists workflows, with an option to filter by status."""
    @property
    def name(self) -> str:
        return "workflows"

    @property
    def description(self) -> str:
        return "List workflows, with an option to filter by status"

    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        
        status_filter = args.strip().capitalize()
        valid_statuses = ["Running", "Completed", "Failed", "Canceled", "Terminated", "TimedOut", "All"]

        if status_filter not in valid_statuses:
            console.print_info("Select a workflow status to filter by:")
            for i, status in enumerate(valid_statuses):
                console.print_message(f"  [{i+1}] {status}")
            
            while True:
                try:
                    choice = IntPrompt.ask("Enter selection", default=1)
                    if 1 <= choice <= len(valid_statuses):
                        status_filter = valid_statuses[choice - 1]
                        break
                    else:
                        console.print_error(f"Please enter a number between 1 and {len(valid_statuses)}.")
                except (ValueError, TypeError):
                     console.print_error("Invalid input. Please enter a number.")

        title = f"{status_filter} Temporal Workflows" if status_filter.lower() != 'all' else "All Temporal Workflows"
        
        workflows = await list_workflows(config.temporal, status_filter)
        if not workflows:
            console.print_info(f"No {status_filter.lower()} workflows found.")
            return CommandResult()

        table = Table(
            "Workflow ID", "Workflow Type", "Start Time", "Status", "Task Queue",
            title=title, show_header=True, header_style="bold magenta"
        )
        for wf in workflows:
            table.add_row(
                wf.get("workflow_id", "N/A"), wf.get("workflow_type", "N/A"),
                wf.get("start_time", "N/A"), wf.get("status", "N/A"),
                wf.get("task_queue", "N/A")
            )
        console.print_table(table)
        return CommandResult()


class RefreshCommand(SlashCommand):
    """Gets the latest status of the current workflow."""
    @property
    def name(self) -> str:
        return "refresh"
    
    @property
    def description(self) -> str:
        return "Get the latest workflow status"

    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        if not workflow_id:
            console.print_warning("No active workflow to refresh.")
            return CommandResult()

        console.print_info("Refreshing workflow status...")
        try:
            status = await get_workflow_status(client, workflow_id)
            console.print_success(f"State: {status.state}")
            if status.current_question:
                console.print_newline()
                console.print_message(status.current_question)
            if status.suggested_mcp_tools:
                console.print_dim(f"Suggested tools: {', '.join(status.suggested_mcp_tools)}")
        except Exception as e:
            console.print_error(f"Failed to refresh status: {e}")
        return CommandResult()


class EndCommand(SlashCommand):
    """Ends the current conversation and exits the CLI."""
    @property
    def name(self) -> str:
        return "end"

    @property
    def description(self) -> str:
        return "End the conversation and close the workflow"
    
    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        console.print_warning("Exiting.")
        return CommandResult(should_exit=True)


class ConnectWorkflowCommand(SlashCommand):
    """Connects to an existing workflow."""
    @property
    def name(self) -> str:
        return "connect-workflow"

    @property
    def description(self) -> str:
        return "Connect to an existing workflow: /connect-workflow <workflow-id>"

    async def execute(self, args: str, config: HumanInLoopConfig, client: TemporalClient, workflow_id: Optional[str]) -> CommandResult:
        new_workflow_id = args.strip()
        if not new_workflow_id:
            console.print_error("Please provide a workflow ID.")
            return CommandResult()

        console.print_info(f"Connecting to workflow: {new_workflow_id}")
        try:
            status = await get_workflow_status(client, new_workflow_id)
            if status.state in ["completed", "failed"]:
                console.print_error(f"Cannot connect: workflow is {status.state}")
                return CommandResult()

            console.print_success(f"✓ Connected to workflow: {new_workflow_id}")
            console.print_dim(f"Current state: {status.state}")
            return CommandResult(should_continue=False, workflow_id=new_workflow_id)
        except Exception as e:
            console.print_error(f"Failed to connect to workflow: {e}")
            return CommandResult()


class CommandRegistry:
    """A registry for slash commands."""
    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}
        # The help command needs a reference to the registry itself
        self.register(HelpCommand(self))

    def register(self, command: SlashCommand):
        """Registers a command."""
        self._commands[command.name] = command

    def find(self, name: str) -> Optional[SlashCommand]:
        """Finds a command by its name."""
        return self._commands.get(name)
    
    def get_all(self) -> list[SlashCommand]:
        """Returns a list of all registered commands."""
        return list(self._commands.values())


async def handle_command(
    user_input: str,
    registry: CommandRegistry,
    config: HumanInLoopConfig,
    client: TemporalClient,
    workflow_id: Optional[str]
) -> CommandResult:
    """
    Parses and executes a slash command from user input.

    Args:
        user_input: The raw string from the user.
        registry: The command registry.
        config: The active human-in-the-loop configuration.
        client: The connected Temporal client.
        workflow_id: The current workflow ID, if any.
        
    Returns:
        The result of the command execution.
    """
    if not user_input.startswith('/'):
        return CommandResult(should_continue=False) # Not a command, probably a text response

    parts = user_input.strip()[1:].split(' ', 1)
    command_name = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    command = registry.find(command_name)
    if not command:
        console.print_error(f"Unknown command: /{command_name}")
        return CommandResult()

    return await command.execute(args, config, client, workflow_id)
