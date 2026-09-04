# PRI-PRE-002 infrastructure

This control deploys only:

1. a subscription-scope custom Azure Policy definition with `audit`;
2. a resource-group-scoped assignment of that definition.

The core demo separately creates one disabled Action Group with no receivers so
Azure can report a real compliance state. Remove that target before cleaning up
the policy:

```bash
./demo.sh cleanup
./infra/cleanup.sh
```

The scripts never delete the resource group or shared repository resources.
Creating the custom definition requires subscription-scope policy permissions.

If you deployed an older Table Storage/Chainlit version of this control,
incremental deployment does not automatically delete that retired storage
account or its old role assignments. Verify their names before removing them.
