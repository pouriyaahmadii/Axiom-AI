# n8n Automation Workflows (`workflows/n8n`)

Self-hosted n8n Community Edition workflow templates for external triggers, notifications, and scheduled research runs.

## Directory Layout
- `triggers/`: Workflows that initiate AgentOps runs (e.g., cron schedules, incoming webhooks, RSS feeds).
- `notifications/`: Workflows that dispatch outbound alerts (e.g., Slack alerts on `AWAITING_APPROVAL`, email digests on `COMPLETED`).
- `error-handling/`: Workflows for dead-letter alerts and operational failure notifications.
- `examples/`: Exported n8n workflow JSON templates ready for import.

## Security Rule
All communication between n8n and AgentOps must pass HMAC-SHA256 signature verification via the `X-AgentOps-Signature` header.
