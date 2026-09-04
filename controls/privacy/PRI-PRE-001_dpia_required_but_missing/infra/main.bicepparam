using './main.bicep'

param policyDefinitionId = readEnvironmentVariable('PRIPRE001_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('PRIPRE001_POLICY_ASSIGNMENT_NAME', 'pri-pre-001-dpia-gate-assignment')
