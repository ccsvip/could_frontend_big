# Treat third-party chatbots as separate runtime backends

Third-party chatbot integrations are externally hosted applications with their own credentials and conversation lifecycle, not OpenAI-compatible model providers. We keep them parallel to platform LLM providers and let each Agent Application choose exactly one Agent Runtime Backend at a time, so failures or protocol quirks in a company-specific chatbot cannot change the existing platform LLM behavior or the device chat contract.
