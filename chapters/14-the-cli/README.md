# Chapter 14 - The CLI

> **Goal:** the same data from the terminal. A small `chainidx` command to look up
> the tip, blocks, transactions, balances, pools, and governance - and to run the
> follower - without starting a web server.

An HTTP API is great for programs; a command-line tool is great for people and for
scripts. This chapter adds `chainidx`, a thin terminal front-end over the same
store. It is short, because all the work is already done - the CLI just prints
what the store returns.

## Commands

```bash
chainidx tip                      # current tip height and hash
chainidx block <hash>             # a block's height, slot, and tx count
chainidx tx <hash>                # a transaction's inputs and outputs
chainidx balance <address>        # an address's lovelace
chainidx pools                    # active stake pool ids
chainidx account <stake_address>  # registration and delegation
chainidx governance               # actions and vote tallies
chainidx follow                   # index a live chain into the database
```

Every command takes `--db PATH` (default `chain.db`) to choose the database.

## click, briefly

We use `click`, the same library cardonnay uses. The essentials:

- `@click.group()` makes a command that has subcommands (like `git`), and
  `@main.command()` attaches one.
- `@click.argument("name")` is a required positional argument; `@click.option`
  is a flag like `--db`.
- `@click.pass_context` gives a handler the shared context, where we stash the
  database path so every subcommand can reach it.
- `click.echo(...)` prints, and `ctx.exit(1)` exits with a failure code - which we
  use when a block or transaction is not found, so scripts can detect it.

The console command itself is wired in `pyproject.toml`:

```toml
[project.scripts]
chainidx = "chainidx.cli:main"
```

so after `make install` the word `chainidx` runs our `main` group.

## The follow command

`chainidx follow` runs the sync loop from the terminal. It picks a source - our
own `NodeSource` by default, or `--source ogmios` - and indexes into the database:

```bash
chainidx --db chain.db follow --source node --events 300
```

Because it drives a live node, its body is excluded from the coverage gate, just
like the API's `create_default_app`. Everything above it - the query commands - is
fully tested.

## Tested with CliRunner

click ships a `CliRunner` that invokes commands in-process and captures their
output and exit code. The tests populate a temporary database, then run each
command and check what it printed - including the non-zero exit codes for a
missing block and a missing transaction, and the "no blocks" message on an empty
database. No subprocess, no real node.

Run for real against a freshly-followed database, `chainidx tip` prints the true
tip height and `chainidx pools` prints the cluster's three real pool ids - the CLI
reads exactly what the indexer wrote.

## What we built

- `chainidx.cli`: a click group with query subcommands and a `follow` command.
- Full test coverage of the query commands via `CliRunner`.

## Glossary

- **CLI**: command-line interface; a program you drive with typed commands.
- **click**: the Python library we use to build the CLI.
- **Exit code**: the number a program returns; 0 for success, non-zero for
  failure, so scripts can branch on it.
- **`CliRunner`**: click's in-process test driver.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch14): add the chainidx command-line interface"
git tag ch14
```

## Next up

[Chapter 15 - The explorer](../15-the-explorer/): a browsable block explorer. A
single web page over the REST API where you click from the latest blocks into a
block, into its transactions, into an address - the cardanoscan-style view of the
data we index.
