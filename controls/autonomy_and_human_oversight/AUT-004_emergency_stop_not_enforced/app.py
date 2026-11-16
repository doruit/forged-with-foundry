"""Chainlit entry point for the AUT-004 live demo on App Service."""

import truststore

truststore.inject_into_ssl()

from src.aut_004 import chat as _aut_004_chat  # noqa: E402, F401
