import io
import json
import os
import typing
import dataclasses

import click

from gwenlake.factory import FactoryClient


@dataclasses.dataclass
class _Context:
    obj: FactoryClient


@click.group()  # type: ignore
@click.pass_context  # type: ignore
def cli(ctx: _Context):
    ctx.obj = FactoryClient()


if __name__ == "__main__":
    cli()