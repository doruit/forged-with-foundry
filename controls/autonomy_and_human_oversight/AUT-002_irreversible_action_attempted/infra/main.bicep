targetScope = 'resourceGroup'

param location string = resourceGroup().location
param foundryAccountName string
param setupPrincipalId string
param projectName string = 'aut-002'
param modelDeploymentName string = 'aut-002-gpt-5'
param modelCapacity int = 10
param appName string = 'aut002-${uniqueString(resourceGroup().id)}'
param mandateSha256 string = ''

var tags = {
  'control-id': 'AUT-002'
  purpose: 'synthetic-irreversible-action-demo'
  autonomyBoundaryStatus: 'complete'
  humanGatesStatus: 'complete'
  mandateSha256: mandateSha256
}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'AUT-002 irreversible action demo'
    description: 'Control-owned synthetic action governed through ACS.'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  dependsOn: [project]
  name: modelDeploymentName
  sku: { name: 'GlobalStandard', capacity: modelCapacity }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-5', version: '2025-08-07' }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-identity'
  location: location
  tags: tags
}

resource plan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: '${appName}-plan'
  location: location
  kind: 'linux'
  tags: tags
  sku: { name: 'B1', tier: 'Basic', capacity: 1 }
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2024-11-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      appCommandLine: 'python -m chainlit run app.py --host 0.0.0.0 --port 8000 --headless'
      alwaysOn: true
      webSocketsEnabled: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
        { name: 'AZURE_AI_PROJECT_ENDPOINT', value: 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${projectName}' }
        { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: modelDeploymentName }
        { name: 'AUT002_TENANT_ID', value: tenant().tenantId }
        { name: 'AUT002_EVIDENCE_DIR', value: '/home/aut002/evidence' }
        { name: 'OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID', value: identity.properties.clientId }
        { name: 'WEBSITE_AUTH_USE_LEGACY_CLAIMS', value: 'false' }
      ]
    }
  }
}

resource authentication 'Microsoft.Web/sites/config@2024-11-01' = {
  parent: app
  name: 'authsettingsV2'
  properties: {
    platform: { enabled: true, runtimeVersion: '~1' }
    globalValidation: { requireAuthentication: true, unauthenticatedClientAction: 'Return401' }
  }
}

resource runtimeRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, identity.id, 'runtime-foundry-user')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

resource inferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, identity.id, 'inference')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

resource setupRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, setupPrincipalId, 'setup')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

output webAppName string = app.name
output webAppId string = app.id
output webAppUrl string = 'https://${app.properties.defaultHostName}'
output planId string = plan.id
output identityId string = identity.id
output identityClientId string = identity.properties.clientId
output identityPrincipalId string = identity.properties.principalId
output projectId string = project.id
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
output modelId string = model.id
output modelDeploymentName string = model.name
output roleAssignmentIds array = [runtimeRole.id, inferenceRole.id, setupRole.id]