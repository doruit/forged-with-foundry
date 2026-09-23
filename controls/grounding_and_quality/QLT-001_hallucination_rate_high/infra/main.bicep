targetScope = 'resourceGroup'

// This deployment provisions only the Log Analytics workspace and Application
// Insights resource used to query Continuous Evaluation's groundedness
// scores. The Foundry project, model deployment, hosted agent, the Eval
// definition (groundedness evaluator), and the continuous-evaluation rule
// itself are configured separately -- the Eval definition and rule through
// the Foundry portal's "Set up continuous evaluation" flow (see README.md
// Implementation), not through this file. See ASSESSMENT.md for why that
// split is the documented, non-preview core path.

param location string = resourceGroup().location
param publisherPrincipalId string = ''
param publisherPrincipalType string = 'ServicePrincipal'

// Deliberately avoids resourceGroup() in this top-level variable: azd's
// Foundry provider composes this template into a subscription-scope
// deployment when reusing an existing AI project, and resourceGroup() is
// not a valid intrinsic function at that evaluation point (confirmed by a
// real ARM InvalidTemplate error during this control's first live deploy).
var suffix = uniqueString(subscription().id, 'QLT-001', deployment().name)
var tags = {
  'control-id': 'QLT-001'
  purpose: 'synthetic-groundedness-demo'
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-qlt001-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.1') }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-qlt001-${suffix}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableLocalAuth: true
    IngestionMode: 'LogAnalytics'
    RetentionInDays: 30
  }
}

resource publisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(publisherPrincipalId)) {
  name: guid(insights.id, publisherPrincipalId, 'metrics-publisher')
  scope: insights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
    principalId: publisherPrincipalId
    principalType: publisherPrincipalType
  }
}

output workspaceId string = workspace.properties.customerId
output workspaceResourceId string = workspace.id
output applicationInsightsId string = insights.id
@secure()
output connectionString string = insights.properties.ConnectionString
