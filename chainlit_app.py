"""Chainlit entry point for the PRI-001 governance demonstration."""

import truststore

# Preserve TLS verification while honoring enterprise certificates installed in
# the operating-system trust store.
truststore.inject_into_ssl()

# Importing the module registers its Chainlit lifecycle handlers.
from app.pri_001 import chat as _pri_001_chat  # noqa: F401
