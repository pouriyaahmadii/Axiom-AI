import * as React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { RunHeader } from "@/components/runs/run-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DEMO_AUDIT_EVENTS,
  DEMO_RUNS,
  DEMO_STEPS,
  type DemoRun,
} from "@/lib/mock-data";
import { formatTimestamp, formatUSD } from "@/lib/utils";

export default function RunOverviewPage({
  params,
}: {
  params: { id: string };
}) {
  const run: DemoRun =
    DEMO_RUNS.find((r) => r.id === params.id) ?? (DEMO_RUNS[0] as DemoRun);

  return (
    <div className="space-y-6">
      <RunHeader run={run} />

      {/* Active HITL Checkpoint Callout */}
      {run.status === "AWAITING_APPROVAL" && (
        <Alert
          variant="warning"
          title="Execution Checkpoint: Human Authorization Required"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
            <span>
              The LangGraph runtime generated a 5-step competitive research DAG
              and paused execution. A verified operator must review the tool
              boundaries and approve resumption.
            </span>
            <Link href="/approvals">
              <Button
                size="sm"
                className="bg-amber-600 text-white hover:bg-amber-700"
              >
                Review & Authorize
              </Button>
            </Link>
          </div>
        </Alert>
      )}

      {/* Overview Grid */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {/* Plan & Step Progress */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Execution State & Step Progress</CardTitle>
            <CardDescription>
              Real-time sequence of bounded LangGraph steps.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-content-muted">
                <span>Overall Progress</span>
                <span className="font-mono font-bold">
                  {run.steps_completed} of {run.steps_total} Steps Completed
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all"
                  style={{
                    width: `${(run.steps_completed / run.steps_total) * 100}%`,
                  }}
                />
              </div>
            </div>

            <div className="rounded-lg border border-border divide-y divide-border/60">
              {DEMO_STEPS.slice(0, 3).map((step) => (
                <div
                  key={step.id}
                  className="p-3 text-xs flex items-center justify-between"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-content-muted">
                      #{step.step_index + 1}
                    </span>
                    <span className="font-medium text-content-primary">
                      {step.title}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] uppercase font-bold text-content-muted">
                    {step.tool_name}
                  </span>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <Link href={`/runs/${run.id}/timeline`}>
                <Button variant="outline" size="sm">
                  View Full Execution Timeline
                  <ArrowRight
                    className="h-3.5 w-3.5 ml-1.5"
                    aria-hidden="true"
                  />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Runtime Diagnostics */}
        <Card>
          <CardHeader>
            <CardTitle>Runtime Parameters</CardTitle>
            <CardDescription>Guaranteed execution bounds.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">LLM Provider</span>
              <span className="font-mono font-semibold">
                mock-deterministic-v1
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Search Provider</span>
              <span className="font-mono font-semibold">mock-corpus</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Budget Limit</span>
              <span className="font-mono font-semibold">
                {formatUSD(run.budget_usd_limit)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Estimated Cost</span>
              <span className="font-mono font-semibold">
                {formatUSD(run.estimated_cost_usd)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Timeout Ceiling</span>
              <span className="font-mono font-semibold">300 seconds</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-content-muted">Durable Checkpoint</span>
              <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                PostgreSQL Verified
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Audit Log for this Run */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Audit Trail (Immutable Events)</CardTitle>
          <CardDescription>
            Chronological transaction log for this execution.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp (UTC)</TableHead>
                <TableHead>Event Type</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Correlation ID</TableHead>
                <TableHead>Payload Preview</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {DEMO_AUDIT_EVENTS.map((evt) => (
                <TableRow key={evt.id}>
                  <TableCell className="text-xs text-content-muted whitespace-nowrap">
                    {formatTimestamp(evt.timestamp)}
                  </TableCell>
                  <TableCell>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono font-semibold">
                      {evt.event_type}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs font-medium text-content-primary">
                    {evt.actor}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-content-muted">
                    {evt.correlation_id}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-content-muted max-w-xs truncate">
                    {JSON.stringify(evt.payload)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
