// Parameters sourced from environment variables (loaded from .env by deploy.sh).
// Run with: az deployment group create ... --parameters infra/main.bicepparam
using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param foundryAccountName = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME', 'foundry-gov-demo')
param foundryProjectName = readEnvironmentVariable('FOUNDRY_PROJECT_NAME', 'default-project')
param foundryProjectDisplayName = readEnvironmentVariable('FOUNDRY_PROJECT_DISPLAY_NAME', 'Governance Controls Demo')
param gpt5Capacity = int(readEnvironmentVariable('GPT5_CAPACITY', '50'))
param gpt5MiniCapacity = int(readEnvironmentVariable('GPT5_MINI_CAPACITY', '50'))
param embeddingCapacity = int(readEnvironmentVariable('EMBEDDING_CAPACITY', '50'))
param languageAccountName = readEnvironmentVariable('AZURE_LANGUAGE_ACCOUNT_NAME')
param piiStorageAccountName = readEnvironmentVariable('PII_STORAGE_ACCOUNT_NAME')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID')
param piiSourceContainerName = readEnvironmentVariable('PII_SOURCE_CONTAINER', 'pii-source')
param piiTargetContainerName = readEnvironmentVariable('PII_TARGET_CONTAINER', 'pii-redacted')
