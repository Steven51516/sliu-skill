# Scope: MIT ORCD Engaging (Slurm)

Source: https://orcd-docs.mit.edu (checked 2026-09-17). The org policy in /etc/claude-code/CLAUDE.md covers filesystem-scan and etiquette rules.
Scope interface: `~/research-harness/scopes/README.md`.

## Login node: edit and submit, never compute
Claude runs on a **login node** (`login*`). Allowed there: editing files, git, installing packages, small downloads, submitting and
checking jobs, and checks that take seconds and under ~1 GB. **Everything else goes through Slurm** (`srun` for minutes, `sbatch` for the rest): training, evals, preprocessing, tests that load
models or data, notebooks. If unsure, submit it.

## Running jobs
- **Batch (default):** `sbatch job.sbatch`. Template:
  ```bash
  #!/bin/bash
  #SBATCH -J <name>
  #SBATCH -p mit_normal_gpu         # partition, see table
  #SBATCH -G l40s:1                 # GPUs; omit for CPU jobs
  #SBATCH -c 8                      # CPU cores (4–8 per GPU)
  #SBATCH --mem=64G                 # ~1.5–2x GPU memory per GPU
  #SBATCH -t 04:00:00               # realistic; shorter starts sooner
  #SBATCH -o logs/%x-%j.out         # arrays: logs/%x-%A_%a.out
  module purge
  module load miniforge/25.11.0-0   # pin versions (also cuda/12.9.1 etc. if needed)
  source activate <env>             # or: source .venv/bin/activate
  python train.py ...
  ```
- **Smoke test first**: the same script with a tiny config: CPU jobs on `-p mit_quicktest -t 00:15:00`; GPU jobs on
  `-p mit_normal_gpu` (or `mit_preemptable`) with a short `-t` (`mit_quicktest` has no GPUs). Smoke train **and** predict **and** score.
- **Sharing the per-user GPU cap** (other sessions, a reserved GPU): name jobs by ticket id, submit with `sbatch --hold`, and run
  `~/research-harness/scopes/engaging-gpu_gate.sh`. Stop background helpers by PID, never `pkill -f` a pattern matching your own shell.
- **Sweeps:** one job array (`#SBATCH --array=0-N%K`, index via `$SLURM_ARRAY_TASK_ID`), never a loop of `sbatch`.
- **Medium one-offs** (minutes, e.g. load a 1 GB h5ad and check a correlation): `srun -p mit_quicktest -c 4 --mem=16G -t 00:10:00 <cmd>`
  from the login node; it blocks, so keep it under the tool-call timeout, and inside an existing allocation it runs as a step
  of that job. For a burst of them, one `salloc -p mit_quicktest -c 4 --mem=16G -t 00:15:00`, released right after.
- **Monitor:** `squeue --me` (the REASON column explains pending jobs), `sacct -j <id> -o JobID,State,Elapsed,MaxRSS`, `jobstats <id>` after
  it ends (right-size the next request). Cancel: `scancel <id>`. Poll no more often than every ~10 min.
- **Record** the Slurm job id in the ticket's `jobs:` when you submit. A run is finished only when its state is `COMPLETED`
  **and** its result files exist and are non-empty.
- **Ask first:** anything on `mit_preemptable` expected to run over 2 days.

| Partition | Limit | Use for |
|---|---|---|
| `mit_quicktest` | 15 min | smoke tests |
| `mit_normal` | 12 h, ≤96 cores | CPU jobs |
| `mit_normal_gpu` | 6 h, ≤2 GPUs, ≤32 cores | GPU jobs. `-G l40s:N` (default, 44GB), `h200:N` (140GB, only when memory needs it) |
| `mit_preemptable` | 48 h, ≤4 GPUs | long runs. **Checkpoint and resume**; add `--requeue` |

Account `mit_general`. Check with `sinfo -s` and `sacctmgr -nP show assoc user=$USER format=account,partition,qos`.

## Software
- Modules: `module avail <name>` / `module load <name>/<version>`. Put `module purge` and `module load` in job scripts, never in `.bashrc`.
- Python: `module load miniforge`, then `mamba create -n <project> python=3.12 ...` and `source activate <project>`, or a venv at `<project>/.venv`.
  Record the env in the repo (`environment.yml` or `requirements.txt`).
- **Never** run `pip install --user`, `conda init`/`mamba init`, or install your own conda.

## Storage
| Path | Size | Notes → use for |
|---|---|---|
| `~` | 200 GB | flash, **snapshots** → code, envs, small results, figures |
| `~/orcd/pool` | 1 TB | disk, not backed up, **no heavy I/O** → kept datasets and checkpoints (project `artifacts/`) |
| `~/orcd/scratch` | 1 TB | flash, not backed up, **purged after 6 months idle** → I/O-heavy job data and intermediates (project `scratch/`) |
| `~/orcd/datasets` | shared | check here before downloading public data |

- Jobs read training data from scratch (copy it from pool if needed). Large downloads go through `-p mit_data_transfer`.
- Bundle many small files (tar, HDF5, WebDataset). Never put data or checkpoints in git.
- Check usage by reading `~/orcd/.quota` (not `du`).

## New project
`research-init` on Engaging:
`SCOPE_FILE=~/research-harness/scopes/engaging.md PROJECTS_ROOT=~/projects POOL_ROOT=~/orcd/pool/projects SCRATCH_ROOT=~/orcd/scratch/projects bash ~/research-harness/skills/research-init/init.sh <name> ["<direction>"]`
