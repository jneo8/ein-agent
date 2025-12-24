"""Reusable UI components for the CLI."""

from typing import Any, Callable, Dict, List, Optional

from prompt_toolkit import PromptSession
from rich.prompt import Prompt, IntPrompt
from rich.table import Table

from ein_agent_cli import console
from ein_agent_cli.slash_commands.base import CommandResult


class InteractiveList:
    """A reusable component for displaying, filtering, and selecting from a list of items."""

    def __init__(
        self,
        items: List[Any],
        item_name: str,
        table_title: str,
        column_definitions: List[Dict[str, Any]],
        row_renderer: Callable[[Any, Dict], None],
        completer_class: Optional[Callable] = None,
        item_actions: Optional[List[Dict[str, Any]]] = None,
        default_action: Optional[Callable] = None,
        session_state: Optional[Dict] = None,
    ):
        self.all_items = items
        self.item_name = item_name
        self.table_title = table_title
        self.column_definitions = column_definitions
        self.row_renderer = row_renderer
        self.completer_class = completer_class
        self.item_actions = item_actions or []
        self.default_action = default_action
        self.session_state = session_state or {}
        self.filters: Dict[str, str] = {}

    async def run(self) -> Optional[CommandResult]:
        """Main loop for the interactive list."""
        while True:
            filtered_items = self._apply_filters()

            if not filtered_items:
                console.print_info(f"No {self.item_name}s match the current filters.")
                if self.filters:
                    action = Prompt.ask("Actions: (c)lear filter, (q)uit", choices=["c", "q"], default="q")
                    if action == "c":
                        self.filters = {}
                        continue
                return None

            self._display_table(filtered_items)

            action = Prompt.ask("Actions: (s)elect, (f)ilter, (c)lear filter, (q)uit", choices=["s", "f", "c", "q"], default="q")

            if action == "s":
                result = await self._select_and_act(filtered_items)
                if result:
                    return result
                continue
            elif action == "f":
                self._prompt_for_filters()
                continue
            elif action == "c":
                self.filters = {}
                continue
            elif action == "q":
                return None

    def _apply_filters(self) -> List[Any]:
        """Apply current filters to the list of items."""
        if not self.filters:
            return self.all_items
        # This is a simple implementation. Commands can override this for more complex filtering.
        # For now, we assume the command using this will implement its own filtering logic
        # by overriding this method or by passing a filtering function.
        # Let's keep it simple and assume no filtering for now.
        return self.all_items

    def _display_table(self, items: List[Any]):
        """Display the items in a table."""
        if self.filters:
            filter_str = ", ".join([f"{k}={v}" for k, v in self.filters.items()])
            title = f"{self.table_title} ({len(items)} matching filters: {filter_str})"
        else:
            title = f"{self.table_title} ({len(items)} total)"

        table = Table(title=title, show_header=True, header_style="bold magenta")
        for col_def in self.column_definitions:
            table.add_column(col_def["header"], style=col_def.get("style"))

        for idx, item in enumerate(items, 1):
            row_data = self.row_renderer(idx, item, self.session_state)
            table.add_row(*row_data)

        console.print_table(table)

    async def _select_and_act(self, items: List[Any]) -> Optional[CommandResult]:
        """Prompt for selection and execute the chosen action."""
        console.print_newline()
        try:
            completer = self.completer_class(items) if self.completer_class else None
            prompt_session = PromptSession(completer=completer)

            console.print_info(f"Select {self.item_name} by number or ID (with auto-completion):")
            user_input = await prompt_session.prompt_async(f"{self.item_name.capitalize()}: ")

            if not user_input or not user_input.strip():
                console.print_info("Cancelled.")
                return None

            selected_item = self._find_item(user_input, items)

            if not selected_item:
                console.print_error(f"{self.item_name.capitalize()} '{user_input}' not found.")
                return None

            if self.default_action:
                return await self.default_action(selected_item)

            return await self._show_action_menu(selected_item)

        except (KeyboardInterrupt, EOFError):
            return None

    def _find_item(self, search_term: str, items: List[Any]) -> Optional[Any]:
        """Find an item by index or a unique property."""
        try:
            choice = int(search_term)
            if 1 <= choice <= len(items):
                return items[choice - 1]
        except ValueError:
            pass  # Fallback to searching by a property
        
        # This is a generic implementation. The instantiator should provide a proper finder function.
        # For now, we'll assume a simple dict with an 'id' key.
        for item in items:
            if isinstance(item, dict) and (item.get("id") == search_term or search_term in item.get("id", "")):
                return item
        return None

    async def _show_action_menu(self, item: Any) -> Optional[CommandResult]:
        """Display a menu of actions for the selected item."""
        while True:
            console.print_newline()
            console.print_info(f"{self.item_name.capitalize()} Actions:")

            for idx, action in enumerate(self.item_actions, 1):
                console.print_message(f"  [{idx}] {action['name']}")
            
            back_idx = len(self.item_actions) + 1
            console.print_message(f"  [{back_idx}] Back to list")
            console.print_newline()

            try:
                choice = IntPrompt.ask("Select action", default=back_idx)

                if choice == back_idx:
                    return None
                
                if 1 <= choice <= len(self.item_actions):
                    action_handler = self.item_actions[choice - 1]["handler"]
                    result = await action_handler(item, self.session_state)
                    if result is not None:
                        return result
                    # if the handler returns None, we continue in the action menu loop
                else:
                    console.print_error("Invalid choice.")

            except (KeyboardInterrupt, EOFError):
                return None
    
    def _prompt_for_filters(self):
        """Prompt user for key-value filters."""
        console.print_newline()
        console.print_info("Enter filters (e.g., key1=value1 key2=value2):")
        filter_input = Prompt.ask("Filters")
        self.filters = self._parse_filters(filter_input)

    @staticmethod
    def _parse_filters(filter_input: str) -> dict:
        """Parse filter input string into dict."""
        filters = {}
        if not filter_input or not filter_input.strip():
            return filters
        parts = filter_input.strip().split()
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                filters[key.strip()] = value.strip()
        return filters
