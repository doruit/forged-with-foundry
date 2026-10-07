using './main.bicep'

param location = readEnvironmentVariable('AZURE_LOCATION')
param foundryAccountName = readEnvironmentVariable('FOUNDRY_ACCOUNT_NAME')
param setupPrincipalId = readEnvironmentVariable('AUT002_SETUP_PRINCIPAL_ID')
param modelCapacity = int(readEnvironmentVariable('AUT002_MODEL_CAPACITY', '10'))