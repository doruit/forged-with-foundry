using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param storageAccountName = readEnvironmentVariable('PRI002_STORAGE_ACCOUNT_NAME', 'foundrygovdemoretention')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param containerName = readEnvironmentVariable('PRI002_CONTAINER', 'pri-002-retention-demo')
param lifecycleClass = readEnvironmentVariable('PRI002_LIFECYCLE_CLASS', 'customer-conversation-30d')
param retentionDays = int(readEnvironmentVariable('PRI002_RETENTION_DAYS', '30'))
