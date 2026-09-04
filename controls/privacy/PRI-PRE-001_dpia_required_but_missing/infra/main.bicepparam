using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param storageAccountName = readEnvironmentVariable('PRIPRE001_STORAGE_ACCOUNT_NAME', 'foundrygovdemodpia')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param tableName = readEnvironmentVariable('PRIPRE001_TABLE_NAME', 'pripre001projects')
param policyDefinitionId = readEnvironmentVariable('PRIPRE001_POLICY_DEFINITION_ID', '')
param policyAssignmentName = readEnvironmentVariable('PRIPRE001_POLICY_ASSIGNMENT_NAME', 'pri-pre-001-dpia-gate-assignment')
