targetScope = 'resourceGroup'

@description('Synthetic Action Group name; validation creates nothing, the OIDC demo creates and removes it.')
param demoResourceName string = 'valpre002-demo'

@description('Result of the shared FwF governance-contract validator (scripts/validate_governance_contract.py) against a .fwf/agents/<agent-id>/governance.yaml contract: complete or incomplete.')
param kpiBaselineStatus string = 'incomplete'

@description('Run identifier used to restrict cleanup to this demo invocation.')
param demoRunId string = 'validate-only'

// Running fictional example for this category: IT Helpdesk Tier-1 Triage Agent
// (see controls/value_adoption_and_finops/ARCHITECTURE.md).
var demoTags = {
  'control-id': 'VAL-PRE-002'
  purpose: 'governance-control-demo'
  'demo-run-id': demoRunId
  goLiveRequested: 'true'
  kpiBaselineStatus: kpiBaselineStatus
}

resource validationTarget 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: demoResourceName
  location: 'global'
  tags: demoTags
  properties: {
    groupShortName: 'kpibase-demo'
    enabled: false
  }
}
