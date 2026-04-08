import os
import uvicorn
from openenv.core import create_fastapi_app
from env import SchedulingEnv, Action, Observation

def make_env():
    task_level = os.getenv("TASK_LEVEL", "medium")
    return SchedulingEnv(task_level=task_level)

app = create_fastapi_app(
    env=make_env,
    action_cls=Action,
    observation_cls=Observation
)

@app.get("/")
def read_root():
    return {"status": "Running", "message": "OpenEnv Scheduling Assistant API is securely hosted and active! This environment is headless. Please direct programmatic agents to the /reset and /step POST endpoints."}

def main():
    port = int(os.getenv("PORT", 7860))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    main()
