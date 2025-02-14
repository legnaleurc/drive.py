#! /bin/sh

OPENSSL_CONF=./assets/openssl.cnf exec uv run -m app.jav "$@"
