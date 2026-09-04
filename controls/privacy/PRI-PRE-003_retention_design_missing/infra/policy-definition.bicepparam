using './policy-definition.bicep'

param policyDefinitionName = readEnvironmentVariable('PRIPRE003_POLICY_DEFINITION_NAME', 'pri-pre-003-retention-gate')
