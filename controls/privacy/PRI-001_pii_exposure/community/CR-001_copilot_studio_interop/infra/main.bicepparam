using 'main.bicep'

param appServiceName = readEnvironmentVariable('CR001_APP_SERVICE_NAME', 'fwf-cr001-mcp')
param appServicePlanName = readEnvironmentVariable('CR001_APP_SERVICE_PLAN_NAME', 'fwf-cr001-plan')
param languageAccountName = readEnvironmentVariable('AZURE_LANGUAGE_ACCOUNT_NAME', '')
param piiStorageAccountName = readEnvironmentVariable('PII_STORAGE_ACCOUNT_NAME', '')
