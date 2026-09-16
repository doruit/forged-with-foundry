targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Globally unique App Service name hosting the CR-001 MCP server.')
param appServiceName string

@description('Globally unique App Service name hosting the CR-001 A2A server.')
param a2aAppServiceName string

@description('Name of the App Service Plan (Linux) backing the CR-001 App Services.')
param appServicePlanName string

@description('Name of the existing Azure AI Language account owned by PRI-001.')
param languageAccountName string

@description('Name of the existing PII storage account owned by PRI-001.')
param piiStorageAccountName string

@description('Name of the shared Foundry account provisioned by the repo-root infra.')
param foundryAccountName string

@description('Name of the shared Foundry project provisioned by the repo-root infra.')
param foundryProjectName string

@description('Chat model deployment name used by the A2A variant\'s governed Foundry agent.')
param foundryChatDeploymentName string = 'gpt-5'

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
// Foundry User: data-plane access to a Foundry project (not Azure AI Developer,
// whose own description defers project-scoped access to this role instead).
var foundryUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '53ca6127-db72-4b80-b1b0-d745d6d5456d'
)

resource languageAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: languageAccountName
}

resource piiStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: piiStorageAccountName
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
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

// --- A2A App Service: same plan as MCP, plus access to the shared Foundry project ---

resource a2aAppService 'Microsoft.Web/sites@2023-12-01' = {
  name: a2aAppServiceName
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
      appCommandLine: 'python -m uvicorn src.cr001_interop.a2a_server:create_app --factory --host 0.0.0.0 --port 8000'
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
          name: 'AZURE_AI_PROJECT_ENDPOINT'
          value: 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
        }
        {
          name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
          value: foundryChatDeploymentName
        }
        {
          name: 'CR001_EVIDENCE_PATH'
          value: '/home/data/interop_evidence.jsonl'
        }
      ]
    }
  }
}

resource a2aLanguageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(languageAccount.id, a2aAppService.id, cognitiveServicesUserRoleId)
  scope: languageAccount
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: a2aAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource a2aFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, a2aAppService.id, foundryUserRoleId)
  scope: foundryAccount
  properties: {
    roleDefinitionId: foundryUserRoleId
    principalId: a2aAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output appServiceHostName string = appService.properties.defaultHostName
output appServiceName string = appService.name
output a2aAppServiceHostName string = a2aAppService.properties.defaultHostName
output a2aAppServiceName string = a2aAppService.name
