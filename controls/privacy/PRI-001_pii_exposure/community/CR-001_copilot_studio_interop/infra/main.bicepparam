using 'main.bicep'

param appServiceName = readEnvironmentVariable('CR001_APP_SERVICE_NAME', 'fwf-cr001-mcp')
param a2aAppServiceName = readEnvironmentVariable('CR001_A2A_APP_SERVICE_NAME', 'fwf-cr001-a2a')
param appServicePlanName = readEnvironmentVariable('CR001_APP_SERVICE_PLAN_NAME', 'fwf-cr001-plan')
param languageAccountName = readEnvironmentVariable('AZURE_LANGUAGE_ACCOUNT_NAME', '')
param piiStorageAccountName = readEnvironmentVariable('PII_STORAGE_ACCOUNT_NAME', '')
param foundryAccountName = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME', '')
param foundryProjectName = readEnvironmentVariable('FOUNDRY_PROJECT_NAME', 'default-project')
param foundryChatDeploymentName = readEnvironmentVariable('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-5')
