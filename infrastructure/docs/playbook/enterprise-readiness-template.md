# Step 8 (optional) — Enterprise readiness doc

## Context

Once the POC works, capture "what's missing to go live" as a real document instead of leaving it
in chat history. This is the prompt that produced `ENTERPRISE_READINESS.md` in the reference
build (`cwinter1/automation`) — reuse it as-is, or point Claude at your actual target
infrastructure so the recommendations are concrete instead of generic.

## Prompt

```
Write ENTERPRISE_READINESS.md: what's missing to take this from POC to a real, multi-user,
production deployment, and what's recommended once it gets there. Cover at minimum:

- Data layer: is the current database engine adequate for production concurrency? Are there
  real migrations, or does startup just create tables? Any missing indexes for the query
  patterns that exist? Any need for an audit/history trail on the "publish" action?
- Security: CSRF, credential rotation for any shared/master accounts, rate limiting on login,
  TLS/secure cookies, audit logging of who-did-what, secrets management for connection strings
  and keys.
- Operability: containerization/CI, structured logging and error monitoring, backup strategy,
  health checks.
- Product decisions still open (e.g. final design, retention policy for old datasets).

Also list what's already solid and does NOT need rework — cite the specific mechanisms (by file/
function) that got the most scrutiny during development and held up under testing, so it's clear
what's foundation versus what's backlog.

Our actual target infrastructure is: [fill in — e.g. "AWS, Postgres RDS, ECS, company SSO via
Okta, Datadog for monitoring"]. Ground the recommendations in that, not generic advice.
```

## Expect / confirm

- If you don't fill in your target infrastructure, Claude will produce generic recommendations
  (Postgres "or similar," "a secrets manager") — that's fine as a first pass, but revisit once
  you know your actual target stack so the doc gives concrete next steps, not categories.

## Checklist after this step

- [ ] Doc distinguishes clearly between "must-do before real users" (security, data-layer
      correctness) and "recommended once you're there" (operability polish) — not one flat list.
- [ ] Doc cites what's already solid, not just what's missing — useful for anyone auditing the
      handoff later.
