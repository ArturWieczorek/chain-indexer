# Contributing

Thanks for your interest in chain-indexer. It is a teaching project: the git history
is a step-by-step course, one chapter per commit, each tagged `chNN` with a matching
write-up in [`chapters/`](chapters/). That shape is intentional, so a few
conventions keep it readable.

## Setting up

```bash
python3 -m venv .venv
source .venv/bin/activate
make install        # editable install with the chain libraries and dev tools
make check          # linter, type checker, and tests - exactly what CI runs
```

`make check` runs `ruff check`, `ruff format --check`, `mypy` (strict), and `pytest`
with a 100 percent coverage gate on the pure core. It must be green before anything
is merged; CI runs the same on Python 3.12 and 3.13.

## Ground rules

- **Small, clear steps over clever code.** The code is meant to be read.
- **Test-driven.** Add or update the failing test first, then the code. Unit tests
  are fully offline and deterministic (no sleeping on the real clock; inject a fake).
- **Keep the core standard-library first.** Add a dependency only when a feature
  needs it, and say why.
- **Coverage stays at 100 percent** on the pure core. Integration-only modules
  (those that need a live node) are marked `# pragma: no cover` and listed in the
  coverage `omit` config.

## Submitting a change

1. Fork and branch from `main`.
2. Make the change with its tests; run `make check` until green.
3. Use clear commit messages in the Conventional Commits style
   (`feat(...)`, `fix(...)`, `docs(...)`).
4. Open a pull request describing what changed and why. CI must pass.

## Reporting bugs

Open an issue with the steps to reproduce, what you expected, and what happened
(include the network/config and any relevant output).
