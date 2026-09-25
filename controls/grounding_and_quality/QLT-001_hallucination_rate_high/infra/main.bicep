targetScope = 'resourceGroup'

// This deployment provisions the Log Analytics workspace and Application
// Insights resource Continuous Evaluation writes groundedness/relevance/
// retrieval scores to, registers that Application Insights resource as a
// connection on the existing Foundry project (required -- confirmed live
// 2026-09-24 that evaluation_rules.create_or_update() 403s with "Principal
// does not have access to API/Operation" until this connection exists, even
// with the Foundry User role already granted), and grants the project's
// managed identity the two roles Continuous Evaluation needs end to end:
// Foundry User on the project (confirmed required for evaluation_rules
// access) and Monitoring Reader on Application Insights itself (confirmed
// required for the rule to actually read sampled traces). The Foundry
// project, model deployment, prompt agent, the Eval definition, and the
// continuous-evaluation rule itself are configured separately -- see
// README.md and docs/IMPLEMENTATION.md for the current evidence boundary.

param location string = resourceGroup().location
param publisherPrincipalId string = ''
param publisherPrincipalType string = 'ServicePrincipal'
param foundryAccountName string
param foundryProjectName string
param foundryProjectPrincipalId string

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

// Monitoring Metrics Publisher on Application Insights, for whichever
// identity actually runs demo.py's client-side telemetry export (not
// necessarily the Foundry project's own managed identity -- see
// foundryProjectPrincipalId's roles below, which are for reading, not
// publishing). Confirmed live (2026-09-25) this is required in addition to
// passing `credential=` to `configure_azure_monitor()`: because `insights`
// above has `DisableLocalAuth: true`, ingestion requires Entra ID auth, and
// Entra-authenticated ingestion calls still 403 without this specific role --
// Monitoring Reader (granted to foundryProjectPrincipalId below) does not
// cover publishing, only reading. See docs/IMPLEMENTATION.md for the current prerequisite summary.
resource publisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(publisherPrincipalId)) {
  name: guid(insights.id, publisherPrincipalId, 'metrics-publisher')
  scope: insights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
    principalId: publisherPrincipalId
    principalType: publisherPrincipalType
  }
}

// Foundry account/project already exist (provisioned by azd's Foundry
// provider in a separate deployment) -- referenced here only to attach the
// Application Insights connection and role assignments Continuous
// Evaluation needs.
resource foundryAccount 'Microsoft.CognitiveServices/accounts@2026-07-15-preview' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2026-07-15-preview' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2026-07-15-preview' = {
  parent: foundryProject
  name: 'appinsights-connection'
  properties: {
    category: 'AppInsights'
    target: insights.id
    authType: 'ApiKey'
    credentials: {
      key: insights.properties.ConnectionString
    }
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: insights.id
    }
  }
}

// Foundry User on the project: confirmed live (2026-09-24) required for
// evaluation_rules.create_or_update() to succeed at all on a prompt-kind
// agent -- without it, the call 403s even though the agent kind itself is
// accepted.
resource foundryUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(foundryProjectPrincipalId)) {
  name: guid(foundryProject.id, foundryProjectPrincipalId, 'foundry-user')
  scope: foundryProject
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Monitoring Reader on Application Insights: confirmed live (2026-09-24)
// required in addition to Foundry User -- without it, rule creation still
// 403s with a generic "Principal does not have access to API/Operation"
// even after the connection above exists and Foundry User is granted.
resource monitoringReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(foundryProjectPrincipalId)) {
  name: guid(insights.id, foundryProjectPrincipalId, 'monitoring-reader')
  scope: insights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '43d0d8ad-25c7-4714-9337-8ba259a9fe05')
    principalId: foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Log Analytics Reader on the workspace: confirmed live (2026-09-25)
// distinct from Monitoring Reader on Application Insights above -- Monitoring
// Reader alone was not sufficient to read the sampled traces back out of the
// linked Log Analytics workspace once they existed.
resource logAnalyticsReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(foundryProjectPrincipalId)) {
  name: guid(workspace.id, foundryProjectPrincipalId, 'log-analytics-reader')
  scope: workspace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '73c42c96-874c-492b-b04d-ab87d138a893')
    principalId: foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output workspaceId string = workspace.properties.customerId
output workspaceResourceId string = workspace.id
output applicationInsightsId string = insights.id
@secure()
output connectionString string = insights.properties.ConnectionString
