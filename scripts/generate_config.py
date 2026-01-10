import json
import os
import sys


def generate_config() -> None:
    """Generates the Claude Desktop configuration JSON."""
    # Anchor to the project root (one level up from scripts/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_path = sys.executable
    script_path = os.path.join(project_root, "src", "claude_memory", "server.py")

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
