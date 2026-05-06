# ADR 0012: Claude Code Subagents for the Build Swarm

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

OceansX V2 is a solo project with a 9-week phased timeline covering database design, backend services, frontend components, AI agent integration, security hardening, and documentation. AI assistance is part of the build process — the question is how to structure that assistance effectively.

Three approaches were evaluated:
1. Ad-hoc prompts — ask a general-purpose AI assistant whatever is needed, case by case.
2. A single large agent — one AI agent with broad permissions and a comprehensive system prompt covering all development tasks.
3. Specialized role agents — multiple AI agents, each with a defined scope, restricted tools, and an explicit checklist.

The structural problem with ad-hoc prompts and single-agent approaches is consistency. A general-purpose AI responding to "write a database migration" and "review this endpoint for SQL injection" in the same session produces inconsistent quality — the context drifts, the role boundaries are implicit rather than enforced, and there is no structural mechanism to ensure that security review actually happens before a PR is merged.

Claude Code's native subagent architecture provides a built-in solution: markdown files in `.claude/agents/` with YAML frontmatter define named roles with specific tools, models, and system prompts. Claude Code automatically routes tasks to the appropriate agent based on the agent's description, or the developer invokes a specific agent by name.

---

## Decision

Implement the Build Swarm as **nine Claude Code subagent files** in `.claude/agents/`, one per role:

| File | Role | Scope |
|---|---|---|
| `architect.md` | Architect | High-level design, ADRs, architecture document |
| `db-engineer.md` | Database Engineer | Alembic migrations, indexes, query optimization |
| `backend-engineer.md` | Backend Engineer | Services, routers, clients (excluding DB and agents) |
| `frontend-engineer.md` | Frontend Engineer | React components, hooks, Tailwind styles |
| `agent-engineer.md` | Agent Engineer | Operations Swarm code only |
| `security-reviewer.md` | Security Reviewer | Security review on all PRs |
| `code-reviewer.md` | Code Reviewer | General code quality review |
| `test-engineer.md` | Test Engineer | pytest, vitest, test fixtures |
| `doc-maintainer.md` | Documentation Maintainer | Phase journal, ADRs, glossary |

Each agent file specifies: allowed file globs (which parts of the codebase the agent can touch), forbidden actions (e.g., the Security Reviewer cannot write code; it can only read and report), a mandatory review checklist (Security Reviewer must verify: no SQL string interpolation, no secrets in code, all admin endpoints gated, etc.), and a defined output format.

The per-feature workflow is: Architect → Database Engineer → Backend Engineer → Frontend Engineer → Test Engineer → Code Reviewer + Security Reviewer in sequence → Documentation Maintainer → manual commit by the developer. No code is merged without Code Reviewer and Security Reviewer sign-off.

---

## Alternatives Considered

1. **Ad-hoc AI prompts** — No agent files; ask Claude whatever is needed without a defined structure. Rejected because there is no mechanism to ensure that security review, test coverage, or documentation update actually happen. The quality of each task depends entirely on what the developer thinks to ask. Critical checks get missed under time pressure.

2. **Single large agent with a comprehensive system prompt** — One agent definition covering all development tasks. Rejected because a single agent with broad permissions (write any file, run any bash command) has a large blast radius if it misbehaves. More importantly, the quality of specialized tasks (security review, migration writing) is better when the agent's entire context is oriented toward that specialization — not diluted by a general-purpose system prompt covering nine different roles.

3. **External AI development tool (e.g., GitHub Copilot Workspace, Devin)** — Third-party AI development automation. Rejected because the project is already structured around Claude Code, which provides the subagent capability natively. Switching tools would require re-specifying all constraints in a different system, with no benefit for this use case.

---

## Consequences

- **Enables:** Consistent, role-specific AI assistance for each development task; mandatory review checklists that are structurally enforced (a PR without Security Reviewer sign-off cannot be merged); clear attribution of which agent produced which output; a documented, repeatable development workflow across all nine phases.
- **Precludes:** The Build Swarm agents from running autonomously. Claude Code subagents are always developer-initiated — they do not run on a schedule or trigger each other. (The Operations Swarm handles autonomous runtime tasks; see ADR-0003.)
- **Costs:** Nine agent files to maintain and update as the project evolves. If a role's scope or checklist changes, the corresponding file must be updated. The Documentation Maintainer agent is responsible for keeping the agent files accurate.
- **Reversibility:** 1 (trivial). Agent files are markdown files. Removing, merging, or changing them requires no migration and no system-level change.

---

## Plain-English Summary

Building a project this complex with AI assistance works much better when the AI knows what role it is playing at any given moment. Asking a general assistant to switch between "write a database migration" and "review this code for SQL injection vulnerabilities" in the same conversation produces inconsistent results — the context and priorities mix together.

OceansX V2 solves this by defining nine specialized AI roles — each stored as a text file that describes the role's responsibilities, what files it can touch, what it is forbidden to do, and what checklist it must complete before signing off. Claude Code reads these files and automatically routes tasks to the right role. A security review is performed by the Security Reviewer, not the Backend Engineer. A database migration is written by the Database Engineer, not the Architect. Each role has one job and clear constraints. The mandatory checklists — which must be filled in before code is merged — are what make this more than organizational tidiness. They are the mechanism that ensures security review, test coverage, and documentation updates actually happen on every feature, not just when the developer remembers to ask.
