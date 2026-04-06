import os
import json
from openai import OpenAI
from env import SchedulingEnv, Action

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
    
    print("[START]")
    
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

    total_reward = 0.0
    
    for step_num in range(1, env.max_steps + 1):
        print(f"[STEP] {step_num}")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "step_environment"}}
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        tool_calls = response_message.tool_calls
        if not tool_calls:
            # Model failed to call a tool, force a submit task
            action = Action(action_type="submit_task")
            obs, reward, done = env.step(action)
            total_reward = reward
            break
            
        tool_call = tool_calls[0]
        try:
            action_args = json.loads(tool_call.function.arguments)
            action = Action(**action_args)
        except Exception as e:
            # Fallback if invalid action
            action = Action(action_type="submit_task")
            
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": json.dumps({"action_taken": action.model_dump()})
        })
        
        obs, reward, done = env.step(action)
        total_reward = reward
        
        messages.append({
            "role": "user",
            "content": f"Observation:\n{json.dumps(obs)}\nReward so far: {reward}"
        })
        
        if done:
            break

    print(f"[END] Final Reward: {total_reward}")

if __name__ == "__main__":
    main()
