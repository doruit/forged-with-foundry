using './policy-definition.bicep'

param policyDefinitionName = readEnvironmentVariable('VALPRE001_POLICY_DEFINITION_NAME', 'val-pre-001-value-hypothesis-gate')
