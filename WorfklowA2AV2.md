
--- START OF FILE WorkflowA2Av2.md ---

# AgentVault Workflow v2 (WorkflowA2Av2) - Manual Collaboration

This document outlines the **Manual Collaboration Workflow (WorkflowA2Av2)** using provided scripts, tailored for developing AgentVault *without* a fully automated loop, but leveraging its core ideas and scripts. This version incorporates a Cloud AI pre-processing step to optimize context provision.

**Goal:** Structure our manual interaction to maximize efficiency and minimize errors, leveraging helper scripts for context preparation and file extraction, while managing context window size effectively.

**Core Principle:** You drive the process, execute all actions (including Cloud AI summary generation), and provide structured context/feedback to me. I generate code/tests/docs based on your inputs.

---

**WorkflowA2Av2 - Manual Collaboration Steps**

**(Preparation Phase - Done Once & Periodically)**

1.  **Finalize Requirements:** Ensure detailed phase requirements (e.g., Phase 2.1, 2.2, 2.2.1) are clear and accessible in dedicated documents.
2.  **Setup Project Structure:** Manually create initial directories for components, shared tests, etc. Initialize Git.
3.  **Prepare Helper Scripts:** Ensure `compile_project_to_text.py` and `extract_and_write_files.py` are functional. `compile_project_to_text.py` will be used for gathering *focused component* context. `extract_and_write_files.py` is used for applying my output.
4.  **(NEW) Generate Initial Project Overview Summary (You + Cloud AI):**
    *   **Action:** Feed the *entire current project codebase* (all components) to your chosen Cloud AI.
    *   **Prompt (Example):** "Analyze this Python monorepo codebase ('AgentVault'). Provide a detailed, structured summary suitable for another AI assistant (like Claude 3 Opus) to quickly understand the project's overall architecture, the purpose and key functionalities of each main component (`agentvault_library`, `agentvault_registry`, `agentvault_cli`, `agentvault_server_sdk`, etc.), the core technologies used (FastAPI, SQLAlchemy, Click, Pydantic, Poetry, etc.), the main data models (AgentCard, Task, Developer, etc.), and the key interactions *between* the components. Focus on technical details, interfaces, and dependencies relevant for understanding how to modify or add features. Avoid generic descriptions; prioritize specific class names, key methods, API routes, and data flow."
    *   **Action:** Review/refine the Cloud AI's output for accuracy and technical depth.
    *   **Output:** Save the summary to `temp/project_overview_summary.txt`.
    *   **Frequency:** Regenerate this summary periodically, especially after significant architectural changes or adding new components.

**(Development Cycle - Repeat for Each Logical Feature/Requirement Group)**

**Step 1: Define Work Unit (You)**

*   **Action:** Select the next logical requirement(s) or task to implement from the detailed phase requirements document. Define a clear, specific goal.
*   **Output:** A clear statement of the immediate goal (e.g., "Implement REQ-SDK-PKG-002: Generate standardized multi-stage Dockerfile").

**Step 2: Gather Focused Context (You)**

*   **Action:** Use `scripts/compile_project_to_text.py` (or similar) configured to gather the current state of code files **only within the target component(s)** relevant to the current Work Unit (e.g., only files in `agentvault_server_sdk/src/agentvault_server_sdk/packager/` if implementing packaging).
*   **Output:** Save this focused code context to `temp/component_context.txt`.
*   **Action:** Retrieve the latest `temp/project_overview_summary.txt` (from Preparation Step 4).
*   **Action:** Extract the specific, detailed requirement text for the current Work Unit.
*   **Output:** `temp/component_context.txt`, `temp/project_overview_summary.txt`, Text snippet of specific requirements.

**Step 3: Request Code Generation (You -> Me)**

*   **Action:** Provide me with the information using the revised **Plate A2v: Code Generation Request**.
*   **Input (from You):** See Plate A2v details below.
*   **Output (from Me):** Code snippets formatted with `--- START/END OF FILE ---` markers, potentially including new files (`CREATE_FILE`) and modifications to existing ones.

**Step 4: Apply Generated Code (You)**

*   **Action:** Copy my *entire* response containing the code blocks. Save it to a temporary file (e.g., `temp/ai_output.txt`).
*   **Action:** Run `scripts/extract_and_write_files.py temp/ai_output.txt .` (adjust project root if needed) to apply the changes to your local codebase. Review the script's output.
*   **Output:** Modified local code files within the target component(s).

**Step 5: Execute & Test (You)**

*   **Action:** Run relevant checks against the modified code:
    *   Static Analysis (e.g., `ruff check .` within the component directory).
    *   Unit Tests (e.g., `pytest` within the component directory or targeting specific new test files).
    *   (Later) Integration Tests.
*   **Output:** Test results, linting errors, tracebacks, console output.

**Step 6A: Success - Review & Commit (You)**

*   **Action:** If all checks pass:
    *   Manually review the code changes (`git diff`).
    *   If satisfied, stage changes (`git add .`) and commit (`git commit -m "Implement REQ-XXX / Task X.Y.Z: Feature description"`).
    *   Return to Step 1 for the next Work Unit.

**Step 6B: Failure - Request Debugging/Correction (You -> Me)**

*   **Action:** If checks fail:
    *   Gather the **exact** error messages, tracebacks, and test failure summaries.
    *   Re-gather the **current focused code context** (including the just-applied, failing code within the relevant component) using `compile_project_to_text.py` -> `temp/component_context.txt`.
    *   Retrieve the latest `temp/project_overview_summary.txt`.
    *   Extract the specific requirement text again.
    *   Provide this information to me using the revised **Plate B2v: Debugging Request**.
*   **Input (from You):** See Plate B2v details below.
*   **Output (from Me):** Corrected code snippets formatted with `--- START/END OF FILE ---` markers.
*   **Action (You):** Return to Step 4 (Apply Generated Code) with the corrected code. Repeat the cycle until tests pass.

---

**Communication Plates v2 (Templates for You to Provide Me)**

**Plate A2v: Code Generation Request**

```text
**ACTION_REQUESTED:** Generate Code

**WORK_UNIT_GOAL:** [Clear description of the immediate goal, e.g., "Implement REQ-SDK-PKG-002: Generate standardized multi-stage Dockerfile"]

**TARGET_COMPONENT(S):** [Specify component key(s), e.g., "server-sdk"]

**PROJECT_OVERVIEW_SUMMARY:**
```text
[Paste the ENTIRE content of temp/project_overview_summary.txt generated by Cloud AI]
```

**RELEVANT_REQUIREMENTS:**
```markdown
[Paste the EXACT, DETAILED requirement text(s) relevant to this goal]
```

**CURRENT_TARGET_CODE_CONTEXT:**
```text
[Paste the ENTIRE content of temp/component_context.txt containing ONLY the code for the TARGET_COMPONENT(S)]
```

**SPECIFIC_INSTRUCTIONS (Optional):**
[Add any specific guidance, e.g., "Use python:3.11-slim-bookworm as the base image.", "Ensure the generated Dockerfile uses a non-root user."]
```

**Plate B2v: Debugging Request**

```text
**ACTION_REQUESTED:** Debug Code / Fix Errors

**WORK_UNIT_GOAL:** [Same goal as the initial generation request, e.g., "Implement REQ-SDK-PKG-002: Generate standardized multi-stage Dockerfile"]

**TARGET_COMPONENT(S):** [Specify component key(s), e.g., "server-sdk"]

**FAILED_STEP:** [Describe what failed, e.g., "Unit Tests", "Docker build"]

**ERROR_OUTPUT / TEST_FAILURE_DETAILS:**
```text
[Paste the EXACT, COMPLETE error message, traceback, pytest summary, or Docker build output]
```

**PROJECT_OVERVIEW_SUMMARY:**
```text
[Paste the ENTIRE content of temp/project_overview_summary.txt]
```

**RELEVANT_REQUIREMENTS:**
```markdown
[Paste the EXACT, DETAILED requirement text(s) again for context]
```

**CURRENT_TARGET_CODE_CONTEXT (Including Failing Code):**
```text
[Paste the ENTIRE, UP-TO-DATE content of temp/component_context.txt for the TARGET_COMPONENT(S)]
```

**SPECIFIC_INSTRUCTIONS (Optional):**
[Add context if helpful, e.g., "The error seems related to file permissions in the Docker runtime stage.", "Focus on the CMD line in the Dockerfile."]

**PREVIOUS_AI_OUTPUT_THAT_FAILED (Optional but helpful):**
```text
[If easily available, paste the --- START/END OF FILE --- blocks from my *previous* response that led to this error]
```
```

---

**Benefits of WorkflowA2Av2:**

*   **Structure & Clarity:** Maintains the clear, repeatable process and plate structure.
*   **Optimized Context:** Provides focused code context for specific tasks while retaining global project awareness via the summary.
*   **Efficiency:** Reduces the amount of code context transferred in each request, saving time and potentially avoiding context window limitations.
*   **Leverages Tools:** Continues to effectively use your helper scripts (`compile_project_to_text.py` for focused context, `extract_and_write_files.py`) alongside the Cloud AI for summarization.

--- END OF FILE WorkflowA2Av2.md ---