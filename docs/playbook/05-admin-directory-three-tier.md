# Step 5 — Three-tier admin directory

## Context

Moves off a single shared admin password toward a real directory, without going all the way to
a full identity-provider integration. If your company already has SSO, replace this prompt with
one describing your actual identity requirement — don't bolt this scheme on top of SSO, they
solve overlapping problems differently.

## Prompt

```
Replace the single shared admin password with a three-tier admin model:

- Master admin: the one account with the original shared credential. Has full admin access to
  everything, PLUS the exclusive ability to create and remove named admin accounts.
- Admin: an individual username+password account, created by the master admin. Full admin
  access — everything a master admin can do EXCEPT manage other admin accounts. That one
  capability is master-admin-only.
- End user: unchanged from before — individual username+password, created by an admin.

The login page should make the three roles clearly distinguishable (separate tabs/sections), not
one ambiguous form.
```

## Expect / confirm

- Claude should ask what, besides admin-account management, is master-admin-only. The answer
  (unless you have a specific reason to differ): **nothing else** — treat "admin" and "master
  admin" as equal for every other capability, so you don't end up with features accidentally
  gated to the top tier with no product reason (`invariants.md` point 10).
- If you want a *fourth* tier or a different split of capabilities, say so explicitly here —
  don't let Claude infer additional restrictions from "master" sounding more senior.

## Checklist after this step

- [ ] Master admin can create/remove named admin accounts; named admins cannot.
- [ ] A named admin has identical access to every other admin feature (ingestion, rules, end-user
      management, shipping, etc.) as the master admin.
- [ ] Login clearly distinguishes the three roles.
- [ ] Existing tests that assumed a single shared "admin" role are updated to specify master
      admin vs. named admin where the distinction matters.
