"""calendar_tool.py — Calendar & reminder management using local JSON storage"""
import json, os, time
from datetime import datetime, timedelta

CALENDAR_FILE = "memory/calendar.json"

def _load():
    os.makedirs("memory", exist_ok=True)
    if not os.path.exists(CALENDAR_FILE):
        return []
    try:
        with open(CALENDAR_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def _save(events):
    os.makedirs("memory", exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(events, f, indent=2)

class CalendarTool:
    name = "calendar_tool"
    description = (
        "Manage calendar events and reminders. "
        "INPUT: JSON with 'action' and fields. "
        "Actions: add_event (title, date, time, notes), list_events (optional date filter), "
        "add_reminder (title, remind_at, notes), delete_event (id). "
        "OUTPUT: confirmation or list of events."
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if isinstance(input_str, str) else input_str
        except Exception:
            return "ERROR: Input must be valid JSON. Example: {\"action\":\"list_events\"}"

        action = data.get("action", "list_events")
        events = _load()

        if action == "add_event":
            event = {
                "id": f"evt_{int(time.time())}",
                "type": "event",
                "title": data.get("title", "Untitled"),
                "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
                "time": data.get("time", ""),
                "notes": data.get("notes", ""),
                "created_at": datetime.now().isoformat(),
            }
            events.append(event)
            _save(events)
            return f"✅ Event added: '{event['title']}' on {event['date']} {event['time']}"

        elif action == "add_reminder":
            reminder = {
                "id": f"rem_{int(time.time())}",
                "type": "reminder",
                "title": data.get("title", "Reminder"),
                "remind_at": data.get("remind_at", ""),
                "notes": data.get("notes", ""),
                "created_at": datetime.now().isoformat(),
            }
            events.append(reminder)
            _save(events)
            return f"🔔 Reminder set: '{reminder['title']}' at {reminder['remind_at']}"

        elif action == "list_events":
            if not events:
                return "No events or reminders found."
            date_filter = data.get("date", "")
            filtered = [e for e in events if not date_filter or e.get("date","").startswith(date_filter)]
            if not filtered:
                return f"No events found for date: {date_filter}"
            lines = ["📅 CALENDAR EVENTS & REMINDERS\n"]
            for e in sorted(filtered, key=lambda x: x.get("date", x.get("remind_at", ""))):
                if e["type"] == "event":
                    lines.append(f"[{e['id']}] 📌 {e['title']} — {e['date']} {e.get('time','')}")
                    if e.get("notes"): lines.append(f"    Notes: {e['notes']}")
                else:
                    lines.append(f"[{e['id']}] 🔔 {e['title']} — remind at: {e.get('remind_at','')}")
                    if e.get("notes"): lines.append(f"    Notes: {e['notes']}")
            return "\n".join(lines)

        elif action == "delete_event":
            eid = data.get("id", "")
            before = len(events)
            events = [e for e in events if e.get("id") != eid]
            _save(events)
            if len(events) < before:
                return f"🗑️ Deleted event/reminder: {eid}"
            return f"ERROR: Event not found: {eid}"

        else:
            return f"ERROR: Unknown action '{action}'. Use: add_event, add_reminder, list_events, delete_event"
