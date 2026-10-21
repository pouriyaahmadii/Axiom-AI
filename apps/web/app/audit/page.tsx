"use client";

import * as React from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronRight,
  Filter,
  Search,
  ShieldCheck,
} from "lucide-react";
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
import { DEMO_AUDIT_EVENTS } from "@/lib/mock-data";
import { formatTimestamp, truncateIdentifier } from "@/lib/utils";

export default function AuditHistoryPage() {
  const [selectedEventType, setSelectedEventType] =
    React.useState<string>("ALL");
  const [expandedEventId, setExpandedEventId] = React.useState<string | null>(
    null,
  );

  const filteredEvents =
    selectedEventType === "ALL"
      ? DEMO_AUDIT_EVENTS
      : DEMO_AUDIT_EVENTS.filter((e) => e.event_type === selectedEventType);

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Audit History" },
        ]}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between pb-2 border-b border-border">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
            System Audit History
          </h1>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Cryptographically sealed and immutable audit event ledger.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="success">
            <ShieldCheck className="h-3.5 w-3.5 mr-1" />
            Append-Only Verification
          </Badge>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative w-64">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-content-muted" />
              <input
                type="search"
                placeholder="Search correlation ID or actor..."
                className="h-8 w-full rounded-md border border-border bg-muted/50 pl-8 pr-3 text-xs text-content-primary placeholder:text-content-muted focus-ring"
              />
            </div>

            <div className="flex items-center gap-1.5 text-xs">
              <Filter className="h-3.5 w-3.5 text-content-muted" />
              <span className="text-content-muted">Filter:</span>
              <select
                value={selectedEventType}
                onChange={(e) => setSelectedEventType(e.target.value)}
                className="h-8 rounded-md border border-border bg-surface px-2.5 text-xs text-content-primary focus-ring"
              >
                <option value="ALL">All Event Types</option>
                <option value="RUN_QUEUED">RUN_QUEUED</option>
                <option value="PLAN_SYNTHESIZED">PLAN_SYNTHESIZED</option>
                <option value="TOOL_CALLED">TOOL_CALLED</option>
                <option value="APPROVAL_REQUESTED">APPROVAL_REQUESTED</option>
              </select>
            </div>
          </div>

          <span className="text-xs font-mono text-content-muted">
            {filteredEvents.length} recorded events
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>Timestamp (UTC)</TableHead>
                <TableHead>Event Classification</TableHead>
                <TableHead>Actor Identity</TableHead>
                <TableHead>Target Run</TableHead>
                <TableHead>Correlation ID</TableHead>
                <TableHead>Payload Preview</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEvents.map((evt) => {
                const isExpanded = expandedEventId === evt.id;

                return (
                  <React.Fragment key={evt.id}>
                    <TableRow
                      onClick={() =>
                        setExpandedEventId(isExpanded ? null : evt.id)
                      }
                      className="cursor-pointer"
                    >
                      <TableCell className="w-10 p-2 text-center text-content-muted">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </TableCell>
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
                      <TableCell className="font-mono text-xs">
                        <Link
                          href={`/runs/${evt.run_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          {truncateIdentifier(evt.run_id)}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-content-muted">
                        {evt.correlation_id}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-content-muted max-w-xs truncate">
                        {JSON.stringify(evt.payload)}
                      </TableCell>
                    </TableRow>

                    {isExpanded && (
                      <TableRow className="bg-muted/30">
                        <TableCell colSpan={7} className="p-4">
                          <div className="space-y-2">
                            <span className="text-xs font-semibold text-content-secondary block">
                              Full Audit Event Payload (Immutable Record):
                            </span>
                            <pre className="font-mono text-[11px] bg-slate-900 text-slate-100 p-3 rounded overflow-x-auto leading-relaxed">
                              {JSON.stringify(evt, null, 2)}
                            </pre>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
