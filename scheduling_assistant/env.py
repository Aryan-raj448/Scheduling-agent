import uuid
from datetime import datetime, timedelta
import dateutil.parser
import pytz
from typing import Literal, List, Dict, Optional, Any
from pydantic import BaseModel, Field

class Observation(BaseModel):
    current_simulated_time: str
    task_description: str
    last_action_result: str
    error_message: str = ""

class Action(BaseModel):
    action_type: Literal['lookup_employee', 'view_calendar', 'book_meeting', 'cancel_meeting', 'submit_task']
    employee_ids: List[str] = Field(default_factory=list, description="List of employee IDs for lookups or meetings")
    start_time: Optional[str] = Field(None, description="ISO 8601 start time for the meeting")
    end_time: Optional[str] = Field(None, description="ISO 8601 end time for the meeting")
    meeting_id: Optional[str] = Field(None, description="ID of meeting to cancel")

EMPLOYEES = {
    "alice": {"id": "alice", "name": "Alice", "timezone": "UTC"},
    "bob": {"id": "bob", "name": "Bob", "timezone": "UTC"},
    "charlie": {"id": "charlie", "name": "Charlie", "timezone": "US/Pacific"},
    "dave": {"id": "dave", "name": "Dave", "timezone": "US/Eastern"},
    "eve": {"id": "eve", "name": "Eve", "timezone": "Asia/Kolkata"},
    "ceo": {"id": "ceo", "name": "CEO", "timezone": "US/Eastern"},
    "vp_sales": {"id": "vp_sales", "name": "VP of Sales", "timezone": "US/Pacific"}
}

class SchedulingEnv:
    def __init__(self, task_level: str = "easy"):
        self.task_level = task_level.lower()
        if self.task_level not in ["easy", "medium", "hard"]:
            self.task_level = "easy"
            
        self.max_steps = 15
        self.reset()
        
    def reset(self) -> Dict:
        self.current_step = 0
        # Simulated time is Oct 10 2023 08:00 UTC
        self.simulated_time = datetime(2023, 10, 10, 8, 0, 0, tzinfo=pytz.UTC)
        self.calendars = {k: [] for k in EMPLOYEES.keys()}
        self.task_state = {
            "calendar_lookups": set(),
            "found_valid_slot": False,
            "booked_successfully": False,
            "canceled_blocker": False,
            "rescheduled_blocker": False,
            "wrong_cancellation": False
        }
        
        self.target_meeting_id = None
        self.blocked_meeting_id = None
        self.high_priority_meeting_id = None
        
        self._setup_scenario()
        return self.state()

    def _setup_scenario(self):
        start_of_day = self.simulated_time.replace(hour=0, minute=0, second=0)
        
        if self.task_level == "easy":
            self.task_description = (
                "Book a 30-minute meeting between Alice and Bob (both in UTC). "
                "Find a non-conflicting time tomorrow (Oct 11) within their 9-to-5 working hours. "
                "When finished, run submit_task."
            )
            # Add some random meetings
            self._force_book("alice", start_of_day + timedelta(days=1, hours=9), start_of_day + timedelta(days=1, hours=10), "Sync 1")
            self._force_book("bob", start_of_day + timedelta(days=1, hours=9, minutes=30), start_of_day + timedelta(days=1, hours=10, minutes=30), "Sync 2")
            
        elif self.task_level == "medium":
            self.task_description = (
                "Schedule a 1-hour meeting for 4 people: Charlie (PST), Dave (EST), Alice (UTC), and Eve (IST). "
                "The meeting must fall specifically within the 9-to-5 local working hours of ALL 4 participants tomorrow (Oct 11). "
                "When finished, run submit_task."
            )
            self._force_book("eve", start_of_day + timedelta(days=1, hours=10), start_of_day + timedelta(days=1, hours=11), "Sync")
            
        elif self.task_level == "hard":
            self.task_description = (
                "The CEO needs an urgent 1-hour meeting tomorrow (Oct 11) with the VP of Sales. "
                "Their calendars are full. You must find a 'low priority' internal sync blocking them, cancel it, "
                "book the CEO + VP of Sales in that slot, and reschedule the canceled sync to another non-conflicting time tomorrow. "
                "Do NOT cancel 'high priority' meetings. Submit the task when finished."
            )
            # Fill tomorrow 9 to 5 PST (VP Sales hours) which restricts the slot heavily
            # CEO is EST. Valid overlap between EST (9-5) and PST (9-5) is 12:00 PM EST to 5:00 PM EST -> 9:00 AM PST to 2:00 PM PST
            # which is 17:00 UTC to 22:00 UTC.
            vp_start = start_of_day + timedelta(days=1, hours=17) # 9 AM PST
            
            # High Priority meeting
            self.high_priority_meeting_id = self._force_book(
                ["ceo", "vp_sales"], 
                vp_start, 
                vp_start + timedelta(hours=2), 
                "High Priority Client Pitch"
            )
            
            # Low Priority meeting
            self.blocked_meeting_id = self._force_book(
                ["ceo", "vp_sales"], 
                vp_start + timedelta(hours=3), # 20:00 UTC -> 12pm PST / 3pm EST
                vp_start + timedelta(hours=4), # 21:00 UTC -> 1pm PST / 4pm EST
                "Low priority internal sync"
            )
            
            # Pad the rest of the valid overlap with High Priority
            self._force_book(
                ["vp_sales"], 
                vp_start + timedelta(hours=2), 
                vp_start + timedelta(hours=3), 
                "High Priority Q3 Review"
            )

    def _force_book(self, emp_ids, start_time: datetime, end_time: datetime, title: str) -> str:
        if isinstance(emp_ids, str):
            emp_ids = [emp_ids]
        m_id = str(uuid.uuid4())
        for e in emp_ids:
            self.calendars[e].append({
                "id": m_id,
                "title": title,
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "participants": emp_ids
            })
        return m_id

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        try:
            dt = dateutil.parser.isoparse(time_str)
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            return dt
        except Exception:
            return None

    def _is_working_hours(self, emp_id: str, start_dt: datetime, end_dt: datetime) -> bool:
        tz_str = EMPLOYEES[emp_id]["timezone"]
        tz = pytz.timezone(tz_str)
        local_start = start_dt.astimezone(tz)
        local_end = end_dt.astimezone(tz)
        
        if local_start.date() != local_end.date():
            return False # crosses midnight locally
            
        start_hour = local_start.hour + local_start.minute / 60.0
        end_hour = local_end.hour + local_end.minute / 60.0
        return 9.0 <= start_hour and end_hour <= 17.0

    def _check_conflict(self, emp_id: str, start_dt: datetime, end_dt: datetime) -> bool:
        for m in self.calendars.get(emp_id, []):
            m_s = self._parse_time(m["start"])
            m_e = self._parse_time(m["end"])
            # Overlap condition
            if max(start_dt, m_s) < min(end_dt, m_e):
                return True
        return False

    def step(self, action: Action) -> tuple[Dict, float, bool]:
        self.current_step += 1
        reward = 0.0
        done = False
        last_action_result = ""
        error_message = ""
        
        if self.current_step >= self.max_steps:
            done = True
            error_message = f"Max steps ({self.max_steps}) reached."
            return self._finalize_step(last_action_result, error_message, done)

        if action.action_type == "lookup_employee":
            results = []
            for e_id in action.employee_ids:
                if e_id in EMPLOYEES:
                    results.append(EMPLOYEES[e_id])
                else:
                    error_message += f"Employee {e_id} not found. "
            if not error_message:
                last_action_result = str(results)

        elif action.action_type == "view_calendar":
            results = {}
            for e_id in action.employee_ids:
                if e_id in EMPLOYEES:
                    results[e_id] = self.calendars[e_id]
                    self.task_state["calendar_lookups"].add(e_id)
                else:
                    error_message += f"Employee {e_id} not found. "
            if not error_message:
                last_action_result = str(results)

        elif action.action_type == "book_meeting":
            if not action.start_time or not action.end_time or not action.employee_ids:
                error_message = "book_meeting requires start_time, end_time, and employee_ids."
            else:
                s_dt = self._parse_time(action.start_time)
                e_dt = self._parse_time(action.end_time)
                
                if not s_dt or not e_dt or s_dt >= e_dt:
                    error_message = "Invalid times provided."
                else:
                    # check constraints
                    valid = True
                    for e_id in action.employee_ids:
                        if e_id not in EMPLOYEES:
                            error_message += f"Employee {e_id} missing. "
                            valid = False
                            continue
                        if not self._is_working_hours(e_id, s_dt, e_dt):
                            error_message += f"Outside working hours for {e_id}. "
                            valid = False
                        if self._check_conflict(e_id, s_dt, e_dt):
                            error_message += f"Schedule conflict for {e_id}. "
                            valid = False
                    
                    if valid:
                        meeting_id = self._force_book(action.employee_ids, s_dt, e_dt, "Agent Booked Sync")
                        last_action_result = f"Successfully booked. Meeting ID: {meeting_id}"
                        
                        # Task tracking logic
                        dur = (e_dt - s_dt).total_seconds() / 60.0
                        if self.task_level == "easy" and set(action.employee_ids) == {"alice", "bob"} and dur >= 30:
                            self.task_state["booked_successfully"] = True
                            
                        elif self.task_level == "medium" and set(action.employee_ids) == {"charlie", "dave", "alice", "eve"} and dur >= 60:
                            self.task_state["booked_successfully"] = True
                            
                        elif self.task_level == "hard":
                            if set(action.employee_ids) == {"ceo", "vp_sales"} and dur >= 60:
                                self.task_state["booked_successfully"] = True
                            if "ceo" in action.employee_ids and "vp_sales" in action.employee_ids and self.task_state["canceled_blocker"]:
                                # they are booking the CEO/VP in the freed slot
                                pass
                            if len(action.employee_ids) == 2 and "ceo" in action.employee_ids and "vp_sales" in action.employee_ids and self.task_state["canceled_blocker"]:
                                # Maybe this is the rescheduled sync? No, the rescheduled is just the same internal sync.
                                # Let's assume the agent uses the same participants or general booking.
                                pass
                                
                            # If they are rescheduling the canceled sync, they need to book anyone else, but the canceled meeting was with ceo, vp_sales
                            # If they make another booking after booking the top priority, we count it.
                            if self.task_state["booked_successfully"] and not set(action.employee_ids) == {"ceo", "vp_sales"}:
                                # Hacky check for rescheduling
                                pass
                            if self.task_state["canceled_blocker"]:
                                # They booked *something* after canceling. Let's count it if it's the right participants (ceo, vp_sales) but not the main one?
                                # Actually, original had CEO + VP Sales. So they just re-book them.
                                if set(action.employee_ids) == {"ceo", "vp_sales"} and self.task_state["booked_successfully"]:
                                     self.task_state["rescheduled_blocker"] = True
                                     
                        self.target_meeting_id = meeting_id

        elif action.action_type == "cancel_meeting":
            if not action.meeting_id:
                error_message = "cancel_meeting requires meeting_id."
            else:
                found = False
                for emp, cals in self.calendars.items():
                    cals_new = [m for m in cals if m["id"] != action.meeting_id]
                    if len(cals_new) < len(cals):
                        self.calendars[emp] = cals_new
                        found = True
                
                if found:
                    last_action_result = f"Meeting {action.meeting_id} canceled."
                    if self.task_level == "hard":
                        if action.meeting_id == self.blocked_meeting_id:
                            self.task_state["canceled_blocker"] = True
                        elif action.meeting_id == self.high_priority_meeting_id:
                            self.task_state["wrong_cancellation"] = True
                else:
                    error_message = "Meeting ID not found."

        elif action.action_type == "submit_task":
            done = True
            last_action_result = "Task submitted."

        return self._finalize_step(last_action_result, error_message, done)

    def _finalize_step(self, last_action_result: str, error_message: str, done: bool) -> tuple[Dict, float, bool]:
        reward = self._calculate_reward()
        obs = Observation(
            current_simulated_time=self.simulated_time.isoformat(),
            task_description=self.task_description,
            last_action_result=last_action_result,
            error_message=error_message
        )
        return obs.model_dump(), reward, done

    def _calculate_reward(self) -> float:
        r = 0.0
        
        if self.task_level == "easy":
            if "alice" in self.task_state["calendar_lookups"]: r += 0.1
            if "bob" in self.task_state["calendar_lookups"]: r += 0.1
            # Found time happens during book_meeting validation
            # Booked gives remaining
            if self.task_state["booked_successfully"]: r += 0.8
            
        elif self.task_level == "medium":
            for e in ["charlie", "dave", "alice", "eve"]:
                if e in self.task_state["calendar_lookups"]:
                    r += 0.05 # up to 0.2
            if self.task_state["booked_successfully"]:
                r += 0.8
                
        elif self.task_level == "hard":
            for e in ["ceo", "vp_sales"]:
                if e in self.task_state["calendar_lookups"]: r += 0.1
            
            if self.task_state["canceled_blocker"]: r += 0.2
            if self.task_state["wrong_cancellation"]: r -= 0.5
            if self.task_state["booked_successfully"]: r += 0.3
            if self.task_state["rescheduled_blocker"]: r += 0.3
            
        return max(min(r, 1.0), 0.0)

    def state(self) -> Dict:
        return Observation(
            current_simulated_time=self.simulated_time.isoformat(),
            task_description=self.task_description,
            last_action_result="",
            error_message=""
        ).model_dump()
