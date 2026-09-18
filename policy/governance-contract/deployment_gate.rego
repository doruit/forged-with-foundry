package main

# Forged with Foundry deployment gate policy: given a deployment plan
# document (built by scripts/build_deployment_plan.py, never authored by a
# workload's own governance.yaml), deny deployment unless every expected
# agent has a structurally valid governance contract declaring every
# control the trusted pipeline's policy profile requires.
#
# This is the organisational POLICY layer: "which agents must be covered,
# and which controls are mandatory for them" is a decision made by whoever
# builds the deployment plan (the trusted pipeline), never by the workload
# repository itself. Field types, required fields, and structural
# conditional requirements (is a value numeric, is a date real, is a
# control version supported) are NOT duplicated here -- those stay in
# JSON Schema (schemas/governance-contract/v1alpha1/), which is what
# `scripts/validate_governance_contract.py` already produced the `valid`
# and `controlStatuses` fields on this input from.
#
# See docs/governance-contract.md#policy-layer.

agent_found(agent) if {
	some discovered in input.discoveredAgents
	discovered.agentId == agent
}

discovered_for(agent) := discovered if {
	some discovered in input.discoveredAgents
	discovered.agentId == agent
}

control_complete(discovered, control_id) if {
	discovered.controlStatuses[control_id] == "complete"
}

# An expected agent must have a discovered .fwf/agents/<agent-id>/ folder at all.
deny contains msg if {
	some agent in input.expectedAgents
	not agent_found(agent)
	msg := sprintf(
		"expected agent '%s' has no discovered .fwf/agents/ folder -- it is not covered by any governance contract",
		[agent],
	)
}

# The folder exists, but it never had a governance.yaml file in it.
deny contains msg if {
	some agent in input.expectedAgents
	discovered := discovered_for(agent)
	not discovered.hasContract
	msg := sprintf(
		"expected agent '%s' has a .fwf/agents/ folder but no governance.yaml contract",
		[agent],
	)
}

# The contract exists but failed structural (JSON Schema) validation.
deny contains msg if {
	some agent in input.expectedAgents
	discovered := discovered_for(agent)
	discovered.hasContract
	discovered.valid == false
	msg := sprintf(
		"expected agent '%s' has a governance.yaml contract that fails structural validation",
		[agent],
	)
}

# The contract is structurally valid but omits (or does not complete) a
# control this deployment's policy profile requires. This is the genuine
# policy decision: the required-control set comes from input.requiredControls,
# which is supplied by the trusted pipeline building the deployment plan,
# never read from the workload's own governance.yaml.
deny contains msg if {
	some agent in input.expectedAgents
	discovered := discovered_for(agent)
	discovered.hasContract
	discovered.valid == true
	some required_control in input.requiredControls
	not control_complete(discovered, required_control)
	msg := sprintf(
		"expected agent '%s' does not have a complete '%s' control (required by policy profile '%s')",
		[agent, required_control, input.policyProfile],
	)
}
