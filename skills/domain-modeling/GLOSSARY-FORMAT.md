# GLOSSARY.md format


```md
# {Project name}

{One or two sentences: what this project studies.}

## Metrics

**z_rel**:
Teacher-forced error of one flow-head draw, sqrt(mean ‖pred − true‖² / mean ‖true‖²); 1.0 = predicting zero, √2 = an
independent draw from the marginal.
_Avoid_: relative error, z error

## Data

**Store**:
The encoded continuous-token table that training reads, one row per residue, covering a prefix of the training rows.
_Avoid_: cache, latent DB
```

Rules
- **Be opinionated.** When several words name one concept, pick one and list the rest under `_Avoid_`.
- **Keep definitions tight.** One or two sentences: what it IS, not what it does or where it lives.
- **Only project-specific terms.** General ML vocabulary (learning rate, attention, TM-score itself) stays out unless the
  project uses it in a specific way (which TM, against which reference).
- **Group by clusters** that emerge naturally: metrics, data, models and arms, gates and baselines.
- One `GLOSSARY.md` at the project root. Create it lazily, when the first term settles.
