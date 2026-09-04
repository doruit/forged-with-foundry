targetScope = 'subscription'

@description('Name of the custom lawful-basis-gate policy definition.')
param policyDefinitionName string = 'pri-pre-002-lawful-basis-gate'

// Illustrative teaching policy, not production compliance guidance.
resource lawfulBasisGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'PRI-PRE-002: Flag missing lawful basis or purpose for personal-data projects'
    description: 'In production, flags (audit, does not block) any resource tagged personalDataProcessing=true unless lawfulBasis is one of the six GDPR Article 6(1) categories and the purposeId tag is present. Illustrative teaching policy for the Forged with Foundry PRI-PRE-002 control; not a production compliance policy.'
    policyType: 'Custom'
    mode: 'Indexed'
    policyRule: {
      if: {
        allOf: [
          {
            field: 'tags[\'environment\']'
            equals: 'production'
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
