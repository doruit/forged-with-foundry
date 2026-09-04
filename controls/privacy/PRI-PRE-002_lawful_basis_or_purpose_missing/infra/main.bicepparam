using './main.bicep'

param policyDefinitionId = readEnvironmentVariable('PRIPRE002_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('PRIPRE002_POLICY_ASSIGNMENT_NAME', 'pri-pre-002-lawful-basis-gate-assignment')
