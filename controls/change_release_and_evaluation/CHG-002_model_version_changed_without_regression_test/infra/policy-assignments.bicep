targetScope = 'resourceGroup'

param approvedModelsDefinitionId string
param noAutoUpgradeDefinitionId string
param allowedAssetIds array

resource approvedModels 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'chg-002-approved-models'
  properties: {
    displayName: 'CHG-002 demo: only released model versions'
    policyDefinitionId: approvedModelsDefinitionId
    parameters: {
      effect: { value: 'Deny' }
      allowedPublishers: { value: [] }
      allowedAssetIds: { value: allowedAssetIds }
    }
    metadata: { 'control-id': 'CHG-002' }
  }
}

resource noAutoUpgrade 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'chg-002-no-auto-upgrade'
  properties: {
    displayName: 'CHG-002 demo: no automatic model upgrades'
    policyDefinitionId: noAutoUpgradeDefinitionId
    metadata: { 'control-id': 'CHG-002' }
  }
}

output approvedModelsAssignmentId string = approvedModels.id
output noAutoUpgradeAssignmentId string = noAutoUpgrade.id
