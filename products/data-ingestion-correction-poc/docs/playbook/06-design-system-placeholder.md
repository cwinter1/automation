# Step 6 — Design system

## Context

The reference build hit a case where the intended design reference (an internal repo) wasn't
accessible mid-session, so it shipped a documented placeholder instead of guessing at a brand. In
your company environment you likely *do* have your design reference available — use it here
instead of repeating the placeholder step, unless you genuinely want a brand-neutral starting
point first.

## Prompt — if you have a design reference available now

```
Restyle the app to match [our design system repo / these screenshots — attach or point at them].
Express every color, spacing, radius, and shadow value as a small set of tokens (CSS custom
properties or your framework's equivalent) rather than hardcoding values in component rules, so
future palette changes are a token edit, not a rewrite. Cover light and dark mode if our design
system has both.
```

## Prompt — if you don't have one yet (placeholder, matches the reference build)

```
We don't have a final design system available yet. Build a clean, professional, accessible
placeholder: a token-based system (color, spacing, radius, shadow, font as reusable
properties), light + dark mode, applied consistently across every component — don't hardcode
colors in individual component rules. Document clearly in the code and in a project skill/doc
that this is a placeholder, not the final design, and structure it so swapping in a real design
later is a token-value change, not a rewrite. Create a folder for me to drop in reference
screenshots or a design-system repo link later, and note in the docs that the next design pass
should start there.
```

## Expect / confirm

- If using the placeholder path, confirm Claude documents *where* the eventual real design
  should come from (a repo, screenshots, a design-system package) so a future session doesn't
  have to rediscover that context.
- Either way, confirm no component rule hardcodes a color/spacing value outside the token
  definitions — that's the property that makes the later swap cheap.

## Checklist after this step

- [ ] All color/spacing/radius/shadow values are tokens, not hardcoded per-rule values.
- [ ] Light and dark mode both work (or your equivalent, if not doing dark mode).
- [ ] If placeholder: a docs note + a folder exists for the real design reference to land in
      later, and the placeholder is clearly labeled as provisional.
