targetScope = 'resourceGroup'

@description('Existing shared Foundry account created by the root infra/ deployment.')
param foundryAccountName string

@description('Existing shared model deployment on that account.')
param modelDeploymentName string

@description('Object ID of the operator running the demo: holds the red button (App Configuration Data Owner).')
param operatorPrincipalId string

param location string = resourceGroup().location
param projectName string = 'aut-004'
param suffix string = uniqueString(resourceGroup().id, 'aut-004')

var appName = 'aut004-${suffix}'
var tags = {
  'control-id': 'AUT-004'
  purpose: 'synthetic-emergency-stop-demo'
}
var roles = {
  foundryUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  appConfigDataReader: '516239f1-63e1-4d78-a4de-a74fb236a071'
  appConfigDataOwner: '5ae67dd6-50cb-40e7-96ff-dc2bfa4b606b'
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
    displayName: 'AUT-004 emergency stop demo'
    description: 'Control-owned project for the synthetic AUT-004 support refunds agent.'
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${appName}-identity'
  location: location
  tags: tags
}

// The stop switch lives here, outside the agent runtime.
resource store 'Microsoft.AppConfiguration/configurationStores@2024-06-01' = {
  name: '${appName}-switch'
  location: location
  tags: tags
  sku: { name: 'free' }
  properties: {
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

// Who pressed stop and who recovered: App Configuration's own audit log.
resource auditLogs 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: store
  name: 'aut004-audit-to-logs'
  properties: {
    workspaceId: workspace.id
    logs: [
      { category: 'Audit', enabled: true }
    ]
  }
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
        { name: 'AUT004_APPCONFIG_ENDPOINT', value: store.properties.endpoint }
        { name: 'AUT004_TENANT_ID', value: tenant().tenantId }
        { name: 'AUT004_EVIDENCE_DIR', value: '/home/aut004/evidence' }
        { name: 'OVERRIDE_USE_MI_FIC_ASSERTION_CLIENTID', value: identity.properties.clientId }
        { name: 'WEBSITE_AUTH_USE_LEGACY_CLAIMS', value: 'false' }
        { name: 'CHAINLIT_NO_TELEMETRY', value: 'true' }
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

// Runtime: read the switch, never write it.
resource runtimeSwitchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: store
  name: guid(store.id, identity.id, 'aut004-switch-reader')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.appConfigDataReader)
  }
}

// Operator: the red button and the recovery.
resource operatorSwitchOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: store
  name: guid(store.id, operatorPrincipalId, 'aut004-switch-owner')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.appConfigDataOwner)
  }
}

resource runtimeFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, identity.id, 'aut004-runtime-foundry-user')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
  }
}

resource runtimeInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, identity.id, 'aut004-inference')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
  }
}

resource operatorFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, operatorPrincipalId, 'aut004-operator-foundry-user')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.foundryUser)
  }
}

output projectId string = project.id
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
output webAppName string = app.name
output webAppId string = app.id
output webAppUrl string = 'https://${app.properties.defaultHostName}'
output planId string = plan.id
output identityId string = identity.id
output identityPrincipalId string = identity.properties.principalId
output storeId string = store.id
output storeEndpoint string = store.properties.endpoint
output workspaceId string = workspace.id
output roleAssignmentIds array = [
  runtimeSwitchReader.id
  operatorSwitchOwner.id
  runtimeFoundryUser.id
  runtimeInference.id
  operatorFoundryUser.id
]
