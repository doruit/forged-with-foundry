targetScope = 'resourceGroup'

param location string = resourceGroup().location
param publisherPrincipalId string = ''
param publisherPrincipalType string = 'ServicePrincipal'

var suffix = uniqueString(resourceGroup().id, 'VAL-002')
var tags = {
  'control-id': 'VAL-002'
  purpose: 'synthetic-benefits-realisation-demo'
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-val002-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.1') }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-val002-${suffix}'
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
