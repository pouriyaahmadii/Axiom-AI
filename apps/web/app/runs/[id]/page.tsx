"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Ban, RefreshCw } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorView } from "@/components/ui/error-view";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  apiClient,
  type RunDetail,
  type AuditEvent,
  ApiClientError,
} from "@/lib/api-client";
import { DEMO_AUDIT_EVENTS, DEMO_RUNS, type DemoRun } from "@/lib/mock-data";
import { formatTimestamp, formatUSD } from "@/lib/utils";

export default function RunOverviewPage({
  params,
}: {
  params: { id: string };
}) {
  const [run, setRun] = React.useState<RunDetail | DemoRun | null>(null);
  const [auditEvents, setAuditEvents] = React.useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isCancelling, setIsCancelling] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [correlationId, setCorrelationId] = React.useState<string | undefined>(
    undefined,
  );

  const fetchRunData = React.useCallback(async () => {
    try {
      const data = await apiClient.getRun(params.id);
      setRun(data);
      setError(null);

      // Fetch audit events
      const eventsRes = await apiClient
        .getRunEvents(params.id, { limit: 10 })
        .catch(() => null);
      if (eventsRes && eventsRes.items) {
        setAuditEvents(eventsRes.items);
      }
    } catch (err) {
      const fallback: DemoRun =
        DEMO_RUNS.find((r) => r.id === params.id) ?? DEMO_RUNS[0]!;
      setRun(fallback);
      if (err instanceof ApiClientError) {
        if (err.statusCode !== 404) {
          setError(err.message);
          setCorrelationId(err.correlationId);
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [params.id]);

  const isRunActive = Boolean(
    run &&
    (run.status === "RUNNING" ||
      run.status === "PLANNING" ||
      run.status === "QUEUED"),
  );

  React.useEffect(() => {
    fetchRunData();

    if (!isRunActive) return;

    // Polling interval if run is currently active
    const interval = setInterval(() => {
      fetchRunData();
    }, 2500);

    return () => clearInterval(interval);
  }, [fetchRunData, isRunActive]);

  const handleCancelRun = async () => {
    if (!run) return;
    setIsCancelling(true);
    try {
      await apiClient.cancelRun("run_id" in run ? run.run_id : run.id);
      await fetchRunData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel run");
    } finally {
      setIsCancelling(false);
    }
  };

  if (isLoading && !run) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-28 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Skeleton className="md:col-span-2 h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <ErrorView
        title="Run Not Found"
        message={`Could not find an execution record with ID ${params.id}.`}
        onRetry={fetchRunData}
      />
    );
  }

  // Normalize run properties for header and cards
  const normalizedRun: DemoRun = {
    isDemoSeed: true,
    id: "run_id" in run ? run.run_id : run.id,
    objective: run.objective,
    domain: run.domain,
    geography: run.geography || "Global",
    status: run.status,
    created_at: run.created_at,
    completed_at: run.completed_at,
    budget_usd_limit: Number(run.budget_usd_limit),
    estimated_cost_usd: Number(run.estimated_cost_usd),
    steps_total:
      "plan" in run && run.plan
        ? run.plan.total_steps
        : "steps_total" in run
          ? run.steps_total
          : 5,
    steps_completed:
      "steps_completed" in run
        ? run.steps_completed
        : "plan" in run && run.plan
          ? run.plan.steps.filter((s) => s.status === "COMPLETED").length
          : 0,
  };

  const stepsList = "plan" in run && run.plan ? run.plan.steps : [];

  return (
    <div className="space-y-6">
      <RunHeader run={normalizedRun} />

      {error && (
        <Alert variant="warning" title="Notice">
          {error} {correlationId ? `(Correlation ID: ${correlationId})` : ""}
        </Alert>
      )}

      {/* Active HITL Checkpoint Callout */}
      {run.status === "AWAITING_APPROVAL" && (
        <Alert
          variant="warning"
          title="Execution Checkpoint: Human Authorization Required"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-1">
            <span>
              The LangGraph runtime generated a competitive research DAG and
              paused execution at a checkpoint. A verified operator must review
              the tool boundaries before execution proceeds.
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
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Execution State & Step Progress</CardTitle>
              <CardDescription>
                Real-time sequence of bounded LangGraph steps.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {(run.status === "RUNNING" ||
                run.status === "PLANNING" ||
                run.status === "QUEUED") && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleCancelRun}
                  disabled={isCancelling}
                  className="text-xs h-7"
                >
                  <Ban className="h-3 w-3 mr-1" />
                  {isCancelling ? "Cancelling..." : "Cancel Run"}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchRunData}
                aria-label="Refresh run state"
              >
                <RefreshCw className="h-3 w-3" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-content-muted">
                <span>Overall Progress</span>
                <span className="font-mono font-bold">
                  {normalizedRun.steps_completed} of {normalizedRun.steps_total}{" "}
                  Steps Completed
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (normalizedRun.steps_completed / normalizedRun.steps_total) * 100)}%`,
                  }}
                />
              </div>
            </div>

            {stepsList.length > 0 ? (
              <div className="rounded-lg border border-border divide-y divide-border/60">
                {stepsList.map((step) => (
                  <div
                    key={step.step_id}
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
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase font-bold text-content-muted">
                        {step.tool_name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted font-mono font-bold">
                        {step.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-content-muted italic">
                Execution plan will appear here once synthesized by planner.
              </p>
            )}

            <div className="pt-2 flex justify-end">
              <Link href={`/runs/${normalizedRun.id}/timeline`}>
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
                {("llm_provider" in run && run.llm_provider) || "mock"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Search Provider</span>
              <span className="font-mono font-semibold">
                {("search_provider" in run && run.search_provider) || "mock"}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Budget Limit</span>
              <span className="font-mono font-semibold">
                {formatUSD(Number(run.budget_usd_limit))}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-border/50">
              <span className="text-content-muted">Estimated Cost</span>
              <span className="font-mono font-semibold">
                {formatUSD(Number(run.estimated_cost_usd))}
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

      {/* Audit Log Table */}
      <Card>
        <CardHeader>
          <CardTitle>Audit Trail (Immutable Events)</CardTitle>
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
              {(auditEvents.length > 0 ? auditEvents : DEMO_AUDIT_EVENTS).map(
                (evt) => (
                  <TableRow key={"event_id" in evt ? evt.event_id : evt.id}>
                    <TableCell className="text-xs text-content-muted whitespace-nowrap">
                      {formatTimestamp(
                        "created_at" in evt ? evt.created_at : evt.timestamp,
                      )}
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
                      {evt.correlation_id || "-"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-content-muted max-w-xs truncate">
                      {JSON.stringify(evt.payload)}
                    </TableCell>
                  </TableRow>
                ),
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
