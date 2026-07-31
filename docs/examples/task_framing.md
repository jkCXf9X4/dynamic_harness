# Task Framing: Root-Level Tasks

The quality of the root task description directly determines the entire agent tree's behavior. A vague root task produces wandering agents; a precise root task produces focused, verifiable output.

## Principles

1. **Be specific about scope** — What codebase? What directory? What problem?
2. **State the desired outcome** — What should exist or be true when done?
3. **Specify format** — How should the final report be structured?
4. **Set boundaries** — What should NOT be changed or investigated?
5. **Provide context** — File paths, conventions, constraints the agents can't discover

## Example

**BAD:**
> "Fix the bugs in my project."

**GOOD:**
> "The user reports that login fails with a 500 error when the password contains special characters. Investigate `src/auth/login.py` and `src/auth/password.py` to find the root cause. Apply a minimal fix. Verify by running `pytest tests/test_auth.py`. Do NOT modify the database schema or frontend code. Write a summary to `/tmp/fix_report.md`."

---

## Report Structure

A good `report()` call makes the parent's job of verification and synthesis straightforward.

```
report(
    summary="[1–2 sentences summarizing the concrete finding or change]. "
             "Verified by: [how]. Artifacts written: [files].",
    artifact_ids=["/tmp/analysis_results.json", "/tmp/changes_summary.txt"]
)
```

### Report Quality Checklist

- **Concrete, not abstract:** "Added `expiry_check()` to auth.py, 3 tests pass" not "Improved auth security"
- **Self-verifying:** Include the verification method (e.g., "Confirmed via pytest")
- **Artifact-referenced:** Every output file is listed in `artifact_ids`
- **One topic:** The report covers the sub-task, nothing else
- **No fabrication:** Every claim is backed by actual tool output or artifact content