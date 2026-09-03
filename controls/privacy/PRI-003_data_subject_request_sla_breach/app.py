"""Chainlit entry point for the self-contained PRI-003 demo."""

import truststore

truststore.inject_into_ssl()

from src.pri_003 import chat as _pri_003_chat  # noqa: E402, F401
