# PRI-PRE-002 infrastructure

This incremental deployment owns the Azure resources required by
PRI-PRE-002, in **two stages**:

1. A **subscription-scope** custom Azure Policy definition
   (`policy-definition.bicep`) that, in production, flags (`audit`, does
   not block) any resource tagged `personalDataProcessing=true` unless
   `lawfulBasis` is one of the six GDPR Article 6(1) categories and the
   `purposeId` tag is present.
2. The usual **resource-group-scope** resources (`main.bicep`): a
   dedicated OAuth-only Table Storage account, one private table reserved
   for synthetic AI-system/project records, a policy **assignment**
   binding the subscription-scope definition to this resource group, and
   scoped RBAC for the local demo identity.

Unlike PRI-PRE-001, no extra RBAC exception is needed here — `audit`
never creates or validates a placeholder resource, so the demo identity
only needs **Storage Table Data Contributor** on the storage account.
