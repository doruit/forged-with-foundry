targetScope = 'subscription'

@description('Name of the custom value-hypothesis-gate policy definition.')
param policyDefinitionName string = 'val-pre-001-value-hypothesis-gate'

// Illustrative teaching policy, not production governance guidance.
resource valueHypothesisGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'VAL-PRE-001: Deny go-live without a measurable value hypothesis'
    description: 'Denies a tagged go-live request unless valueHypothesisStatus=complete and a non-empty businessCaseId is present. Scoped to tags[\'control-id\']==\'VAL-PRE-001\' so this policy coexists safely with other Pre-Live control demos (for example VAL-PRE-002) assigned to the same resource group; each policy only ever evaluates requests explicitly tagged for its own control. This control-id tag is caller-supplied and illustrative, like every other tag here -- it can be omitted or forged, and Azure Policy does not authenticate that a real contract assessment produced it. The full structured evidence (metric, target, direction, baseline, owner, businessCaseId) is assessed by the shared FwF governance-contract validator (scripts/validate_governance_contract.py) against a .fwf/agents/<agent-id>/governance.yaml contract before these tags are set; Azure Policy only re-checks the reduced tags, never the contract itself. Illustrative teaching policy; not production governance guidance.'
    policyType: 'Custom'
    mode: 'Indexed'
    metadata: {
      category: 'Forged with Foundry'
      version: '2.1.0'
    }
    policyRule: {
      if: {
        allOf: [
          {
            field: 'tags[\'goLiveRequested\']'
            equals: 'true'
          }
          {
            field: 'tags[\'control-id\']'
            equals: 'VAL-PRE-001'
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
