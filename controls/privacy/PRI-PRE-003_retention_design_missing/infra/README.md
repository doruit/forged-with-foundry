# PRI-PRE-003 infrastructure

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
