targetScope = 'resourceGroup'

@description('Resource ID of the PRI-PRE-002 policy definition.')
param policyDefinitionId string

@description('Name of the resource-group-scoped policy assignment.')
param policyAssignmentName string = 'pri-pre-002-lawful-basis-gate-assignment'

resource assignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: policyAssignmentName
  properties: {
    displayName: 'PRI-PRE-002: Lawful basis and purpose audit demo'
    description: 'Bite-sized demo assignment. Remove with infra/cleanup.sh.'
    policyDefinitionId: policyDefinitionId
    enforcementMode: 'Default'
    metadata: {
      controlId: 'PRI-PRE-002'
      version: '1.0.0'
    }
  }
}

output policyAssignmentId string = assignment.id
