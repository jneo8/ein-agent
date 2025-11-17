"""Temporal worker for Catcher Agent."""

import asyncio
import os
from temporalio.client import Client
from temporalio.worker import Worker

from catcher_agent_worker.workflows.helloworld import HelloWorkflow


async def main():
    """Start the Temporal worker."""
    # Get config from environment (injected by temporal-worker-k8s-operator)
    host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    namespace = os.getenv("TWC_NAMESPACE", "default")
    queue = os.getenv("TEMPORAL_QUEUE", "catcher-agent-queue")

    print(f"Connecting to Temporal: host={host}, namespace={namespace}, queue={queue}")

    # Create Temporal client
    client = await Client.connect(host, namespace=namespace)

    # Create worker
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[HelloWorkflow],
    )

    print(f"Worker started successfully on queue: {queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
