# Keep Device Agent ASR runtime settings company-scoped

Device Agent ASR behavior that changes a company's interaction policy, beginning with Effective Input Timeout, is stored as a company override with a fixed platform fallback rather than in the platform-singleton ASR provider configuration. This preserves company isolation and prevents one company from changing another company's device behavior; company runtime settings use their own REST resource, while provider-level VAD configuration and manual Management ASR Tests remain separate.
