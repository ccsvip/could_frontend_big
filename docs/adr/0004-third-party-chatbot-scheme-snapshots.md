# Store third-party chatbot scheme instances as API flow snapshots

Third-party chatbot requirements may repeat across companies, but each external chatbot contract can also diverge. We represent the reusable contract as a Third-Party Chatbot Scheme and store each configured scheme instance as an editable snapshot of its API flow, credentials, application identity, maintenance remark, and company grants.

This keeps company authorization on the existing Third-Party Chatbot Application grant model while allowing platform administrators to reuse Scheme A for matching companies. When a later company needs a different external protocol, we can add Scheme B or later schemes without changing the company grant boundary or mutating existing Scheme A instances. Scheme B is the FlowMesh LLM synchronous chat template, represented as a single JSON request/response step on the same API flow executor.

For now, a `stream` field is only part of an outgoing request body when the scheme step explicitly includes it. The platform does not parse third-party streaming responses until a concrete scheme needs that runtime contract.
