# AUT-002 Irreversible Action Gate

This local demo shows how the Agent Control Specification (ACS) stops an
agent from executing an irreversible action until an Ops Manager approves
that exact action.

## What happens

1. **Attempt irreversible action**: the agent calls the synthetic
   `permanently_delete_demo_record` tool without an approval resolver.
2. **Blocked by ACS**: the `pre_tool_call` policy escalates, the tool does
   not run, and metadata-only evidence is written.
3. **Approve as Ops Manager**: the exact action is retried with a
   short-lived approval bound to the ACS action identity.
4. **Action executed and verified**: ACS allows the call, the synthetic store
   confirms the record is absent, and the approved evidence is written.

Use **Clean up evidence** when you are done. The demo uses a synthetic record
only and needs no Azure credentials or Foundry deployment.
