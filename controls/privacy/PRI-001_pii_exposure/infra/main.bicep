targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Name of the single-service Azure AI Language resource.')
param languageAccountName string

@description('Globally unique lowercase storage account name for native Document PII.')
@minLength(3)
@maxLength(24)
param piiStorageAccountName string

@description('Object ID of the user or service principal running the local demo.')
param deployerPrincipalId string

param piiSourceContainerName string = 'pii-source'
param piiTargetContainerName string = 'pii-redacted'

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

resource languageAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: languageAccountName
  location: location
  kind: 'TextAnalytics'
  sku: {
    name: 'S'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: languageAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource piiStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: piiStorageAccountName
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
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: piiStorage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 1
    }
  }
}

resource piiSourceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: piiSourceContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource piiTargetContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: piiTargetContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource languageStorageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(piiStorage.id, languageAccount.id, storageBlobDataContributorRoleId)
  scope: piiStorage
  properties: {
    principalId: languageAccount.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

resource deployerStorageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(piiStorage.id, deployerPrincipalId, storageBlobDataContributorRoleId)
  scope: piiStorage
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: storageBlobDataContributorRoleId
  }
}

resource deployerLanguageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(languageAccount.id, deployerPrincipalId, cognitiveServicesUserRoleId)
  scope: languageAccount
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: cognitiveServicesUserRoleId
  }
}

output languageEndpoint string = languageAccount.properties.endpoint
output piiStorageBlobEndpoint string = piiStorage.properties.primaryEndpoints.blob
output piiSourceContainerName string = piiSourceContainer.name
output piiTargetContainerName string = piiTargetContainer.name
