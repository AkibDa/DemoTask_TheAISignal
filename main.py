# main.py

import argparse
import sys
import traceback
from agent.graph import agent

def main():
    parser = argparse.ArgumentParser(description="Compiler-style App Generation System")
    parser.add_argument("--recursion-limit", "-r", type=int, default=100, help="Recursion limit")
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Run the deterministic benchmark suite (see benchmark.py for full suite)"
    )
    args = parser.parse_args()

    try:
        if args.benchmark:
            print("--- Running Quick Benchmark (single case) ---")
            print("Tip: run `python benchmark.py` for the full 20-case evaluation suite.\n")
            test_prompt = "Build a multi-tenant SaaS for managing gym memberships."
            result = agent.invoke(
                {"user_prompt": test_prompt},
                {"recursion_limit": args.recursion_limit},
            )
            vr = result.get("validation_report")
            rr = result.get("runtime_report")
            print(f"Validation Score  : {vr.consistency_score if vr else 'N/A'}")
            print(f"Validation Passed : {vr.is_valid if vr else 'N/A'}")
            print(f"Repair Cycles     : {result.get('metrics', {}).get('repairs', 0)}")
            if rr:
                print(f"Runtime Pass Rate : {rr.success_rate}%")
            sys.exit(0)

        user_prompt = input("Enter your system requirements: ")
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": args.recursion_limit},
        )

        print(f"\n✅ Final Compilation State : {result['status']}")

        vr = result.get("validation_report")
        if vr:
            print(f"   Consistency Score      : {vr.consistency_score}%")
            print(f"   Validation Passed      : {vr.is_valid}")

        rr = result.get("runtime_report")
        if rr:
            print(f"   Runtime Endpoints      : {rr.passed}/{rr.total_endpoints} passed ({rr.success_rate}%)")

        print(f"   Repair Cycles          : {result.get('metrics', {}).get('repairs', 0)}")

        rh = result.get("repair_history", [])
        if rh:
            print("\n   Repair History:")
            for entry in rh:
                print(f"     • {entry}")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
