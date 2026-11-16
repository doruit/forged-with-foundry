targetScope = 'resourceGroup'

@description('Existing shared Foundry account created by the root infra/ deployment.')
param foundryAccountName string

@description('Object ID of the person running the demo.')
param setupPrincipalId string

@description('Deploy the Azure Monitor notification path (Application Insights, log alert, action group). Set false where subscription policy disallows these resource types; the inline ACS stop works either way.')
param enableAlerting bool = true

@secure()
@description('Email address of the AI Ops Lead who receives the loop alert. Secure so it stays out of deployment history.')
param alertEmail string = ''

param location string = resourceGroup().location
param projectName string = 'run-006'
param suffix string = uniqueString(resourceGroup().id, 'run-006')

var tags = {
  'control-id': 'RUN-006'
  purpose: 'synthetic-agent-loop-demo'
}
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var monitoringMetricsPublisherRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'

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
    displayName: 'RUN-006 agent loop demo'
    description: 'Control-owned project for the synthetic RUN-006 support refunds agent.'
  }
}

resource projectFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: project
  name: guid(project.id, setupPrincipalId, 'run-006-foundry-user')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (enableAlerting) {
  name: 'run006-logs-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    // Bounded ingestion: also required by common subscription guardrail policies.
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = if (enableAlerting) {
  name: 'run006-appi-${suffix}'
  location: location
  kind: 'other'
  tags: tags
  properties: {
    Application_Type: 'other'
    WorkspaceResourceId: workspace.id
    // Keyless ingestion only: the runner exports with an Entra token.
    DisableLocalAuth: true
  }
}

resource metricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableAlerting) {
  scope: appInsights
  name: guid(appInsights.id, setupPrincipalId, 'run-006-metrics-publisher')
  properties: {
    principalId: setupPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', monitoringMetricsPublisherRoleId)
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (enableAlerting) {
  name: 'run006-ai-ops-lead-${suffix}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'run006'
    enabled: true
    emailReceivers: [
      {
        name: 'ai-ops-lead'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource loopAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = if (enableAlerting) {
  name: 'run006-loop-stopped-${suffix}'
  location: location
  tags: tags
  properties: {
    displayName: 'RUN-006 agent run stopped for repeating an action'
    description: 'Fires when ACS denies a repeated action under policy run_006_loop_detection. Notification only; the stop happens inline in ACS.'
    severity: 2
    enabled: true
    scopes: [appInsights.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: false
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where name == "acs_intervention_deny_total" | where tostring(customDimensions.policy_id) == "run_006_loop_detection" | where tostring(customDimensions.reason_code) == "run_006_loop_detected"'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

output projectId string = project.id
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${projectName}'
output projectRoleAssignmentId string = projectFoundryUser.id
output metricsRoleAssignmentId string = enableAlerting ? metricsPublisher.id : ''
output workspaceId string = enableAlerting ? workspace.id : ''
output appInsightsId string = enableAlerting ? appInsights.id : ''
output appInsightsConnectionString string = enableAlerting ? appInsights!.properties.ConnectionString : ''
output actionGroupId string = enableAlerting ? actionGroup.id : ''
output alertRuleId string = enableAlerting ? loopAlert.id : ''
