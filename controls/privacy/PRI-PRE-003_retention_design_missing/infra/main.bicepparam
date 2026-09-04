using './main.bicep'

param policyDefinitionId = readEnvironmentVariable('PRIPRE003_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('PRIPRE003_POLICY_ASSIGNMENT_NAME', 'pri-pre-003-retention-gate-assignment')
