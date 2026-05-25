# app.py

import streamlit as st
import json
import time
import os
import pandas as pd

st.set_page_config(page_title="App Compiler System", layout="wide")
st.title("⚙️ System Compiler: Interactive Demo Viewer")

def dict_get(obj, key, default=None):
  if isinstance(obj, dict):
    return obj.get(key, default)
  return getattr(obj, key, default)

st.header("Aggregate Benchmark Performance")
st.markdown("Scans the `benchmark_results` directory to compare pipeline runs.")

benchmark_dir = "benchmark_results"

if not os.path.exists(benchmark_dir):
  st.warning(f"Directory `{benchmark_dir}` not found. Please create it and add your JSON benchmark files.")
else:
  all_results = []
  for filename in os.listdir(benchmark_dir):
    if filename.endswith(".json"):
      file_path = os.path.join(benchmark_dir, filename)
      try:
        with open(file_path, "r", encoding="utf-8") as f:
          data = json.load(f)
          if "description" in data and "consistency_score" in data:
            all_results.append(data)
      except Exception as e:
        st.error(f"Could not read {filename}: {e}")

  if not all_results:
    st.info(f"No valid benchmark JSON files found in `{benchmark_dir}`.")
  else:
    df = pd.DataFrame(all_results)

    display_cols = [
      "case_id", "category", "description", "consistency_score",
      "runtime_success_rate", "repair_cycles", "elapsed_seconds",
      "validation_passed", "deterministic_passed"
    ]

    existing_cols = [col for col in display_cols if col in df.columns]
    df_display = df[existing_cols].sort_values("case_id")

    avg_consistency = df["consistency_score"].mean()
    avg_runtime = df["runtime_success_rate"].mean()
    avg_time = df["elapsed_seconds"].mean()

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Consistency Score", f"{avg_consistency:.1f}%")
    c2.metric("Avg Runtime Success", f"{avg_runtime:.1f}%")
    c3.metric("Avg Compilation Time", f"{avg_time:.1f}s")

    st.divider()

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
      st.subheader("Consistency vs. Runtime Success")
      chart_data = df.set_index("description")[["consistency_score", "runtime_success_rate"]]
      st.bar_chart(chart_data)

    with col_chart2:
      st.subheader("Compilation Time (Seconds)")
      time_data = df.set_index("description")[["elapsed_seconds"]]
      st.bar_chart(time_data)

    st.divider()

    st.subheader("Raw Benchmark Data")
    st.dataframe(df_display, use_container_width=True, hide_index=True)