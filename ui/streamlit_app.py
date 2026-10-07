"""OrchestrAI dashboard (Streamlit). Talks to the FastAPI backend only."""
from __future__ import annotations

import os
import time

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
ICON = {"queued": "⏳", "running": "🟢", "awaiting_approval": "🟠", "completed": "✅", "failed": "🔴",
        "waiting": "🕒"}

st.set_page_config(page_title="OrchestrAI", page_icon="🧠", layout="wide")


def api(method: str, path: str, **kwargs):
    try:
        response = httpx.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except ValueError:
            pass
        st.error(f"API error {exc.response.status_code}: {detail}")
    except httpx.HTTPError as exc:
        st.error(f"Cannot reach the API at {API_URL}: {exc}")
    return None


# ----------------------------------------------------------------------------- pages
def page_overview() -> None:
    st.title("Overview")
    stats = api("GET", "/stats") or {}
    cols = st.columns(5)
    for col, key in zip(cols, ["running", "queued", "awaiting_approval", "completed", "failed"], strict=True):
        col.metric(f"{ICON[key]} {key.replace('_', ' ').title()}", stats.get(key, 0))
    st.subheader("Recent runs")
    runs = api("GET", "/runs", params={"limit": 10}) or []
    for run in runs:
        st.write(f"{ICON.get(run['status'], '')} **{run['goal'][:90]}** · {run['status']} · `{run['id'][:8]}`")
    if not runs:
        st.info("No runs yet. Open **New run** to start one.")


def page_new_run() -> None:
    st.title("New run")
    with st.form("new_run"):
        goal = st.text_area(
            "Goal",
            value="Research and prepare the Q2 2025 quarterly product report: product performance, user growth, "
                  "competitors, market trends and recommendations.",
            height=120,
        )
        priority = st.selectbox("Priority", ["normal", "high", "low"])
        requested_by = st.text_input("Requested by", value="me")
        submitted = st.form_submit_button("Start run")
    if submitted:
        result = api("POST", "/runs", json={"goal": goal, "priority": priority, "requested_by": requested_by})
        if result:
            st.session_state["run_id"] = result["id"]
            st.success(f"Run {result['id']} queued. Open the **Runs** page to watch it.")


def page_runs() -> None:
    st.title("Runs")
    runs = api("GET", "/runs", params={"limit": 50}) or []
    if not runs:
        st.info("No runs yet.")
        return
    labels = {r["id"]: f"{ICON.get(r['status'], '')} {r['goal'][:70]}  ({r['id'][:8]})" for r in runs}
    ids = list(labels)
    current = st.session_state.get("run_id")
    run_id = st.selectbox("Select a run", ids, index=ids.index(current) if current in ids else 0,
                          format_func=labels.get)
    st.session_state["run_id"] = run_id
    run = api("GET", f"/runs/{run_id}")
    if not run:
        return

    st.subheader(run["goal"])
    st.caption(f"Run `{run['id']}` · {ICON.get(run['status'], '')} **{run['status']}** · priority {run['priority']} "
               f"· requested by {run['requested_by']}")
    if run["error"]:
        st.error(run["error"])
    if run["status"] == "awaiting_approval":
        st.warning("Human approval required - open the **Approvals** page.")

    tab_flow, tab_out, tab_tools, tab_logs = st.tabs(["Orchestration", "Outputs", "Tools used", "Logs"])
    with tab_flow:
        cards = run["cards"]
        if cards:
            for col, card in zip(st.columns(len(cards)), cards, strict=True):
                with col.container(border=True):
                    st.markdown(f"**{card['title']}**")
                    st.caption(f"{ICON.get(card['status'], '')} {card['status']} · {card['steps_done']}/"
                               f"{card['steps_total']} steps · {card['tool_calls']} tool calls")
                    st.caption(f"model: `{card['model']}`")
                    st.write((card["last_message"] or "-")[:160])
        st.markdown("#### Activity timeline")
        for event in reversed(run["events"][-40:]):
            st.write(f"`{event['ts'][11:19]}` **{event['agent']}** · {event['kind']} - {event['message'][:200]}")
    with tab_out:
        if run["review"]:
            verdict = "approved" if run["review"]["approved"] else "found issues"
            st.info(f"Reviewer {verdict}: {run['review'].get('summary', '')}")
            for issue in run["review"].get("issues", []):
                st.write(f"- {issue}")
        st.markdown(run["draft"] or "_No draft yet._")
        for agent, text in run["results"].items():
            if agent != "writer":
                with st.expander(f"{agent} output"):
                    st.markdown(text)
    with tab_tools:
        calls = [e for e in run["events"] if e["kind"] == "tool_call"]
        for e in calls:
            with st.expander(f"{e['agent']} → {e['message'][:100]}"):
                st.code(e["data"].get("output", ""), language="text")
        if not calls:
            st.write("No tool calls yet.")
    with tab_logs:
        st.json(run["events"])

    if run["status"] in ("queued", "running") and st.toggle("Auto-refresh every 3 s", value=True):
        time.sleep(3)
        st.rerun()


def page_approvals() -> None:
    st.title("Approvals")
    pending = api("GET", "/approvals") or []
    if not pending:
        st.success("Nothing waiting for approval.")
        return
    for item in pending:
        with st.container(border=True):
            st.subheader(item["goal"][:100])
            if item["escalated"]:
                st.error(f"Escalated: {item['escalation_reason']}")
            review = item.get("review") or {}
            if review:
                st.caption(f"Reviewer: {'approved' if review.get('approved') else 'found issues'} - "
                           f"{review.get('summary', '')}")
                for issue in review.get("issues", []):
                    st.write(f"- {issue}")
            with st.expander("Read the draft", expanded=True):
                st.markdown(item["draft"] or "_empty draft_")
            feedback = st.text_area("Feedback (required to request changes)", key=f"fb-{item['id']}")
            approve_col, changes_col = st.columns(2)
            if approve_col.button("✅ Approve", key=f"ok-{item['id']}", type="primary"):
                if api("POST", f"/runs/{item['id']}/approval", json={"decision": "approve"}):
                    st.success("Approved - finishing the run.")
                    st.rerun()
            if changes_col.button("✏️ Request changes", key=f"chg-{item['id']}"):
                if api("POST", f"/runs/{item['id']}/approval",
                       json={"decision": "request_changes", "feedback": feedback}):
                    st.success("Sent back to the writer.")
                    st.rerun()


def page_memory() -> None:
    st.title("Persistent memory")
    query = st.text_input("Semantic search (leave empty to list recent memories)")
    items = api("GET", "/memory", params={"q": query}) or []
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{item['title']}** · {item.get('category', '')}")
            st.caption(item["snippet"])
    if not items:
        st.info("No memories found. Approved reports are saved here automatically.")


def page_tools() -> None:
    st.title("Tools & integrations")
    for tool in api("GET", "/tools") or []:
        state = "available" if tool["configured"] else "needs configuration"
        st.markdown(f"**{tool['name']}** · {state}  \n{tool['description']}  \n"
                    f"_used by: {', '.join(tool['used_by']) or 'nobody'}_")


PAGES = {"Overview": page_overview, "Runs": page_runs, "New run": page_new_run,
         "Approvals": page_approvals, "Memory": page_memory, "Tools": page_tools}

st.sidebar.markdown("## 🧠 OrchestrAI")
choice = st.sidebar.radio("Navigate", list(PAGES), label_visibility="collapsed")
PAGES[choice]()
