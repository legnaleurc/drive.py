#! /bin/sh

exec uv run -m app.faststart --data-path="~/.local/share/wcpan.drive/_faststart" "$@"
