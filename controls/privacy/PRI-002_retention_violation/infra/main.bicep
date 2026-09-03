targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Globally unique lowercase storage account name owned by PRI-002.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Object ID of the user or service principal running the local demo.')
param deployerPrincipalId string

@description('Private container reserved for PRI-002 synthetic records.')
param containerName string = 'pri-002-retention-demo'

@description('Lifecycle classification applied to governed records.')
param lifecycleClass string = 'customer-conversation-30d'

@description('Days after modification before the lifecycle service deletes governed records.')
@minValue(1)
param retentionDays int = 30

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
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

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 1
    }
  }
}

resource demoContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}

resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-expired-pri-002-records'
          enabled: true
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: retentionDays
                }
              }
            }
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                '${containerName}/records/'
              ]
              blobIndexMatch: [
                {
                  name: 'LifecycleClass'
                  op: '=='
                  value: lifecycleClass
                }
              ]
            }
          }
        }
      ]
    }
  }
}

resource deployerStorageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, deployerPrincipalId, storageBlobDataContributorRoleId)
  scope: storage
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

output storageBlobEndpoint string = storage.properties.primaryEndpoints.blob
output containerName string = demoContainer.name
output lifecyclePolicyName string = lifecyclePolicy.name
