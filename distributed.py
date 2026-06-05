from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
import asyncio

# -----------------------------
# Global Task Queue
# -----------------------------
task_queue = asyncio.Queue()


# -----------------------------
# Task Model
# -----------------------------
class Task(BaseModel):
    name: str


# -----------------------------
# Retry Decorator
# -----------------------------
def retry(max_attempts=3):

    def decorator(func):

        async def wrapper(*args, **kwargs):

            for attempt in range(max_attempts):

                try:
                    return await func(*args, **kwargs)

                except Exception as e:

                    print(
                        f"Attempt {attempt + 1} failed: {e}"
                    )

                    if attempt == max_attempts - 1:
                        print(
                            "Task permanently failed"
                        )

                    await asyncio.sleep(1)

        return wrapper

    return decorator


# -----------------------------
# Worker Class
# -----------------------------
class Worker:

    def __init__(self, worker_id):
        self.worker_id = worker_id

    @retry(max_attempts=3)
    async def process_task(self, task):

        print(
            f"Worker-{self.worker_id} processing {task}"
        )

        # Simulate task execution
        await asyncio.sleep(5)

        # Simulate failure
        if task.lower() == "fail":
            raise Exception(
                "Simulated Failure"
            )

        print(
            f"Worker-{self.worker_id} completed {task}"
        )

    async def start(self):

        while True:

            task = await task_queue.get()

            try:
                await self.process_task(task)

            except asyncio.CancelledError:
                break

            finally:
                task_queue.task_done()


# -----------------------------
# Lifespan Event Handler
# -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Starting Workers...")

    worker1 = Worker(1)
    worker2 = Worker(2)

    worker_task1 = asyncio.create_task(
        worker1.start()
    )

    worker_task2 = asyncio.create_task(
        worker2.start()
    )

    print("Workers Started")

    yield

    print("Stopping Workers...")

    worker_task1.cancel()
    worker_task2.cancel()

    await asyncio.gather(
        worker_task1,
        worker_task2,
        return_exceptions=True
    )

    print("Workers Stopped")


# -----------------------------
# FastAPI Application
# -----------------------------
app = FastAPI(
    title="Distributed Task Queue",
    version="1.0",
    lifespan=lifespan
)


# -----------------------------
# Home Route
# -----------------------------
@app.get("/")
async def home():

    return {
        "message": "Distributed Task Queue Running"
    }


# -----------------------------
# Submit Task
# -----------------------------
@app.post("/submit-task")
async def submit_task(task: Task):

    await task_queue.put(task.name)

    return {
        "status": "queued",
        "task": task.name,
        "queue_size": task_queue.qsize()
    }


# -----------------------------
# Queue Status
# -----------------------------
@app.get("/queue-size")
async def queue_size():

    return {
        "pending_tasks": task_queue.qsize()
    }