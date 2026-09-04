# PRI-PRE-001 infrastructure

This incremental deployment owns the Azure resources required by
PRI-PRE-001, in **two stages**:

1. A **subscription-scope** custom Azure Policy definition
   (`policy-definition.bicep`) that, in production, denies any resource
   tagged `aiSystemHighRisk=true` unless `dpiaRequired=no` (a conscious
   "not required" declaration) or the `requestorEmail`, `dpiaApprover`,
   and `dpiaCaseId` tags are all present.
2. The usual **resource-group-scope** resources (`main.bicep`): a
   dedicated OAuth-only Table Storage account, one private table reserved
   for synthetic AI-system/project records, a policy **assignment**
   binding the subscription-scope definition to this resource group, and
   scoped RBAC for the local demo identity.

Deploying the policy definition requires **Resource Policy Contributor (or
equivalent) at subscription scope** — a more elevated, one-time
prerequisite than any other control in this repository needs. Running the
demo afterward only needs the narrower resource-group-scoped roles granted
by stage 2.

Deploy the shared Foundry resources first with the repository-level
deployment. Then, from the repository root, run:

```bash
./controls/privacy/PRI-PRE-001_dpia_required_but_missing/infra/deploy.sh
```

The script reads generic settings from the repository's shared
`infra/.env`, reads control settings from the PRI-PRE-001 `.env`, deploys
both stages, and writes the policy definition/assignment IDs and table
endpoint back to the PRI-PRE-001 `.env`.

The demo's "go-live attempt" never creates a real resource — it calls
`az deployment group validate` against a trivial placeholder template,
which genuinely triggers Azure Policy's `deny` evaluation
(`RequestDisallowedByPolicy`) without provisioning anything billable. See
[Azure Policy definition structure — policy rules](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-policy-rule)
and
[Azure Policy definitions effect basics](https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics).
