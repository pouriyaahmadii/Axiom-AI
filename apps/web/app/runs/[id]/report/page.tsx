"use client";

import * as React from "react";
import {
  Download,
  ExternalLink,
  FileCheck,
  Printer,
  ShieldCheck,
} from "lucide-react";
import { RunHeader } from "@/components/runs/run-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DEMO_REPORT, DEMO_RUNS, type DemoRun } from "@/lib/mock-data";

export default function RunReportPage({ params }: { params: { id: string } }) {
  const run: DemoRun =
    DEMO_RUNS.find((r) => r.id === params.id) ?? (DEMO_RUNS[1] as DemoRun);

  const report = DEMO_REPORT;

  return (
    <div className="space-y-6">
      <RunHeader run={run} />

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-2">
          <FileCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          <h2 className="text-base font-bold text-content-primary">
            Synthesized Research Report
          </h2>
          <span className="rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 px-2 py-0.5 text-[10px] font-bold">
            100% GROUNDED
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Printer className="h-3.5 w-3.5 mr-1" />
            Print / PDF
          </Button>
          <Button variant="outline" size="sm">
            <Download className="h-3.5 w-3.5 mr-1" />
            Export Markdown
          </Button>
        </div>
      </div>

      {/* Executive Summary Card */}
      <Card className="border-l-4 border-l-blue-600 bg-blue-50/20 dark:bg-blue-950/10">
        <CardHeader>
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-blue-900 dark:text-blue-300">
            Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-content-primary leading-relaxed font-serif">
            {report.executive_summary}
          </p>
        </CardContent>
      </Card>

      {/* Report Markdown Content */}
      <Card>
        <CardContent className="p-6 sm:p-8 space-y-6 text-content-primary">
          <div className="prose dark:prose-invert max-w-none space-y-4">
            <h1 className="text-xl font-bold tracking-tight border-b border-border pb-3">
              {report.title}
            </h1>

            <div className="space-y-4 text-sm leading-relaxed whitespace-pre-line font-sans">
              {report.markdown_content}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Citations & Evidence Traceability Matrix */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            Verified Citations & Fact Grounding
          </CardTitle>
          <CardDescription>
            Every material claim in this synthesized report is grounded in
            primary evidence.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="divide-y divide-border/60">
            {report.citations.map((cite, index) => (
              <div
                key={cite.citation_id}
                className="py-3 text-xs flex items-start gap-3"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded bg-muted text-content-muted font-mono font-bold flex-shrink-0 text-[11px]">
                  [{index + 1}]
                </span>
                <div className="space-y-1 flex-1">
                  <p className="font-medium text-content-primary">
                    {cite.claim}
                  </p>
                  <a
                    href={cite.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 font-mono text-[11px]"
                  >
                    <span>{cite.url}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
