targetScope = 'subscription'

@allowed(['westeurope'])
param location string = 'westeurope'

@allowed(['rg-knw001-demo'])
param resourceGroupName string = 'rg-knw001-demo'

param setupPrincipalId string
@allowed(['free', 'standard'])
param searchSku string = 'free'
@allowed(['westeurope', 'swedencentral'])
param searchLocation string = 'westeurope'

resource group 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: {
    'control-id': 'KNW-001'
    purpose: 'synthetic-knowledge-freshness-demo'
  }
}

module resources 'resources.bicep' = {
  name: 'knw001-resources'
  scope: group
  params: {
    location: location
    setupPrincipalId: setupPrincipalId
    searchSku: searchSku
    searchLocation: searchLocation
  }
}

output resources object = resources.outputs
