targetScope = 'resourceGroup'

@description('Name used only during deployment validation; the resource is never created.')
param demoResourceName string = 'pripre001-demo'

@description('Include approved DPIA evidence in the validation request.')
param dpiaApproved bool = false

var demoTags = dpiaApproved ? {
  'control-id': 'PRI-PRE-001'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
  aiSystemHighRisk: 'true'
  dpiaStatus: 'approved'
  dpiaEvidenceId: 'DPIA-DEMO-001'
} : {
  'control-id': 'PRI-PRE-001'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
  aiSystemHighRisk: 'true'
  dpiaStatus: 'missing'
}

resource validationTarget 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: demoResourceName
  location: 'global'
  tags: demoTags
  properties: {
    groupShortName: 'dpia-demo'
    enabled: false
  }
}
