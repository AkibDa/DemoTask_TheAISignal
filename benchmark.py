# benchmark.py

import argparse
import csv
import json
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from agent.graph import agent

@dataclass
class TestCase:
    id: int
    category: str
    prompt: str
    description: str
    expected_min_score: int = 70
    expected_roles_contain: List[str] = field(default_factory=list)
    expected_entities_min: int = 2

STANDARD_CASES: List[TestCase] = [
    TestCase(
        id=1, category="standard",
        description="Multi-tenant SaaS — gym memberships",
        prompt="Build a multi-tenant SaaS for managing gym memberships. Members can sign up, book classes, and pay monthly. Admins manage trainers and schedules.",
        expected_min_score=75,
        expected_roles_contain=["admin", "member"],
        expected_entities_min=4,
    ),
    TestCase(
        id=2, category="standard",
        description="Hospital management system with RBAC",
        prompt="Build a multi-tenant hospital management system with role-based auth for doctors, nurses, patients, and admins. Include appointment scheduling, patient records, and billing.",
        expected_min_score=75,
        expected_roles_contain=["doctor", "patient", "admin"],
        expected_entities_min=5,
    ),
    TestCase(
        id=3, category="standard",
        description="E-commerce marketplace with seller onboarding",
        prompt="Build an e-commerce marketplace where sellers can list products, buyers can purchase and review, and admins moderate listings. Include Stripe payments and email notifications.",
        expected_min_score=70,
        expected_roles_contain=["seller", "buyer"],
        expected_entities_min=5,
    ),
    TestCase(
        id=4, category="standard",
        description="LMS — online learning platform",
        prompt="Create a learning management system where instructors create courses with video lessons and quizzes. Students enroll and track progress. Admins approve courses.",
        expected_min_score=70,
        expected_roles_contain=["instructor", "student"],
        expected_entities_min=4,
    ),
    TestCase(
        id=5, category="standard",
        description="Project management tool (Jira-style)",
        prompt="Build a project management tool like Jira. Teams can create projects, manage sprints, assign tickets, and track velocity. Supports manager, developer, and QA roles.",
        expected_min_score=70,
        expected_roles_contain=["manager", "developer"],
        expected_entities_min=4,
    ),
    TestCase(
        id=6, category="standard",
        description="Real estate listing platform",
        prompt="Build a real estate platform where agents list properties, buyers browse and schedule viewings, and admins verify agent credentials. Include map search and mortgage calculator.",
        expected_min_score=70,
        expected_roles_contain=["agent", "buyer", "admin"],
        expected_entities_min=4,
    ),
    TestCase(
        id=7, category="standard",
        description="Restaurant POS and ordering system",
        prompt="Build a restaurant POS system with table management, menu CRUD, kitchen display, and customer ordering via QR code. Roles: owner, waiter, chef, customer.",
        expected_min_score=70,
        expected_roles_contain=["owner", "waiter", "chef"],
        expected_entities_min=4,
    ),
    TestCase(
        id=8, category="standard",
        description="HR onboarding and payroll system",
        prompt="Create an HR platform for employee onboarding, leave management, payroll processing, and performance reviews. Roles: HR admin, manager, employee.",
        expected_min_score=70,
        expected_roles_contain=["hr_admin", "employee"],
        expected_entities_min=4,
    ),
    TestCase(
        id=9, category="standard",
        description="Event ticketing platform",
        prompt="Build an event ticketing platform where organisers create events, attendees purchase tickets with QR codes, and admins handle fraud. Include Stripe and email confirmations.",
        expected_min_score=70,
        expected_roles_contain=["organiser", "attendee", "admin"],
        expected_entities_min=3,
    ),
    TestCase(
        id=10, category="standard",
        description="IoT device management dashboard",
        prompt="Build a dashboard for managing IoT devices across factory floors. Operators monitor real-time sensor data, engineers configure devices, and admins manage firmware OTA updates.",
        expected_min_score=65,
        expected_roles_contain=["operator", "engineer", "admin"],
        expected_entities_min=3,
    ),
]

EDGE_CASES: List[TestCase] = [
    TestCase(
        id=11, category="edge",
        description="Single-word vague prompt",
        prompt="CRM",
        expected_min_score=50,
        expected_entities_min=2,
    ),
    TestCase(
        id=12, category="edge",
        description="No roles specified",
        prompt="Build a note-taking app where users can create, edit, and share notes.",
        expected_min_score=60,
        expected_entities_min=2,
    ),
    TestCase(
        id=13, category="edge",
        description="Contradictory requirements",
        prompt="Build a fully offline app that also syncs in real-time with the cloud and has zero latency.",
        expected_min_score=50,
        expected_entities_min=1,
    ),
    TestCase(
        id=14, category="edge",
        description="Extremely large scope",
        prompt="Build a full ERP system including accounting, HR, CRM, supply chain, manufacturing, warehouse, and analytics — all with AI copilots and blockchain audit trails.",
        expected_min_score=55,
        expected_entities_min=8,
    ),
    TestCase(
        id=15, category="edge",
        description="No clear app type — social network description",
        prompt="People should be able to follow each other and post content and like things and have a feed.",
        expected_min_score=55,
        expected_entities_min=2,
    ),
    TestCase(
        id=16, category="edge",
        description="Very technical / low-level prompt",
        prompt="Implement a distributed key-value store with consistent hashing, WAL, and Raft consensus.",
        expected_min_score=50,
        expected_entities_min=1,
    ),
    TestCase(
        id=17, category="edge",
        description="Mobile-first ambiguity",
        prompt="Build a food delivery app like Uber Eats.",
        expected_min_score=65,
        expected_roles_contain=["driver", "customer"],
        expected_entities_min=4,
    ),
    TestCase(
        id=18, category="edge",
        description="Security-heavy with compliance mention",
        prompt="Build a HIPAA-compliant telemedicine platform with end-to-end encryption, audit logs, MFA, and SOC 2 controls.",
        expected_min_score=65,
        expected_roles_contain=["doctor", "patient"],
        expected_entities_min=3,
    ),
    TestCase(
        id=19, category="edge",
        description="Minimal prompt — single sentence",
        prompt="Online bookstore.",
        expected_min_score=50,
        expected_entities_min=2,
    ),
    TestCase(
        id=20, category="edge",
        description="Game-like system — non-standard domain",
        prompt="Build a multiplayer RPG backend with character management, inventory, guilds, real-time combat, and leaderboards.",
        expected_min_score=55,
        expected_roles_contain=["player", "admin"],
        expected_entities_min=4,
    ),
]

ALL_CASES = STANDARD_CASES + EDGE_CASES

@dataclass
class BenchmarkResult:
    case_id: int
    category: str
    description: str
    final_status: str
    validation_passed: bool
    consistency_score: int
    deterministic_passed: bool
    repair_cycles: int
    runtime_success_rate: float
    assumptions_made: int
    n_entities: int
    n_endpoints: int
    score_meets_threshold: bool
    elapsed_seconds: float
    error: Optional[str] = None

def run_case(tc: TestCase, recursion_limit: int = 100) -> BenchmarkResult:
    start = time.time()
    try:
        result = agent.invoke(
            {"user_prompt": tc.prompt},
            {"recursion_limit": recursion_limit},
        )
        elapsed = round(time.time() - start, 2)

        vr = result.get("validation_report")
        det = vr.deterministic_check if vr else None
        rr = result.get("runtime_report")
        arch = result.get("architecture_ir")
        schemas = result.get("system_schemas")
        ir = result.get("intent_ir")

        consistency_score = vr.consistency_score if vr else 0
        validation_passed = bool(vr and vr.is_valid)
        deterministic_passed = bool(det and det.passed)
        repair_cycles = result.get("metrics", {}).get("repairs", 0)
        runtime_rate = rr.success_rate if rr else 0.0
        assumptions_made = len(ir.assumptions) if ir else 0
        n_entities = len(arch.entities) if arch else 0
        n_endpoints = len(schemas.api_schema) if schemas else 0

        return BenchmarkResult(
            case_id=tc.id,
            category=tc.category,
            description=tc.description,
            final_status=result.get("status", "UNKNOWN"),
            validation_passed=validation_passed,
            consistency_score=consistency_score,
            deterministic_passed=deterministic_passed,
            repair_cycles=repair_cycles,
            runtime_success_rate=runtime_rate,
            assumptions_made=assumptions_made,
            n_entities=n_entities,
            n_endpoints=n_endpoints,
            score_meets_threshold=consistency_score >= tc.expected_min_score,
            elapsed_seconds=elapsed,
        )

    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        traceback.print_exc()
        return BenchmarkResult(
            case_id=tc.id,
            category=tc.category,
            description=tc.description,
            final_status="ERROR",
            validation_passed=False,
            consistency_score=0,
            deterministic_passed=False,
            repair_cycles=0,
            runtime_success_rate=0.0,
            assumptions_made=0,
            n_entities=0,
            n_endpoints=0,
            score_meets_threshold=False,
            elapsed_seconds=elapsed,
            error=str(exc),
        )

def print_result(r: BenchmarkResult) -> None:
    status_icon = "✅" if r.score_meets_threshold and not r.error else "❌"
    print(
        f"  {status_icon} [{r.category.upper():8}] Case {r.case_id:02d}: {r.description[:50]:<50} | "
        f"Score={r.consistency_score:3d} | Repairs={r.repair_cycles} | "
        f"Runtime={r.runtime_success_rate:5.1f}% | {r.elapsed_seconds:.1f}s"
    )
    if r.error:
        print(f"           ERROR: {r.error}")

def print_summary(results: List[BenchmarkResult]) -> None:
    total = len(results)
    errored = [r for r in results if r.error]
    passed_threshold = [r for r in results if r.score_meets_threshold]
    validated = [r for r in results if r.validation_passed]
    det_passed = [r for r in results if r.deterministic_passed]

    scores = [r.consistency_score for r in results if not r.error]
    repair_counts = [r.repair_cycles for r in results if not r.error]
    runtime_rates = [r.runtime_success_rate for r in results if not r.error]
    elapsed = [r.elapsed_seconds for r in results]

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  Total cases run           : {total}")
    print(f"  Errors                    : {len(errored)}")
    print(f"  Met score threshold       : {len(passed_threshold)}/{total}  ({100*len(passed_threshold)//total}%)")
    print(f"  Validation passed         : {len(validated)}/{total}  ({100*len(validated)//total}%)")
    print(f"  Deterministic checks pass : {len(det_passed)}/{total}  ({100*len(det_passed)//total}%)")
    if scores:
        print(f"  Avg consistency score     : {sum(scores)/len(scores):.1f}")
        print(f"  Min / Max score           : {min(scores)} / {max(scores)}")
    if repair_counts:
        print(f"  Avg repair cycles         : {sum(repair_counts)/len(repair_counts):.2f}")
        print(f"  Max repair cycles         : {max(repair_counts)}")
    if runtime_rates:
        print(f"  Avg runtime success rate  : {sum(runtime_rates)/len(runtime_rates):.1f}%")
    if elapsed:
        print(f"  Avg time per case         : {sum(elapsed)/len(elapsed):.1f}s")
        print(f"  Total wall time           : {sum(elapsed):.1f}s")
    print("=" * 70)

    for cat in ["standard", "edge"]:
        cat_results = [r for r in results if r.category == cat]
        if not cat_results:
            continue
        cat_pass = [r for r in cat_results if r.score_meets_threshold]
        cat_scores = [r.consistency_score for r in cat_results if not r.error]
        avg = sum(cat_scores) / len(cat_scores) if cat_scores else 0
        print(
            f"  [{cat.upper():8}] {len(cat_pass)}/{len(cat_results)} passed threshold | avg score={avg:.1f}"
        )
    print()

def save_csv(results: List[BenchmarkResult], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
    print(f"Results saved to {path}")

def main():
    parser = argparse.ArgumentParser(description="App Compiler Benchmark Harness")
    parser.add_argument("--category", choices=["standard", "edge", "all"], default="all")
    parser.add_argument("--case", type=int, help="Run a single test case by ID")
    parser.add_argument("--recursion-limit", "-r", type=int, default=100)
    parser.add_argument("--csv", type=str, help="Path to save CSV results")
    args = parser.parse_args()

    if args.case:
        cases = [tc for tc in ALL_CASES if tc.id == args.case]
        if not cases:
            print(f"Case {args.case} not found.", file=sys.stderr)
            sys.exit(1)
    elif args.category == "standard":
        cases = STANDARD_CASES
    elif args.category == "edge":
        cases = EDGE_CASES
    else:
        cases = ALL_CASES

    print(f"\n{'='*70}")
    print(f"  APP COMPILER BENCHMARK  —  {len(cases)} case(s)")
    print(f"{'='*70}\n")

    results: List[BenchmarkResult] = []
    for tc in cases:
        print(f"\nRunning case {tc.id:02d}: {tc.description}")
        r = run_case(tc, recursion_limit=args.recursion_limit)
        print_result(r)
        results.append(r)

    print_summary(results)

    if args.csv:
        save_csv(results, args.csv)

if __name__ == "__main__":
    main()
