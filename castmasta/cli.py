"""CLI interface for CastMasta."""

import asyncio
import json

import click

from castmasta import CastAgent
from pyatv.const import Protocol


@click.group()
@click.pass_context
def cli(ctx):
    """CastMasta - Control AirPlay and Google Cast devices."""
    ctx.ensure_object(dict)
    ctx.obj["agent"] = CastAgent()


@cli.command()
@click.option("--timeout", "-t", default=5.0, help="Scan timeout in seconds")
@click.pass_context
def scan(ctx, timeout):
    """Scan for AirPlay and Google Cast devices on the network."""
    agent: CastAgent = ctx.obj["agent"]
    devices = asyncio.run(agent.scan(timeout))
    if devices:
        click.echo("Found devices:")
        for dev in devices:
            click.echo(f"  - {dev['name']} ({dev['address']}) [{dev['device_type']}]")
            click.echo(f"    Identifier: {dev['identifier']}")
            click.echo(f"    Protocols: {', '.join(dev['protocols'])}")
    else:
        click.echo("No devices found")


@cli.command()
@click.argument("name")
@click.option(
    "--protocol", "-p", type=click.Choice(["airplay", "companion"]), default="airplay"
)
@click.pass_context
def connect(ctx, name, protocol):
    """Connect to a device by name (auto-detects AirPlay or Google Cast)."""
    agent: CastAgent = ctx.obj["agent"]
    proto = Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
    backend = asyncio.run(agent.connect_by_name(name, proto))
    click.echo(f"Connected to {name} [{backend.device_type}]")


@cli.command()
@click.argument("identifier")
@click.pass_context
def disconnect(ctx, identifier):
    """Disconnect from a device."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.disconnect(identifier))
    click.echo(f"Disconnected from {identifier}")


@cli.command()
@click.argument("name")
@click.option(
    "--protocol", "-p", type=click.Choice(["airplay", "companion"]), default="airplay"
)
@click.pass_context
def pair(ctx, name, protocol):
    """Start pairing with a device (AirPlay only)."""
    agent: CastAgent = ctx.obj["agent"]

    async def do_pair():
        devices = await agent.scan()
        for dev in devices:
            if dev["name"] == name:
                proto = (
                    Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
                )
                result = await agent.pair(
                    dev["identifier"], dev["address"], dev["name"], proto
                )
                return dev, result
        return None, None

    dev, result = asyncio.run(do_pair())
    if not dev:
        click.echo(f"Device '{name}' not found")
        return

    if result["status"] == "pin_required":
        click.echo(
            "PIN required on device - use pair-pin command with the code shown on your device"
        )
    else:
        click.echo("Pairing initiated - use pair-pin command")


@cli.command()
@click.argument("name")
@click.option("--pin", prompt="Enter PIN", hide_input=False, help="Pairing PIN code")
@click.option(
    "--protocol", "-p", type=click.Choice(["airplay", "companion"]), default="airplay"
)
@click.pass_context
def pair_pin(ctx, name, pin, protocol):
    """Complete pairing with a PIN code (AirPlay only)."""
    agent: CastAgent = ctx.obj["agent"]

    async def do_pair_pin():
        devices = await agent.scan()
        for dev in devices:
            if dev["name"] == name:
                proto = (
                    Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
                )
                success = await agent.pair_with_pin(
                    dev["identifier"], dev["address"], dev["name"], pin, proto
                )
                return success
        return False

    success = asyncio.run(do_pair_pin())
    if success:
        click.echo("Pairing successful! Credentials cached.")
    else:
        click.echo("Pairing failed. Please try again.")


@cli.command()
@click.argument("identifier")
@click.option(
    "--protocol",
    "-p",
    type=click.Choice(["airplay", "companion", "all"]),
    default="all",
)
@click.pass_context
def remove_credentials(ctx, identifier, protocol):
    """Remove cached credentials for a device."""
    agent: CastAgent = ctx.obj["agent"]
    if protocol == "all":
        agent.credentials.delete(identifier)
    else:
        proto = Protocol.AirPlay if protocol == "airplay" else Protocol.Companion
        agent.credentials.delete(identifier, proto.name)
    click.echo(f"Credentials removed for {identifier}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def power_on(ctx, identifier):
    """Turn on a device."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.power_on(identifier))
    click.echo(f"Powered on {identifier}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def power_off(ctx, identifier):
    """Turn off a device (quits app on Google Cast)."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.power_off(identifier))
    click.echo(f"Powered off {identifier}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def power_state(ctx, identifier):
    """Get power state of a device."""
    agent: CastAgent = ctx.obj["agent"]
    state = asyncio.run(agent.get_power_state(identifier))
    click.echo(f"Power state: {'on' if state else 'off'}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def play(ctx, identifier):
    """Start/resume playback."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.play(identifier))
    click.echo("Playing")


@cli.command()
@click.argument("identifier")
@click.pass_context
def pause(ctx, identifier):
    """Pause playback."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.pause(identifier))
    click.echo("Paused")


@cli.command()
@click.argument("identifier")
@click.pass_context
def stop(ctx, identifier):
    """Stop playback."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.stop(identifier))
    click.echo("Stopped")


@cli.command()
@click.argument("identifier")
@click.argument("url")
@click.option("--position", "-p", default=0, help="Starting position in seconds")
@click.pass_context
def play_url(ctx, identifier, url, position):
    """Play a URL."""
    agent: CastAgent = ctx.obj["agent"]
    kwargs = {}
    if position > 0:
        kwargs["position"] = position
    asyncio.run(agent.play_url(identifier, url, **kwargs))
    click.echo(f"Playing {url}")


@cli.command()
@click.argument("identifier")
@click.argument("file_path")
@click.pass_context
def stream_file(ctx, identifier, file_path):
    """Stream a local file."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.stream_file(identifier, file_path))
    click.echo(f"Streaming {file_path}")


@cli.command()
@click.argument("identifier")
@click.argument("image_path")
@click.option("--duration", "-d", default=3600, type=int, help="Display duration in seconds (default: 3600)")
@click.pass_context
def display_image(ctx, identifier, image_path, duration):
    """Display a static image on a device (converts to video via ffmpeg)."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.display_image(identifier, image_path, duration))
    click.echo(f"Displaying {image_path} for {duration}s")


@cli.command()
@click.argument("identifier")
@click.argument("text", nargs=-1, required=True)
@click.option(
    "--voice", "-v", default="en_US-lessac-medium",
    help="Piper voice model name (default: en_US-lessac-medium)",
)
@click.pass_context
def announce(ctx, identifier, text, voice):
    """Synthesise text to speech and play it on a device."""
    text = " ".join(text)
    agent: CastAgent = ctx.obj["agent"]
    try:
        asyncio.run(agent.announce(identifier, text, voice))
    except (ValueError, FileNotFoundError) as e:
        raise click.ClickException(str(e))
    except RuntimeError as e:
        raise click.ClickException(f"Piper TTS error: {e}")
    click.echo(f"Announced: {text}")


@cli.command()
@click.argument("identifier")
@click.argument("volume", type=float)
@click.pass_context
def set_volume(ctx, identifier, volume):
    """Set volume (0.0 to 1.0)."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.set_volume(identifier, volume))
    click.echo(f"Volume set to {volume}")


@cli.command()
@click.argument("identifier")
@click.option("--delta", "-d", default=0.1, help="Volume delta")
@click.pass_context
def volume_up(ctx, identifier, delta):
    """Increase volume."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.volume_up(identifier, delta))
    click.echo(f"Volume up by {delta}")


@cli.command()
@click.argument("identifier")
@click.option("--delta", "-d", default=0.1, help="Volume delta")
@click.pass_context
def volume_down(ctx, identifier, delta):
    """Decrease volume."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.volume_down(identifier, delta))
    click.echo(f"Volume down by {delta}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def get_volume(ctx, identifier):
    """Get current volume."""
    agent: CastAgent = ctx.obj["agent"]
    volume = asyncio.run(agent.get_volume(identifier))
    click.echo(f"Volume: {volume}")


@cli.command()
@click.argument("identifier")
@click.pass_context
def now_playing(ctx, identifier):
    """Get now playing information."""
    agent: CastAgent = ctx.obj["agent"]
    info = asyncio.run(agent.now_playing(identifier))
    click.echo(json.dumps(info, indent=2))


@cli.command()
@click.argument("identifier")
@click.argument("position", type=float)
@click.pass_context
def seek(ctx, identifier, position):
    """Seek to position in seconds."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.seek(identifier, position))
    click.echo(f"Seeked to {position}s")


@cli.command()
@click.argument("identifier")
@click.argument("key")
@click.pass_context
def send_key(ctx, identifier, key):
    """Send a key press (AirPlay only)."""
    agent: CastAgent = ctx.obj["agent"]
    asyncio.run(agent.send_key(identifier, key))
    click.echo(f"Sent key: {key}")


@cli.command()
@click.pass_context
def tools(ctx):
    """Print LLM tool definitions (JSON)."""
    agent: CastAgent = ctx.obj["agent"]
    click.echo(json.dumps(agent.get_tool_definitions(), indent=2))


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
