targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Globally unique lowercase storage account name owned by PRI-003.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Object ID of the user or service principal running the local demo.')
param deployerPrincipalId string

@description('Table name reserved for PRI-003 synthetic DSR records (alphanumeric only).')
param tableName string = 'pri003dsrrequests'

// Built-in "Storage Table Data Contributor" role.
// Verify this GUID against current Azure RBAC documentation before reuse.
var storageTableDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
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

output storageTableEndpoint string = storage.properties.primaryEndpoints.table
output tableName string = demoTable.name
