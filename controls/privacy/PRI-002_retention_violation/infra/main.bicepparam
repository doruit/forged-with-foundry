using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param storageAccountName = readEnvironmentVariable('PRI002_STORAGE_ACCOUNT_NAME')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID')
param containerName = readEnvironmentVariable('PRI002_CONTAINER', 'pri-002-retention-demo')
param lifecycleClass = readEnvironmentVariable('PRI002_LIFECYCLE_CLASS', 'customer-conversation-30d')
param retentionDays = int(readEnvironmentVariable('PRI002_RETENTION_DAYS', '30'))
