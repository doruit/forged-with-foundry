using './main.bicep'

param policyDefinitionId = readEnvironmentVariable('VALPRE002_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('VALPRE002_POLICY_ASSIGNMENT_NAME', 'val-pre-002-kpi-baseline-gate-assignment')
