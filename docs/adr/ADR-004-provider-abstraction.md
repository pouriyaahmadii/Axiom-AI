# ADR-004: Model & Provider Abstraction with Deterministic Mock Mode

## Status
Accepted

## Context
AI agent platforms typically bind tightly to specific external API providers (e.g., OpenAI, Anthropic, Tavily). This introduces severe architectural defects for open-source and portfolio projects:
1. **Financial & Authentication Friction**: Users and technical reviewers cannot test or verify the platform without active paid API keys and credit card setups.
2. **Non-Deterministic CI Testing**: External API latency, model weight updates, rate limits, and outages cause intermittent test failures in automated CI/CD pipelines.
3. **Vendor Lock-in**: Hardcoded SDK calls prevent dropping in local models (e.g., Ollama) or alternative search backends.

## Decision
We implement a **Provider Adapter Pattern** using strict Python abstract base classes:
- `BaseLLMAdapter`: Defines abstract methods for structured plan generation, tool argument extraction, and report synthesis.
- `BaseSearchAdapter`: Defines abstract methods for searching queries and fetching domain excerpts.

We establish **Deterministic Mock Mode** as the default, first-class implementation:
- `MockLLMAdapter`: Generates reproducible, schema-validated execution plans and grounded report syntheses using seeded random generation and canned templates.
- `MockSearchAdapter`: Queries a checked-in, realistic competitor intelligence corpus (`competitor_corpus.json`).
- Optional live adapters (`OpenAIAdapter`, `OllamaAdapter`, `TavilySearchAdapter`) inherit from the same base classes and activate only when configured via `.env`.

## Alternatives Considered
1. **Direct Integration with OpenAI & Tavily SDKs Only**:
   - *Pros*: Faster initial prototyping; fewer abstractions to maintain.
   - *Cons*: Fails immediately for reviewers without API keys; breaks in offline environments; makes CI dependent on third-party uptime.
2. **VCR.py / WireMock HTTP Recording Only**:
   - *Pros*: Records real HTTP requests once and replays them.
   - *Cons*: Brittle when prompt templates or parameters change slightly; does not provide a clean software design pattern for swapping providers (e.g., to Ollama).

## Consequences
- **Positive**:
  - Zero-cost, 100% offline demonstration capability.
  - Bit-for-bit reproducible unit and integration tests with deterministic seeds.
  - Clean separation between core orchestration logic and external provider SDKs.
- **Negative / Trade-offs**:
  - Requires maintaining the adapter interfaces and mock data corpus alongside live provider implementations.

## Rejected Options
- **Requiring Paid API Keys for Basic Setup**: Rejected to ensure immediate accessibility and zero-friction evaluation.
- **Uncontrolled Live Scraping Fallback**: Rejected due to anti-scraping blocks, legal risks, and lack of reproducibility.

## Conditions for Revisiting
- If an industry-standard universal abstraction (e.g., unified OpenTelemetry GenAI semantic conventions) completely supplants custom provider adapters.
