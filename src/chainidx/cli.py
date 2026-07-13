"""The ``chainidx`` command-line interface.

A small tool to query the indexed database from the terminal - handy for
scripting and for glancing at the indexer's state without starting the API. It
reads the same store the API does.

Built with ``click``: ``@click.group`` makes a command with subcommands, and each
``@main.command`` is one subcommand. The ``--db`` option (on the group) picks
which database file to read; it defaults to ``chain.db``.
"""

from __future__ import annotations

import click

from chainidx.store import SqliteStore, Store


def _store(ctx: click.Context) -> Store:
    return SqliteStore(str(ctx.obj))


@click.group()
@click.option("--db", default="chain.db", show_default=True, help="Path to the index database.")
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """Query a chain-indexer database."""
    ctx.obj = db


@main.command()
@click.pass_context
def tip(ctx: click.Context) -> None:
    """Show the current tip."""
    store = _store(ctx)
    current = store.tip()
    if current is None:
        click.echo("no blocks indexed yet")
    else:
        click.echo(f"tip: block {current.block_no} at slot {current.point.slot_no}")
        click.echo(current.point.block_hash)
    store.close()


@main.command()
@click.argument("block_hash")
@click.pass_context
def block(ctx: click.Context, block_hash: str) -> None:
    """Show a block by hash."""
    store = _store(ctx)
    found = store.get_block(block_hash)
    if found is None:
        click.echo("block not found", err=True)
        ctx.exit(1)
    else:
        click.echo(f"block {found.block_no} at slot {found.slot_no}")
        click.echo(f"prev: {found.prev_hash}")
        click.echo(f"transactions: {len(found.txs)}")
    store.close()


@main.command()
@click.argument("tx_hash")
@click.pass_context
def tx(ctx: click.Context, tx_hash: str) -> None:
    """Show a transaction's inputs and outputs."""
    store = _store(ctx)
    detail = store.get_tx(tx_hash)
    if detail is None:
        click.echo("transaction not found", err=True)
        ctx.exit(1)
    else:
        click.echo(f"tx {detail.tx_id} in block {detail.block_hash}")
        for i in detail.inputs:
            click.echo(f"  in  <- {i.tx_id}#{i.index}")
        for o in detail.outputs:
            click.echo(f"  out -> {o.address}  {o.lovelace} lovelace")
    store.close()


@main.command()
@click.argument("address")
@click.pass_context
def balance(ctx: click.Context, address: str) -> None:
    """Show an address's balance in lovelace."""
    store = _store(ctx)
    click.echo(f"{store.balance(address)} lovelace")
    store.close()


@main.command()
@click.pass_context
def pools(ctx: click.Context) -> None:
    """List active stake pools."""
    store = _store(ctx)
    for pool_id in store.pools():
        click.echo(pool_id)
    store.close()


@main.command()
@click.argument("stake_address")
@click.pass_context
def account(ctx: click.Context, stake_address: str) -> None:
    """Show a stake account's registration and delegation."""
    store = _store(ctx)
    registered = store.is_stake_registered(stake_address)
    click.echo(f"registered: {registered}")
    click.echo(f"delegated to: {store.delegation_of(stake_address) or '(none)'}")
    store.close()


@main.command()
@click.pass_context
def governance(ctx: click.Context) -> None:
    """List governance actions and their vote tallies."""
    store = _store(ctx)
    for action in store.governance_actions():
        click.echo(f"{action}  {store.vote_tally(action)}")
    store.close()


@main.command()
@click.option("--source", type=click.Choice(["node", "ogmios"]), default="node")
@click.option("--socket", envvar="CARDANO_NODE_SOCKET_PATH", default="")
@click.option("--ogmios-url", default="ws://127.0.0.1:1337")
@click.option("--magic", default=42, type=int)
@click.option("--events", default=0, type=int, help="Stop after N events (0 = forever).")
@click.pass_context
def follow(  # pragma: no cover - drives a live node
    ctx: click.Context,
    source: str,
    socket: str,
    ogmios_url: str,
    magic: int,
    events: int,
) -> None:
    """Follow a live chain and index it into the database."""
    import asyncio

    from chainidx.follow import Follower

    async def run() -> None:
        store = SqliteStore(str(ctx.obj))
        if source == "node":
            from chainidx.node import NodeSource

            chain_source = NodeSource(socket, magic)
        else:
            from chainidx.ogmios import OgmiosSource

            chain_source = OgmiosSource(ogmios_url)  # type: ignore[assignment]
        follower = Follower(chain_source, store)
        try:
            await follower.run(max_events=events or None)
        finally:
            await chain_source.close()
            store.close()

    asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    main()
