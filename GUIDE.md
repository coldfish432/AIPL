# Model Self-Verification Before Human Review
# （模型先验证跑通，再交给人工审核）

## 1. Goal and Non-Goals

### Goal

The goal of this system is:

> **Before any code changes are presented to a human reviewer, the system MUST ensure that the code can actually run, build, or pass defined verification steps in a real execution environment.**

The model is required to:
- Generate code changes
- Trigger real verification runs
- Read and react to real execution results
- Iterate until verification passes or retry limits are reached

Only code that has **passed real execution-based verification** may be submitted for human review.

### Non-Goals

- The model is NOT trusted to determine correctness by reasoning alone.
- The model is NOT allowed to declare success without real execution.
- Business correctness, architectural quality, and long-term maintainability are still the responsibility of human reviewers.

---

## 2. Core Principle: Execution Is the Source of Truth

The system MUST follow this principle:

> **LLM reasoning is never the source of truth.  
> Real command execution (exit code + logs) is the source of truth.**

Implications:
- A change that “looks correct” but fails to build/test is considered a failure.
- A change that the model claims is correct but has not been executed is considered unverified.
- The model may only explain, debug, and fix based on execution results.

---

## 3. Role Separation

The pipeline MUST clearly separate responsibilities:

### Execution Engine (Verifier)

- Executes real commands locally or in a sandbox/container.
- Produces:
  - exit code
  - stdout / stderr (truncated if needed)
  - structured verification results
- Has final authority on pass/fail.

### LLM (Model / Codex)

- Proposes code changes.
- Proposes which verification commands to run (within constraints).
- Reads execution logs and fixes errors.
- Generates human-readable verification reports.
- **Must never self-certify success.**

### Human Reviewer

- Reviews only code that has already passed verification.
- Focuses on:
  - architecture
  - design quality
  - correctness beyond tests
  - maintainability and risk

---

## 4. Verification Levels (Signal Strength)

Verification signals are ranked by strength:

| Level | Signal Type                          | Requires Tests |
|------|--------------------------------------|----------------|
| L4   | Real test assertions (pytest, mvn test, jest) | Yes |
| L3   | Build / compile / startup             | No |
| L2   | Type checking / linting               | No |
| L1   | LLM self-reasoning                    | No (aux only) |

System requirement:
- The pipeline MUST reach **at least L3**.
- L1 signals alone are never sufficient.
- LLM reasoning is allowed only as a supplement.

---

## 5. Projects Without Tests Are Still Verifiable

A target project is NOT required to contain test code.

If no tests exist, the verifier MUST fall back to real executable checks such as:

- Python:
  - `python -m py_compile`
  - `python -m compileall`
  - minimal CLI smoke run (`--help`)
- Java:
  - `mvn package -DskipTests`
  - minimal application startup
- Node / UI:
  - `npm run build`
  - `tsc --noEmit`

At least one command MUST be:
- Executed
- Able to fail
- Checked via exit code

---

## 6. Command Discovery (Zero Configuration Support)

The system MUST NOT assume projects follow a predefined verification template.

Instead, it MUST implement **automatic command discovery**, including:

- Detect build systems:
  - `pom.xml`, `build.gradle`
  - `package.json`
  - `pyproject.toml`, `requirements.txt`
- Detect test frameworks:
  - `pytest.ini`, `tests/`
  - `src/test/java`
  - Jest/Vitest configs
- Extract executable commands:
  - `package.json` scripts
  - Maven / Gradle lifecycle commands
  - Standard language toolchains

Discovered capabilities MUST be exported as structured data (e.g. `capabilities.json`).

---

## 7. LLM Command Selection Rules

The LLM may participate in selecting verification commands ONLY under the following constraints:

- The LLM may choose commands ONLY from the discovered whitelist.
- The LLM may NOT invent new commands.
- The LLM must respect time / budget constraints (fast / PR / nightly).
- The LLM must include at least one hard-failure command (build/test).

The LLM output MUST be structured (e.g. JSON), never free-form text.

---

## 8. Mandatory Fallback and Escalation

To prevent missed failures:

- If no tests are discovered → run build + lint + smoke checks.
- If targeted tests pass but changes are high-risk → escalate to broader verification.
- If LLM cannot confidently choose → run the safest full verification.

The verifier has authority to override LLM choices.

---

## 9. Verification Loop (Required Behavior)

The pipeline MUST follow this loop:

1. LLM generates code changes.
2. Changes are applied to the workspace.
3. Verifier executes selected commands.
4. Results are recorded in a structured verification result.
5. If any command fails:
   - Logs are summarized.
   - LLM is asked to fix the issue.
   - The loop repeats.
6. Only when all required checks pass:
   - A final verification report is generated.
   - The result is eligible for human review.

---

## 10. Anti-Hallucination Hard Rules

The following rules are absolute:

1. The LLM may NOT declare success.
2. Success is defined only by verifier execution results.
3. Every failure MUST be backed by:
   - command
   - working directory
   - exit code
   - stderr/stdout evidence
4. If verification was not executed, the result is invalid.

---

## 11. Output Contract

The verifier MUST output a structured result, including:

- Overall status (success / failed)
- Executed commands
- Exit codes
- Error summaries
- Optional artifacts (reports, logs)

The human-facing UI MUST show:
- Code diff
- Verification summary
- Explicit confirmation that execution passed

---

## 12. Design Philosophy (Non-Negotiable)

> **The model is not trusted.  
> Execution is trusted.  
> Humans are the final authority.**

This system exists to:
- Eliminate low-level failures before human review
- Prevent LLM hallucination from reaching reviewers
- Make automated code generation safe, auditable, and boring

Any implementation that allows the model to bypass real execution
is considered incorrect.

---

## 13. Future Extensions (Out of Scope for Initial Implementation)

- Containerized multi-language runners
- Automatic smoke-test generation
- CodeGraph-driven test impact analysis
- Nightly full verification pipelines

These are optional extensions and MUST NOT weaken the guarantees above.
