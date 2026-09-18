targetScope = 'subscription'

@description('Name of the custom KPI-baseline-gate policy definition.')
param policyDefinitionName string = 'val-pre-002-kpi-baseline-gate'

// Illustrative teaching policy, not production governance guidance.
resource kpiBaselineGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'VAL-PRE-002: Deny go-live without a recorded KPI baseline'
    description: 'Denies a tagged go-live request unless kpiBaselineStatus=complete. Scoped to tags[\'control-id\']==\'VAL-PRE-002\' so this policy coexists safely with other Pre-Live control demos (for example VAL-PRE-001) assigned to the same resource group; each policy only ever evaluates requests explicitly tagged for its own control. This control-id tag is caller-supplied and illustrative, like every other tag here -- it can be omitted or forged, and Azure Policy does not authenticate that a real contract assessment produced it. The full structured evidence (baseline status, value, measured date) is assessed by the shared FwF governance-contract validator (scripts/validate_governance_contract.py) against a .fwf/agents/<agent-id>/governance.yaml contract before this tag is set; Azure Policy only re-checks the reduced tag, never the contract itself. Self-contained: does not depend on a VAL-PRE-001 entry existing in the same contract. Illustrative teaching policy; not production governance guidance.'
    policyType: 'Custom'
    mode: 'Indexed'
    metadata: {
      category: 'Forged with Foundry'
      version: '1.1.0'
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
            equals: 'VAL-PRE-002'
          }
          {
            field: 'tags[\'kpiBaselineStatus\']'
            notEquals: 'complete'
          }
        ]
      }
      then: {
        effect: 'deny'
      }
    }
  }
}

output policyDefinitionId string = kpiBaselineGatePolicy.id
