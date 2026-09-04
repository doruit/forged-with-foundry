targetScope = 'resourceGroup'

@description('Azure region inherited from the shared deployment settings.')
param location string = resourceGroup().location

@description('Log Analytics workspace name owned by PRI-004.')
@minLength(4)
@maxLength(63)
param workspaceName string

@description('Object ID of the user or service principal running the local demo.')
param deployerPrincipalId string

@description('Custom table name reserved for PRI-004 synthetic log records (must end in _CL).')
param tableName string = 'PRI004AppLogs_CL'

@description('Data collection rule name; its own logsIngestion endpoint is used, so no DCE is needed.')
param dataCollectionRuleName string = 'pri004-app-logs-dcr'

var streamName = 'Custom-PRI004AppLogs'

// Built-in roles; verify these GUIDs against current Azure RBAC documentation before reuse.
var dataPurgerRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '150f5e0c-0603-4f03-8c7f-cf70034c4e90'
)
var logAnalyticsDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '3b03c2da-16b3-4a49-8834-0f8130efdd3b'
)
var monitoringMetricsPublisherRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '3913510d-42f4-4e42-8a64-420c390055eb'
)

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      disableLocalAuth: true
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource demoTable 'Microsoft.OperationalInsights/workspaces/tables@2022-10-01' = {
  parent: workspace
  name: tableName
  properties: {
    schema: {
      name: tableName
      columns: [
        { name: 'TimeGenerated', type: 'datetime', description: 'Timestamp of the synthetic log entry.' }
        { name: 'RecordId', type: 'string', description: 'Opaque record identifier (pri004-demo- prefixed).' }
        { name: 'FieldName', type: 'string', description: 'Name of the field that may carry personal data.' }
        { name: 'Message', type: 'string', description: 'Synthetic log message content.' }
        { name: 'Source', type: 'string', description: 'Synthetic emitting component.' }
      ]
    }
  }
}

// kind: 'Direct' gives this DCR its own logsIngestion endpoint; no separate DCE is deployed.
resource dcr 'Microsoft.Insights/dataCollectionRules@2024-03-11' = {
  name: dataCollectionRuleName
  location: location
  kind: 'Direct'
  properties: {
    streamDeclarations: {
      '${streamName}': {
        columns: [
          { name: 'TimeGenerated', type: 'datetime' }
          { name: 'RecordId', type: 'string' }
          { name: 'FieldName', type: 'string' }
          { name: 'Message', type: 'string' }
          { name: 'Source', type: 'string' }
        ]
      }
    }
    destinations: {
      logAnalytics: [
        {
          workspaceResourceId: workspace.id
          name: 'pri004Workspace'
        }
      ]
    }
    dataFlows: [
      {
        streams: [streamName]
        destinations: ['pri004Workspace']
        transformKql: 'source'
        outputStream: 'Custom-${tableName}'
      }
    ]
  }
  dependsOn: [
    demoTable
  ]
}

resource deployerPurgeAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workspace.id, deployerPrincipalId, dataPurgerRoleId)
  scope: workspace
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: dataPurgerRoleId
  }
}

resource deployerQueryAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(workspace.id, deployerPrincipalId, logAnalyticsDataReaderRoleId)
  scope: workspace
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: logAnalyticsDataReaderRoleId
  }
}

resource deployerIngestionAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(dcr.id, deployerPrincipalId, monitoringMetricsPublisherRoleId)
  scope: dcr
  properties: {
    principalId: deployerPrincipalId
    roleDefinitionId: monitoringMetricsPublisherRoleId
  }
}

output workspaceName string = workspace.name
output workspaceCustomerId string = workspace.properties.customerId
output tableName string = demoTable.name
output dataCollectionRuleImmutableId string = dcr.properties.immutableId
output dataCollectionRuleLogsIngestionEndpoint string = dcr.properties.endpoints.logsIngestion
output streamName string = streamName
