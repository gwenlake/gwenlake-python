import json

import click

from gwenlake import Gwenlake


@click.group()
@click.option("--profile", type=str, help="Credentials profile to use.", default="default")
@click.pass_context
def main(ctx: click.Context, profile: str) -> None:
    ctx.obj = Gwenlake(profile=profile)


@main.command()
@click.pass_obj
def models(client: Gwenlake) -> None:
    """List available inference models."""
    click.echo(json.dumps(client.models.list(), indent=2))


@main.command()
@click.pass_obj
def datasets(client: Gwenlake) -> None:
    """List accessible datasets."""
    click.echo(json.dumps(client.datasets.list(), indent=2))


@main.command()
@click.pass_obj
def projects(client: Gwenlake) -> None:
    """List accessible projects."""
    click.echo(json.dumps(client.projects.list(), indent=2))


if __name__ == "__main__":
    main()
