targetScope = 'resourceGroup'

@allowed(['westeurope'])
param location string = 'westeurope'
@allowed(['swedencentral'])
param foundryLocation string = 'swedencentral'
param storageName string
param searchName string
param setupPrincipalId string
param ownerObjectId string
param sourceId string = 'vpn-reset-guide'
param sourceBlob string = 'vpn-reset-guide.md'
@minValue(1)
param maximumReviewAgeDays int = 30
param policyVersion string = 'knw001-v1'
param searchIndex string = 'knw001-index'
param searchIndexer string = 'knw001-indexer'
param modelDeploymentName string = 'knw001-gpt-4-1-mini'
@minValue(1)
@maxValue(20)
param modelCapacity int = 10

var token = uniqueString(resourceGroup().id)
var tags = {
  'control-id': 'KNW-001'
  purpose: 'synthetic-knowledge-freshness-demo'
}
var foundryName = 'aif-knw001-${token}'
var projectName = 'knw-001'
var roles = {
  blobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchName
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-knw001-${token}'
  location: location
  tags: tags
  kind: 'functionapp'
  sku: { tier: 'FlexConsumption', name: 'FC1' }
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: 'func-knw001-${token}'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
        { name: 'KNW001_SOURCE_ID', value: sourceId }
        { name: 'KNW001_OWNER_OBJECT_ID', value: ownerObjectId }
        { name: 'KNW001_MAX_REVIEW_AGE_DAYS', value: string(maximumReviewAgeDays) }
        { name: 'KNW001_POLICY_VERSION', value: policyVersion }
        { name: 'KNW001_BLOB_ENDPOINT', value: storage.properties.primaryEndpoints.blob }
        { name: 'KNW001_SOURCE_CONTAINER', value: 'source' }
        { name: 'KNW001_SOURCE_BLOB', value: sourceBlob }
        { name: 'KNW001_REVIEWS_CONTAINER', value: 'reviews' }
        { name: 'KNW001_EVIDENCE_CONTAINER', value: 'evidence' }
        { name: 'KNW001_SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
        { name: 'KNW001_SEARCH_INDEX', value: searchIndex }
        { name: 'KNW001_SEARCH_INDEXER', value: searchIndexer }
        { name: 'KNW001_ACCOUNTABLE_ROLE', value: 'Knowledge Owner' }
      ]
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}deployment'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { maximumInstanceCount: 40, instanceMemoryMB: 2048 }
      runtime: { name: 'python', version: '3.12' }
    }
  }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: foundryLocation
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: projectName
  location: foundryLocation
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'KNW-001 knowledge freshness demo'
    description: 'Control-owned synthetic knowledge consumer for KNW-001.'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  dependsOn: [project]
  name: modelDeploymentName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4.1-mini', version: '2025-04-14' }
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: project
  name: 'knw001-search'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${search.name}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.id
      location: search.location
    }
  }
}

resource appBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, app.id, roles.blobDataOwner)
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobDataOwner)
  }
}

resource appSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in [roles.searchIndexDataReader, roles.searchServiceContributor]: {
  scope: search
  name: guid(search.id, app.id, role)
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]

resource projectSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in [roles.searchIndexDataReader, roles.searchServiceContributor]: {
  scope: search
  name: guid(search.id, project.id, role)
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]

resource setupProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, setupPrincipalId, roles.azureAiUser)
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.azureAiUser)
  }
}

output functionAppName string = app.name
output functionAppId string = app.id
output functionAppUrl string = 'https://${app.properties.defaultHostName}'
output functionPrincipalId string = app.identity.principalId
output planId string = plan.id
output foundryId string = foundry.id
output foundryName string = foundry.name
output foundryLocation string = foundry.location
output projectEndpoint string = 'https://${foundryName}.services.ai.azure.com/api/projects/${projectName}'
output modelDeploymentName string = model.name
output searchConnectionName string = searchConnection.name
output sourceId string = sourceId
output sourceBlob string = sourceBlob
output policyVersion string = policyVersion
output searchIndex string = searchIndex
output searchIndexer string = searchIndexer
