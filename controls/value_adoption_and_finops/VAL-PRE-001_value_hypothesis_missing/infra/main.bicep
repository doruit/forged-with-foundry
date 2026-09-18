targetScope = 'resourceGroup'

@description('Resource ID of the VAL-PRE-001 policy definition.')
param policyDefinitionId string

@description('Name of the resource-group-scoped policy assignment.')
param policyAssignmentName string = 'val-pre-001-value-hypothesis-gate-assignment'

resource assignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: policyAssignmentName
  properties: {
    displayName: 'VAL-PRE-001: Value hypothesis gate demo'
    description: 'Bite-sized demo assignment. Remove with infra/cleanup.sh.'
    policyDefinitionId: policyDefinitionId
    enforcementMode: 'Default'
    metadata: {
      controlId: 'VAL-PRE-001'
      version: '1.0.0'
    }
  }
}

output policyAssignmentId string = assignment.id
