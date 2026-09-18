targetScope = 'subscription'

@description('Name of the custom value-hypothesis-gate policy definition.')
param policyDefinitionName string = 'val-pre-001-value-hypothesis-gate'

// Illustrative teaching policy, not production governance guidance.
resource valueHypothesisGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'VAL-PRE-001: Deny go-live without a measurable value hypothesis'
    description: 'Denies a tagged go-live request unless valueHypothesisStatus=complete and a non-empty businessCaseId is present. The full structured evidence (metric, target, direction, baseline, owner, businessCaseId) is assessed by the shared FwF governance-contract validator (scripts/validate_governance_contract.py) against a .fwf/agents/<agent-id>/governance.yaml contract before these two tags are set; Azure Policy only re-checks the reduced tags, never the contract itself, so it cannot distinguish genuine tags from forged ones. Illustrative teaching policy; not production governance guidance.'
    policyType: 'Custom'
    mode: 'Indexed'
    metadata: {
      category: 'Forged with Foundry'
      version: '2.0.0'
    }
    policyRule: {
      if: {
        allOf: [
          {
            field: 'tags[\'goLiveRequested\']'
            equals: 'true'
          }
          {
            anyOf: [
              {
                field: 'tags[\'valueHypothesisStatus\']'
                notEquals: 'complete'
              }
              {
                field: 'tags[\'businessCaseId\']'
                exists: 'false'
              }
              {
                field: 'tags[\'businessCaseId\']'
                equals: ''
              }
            ]
          }
        ]
      }
      then: {
        effect: 'deny'
      }
    }
  }
}

output policyDefinitionId string = valueHypothesisGatePolicy.id
