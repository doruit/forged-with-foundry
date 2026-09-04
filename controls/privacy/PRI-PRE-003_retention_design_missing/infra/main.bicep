targetScope = 'resourceGroup'

@description('Resource ID of the PRI-PRE-003 policy definition.')
param policyDefinitionId string

@description('Name of the resource-group-scoped policy assignment.')
param policyAssignmentName string = 'pri-pre-003-retention-gate-assignment'

resource assignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: policyAssignmentName
  properties: {
    displayName: 'PRI-PRE-003: Retention design gate demo'
    description: 'Bite-sized demo assignment. Remove with infra/cleanup.sh.'
    policyDefinitionId: policyDefinitionId
    enforcementMode: 'Default'
    metadata: {
      controlId: 'PRI-PRE-003'
      version: '1.0.0'
    }
  }
}

output policyAssignmentId string = assignment.id
