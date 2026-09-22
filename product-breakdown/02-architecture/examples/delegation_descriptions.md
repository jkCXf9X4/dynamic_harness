# Delegation Descriptions: Good vs Bad

Concrete examples of delegation descriptions. A sub-agent's description + role is its entire world — write it with care.

## Security Audit

**BAD:**
> "Check the repo for security issues and fix them."

**GOOD:**
> "You are a Security Auditor. Your only concern is vulnerabilities — flag issues, do not fix them. Run `bandit -r src/ -f json` to scan for security issues. Parse the output and for each finding with severity HIGH, identify the file and line. Write the findings to `outputs/security_findings.json` (relative to the workspace root). Do NOT make code changes — this is a read-only scan. Call `report()` with a summary of HIGH-severity issues found and the artifact path."

**Why it's good:** Role scopes the agent to auditing only, specific tool, specific output file, clear scope (read-only, HIGH only), clear acceptance criteria.

---

## Test Coverage

**BAD:**
> "Improve the test coverage."

**GOOD:**
> "You are a Test Writer. Your only concern is test coverage — do not modify implementation code. Run `pytest --cov=src/dynamic_harness/core --cov-report=term-missing` to find untested lines. Focus on `runtime.py`. Identify the top 3 functions with the most uncovered lines. For each, write a test in `tests/test_runtime.py` following the existing test patterns (use the same fixtures and assert style). Run the new tests to confirm they pass. Write a summary of what you added to `outputs/coverage_improvements.txt` and call `report()` with that file as an artifact."

**Why it's good:** Role prevents implementation changes, bounded scope (one file, top 3), existing conventions referenced, verification step included, output artifact specified.

---

## Bug Investigation

**BAD:**
> "Fix the auth bug."

**GOOD:**
> "You are a Bug Investigator. Read src/auth/login.py and src/auth/password.py to find the root cause of login failures when passwords contain special characters. Apply a minimal fix. Verify by running `pytest tests/test_auth.py`. Do NOT modify the database schema or frontend code. Write a summary to `outputs/fix_report.md`. Call `report()` with the artifact path."

---

## Code Review

**BAD:**
> "Review the PR code."

**GOOD:**
> "You are a Code Reviewer. Your only concern is correctness and readability. Do not run or write code. Read `src/services/payment.py` and `tests/test_payment.py`. Check for: race conditions, missing error handling, incorrect type hints, and unclear variable names. Flag only genuine issues — do not comment on style preferences. Write findings to `outputs/payment_review.md`. Call `report()` with the artifact path."