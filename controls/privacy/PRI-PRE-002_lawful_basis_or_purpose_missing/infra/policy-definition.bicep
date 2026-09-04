targetScope = 'subscription'

@description('Name of the custom lawful-basis-gate policy definition.')
param policyDefinitionName string = 'pri-pre-002-lawful-basis-gate'

// Illustrative teaching policy, not production compliance guidance.
resource lawfulBasisGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'PRI-PRE-002: Flag missing lawful basis or purpose for personal-data projects'
    description: 'Audits an explicitly tagged personal-data go-live request when lawfulBasis is missing or unrecognized, or purposeId is missing or empty. Illustrative teaching policy; not production compliance guidance.'
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
            field: 'tags[\'personalDataProcessing\']'
            equals: 'true'
          }
          {
            anyOf: [
              {
                field: 'tags[\'lawfulBasis\']'
                notIn: [
                  'consent'
                  'contract'
                  'legal_obligation'
                  'vital_interests'
                  'public_task'
                  'legitimate_interests'
                ]
              }
              {
                field: 'tags[\'purposeId\']'
                exists: 'false'
              }
              {
                field: 'tags[\'purposeId\']'
                equals: ''
              }
            ]
          }
        ]
      }
      then: {
        effect: 'audit'
      }
    }
  }
}

output policyDefinitionId string = lawfulBasisGatePolicy.id
