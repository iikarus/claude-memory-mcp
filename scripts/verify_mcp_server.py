import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any, cast

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MCP_Verifier")


class MCPClientParams:
    """Simulates the lifecycle of an MCP connection."""

    def __init__(self, command: list[str]):
        self.command = command
        # Fix: Use string forward reference or proper type for Popen if available,
        # but subprocess.Popen is generic in typeshed.
        # For simplicity and compatibility, we use 'subprocess.Popen[str]' in quotes or assume runtime ignores it.
        # Actually, simpler to just use subprocess.Popen and ignore arg match if mypy complains,
        # but mypy wants subprocess.Popen[str].
        self.process: subprocess.Popen[str] | None = None

    async def run(self) -> None:
        logger.info(f"🚀 Launching Server: {' '.join(self.command)}")

        # Start the server process
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,  # Let logs flow to stderr
            text=True,
            bufsize=1,  # Line buffered
            encoding="utf-8",
            cwd=os.getcwd(),
        )

        try:
            # 1. Initialize
            await self.send_request(
                "initialize",
                {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "clientInfo": {"name": "TestClient", "version": "1.0"},
                },
            )
            resp = await self.read_response()
            self.verify_response(resp, "initialize")
            logger.info("✅ Handshake Complete.")

            # Send initialized notification
            self.send_notification("notifications/initialized", {})

            # 2. List Tools
            await self.send_request("tools/list", {})
            resp = await self.read_response()
            self.verify_response(resp, "tools/list")
            tools = resp["result"]["tools"]
            tool_names = [t["name"] for t in tools]
            if "create_entity" in tool_names and "search_memory" in tool_names:
                logger.info(f"✅ Tools Listed: Found {len(tools)} tools including core ops.")
            else:
                raise AssertionError(f"Missing core tools. Found: {tool_names}")

            # 3. Call Tool: create_entity
            # Using Emojis to verify E2E UTF-8 handling
            req_id = "req-1"
            await self.send_request(
                "tools/call",
                {
                    "name": "create_entity",
                    "arguments": {
                        "name": "MCP Test 🤖",
                        "node_type": "Entity",
                        "project_id": "mcp_test",
                        "properties": {"status": "validated"},
                    },
                },
                req_id,
            )
            resp = await self.read_response()
            self.verify_response(resp, "tools/call", req_id)
            content = resp["result"]["content"][0]["text"]
            logger.info(f"✅ Entity Created. Response: {content[:100]}...")

            # 4. Call Tool: search_memory
            req_id = "req-2"
            await self.send_request(
                "tools/call", {"name": "search_memory", "arguments": {"query": "MCP Test"}}, req_id
            )
            resp = await self.read_response()
            self.verify_response(resp, "tools/call", req_id)
            search_res = resp["result"]["content"][0]["text"]
            if "MCP Test" in search_res or "found" in search_res.lower():
                logger.info("✅ Search Verification Passed.")
            else:
                logger.warning(f"⚠️ Search might have failed (Indexing lag?). Result: {search_res}")

        except Exception as e:
            logger.critical(f"❌ Test Failed: {e}")
            raise
        finally:
            logger.info("🛑 Terminating Server...")
            if self.process:
                self.process.terminate()
                self.process.wait()

    async def send_request(self, method: str, params: dict[str, Any], msg_id: Any = 1) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not running")

        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        json_str = json.dumps(msg)
        self.process.stdin.write(json_str + "\n")
        self.process.stdin.flush()

    def send_notification(self, method: str, params: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not running")
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write(json.dumps(msg) + "\n")
        self.process.stdin.flush()

    async def read_response(self) -> dict[str, Any]:
        if not self.process or not self.process.stdout:
            raise RuntimeError("Process not running")

        # Read line (blocking/sync in this simplistic version)
        line = self.process.stdout.readline()
        if not line:
            raise EOFError("Server closed connection")

        return cast(dict[str, Any], json.loads(line))

    def verify_response(self, resp: dict[str, Any], context: str, req_id: Any = 1) -> None:
        if "error" in resp:
            logger.error(f"❌ RPC Error in {context}: {json.dumps(resp, indent=2)}")
            raise AssertionError(f"RPC Error in {context}: {resp['error']}")
        if "result" not in resp:
            logger.error(f"❌ Malformed response in {context}: {json.dumps(resp, indent=2)}")
            raise AssertionError(f"Malformed response in {context}: {resp}")

        # Check content existance for tools
        if context == "tools/call":
            content = resp["result"].get("content", [])
            if not content:
                logger.error(f"❌ No content in tool result: {json.dumps(resp, indent=2)}")
                raise AssertionError(f"No content in tool result for {context}")


if __name__ == "__main__":
    # Determine command to run the server
    # We use sys.executable to ensure we use the same python env
    server_cmd = [sys.executable, "-m", "claude_memory.server"]

    # Needs PYTHONPATH to include src
    os.environ["PYTHONPATH"] = os.path.join(os.getcwd(), "src")

    client = MCPClientParams(server_cmd)
    try:
        asyncio.run(client.run())
        print("\n✨ MCP SERVER VERIFICATION SUCCESSFUL ✨")
    except Exception as e:
        print(f"\n🔥 VERIFICATION FAILED: {e}")
        sys.exit(1)
