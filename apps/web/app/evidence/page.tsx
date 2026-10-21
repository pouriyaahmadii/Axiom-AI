import * as React from "react";
import { ExternalLink, Search } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { DEMO_EVIDENCE } from "@/lib/mock-data";
import { formatTimestamp, truncateIdentifier } from "@/lib/utils";

export default function GlobalEvidencePage() {
  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Global Evidence Explorer" },
        ]}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between pb-2 border-b border-border">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
            Evidence & Knowledge Repository
          </h1>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Traceable repository of verified sources, hashed content snapshots,
            and extracted facts.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded bg-muted px-2 py-1 text-xs font-mono font-semibold text-content-muted">
            {DEMO_EVIDENCE.length} Captured Items
          </span>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-content-muted" />
            <input
              type="search"
              placeholder="Filter by entity, claim, or domain..."
              className="h-8 w-full rounded-md border border-border bg-muted/50 pl-8 pr-3 text-xs text-content-primary placeholder:text-content-muted focus-ring"
            />
          </div>
          <span className="text-xs font-mono text-content-muted">
            All records cryptographically hashed (SHA-256)
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source & URL</TableHead>
                <TableHead>Target Entity</TableHead>
                <TableHead>Extracted Fact / Evidence Excerpt</TableHead>
                <TableHead>Content Hash</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Captured</TableHead>
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
                      <span>{item.domain}</span>
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                  </TableCell>
                  <TableCell>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs font-mono font-medium">
                      {item.related_entity}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-md">
                    <p className="text-xs text-content-primary line-clamp-2 leading-relaxed">
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
