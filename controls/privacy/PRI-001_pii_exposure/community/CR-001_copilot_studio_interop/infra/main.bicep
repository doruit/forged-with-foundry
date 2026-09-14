targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Globally unique App Service name hosting the CR-001 MCP server.')
param appServiceName string

@description('Name of the App Service Plan (Linux) backing the CR-001 App Service.')
param appServicePlanName string

@description('Name of the existing Azure AI Language account owned by PRI-001.')
param languageAccountName string

@description('Name of the existing PII storage account owned by PRI-001.')
param piiStorageAccountName string

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

resource languageAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: languageAccountName
}

resource piiStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: piiStorageAccountName
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
}

resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: appServiceName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.13'
      alwaysOn: true
      appCommandLine: 'python -m uvicorn src.cr001_interop.mcp_server:create_app --factory --host 0.0.0.0 --port 8000'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'AZURE_LANGUAGE_ENDPOINT'
          value: languageAccount.properties.endpoint
        }
        {
          name: 'PII_STORAGE_BLOB_ENDPOINT'
          value: piiStorage.properties.primaryEndpoints.blob
        }
        {
          name: 'PII_SOURCE_CONTAINER'
          value: piiSourceContainerName
        }
        {
          name: 'PII_TARGET_CONTAINER'
          value: piiTargetContainerName
        }
        {
          name: 'CR001_EVIDENCE_PATH'
          value: '/home/data/interop_evidence.jsonl'
        }
      ]
    }
  }
}

resource languageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(languageAccount.id, appService.id, cognitiveServicesUserRoleId)
  scope: languageAccount
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(piiStorage.id, appService.id, storageBlobDataContributorRoleId)
  scope: piiStorage
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output appServiceHostName string = appService.properties.defaultHostName
output appServiceName string = appService.name
