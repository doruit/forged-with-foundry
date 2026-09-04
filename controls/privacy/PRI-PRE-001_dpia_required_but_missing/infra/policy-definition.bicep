targetScope = 'subscription'

@description('Name of the custom DPIA-gate policy definition.')
param policyDefinitionName string = 'pri-pre-001-dpia-gate'

// Illustrative teaching policy, not production compliance guidance.
resource dpiaGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'PRI-PRE-001: Deny go-live without a completed DPIA for high-risk AI systems'
    description: 'Denies any resource tagged aiSystemHighRisk=true unless dpiaStatus=completed and the dpiaApprover, dpiaDate, and dpiaReportId tags are all present. Illustrative teaching policy for the Forged with Foundry PRI-PRE-001 control; not a production compliance policy.'
    policyType: 'Custom'
    mode: 'Indexed'
    policyRule: {
      if: {
        allOf: [
          {
            field: 'tags[\'aiSystemHighRisk\']'
            equals: 'true'
          }
          {
            anyOf: [
              {
                field: 'tags[\'dpiaStatus\']'
                notEquals: 'completed'
              }
              {
                field: 'tags[\'dpiaApprover\']'
                exists: 'false'
              }
              {
                field: 'tags[\'dpiaDate\']'
                exists: 'false'
              }
              {
                field: 'tags[\'dpiaReportId\']'
                exists: 'false'
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
