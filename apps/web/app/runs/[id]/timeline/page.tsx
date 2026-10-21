"use client";

import * as React from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  RefreshCw,
} from "lucide-react";
import { RunHeader } from "@/components/runs/run-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { apiClient, type RunStep, type RunDetail } from "@/lib/api-client";
import {
  DEMO_RUNS,
  DEMO_STEPS,
  type DemoRun,
  type DemoStep,
} from "@/lib/mock-data";
import { formatTimestamp } from "@/lib/utils";

export default function ExecutionTimelinePage({
  params,
}: {
  params: { id: string };
}) {
  const [run, setRun] = React.useState<RunDetail | DemoRun | null>(null);
  const [steps, setSteps] = React.useState<Array<RunStep | DemoStep>>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [expandedStep, setExpandedStep] = React.useState<string | null>(null);

  const fetchTimeline = React.useCallback(async () => {
    try {
      const [runData, stepsData] = await Promise.all([
        apiClient.getRun(params.id),
        apiClient.getRunSteps(params.id),
      ]);
      setRun(runData);
      if (stepsData.items && stepsData.items.length > 0) {
        setSteps(stepsData.items);
        if (!expandedStep && stepsData.items[0]) {
          setExpandedStep(stepsData.items[0].step_id);
        }
      } else {
        setSteps(DEMO_STEPS);
        const defaultStep = DEMO_STEPS[2] ?? DEMO_STEPS[0];
        if (defaultStep) {
          setExpandedStep(defaultStep.id);
        }
      }
    } catch {
      const fallbackRun: DemoRun =
        DEMO_RUNS.find((r) => r.id === params.id) ?? DEMO_RUNS[0]!;
      setRun(fallbackRun);
      setSteps(DEMO_STEPS);
      const defaultStep = DEMO_STEPS[2] ?? DEMO_STEPS[0];
      if (defaultStep) {
        setExpandedStep(defaultStep.id);
      }
    } finally {
      setIsLoading(false);
    }
  }, [params.id, expandedStep]);

  React.useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  const toggleStep = (stepId: string) => {
    setExpandedStep(expandedStep === stepId ? null : stepId);
  };

  const normalizedRun: DemoRun = run
    ? {
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
        steps_total: steps.length || 5,
        steps_completed: steps.filter((s) => s.status === "COMPLETED").length,
      }
    : DEMO_RUNS[0]!;

  return (
    <div className="space-y-6">
      <RunHeader run={normalizedRun} />

      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle>LangGraph Execution DAG & Step Sequence</CardTitle>
            <CardDescription>
              Deterministic step execution sequence with parameters, timing, and
              tool outputs.
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={fetchTimeline}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh Steps
          </Button>
        </CardHeader>

        <CardContent className="space-y-4">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : (
            <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-border">
              {steps.map((step) => {
                const stepKey = "step_id" in step ? step.step_id : step.id;
                const isExpanded = expandedStep === stepKey;

                return (
                  <div key={stepKey} className="relative group">
                    {/* Timeline Node Bullet */}
                    <div className="absolute -left-6 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-surface border-2 border-border shadow-sm">
                      {step.status === "COMPLETED" && (
                        <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                      )}
                      {step.status === "RUNNING" && (
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600"></span>
                        </span>
                      )}
                      {step.status === "PENDING" && (
                        <Clock className="h-2.5 w-2.5 text-content-disabled" />
                      )}
                    </div>

                    {/* Step Card */}
                    <div className="rounded-lg border border-border bg-surface shadow-sm overflow-hidden transition-colors">
                      <button
                        type="button"
                        onClick={() => toggleStep(stepKey)}
                        className="w-full p-4 flex items-center justify-between text-left hover:bg-muted/40 transition-colors focus-ring"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-xs font-bold text-content-muted">
                            #{step.step_index + 1}
                          </span>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <h4 className="text-xs font-semibold text-content-primary sm:text-sm">
                                {step.title}
                              </h4>
                              {step.requires_human_approval && (
                                <span className="rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-700 px-2 py-0.5 text-[10px] font-bold">
                                  HITL GATE
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-[11px] text-content-muted">
                              <span className="font-mono bg-muted px-1.5 py-0.2 rounded">
                                tool: {step.tool_name}
                              </span>
                              {step.started_at && (
                                <span>
                                  Started: {formatTimestamp(step.started_at)}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <Badge
                            variant={
                              step.status === "COMPLETED"
                                ? "success"
                                : step.status === "RUNNING"
                                  ? "info"
                                  : "neutral"
                            }
                          >
                            {step.status}
                          </Badge>
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-content-muted" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-content-muted" />
                          )}
                        </div>
                      </button>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <div className="p-4 pt-2 border-t border-border/60 bg-muted/20 space-y-3 text-xs">
                          {"output_summary" in step && step.output_summary && (
                            <div>
                              <span className="font-semibold text-content-secondary block mb-1">
                                Execution Result:
                              </span>
                              <p className="text-content-primary bg-surface p-2.5 rounded border border-border/60 leading-relaxed font-mono text-[11px]">
                                {step.output_summary}
                              </p>
                            </div>
                          )}

                          {"error_message" in step &&
                            Boolean(step.error_message) && (
                              <Alert variant="danger" title="Step Error">
                                {step.error_message}
                              </Alert>
                            )}

                          <div>
                            <span className="font-semibold text-content-secondary block mb-1">
                              Input Parameters & Safeguards:
                            </span>
                            <pre className="font-mono text-[11px] bg-slate-900 text-slate-100 p-3 rounded overflow-x-auto leading-relaxed max-h-48">
                              {JSON.stringify(step.parameters, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
