#! /bin/sh

export UV_NO_SYNC=1
export UV_FROZEN=1

exec uv run -m app.cg "$@"
