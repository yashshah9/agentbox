"""CLI entry point."""

import click
import uvicorn

from agentbox import __version__
from agentbox.config import Settings


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Self-hosted code execution sandbox for AI agents."""


@main.command("serve")
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def serve(host: str | None, port: int | None) -> None:
    settings = Settings()
    uvicorn.run(
        "agentbox.api.app:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
    )


@main.command("health")
def health_cmd() -> None:
    click.echo(f"agentbox {__version__} OK")


if __name__ == "__main__":
    main()
