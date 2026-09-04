targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Globally unique lowercase storage account name owned by PRI-PRE-001.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Object ID of the user or service principal running the local demo.')
param deployerPrincipalId string

@description('Table name reserved for PRI-PRE-001 synthetic project records (alphanumeric only).')
param tableName string = 'pripre001projects'

@description('Resource ID of the PRI-PRE-001 DPIA-gate policy definition (subscription-scope deployment output).')
param policyDefinitionId string

@description('Name for the resource-group-scoped policy assignment.')
param policyAssignmentName string = 'pri-pre-001-dpia-gate-assignment'

// Built-in "Storage Table Data Contributor" role.
// Verify this GUID against current Azure RBAC documentation before reuse.
var storageTableDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
)

// Built-in "Monitoring Contributor" role. `az deployment group validate` needs
// write permission on the placeholder resource type even though nothing is
// ever created; scoped to the resource group because a role assignment cannot
// target a resource that is never actually created (validate-only, by design).
var monitoringContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '749f88d5-cbae-40b8-bcfc-e573ddc772fa'
)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    isHnsEnabled: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource demoTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: tableName
}

resource deployerTableAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, deployerPrincipalId, storageTableDataContributorRoleId)
  scope: storage
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: storageTableDataContributorRoleId
  }
}

resource deployerValidateAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deployerPrincipalId, monitoringContributorRoleId)
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: monitoringContributorRoleId
  }
}

// deny effect needs no managed identity; the assignment applies at this deployment's own scope.
resource dpiaGateAssignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: policyAssignmentName
  properties: {
    displayName: 'PRI-PRE-001: DPIA gate (resource group scope)'
    policyDefinitionId: policyDefinitionId
    enforcementMode: 'Default'
  }
}

output storageTableEndpoint string = storage.properties.primaryEndpoints.table
output tableName string = demoTable.name
output policyAssignmentId string = dpiaGateAssignment.id
