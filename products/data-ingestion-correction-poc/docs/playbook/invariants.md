# Confirmed invariants — not open questions

These were explicitly decided in the reference build. Paste this file's contents into your
project's `CLAUDE.md` after running step 1, so no later session (or agent) proposes "improving"
one of these as if it were still undecided.

1. **A row has exactly one assigned end user, permanently.** Two end users must never see the
   same row. Do not add a many-to-many (join-table) model here, even as an option — the
   single-FK ownership model is the intended design, not a POC shortcut to revisit.
2. **Autosave (persist) and Ship (publish) are two separate steps that must stay separate.**
   Autosave only persists an end user's edit into the app's own storage — it never touches the
   target database table. Publishing is a separate, explicit action that rebuilds the target
   table from *every* persisted edit across *every* end user, not just whoever just clicked
   publish. This is what lets two different end users save independently without one clobbering
   the other's earlier corrections. Do not merge these into one "save and publish" call.
3. **End users only ever see rows assigned to them.** Enforced server-side on both the read
   (grid) and write (save) paths — a row not assigned to the caller is invisible and rejected if
   targeted directly.
4. **Datasets coexist.** Ingesting new data never wipes a prior dataset — every ingest creates a
   new, independently-configured dataset (own rules, own target table, own assigned end users).
   Don't reintroduce a singleton "current dataset" concept.
5. **SQL identifiers are never string-interpolated without validation first.** Any table/column
   name built from admin input (target table name, derived column names) must pass through a
   single validation function before being used in dynamically generated DDL/DML. Values always
   go through bound parameters; identifiers never do (they can't be parameterized).
6. **Two kinds of cell editability, don't collapse them.** An ingested column's editability is
   per-cell and admin-flagged (the admin picks specific row+column cells and gives each its own
   dropdown of valid corrections). An admin-added column's editability is per-column and
   inherent (every assigned row gets an editable cell in that column automatically, validated
   against the column's own type/options instead of a per-cell rule).
7. **Every write path — autosave and publish alike — goes through the same validated function.**
   No "fast path" that writes a correction or touches the target table without going through the
   same ownership/editability/value validation as any other request.
8. **A row belongs to exactly one dataset.** Any request that saves an edit must carry an
   explicit dataset identifier alongside it — never assume a row index is globally unique or try
   to infer which dataset it belongs to.
9. **An end user's view aggregates across every dataset they have assigned rows in.** Publishing
   is per-dataset — an end user can publish a dataset only if they have at least one row
   assigned in it. Don't add a "publish everything" action that iterates datasets implicitly.
10. **If you add a multi-tier admin model, keep the tiers equal except for one explicit
    difference.** In the reference build: master admin and named admin have identical access to
    everything *except* that only the master admin can manage other admin accounts. Don't scope
    any other admin feature to the top tier without it being a deliberate new product decision.
