using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param workspaceName = readEnvironmentVariable('PRI004_WORKSPACE_NAME', 'foundrygovdemologs')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param tableName = readEnvironmentVariable('PRI004_TABLE_NAME', 'PRI004AppLogs_CL')
param dataCollectionRuleName = readEnvironmentVariable('PRI004_DCR_NAME', 'pri004-app-logs-dcr')
