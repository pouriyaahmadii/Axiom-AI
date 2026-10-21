import * as React from "react";
import { ExternalLink, ShieldCheck } from "lucide-react";
import { RunHeader } from "@/components/runs/run-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DEMO_EVIDENCE, DEMO_RUNS, type DemoRun } from "@/lib/mock-data";
import { formatTimestamp, truncateIdentifier } from "@/lib/utils";

export default function RunEvidencePage({
  params,
}: {
  params: { id: string };
}) {
  const run: DemoRun =
    DEMO_RUNS.find((r) => r.id === params.id) ?? (DEMO_RUNS[0] as DemoRun);

  return (
    <div className="space-y-6">
      <RunHeader run={run} />

      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <CardTitle>Grounded Evidence & Primary Sources</CardTitle>
            <CardDescription>
              Verified web pages, content hashes, and structured factual claims
              extracted during execution.
            </CardDescription>
          </div>
          <span className="text-xs font-mono font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
            <ShieldCheck className="h-4 w-4" />
            100% Citation Grounding
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source & URL</TableHead>
                <TableHead>Target Entity</TableHead>
                <TableHead>Extracted Fact / Passage</TableHead>
                <TableHead>Content Hash (SHA-256)</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Retrieved</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {DEMO_EVIDENCE.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-xs">
                    <div className="font-semibold text-xs text-content-primary">
                      {item.title}
                    </div>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 mt-0.5 truncate max-w-full font-mono"
                    >
                      <span>{item.url}</span>
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                  </TableCell>
                  <TableCell>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono font-medium">
                      {item.related_entity}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-md">
                    <p className="text-xs text-content-primary line-clamp-3 leading-relaxed">
                      &ldquo;{item.passage}&rdquo;
                    </p>
                  </TableCell>
                  <TableCell>
                    <code className="font-mono text-[11px] text-content-muted bg-muted px-1.5 py-0.5 rounded">
                      {truncateIdentifier(item.content_hash, 6, 4)}
                    </code>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        item.validation_status === "VERIFIED"
                          ? "success"
                          : "warning"
                      }
                    >
                      {item.validation_status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-content-muted whitespace-nowrap">
                    {formatTimestamp(item.retrieved_at)}
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
