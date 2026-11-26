// Independent ARM route: Azure Policy on the production resource group.
// 1. Built-in "Foundry model deployments should only use approved models" (GA)
//    with Deny and an allow-list of full model asset IDs (one version each).
// 2. Custom definition that denies model deployments set to upgrade themselves,
//    because an automatic upgrade is a model change without a regression test.
targetScope = 'subscription'

param prodResourceGroupName string
@description('Full asset IDs (including version) of released models plus the judge model.')
param allowedAssetIds array

var approvedModelsDefinitionId = '/providers/Microsoft.Authorization/policyDefinitions/aafe3651-cb78-4f68-9f81-e7e41509110f'

resource noAutoUpgrade 'Microsoft.Authorization/policyDefinitions@2023-04-01' = {
  name: 'chg-002-deny-model-auto-upgrade'
  properties: {
    displayName: 'CHG-002 demo: model deployments must not upgrade automatically'
    description: 'Denies Foundry model deployments whose versionUpgradeOption is not NoAutoUpgrade. Synthetic demo definition owned by CHG-002.'
    policyType: 'Custom'
    mode: 'All'
    metadata: { category: 'Cognitive Services', 'control-id': 'CHG-002' }
    policyRule: {
      if: {
        allOf: [
          { field: 'type', equals: 'Microsoft.CognitiveServices/accounts/deployments' }
          { field: 'Microsoft.CognitiveServices/accounts/deployments/versionUpgradeOption', notEquals: 'NoAutoUpgrade' }
        ]
      }
      then: { effect: 'deny' }
    }
  }
}

module assignments 'policy-assignments.bicep' = {
  name: 'chg-002-policy-assignments'
  scope: resourceGroup(prodResourceGroupName)
  params: {
    approvedModelsDefinitionId: approvedModelsDefinitionId
    noAutoUpgradeDefinitionId: noAutoUpgrade.id
    allowedAssetIds: allowedAssetIds
  }
}

output noAutoUpgradeDefinitionId string = noAutoUpgrade.id
output approvedModelsAssignmentId string = assignments.outputs.approvedModelsAssignmentId
output noAutoUpgradeAssignmentId string = assignments.outputs.noAutoUpgradeAssignmentId
