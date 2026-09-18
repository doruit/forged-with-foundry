targetScope = 'resourceGroup'

@description('Name used only during deployment validation; the resource is never created.')
param demoResourceName string = 'valpre001-demo'

@description('Result of scripts/validate_value_hypothesis.py against an agent.yaml fixture: approved or missing.')
param valueHypothesisStatus string = 'missing'

@description('Business case reference from the same agent.yaml fixture; empty when the hypothesis is not measurable.')
param businessCaseId string = ''

// Running fictional example for this category: IT Helpdesk Tier-1 Triage Agent
// (see controls/value_adoption_and_finops/ARCHITECTURE.md).
var demoTags = {
  'control-id': 'VAL-PRE-001'
  purpose: 'governance-control-demo'
  goLiveRequested: 'true'
  valueHypothesisStatus: valueHypothesisStatus
  businessCaseId: businessCaseId
}

resource validationTarget 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: demoResourceName
  location: 'global'
  tags: demoTags
  properties: {
    groupShortName: 'valhyp-demo'
    enabled: false
  }
}
