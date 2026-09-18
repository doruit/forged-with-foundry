using './policy-definition.bicep'

param policyDefinitionName = readEnvironmentVariable('VALPRE002_POLICY_DEFINITION_NAME', 'val-pre-002-kpi-baseline-gate')
