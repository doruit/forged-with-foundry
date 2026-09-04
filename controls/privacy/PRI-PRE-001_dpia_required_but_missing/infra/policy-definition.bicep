targetScope = 'subscription'

@description('Name of the custom DPIA-gate policy definition.')
param policyDefinitionName string = 'pri-pre-001-dpia-gate'

// Illustrative teaching policy, not production compliance guidance.
resource dpiaGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'PRI-PRE-001: Deny high-risk go-live without approved DPIA evidence'
    description: 'Denies an explicitly tagged high-risk go-live request unless dpiaStatus=approved and a non-empty dpiaEvidenceId is present. Illustrative teaching policy; not production compliance guidance.'
    policyType: 'Custom'
    mode: 'Indexed'
    metadata: {
      category: 'Forged with Foundry'
      version: '1.0.0'
    }
    policyRule: {
      if: {
        allOf: [
          {
            field: 'tags[\'goLiveRequested\']'
            equals: 'true'
          }
          {
            field: 'tags[\'aiSystemHighRisk\']'
            equals: 'true'
          }
          {
            anyOf: [
              {
                field: 'tags[\'dpiaStatus\']'
                notEquals: 'approved'
              }
              {
                field: 'tags[\'dpiaEvidenceId\']'
                exists: 'false'
              }
              {
                field: 'tags[\'dpiaEvidenceId\']'
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

output policyDefinitionId string = dpiaGatePolicy.id
