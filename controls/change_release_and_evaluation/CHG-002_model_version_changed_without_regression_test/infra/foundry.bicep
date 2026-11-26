// One control-owned Foundry account, project and model deployments.
// Deployed twice by deploy.sh: an evaluation stage and a production stage,
// each in its own resource group, so the production Azure Policy allow-list
// never blocks evaluating a candidate that is not yet approved.
targetScope = 'resourceGroup'

@allowed(['eval', 'prod'])
param stage string
param accountName string
param location string = resourceGroup().location
@description('Object ID of the person running the demo; granted Foundry User on the project.')
param setupPrincipalId string
@description('Model deployments: [{ name, model: { format, name, version }, sku: { name, capacity }, versionUpgradeOption }].')
param deployments array

var tags = {
  'control-id': 'CHG-002'
  purpose: 'synthetic-model-change-gate-demo'
  stage: stage
}
// Foundry User (formerly Azure AI User): agents, responses and evaluations.
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
// Cognitive Services OpenAI User: lets the project's identity call the judge and agent models.
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: 'chg-002-${stage}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'CHG-002 ${stage}'
    description: 'Control-owned ${stage} project for the synthetic CHG-002 support assistant.'
  }
}

@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [for d in deployments: {
  parent: account
  name: d.name
  dependsOn: [project]
  sku: d.sku
  tags: tags
  properties: {
    model: d.model
    versionUpgradeOption: d.versionUpgradeOption
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}]

resource setupFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, setupPrincipalId, 'chg-002-foundry-user')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

resource projectOpenAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, project.id, 'chg-002-openai-user')
  properties: {
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
  }
}

output accountName string = account.name
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${project.name}'
