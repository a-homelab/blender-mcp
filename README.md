# Blender MCP container

Container packaging for the official [Blender Lab MCP server](https://projects.blender.org/lab/blender_mcp).
The image runs the upstream entrypoint unchanged:

```sh
blender-mcp --transport http --host 0.0.0.0 --port 8000
```

The server uses Streamable HTTP at `/`. All 26 upstream tools are available.
There is no custom HTTP application, authentication, tool filtering, or health API.
Access control belongs at the gateway; this image is intended for an internal endpoint.

## Runtime

The image uses the pinned LinuxServer Blender 5.2.2 image and the official MCP
`v1.0.3` source commit. `pyproject.toml` pins the official Git source; `uv.lock` records the resolved
runtime and development dependencies for Python 3.14. The image uses uv 0.12.17
and `uv sync --locked --no-dev --no-editable` at build time. Ruff and uv are not
installed in the final runtime image.

The LinuxServer desktop entrypoint is replaced with `blender-mcp`, so this
container only starts the MCP server. The included Blender executable supports
the six upstream `_for_cli` tools, which launch separate background Blender
processes. Connected-session tools use `BLENDER_MCP_HOST` and `BLENDER_MCP_PORT`
(defaults: `127.0.0.1:9876`) to reach the addon in the authoring container.

Mount the same `/workspace` in both containers so CLI tools can open saved scenes,
resolve assets, and exchange temporary copies of unsaved scenes. The chart gives
the sidecar a writable `/tmp` and runs it as UID/GID 1000 with a read-only root
filesystem. It does not request a second GPU: background CLI execution uses CPU,
while connected tools execute inside the GPU-enabled authoring container.

Kubernetes TCP startup/readiness probes check port 8000. They do not prove that
the addon is connected or Blender is responsive. Keep one active scene writer.

## Development

Use uv 0.12.17 or newer. `.python-version` selects Python 3.14.

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Ruff 0.16.8 enables all stable lint rules, including type annotations and import
sorting. Exceptions cover formatter conflicts, optional copyright headers, and
smoke-test conventions: no mandatory docstrings/package marker, assertions,
fixed subprocess commands, and console output. Run `uv lock --check` and the
local lint and formatting commands before publishing changes.

Upgrade dependencies with `uv lock --upgrade`, then rerun lint and the container
smoke test. This resolves the newest versions allowed by upstream constraints.
Blender MCP 1.0.3 requires `mcp<2`, so the lock currently selects SDK 1.30.0 even
though SDK 2.x exists. Upgrade the official server and matching addon together
before changing that compatibility boundary. The upstream setuptools build
backend is constrained separately in `tool.uv.build-constraint-dependencies`.

## Build and test

```sh
docker build -t blender-mcp:local .
docker run --rm --read-only --tmpfs /tmp:uid=1000,gid=1000 \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --mount type=bind,src="$PWD/tests",dst=/tests,readonly \
  --entrypoint /opt/mcp/bin/python blender-mcp:local /tests/smoke.py
```

The smoke test initializes a real HTTP MCP client, lists all 26 tools, and executes
a background Blender tool against a disposable scene without a running addon.
Run this smoke test locally before publishing.

CI calls the shared
[`build-push-container` workflow](https://github.com/a-homelab/github-actions/blob/main/.github/workflows/build-push-container.yaml)
to build, scan, and publish the image. The `tags` input in
`.github/workflows/build.yaml` owns the image tag, currently
`1.0.3-blender5.2.2-1`. GitHub Actions publishes `ghcr.io/a-homelab/blender-mcp`
on main or manual dispatch; pull requests build and scan without publishing.
Ruff and the HTTP/CLI smoke test run locally. The Git remote is
`git@github.com:a-homelab/blender-mcp.git`. Allow the cluster to pull the package
before deploying it.

The deployment chart lives separately in `a-homelab/helm-charts/charts/blender`.
Update its sidecar image tag when publishing a new version. Upgrade the source
commit, addon version/checksum in the chart, and Blender image together.

## Verification on 2026-09-18

After conversion to uv, lockfile freshness, strict Ruff linting, and formatting
checks passed. The image built using `uv sync --locked --no-dev --no-editable`
and passed the HTTP/CLI smoke test with all 26 tools. Its runtime contains MCP
SDK 1.30.0 and excludes uv and Ruff executables. Build/test logs for this check
are under `/tmp/blender-mcp-uv/` on the validation machine.

The image built and passed the HTTP/CLI smoke test with a read-only root filesystem
and no extra container capabilities. An isolated Blender desktop and MCP sidecar
then initialized over HTTP, listed 26 tools, saved a disposable scene and GLB,
read the shared scene through a CLI tool, and reopened it after both containers
restarted without external network access. Temporary containers were removed.
Raw evidence is under `/tmp/blender-mcp-simplify/` on the validation machine.

No image was published and no cluster deployment changed. Package publication
remains a prerequisite for deployment.
