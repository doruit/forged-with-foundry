"""Chainlit entry point for the AUT-002 live demo."""

import truststore
import os

truststore.inject_into_ssl()

from src.aut_002 import cloud_chat as _aut_002_chat  # noqa: E402, F401

if os.environ.get("AUT002_WORKFLOW_ENABLED") == "true":
	from chainlit.server import app
	from src.aut_002.teams import install

	install(app)