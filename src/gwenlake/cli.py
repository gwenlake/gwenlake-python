import io
import json
import os
import typing
import dataclasses

import click

from gwenlake import Credentials, InferenceClient, FactoryClient


# @dataclasses.dataclass
# class _Context:
#     inference: InferenceClient
#     factory: FactoryClient


@click.group()
@click.pass_context
@click.option(
    "--profile", type=str, help="Profile.", default="default",
)
def main(
    ctx: click.Context,
    profile: str | None,
) -> None:
    credentials = Credentials.from_profile(profile)
    ctx.obj = InferenceClient(api_key=credentials.token)


# main.add_command(embeddings)


if __name__ == "__main__":
    main()