using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param storageAccountName = readEnvironmentVariable('PRIPRE002_STORAGE_ACCOUNT_NAME', 'foundrygovdemolawful')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param tableName = readEnvironmentVariable('PRIPRE002_TABLE_NAME', 'pripre002projects')
param policyDefinitionId = readEnvironmentVariable('PRIPRE002_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('PRIPRE002_POLICY_ASSIGNMENT_NAME', 'pri-pre-002-lawful-basis-gate-assignment')
