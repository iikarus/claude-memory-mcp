import json
import os
import sys


def generate_config() -> None:
    """Generates the Claude Desktop configuration JSON."""
    cwd = os.getcwd()
    python_path = sys.executable
    script_path = os.path.join(cwd, "src", "claude_memory", "server.py")

    config = {
        "mcpServers": {
            "claude-memory": {
                "command": python_path,
                "args": [script_path],
                "env": {"FALKORDB_HOST": "localhost", "FALKORDB_PORT": "6379"},
            }
        }
    }

    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    generate_config()
