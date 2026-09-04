using './policy-definition.bicep'

param policyDefinitionName = readEnvironmentVariable('PRIPRE002_POLICY_DEFINITION_NAME', 'pri-pre-002-lawful-basis-gate')
