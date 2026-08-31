// -----------------------------------------------------------------------------
// Microsoft Foundry account + default project + latest GPT-5 model deployments
// -----------------------------------------------------------------------------

targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the Foundry (AI Services) account. Must be globally unique.')
param foundryAccountName string

@description('Name of the default Foundry project.')
param foundryProjectName string = 'default-project'

@description('Friendly display name for the default project.')
param foundryProjectDisplayName string = 'Governance Controls Demo'

@description('Capacity (in thousands of TPM) for the gpt-5 deployment.')
param gpt5Capacity int = 50

@description('Capacity (in thousands of TPM) for the gpt-5-mini deployment.')
param gpt5MiniCapacity int = 50

@description('Capacity (in thousands of TPM) for the text-embedding-3-large deployment.')
param embeddingCapacity int = 50

@description('Name of the single-service Azure AI Language resource.')
param languageAccountName string

@description('Globally unique, lowercase name of the storage account used by native Document PII.')
@minLength(3)
@maxLength(24)
param piiStorageAccountName string

@description('Object ID of the user or service principal running the demo locally.')
param deployerPrincipalId string

@description('Source container used for native documents before PII enforcement.')
param piiSourceContainerName string = 'pii-source'

@description('Target container used for Azure AI Language redacted documents and structured results.')
param piiTargetContainerName string = 'pii-redacted'

var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

// ----------------------------------------------------------------------------
// Foundry account (Cognitive Services, kind = AIServices)
// ----------------------------------------------------------------------------
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    // Enable the Foundry (project-based) experience
    allowProjectManagement: true
    // Custom subdomain is required for token-based (Entra ID) auth
    customSubDomainName: foundryAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ----------------------------------------------------------------------------
// Default Foundry project
// ----------------------------------------------------------------------------
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: foundryProjectDisplayName
    description: 'Default project for the AI governance controls demo.'
  }
}

// ----------------------------------------------------------------------------
// Deterministic PII enforcement infrastructure
// Native Document PII requires a single-service Language resource and Blob
// source/target locations. The Foundry AIServices account is intentionally not
// reused for this governance boundary.
// ----------------------------------------------------------------------------
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

resource piiStorage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
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

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-06-01' = {
  parent: piiStorage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 1
    }
  }
}

resource piiSourceContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01' = {
  parent: blobService
  name: piiSourceContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource piiTargetContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01' = {
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

// ----------------------------------------------------------------------------
// Model deployments
// Deployed serially (dependsOn chain) because an account can only process one
// deployment change at a time.
// ----------------------------------------------------------------------------
resource gpt5 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'gpt-5'
  sku: {
    name: 'GlobalStandard'
    capacity: gpt5Capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource gpt5Mini 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'gpt-5-mini'
  sku: {
    name: 'GlobalStandard'
    capacity: gpt5MiniCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [
    gpt5
  ]
}

resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'text-embedding-3-large'
  sku: {
    name: 'GlobalStandard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [
    gpt5Mini
  ]
}

// ----------------------------------------------------------------------------
// Outputs
// ----------------------------------------------------------------------------
@description('The Foundry account resource ID.')
output accountId string = account.id

@description('The Foundry account endpoint.')
output accountEndpoint string = account.properties.endpoint

@description('The default Foundry project endpoint (use this for AZURE_AI_PROJECT_ENDPOINT).')
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'

@description('Deployed chat model deployment name.')
output chatDeploymentName string = gpt5.name

@description('Deployed mini chat model deployment name.')
output miniDeploymentName string = gpt5Mini.name

@description('Deployed embedding model deployment name.')
output embeddingDeploymentName string = embedding.name

@description('Single-service Azure AI Language endpoint used by Text PII and Document PII.')
output languageEndpoint string = languageAccount.properties.endpoint

@description('Blob service endpoint used by native Document PII.')
output piiStorageBlobEndpoint string = piiStorage.properties.primaryEndpoints.blob

output piiSourceContainerName string = piiSourceContainer.name
output piiTargetContainerName string = piiTargetContainer.name
