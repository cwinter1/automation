# Design reference screenshots

Drop reference screenshots here — UI mockups, the `maya-math` app's actual screens, or any
"this is the look we want" images.

`app/static/app.css` currently uses a brand-neutral placeholder token system (documented in
`.claude/skills/frontend/SKILL.md`) specifically so that swapping in a real design is a token
update, not a rewrite. Once screenshots land here, the next design pass should:

1. Read the images in this folder.
2. Update the color/spacing/radius/shadow custom properties in `app/static/app.css`'s `:root`
   and dark-mode blocks to match.
3. Only touch individual component rules (buttons, tables, panels, etc.) if the real design
   needs a different shape, not just different colors — see `frontend/SKILL.md` for the pattern.

No naming convention required — just add images (`.png`/`.jpg`/`.svg`) and, if it's not obvious
from the filename, a line or two here about which screen/state each one shows.
