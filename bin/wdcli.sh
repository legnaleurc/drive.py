#! /bin/sh

export UV_NO_SYNC=1
export UV_FROZEN=1

exec uv run -m wcpan.drive.cli -c "$HOME/.config/wcpan.drive/cli.yaml" "$@"
