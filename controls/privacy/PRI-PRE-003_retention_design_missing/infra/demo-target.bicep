targetScope = 'resourceGroup'

@description('Name used only during deployment validation; the resource is never created.')
param demoResourceName string = 'pripre003-demo'

@allowed([
  'healthy'
  'missing'
  'invalid-period'
  'invalid-disposition'
  'not-applicable'
])
@description('Which retention-design scenario tags to apply to the validation request.')
param scenario string = 'missing'

var baseTags = {
  'control-id': 'PRI-PRE-003'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
}

var healthyRetentionTags = {
  governedDataPresent: 'true'
  retentionDataCategory: 'foundry-traces'
  retentionStorageSystem: 'LogAnalytics'
  retentionPeriodDays: '30'
  retentionDisposition: 'delete'
  retentionOwner: 'Privacy Officer'
}

// Each invalid-* scenario changes exactly one field from the healthy
// baseline so a denial can be attributed to that one policy condition.
var scenarioTags = scenario == 'healthy' ? healthyRetentionTags : scenario == 'invalid-period' ? union(healthyRetentionTags, {
  retentionPeriodDays: '-5'
}) : scenario == 'invalid-disposition' ? union(healthyRetentionTags, {
  retentionDisposition: 'delete-forever'
}) : scenario == 'not-applicable' ? {
  governedDataPresent: 'false'
} : {
  governedDataPresent: 'true'
}

resource validationTarget 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: demoResourceName
  location: 'global'
  tags: union(baseTags, scenarioTags)
  properties: {
    groupShortName: 'ret-demo'
    enabled: false
  }
}
