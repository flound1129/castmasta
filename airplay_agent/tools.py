"""Tool definitions for LLM function calling."""

TOOLS = [
    {
        "name": "scan_airplay_devices",
        "description": "Scan the local network for AirPlay devices (Apple TV, HomePod, AirPort Express, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "description": "Scan timeout in seconds (default: 5)",
                    "default": 5.0,
                }
            },
        },
    },
    {
        "name": "connect_device",
        "description": "Connect to a specific AirPlay device by name or identifier",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Device name (e.g., 'Living Room Apple TV') or identifier",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "disconnect_device",
        "description": "Disconnect from an AirPlay device",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "power_on",
        "description": "Turn on an AirPlay device",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "power_off",
        "description": "Turn off an AirPlay device",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_power_state",
        "description": "Get the power state of a device (on/off)",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "play",
        "description": "Start or resume playback",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "pause",
        "description": "Pause playback",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "stop",
        "description": "Stop playback",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "play_url",
        "description": "Play a video or audio URL (YouTube, streaming, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "url": {"type": "string", "description": "URL to play"},
                "position": {
                    "type": "number",
                    "description": "Starting position in seconds (optional)",
                },
            },
            "required": ["identifier", "url"],
        },
    },
    {
        "name": "stream_file",
        "description": "Stream a local audio/video file to the device",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "file_path": {
                    "type": "string",
                    "description": "Path to local file (mp3, wav, flac, ogg, mp4, etc.)",
                },
            },
            "required": ["identifier", "file_path"],
        },
    },
    {
        "name": "set_volume",
        "description": "Set volume (0.0 = mute, 1.0 = max)",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "volume": {
                    "type": "number",
                    "description": "Volume level from 0.0 to 1.0",
                },
            },
            "required": ["identifier", "volume"],
        },
    },
    {
        "name": "volume_up",
        "description": "Increase volume by a delta",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "delta": {
                    "type": "number",
                    "description": "Volume increase amount (default: 0.1)",
                    "default": 0.1,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "volume_down",
        "description": "Decrease volume by a delta",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "delta": {
                    "type": "number",
                    "description": "Volume decrease amount (default: 0.1)",
                    "default": 0.1,
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "get_volume",
        "description": "Get current volume level",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "now_playing",
        "description": "Get currently playing media information (title, artist, position, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"}
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "seek",
        "description": "Seek to a specific position in the current media",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "position": {"type": "number", "description": "Position in seconds"},
            },
            "required": ["identifier", "position"],
        },
    },
    {
        "name": "send_key",
        "description": "Send a remote control key press",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "Device identifier"},
                "key": {
                    "type": "string",
                    "description": "Key name: up, down, left, right, select, menu, home, play, pause, play_pause, next, previous",
                },
            },
            "required": ["identifier", "key"],
        },
    },
]


def get_tool_definitions() -> list[dict]:
    """Return the list of tool definitions for LLM function calling."""
    return TOOLS


def get_tool_names() -> list[str]:
    """Return the list of tool names."""
    return [tool["name"] for tool in TOOLS]
