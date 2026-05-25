# app.py

import streamlit as st
import json
import time
import os
import pandas as pd

st.set_page_config(page_title="App Compiler System", layout="wide")
st.title("⚙️ System Compiler: Interactive Demo Viewer")

# Define our benchmark cases and their default prompts for the Demo Viewer
BENCHMARKS = {
  "LMS": {
    "file": "demos/lms.json",
    "prompt": "Build a Learning Management System with distinct roles for Students, Instructors, and Admins. Include course creation, video uploads, and grading functionality."
  },
  "Restaurant POS": {
    "file": "demos/pos.json",
    "prompt": "Create a cloud-based Point of Sale system for a restaurant. Needs real-time table management, kitchen ticketing, and split-billing capabilities."
  },
  "Contradictory Requirements": {
    "file": "demos/contradictory.json",
    "prompt": "Design an app where users can only view their own data, but also include a public dashboard showing everyone's personal data."
  },
  "Mobile Ambiguity": {
    "file": "demos/mobile.json",
    "prompt": "Make an app for mobile devices that tracks things using GPS."
  }
}


# Helper for dict access
def dict_get(obj, key, default=None):
  if isinstance(obj, dict):
    return obj.get(key, default)
  return getattr(obj, key, default)


# Create main tabs for the application
tab_demo, tab_benchmarks = st.tabs(["🔍 Interactive Demo Viewer", "📊 Benchmark Dashboard"])

# ==========================================
# TAB 1: INTERACTIVE DEMO VIEWER
# ==========================================
with tab_demo:
  with st.sidebar:
    st.header("Viewer Settings")
    selected_case = st.selectbox(
      "Select Benchmark Case",
      list(BENCHMARKS.keys())
    )
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
    "Select a benchmark case from the sidebar. The viewer will load the saved JSON outputs, "
    "simulating the compiler's full zero-to-architecture pipeline."
  )

  user_prompt = st.text_area(
    "System Prompt",
    value=BENCHMARKS[selected_case]["prompt"],
    height=100,
  )

  if st.button("🚀 Run Showcase Compilation"):
    status_placeholder = st.empty()
    pipeline_placeholder = st.empty()
    status_placeholder.info("Loading Saved Benchmark Data…")

    # Simulate processing time for polish
    time.sleep(1.2)

    try:
      target_file = BENCHMARKS[selected_case]["file"]

      if not os.path.exists(target_file):
        st.error(f"Demo file not found: `{target_file}`. Please ensure the JSON file exists.")
        result = {"status": "FAILED - File not found"}
      else:
        with open(target_file, "r", encoding="utf-8") as f:
          result = json.load(f)

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
      col1.metric("Repair Cycles", dict_get(metrics, "repairs", 0))

      vr = result.get("validation_report")
      if vr:
        score = dict_get(vr, "consistency_score", 0)
        is_valid = dict_get(vr, "is_valid", False)
        col2.metric("Consistency Score", f"{score}%")
        col3.metric("Validation", "PASSED ✅" if is_valid else "FAILED ❌")

      rr = result.get("runtime_report")
      if rr:
        success_rate = dict_get(rr, "success_rate", 0)
        col4.metric("Runtime Pass Rate", f"{success_rate}%")

      det = result.get("deterministic_check")
      if not det and vr:
        det = dict_get(vr, "deterministic_check")

      if det:
        with st.expander("🔬 Deterministic Validator Results", expanded=False):
          if dict_get(det, "passed"):
            st.success("All deterministic checks passed.")
          else:
            for err in dict_get(det, "missing_api_fields", []):
              st.error(f"[API→DB] {err}")
            for err in dict_get(det, "missing_db_tables", []):
              st.error(f"[DB] {err}")
            for err in dict_get(det, "ui_binding_errors", []):
              st.warning(f"[UI] {err}")
            for err in dict_get(det, "auth_role_errors", []):
              st.warning(f"[Auth] {err}")

      repair_history = result.get("repair_history", [])
      if repair_history:
        with st.expander(f"🔧 Repair History ({len(repair_history)} cycle(s))", expanded=False):
          for entry in repair_history:
            st.info(entry)

      st.divider()

      t1, t2, t3, t4, t5, t6, t7 = st.tabs([
        "🧠 Intent IR", "🏛️ Architecture", "📦 DB Schema",
        "🔌 API Schema", "🖥️ UI Schema", "🛡️ Validation Report", "🚀 Runtime Report"
      ])

      with t1:
        ir = result.get("intent_ir")
        if ir:
          st.json(ir if isinstance(ir, dict) else ir.model_dump())
          assumptions = dict_get(ir, "assumptions", [])
          if assumptions:
            st.subheader("📌 Compiler Assumptions")
            for a in assumptions:
              st.info(a)
      with t2:
        arch = result.get("architecture_ir")
        if arch:
          st.json(arch if isinstance(arch, dict) else arch.model_dump())
      system_schemas = result.get("system_schemas")
      with t3:
        if system_schemas:
          db = dict_get(system_schemas, "db_schema", [])
          st.json([t if isinstance(t, dict) else t.model_dump() for t in db])
      with t4:
        if system_schemas:
          api = dict_get(system_schemas, "api_schema", [])
          st.json([e if isinstance(e, dict) else e.model_dump() for e in api])
      with t5:
        if system_schemas:
          ui = dict_get(system_schemas, "ui_schema", [])
          st.json([u if isinstance(u, dict) else u.model_dump() for u in ui])
      with t6:
        if vr:
          st.json(vr if isinstance(vr, dict) else vr.model_dump())
          issues = dict_get(vr, "issues", [])
          if issues:
            st.subheader("Issues")
            for issue in issues:
              severity = dict_get(issue, "severity", "info").lower()
              severity_color = {"high": "error", "medium": "warning", "low": "info"}.get(severity, "info")
              getattr(st, severity_color)(
                f"**[{dict_get(issue, 'layer')}]** {dict_get(issue, 'issue')}\n\n_Fix: {dict_get(issue, 'suggested_fix')}_"
              )
        rp = result.get("repair_plan")
        if rp:
          st.subheader("Last Repair Plan")
          st.markdown(f"**Target Layer:** `{dict_get(rp, 'target_layer')}`")
          st.markdown(f"**Explanation:** {dict_get(rp, 'explanation')}")
          st.subheader("Patches")
          for patch in dict_get(rp, "patches", []):
            st.json(patch if isinstance(patch, dict) else patch.model_dump())
      with t7:
        if rr:
          sub1, sub2, sub3 = st.columns(3)
          sub1.metric("Total Endpoints", dict_get(rr, "total_endpoints", 0))
          sub2.metric("Passed", dict_get(rr, "passed", 0))
          sub3.metric("Failed", dict_get(rr, "failed", 0))
          st.progress(int(dict_get(rr, "success_rate", 0)))
          for ep_result in dict_get(rr, "results", []):
            status = dict_get(ep_result, "status")
            method = dict_get(ep_result, "method")
            route = dict_get(ep_result, "route")
            if status == "PASS":
              st.success(f"✅ `{method} {route}` → {dict_get(ep_result, 'response_code')}")
            else:
              st.error(f"❌ `{method} {route}` → {dict_get(ep_result, 'detail')}")

    except Exception as e:
      import traceback

      status_placeholder.error(f"Compilation Error: {e}")
      st.code(traceback.format_exc())

# ==========================================
# TAB 2: BENCHMARK DASHBOARD
# ==========================================
with tab_benchmarks:
  st.header("Aggregate Benchmark Performance")
  st.markdown("Scans the `benchmark_results` directory to compare pipeline runs.")

  benchmark_dir = "benchmark_results"

  if not os.path.exists(benchmark_dir):
    st.warning(f"Directory `{benchmark_dir}` not found. Please create it and add your JSON benchmark files.")
  else:
    # Load all JSON files in the directory
    all_results = []
    for filename in os.listdir(benchmark_dir):
      if filename.endswith(".json"):
        file_path = os.path.join(benchmark_dir, filename)
        try:
          with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Only add if it looks like a benchmark result
            if "description" in data and "consistency_score" in data:
              all_results.append(data)
        except Exception as e:
          st.error(f"Could not read {filename}: {e}")

    if not all_results:
      st.info(f"No valid benchmark JSON files found in `{benchmark_dir}`.")
    else:
      # Convert to Pandas DataFrame for easy manipulation
      df = pd.DataFrame(all_results)

      # Reorder and rename columns for a cleaner display if they exist
      display_cols = [
        "case_id", "category", "description", "consistency_score",
        "runtime_success_rate", "repair_cycles", "elapsed_seconds",
        "validation_passed", "deterministic_passed"
      ]
      # Keep only columns that actually exist in the dataframe
      existing_cols = [col for col in display_cols if col in df.columns]
      df_display = df[existing_cols].sort_values("case_id")

      # --- High Level Metrics ---
      avg_consistency = df["consistency_score"].mean()
      avg_runtime = df["runtime_success_rate"].mean()
      avg_time = df["elapsed_seconds"].mean()

      c1, c2, c3 = st.columns(3)
      c1.metric("Avg Consistency Score", f"{avg_consistency:.1f}%")
      c2.metric("Avg Runtime Success", f"{avg_runtime:.1f}%")
      c3.metric("Avg Compilation Time", f"{avg_time:.1f}s")

      st.divider()

      # --- Visualizations ---
      col_chart1, col_chart2 = st.columns(2)

      with col_chart1:
        st.subheader("Consistency vs. Runtime Success")
        # Set index to description so labels show up correctly on the X-axis
        chart_data = df.set_index("description")[["consistency_score", "runtime_success_rate"]]
        st.bar_chart(chart_data)

      with col_chart2:
        st.subheader("Compilation Time (Seconds)")
        time_data = df.set_index("description")[["elapsed_seconds"]]
        st.bar_chart(time_data)

      st.divider()

      # --- Raw Data Table ---
      st.subheader("Raw Benchmark Data")
      st.dataframe(df_display, use_container_width=True, hide_index=True)