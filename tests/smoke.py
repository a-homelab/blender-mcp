import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOL_COUNT = 26
EXPECTED_CLI_TOOL_COUNT = 6


async def check_server(blend_file: Path) -> None:
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", 8000)
            writer.close()
            await writer.wait_closed()
            break
        except OSError:
            await asyncio.sleep(0.1)
    else:
        message = "MCP server did not start"
        raise TimeoutError(message)
    async with (
        streamable_http_client("http://127.0.0.1:8000/") as (read, write, _),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        tools = await client.list_tools()
        assert len(tools.tools) == EXPECTED_TOOL_COUNT, len(tools.tools)
        assert (
            len([t for t in tools.tools if t.name.endswith("_for_cli")])
            == EXPECTED_CLI_TOOL_COUNT
        )
        response = await client.call_tool(
            "execute_blender_code_for_cli",
            {
                "blend_file": str(blend_file),
                "code": "import bpy; result = {'cube': bpy.data.objects['Cube'].type}",
            },
        )
        assert not response.isError, response
        payload = json.loads(response.content[0].text)
        assert payload["cube"] == "MESH", payload
        print(
            "OK: upstream HTTP server, 26 tools, and background Blender CLI execution"
        )


def main() -> None:
    with (
        tempfile.TemporaryDirectory(prefix="blender-mcp-smoke-") as work,
        tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log,
    ):
        blend_file = Path(work) / "scene.blend"
        subprocess.run(
            [
                "blender",
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python-expr",
                (
                    "import bpy; bpy.ops.wm.save_as_mainfile("
                    f"filepath={str(blend_file)!r})"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        server = subprocess.Popen(
            [
                "blender-mcp",
                "--transport",
                "http",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            stdout=log,
            stderr=log,
        )
        try:
            asyncio.run(asyncio.wait_for(check_server(blend_file), timeout=90))
        except BaseException:
            log.seek(0)
            print(log.read())
            raise
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
