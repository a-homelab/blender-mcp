FROM lscr.io/linuxserver/blender:5.2.2-ls240@sha256:8b1377cca1a53009e5e2ad4bc313c21edee6abc89cf0333ef3f06b35a661be11 AS base

FROM ghcr.io/astral-sh/uv:0.12.17 AS uv

FROM base AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/mcp \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    env -u VIRTUAL_ENV uv sync --locked --no-dev --no-editable --python /lsiopy/bin/python3

FROM base
COPY --from=build /opt/mcp /opt/mcp
ENV PATH="/opt/mcp/bin:${PATH}" \
    HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BLENDER_MCP_HOST=127.0.0.1 \
    BLENDER_MCP_PORT=9876
WORKDIR /workspace
USER 1000:1000
EXPOSE 8000
ENTRYPOINT ["/opt/mcp/bin/blender-mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
