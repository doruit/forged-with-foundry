# VAL-PRE-001 infrastructure

This control deploys only:

1. a subscription-scope custom Azure Policy definition with `deny`;
2. a resource-group-scoped assignment of that definition.

The demo target is submitted only to `az deployment group validate`, so no
workload is created. A pre-existing resource group is required. Deploy and
clean up with:

```bash
./infra/deploy.sh
./infra/cleanup.sh
```

The scripts never delete the resource group or shared repository resources.
Creating the custom definition requires subscription-scope policy permissions.

## Table of contents

* [Optional: GitHub Actions OIDC identity](#optional-github-actions-oidc-identity)

## Optional: GitHub Actions OIDC identity

`oidc-identity.bicep`, `deploy-oidc.sh`, and `cleanup-oidc.sh` are a separate,
optional extension used only by
`.github/workflows/val-pre-001-value-gate-demo.yml`. They provision a
user-assigned managed identity, a federated credential trusting the
repository's `production` GitHub Environment, and a **Monitoring
Contributor** role assignment scoped to the resource group (not
`Contributor`). Not required for the core demo above; see the control's
README, "Optional: run the real CI/CD + OIDC gate demo".
