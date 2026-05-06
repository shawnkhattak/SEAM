# ADR 0010: Deterministic Security — No AI Security Monitoring

**Status:** Accepted
**Decided:** 2026-04-30
**Deciders:** Solo (Shawn Khattak)

---

## Context

The project includes a system of autonomous AI agents (the Operations Swarm) that could theoretically be extended to monitor for security threats — detecting unusual access patterns, analyzing failed login attempts, identifying anomalous outbound requests. AI-based security monitoring is a legitimate approach used in enterprise environments.

The question for OceansX V2 is whether AI security monitoring belongs in this project's security posture, given its nature as a single-user, non-public portfolio project running on a single VPS.

---

## Decision

**All security measures are deterministic — no AI security monitoring.** The security posture consists entirely of:

- **fail2ban** — automatic IP blocking after repeated failed SSH login attempts or repeated HTTP 401/403 responses
- **ufw** — server-level firewall allowing only ports 22, 80, and 443 inbound; Postgres locked to localhost only
- **pip-audit and npm audit** — daily automated dependency vulnerability scans; results written to `dependency_audit_log`; HIGH/CRITICAL findings create `audit_log` entries with admin dashboard visibility
- **HMAC verification** — cryptographic signature check on every RSS.app webhook delivery; mismatches rejected immediately
- **Parameterized SQL** — all database queries use parameterized statements (placeholders, not string concatenation); no SQL injection possible via input; reviewed by Security Reviewer Build Swarm agent on every PR
- **Outbound HTTP allowlist** — the Operations Swarm agents can only make HTTP calls to a defined whitelist of domains (`oceans-x.mpa.gov.sg`, `data.opensanctions.org`, `marine-api.open-meteo.com`, `*.rss.app`, `api.anthropic.com`); enforced at the HTTP transport layer, not by convention
- **Log sanitization** — a log filter strips known secret-pattern strings before log lines are emitted
- **Quarterly secret rotation reminder** — a cron job checks whether each secret is older than 90 days and writes a warning to `audit_log`, surfaced as a banner in the admin dashboard

There is no `security_alert` change type in the `agent_review_queue`. No AI agent monitors logs, traffic, or access patterns.

---

## Alternatives Considered

1. **Add an AI Sentinel agent for real-time log monitoring** — Could detect novel attack patterns that rule-based systems miss; surfaces anomalies proactively. Rejected because: (a) the threat surface for a single-user, non-public portfolio project is narrow and well-covered by deterministic measures; (b) an AI sentinel capable of meaningful threat detection requires significant prompt engineering, ongoing model evaluation, and high false-positive management; (c) it would add approximately $5–15/month to the AI cost budget for a capability that provides marginal additional protection over fail2ban on this project's threat profile.

2. **AI-assisted dependency audit analysis** — Use Claude to summarize and prioritize CVE findings from pip-audit and npm audit. Rejected because pip-audit and npm audit already produce structured, machine-readable output with severity ratings. No AI synthesis is needed to act on a HIGH or CRITICAL CVE finding — the appropriate response (update the dependency, or document a workaround) does not require AI judgment.

3. **No security measures beyond basic firewall** — Minimize maintenance overhead. Rejected because fail2ban, parameterized SQL, HMAC verification, and the outbound allowlist all address real attack vectors that have materialized on internet-exposed servers of comparable scale. The chosen measures are low-maintenance, well-understood, and proportionate to the threat.

---

## Consequences

- **Enables:** A security posture that is entirely predictable, auditable, and maintainable without ongoing AI cost; fail2ban and ufw cover the primary external attack vectors; the outbound HTTP allowlist prevents a compromised agent from exfiltrating data to arbitrary external services.
- **Precludes:** Detecting novel attack patterns that do not trigger fail2ban thresholds (e.g., slow-and-low brute-force spread across many IPs). This is an acceptable gap for a non-public portfolio project; it would need to be revisited at a public launch with real users.
- **Costs:** No additional ongoing cost. Security measures described here are all free and largely automated.
- **Reversibility:** 1 (trivial). Adding AI security monitoring later requires adding an agent to the Operations Swarm and a `security_alert` queue type. Nothing in the current architecture prevents this.

---

## Plain-English Summary

A security system can be either rule-based ("block any IP that fails to log in five times") or AI-powered ("analyze patterns and flag anything unusual"). For an enterprise bank or large public platform, AI-powered security monitoring is worth the investment. For a single-user portfolio project that is not yet publicly accessible, it adds cost and complexity without meaningfully changing the protection level.

OceansX V2's security is entirely rule-based. The server blocks repeated login failures automatically. The firewall only allows web traffic. Dependencies are checked for known vulnerabilities every day. Every outbound connection from the AI agents must go to an approved list of domains — attempts to contact anything else fail immediately. Secrets rotate on a 90-day calendar reminder. These are well-understood, low-maintenance measures that cover the actual threats this project faces. The decision to exclude AI from security monitoring is not a gap — it is a deliberate scope choice that keeps the system transparent and the budget on target.
