targetScope = 'resourceGroup'

@description('Name used only during deployment validation; the resource is never created.')
param demoResourceName string = 'pripre003-demo'

@allowed([
  'healthy'
  'missing'
  'invalid'
  'not-applicable'
])
@description('Which retention-design scenario tags to apply to the validation request.')
param scenario string = 'missing'

var baseTags = {
  'control-id': 'PRI-PRE-003'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
}

var scenarioTags = scenario == 'healthy' ? {
  governedDataPresent: 'true'
  retentionDataCategory: 'foundry-traces'
  retentionStorageSystem: 'LogAnalytics'
  retentionPeriodDays: '30'
  retentionDisposition: 'delete'
  retentionOwner: 'Privacy Officer'
} : scenario == 'invalid' ? {
  governedDataPresent: 'true'
  retentionDataCategory: 'foundry-traces'
  retentionStorageSystem: 'LogAnalytics'
  retentionPeriodDays: '0'
  retentionDisposition: 'delete-forever'
  retentionOwner: 'Privacy Officer'
} : scenario == 'not-applicable' ? {
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
