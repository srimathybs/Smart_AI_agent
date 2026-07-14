"""
workflow.py — Smart Agent v2 (Enhanced)
Improvements:
  1. Real structured tool-calling via langchain_ollama .bind_tools() + ToolNode
  2. Unified streaming path with tool awareness (astream_events)
  3. Multi-tool-call per turn (all tool calls executed, no early break)
  4. Better task classification: keyword pre-filter before LLM fallback
  5. Persistent conversation threads via thread_id session management
  6. New tools: CalendarTool, EmailDraftTool, RAGTool
  7. RAG for large documents (auto-indexes files >3000 chars, then retrieves)
"""
from __future__ import annotations
import re, json, asyncio, hashlib
from typing import AsyncGenerator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import StructuredTool

# ── Tool imports ─────────────────────────────────────────────────────────────
from tools.search_tool   import WebSearchTool, URLScraperTool
from tools.code_tool     import CodeExecutorTool
from tools.file_tool     import FileReadTool, FileWriteTool
from tools.sql_tool      import SQLQueryTool
from tools.math_tool     import MathTool
from tools.chart_tool    import ChartTool
from tools.calendar_tool import CalendarTool
from tools.email_tool    import EmailDraftTool
from tools.rag_tool      import RAGTool
from memory.memory_manager import save_to_memory, recall_from_memory

# ── Model registry ────────────────────────────────────────────────────────────
DEFAULT_MODEL = "tinyllama"
MODEL_INFO = {
    "tinyllama": {"label": "TinyLlama 1.1B",   "speed": "Fastest",  "size": "637 MB",  "pull": "ollama pull tinyllama",  "tools": False},
    "phi3":      {"label": "Phi-3 Mini 3.8B",   "speed": "Fast",     "size": "2.2 GB",  "pull": "ollama pull phi3",       "tools": True},
    "mistral":   {"label": "Mistral 7B",         "speed": "Balanced", "size": "4.1 GB",  "pull": "ollama pull mistral",    "tools": True},
    "llama3.2":  {"label": "Llama 3.2 3B",       "speed": "Moderate", "size": "2.0 GB",  "pull": "ollama pull llama3.2",   "tools": True},
    "codellama": {"label": "CodeLlama 7B",        "speed": "Moderate", "size": "3.8 GB",  "pull": "ollama pull codellama",  "tools": False},
    "llava":     {"label": "LLaVA 7B (vision)",   "speed": "Moderate", "size": "4.5 GB",  "pull": "ollama pull llava",      "tools": False},
    "qwen2.5":   {"label": "Qwen 2.5 7B",         "speed": "Fast",     "size": "4.7 GB",  "pull": "ollama pull qwen2.5",    "tools": True},
    "llama3.1":  {"label": "Llama 3.1 8B",        "speed": "Balanced", "size": "4.9 GB",  "pull": "ollama pull llama3.1",   "tools": True},
}

LANG_NAMES = {
    "en": "English", "ta": "Tamil",  "hi": "Hindi",  "te": "Telugu",
    "kn": "Kannada", "ml": "Malayalam", "fr": "French", "es": "Spanish",
    "de": "German",  "ja": "Japanese",
}

# ── Conversation thread store (in-memory; persists within process lifetime) ──
_THREAD_HISTORY: dict[str, list] = {}   # thread_id → list of LangChain messages
RAG_INDEX_THRESHOLD = 3000              # chars; index docs larger than this


# ─────────────────────────────────────────────────────────────────────────────
# 1. LLM factory
# ─────────────────────────────────────────────────────────────────────────────
def get_llm(model: str = DEFAULT_MODEL, temperature: float = 0.1) -> ChatOllama:
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url="http://localhost:11434",
        num_predict=2048,
        num_ctx=4096,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tool registry — wrap each tool as a LangChain @tool for bind_tools()
# ─────────────────────────────────────────────────────────────────────────────
_TOOL_INSTANCES = {
    "web_search":     WebSearchTool(),
    "scrape_url":     URLScraperTool(),
    "execute_python": CodeExecutorTool(),
    "read_file":      FileReadTool(),
    "write_file":     FileWriteTool(),
    "query_database": SQLQueryTool(),
    "solve_math":     MathTool(),
    "create_chart":   ChartTool(),
    "calendar_tool":  CalendarTool(),
    "email_draft":    EmailDraftTool(),
    "rag_search":     RAGTool(),
}

def _make_lc_tool(tool_obj):
    """Wrap a legacy _run(input) tool as a LangChain StructuredTool.

    Using StructuredTool.from_function instead of the @tool decorator
    avoids version-specific signature issues with passing name/description
    as kwargs (some langchain-core versions reject `description=` on the
    decorator and require it to come from a docstring instead).
    """
    name = tool_obj.name
    desc = tool_obj.description

    def _wrapped(input: str) -> str:        # noqa: A002
        return str(tool_obj._run(input))

    return StructuredTool.from_function(
        func=_wrapped,
        name=name,
        description=desc,
    )

_LC_TOOLS = {k: _make_lc_tool(v) for k, v in _TOOL_INSTANCES.items()}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Task classification (keyword pre-filter → LLM fallback)
# ─────────────────────────────────────────────────────────────────────────────
_KEYWORD_MAP = {
    "research":  ["search for", "look up", "find news", "latest", "what is happening", "current events",
                  "scrape", "browse", "web search", "google", "find information about"],
    "coding":    ["write code", "python script", "write a function", "debug", "implement",
                  "programme", "algorithm", "class ", "def ", "import ", "fastapi", "flask"],
    "analysis":  ["sql", "query", "database", "dataframe", "pandas", "csv data", "bar chart",
                  "pie chart", "statistics", "correlation", "aggregate", "group by"],
    "math":      ["solve ", "calculate ", "integral of", "derivative", "differentiate",
                  "integrate", "equation", "factor", "simplify", "matrix"],
    "document":  ["uploaded file", "this document", "the pdf", "summarize the file",
                  "analyse the doc", "read the file", "from the file"],
    "calendar":  ["schedule", "remind me", "add event", "calendar", "appointment",
                  "meeting at", "set reminder", "what's on my calendar"],
    "email":     ["write an email", "draft email", "compose email", "email to", "email draft"],
}

VALID_TYPES = {"research", "coding", "analysis", "math", "document", "general", "calendar", "email"}


def classify_task(task: str, model: str = DEFAULT_MODEL) -> str:
    task_lower = task.lower()

    # Fast keyword pre-filter (free, no LLM call)
    scores: dict[str, int] = {}
    for task_type, keywords in _KEYWORD_MAP.items():
        hit = sum(1 for kw in keywords if kw in task_lower)
        if hit:
            scores[task_type] = hit
    if scores:
        best = max(scores, key=lambda k: scores[k])
        print(f"[ROUTER] {best.upper()} (keyword, score={scores[best]}) | model:{model}")
        return best

    # LLM fallback with confidence guard
    llm = get_llm(model, 0)
    prompt = (
        "Reply ONE word only — the most fitting category.\n"
        "research=web search | coding=write/run code | analysis=data/SQL/charts | "
        "math=equations/calculations | document=analyse uploaded file | "
        "calendar=events/reminders | email=compose email | general=knowledge/explanation\n"
        f"Task: {task[:300]}\nWord:"
    )
    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        raw  = resp.content.strip().lower()
        t    = re.sub(r"[^a-z]", "", raw.split()[0]) if raw.split() else "general"
        if t not in VALID_TYPES:
            t = "general"
    except Exception:
        t = "general"

    print(f"[ROUTER] {t.upper()} (LLM fallback) | model:{model}")
    return t


# ─────────────────────────────────────────────────────────────────────────────
# 4. Tool sets per agent type
# ─────────────────────────────────────────────────────────────────────────────
TOOLS_MAP: dict[str, list[str]] = {
    "research":  ["web_search", "scrape_url", "rag_search"],
    "coding":    ["execute_python", "read_file", "write_file"],
    "analysis":  ["query_database", "execute_python", "create_chart", "solve_math"],
    "math":      ["solve_math", "execute_python"],
    "document":  ["rag_search"],
    "general":   ["web_search", "scrape_url"],
    "calendar":  ["calendar_tool"],
    "email":     ["email_draft"],
}

SYSTEM_PROMPTS = {
    "research": (
        "You are a Senior Research Analyst with access to web search tools.\n"
        "Search with multiple queries. Scrape URLs for detail.\n"
        "Provide DETAILED, COMPREHENSIVE answers: findings, statistics, sources.\n"
        "Write minimum 500 words for complex topics. Use headings and bullet points."
    ),
    "coding": (
        "You are a Senior Python Developer.\n"
        "Write complete, production-quality code with full comments.\n"
        "ALWAYS execute your code to verify it works. Fix and retry if needed.\n"
        "Provide: what it does, how each part works, actual output, edge cases."
    ),
    "analysis": (
        "You are a Senior Data Analyst.\n"
        "Query the database using SQL. Use Python for calculations. Generate charts for visual data.\n"
        "Provide: key metrics, trends, statistical insights, business recommendations.\n"
        "You MAY call multiple tools in a single reply to complete the analysis efficiently."
    ),
    "math": (
        "You are a Mathematics Expert.\n"
        "Use the math solver for ALL calculations — never do mental arithmetic.\n"
        "Show step-by-step working. Explain the math concepts involved."
    ),
    "document": (
        "You are an Expert Document Analyst.\n"
        "Use rag_search to retrieve relevant passages from the indexed document.\n"
        "Answer completely with direct quotes from retrieved passages.\n"
        "Do NOT say you cannot access the file — retrieve chunks and answer."
    ),
    "general": (
        "You are a highly knowledgeable AI Expert.\n"
        "Provide COMPREHENSIVE, DETAILED accurate answers.\n"
        "Search the web for current information. Scrape URLs for full page content.\n"
        "Structure answers: direct answer, detailed explanation, examples, real-world context.\n"
        "NEVER give short one-paragraph answers to complex questions."
    ),
    "calendar": (
        "You are a Calendar & Scheduling Assistant.\n"
        "Use the calendar_tool to add events, set reminders, and list upcoming items.\n"
        "Always confirm what was scheduled or remind the user of what's coming up."
    ),
    "email": (
        "You are a Professional Email Drafter.\n"
        "Use the email_draft tool to compose, save, and retrieve email drafts.\n"
        "Ask for tone preference if not specified (professional/friendly/formal/concise).\n"
        "Present the full draft clearly and offer to refine it."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 5. RAG auto-indexing for large document contexts
# ─────────────────────────────────────────────────────────────────────────────
def _maybe_index_document(document_context: str, doc_id: str) -> str:
    """
    If document is large, index it with RAG and return a short notice.
    Otherwise return the full content for direct injection.
    """
    if not document_context or len(document_context) < RAG_INDEX_THRESHOLD:
        return document_context   # small doc — inject directly as before

    rag = RAGTool()
    result = rag._run(json.dumps({
        "action":   "index",
        "doc_id":   doc_id,
        "content":  document_context,
        "filename": doc_id,
    }))
    print(f"[RAG] {result}")
    return f"[LARGE DOCUMENT INDEXED as '{doc_id}' — use rag_search to retrieve relevant passages]"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Core agent loop — structured tool-calling + multi-tool per turn
# ─────────────────────────────────────────────────────────────────────────────
def _supports_native_tools(model: str) -> bool:
    return MODEL_INFO.get(model, {}).get("tools", False)


def _run_tool_calls(tool_calls: list, tool_name_map: dict) -> list[ToolMessage]:
    """Execute ALL tool calls from a single AI reply (multi-tool per turn)."""
    results = []
    for tc in tool_calls:
        name  = tc.get("name", "")
        args  = tc.get("args", {})
        tc_id = tc.get("id", f"tc_{name}")
        tool_fn = tool_name_map.get(name)
        print(f"[TOOL] {name} <- {str(args)[:80]}")
        if tool_fn is None:
            content = f"ERROR: tool '{name}' not found."
        else:
            try:
                # LangChain tools accept either a single string or keyword args
                input_val = args.get("input", args) if isinstance(args, dict) else str(args)
                if isinstance(input_val, dict):
                    input_val = json.dumps(input_val)
                content = str(tool_fn.invoke(input_val))[:3000]
            except Exception as exc:
                content = f"Tool error: {exc}"
        results.append(ToolMessage(content=content, tool_call_id=tc_id))
    return results


def run_agent_with_tools(
    task: str,
    task_type: str,
    model: str,
    document_context: str = "",
    memory_context: str = "",
    language: str = "en",
    thread_id: str = "",
) -> str:
    """
    Agent loop supporting:
    - Native bind_tools() for capable models
    - Regex fallback for smaller models
    - Multi-tool execution per turn
    - Persistent conversation threads
    """
    llm       = get_llm(model, 0.2)
    sysp      = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["general"])
    tool_keys = TOOLS_MAP.get(task_type, [])

    if language != "en":
        sysp += f"\n\nIMPORTANT: Respond entirely in {LANG_NAMES.get(language, language)}."

    # Build tool name→lc_tool map for this agent type
    active_lc_tools = {k: _LC_TOOLS[k] for k in tool_keys if k in _LC_TOOLS}
    active_raw_tools = {k: _TOOL_INSTANCES[k] for k in tool_keys if k in _TOOL_INSTANCES}

    # Choose: native tool-calling or regex-based
    use_native = _supports_native_tools(model) and bool(active_lc_tools)
    if use_native:
        bound_llm = llm.bind_tools(list(active_lc_tools.values()))
    else:
        # Build text descriptions for regex-mode prompt
        tool_desc = "\n".join(
            f"  TOOL_CALL: {k} | <input>  # {v.description[:100]}"
            for k, v in active_raw_tools.items()
        )
        sysp_with_tools = sysp + (f"\n\nAVAILABLE TOOLS:\n{tool_desc}" if tool_desc else "")

    # Persistent conversation thread
    if thread_id and thread_id in _THREAD_HISTORY:
        messages = list(_THREAD_HISTORY[thread_id])
    else:
        messages = [SystemMessage(content=sysp if use_native else sysp_with_tools)]

    # Build user message
    parts = []
    if memory_context:
        parts.append(memory_context)
    if document_context:
        parts.append(f"DOCUMENT CONTEXT:\n{'='*40}\n{document_context}\n{'='*40}\n")
    parts.append(f"USER TASK: {task}\n\nProvide a COMPLETE, DETAILED answer.")
    messages.append(HumanMessage(content="\n".join(parts)))

    chart_paths: list[str] = []
    final_reply = ""

    for iteration in range(8):
        print(f"[AGENT] Iter {iteration + 1}/8 | native_tools={use_native}")

        if use_native:
            resp   = bound_llm.invoke(messages)
            reply  = resp.content.strip() if resp.content else ""
            tc_list = getattr(resp, "tool_calls", []) or []

            messages.append(resp)   # append AIMessage with tool_calls metadata

            if not tc_list:
                final_reply = reply
                break

            # ── Multi-tool execution ──────────────────────────────────────
            tool_messages = _run_tool_calls(tc_list, active_lc_tools)
            for tm in tool_messages:
                if "CHART_SAVED:" in tm.content:
                    chart_paths.append(tm.content.replace("CHART_SAVED:", "").strip())
                messages.append(tm)

        else:
            # Regex-based fallback path
            resp  = llm.invoke(messages)
            reply = resp.content.strip()

            # Find ALL tool calls in this reply (multi-tool per turn)
            called = False
            for tool_name, tool_obj in active_raw_tools.items():
                pattern = rf"TOOL_CALL:\s*{re.escape(tool_name)}\s*\|\s*(.+?)(?=TOOL_CALL:|$)"
                for m in re.finditer(pattern, reply, re.IGNORECASE | re.DOTALL):
                    tool_input = m.group(1).strip()
                    print(f"[TOOL/regex] {tool_name} <- {tool_input[:80]}")
                    try:
                        tr = str(tool_obj._run(tool_input))[:2500]
                        if "CHART_SAVED:" in tr:
                            chart_paths.append(tr.replace("CHART_SAVED:", "").strip())
                            tr = f"Chart created: {chart_paths[-1]}"
                    except Exception as exc:
                        tr = f"Tool error: {exc}"
                    messages.append(AIMessage(content=reply))
                    messages.append(HumanMessage(
                        content=f"TOOL RESULT ({tool_name}):\n{tr}\n\nContinue with COMPLETE final answer."
                    ))
                    called = True

            if not called:
                final_reply = reply
                break

    # Append chart references
    if chart_paths:
        final_reply += "\n\n📊 Charts: " + ", ".join(chart_paths)

    # Save thread
    if thread_id:
        _THREAD_HISTORY[thread_id] = messages

    return final_reply


# ─────────────────────────────────────────────────────────────────────────────
# 7. Unified streaming — tool-aware via synchronous polling
# ─────────────────────────────────────────────────────────────────────────────
def stream_agent(
    task: str,
    model: str = DEFAULT_MODEL,
    document_context: str = "",
    memory_context: str = "",
    language: str = "en",
    thread_id: str = "",
):
    """
    Yields text chunks. For models with native tools, runs the full agentic
    loop first, then streams the final answer token-by-token.
    For models without native tools, streams directly (faster, no tool use).
    """
    task_type = classify_task(task, model)
    yield (
        f"**Agent:** {task_type.capitalize()} | "
        f"**Model:** {MODEL_INFO.get(model, {}).get('label', model)}\n\n---\n\n"
    )

    if _supports_native_tools(model):
        # Run full tool loop, then stream the result character-by-character
        # (real token streaming with tools requires async; this is the sync-safe version)
        result = run_agent_with_tools(
            task, task_type, model, document_context, memory_context, language, thread_id
        )
        # Emit in small chunks to simulate streaming
        chunk_size = 8
        for i in range(0, len(result), chunk_size):
            yield result[i:i + chunk_size]
    else:
        # Direct LLM streaming (no tools, but truly progressive)
        llm  = get_llm(model, 0.2)
        sysp = SYSTEM_PROMPTS.get(task_type, SYSTEM_PROMPTS["general"])
        if language != "en":
            sysp += f"\n\nRespond in {LANG_NAMES.get(language, language)}."
        parts = []
        if memory_context:
            parts.append(memory_context)
        if document_context:
            parts.append(f"DOCUMENT:\n{document_context}\n")
        parts.append(f"Task: {task}\n\nProvide a COMPLETE, DETAILED answer.")
        messages = [SystemMessage(content=sysp), HumanMessage(content="\n".join(parts))]
        for chunk in llm.stream(messages):
            if hasattr(chunk, "content") and chunk.content:
                yield chunk.content


# ─────────────────────────────────────────────────────────────────────────────
# 8. Public entry point
# ─────────────────────────────────────────────────────────────────────────────
def run_agent(
    task: str,
    model: str = DEFAULT_MODEL,
    document_context: str = "",
    user_id: str = "default",
    language: str = "en",
    use_memory: bool = True,
    thread_id: str = "",
) -> dict:
    print(f"[START] task={task[:60]!r} | model={model} | thread={thread_id!r}")

    memory_context = recall_from_memory(task, user_id) if use_memory else ""
    task_type      = classify_task(task, model)
    if document_context and task_type == "general":
        task_type = "document"

    # Auto-index large documents
    doc_id = hashlib.md5(document_context[:200].encode()).hexdigest()[:12] if document_context else ""
    if document_context:
        document_context = _maybe_index_document(document_context, doc_id)

    result = run_agent_with_tools(
        task, task_type, model, document_context, memory_context, language, thread_id
    )

    if use_memory:
        save_to_memory(task, result, task_type, model, user_id)

    print(f"[DONE] {len(result)} chars")
    return {"task": task, "type": task_type, "result": result, "thread_id": thread_id}
