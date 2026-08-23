"""
Pytest wrapper for the evaluation suite.
Allows running evaluations via `pytest evaluation/` with proper test discovery.
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.eval_runner import run_case, check_assertion
from src.agent.agent import SupportAgent

# Load test cases
EVAL_DIR = Path(__file__).parent
VISIBLE_CASES = json.loads((EVAL_DIR / "visible-cases.json").read_text())
CUSTOM_CASES = json.loads((EVAL_DIR / "custom-cases.json").read_text())
ALL_CASES = VISIBLE_CASES + CUSTOM_CASES

# Create a shared agent instance for efficiency
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


@pytest.fixture(scope="session")
def agent():
    return get_agent()


# Generate parameterized test cases
@pytest.mark.parametrize(
    "case",
    ALL_CASES,
    ids=[c["id"] for c in ALL_CASES],
)
def test_eval_case(case, agent):
    """Run a single evaluation case and assert all checks pass."""
    result = run_case(agent, case)
    
    # Collect all failure messages
    failures = []
    for assertion in result.assertions:
        if not assertion.passed:
            failures.append(
                f"  [{assertion.assertion_type}] {assertion.description}\n"
                f"    Expected: {assertion.expected}\n"
                f"    Got: {assertion.actual_snippet[:200]}"
            )
    
    if result.error:
        failures.append(f"  Error: {result.error}")
    
    if failures:
        failure_msg = (
            f"\n{'='*60}\n"
            f"Case: {case['id']} ({case['category']})\n"
            f"Description: {case['description']}\n"
            f"Response: {result.response[:300]}...\n"
            f"Tool calls: {[tc.get('name') for tc in result.tool_calls]}\n"
            f"Failed assertions:\n" + "\n".join(failures)
        )
        pytest.fail(failure_msg)
