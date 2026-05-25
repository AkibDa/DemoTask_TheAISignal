# app.py

import streamlit as st
from agent.graph import agent

st.set_page_config(page_title="App Compiler System", layout="wide")
st.title("⚙️ System Compiler: Zero-to-Architecture Pipeline")

with st.sidebar:
    st.header("Compiler Settings")
    recursion_limit = st.number_input(
        "Recursion limit", min_value=10, max_value=500, value=100, step=10
    )
    st.markdown("---")
    st.markdown("**Pipeline Passes**")
    st.markdown(
        """
1. 🧠 Intent Extraction  
2. 🏛️ Architecture Design  
3. 📦 Schema Generation  
4. 🛡️ Validation (Det + LLM)  
5. 🔧 Repair Engine (if needed)  
6. 🚀 Runtime Execution  
"""
    )

st.markdown(
    "Enter system requirements. The compiler will generate IR, design schemas, "
    "validate layers (deterministic + semantic), self-repair, and simulate runtime execution."
)

user_prompt = st.text_area(
    "System Prompt",
    placeholder="Build a multi-tenant hospital management system with role-based auth...",
    height=100,
)

def _pipeline_icon(step: str) -> str:
    icons = {
        "INTENT": "🧠", "ARCHITECTURE": "🏛️", "SCHEMA": "📦",
        "VALIDATION": "🛡️", "REPAIR": "🔧", "RUNTIME": "🚀",
    }
    for key, icon in icons.items():
        if key in step.upper():
            return icon
    return "•"

if st.button("🚀 Run Compilation"):
    if user_prompt.strip():
        status_placeholder = st.empty()
        pipeline_placeholder = st.empty()
        status_placeholder.info("Running Compiler Passes…")

        try:
            result = agent.invoke(
                {"user_prompt": user_prompt},
                {"recursion_limit": int(recursion_limit)},
            )
            final_status = result.get("status", "UNKNOWN")

            if "COMPLETE" in final_status or "PASSED" in final_status:
                status_placeholder.success(f"✅ Compilation Finished: {final_status}")
            elif "FAILED" in final_status:
                status_placeholder.warning(f"⚠️ Compilation Finished with issues: {final_status}")
            else:
                status_placeholder.info(f"Compilation status: {final_status}")

            pipeline_log = result.get("pipeline_log", [])
            if pipeline_log:
                with pipeline_placeholder.container():
                    st.subheader("🔄 Compiler Pipeline Log")
                    for entry in pipeline_log:
                        stripped = entry.strip()
                        if not stripped:
                            continue
                        if stripped.startswith("---"):
                            st.markdown(f"**{stripped.replace('-', '').strip()}**")
                        elif stripped.startswith("✓"):
                            st.success(stripped, icon="✅")
                        elif stripped.startswith("✗") or stripped.startswith("⛔"):
                            st.error(stripped, icon="❌")
                        elif stripped.startswith("⚠") or "FAIL" in stripped:
                            st.warning(stripped, icon="⚠️")
                        else:
                            st.text(stripped)

            st.divider()
            metrics = result.get("metrics", {})
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Repair Cycles", metrics.get("repairs", 0))

            if result.get("validation_report"):
                score = result["validation_report"].consistency_score
                is_valid = result["validation_report"].is_valid
                col2.metric("Consistency Score", f"{score}%")
                col3.metric("Validation", "PASSED ✅" if is_valid else "FAILED ❌")

            if result.get("runtime_report"):
                rr = result["runtime_report"]
                col4.metric("Runtime Pass Rate", f"{rr.success_rate}%")

            det = result.get("deterministic_check") or (
                result.get("validation_report", {}) and
                result["validation_report"].deterministic_check
            )
            if det:
                with st.expander("🔬 Deterministic Validator Results", expanded=False):
                    if det.passed:
                        st.success("All deterministic checks passed.")
                    else:
                        for err in det.missing_api_fields:
                            st.error(f"[API→DB] {err}")
                        for err in det.missing_db_tables:
                            st.error(f"[DB] {err}")
                        for err in det.ui_binding_errors:
                            st.warning(f"[UI] {err}")
                        for err in det.auth_role_errors:
                            st.warning(f"[Auth] {err}")

            repair_history = result.get("repair_history", [])
            if repair_history:
                with st.expander(f"🔧 Repair History ({len(repair_history)} cycle(s))", expanded=False):
                    for entry in repair_history:
                        st.info(entry)

            st.divider()

            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
                "🧠 Intent IR",
                "🏛️ Architecture",
                "📦 DB Schema",
                "🔌 API Schema",
                "🖥️ UI Schema",
                "🛡️ Validation Report",
                "🚀 Runtime Report",
            ])

            with tab1:
                if result.get("intent_ir"):
                    ir = result["intent_ir"]
                    st.json(ir.model_dump())
                    if ir.assumptions:
                        st.subheader("📌 Compiler Assumptions")
                        for a in ir.assumptions:
                            st.info(a)

            with tab2:
                if result.get("architecture_ir"):
                    st.json(result["architecture_ir"].model_dump())

            system_schemas = result.get("system_schemas")
            with tab3:
                if system_schemas:
                    st.json([t.model_dump() for t in system_schemas.db_schema])

            with tab4:
                if system_schemas:
                    st.json([e.model_dump() for e in system_schemas.api_schema])

            with tab5:
                if system_schemas:
                    st.json([u.model_dump() for u in system_schemas.ui_schema])

            with tab6:
                if result.get("validation_report"):
                    vr = result["validation_report"]
                    st.json(vr.model_dump())
                    if vr.issues:
                        st.subheader("Issues")
                        for issue in vr.issues:
                            severity_color = {"high": "error", "medium": "warning", "low": "info"}.get(
                                issue.severity.lower(), "info"
                            )
                            getattr(st, severity_color)(
                                f"**[{issue.layer}]** {issue.issue}\n\n_Fix: {issue.suggested_fix}_"
                            )
                if result.get("repair_plan"):
                    st.subheader("Last Repair Plan")
                    rp = result["repair_plan"]
                    st.markdown(f"**Target Layer:** `{rp.target_layer}`")
                    st.markdown(f"**Explanation:** {rp.explanation}")
                    st.subheader("Patches")
                    for patch in rp.patches:
                        st.json(patch.model_dump())

            with tab7:
                rr = result.get("runtime_report")
                if rr:
                    sub1, sub2, sub3 = st.columns(3)
                    sub1.metric("Total Endpoints", rr.total_endpoints)
                    sub2.metric("Passed", rr.passed)
                    sub3.metric("Failed", rr.failed)
                    st.progress(int(rr.success_rate))
                    for ep_result in rr.results:
                        if ep_result.status == "PASS":
                            st.success(
                                f"✅ `{ep_result.method} {ep_result.route}` → {ep_result.response_code}"
                            )
                        else:
                            st.error(
                                f"❌ `{ep_result.method} {ep_result.route}` → {ep_result.detail}"
                            )

        except Exception as e:
            import traceback
            status_placeholder.error(f"Compilation Error: {e}")
            st.code(traceback.format_exc())
    else:
        st.warning("Please enter a system prompt.")
