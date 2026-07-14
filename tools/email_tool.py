"""email_tool.py — AI-assisted email draft composer (local, no credentials needed)"""
import json, os, time

DRAFTS_FILE = "memory/email_drafts.json"

def _load_drafts():
    os.makedirs("memory", exist_ok=True)
    if not os.path.exists(DRAFTS_FILE):
        return []
    try:
        with open(DRAFTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def _save_drafts(drafts):
    os.makedirs("memory", exist_ok=True)
    with open(DRAFTS_FILE, "w") as f:
        json.dump(drafts, f, indent=2)

class EmailDraftTool:
    name = "email_draft"
    description = (
        "Compose, save, and list email drafts. "
        "INPUT: JSON with 'action' and fields. "
        "Actions: compose (to, subject, body_prompt, tone), list_drafts, get_draft (id), delete_draft (id). "
        "For 'compose': provide to, subject, and either body (raw text) or body_prompt (description of what to write). "
        "Tone options: professional, friendly, formal, concise. "
        "OUTPUT: drafted email or list of drafts."
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if isinstance(input_str, str) else input_str
        except Exception:
            return "ERROR: Input must be valid JSON."

        action = data.get("action", "compose")
        drafts = _load_drafts()

        if action == "compose":
            to      = data.get("to", "")
            subject = data.get("subject", "")
            tone    = data.get("tone", "professional")
            body    = data.get("body", "")

            # If no raw body, build a structured draft from body_prompt
            if not body:
                prompt = data.get("body_prompt", "General message")
                tone_guide = {
                    "professional": "Use clear, professional business language.",
                    "friendly":     "Use warm, conversational language.",
                    "formal":       "Use very formal and polished language.",
                    "concise":      "Keep it brief and to the point.",
                }.get(tone, "Use clear, professional language.")
                body = (
                    f"[DRAFT — {tone.upper()} TONE]\n\n"
                    f"To: {to or '[recipient]'}\n"
                    f"Subject: {subject or '[subject]'}\n\n"
                    f"Dear [Name],\n\n"
                    f"[This is a draft based on: {prompt}]\n"
                    f"[{tone_guide}]\n\n"
                    f"[Your main message here — describe: {prompt}]\n\n"
                    f"Best regards,\n[Your Name]"
                )

            draft = {
                "id": f"draft_{int(time.time())}",
                "to": to,
                "subject": subject,
                "body": body,
                "tone": tone,
                "created_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            drafts.append(draft)
            _save_drafts(drafts)

            return (
                f"✉️ EMAIL DRAFT SAVED (ID: {draft['id']})\n"
                f"{'─'*50}\n"
                f"To:      {to or '[recipient]'}\n"
                f"Subject: {subject or '[subject]'}\n"
                f"Tone:    {tone}\n"
                f"{'─'*50}\n"
                f"{body}"
            )

        elif action == "list_drafts":
            if not drafts:
                return "No drafts saved."
            lines = ["📬 SAVED EMAIL DRAFTS\n"]
            for d in drafts:
                lines.append(f"[{d['id']}] To: {d.get('to','?')} | Subject: {d.get('subject','?')} | {d.get('created_at','')}")
            return "\n".join(lines)

        elif action == "get_draft":
            did = data.get("id","")
            for d in drafts:
                if d.get("id") == did:
                    return (
                        f"✉️ DRAFT: {did}\n{'─'*50}\n"
                        f"To: {d.get('to','')}\nSubject: {d.get('subject','')}\n"
                        f"{'─'*50}\n{d.get('body','')}"
                    )
            return f"ERROR: Draft not found: {did}"

        elif action == "delete_draft":
            did = data.get("id","")
            before = len(drafts)
            drafts = [d for d in drafts if d.get("id") != did]
            _save_drafts(drafts)
            return f"🗑️ Deleted draft: {did}" if len(drafts) < before else f"ERROR: Draft not found: {did}"

        else:
            return f"ERROR: Unknown action '{action}'. Use: compose, list_drafts, get_draft, delete_draft"
