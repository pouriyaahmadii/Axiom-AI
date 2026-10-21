"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";

const DOMAIN_OPTIONS = [
  { value: "ai-observability", label: "AI Observability & Evaluations" },
  { value: "devtools", label: "Developer Tools & Infrastructure" },
  { value: "databases", label: "Vector & Relational Databases" },
  { value: "security", label: "Cloud Security & Compliance" },
  { value: "other", label: "Custom Domain..." },
];

export default function NewAnalysisPage() {
  const router = useRouter();

  const [objective, setObjective] = React.useState(
    "Competitive landscape analysis of AI agent observability and evaluation frameworks in Q4 2026",
  );
  const [domain, setDomain] = React.useState("ai-observability");
  const [geography, setGeography] = React.useState("Global");
  const [budgetLimit, setBudgetLimit] = React.useState("1.00");
  const [requirePlanApproval, setRequirePlanApproval] = React.useState(true);
  const [requireReportApproval, setRequireReportApproval] =
    React.useState(false);
  const [providerMode, setProviderMode] = React.useState("mock");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!objective.trim() || objective.length < 10) {
      setError("Objective must be at least 10 characters long.");
      return;
    }
    setError(null);
    setIsSubmitting(true);

    // Simulated acceptance transition for Phase 17 UI preview
    setTimeout(() => {
      setIsSubmitting(false);
      // Route to our seeded run detail view
      router.push("/runs/9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3");
    }, 600);
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Runs", href: "/dashboard" },
          { label: "New Analysis" },
        ]}
      />

      <div className="flex items-center justify-between pb-2 border-b border-border">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
            Launch Research Analysis
          </h1>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Configure an asynchronous, bounded analytical agent workflow.
          </p>
        </div>
        <Link href="/dashboard">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-1.5" aria-hidden="true" />
            Back
          </Button>
        </Link>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Research Scope & Objectives</CardTitle>
            <CardDescription>
              Define the analytical query and execution boundaries.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              label="Primary Research Objective"
              required
              rows={3}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              charCount={{ current: objective.length, max: 2000 }}
              hint="Specify the competitive entities, market segment, and evaluation parameters."
              error={error || undefined}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select
                label="Target Domain"
                required
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                options={DOMAIN_OPTIONS}
              />
              <Input
                label="Geographical Scope"
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                hint="e.g. Global, North America, EMEA"
              />
            </div>
          </CardContent>
        </Card>

        {/* Governance & Safeguards */}
        <Card>
          <CardHeader>
            <CardTitle>Governance & Execution Safeguards</CardTitle>
            <CardDescription>
              Enforce hard budget ceilings and Human-in-the-Loop approval
              checkpoints.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Budget Limit (USD)"
                type="number"
                step="0.10"
                min="0.10"
                max="5.00"
                required
                value={budgetLimit}
                onChange={(e) => setBudgetLimit(e.target.value)}
                hint="Hard ceiling limit. Run terminates if spend exceeds limit."
              />

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-content-secondary">
                  Execution Provider Mode
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setProviderMode("mock")}
                    className={`flex-1 rounded-md border p-2.5 text-left text-xs transition-all focus-ring ${
                      providerMode === "mock"
                        ? "border-blue-600 bg-blue-50/50 dark:bg-blue-950/30 text-blue-900 dark:text-blue-200 font-semibold"
                        : "border-border bg-surface text-content-secondary hover:bg-muted"
                    }`}
                  >
                    <div className="font-bold flex items-center justify-between">
                      Mock Mode
                      {providerMode === "mock" && (
                        <Check className="h-3.5 w-3.5 text-blue-600" />
                      )}
                    </div>
                    <span className="text-[11px] opacity-80 block mt-0.5">
                      Deterministic offline seed
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setProviderMode("live")}
                    className={`flex-1 rounded-md border p-2.5 text-left text-xs transition-all focus-ring ${
                      providerMode === "live"
                        ? "border-blue-600 bg-blue-50/50 dark:bg-blue-950/30 text-blue-900 dark:text-blue-200 font-semibold"
                        : "border-border bg-surface text-content-secondary hover:bg-muted"
                    }`}
                  >
                    <div className="font-bold flex items-center justify-between">
                      Live Providers
                      {providerMode === "live" && (
                        <Check className="h-3.5 w-3.5 text-blue-600" />
                      )}
                    </div>
                    <span className="text-[11px] opacity-80 block mt-0.5">
                      OpenAI / Tavily API
                    </span>
                  </button>
                </div>
              </div>
            </div>

            {/* Checkpoints */}
            <div className="pt-3 border-t border-border/60 space-y-2">
              <label className="block text-xs font-semibold text-content-secondary">
                Human-in-the-Loop Checkpoints
              </label>

              <label className="flex items-start gap-2.5 cursor-pointer text-xs text-content-primary">
                <input
                  type="checkbox"
                  checked={requirePlanApproval}
                  onChange={(e) => setRequirePlanApproval(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
                />
                <div>
                  <span className="font-medium">
                    Require approval on generated plan
                  </span>
                  <p className="text-[11px] text-content-muted">
                    Execution pauses after plan synthesis to let you review the
                    DAG and tools before any network requests occur.
                  </p>
                </div>
              </label>

              <label className="flex items-start gap-2.5 cursor-pointer text-xs text-content-primary">
                <input
                  type="checkbox"
                  checked={requireReportApproval}
                  onChange={(e) => setRequireReportApproval(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-blue-600 focus:ring-blue-500"
                />
                <div>
                  <span className="font-medium">
                    Require approval before publishing final report
                  </span>
                  <p className="text-[11px] text-content-muted">
                    Execution holds before marking the run completed to permit
                    report draft review.
                  </p>
                </div>
              </label>
            </div>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Link href="/dashboard">
              <Button type="button" variant="outline" size="sm">
                Cancel
              </Button>
            </Link>
            <Button type="submit" size="sm" isLoading={isSubmitting}>
              <Sparkles className="h-4 w-4 mr-1.5" aria-hidden="true" />
              Enqueue Research Run
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}
