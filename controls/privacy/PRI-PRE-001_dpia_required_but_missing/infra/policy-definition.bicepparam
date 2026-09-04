using './policy-definition.bicep'

param policyDefinitionName = readEnvironmentVariable('PRIPRE001_POLICY_DEFINITION_NAME', 'pri-pre-001-dpia-gate')
