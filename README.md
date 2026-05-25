# DemoTask_TheAISignal
Compiler-style app generation system that takes a natural-language product prompt and compiles it into:
- intent IR,
- architecture IR,
- DB/API/UI/Auth schemas,
- validation + repair history,
- runtime simulation results.

It is designed to run on a **local Ollama model** (`qwen2.5-coder:1.5b`) with no remote LLM dependency required by default.

## What this repository gives you
- A **CLI compiler** (`main.py`) for interactive prompt-to-architecture runs.
- A **Streamlit UI** (`app.py`) for visual inspection of every pipeline artifact.
- A **benchmark harness** (`benchmark.py`) with 20 fixed test cases and resumable result files.
- A **LangGraph pipeline** (`agent/graph.py`) implementing deterministic checks, repair loops, and runtime simulation.

## Clone and run on your own system
For a clean machine setup, use this full sequence:

```bash
git clone https://github.com/AkibDa/DemoTask_TheAISignal.git
cd DemoTask_TheAISignal
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install streamlit python-dotenv langgraph langchain-core langchain-ollama pydantic tenacity
ollama pull qwen2.5-coder:1.5b
```

Then start either mode:

```bash
# CLI mode
python main.py

# UI mode
streamlit run app.py
```

## End-to-end flow
1. Extract intent from prompt (`IntentIR`)
2. Sanitize role labels
3. Design architecture (`ArchitectureIR`)
4. Generate DB, Auth, API, UI schemas (`SystemSchemas`)
5. Validate consistency (deterministic + semantic)
6. If needed, repair targeted layers and re-validate (loop)
7. Simulate runtime endpoint behavior (`RuntimeReport`)

## Architecture diagram
```mermaid
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           APP COMPILER SYSTEM ARCHITECTURE                           │
│                      Zero-to-Architecture Pipeline with Self-Repair                  │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── INPUT LAYER ───────────────────────────────────┐
│                                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   main.py   │    │  app.py     │    │benchmark.py │    │   CLI       │        │
│  │   (CLI)     │    │ (Streamlit) │    │ (Harness)   │    │  Args       │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                  │                  │                  │                │
│         └──────────────────┴──────────────────┴──────────────────┘                │
│                                    │                                               │
│                              user_prompt                                           │
└────────────────────────────────────┼──────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           CORE ORCHESTRATION ENGINE                                  │
│                        (LangGraph StateGraph - agent.py)                             │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           COMPILER PIPELINE (8 Nodes)                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                         PASS 1: INTENT EXTRACTION                             │  │
│  │  ┌─────────────────────┐    ┌─────────────────────┐                          │  │
│  │  │ intent_extractor    │───▶│ intent_sanitizer    │                          │  │
│  │  │ (LLM: IntentIR)     │    │ (Role Cleaner)      │                          │  │
│  │  └─────────────────────┘    └─────────────────────┘                          │  │
│  │         Output: IntentIR (app_type, roles, features, assumptions)             │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                       PASS 2: ARCHITECTURE DESIGN                             │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │              architecture_designer (LLM: ArchitectureIR)                │ │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │  │
│  │         Output: ArchitectureIR (entities, pages, workflows)                  │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                        PASS 3: SCHEMA GENERATION                              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │  │
│  │  │ DB Schema    │  │ Auth Schema  │  │ API Schema   │  │ UI Schema    │     │  │
│  │  │ (Tables)     │  │ (Roles +     │  │ (Endpoints)  │  │ (Pages +     │     │  │
│  │  │              │  │  Permissions)│  │              │  │  Components) │     │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │  │
│  │                    Output: SystemSchemas (all layers)                         │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                      PASS 4: VALIDATION + REPAIR LOOP                         │  │
│  │                                                                               │  │
│  │         ┌─────────────────────────────────────────────────────┐             │  │
│  │         │              validator_node (Dual Validation)        │             │  │
│  │         │  ┌─────────────────┐      ┌─────────────────────┐   │             │  │
│  │         │  │ Deterministic   │      │ Semantic (LLM)      │   │             │  │
│  │         │  │ Checks (Python) │      │ Validator           │   │             │  │
│  │         │  └─────────────────┘      └─────────────────────┘   │             │  │
│  │         │         │                          │                 │             │  │
│  │         │         └──────────┬───────────────┘                 │             │  │
│  │         │                    ▼                                 │             │  │
│  │         │         Blended Score (60/40 or boost)               │             │  │
│  │         │                    │                                 │             │  │
│  │         │         ┌──────────┴──────────┐                      │             │  │
│  │         │         ▼                     ▼                      │             │  │
│  │         │    VALIDATION_PASS      VALIDATION_FAIL               │             │  │
│  │         │         │                     │                      │             │  │
│  │         │         │                     ▼                      │             │  │
│  │         │         │         ┌─────────────────────┐            │             │  │
│  │         │         │         │   repair_engine     │            │             │  │
│  │         │         │         │  (Layer-specific)   │            │             │  │
│  │         │         │         │                     │            │             │  │
│  │         │         │         │  • DB Repair        │            │             │  │
│  │         │         │         │  • API Repair       │            │             │  │
│  │         │         │         │  • Auth Repair      │            │             │  │
│  │         │         │         │  • UI Repair        │            │             │  │
│  │         │         │         └──────────┬──────────┘            │             │  │
│  │         │         │                    │                       │             │  │
│  │         │         │                    ▼                       │             │  │
│  │         │         │         ┌─────────────────────┐            │             │  │
│  │         │         │         │    schema_sync      │            │             │  │
│  │         │         │         │ (Dependency Resolver)│            │             │  │
│  │         │         │         └──────────┬──────────┘            │             │  │
│  │         │         │                    │                       │             │  │
│  │         │         └────────────────────┘                       │             │  │
│  │         │                  (loop until pass or max 3 repairs)   │             │  │
│  │         └─────────────────────────────────────────────────────┘             │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                      │                                              │
│                                      ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                        PASS 5: RUNTIME EXECUTION                              │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │              runtime_executor (Simulation Engine)                        │ │  │
│  │  │  • Simulates all API endpoints                                          │ │  │
│  │  │  • Validates request/response patterns                                  │ │  │
│  │  │  • Generates success rate                                               │ │  │
│  │  │  • Boosts validation score if ≥70%                                      │ │  │
│  │  └─────────────────────────────────────────────────────────────────────────┘ │  │
│  │                    Output: RuntimeReport (pass/fail per endpoint)            │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────── OUTPUT LAYER ──────────────────────────────────┐
│                                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  IntentIR       │  │  ArchitectureIR │  │  SystemSchemas  │                   │
│  │  • app_type     │  │  • entities     │  │  • db_schema    │                   │
│  │  • roles        │  │  • pages        │  │  • api_schema   │                   │
│  │  • features     │  │  • workflows    │  │  • ui_schema    │                   │
│  │  • assumptions  │  │                 │  │  • auth_schema  │                   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                   │
│                                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ ValidationReport│  │  RuntimeReport  │  │  RepairHistory  │                   │
│  │  • is_valid     │  │  • success_rate │  │  • repair_cycles│                   │
│  │  • score        │  │  • passed/total │  │  • patches      │                   │
│  │  • issues       │  │  • per-endpoint │  │  • explanations │                   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                   │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── SUPPORTING LAYERS ─────────────────────────────┐
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                           LLM INTEGRATION (config.py)                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────────┐    │  │
│  │  │              ChatOllama (qwen2.5-coder:1.5b)                        │    │  │
│  │  │              • Temperature: 0                                       │    │  │
│  │  │              • Retry logic with exponential backoff                 │    │  │
│  │  │              • Structured output parsing                            │    │  │
│  │  └─────────────────────────────────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                           PROMPT ENGINE (prompt.py)                          │  │
│  │  • 10 specialized prompts per pipeline node                                  │  │
│  │  • Repair-specific prompts for each layer                                    │  │
│  │  • Role sanitization instructions                                            │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                         DETERMINISTIC TOOLS (tools.py)                       │  │
│  │  • run_deterministic_checks() - Cross-layer validation                       │  │
│  │  • deterministic_consistency_score() - Scoring                               │  │
│  │  • run_runtime_simulation() - Endpoint testing                               │  │
│  │  • _build_sample_payload() - Test data generation                           │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                           DATA MODELS (states.py)                            │  │
│  │  • 15+ Pydantic models for type safety                                       │  │
│  │  • IntentIR, ArchitectureIR, SystemSchemas                                   │  │
│  │  • ValidationReport, RepairPlan, RuntimeReport                               │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── DATA FLOW ─────────────────────────────────────┐
│                                                                                    │
│  user_prompt ──▶ IntentIR ──▶ ArchitectureIR ──▶ SystemSchemas                    │
│                                                           │                        │
│                                                           ▼                        │
│                                              ┌────────────────────┐               │
│                                              │  Validation Loop   │               │
│                                              │  (max 3 cycles)    │               │
│                                              └─────────┬──────────┘               │
│                                                        │                           │
│                                    ┌───────────────────┼───────────────────┐       │
│                                    │                   │                   │       │
│                                    ▼                   ▼                   ▼       │
│                              DB Schema           API Schema           UI Schema    │
│                                    │                   │                   │       │
│                                    └───────────────────┼───────────────────┘       │
│                                                        │                           │
│                                                        ▼                           │
│                                              RuntimeReport                         │
│                                                        │                           │
│                                                        ▼                           │
│                                              Final Output                          │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── REPAIR ARCHITECTURE ───────────────────────────┐
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                      VALIDATOR → REPAIR MAPPING                              │  │
│  ├─────────────────────────────────────────────────────────────────────────────┤  │
│  │  Deterministic Failure          │  Repair Capability                        │  │
│  ├─────────────────────────────────┼───────────────────────────────────────────┤  │
│  │  missing_db_tables              │  add_endpoint (DB layer)                  │  │
│  │  missing_api_fields             │  add_field (API layer)                    │  │
│  │  auth_role_errors               │  add_role (Auth layer)                    │  │
│  │  ui_binding_errors              │  bind_component (UI layer)                │  │
│  │  empty_response_fields          │  add_field to endpoint                    │  │
│  │  semantic issues only           │  Cross-Layer synchronization + repair     │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                      PATCH NORMALIZATION                                     │  │
│  │  "add" ──▶ add_field / add_role / add_endpoint (based on context)           │  │
│  │  "remove" ──▶ remove_field / remove_role / remove_endpoint                  │  │
│  │  "bind" ──▶ bind_component                                                  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── SCORING SYSTEM ────────────────────────────────┐
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                      BLENDED CONSISTENCY SCORE                               │  │
│  ├─────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                              │  │
│  │  IF semantic_issues == 0:                                                   │  │
│  │      score = max(det_score, 75)  # Boost to at least 75                     │  │
│  │  ELSE:                                                                       │  │
│  │      score = (det_score * 0.6) + (semantic_score * 0.4)  # 60/40 blend      │  │
│  │                                                                              │  │
│  │  IF runtime_success_rate >= 70:                                             │  │
│  │      score = max(score, runtime_success_rate)  # Runtime override           │  │
│  │                                                                              │  │
│  │  VALIDATION_PASS conditions:                                                │  │
│  │    1. semantic_issues == 0                                                  │  │
│  │    2. (is_valid AND score >= 65 AND det_passed)                             │  │
│  │    3. runtime_success_rate >= 70                                            │  │
│  │                                                                              │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── EXTERNAL INTERFACES ───────────────────────────┐
│                                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
│  │   Streamlit UI  │  │   CLI (main.py) │  │   Benchmark     │                   │
│  │   (app.py)      │  │   Interactive   │  │   Suite         │                   │
│  │                 │  │   Mode          │  │   (20 cases)    │                   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                   │
│                                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │                         RESULTS PERSISTENCE                                  │  │
│  │  benchmark_results/                                                          │  │
│  │  ├── case_01.json  ──▶ case_20.json (cached results)                        │  │
│  │  └── results.csv (exportable)                                               │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── KEY METRICS ───────────────────────────────────┐
│                                                                                    │
│  • Intent Extraction Accuracy    : roles, features, assumptions                   │
│  • Architecture Completeness     : entities (≤6), pages (≤8), workflows (≤5)      │
│  • Schema Generation Quality     : DB, API, UI, Auth alignment                    │
│  • Validation Score              : 0-100 blended score                            │
│  • Repair Cycles                 : 0-5 attempts                                   │
│  • Runtime Success Rate          : % of endpoints passing simulation              │
│  • Convergence Rate              : % of cases passing validation                  │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## Repository structure
```text
.
├── agent/
│   ├── config.py      # LLM configuration + retry wrapper
│   ├── graph.py       # LangGraph nodes + routing + pipeline orchestration
│   ├── prompt.py      # Prompt templates for each pass
│   ├── states.py      # Pydantic schemas for IR/reports
│   ├── tools.py       # Deterministic checks + runtime simulation helpers
│   └── utility.py     # Generic retry helpers (currently not wired into graph)
├── app.py             # Streamlit UI entrypoint
├── benchmark.py       # 20-case benchmark runner + summary/export
├── benchmark_results/ # Saved per-case benchmark JSON outputs
├── main.py            # CLI entrypoint
└── README.md
```

## Prerequisites
- Python 3.9+
- Ollama installed locally
- Ollama model: `qwen2.5-coder:1.5b`

## Setup (first-time)
1) Create and activate virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2) Install dependencies:
```bash
python -m pip install --upgrade pip
python -m pip install streamlit python-dotenv langgraph langchain-core langchain-ollama pydantic tenacity
```

3) Start Ollama and ensure the model is available:
```bash
ollama serve
ollama pull qwen2.5-coder:1.5b
```

## How to run

### A) Interactive CLI compiler
```bash
python main.py
```
What happens:
- prompts: `Enter your system requirements:`
- executes full graph via `agent.invoke(...)`
- prints final status, consistency score, validation flag, runtime pass rate, repair cycles, repair history.

Optional recursion limit:
```bash
python main.py -r 150
```

### B) Quick single-case benchmark from CLI
```bash
python main.py --benchmark
```
What happens:
- runs one fixed prompt (`gym memberships`)
- prints compact benchmark metrics (validation score/pass, repair cycles, runtime pass rate).

### C) Streamlit UI mode
```bash
streamlit run app.py
```
What happens:
- opens a UI with recursion-limit input and prompt box,
- shows pipeline logs and metrics,
- exposes tabs for Intent IR, Architecture, DB/API/UI schemas, Validation Report, Runtime Report.

### D) Full benchmark harness (20 cases)
Useful commands:
```bash
python benchmark.py --dry-run
python benchmark.py --next
python benchmark.py --case 1
python benchmark.py --category standard --delay 30
python benchmark.py --summary
python benchmark.py --summary --csv benchmark_results/results.csv
python benchmark.py --reset
```

Behavior notes:
- results are persisted in `benchmark_results/case_XX.json`,
- reruns skip completed cases by default,
- use `--no-skip` to force rerun,
- `--dry-run` and `--summary` do not call the model.

## Exactly which code does what

### Entry points
- `main.py`
  - `main()`: CLI argument parsing and execution mode switch.
  - Interactive mode calls `agent.invoke(...)` with user prompt.
  - `--benchmark` mode runs one fixed test prompt and prints summary metrics.
- `app.py`
  - Streamlit page setup and UI controls.
  - On button click, calls `agent.invoke(...)`.
  - Renders pipeline logs, metrics, deterministic issues, repair plan/history, and JSON tabs.
- `benchmark.py`
  - Defines benchmark cases (`STANDARD_CASES`, `EDGE_CASES`).
  - `run_case()`: executes one benchmark prompt through the same graph.
  - `_save_result()`/`_load_result()`: persist and reuse case outputs.
  - `print_summary()`: computes aggregate benchmark stats.
  - `save_csv()`: exports saved results.

### Pipeline orchestration (core logic)
- `agent/graph.py`
  - `_call()`: central model invocation wrapper using retry from `agent/config.py`.
  - `_log()`: records pipeline logs for both terminal and UI.
  - `intent_extractor_node()`: builds `IntentIR` from user prompt.
  - `intent_sanitizer_node()`: filters/normalizes invalid role labels.
  - `architecture_designer_node()`: builds constrained `ArchitectureIR`.
  - `schema_generator_node()`: generates DB/Auth/API/UI schemas, with targeted regeneration during repair loops.
  - `validator_node()`: runs deterministic checks + semantic validation, computes blended consistency score, pass/fail status.
  - `repair_engine_node()`: chooses target layer and applies atomic schema patches.
  - `schema_sync_node()`: cleans downstream references (fields/endpoints/roles) after repair.
  - `runtime_executor_node()`: simulates endpoint runtime behavior and reports pass/fail.
  - `validation_router()`: decides whether to continue to runtime or loop back to repair (max 5 repair cycles).
  - `agent = graph.compile()`: compiled LangGraph app used by all entrypoints.

### Prompt engineering layer
- `agent/prompt.py`
  - Contains one prompt template per pass:
    - intent extraction,
    - architecture generation,
    - DB/API/Auth/UI schema generation,
    - validation,
    - generic + layer-specific repairs.
  - Encodes structural constraints such as role semantics, endpoint bindings, and schema consistency requirements.

### Data contracts / schemas
- `agent/states.py`
  - Defines all Pydantic models shared across pipeline passes:
    - `IntentIR`, `ArchitectureIR`, `SystemSchemas`,
    - `ValidationReport`, `RepairPlan`,
    - `RuntimeReport`, and related nested models.
  - These models are the strict structured outputs expected from model calls.

### Deterministic validation and runtime simulation
- `agent/tools.py`
  - `run_deterministic_checks()`: cross-layer rule checks for:
    - API request field vs DB field mismatches,
    - Auth role coverage mismatches,
    - UI endpoint binding errors,
    - UI field mapping errors.
  - `deterministic_consistency_score()`: computes rule-based score floor.
  - `run_runtime_simulation()`: simulates endpoint execution and validates route shape, payload serializability, and response fields.
  - Also includes small tool-decorated utility functions (`validate_json_schema`, `check_api_matches_db`, `simulate_app_execution`) and project-root helpers.

### Model configuration and retries
- `agent/config.py`
  - `get_llm()`: configures `ChatOllama(model="qwen2.5-coder:1.5b", temperature=0)`.
  - `invoke_with_retry()`: retries structured invocations up to 3 attempts with delay.

### Utility helpers
- `agent/utility.py`
  - Generic Tenacity retry wrappers and structured-output repair helpers.
  - Currently present as reusable utilities; the main graph path uses `invoke_with_retry()` from `agent/config.py`.

## What outputs to expect after a run
- In-memory run output (from `agent.invoke(...)`) includes:
  - `status`,
  - `intent_ir`,
  - `architecture_ir`,
  - `system_schemas`,
  - `validation_report`,
  - `deterministic_check`,
  - `repair_plan`,
  - `repair_history`,
  - `runtime_report`,
  - `metrics` and `pipeline_log`.
- Benchmark mode writes disk artifacts:
  - `benchmark_results/case_01.json` ... `case_20.json` (as run).

## Benchmark results snapshot (currently saved)
Data source files:
- `benchmark_results/case_04.json`
- `benchmark_results/case_07.json`
- `benchmark_results/case_13.json`
- `benchmark_results/case_17.json`

| Case | Category | Description | Final Status | Validation Passed | Consistency Score | Deterministic Passed | Runtime Success Rate (%) | Repair Cycles | Elapsed (s) |
| --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| 04 | standard | LMS — online learning platform | COMPILATION_COMPLETE | ✅ | 83 | ❌ | 83.3 | 2 | 145.11 |
| 07 | standard | Restaurant POS and ordering system | COMPILATION_COMPLETE | ✅ | 100 | ❌ | 100.0 | 2 | 161.99 |
| 13 | edge | Contradictory requirements | COMPILATION_COMPLETE | ✅ | 83 | ❌ | 83.3 | 2 | 108.50 |
| 17 | edge | Mobile-first ambiguity | COMPILATION_COMPLETE | ✅ | 100 | ❌ | 100.0 | 2 | 203.54 |

### Aggregate summary (partial run: 4/20 cases)
- Score threshold met: `4/4 (100%)`
- Validation passed: `4/4 (100%)`
- Deterministic checks passed: `0/4 (0%)`
- Average consistency score: `91.5`
- Average runtime success rate: `91.65%`
- Average repair cycles: `2.0`
- Average time per case: `154.78s`
- Total elapsed time (sum): `619.14s`

## Troubleshooting
- If model calls fail immediately:
  - confirm `ollama serve` is running,
  - confirm model exists via `ollama pull qwen2.5-coder:1.5b`.
- If Streamlit UI fails to load:
  - verify `streamlit` is installed in the active `.venv`.
- If benchmark appears slow:
  - use `--next` for incremental execution,
  - increase `--delay` to reduce rate-limit issues,
  - use `--summary` to inspect completed runs without new model calls.
