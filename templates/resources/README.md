# resources/: your inputs to the project

Everything here is optional, and you can add to it at any stage.

| Put | Where |
|---|---|
| Initial direction, intuitions, constraints | `BRIEF.md` |
| Paper / GitHub / dataset links | `LINKS.md` |
| PDFs (papers, slides, drafts, reviews) | `papers/` |
| Your existing code, results, notebooks, or a symlink to them | `prior-work/` |
| Anything else (notes, emails, figures) | `other/` |

The agent **reads but doesn't edit** these files, except that it appends to `INTAKE.md`, a log of what it has read and taken from each resource.
Cloned repositories go to `repos/` (gitignored). PDFs stay out of git.
