using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param storageAccountName = readEnvironmentVariable('PRI003_STORAGE_ACCOUNT_NAME', 'foundrygovdemodsr')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param tableName = readEnvironmentVariable('PRI003_TABLE_NAME', 'pri003dsrrequests')
