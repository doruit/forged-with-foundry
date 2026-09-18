using './main.bicep'

param policyDefinitionId = readEnvironmentVariable('VALPRE001_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('VALPRE001_POLICY_ASSIGNMENT_NAME', 'val-pre-001-value-hypothesis-gate-assignment')
