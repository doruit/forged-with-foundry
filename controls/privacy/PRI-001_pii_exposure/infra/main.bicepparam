using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param languageAccountName = readEnvironmentVariable('AZURE_LANGUAGE_ACCOUNT_NAME', 'foundry-gov-demo-language')
param piiStorageAccountName = readEnvironmentVariable('PII_STORAGE_ACCOUNT_NAME', 'foundrygovdemopii')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID', '00000000-0000-0000-0000-000000000000')
param piiSourceContainerName = readEnvironmentVariable('PII_SOURCE_CONTAINER', 'pii-source')
param piiTargetContainerName = readEnvironmentVariable('PII_TARGET_CONTAINER', 'pii-redacted')
