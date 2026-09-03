using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param languageAccountName = readEnvironmentVariable('AZURE_LANGUAGE_ACCOUNT_NAME')
param piiStorageAccountName = readEnvironmentVariable('PII_STORAGE_ACCOUNT_NAME')
param deployerPrincipalId = readEnvironmentVariable('DEPLOYER_PRINCIPAL_ID')
param piiSourceContainerName = readEnvironmentVariable('PII_SOURCE_CONTAINER', 'pii-source')
param piiTargetContainerName = readEnvironmentVariable('PII_TARGET_CONTAINER', 'pii-redacted')
