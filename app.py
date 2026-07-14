"""
app.py — Smart AI Agent v2 (Enhanced)
Improvements added:
  - Persistent conversation threads (thread_id per session)
  - Multi-user support (login screen with isolated memory)
  - New tools shown: Calendar, Email, RAG
  - Streaming is now tool-aware (uses unified stream_agent)
  - Updated examples covering calendar, email, multi-tool tasks
"""
import streamlit as st
import time, os, tempfile, json, re, uuid, hashlib

from graph.workflow import (
    run_agent, stream_agent, DEFAULT_MODEL, MODEL_INFO, classify_task,
    _THREAD_HISTORY,
)
from tools.document_tool import process_uploaded_file, FILE_ICONS
from tools.voice_tool    import TextToSpeechTool, LANGUAGES
from tools.export_tool   import export_to_pdf, export_to_docx
from memory.memory_manager import (
    get_memory_stats, clear_memory, get_all_memories, save_to_memory,
)

st.set_page_config(
    page_title="Smart AI Agent", page_icon="🤖",
    layout="wide", initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.main-title{font-size:1.9rem;font-weight:700;color:#1a1a2e;margin-bottom:0}
.subtitle{font-size:.9rem;color:#666;margin-bottom:12px}
.fbadge{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500;display:inline-block;margin:2px}
.login-box{max-width:400px;margin:80px auto;padding:32px;border-radius:16px;
           background:#f8f9ff;border:1px solid #e0e4ff;box-shadow:0 4px 24px #0001}
</style>
""", unsafe_allow_html=True)

MODEL_COLORS = {
    "tinyllama":("#E1F5EE","#085041"),"phi3":("#E6F1FB","#0C447C"),
    "mistral":("#EEEDFE","#3C3489"),"llama3.2":("#FAEEDA","#633806"),
    "codellama":("#EAF3DE","#27500A"),"llava":("#FAECE7","#712B13"),
    "qwen2.5":("#E6F1FB","#0C447C"),"llama3.1":("#EEEDFE","#3C3489"),
}
AGENT_COLORS = {
    "research":("#E6F1FB","#0C447C","Researcher"),
    "coding":("#E1F5EE","#085041","Coder"),
    "analysis":("#FAEEDA","#633806","Analyst"),
    "math":("#EAF3DE","#27500A","Mathematician"),
    "document":("#EEEDFE","#3C3489","Document Analyst"),
    "general":("#FAECE7","#712B13","General"),
    "calendar":("#E1F5EE","#085041","Calendar"),
    "email":("#E6F1FB","#0C447C","Email"),
    "streamed":("#F1EFE8","#444441","Streamed"),
}

# ── Session defaults ──────────────────────────────────────────────────────────
DEFAULTS = {
    "history":         [],
    "uploaded_context":"",
    "uploaded_info":   None,
    "user_id":         "",
    "logged_in":       False,
    "thread_id":       str(uuid.uuid4()),   # unique conversation thread
    "threads":         {},                   # thread_id → label
    "monitoring":      [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# MULTI-USER LOGIN  (simple local password; swap with OAuth for production)
# ─────────────────────────────────────────────────────────────────────────────
USERS = {
    # user_id : display_name  (no passwords for local/offline use)
    # Add real passwords via st.secrets["users"] in production.
    "alice":  "Alice",
    "bob":    "Bob",
    "admin":  "Admin",
    "default":"Guest",
}

def login_screen():
    st.markdown("""
    <div class="login-box">
        <h2 style="text-align:center;margin-bottom:8px">🤖 Smart AI Agent</h2>
        <p style="text-align:center;color:#666;margin-bottom:24px">Sign in to continue</p>
    </div>""", unsafe_allow_html=True)

    cols = st.columns([1,2,1])
    with cols[1]:
        st.markdown("### Sign In")
        uid = st.selectbox(
            "Select user",
            list(USERS.keys()),
            format_func=lambda u: f"{USERS[u]} ({u})",
        )
        custom = st.text_input("Or enter a new username (creates isolated memory)", placeholder="e.g. priya")
        if st.button("Sign In", type="primary", use_container_width=True):
            chosen = custom.strip().lower().replace(" ","_") or uid
            st.session_state.user_id    = chosen
            st.session_state.logged_in  = True
            st.session_state.thread_id  = str(uuid.uuid4())
            st.rerun()

if not st.session_state.logged_in:
    login_screen()
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    # User badge
    uid_display = USERS.get(st.session_state.user_id, st.session_state.user_id.capitalize())
    st.markdown(
        f'<div style="background:#E6F1FB;border-radius:8px;padding:8px 12px;margin-bottom:8px">'
        f'👤 <b>{uid_display}</b> <span style="font-size:11px;color:#666">({st.session_state.user_id})</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("Sign out", use_container_width=True):
        for k in ["logged_in","user_id","history","uploaded_context","uploaded_info","thread_id","threads"]:
            st.session_state[k] = DEFAULTS.get(k, "")
        st.rerun()

    st.markdown("## Smart AI Agent v2")
    st.caption("Free · Local · No API key · Ollama")
    tab_main, tab_thread, tab_mem, tab_mon = st.tabs(["Settings","Threads","Memory","Monitor"])

    with tab_main:
        st.markdown("#### AI Model")
        selected_model = st.selectbox(
            "model", list(MODEL_INFO.keys()), index=0,
            format_func=lambda m: f"{MODEL_INFO[m]['label']} ({MODEL_INFO[m]['speed']})"
                                  + (" 🔧" if MODEL_INFO[m].get("tools") else ""),
            label_visibility="collapsed",
        )
        info = MODEL_INFO[selected_model]
        bg,fg = MODEL_COLORS.get(selected_model,("#f0f0f0","#333"))
        native_badge = ' <span style="background:#d4edda;color:#155724;border-radius:4px;padding:1px 6px;font-size:10px">native tools</span>' if info.get("tools") else ""
        st.markdown(
            f'<div style="background:{bg};border-radius:8px;padding:8px 12px;margin-bottom:10px">'
            f'<b style="color:{fg}">{info["label"]}</b>{native_badge}<br>'
            f'<span style="font-size:11px;color:{fg}">Speed: {info["speed"]} | Size: {info["size"]}<br>'
            f'<code>{info["pull"]}</code></span></div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### Response")
        stream_mode  = st.toggle("Streaming (word by word)", value=True)
        detail_level = st.selectbox("Detail level", ["Standard","Detailed","Very detailed (long)"], index=1)
        use_memory   = st.toggle("Use memory", value=True)
        st.markdown("#### Language")
        lang_name = st.selectbox("Output language", list(LANGUAGES.keys()), index=0)
        language  = LANGUAGES[lang_name]
        st.markdown("#### Voice output")
        speak_result = st.toggle("Speak result aloud", value=False)
        st.divider()
        if st.button("Clear history", use_container_width=True):
            st.session_state.history = []
            st.session_state.uploaded_context = ""
            st.session_state.uploaded_info = None
            st.rerun()

    # ── Conversation thread manager ───────────────────────────────────────────
    with tab_thread:
        st.markdown("**Active thread:**")
        tid = st.session_state.thread_id
        label = st.session_state.threads.get(tid, f"Thread {tid[:8]}")
        st.code(label, language=None)

        new_label = st.text_input("Rename thread", value=label, key="rename_thread")
        if st.button("Save name"):
            st.session_state.threads[tid] = new_label
            st.success("Renamed!")

        if st.button("➕ New conversation thread", use_container_width=True):
            new_tid = str(uuid.uuid4())
            st.session_state.thread_id = new_tid
            st.session_state.threads[new_tid] = f"Thread {new_tid[:8]}"
            st.session_state.history = []
            st.rerun()

        if len(st.session_state.threads) > 1:
            st.markdown("**Switch thread:**")
            other = {k: v for k, v in st.session_state.threads.items() if k != tid}
            choice = st.selectbox("Thread", list(other.keys()), format_func=lambda k: other[k])
            if st.button("Switch"):
                st.session_state.thread_id = choice
                st.session_state.history = []
                st.rerun()

        if st.button("🗑️ Delete current thread", use_container_width=True):
            if tid in _THREAD_HISTORY:
                del _THREAD_HISTORY[tid]
            st.session_state.threads.pop(tid, None)
            new_tid = str(uuid.uuid4())
            st.session_state.thread_id = new_tid
            st.session_state.history = []
            st.rerun()

    with tab_mem:
        stats = get_memory_stats(st.session_state.user_id)
        if stats["available"]:
            st.metric("Saved memories", stats["total"])
            mems = get_all_memories(st.session_state.user_id)
            for m in mems[-5:]:
                with st.expander(f"{m.get('timestamp','?')} — {m.get('task','?')[:40]}..."):
                    st.caption(f"Agent: {m.get('agent_type','?')} | Model: {m.get('model','?')}")
                    st.write(m.get("result_preview",""))
            if st.button("Clear all memory", use_container_width=True):
                clear_memory(st.session_state.user_id)
                st.success("Cleared!")
                st.rerun()
        else:
            st.info("Install for memory:\n```\npip install chromadb\n```")

    with tab_mon:
        st.markdown("**Session stats**")
        total = len(st.session_state.history)
        avg_t = round(sum(h.get("time",0) for h in st.session_state.history)/max(total,1), 1)
        c1,c2 = st.columns(2)
        c1.metric("Total tasks", total)
        c2.metric("Avg time", f"{avg_t}s")
        types = {}
        for h in st.session_state.history:
            types[h.get("type","?")] = types.get(h.get("type","?"),0) + 1
        if types:
            st.markdown("**Agent usage:**")
            for t, cnt in sorted(types.items(), key=lambda x: -x[1]):
                bg2,fg2,lbl = AGENT_COLORS.get(t,("#f0f0f0","#444",t))
                pct = round(cnt/total*100)
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0">'
                    f'<span style="background:{bg2};color:{fg2};padding:2px 8px;border-radius:20px;font-size:11px;min-width:90px">{lbl}</span>'
                    f'<div style="flex:1;height:6px;background:#eee;border-radius:3px;overflow:hidden">'
                    f'<div style="width:{pct}%;height:100%;background:{fg2};border-radius:3px"></div></div>'
                    f'<span style="font-size:12px;color:#666">{cnt}</span></div>',
                    unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">Smart AI Agent v2</p>', unsafe_allow_html=True)
features = [
    "No API key","Free forever","Local AI","Memory","Voice","Charts","Math",
    "Multi-language","PDF/DOCX","Code runner","URL scraper","Export PDF/DOCX",
    "Calendar","Email drafts","RAG","Multi-user","Threads","Native tools",
]
badge_bg = ["#E1F5EE","#E6F1FB","#EEEDFE","#FAEEDA","#EAF3DE","#FAECE7"] * 4
st.markdown(
    '<div>' +
    "".join(
        f'<span class="fbadge" style="background:{badge_bg[i%len(badge_bg)]};color:#333">{f}</span>'
        for i,f in enumerate(features)
    ) +
    '</div>',
    unsafe_allow_html=True,
)

# ── FILE UPLOAD ───────────────────────────────────────────────────────────────
with st.expander("Upload a file (PDF, DOCX, image, code, CSV, Excel, text...)", expanded=False):
    uf = st.file_uploader(
        "Drop file here",
        type=[
            "pdf","docx","doc","csv","xlsx","xls","jpg","jpeg","png","gif","bmp","webp",
            "py","js","ts","java","cpp","c","cs","html","css","sql","r","go","rs",
            "php","rb","kt","swift","sh","json","yaml","yml","xml","md","txt",
        ],
        label_visibility="collapsed",
    )
    if uf:
        suffix = os.path.splitext(uf.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uf.read()); tmp_path = tmp.name
        with st.spinner(f"Reading {uf.name}..."):
            di = process_uploaded_file(tmp_path)
        os.unlink(tmp_path)
        st.session_state.uploaded_context = di["content"]
        st.session_state.uploaded_info    = di
        icon = FILE_ICONS.get(di["type"],"📁")
        size_label = f"{di['size_kb']} KB"
        rag_note = " · Auto-indexed for RAG" if len(di["content"]) > 3000 else ""
        st.success(f"{icon} **{di['filename']}** loaded ({size_label} · {di['type'].upper()}{rag_note})")
        st.caption(f"Preview: {di['content'][:200].replace(chr(10),' ')}...")
    elif st.session_state.uploaded_info:
        d = st.session_state.uploaded_info
        st.info(f"Using: **{d['filename']}** ({d['size_kb']} KB)")
        if st.button("Remove file"):
            st.session_state.uploaded_context = ""
            st.session_state.uploaded_info    = None
            st.rerun()

# ── EXAMPLES ──────────────────────────────────────────────────────────────────
with st.expander("Quick examples — click to try", expanded=True):
    examples = [
        ("Coding",    "Write a complete Python class for a student management system with add, remove, search and grade methods"),
        ("Math",      "Solve x**2 - 5x + 6 = 0 and find the derivative of x**3 + 2x**2 - 5x + 1"),
        ("Analysis",  "Query the database and show total revenue by region AND create a bar chart with the results"),
        ("Research",  "Search for the latest developments in AI agents and large language models in 2025"),
        ("General",   "Explain machine learning, deep learning, and neural networks in complete detail with real world examples"),
        ("Calendar",  'Add a team standup event: {"action":"add_event","title":"Team Standup","date":"2025-09-01","time":"09:00","notes":"Daily sync"}'),
        ("Email",     'Draft a professional email to my manager asking for a day off next Friday'),
        ("Analysis",  "Query customers table for total spend by segment AND create a pie chart of the results"),
        ("Coding",    "Write a complete FastAPI app with GET and POST endpoints and Pydantic models"),
        ("Calendar",  '{"action":"list_events"} — show my upcoming events'),
        ("Email",     "Write a friendly follow-up email to a client who hasn't responded in a week"),
        ("Research",  "Scrape and summarise: https://en.wikipedia.org/wiki/Machine_learning"),
    ]
    cmap = {
        "Coding":("#E1F5EE","#085041"),"Math":("#EAF3DE","#27500A"),
        "Analysis":("#FAEEDA","#633806"),"Research":("#E6F1FB","#0C447C"),
        "General":("#EEEDFE","#3C3489"),"Calendar":("#E1F5EE","#085041"),
        "Email":("#E6F1FB","#0C447C"),
    }
    cols = st.columns(4)
    for i,(tag,ex) in enumerate(examples):
        with cols[i % 4]:
            if st.button(f"[{tag}] {ex[:28]}...", key=f"ex_{i}", use_container_width=True):
                st.session_state.pending = ex

# ── TASK INPUT ────────────────────────────────────────────────────────────────
st.divider()
default_task = st.session_state.pop("pending","")
detail_suffix = {
    "Standard": "",
    "Detailed": "\n\nPlease provide a detailed, comprehensive answer with examples.",
    "Very detailed (long)": (
        "\n\nPlease provide an extremely detailed, thorough explanation covering all aspects. "
        "Include examples, comparisons, step-by-step breakdown. Write as much as needed."
    ),
}
placeholder = (
    f"Ask about '{st.session_state.uploaded_info['filename']}'"
    if st.session_state.uploaded_info
    else "Type any task: code, math, research, data analysis, calendar, email, document questions..."
)
task = st.text_area("Your task", value=default_task, height=120, placeholder=placeholder)
task_with_detail = task + detail_suffix.get(detail_level,"")

# Thread info strip
tid = st.session_state.thread_id
thread_label = st.session_state.threads.get(tid, f"Thread {tid[:8]}")
turns_in_thread = len([h for h in st.session_state.history])
st.caption(
    f"🧵 **{thread_label}** · {turns_in_thread} turn(s) · "
    f"user: **{st.session_state.user_id}** · "
    f"{'🔧 native tools' if MODEL_INFO.get(selected_model,{}).get('tools') else '📝 regex tools'}"
)

col_run, col_epdf, col_edocx = st.columns([4,1,1])
with col_run:
    run_btn = st.button(f"Run Agent  ({info['speed']})", type="primary", use_container_width=True)
with col_epdf:
    pdf_btn = st.button("Export PDF", use_container_width=True)
with col_edocx:
    docx_btn = st.button("Export DOCX", use_container_width=True)

if st.session_state.history:
    last = st.session_state.history[-1]
    if pdf_btn:
        path = export_to_pdf(last["task"],last["result"],last.get("type","?"),last.get("model","?"))
        if path and os.path.exists(path):
            with open(path,"rb") as f:
                st.download_button("Download PDF",f.read(),file_name=os.path.basename(path),mime="application/pdf",key="dl_pdf_main")
        else:
            st.error("PDF export failed. Run: pip install fpdf2")
    if docx_btn:
        path = export_to_docx(last["task"],last["result"],last.get("type","?"),last.get("model","?"))
        if path and os.path.exists(path):
            with open(path,"rb") as f:
                st.download_button("Download DOCX",f.read(),file_name=os.path.basename(path),mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",key="dl_docx_main")
        else:
            st.error("DOCX export failed. Run: pip install python-docx")

# ── RUN AGENT ─────────────────────────────────────────────────────────────────
if run_btn and task.strip():
    start       = time.time()
    doc_context = st.session_state.uploaded_context
    c1,c2,c3   = st.columns(3)
    c1.info("Agent running...")
    c2.markdown(
        f'<div style="background:{bg};border-radius:8px;padding:6px 12px;text-align:center;font-weight:600;color:{fg}">'
        f'{info["label"]}</div>',
        unsafe_allow_html=True,
    )
    c3.info("Streaming" if stream_mode else "Batch mode")

    if doc_context:
        st.info(f"📎 Analysing: **{st.session_state.uploaded_info['filename']}**")
    mem_stats = get_memory_stats(st.session_state.user_id)
    if mem_stats["total"] > 0 and use_memory:
        st.caption(f"🧠 Using {mem_stats['total']} memories for {st.session_state.user_id}")

    st.markdown("### Result")
    result_ph = st.empty()

    try:
        if stream_mode:
            full = ""
            for chunk in stream_agent(
                task_with_detail, selected_model, doc_context, "", language,
                thread_id=st.session_state.thread_id,
            ):
                full += chunk
                result_ph.markdown(full + "▌")
            result_ph.markdown(full)
            elapsed    = time.time() - start
            agent_type = "streamed"
            c1.success("Done!")
            if use_memory:
                save_to_memory(task.strip(), full, "streamed", selected_model, st.session_state.user_id)
        else:
            with st.spinner(f"Thinking with {info['label']}..."):
                output = run_agent(
                    task_with_detail, selected_model, doc_context,
                    st.session_state.user_id, language, use_memory,
                    thread_id=st.session_state.thread_id,
                )
            elapsed    = time.time() - start
            agent_type = output.get("type","general")
            full       = output["result"]
            result_ph.markdown(full)
            c1.success("Done!")
            bg2,fg2,lbl = AGENT_COLORS.get(agent_type,("#f0f0f0","#444",agent_type))
            c2.markdown(
                f'<div style="background:{bg2};border-radius:8px;padding:6px 12px;text-align:center;font-weight:600;color:{fg2}">'
                f'{lbl} Agent</div>',
                unsafe_allow_html=True,
            )

        ct,cl,cw = st.columns(3)
        ct.metric("Time",   f"{elapsed:.1f}s")
        cl.metric("Length", f"{len(full):,} chars")
        cw.metric("Words",  f"{len(full.split()):,}")
        st.download_button(
            "Download .txt", data=full,
            file_name=f"result_{int(time.time())}.txt", mime="text/plain",
        )

        if speak_result:
            tts   = TextToSpeechTool()
            apath = tts._run(full[:2000], language)
            if "AUDIO_SAVED:" in apath:
                ap = apath.replace("AUDIO_SAVED:","").strip()
                if os.path.exists(ap):
                    with open(ap,"rb") as f:
                        st.audio(f.read(), format="audio/mp3")

        if "outputs/chart_" in full:
            chart_paths = re.findall(r"outputs/chart_\S+\.html", full)
            for cp in chart_paths:
                if os.path.exists(cp):
                    with open(cp,"r") as cf:
                        st.components.v1.html(cf.read(), height=450)

        st.session_state.history.append({
            "task":  task.strip(),
            "type":  agent_type,
            "result":full,
            "model": selected_model,
            "time":  elapsed,
            "lang":  lang_name,
            "thread":thread_label,
        })

        with st.expander("Debug info"):
            st.json({
                "agent":    agent_type,
                "model":    selected_model,
                "time_sec": round(elapsed, 2),
                "chars":    len(full),
                "has_doc":  bool(doc_context),
                "memory":   use_memory,
                "lang":     lang_name,
                "thread_id":st.session_state.thread_id,
                "user_id":  st.session_state.user_id,
                "native_tools": MODEL_INFO.get(selected_model,{}).get("tools", False),
            })

    except Exception as e:
        c1.error("Failed")
        err = str(e)
        st.error(f"Error: {err}")
        if "11434" in err or "connection" in err.lower():
            st.warning("**Ollama not running.**\n\n```\nollama serve\n```")
        elif "not found" in err.lower():
            st.warning(f"**Model not downloaded.**\n\n```\n{info['pull']}\n```")

elif run_btn and not task.strip():
    st.warning("Please enter a task first.")

# ── HISTORY ───────────────────────────────────────────────────────────────────
if st.session_state.history:
    st.divider()
    st.markdown(f"### Session history ({len(st.session_state.history)} tasks)")
    for item in reversed(st.session_state.history):
        bg2,fg2,lbl = AGENT_COLORS.get(item.get("type","?"),("#f0f0f0","#444","?"))
        header = (
            f"[{lbl}]  {item['task'][:60]}...  ·  "
            f"{item.get('model','?')}  ·  {item.get('time',0):.1f}s"
            + (f"  · 🧵 {item.get('thread','')}" if item.get("thread") else "")
        )
        with st.expander(header):
            st.markdown(item["result"])
            ca,cb = st.columns(2)
            with ca:
                st.download_button(
                    "Download .txt", data=item["result"],
                    file_name=f"result_{int(time.time())}.txt",
                    mime="text/plain", key=f"dl_txt_{id(item)}",
                )
            with cb:
                path = export_to_pdf(
                    item["task"],item["result"],item.get("type","?"),item.get("model","?")
                )
                if path and os.path.exists(path):
                    with open(path,"rb") as f:
                        st.download_button(
                            "Download PDF", f.read(),
                            file_name=os.path.basename(path),
                            mime="application/pdf", key=f"dl_pdf_{id(item)}",
                        )
