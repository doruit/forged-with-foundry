// -----------------------------------------------------------------------------
// Microsoft Foundry account + default project + shared GPT-5 chat deployment
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
    disableLocalAuth: true
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
// Only the model used by implemented controls is shared. Add other model types
// to a control-local deployment when their learning outcome requires them.
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
