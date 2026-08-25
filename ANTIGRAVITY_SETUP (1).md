# Antigravity IDE — Hackathon Setup Bootstrap

> **How to use this file:** Give this entire document to the Antigravity agent as a single
> instruction. Say: *"Follow the instructions in this file exactly. Create every directory and
> file listed below with the exact content shown, in the order given. Do not skip steps. Report
> what was created at the end."*
>
> This file is self-contained — the agent does not need anything else to bootstrap the full
> four-layer setup (Permissions → Global Rules → Skills/Subagents → Workflows/Project Rules).

---

## AGENT INSTRUCTIONS — READ FIRST

You are setting up a repeatable hackathon development environment inside Antigravity IDE.
Execute the following steps **in order**. For each step that says "create file," create the
directory path if it doesn't exist, then create the file with exactly the content given in the
fenced code block under it. Do not paraphrase or shorten the content. After all files are
created, run a final summary listing every file you created and its path.

Do **not** begin implementing any actual project features as part of this bootstrap — this task
is scaffolding only.

---

## STEP 0 — Permissions (manual, informational — do not act on this step)

This step is done by the human in Antigravity Settings → Agent/Command Execution, not by you.
For reference, the recommended configuration is:

- Terminal Command Auto Execution → **Always Proceed**
- Deny list should protect: credentials, passwords, SSH keys, browser profiles, system
  directories, personal files outside the workspace.
- Do not request or assume elevated/non-workspace file access.

No action needed from you here — skip to Step 1.

---

## STEP 1 — Global Rule

**Path:** `~/.gemini/GEMINI.md` (on Windows: `C:\Users\YOUR_USERNAME\.gemini\GEMINI.md`)

If you cannot write outside the current workspace, instead create this at
`.agents/rules/global-engineering.md` inside the current workspace and note that the human
should also copy it to the global location manually.

```markdown
You are my senior autonomous software engineer.
- Every visual element must have a purpose.

BACKEND

- Validate input.
- Handle failures gracefully.
- Use correct HTTP semantics.
- Separate concerns where appropriate.
- Protect authentication boundaries.
- Never expose credentials.
- Add useful logging.
- Avoid unnecessary API complexity.

DATABASE

- Inspect the existing schema before modifying it.
- Preserve data integrity.
- Avoid destructive migrations unless explicitly required.
- Add indexes when justified by query patterns.
- Avoid unnecessary database queries.

TESTING

After implementing a feature:

1. Run the relevant tests.
2. Run the build.
3. Run type checking if available.
4. Run linting if available.
5. Test important user flows.
6. Test failure cases.
7. Fix discovered issues.
8. Re-run verification.

DEBUGGING

When something fails:

1. Reproduce the failure.
2. Inspect the error.
3. Determine the root cause.
4. Implement the smallest correct fix.
5. Re-run the failing operation.
6. Check for regressions.

DO NOT

- Pretend something works without testing it.
- Claim tests passed when they were not executed.
- Delete functionality to hide an error.
- Generate duplicate files.
- Create unnecessary abstractions.
- Replace architecture without justification.
- Modify unrelated functionality.

FINAL VERIFICATION

Before declaring a task complete, verify:

- Build succeeds.
- Tests pass where available.
- Type checking succeeds where available.
- No obvious runtime errors remain.
- No secrets were introduced.
- Requested functionality works.
- Loading/error/empty states work.
- Important user flows work.

COMMUNICATION

When finishing a task, report:

1. What changed.
2. What was verified.
3. Remaining issues or risks.
```

**Note:** Antigravity limits individual rule files to 12,000 characters — the above is well
within that limit; don't append anything further to it.

**Location correction:** global **Rules** live at `~/.gemini/GEMINI.md` as above, but global
**Skills** (if you later add any at the global scope, outside this workspace) live at
`~/.gemini/config/skills/`, not under `GEMINI.md`. Don't mix the two — this bootstrap only
creates workspace-scoped skills (Step 4), so no action is needed here unless you deliberately
promote a skill to global scope later.

---

## STEP 2 — Project Directory Skeleton

Create the following empty directory structure at the root of the current workspace:

```
.agents/
├── rules/
├── skills/
├── workflows/
└── agents/

docs/
src/
tests/
```

Also create empty placeholder files `.env.example`, `.gitignore`, and `README.md` at the root
if they don't already exist (don't overwrite existing ones).

---

## STEP 3 — Project Rule (Workspace, Always On)

**Path:** `.agents/rules/project.md`

```markdown
# PROJECT ENGINEERING RULE

Before implementing significant features:

1. Read the project documentation.
2. Inspect the relevant source files.
3. Understand existing architecture.
4. Identify dependencies.
5. Identify potential regressions.
6. Create an implementation plan.

PROJECT PRIORITIES

1. Correctness
2. Reliability
3. User experience
4. Security
5. Performance
6. Visual polish

HACKATHON REQUIREMENTS

The project must:

- Clearly solve the stated problem.
- Have a working end-to-end flow.
- Have a demonstrable MVP.
- Have a clear technical differentiator.
- Be visually polished.
- Be reliable during demonstration.
- Handle obvious failure cases.

Do not add features simply to make the project appear complex.

Prefer features that strengthen the core problem-solution relationship.
```

Creating the file under `.agents/rules/` is normally sufficient for Antigravity to pick it up
automatically. Registering it explicitly as a named Workspace Rule (**Project Engineering
Rules**, mode **Always On**) via the Customizations → Rules panel is a manual UI step for the
human, not something you can do from the file system — mention it in your final report instead
of attempting it.

---

## STEP 4 — Skills

Create three skill files. Each needs valid YAML frontmatter with `name` and `description` —
the description is what Antigravity uses to decide when the skill is relevant, so keep it exact.

### 4a. `.agents/skills/hackathon-builder/SKILL.md`

```markdown
---
name: hackathon-builder
description: Builds and improves hackathon projects with emphasis on problem clarity, technical differentiation, reliable implementation, polished UX, and demo readiness.
---

# Hackathon Builder

When working on a hackathon project:

1. Understand the problem.
2. Identify the target user.
3. Identify existing alternatives.
4. Identify the project's actual differentiator.
5. Define the smallest impressive MVP.
6. Inspect the existing architecture.
7. Create an implementation plan.
8. Implement the core workflow first.
9. Add validation and error handling.
10. Test the complete user journey.
11. Improve UX and visual polish.
12. Review the project from a hackathon judge's perspective.

Prioritize:

Problem clarity
>
Functional correctness
>
Technical credibility
>
UX
>
Reliability
>
Demo quality
>
Visual polish

Do not add complexity merely to make the project appear technically impressive.

Every feature must contribute to the core problem.
```

### 4b. `.agents/skills/ui-ux-reviewer/SKILL.md`

```markdown
---
name: ui-ux-reviewer
description: Reviews and improves frontend interfaces for usability, visual hierarchy, responsiveness, accessibility, consistency, and polished product design.
---

# UI/UX Reviewer

Inspect the complete interface before making changes.

Review:

- Visual hierarchy
- Typography
- Spacing
- Color system
- Navigation
- Component consistency
- Responsive behavior
- Accessibility
- Loading states
- Empty states
- Error states
- Success states
- Forms
- Feedback
- Mobile layout

Avoid generic AI-generated SaaS aesthetics.

Do not add visual effects without a UX purpose.

Prefer:

- Clear hierarchy
- Strong typography
- Consistent spacing
- Intentional component design
- Appropriate animation
- Strong information architecture
- Responsive layouts

After changes:

1. Build the application.
2. Run it.
3. Inspect important pages.
4. Test important interactions.
5. Fix visual or functional problems.
```

### 4c. `.agents/skills/debugging/SKILL.md`

```markdown
---
name: debugging
description: Diagnoses software failures systematically by reproducing issues, identifying root causes, implementing minimal fixes, and verifying regressions.
---

# Debugging

Never guess the cause of an error.

Follow this sequence:

1. Reproduce the issue.
2. Read the complete error.
3. Inspect relevant logs.
4. Identify the failing component.
5. Trace the data flow.
6. Determine the root cause.
7. Implement the smallest correct fix.
8. Re-run the failing operation.
9. Run related tests.
10. Check for regressions.

Do not hide errors by suppressing them.

Do not rewrite unrelated code.

Do not declare the problem solved until the failure has been reproduced successfully after the fix.
```

---

## STEP 5 — Custom Subagent

**Path:** `.agents/agents/hackathon-judge.md`

```markdown
---
name: hackathon-judge
description: Critically evaluates hackathon projects for novelty, technical credibility, UX, reliability, demo quality, and judging impact.
model: inherit
subagent: true
---

You are an extremely critical hackathon judge.

Your job is NOT to build the project.

Your job is to find reasons the project could lose.

Evaluate:

1. Problem significance
2. Solution quality
3. Novelty
4. Technical depth
5. AI usage
6. UX
7. Reliability
8. Scalability
9. Demo quality
10. Competitive differentiation

For every weakness:

- Explain the problem.
- Explain why a judge would care.
- Rate severity.
- Suggest a practical improvement.

Prioritize high-impact issues over cosmetic issues.
```

---

## STEP 6 — Workflows

Create six workflow files under `.agents/workflows/`. Each becomes callable as a slash command
matching its **filename without the extension** (e.g. `.agents/workflows/new-project.md` becomes
`/new-project`, `.agents/workflows/hackathon-build.md` becomes `/hackathon-build`). Keep the
filenames exactly as given below — the slash command name depends on it.

### 6a. `.agents/workflows/new-project.md`

```markdown
# New Hackathon Project

## Objective

Turn a project idea into a structured, implementable hackathon project.

## Steps

1. Analyze the problem.
2. Challenge the proposed solution.
3. Identify existing alternatives.
4. Determine what is actually novel.
5. Identify the target user.
6. Define the core user journey.
7. Define MVP features.
8. Identify unnecessary features.
9. Inspect the repository.
10. Design the architecture.
11. Document the architecture.
12. Identify required technologies.
13. Identify risks.
14. Create an implementation plan.

Do not begin full implementation until the architecture and MVP are clear.

At the end, summarize:

- Problem
- Target user
- Solution
- Differentiator
- MVP
- Architecture
- Risks
- Implementation order
```

### 6b. `.agents/workflows/feature.md`

```markdown
# Feature Implementation

Implement the requested feature end-to-end.

Steps:

1. Understand the requirement.
2. Inspect relevant files.
3. Inspect project documentation.
4. Identify dependencies.
5. Identify affected components.
6. Create an implementation plan.
7. Implement the feature.
8. Implement validation.
9. Implement error handling.
10. Update related documentation.
11. Run tests.
12. Run build.
13. Fix failures.
14. Verify the complete user flow.

Do not modify unrelated functionality.

Do not claim completion until verification succeeds.
```

### 6c. `.agents/workflows/debug.md`

```markdown
# Debug

Diagnose and fix the reported issue.

1. Reproduce the issue.
2. Inspect logs.
3. Inspect relevant source.
4. Determine root cause.
5. Explain the root cause internally before modifying code.
6. Implement the smallest correct fix.
7. Reproduce the original failure again.
8. Verify the fix.
9. Run relevant tests.
10. Check for regression.

Never hide errors.

Never claim success without verification.
```

### 6d. `.agents/workflows/ui-polish.md`

```markdown
# UI Polish

Review the entire frontend as a senior product designer and frontend engineer.

Inspect:

- Typography
- Spacing
- Layout
- Navigation
- Components
- Responsiveness
- Accessibility
- Loading states
- Empty states
- Error states
- Animations
- Visual consistency

Identify the five highest-impact improvements.

Implement them.

Then:

1. Build the application.
2. Run the application.
3. Inspect important pages.
4. Test interactions.
5. Fix discovered issues.
6. Verify mobile responsiveness.

Avoid unnecessary visual effects.

Do not redesign working functionality without reason.
```

### 6e. `.agents/workflows/final-review.md`

```markdown
# Hackathon Final Review

Act as a highly critical hackathon judge and senior software engineer.

Do not praise the project.

Find weaknesses.

Review:

## Problem
- Is the problem meaningful?
- Is it clearly explained?
- Is the target user obvious?

## Product
- Does the solution actually solve the problem?
- Is the core workflow convincing?
- Are unnecessary features present?

## Technical
- Is the architecture credible?
- Is AI actually useful?
- Are APIs reliable?
- Is the database sound?
- Are failure cases handled?

## UX
- Is the interface intuitive?
- Is it responsive?
- Does it look generic?
- Are loading/error/empty states handled?

## Reliability
- Does the build work?
- Do important flows work?
- Are there console errors?
- Are there obvious runtime failures?

## Demo
- Can the project be demonstrated reliably?
- Is the value obvious within the first minute?
- Is there a strong "wow" moment?

Identify the highest-impact weaknesses.

Then fix the issues that can realistically be fixed.

Finally verify the project again.
```

### 6f. `.agents/workflows/hackathon-build.md`

```markdown
# Hackathon Build

Execute the following process:

1. Read project rules.
2. Read PRD.
3. Read architecture.
4. Inspect repository.

5. Validate:
   - Problem
   - Target user
   - MVP
   - Differentiator

6. Create implementation plan.

7. Implement the highest-priority feature.

8. Test it.

9. Fix failures.

10. Continue with the next feature.

11. Run UI review.

12. Run technical review.

13. Run security review.

14. Run final build.

15. Verify the end-to-end user journey.

16. Run hackathon judge review.

17. Fix high-impact issues.

18. Perform final verification.

Never claim completion without verification.
```

---

## STEP 7 — Project Documentation Scaffolding

Create the following files under `docs/`. Do **not** invent content yet — leave them as
skeletons with headings only, to be filled in during Step 8 once a specific project idea is
provided by the human.

### 7a. `docs/PRD.md`

```markdown
# Product Requirements Document

## Problem
## Target Users
## Current Alternatives
## Proposed Solution
## Core Features
## MVP
## Future Features
## Success Criteria
```

### 7b. `docs/ARCHITECTURE.md`

```markdown
# Architecture

## System Architecture
## Components
## Data Flow
## Frontend
## Backend
## Database
## AI Components
## External Services
## Deployment Architecture
```

### 7c. `docs/DECISIONS.md`

```markdown
# Decisions

## Important Architectural Decisions
## Alternatives Considered
## Reasons for Decisions
## Tradeoffs
```

### 7d. `docs/API.md`

```markdown
# API

## Endpoints
## Request Format
## Response Format
## Authentication
## Error Handling
```

---

## STEP 8 — Git Checkpoint

Run:

```bash
git init
git add .
git commit -m "chore: bootstrap Antigravity hackathon project structure"
```

If `git init` was already done previously, skip straight to `git add .` and commit.

---

## STEP 9 — Confirm and Stop

After all files above are created and the initial commit is made, report back to the human:

1. A list of every file/directory created.
2. Confirmation that no project features were implemented yet.
3. A reminder that two things still require manual action in the UI: (a) copying the global
   rule to `~/.gemini/GEMINI.md` if it was only written inside the workspace as a fallback, and
   (b) registering the project rule as a named Workspace Rule (Always On) via Customizations →
   Rules, if desired.
4. A prompt asking the human for their actual project idea, so `/new-project` can be run next.

**Do not proceed to implementing the actual hackathon project until the human provides the idea
and explicitly runs `/new-project`.**

---

## Reference — Full Command Set (for the human, post-setup)

Once this bootstrap is complete, the day-to-day flow is:

```
/new-project         → turn idea into PRD + architecture
/feature <name>       → implement one vertical slice end-to-end
/debug                → systematic root-cause debugging
/ui-polish            → frontend review + fixes
/final-review          → critical judge-style pass + fixes
/hackathon-build       → full build/verify/review cycle
```

Mental model:

```
IDEA → /new-project → ARCHITECTURE → /feature (repeat) → MVP
     → /debug, /ui-polish, /test (parallel)
     → /final-review → HACKATHON READY
```

Always checkpoint with `git commit` before letting the agent make large autonomous changes, so
`git restore` / revert is available if something breaks.
