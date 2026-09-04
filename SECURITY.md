# Security policy

## Scope

Forged with Foundry is a demonstration repository. Every control uses
synthetic data only and is designed to fail closed. That said, real Azure
resources are deployed by several demos, so genuine security issues
(privilege escalation, an unintended public endpoint, a broken fail-closed
path, a secret committed to the repository, etc.) are still taken seriously.

## Reporting a vulnerability

Please do **not** open a public issue for a security concern. Instead, use
GitHub's private reporting:

1. Go to the repository's **Security** tab.
2. Select **Report a vulnerability** to open a private security advisory.

This lets a maintainer triage the report without exposing exploit details
publicly before a fix is available.

## What to include

- The control ID (e.g., `PRI-004`) or file path affected.
- Steps to reproduce, using synthetic data only.
- The potential impact (e.g., data exposure, privilege escalation, a
  fail-closed control that fails open).

## What to expect

This is a community demo repository maintained on a best-effort basis. There
is no guaranteed response SLA, but reports are reviewed and acknowledged as
soon as reasonably possible.
