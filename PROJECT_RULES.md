# Project Rules — Antigravity IDE Setup

> Drop this file at the root of your project (e.g. `PROJECT_RULES.md` or `.antigravity/rules.md`).
> Antigravity agents read root-level markdown rule files as persistent context, so keep this
> file up to date as the source of truth for how the agent should behave in this repo.

---

## 1. Engineering Rule — Before Implementing Significant Features

Before starting any significant feature, the agent must:

1. **Read the project documentation** — README, `/docs`, existing ADRs/design notes.
2. **Inspect the relevant source files** — don't guess at structure; open and read the actual code.
3. **Understand existing architecture** — how modules/services/components are organized and why.
4. **Identify dependencies** — libraries, APIs, internal modules the feature will touch or rely on.
5. **Identify potential regressions** — what existing behavior could break, and how it will be verified.
6. **Create an implementation plan** — a short written plan (steps, files touched, risks) before writing code.

**Rule of thumb:** "Significant" = anything that touches more than one file, introduces a new
dependency, changes a public interface/API, or affects data/state handling. Trivial fixes
(typos, styling tweaks, one-line bug fixes) don't require the full sequence, but steps 2 and 5
still apply.

---

## 2. Project Priorities (in order)

When priorities conflict, resolve in this order — higher wins:

1. **Correctness** — the feature does what it's supposed to do, with no logic errors.
2. **Reliability** — it works consistently, not just on the happy path or once during testing.
3. **User experience** — it's understandable and usable by the person interacting with it.
4. **Security** — no obvious vulnerabilities, no leaked secrets, no unsafe input handling.
5. **Performance** — fast enough for the use case; don't over-optimize prematurely.
6. **Visual polish** — looks good, but never at the cost of the five priorities above.

> If a change makes something look better but risks correctness or reliability, don't make it —
> flag it instead.

---

## 3. Hackathon Requirements

The project **must**:

- [ ] Clearly solve the stated problem — the connection between problem and solution should be
      obvious to a judge in under a minute.
- [ ] Have a **working end-to-end flow** — no dead ends, no "this part is mocked" gaps in the
      core path.
- [ ] Have a **demonstrable MVP** — a minimum feature set that can be shown live, reliably.
- [ ] Have a **clear technical differentiator** — something that isn't just a CRUD wrapper or a
      thin API call; a reason this project is technically interesting.
- [ ] Be **visually polished** — consistent styling, no obviously broken layouts, no placeholder
      Lorem Ipsum in the demo path.
- [ ] Be **reliable during demonstration** — assume flaky wifi, cold starts, and edge-case input
      during the live demo; design for it.
- [ ] **Handle obvious failure cases** — empty states, invalid input, network errors, slow
      responses. Fail visibly and gracefully, never silently or with a raw stack trace on screen.

### Anti-goals

- **Do not add features simply to make the project appear complex.** Complexity for its own
  sake is a liability during a live demo and a red flag to judges.
- **Prefer features that strengthen the core problem-solution relationship** over features that
  are merely impressive in isolation. Every feature should answer: *"Does this make the core
  demo better, or is this a detour?"*

---

## 4. How the Agent Should Apply This in Antigravity IDE

- Treat this file as **binding context**, not a suggestion — re-read it before starting a new
  feature branch or task, especially after a long session where context may have drifted.
- When asked to build something ambiguous, **default to the smallest version that satisfies the
  hackathon requirements above**, then ask before expanding scope.
- Before marking a task "done," self-check it against the Hackathon Requirements checklist in
  Section 3 — not just "does it run," but "does it demo well."
- When priorities in Section 2 trade off against each other, state the trade-off explicitly in
  the implementation plan rather than silently picking one.
- Keep implementation plans short (a few bullet points is fine) but always produce one for
  anything non-trivial — this is a working artifact, not a formality.

---

## 5. Suggested Project Structure Check (fill in per-project)

| Item | Status |
|---|---|
| README with setup + run instructions | ☐ |
| One-command local run (`npm run dev` / `make run` / etc.) | ☐ |
| `.env.example` with all required env vars documented | ☐ |
| Core user flow has error handling on every network/API call | ☐ |
| Loading and empty states designed (not just happy path) | ☐ |
| Demo script / rehearsed happy path documented | ☐ |
