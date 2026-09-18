targetScope = 'resourceGroup'

@description('Optional extension, not part of the core demo. Provisions the GitHub Actions OIDC identity used only by .github/workflows/val-pre-001-value-gate-demo.yml.')
param identityName string = 'id-val-pre-001-github-oidc'

@description('GitHub repository in "owner/repo" form trusted to federate as this identity.')
param githubRepository string

@description('GitHub Actions environment name trusted for the federated credential.')
param githubEnvironment string = 'production'

// Built-in "Monitoring Contributor" role: the least-privilege built-in role that can
// create and manage the Microsoft.Insights/actionGroups resource this control's
// demo-target.bicep declares. Deliberately narrower than "Contributor".
// https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/monitor
var monitoringContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '749f88d5-cbae-40b8-bcfc-e573ddc772fa'
)

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: resourceGroup().location
  tags: {
    'control-id': 'VAL-PRE-001'
    purpose: 'github-actions-oidc-demo'
  }
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identity
  name: 'github-${githubEnvironment}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepository}:environment:${githubEnvironment}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, monitoringContributorRoleId)
  scope: resourceGroup()
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: monitoringContributorRoleId
  }
}

output identityClientId string = identity.properties.clientId
output identityPrincipalId string = identity.properties.principalId
output identityResourceId string = identity.id
