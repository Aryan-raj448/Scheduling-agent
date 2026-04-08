---
title: Scheduling Assistant OpenEnv
emoji: 🗓️
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
tags:
  - openenv
  - benchmark
  - agents
---

# Scheduling Assistant - OpenEnv

## Motivation & Description
Corporate scheduling is notoriously difficult for LLM agents. While static QA benchmarks test reasoning in a vacuum, calendar management evaluates an agent's ability to act on temporal data, perform cross-timezone arithmetic, and navigate multi-step constraint satisfaction. This OpenEnv benchmark simulates a backend scheduling system to rigidly test these capabilities in a programmatic, autonomous evaluation loop.

## Setup & Running
The environment is containerized. It should run seamlessly via Docker or bare metal Python.

### Via Bare Metal:
```bash
cd scheduling_assistant
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."       # Or any valid proxy like Groq
export TASK_LEVEL="medium"           # "easy" | "medium" | "hard"
python inference.py
```

### Via Docker:
```bash
docker build -t openenv-scheduler .
docker run -e OPENAI_API_KEY="sk-..." -e TASK_LEVEL="easy" openenv-scheduler
```

## Action Space
The agent navigates the environment using the `step_environment` tool. The action schema expects a JSON object containing:
- `action_type`: Evaluated string routing. One of `['lookup_employee', 'view_calendar', 'book_meeting', 'cancel_meeting', 'submit_task']`
- `employee_ids`: Array of strings (e.g. `["charlie", "alice"]`)
- `start_time`: ISO 8601 string containing timezone information
- `end_time`: ISO 8601 string containing timezone information
- `meeting_id`: String (UUID) targeted for cancellation

## Observation Space
The environment emits a strict observation dictionary after every action:
- `current_simulated_time`: Static simulated execution time in ISO 8601.
- `task_description`: The specific instructions and targets for the chosen episode difficulty.
- `last_action_result`: Outcome array/string of the previously called functionality (e.g. returned calendars).
- `error_message`: Missing variables, formatting limitations, or failed logical constraint messages (e.g. "Outside working hours for {employee}").

## Task Descriptions & Difficulty

- **Easy**: Book a 30-minute sync between two people in the identical timezone (UTC) tomorrow. 
  - *Evaluation*: Tests basic JSON array filtering and time addition within standard constraints.
- **Medium**: Schedule a 1-hour global all-hands matching the active 9-to-5 working hours of 4 specific employees across distinct timezones (PST, EST, UTC, and CST).
  - *Evaluation*: Tests rigorous temporal overlap arithmetic. There is exactly one valid 1-hour global window where all 4 conditions are met. 
- **Hard**: The CEO needs an urgent sync that overlaps a booked slot. The agent must override a "low priority" internal meeting to book the VIP event, and reschedule the bumped meeting, all without cancelling "high priority" syncs.
  - *Evaluation*: Tests multi-hop logic, priority understanding, and state backtracking over multiple continuous actions.

## Baseline Scores
Testing was conducted locally with **`llama-3.3-70b-versatile`** (Groq) heavily capped by `MAX_STEPS = 15`.

| Difficulty | Baseline Score (Total Reward) | Observations |
| :--- | :--- | :--- |
| **Easy** | `1.0` | Successfully deduced calendar holes, passed the constraint checker, and successfully booked. |
| **Medium** | `0.2` | Successfully filtered out the employee IDs and scanned calendars, but critically failed to blindly deduce the precise global hour overlap. Trapped in an iterative trial-and-error cycle until max steps were reached. |
| **Hard** | `0.1 - 0.2` | Agent correctly maps the target IDs but is mathematically bottlenecked similar to the Medium benchmark. Exhausts tools prior to completion. |
