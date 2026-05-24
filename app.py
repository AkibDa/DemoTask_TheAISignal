# app.py

import streamlit as st
from agent.graph import agent

st.set_page_config(page_title="App Compiler System", layout="wide")
st.title("⚙️ System Compiler: Zero-to-Architecture Pipeline")

with st.sidebar:
  st.header("Compiler Settings")
  recursion_limit = st.number_input("Recursion limit", min_value=10, max_value=500, value=100, step=10)

st.markdown(
  "Enter system requirements. The compiler will generate IR, design schemas, validate layers, and self-repair.")

user_prompt = st.text_area(
  "System Prompt",
  placeholder="Build a multi-tenant hospital management system with role-based auth...",
  height=100,
)

if st.button("🚀 Run Compilation"):
  if user_prompt.strip():
    status_placeholder = st.empty()
    status_placeholder.info("Running Compiler Passes...")

    try:
      result = agent.invoke(
        {"user_prompt": user_prompt},
        {"recursion_limit": int(recursion_limit)}
      )
      status_placeholder.success(f"Compilation Finished: {result.get('status')}")

      metrics = result.get("metrics", {})
      col1, col2, col3 = st.columns(3)
      col1.metric("Repair Cycles", metrics.get("repairs", 0))
      if result.get("validation_report"):
        score = result["validation_report"].consistency_score
        col2.metric("Consistency Score", f"{score}%")
        is_valid = result["validation_report"].is_valid
        col3.metric("Final Status", "PASSED" if is_valid else "FAILED")

      st.divider()

      tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧠 Intent IR", "🏛️ Architecture", "📦 DB Schema", "🔌 API Schema", "🛡️ Validation Report"
      ])

      with tab1:
        if result.get("intent_ir"):
          st.json(result["intent_ir"].model_dump())

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
        if result.get("validation_report"):
          st.json(result["validation_report"].model_dump())
        if result.get("repair_plan"):
          st.subheader("Auto-Repair Log")
          st.json(result["repair_plan"].model_dump())

    except Exception as e:
      status_placeholder.error(f"Compilation Error: {e}")
