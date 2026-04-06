# Scheduling Assistant - OpenEnv

A simulated corporate scheduling backend. The agent acts as a resource coordinator managing calendars, timezone math, and meeting conflicts.

## Overview
This environment evaluates an agent's ability to:
1. Lookup employee information (names, timezones)
2. View cross-timezone calendars and manage overlap.
3. Successfully book and prioritize syncs across different levels of complexity.

Strict constraints:
- Built purely in Python without external databases to comply with 2 vCPU and 8GB RAM restrictions on Hugging Face Spaces.

## Task Difficulties (`TASK_LEVEL`)
- **Easy**: Book a 30-minute sync between two people in the same timezone (UTC).
- **Medium**: Schedule a 1-hour global all-hands matching the 9-to-5 working hours of 4 employees across PST, EST, UTC, and IST.
- **Hard**: Override a low priority meeting to book a last-minute VIP event, enforcing priority logic without cancelling critical syncs.

## Action Space
`Action` expects a JSON object containing:
- `action_type`: One of `['lookup_employee', 'view_calendar', 'book_meeting', 'cancel_meeting', 'submit_task']`
- `employee_ids`: Array of strings
- `start_time`: ISO 8601 string
- `end_time`: ISO 8601 string
- `meeting_id`: String (uuid)

## Observation Space
`Observation` returns:
- `current_simulated_time`: ISO 8601
- `task_description`: Instructions for the episode
- `last_action_result`: Outcome of the previous tool call
- `error_message`: Formatting limitations or failed constraint messages

## Setup & Running

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
export TASK_LEVEL="hard" # "easy" | "medium" | "hard"
python inference.py
```
