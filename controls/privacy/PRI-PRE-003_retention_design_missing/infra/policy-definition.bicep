targetScope = 'subscription'

@description('Name of the custom retention-design gate policy definition.')
param policyDefinitionName string = 'pri-pre-003-retention-gate'

// Illustrative teaching policy, not production compliance guidance.
resource retentionGatePolicy 'Microsoft.Authorization/policyDefinitions@2021-06-01' = {
  name: policyDefinitionName
  properties: {
    displayName: 'PRI-PRE-003: Deny go-live when a retention design is missing for governed data'
    description: 'Denies an explicitly tagged go-live request that carries governed data unless a data category, storage system, retention period, disposition, and owner are all declared. Illustrative teaching policy; not production compliance guidance.'
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
            field: 'tags[\'governedDataPresent\']'
            equals: 'true'
          }
          {
            anyOf: [
              {
                field: 'tags[\'retentionDataCategory\']'
                exists: 'false'
              }
              {
                field: 'tags[\'retentionDataCategory\']'
                equals: ''
              }
              {
                field: 'tags[\'retentionStorageSystem\']'
                exists: 'false'
              }
              {
                field: 'tags[\'retentionStorageSystem\']'
                equals: ''
              }
              {
                field: 'tags[\'retentionPeriodDays\']'
                exists: 'false'
              }
              {
                field: 'tags[\'retentionPeriodDays\']'
                equals: ''
              }
              {
                field: 'tags[\'retentionPeriodDays\']'
                equals: '0'
              }
              {
                // The tag must be an unsigned integer of 1-5 digits (1-99999
                // days, ~274 years). `match`/`notMatch` require a
                // fixed-length pattern, so a value that fails every
                // digit-only length from 1 to 5 is denied as an invalid
                // format (catches negative numbers, decimals, and any
                // non-numeric text; a bare "0" is caught separately above).
                allOf: [
                  {
                    not: {
                      field: 'tags[\'retentionPeriodDays\']'
                      match: '#'
                    }
                  }
                  {
                    not: {
                      field: 'tags[\'retentionPeriodDays\']'
                      match: '##'
                    }
                  }
                  {
                    not: {
                      field: 'tags[\'retentionPeriodDays\']'
                      match: '###'
                    }
                  }
                  {
                    not: {
                      field: 'tags[\'retentionPeriodDays\']'
                      match: '####'
                    }
                  }
                  {
                    not: {
                      field: 'tags[\'retentionPeriodDays\']'
                      match: '#####'
                    }
                  }
                ]
              }
              {
                field: 'tags[\'retentionDisposition\']'
                exists: 'false'
              }
              {
                field: 'tags[\'retentionDisposition\']'
                notIn: [
                  'delete'
                  'archive'
                ]
              }
              {
                field: 'tags[\'retentionOwner\']'
                exists: 'false'
              }
              {
                field: 'tags[\'retentionOwner\']'
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

output policyDefinitionId string = retentionGatePolicy.id
