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
