"""Simple Hello World workflow for testing."""

from temporalio import workflow


@workflow.defn
class HelloWorkflow:
    """A simple workflow that returns a greeting."""

    @workflow.run
    async def run(self, name: str) -> str:
        """
        Run the workflow.

        Args:
            name: The name to greet

        Returns:
            A greeting message
        """
        workflow.logger.info(f"HelloWorkflow started with name: {name}")
        message = f"Hello, {name}! Welcome to Temporal."
        workflow.logger.info(f"HelloWorkflow completed")
        return message
