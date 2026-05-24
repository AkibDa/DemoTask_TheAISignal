# main.py

import argparse
import sys
import traceback
from agent.graph import agent

def main():
    parser = argparse.ArgumentParser(description="Compiler-style App Generation System")
    parser.add_argument("--recursion-limit", "-r", type=int, default=100, help="Recursion limit")
    parser.add_argument("--benchmark", action="store_true", help="Run in benchmark evaluation mode")

    args = parser.parse_args()

    try:
        if args.benchmark:
            print("--- Running Deterministic Benchmark Mode ---")
            test_prompt = "Build a multi-tenant SaaS for managing gym memberships."
            result1 = agent.invoke({"user_prompt": test_prompt}, {"recursion_limit": args.recursion_limit})
            print(f"Benchmark Run 1 Validation Score: {result1['validation_report'].consistency_score}")
            sys.exit(0)

        user_prompt = input("Enter your system requirements: ")
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": args.recursion_limit}
        )
        print("\n✅ Final Compilation State:", result["status"])
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
