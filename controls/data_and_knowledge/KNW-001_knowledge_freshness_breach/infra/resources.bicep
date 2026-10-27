targetScope = 'resourceGroup'

param location string
param setupPrincipalId string

var token = uniqueString(resourceGroup().id)
var tags = {
  'control-id': 'KNW-001'
  purpose: 'synthetic-knowledge-freshness-demo'
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stknw001${token}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    accessTier: 'Hot'
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: false }
    containerDeleteRetentionPolicy: { enabled: false }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for name in ['source', 'reviews', 'evidence', 'deployment'] : {
  parent: blobs
  name: name
  properties: { publicAccess: 'None' }
}]

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-knw001-${token}'
  location: location
  tags: tags
  sku: { name: 'free' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    disableLocalAuth: true
    publicNetworkAccess: 'enabled'
  }
}

resource setupStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, setupPrincipalId, 'blob-contributor')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource setupSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in ['7ca78c08-252a-4471-8644-bb5ff32d4ba0', '1407120a-92aa-4202-b7e9-c0e197c71c8f'] : {
  scope: search
  name: guid(search.id, setupPrincipalId, role)
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]

output storageName string = storage.name
output storageId string = storage.id
output blobEndpoint string = storage.properties.primaryEndpoints.blob
output searchName string = search.name
output searchId string = search.id
output searchEndpoint string = 'https://${search.name}.search.windows.net'
