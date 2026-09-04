targetScope = 'resourceGroup'

@description('Name of the temporary disabled Action Group used as the demo target.')
param demoResourceName string = 'pripre002-demo'

@description('Add a recognized lawful basis and non-empty purpose reference.')
param remediated bool = false

var demoTags = remediated ? {
  'control-id': 'PRI-PRE-002'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
  personalDataProcessing: 'true'
  lawfulBasis: 'contract'
  purposeId: 'PURPOSE-DEMO-001'
} : {
  'control-id': 'PRI-PRE-002'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
  personalDataProcessing: 'true'
  lawfulBasis: ''
  purposeId: ''
}

resource demoTarget 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: demoResourceName
  location: 'global'
  tags: demoTags
  properties: {
    groupShortName: 'basis-demo'
    enabled: false
  }
}

output demoResourceId string = demoTarget.id
