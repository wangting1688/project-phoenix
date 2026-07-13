import asyncio
from typing import Callable, Any
import time


def run_workflow_sync(workflow_func: Callable, *args, **kwargs) -> Any:
    return workflow_func(*args, **kwargs)


async def run_workflow_async(workflow_func: Callable, *args, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, workflow_func, *args, **kwargs)


class TaskExecutor:
    @staticmethod
    def execute(task_id: int, workflow_instance, callback: Callable = None):
        try:
            result = workflow_instance.execute()
            if callback:
                callback(task_id, result)
            return result
        except Exception as e:
            if callback:
                callback(task_id, {"error": str(e)})
            raise

    @staticmethod
    async def execute_async(task_id: int, workflow_instance, callback: Callable = None):
        try:
            result = await run_workflow_async(workflow_instance.execute)
            if callback:
                callback(task_id, result)
            return result
        except Exception as e:
            if callback:
                callback(task_id, {"error": str(e)})
            raise


def simulate_ai_delay(base_delay: float = 0.5, variance: float = 0.3) -> None:
    import random
    delay = base_delay + random.uniform(-variance, variance)
    time.sleep(max(0.1, delay))
