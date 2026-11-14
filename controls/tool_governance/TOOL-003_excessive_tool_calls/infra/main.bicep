targetScope = 'resourceGroup'

@description('Existing shared Foundry account created by the root infra/ deployment.')
param foundryAccountName string

@description('Object ID of the person running the demo; granted Foundry User on this project only.')
param setupPrincipalId string

param location string = resourceGroup().location
param projectName string = 'tool-003'

var tags = {
  'control-id': 'TOOL-003'
  purpose: 'synthetic-tool-call-budget-demo'
}

// Foundry User (formerly Azure AI User): data-plane access to agents and responses.
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

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
    displayName: 'TOOL-003 tool-call budget demo'
    description: 'Control-owned project for the synthetic TOOL-003 support refunds agent.'
  }
}

resource setupFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, setupPrincipalId, 'tool-003-foundry-user')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

output projectId string = project.id
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
output roleAssignmentId string = setupFoundryUser.id
