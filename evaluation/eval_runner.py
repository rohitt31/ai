"""
Evaluation suite for the Aster & Row support agent.
Runs visible and custom test cases, reports per-case and per-category results.
Uses deterministic assertions (regex, substring, tool call checks) — not LLM-as-judge.
"""

import json
import re
import sys
import os
import time
from pathlib import Path
from dataclasses import dataclass, field

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.agent import SupportAgent


@dataclass
class AssertionResult:
    """Result of a single assertion check."""
    assertion_type: str
    expected: str
    passed: bool
    description: str
    actual_snippet: str = ""


@dataclass
class CaseResult:
    """Result of a single test case."""
    case_id: str
    category: str
    description: str
    passed: bool
    assertions: list[AssertionResult] = field(default_factory=list)
    response: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    error: str = ""
    duration_ms: int = 0


def check_assertion(assertion: dict, response: str, tool_calls: list[dict]) -> AssertionResult:
    """
    Check a single assertion against the response and tool calls.
    Supports assertion types: contains, not_contains, contains_any, 
    source_cited, tool_called, tool_not_called, regex.
    """
    a_type = assertion["type"]
    description = assertion.get("description", "")
    
    response_lower = response.lower()
    
    if a_type == "contains":
        value = assertion["value"]
        passed = value.lower() in response_lower
        return AssertionResult(
            assertion_type=a_type,
            expected=value,
            passed=passed,
            description=description,
            actual_snippet=response[:200],
        )
    
    elif a_type == "not_contains":
        value = assertion["value"]
        passed = value.lower() not in response_lower
        return AssertionResult(
            assertion_type=a_type,
            expected=f"NOT '{value}'",
            passed=passed,
            description=description,
            actual_snippet=response[:200],
        )
    
    elif a_type == "contains_any":
        values = assertion["values"]
        passed = any(v.lower() in response_lower for v in values)
        return AssertionResult(
            assertion_type=a_type,
            expected=f"any of {values}",
            passed=passed,
            description=description,
            actual_snippet=response[:200],
        )
    
    elif a_type == "source_cited":
        value = assertion["value"]
        # Check if the source filename appears in the response
        passed = value.lower() in response_lower or value.replace(".md", "").lower().replace("-", " ") in response_lower
        # Also check common citation patterns
        if not passed:
            # Check for partial filename matches (e.g., "returns-policy-current" or "Returns Policy")
            stem = Path(value).stem
            # Remove leading number prefix like "01-"
            clean_stem = re.sub(r'^\d+-', '', stem).replace('-', ' ')
            passed = clean_stem.lower() in response_lower or stem.lower() in response_lower
        return AssertionResult(
            assertion_type=a_type,
            expected=f"source: {value}",
            passed=passed,
            description=description,
            actual_snippet=response[:300],
        )
    
    elif a_type == "tool_called":
        value = assertion["value"]
        tool_names = [tc.get("name", "") for tc in tool_calls]
        passed = value in tool_names
        return AssertionResult(
            assertion_type=a_type,
            expected=f"tool call: {value}",
            passed=passed,
            description=description,
            actual_snippet=f"Tool calls: {tool_names}",
        )
    
    elif a_type == "tool_not_called":
        value = assertion["value"]
        tool_names = [tc.get("name", "") for tc in tool_calls]
        passed = value not in tool_names
        return AssertionResult(
            assertion_type=a_type,
            expected=f"NO tool call: {value}",
            passed=passed,
            description=description,
            actual_snippet=f"Tool calls: {tool_names}",
        )
    
    elif a_type == "regex":
        pattern = assertion["value"]
        passed = bool(re.search(pattern, response, re.IGNORECASE))
        return AssertionResult(
            assertion_type=a_type,
            expected=f"regex: {pattern}",
            passed=passed,
            description=description,
            actual_snippet=response[:200],
        )
    
    else:
        return AssertionResult(
            assertion_type=a_type,
            expected="unknown",
            passed=False,
            description=f"Unknown assertion type: {a_type}",
        )


def run_case(agent: SupportAgent, case: dict) -> CaseResult:
    """Run a single evaluation case through the agent."""
    case_id = case["id"]
    category = case.get("category", "general")
    description = case.get("description", case_id.replace("-", " ").capitalize())
    
    # Handle turns vs messages
    turns = case.get("turns") or case.get("messages", [])
    
    # Convert 'expect' block to assertions if assertions not explicitly present
    assertions = case.get("assertions", [])
    if not assertions and "expect" in case:
        expect = case["expect"]
        for item in expect.get("must_include", []):
            assertions.append({
                "type": "contains",
                "value": item,
                "description": f"Must mention '{item}'"
            })
        for item in expect.get("must_not_include", []):
            assertions.append({
                "type": "not_contains",
                "value": item,
                "description": f"Must not mention '{item}'"
            })
        for src in expect.get("required_sources", []):
            assertions.append({
                "type": "source_cited",
                "value": src,
                "description": f"Must cite source '{src}'"
            })
        for forbidden in expect.get("forbidden_sources_as_authority", []):
            assertions.append({
                "type": "not_contains",
                "value": forbidden,
                "description": f"Must not rely on forbidden source '{forbidden}'"
            })
        if expect.get("tool") == "not_called":
            assertions.append({
                "type": "tool_not_called",
                "value": "lookup_order",
                "description": "Order lookup tool must not be called"
            })
        elif expect.get("tool") == "lookup_order" or expect.get("tool") == "called":
            assertions.append({
                "type": "tool_called",
                "value": "lookup_order",
                "description": "Order lookup tool must be called"
            })
        if expect.get("handoff") is True:
            assertions.append({
                "type": "contains_any",
                "values": ["support@asterandrow.com", "1-800-555-ASTER", "support team", "support specialist"],
                "description": "Must recommend human handoff"
            })
    
    # Create a unique session for this case
    session_id = f"eval-{case_id}"
    agent.reset_session(session_id)
    
    start_time = time.time()
    
    try:
        # Process all turns
        response = ""
        all_tool_calls = []
        
        for turn in turns:
            if turn.get("role") == "user":
                response = agent.chat(turn.get("content", ""), session_id)
                all_tool_calls.extend(agent.get_last_tool_calls())
                time.sleep(1.5)  # Respect API rate limits between turns
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Check assertions against the LAST response
        assertion_results = []
        for assertion in assertions:
            result = check_assertion(assertion, response, all_tool_calls)
            assertion_results.append(result)
        
        all_passed = all(a.passed for a in assertion_results)
        
        return CaseResult(
            case_id=case_id,
            category=category,
            description=description,
            passed=all_passed,
            assertions=assertion_results,
            response=response,
            tool_calls=all_tool_calls,
            duration_ms=duration_ms,
        )
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return CaseResult(
            case_id=case_id,
            category=category,
            description=description,
            passed=False,
            error=str(e),
            duration_ms=duration_ms,
        )
    finally:
        agent.reset_session(session_id)


def print_results(results: list[CaseResult]) -> None:
    """Print formatted evaluation results."""
    print("\n" + "=" * 80)
    print("ASTER & ROW SUPPORT AGENT — EVALUATION RESULTS")
    print("=" * 80)
    
    # Individual results
    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{status} [{result.category}] {result.case_id}: {result.description}")
        print(f"    Duration: {result.duration_ms}ms")
        
        if result.error:
            print(f"    ⚠️  Error: {result.error}")
        
        for assertion in result.assertions:
            a_status = "  ✓" if assertion.passed else "  ✗"
            print(f"    {a_status} {assertion.description}")
            if not assertion.passed:
                print(f"      Expected: {assertion.expected}")
                print(f"      Got: {assertion.actual_snippet[:150]}...")
    
    # Category summary
    print("\n" + "-" * 80)
    print("CATEGORY SUMMARY")
    print("-" * 80)
    
    categories: dict[str, dict] = {}
    for result in results:
        cat = result.category
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if result.passed:
            categories[cat]["passed"] += 1
    
    for cat, counts in sorted(categories.items()):
        pct = (counts["passed"] / counts["total"] * 100) if counts["total"] > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {cat:20s} {bar} {counts['passed']}/{counts['total']} ({pct:.0f}%)")
    
    # Overall
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pct = (passed / total * 100) if total > 0 else 0
    
    print("\n" + "=" * 80)
    print(f"OVERALL: {passed}/{total} cases passed ({pct:.0f}%)")
    print("=" * 80)


def save_results(results: list[CaseResult], output_path: Path) -> None:
    """Save evaluation results to a JSON file."""
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_cases": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "cases": [],
    }
    
    for result in results:
        case_data = {
            "case_id": result.case_id,
            "category": result.category,
            "description": result.description,
            "passed": result.passed,
            "duration_ms": result.duration_ms,
            "error": result.error,
            "response": result.response[:500],
            "tool_calls": [{"name": tc.get("name"), "args": tc.get("arguments")} for tc in result.tool_calls],
            "assertions": [
                {
                    "type": a.assertion_type,
                    "expected": a.expected,
                    "passed": a.passed,
                    "description": a.description,
                }
                for a in result.assertions
            ],
        }
        output["cases"].append(case_data)
    
    # Category breakdown
    categories: dict[str, dict] = {}
    for result in results:
        cat = result.category
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if result.passed:
            categories[cat]["passed"] += 1
    
    output["categories"] = categories
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the evaluation suite")
    parser.add_argument("--cases", nargs="*", help="Specific case IDs to run (default: all)")
    parser.add_argument("--category", help="Run only cases in this category")
    parser.add_argument("--output", default="evaluation/results.json", help="Output file for results")
    parser.add_argument("--visible-only", action="store_true", help="Run only visible cases")
    parser.add_argument("--custom-only", action="store_true", help="Run only custom cases")
    args = parser.parse_args()
    
    eval_dir = Path(__file__).parent
    
    # Load test cases
    all_cases = []
    
    if not args.custom_only:
        visible_path = eval_dir / "visible-cases.json"
        if visible_path.exists():
            with open(visible_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cases = data["cases"] if isinstance(data, dict) and "cases" in data else data
                all_cases.extend(cases)
            print(f"Loaded {len(cases)} visible cases")
    
    if not args.visible_only:
        custom_path = eval_dir / "custom-cases.json"
        if custom_path.exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom = data["cases"] if isinstance(data, dict) and "cases" in data else data
                all_cases.extend(custom)
            print(f"Loaded {len(custom)} custom cases")
    
    # Filter
    if args.cases:
        all_cases = [c for c in all_cases if c["id"] in args.cases]
    if args.category:
        all_cases = [c for c in all_cases if c["category"] == args.category]
    
    if not all_cases:
        print("No cases to run.")
        return
    
    print(f"\nRunning {len(all_cases)} evaluation cases...\n")
    
    # Create agent
    agent = SupportAgent()
    
    # Run cases
    results = []
    for i, case in enumerate(all_cases, 1):
        print(f"  [{i}/{len(all_cases)}] Running {case['id']}...", end="", flush=True)
        result = run_case(agent, case)
        results.append(result)
        status = "✅" if result.passed else "❌"
        print(f" {status} ({result.duration_ms}ms)")
        time.sleep(1)
    
    # Print and save results
    print_results(results)
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_results(results, output_path)
    
    # Exit with non-zero if any failures
    if any(not r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
