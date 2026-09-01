"""Chainlit entry point for the self-contained PRI-002 demo."""

import truststore

truststore.inject_into_ssl()

from src.pri_002 import chat as _pri_002_chat  # noqa: E402, F401
