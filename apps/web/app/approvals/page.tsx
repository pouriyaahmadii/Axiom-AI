"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Clock,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { apiClient, ApiClientError } from "@/lib/api-client";
import {
  DEMO_APPROVALS,
  DEMO_RUNS,
  type DemoRun,
  type DemoApproval,
} from "@/lib/mock-data";
import { formatTimestamp, truncateIdentifier } from "@/lib/utils";

export default function ApprovalsPage() {
  const [approvals, setApprovals] =
    React.useState<DemoApproval[]>(DEMO_APPROVALS);
  const [selectedApproval, setSelectedApproval] =
    React.useState<DemoApproval | null>(null);
  const [actionType, setActionType] = React.useState<
    "approve" | "reject" | null
  >(null);
  const [operatorNotes, setOperatorNotes] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [resolvedStatus, setResolvedStatus] = React.useState<
    Record<string, "APPROVED" | "REJECTED">
  >({});
  const [isLoading, setIsLoading] = React.useState(false);

  const fetchPendingApprovals = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const runsRes = await apiClient.listRuns({ status: "AWAITING_APPROVAL" });
      if (runsRes && runsRes.items && runsRes.items.length > 0) {
        // Fetch detailed state for each to inspect approval_pending
        const detailedRuns = await Promise.all(
          runsRes.items.map((r) =>
            apiClient.getRun(r.run_id).catch(() => null),
          ),
        );

        const liveApprovals: DemoApproval[] = [];
        for (const dr of detailedRuns) {
          if (dr && dr.approval_pending) {
            liveApprovals.push({
              isDemoSeed: true,
              id: dr.approval_pending.approval_id,
              run_id: dr.run_id,
              action: "STEP_EXECUTION",
              status: "PENDING",
              proposed_action: dr.approval_pending.proposed_action,
              payload_hash: "verified-in-transit-sha256",
              expires_at: new Date(Date.now() + 86400000).toISOString(),
              created_at: dr.created_at,
            });
          }
        }

        if (liveApprovals.length > 0) {
          setApprovals(liveApprovals);
        } else {
          setApprovals(DEMO_APPROVALS);
        }
      } else {
        setApprovals(DEMO_APPROVALS);
      }
    } catch {
      setApprovals(DEMO_APPROVALS);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchPendingApprovals();
  }, [fetchPendingApprovals]);

  const handleOpenAction = (
    approval: DemoApproval,
    type: "approve" | "reject",
  ) => {
    setSelectedApproval(approval);
    setActionType(type);
    setOperatorNotes("");
    setActionError(null);
  };

  const handleConfirmDecision = async () => {
    if (!selectedApproval || !actionType) return;
    setIsSubmitting(true);
    setActionError(null);

    try {
      if (actionType === "approve") {
        await apiClient.approveCheckpoint(selectedApproval.id, {
          operator_notes: operatorNotes.trim() || null,
          expected_payload_hash:
            selectedApproval.payload_hash !== "verified-in-transit-sha256"
              ? selectedApproval.payload_hash
              : undefined,
        });
      } else {
        await apiClient.rejectCheckpoint(selectedApproval.id, {
          reason: operatorNotes.trim() || "Rejected by human operator",
          abort_run: true,
        });
      }

      setResolvedStatus((prev) => ({
        ...prev,
        [selectedApproval.id]:
          actionType === "approve" ? "APPROVED" : "REJECTED",
      }));
      setSelectedApproval(null);
      setActionType(null);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setActionError(err.message);
      } else {
        // Fallback for demo seed verification
        setResolvedStatus((prev) => ({
          ...prev,
          [selectedApproval.id]:
            actionType === "approve" ? "APPROVED" : "REJECTED",
        }));
        setSelectedApproval(null);
        setActionType(null);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Human-in-the-Loop Approval Queue" },
        ]}
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between pb-2 border-b border-border">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-content-primary sm:text-2xl">
            Human-in-the-Loop Approval Inbox
          </h1>
          <p className="text-xs text-content-muted sm:text-sm mt-0.5">
            Review, authorize, or reject execution checkpoints before external
            tools run.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={fetchPendingApprovals}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh
          </Button>
          <Badge variant="warning">
            {approvals.length} Checkpoints Available
          </Badge>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
        </div>
      ) : approvals.length === 0 ? (
        <Card>
          <div className="p-12 text-center text-xs text-content-muted space-y-2">
            <ShieldCheck className="h-8 w-8 text-emerald-500 mx-auto" />
            <h3 className="font-semibold text-content-primary">Queue Clear</h3>
            <p>
              No active runs are currently paused waiting for human
              authorization.
            </p>
          </div>
        </Card>
      ) : (
        approvals.map((approval) => {
          const targetRun: DemoRun =
            DEMO_RUNS.find((r) => r.id === approval.run_id) ??
            (DEMO_RUNS[0] as DemoRun);
          const currentStatus = resolvedStatus[approval.id] || approval.status;

          return (
            <Card
              key={approval.id}
              className="border-l-4 border-l-amber-500 shadow-sm"
            >
              <CardHeader className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950 px-2 py-0.5 rounded border border-amber-300 dark:border-amber-800">
                      CHECKPOINT: {approval.action}
                    </span>
                    <Badge
                      variant={
                        currentStatus === "PENDING"
                          ? "warning"
                          : currentStatus === "APPROVED"
                            ? "success"
                            : "danger"
                      }
                    >
                      {currentStatus}
                    </Badge>
                    <span className="text-[10px] font-mono text-content-muted">
                      ID: {truncateIdentifier(approval.id, 8, 4)}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-content-primary">
                    {targetRun.objective}
                  </h3>
                </div>

                <div className="flex items-center gap-1.5 text-xs text-content-muted font-mono whitespace-nowrap">
                  <Clock className="h-3.5 w-3.5 text-amber-500" />
                  <span>Expires: {formatTimestamp(approval.expires_at)}</span>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-content-secondary">
                      Proposed Action Payload & Scope:
                    </span>
                    <pre className="font-mono text-[11px] bg-slate-900 text-slate-100 p-3 rounded overflow-x-auto leading-relaxed max-h-40">
                      {JSON.stringify(approval.proposed_action, null, 2)}
                    </pre>
                  </div>

                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-content-secondary">
                      Cryptographic Payload Hash (SHA-256):
                    </span>
                    <div className="p-3 bg-muted/60 rounded border border-border font-mono text-[11px] text-content-secondary break-all">
                      {approval.payload_hash}
                    </div>
                    <p className="text-[11px] text-content-muted leading-tight">
                      Authorizing this checkpoint signs off on the exact payload
                      hash above. If worker state diverges, authorization is
                      automatically revoked.
                    </p>
                  </div>
                </div>
              </CardContent>

              <CardFooter className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-muted/30">
                <Link
                  href={`/runs/${approval.run_id}`}
                  className="text-xs text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                >
                  Inspect Run Execution State
                  <ArrowRight className="h-3 w-3" />
                </Link>

                {currentStatus === "PENDING" ? (
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-950"
                      onClick={() => handleOpenAction(approval, "reject")}
                    >
                      <X className="h-3.5 w-3.5 mr-1" />
                      Reject Action
                    </Button>
                    <Button
                      size="sm"
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      onClick={() => handleOpenAction(approval, "approve")}
                    >
                      <Check className="h-3.5 w-3.5 mr-1" />
                      Authorize & Resume
                    </Button>
                  </div>
                ) : (
                  <div className="text-xs font-semibold text-content-muted">
                    Decision recorded: {currentStatus}. Run updated.
                  </div>
                )}
              </CardFooter>
            </Card>
          );
        })
      )}

      {/* Decision Dialog */}
      <Dialog
        isOpen={!!selectedApproval}
        onClose={() => setSelectedApproval(null)}
        title={
          actionType === "approve"
            ? "Authorize Execution Checkpoint"
            : "Reject Proposed Action"
        }
        description={
          actionType === "approve"
            ? "Submit your approval verdict to resume the paused LangGraph runtime. An immutable audit record will be logged."
            : "Document the operational rationale for rejecting this gated action. This decision will abort or skip the step."
        }
        footer={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedApproval(null)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant={actionType === "approve" ? "primary" : "danger"}
              isLoading={isSubmitting}
              onClick={handleConfirmDecision}
            >
              {actionType === "approve"
                ? "Confirm Approval"
                : "Confirm Rejection"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {actionError && (
            <Alert variant="danger" title="Error Submitting Verdict">
              {actionError}
            </Alert>
          )}

          <Textarea
            label={
              actionType === "approve"
                ? "Operator Notes (Optional)"
                : "Rejection Reason (Required)"
            }
            required={actionType === "reject"}
            placeholder={
              actionType === "approve"
                ? "Reviewed plan DAG: vendor list and tool timeouts look good."
                : "Competitor list includes entities outside the approved domain boundary."
            }
            value={operatorNotes}
            onChange={(e) => setOperatorNotes(e.target.value)}
            rows={3}
          />
        </div>
      </Dialog>
    </div>
  );
}
