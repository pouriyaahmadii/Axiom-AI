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
import { Alert } from "@/components/ui/alert";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { apiClient, ApiClientError } from "@/lib/api-client";

const DOMAIN_OPTIONS = [
  { value: "ai-observability", label: "AI Observability & Evaluations" },
  { value: "devtools", label: "Developer Tools & Infrastructure" },
  { value: "databases", label: "Vector & Relational Databases" },
  { value: "security", label: "Cloud Security & Compliance" },
  { value: "general-tech", label: "General Technology Research" },
];

export default function NewAnalysisPage() {
  const router = useRouter();

  const [objective, setObjective] = React.useState(
    "Competitive landscape analysis of AI agent observability and evaluation frameworks in Q4 2026",
  );
  const [domain, setDomain] = React.useState("ai-observability");
  const [geography, setGeography] = React.useState("Global");
  const [budgetLimit, setBudgetLimit] = React.useState("1.00");
  const [providerMode, setProviderMode] = React.useState<"mock" | "live">(
    "mock",
  );
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [validationError, setValidationError] = React.useState<string | null>(
    null,
  );
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [correlationId, setCorrelationId] = React.useState<string | undefined>(
    undefined,
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setServerError(null);

    // 1. Client-Side Usability Validations
    const trimmedObjective = objective.trim();
    if (!trimmedObjective || trimmedObjective.length < 10) {
      setValidationError(
        "Research objective must be at least 10 characters long.",
      );
      return;
    }
    if (trimmedObjective.length > 2000) {
      setValidationError(
        "Research objective exceeds maximum limit of 2000 characters.",
      );
      return;
    }

    const trimmedDomain = domain.trim();
    if (!trimmedDomain || trimmedDomain.length < 2) {
      setValidationError("Domain must be specified (at least 2 characters).");
      return;
    }

    const budgetNum = parseFloat(budgetLimit);
    if (isNaN(budgetNum) || budgetNum < 0.1 || budgetNum > 5.0) {
      setValidationError("Budget limit must be between $0.10 and $5.00 USD.");
      return;
    }

    setIsSubmitting(true);

    try {
      const idempotencyKey = `web-${Math.random().toString(36).substring(2, 10)}-${Date.now()}`;

      const res = await apiClient.createRun({
        objective: trimmedObjective,
        domain: trimmedDomain,
        geography: geography.trim() || null,
        budget_usd_limit: budgetNum,
        idempotency_key: idempotencyKey,
        provider_override: {
          llm: providerMode,
          search: providerMode,
        },
      });

      // HTTP 202 Accepted -> Navigate to the live run
      router.push(`/runs/${res.run_id}`);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setServerError(err.message);
        setCorrelationId(err.correlationId);
      } else {
        setServerError(
          err instanceof Error
            ? err.message
            : "Failed to submit research run to backend API.",
        );
      }
      setIsSubmitting(false);
    }
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

      {serverError && (
        <Alert variant="danger" title="API Submission Error">
          <div>
            <p>{serverError}</p>
            {correlationId && (
              <span className="font-mono text-[10px] mt-1 block opacity-80">
                Correlation ID: {correlationId}
              </span>
            )}
          </div>
        </Alert>
      )}

      {validationError && (
        <Alert variant="warning" title="Validation Notice">
          {validationError}
        </Alert>
      )}

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
              error={
                validationError && objective.length < 10
                  ? validationError
                  : undefined
              }
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
                      Deterministic offline seed (Zero Cost)
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
