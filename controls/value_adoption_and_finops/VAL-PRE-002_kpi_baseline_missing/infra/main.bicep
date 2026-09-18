targetScope = 'resourceGroup'

@description('Resource ID of the VAL-PRE-002 policy definition.')
param policyDefinitionId string

@description('Name of the resource-group-scoped policy assignment.')
param policyAssignmentName string = 'val-pre-002-kpi-baseline-gate-assignment'

resource assignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: policyAssignmentName
  properties: {
    displayName: 'VAL-PRE-002: KPI baseline gate demo'
    description: 'Bite-sized demo assignment. Remove with infra/cleanup.sh.'
    policyDefinitionId: policyDefinitionId
    enforcementMode: 'Default'
    metadata: {
      controlId: 'VAL-PRE-002'
      version: '1.0.0'
    }
  }
}

output policyAssignmentId string = assignment.id
