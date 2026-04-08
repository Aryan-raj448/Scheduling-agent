import os
import json
from typing import List, Optional
from openai import OpenAI
from env import SchedulingEnv, Action
from dotenv import load_dotenv

load_dotenv()

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = str(error).replace('\n', ' ') if error else "null"
    done_val = str(done).lower()
    # clean newlines from action
    action = action.replace('\n', ' ')
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)

def main():
    hf_token = os.getenv("HF_TOKEN")
    api_key = os.getenv("OPENAI_API_KEY")
    
    if api_key:
        api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
    elif hf_token:
        api_key = hf_token
        api_base_url = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
    else:
        # Fallback if neither are set
        api_key = "sk-..."
        api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
        
    model_name = os.getenv("MODEL_NAME", "gpt-4o")

    client = OpenAI(
        base_url=api_base_url,
        api_key=api_key,
    )

    task_level = os.getenv("TASK_LEVEL", "easy")
    env = SchedulingEnv(task_level=task_level)
    
    obs = env.reset()
    
    log_start(task=task_level, env="scheduling_benchmark", model=model_name)
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI Scheduling Assistant. "
                "You manage calendars, check availability, and book meetings. "
                "Always use the `step_environment` tool to take actions. "
                "You must carefully read the task description and take iterative steps. "
                "Do not assume availability, check calendars first."
            )
        },
        {
            "role": "user",
            "content": f"Initial Observation:\n{json.dumps(obs)}"
        }
    ]

    action_schema = Action.model_json_schema()
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "step_environment",
                "description": "Execute an action in the environment.",
                "parameters": action_schema
            }
        }
    ]

    rewards_list = []
    total_reward = 0.0
    steps_taken = 0
    done = False
    
    for step_num in range(1, env.max_steps + 1):
        steps_taken = step_num
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "step_environment"}}
            )
        except Exception as e:
            error_msg = f"Model API Error: {str(e)}"
            log_step(step=step_num, action="api_call_failed", reward=total_reward, done=True, error=error_msg)
            break
            
        response_message = response.choices[0].message
        messages.append(response_message)
        
        tool_calls = response_message.tool_calls
        if not tool_calls:
            # Model failed to call a tool, force a submit task
            action = Action(action_type="submit_task")
            action_str = "submit_task (force_fallback)"
            obs, reward, done = env.step(action)
            total_reward = reward
            rewards_list.append(reward)
            log_step(step=step_num, action=action_str, reward=reward, done=done, error=obs['error_message'])
            break
            
        tool_call = tool_calls[0]
        action_args_str = tool_call.function.arguments
        try:
            action_args = json.loads(action_args_str)
            action = Action(**action_args)
        except Exception as e:
            # Fallback if invalid action
            action = Action(action_type="submit_task")
            action_args_str = f"INVALID_JSON: {action_args_str}"
            
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps({"action_taken": action.model_dump()})
        })
        
        obs, reward, done = env.step(action)
        total_reward = reward
        rewards_list.append(reward)
        
        # log step as per stdout rules
        log_step(step=step_num, action=action_args_str, reward=reward, done=done, error=obs.get('error_message'))
        
        if done:
            break
            
        messages.append({
            "role": "user",
            "content": f"Observation:\n{json.dumps(obs)}\nReward so far: {reward}"
        })

    success = total_reward >= 1.0
    log_end(success=success, steps=steps_taken, score=total_reward, rewards=rewards_list)

if __name__ == "__main__":
    main()
