import {
  Clock,
  Cpu,
  PlayCircle,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Ban,
  UserX,
  type LucideIcon,
} from "lucide-react";

export type RunStatusType =
  | "QUEUED"
  | "PLANNING"
  | "RUNNING"
  | "AWAITING_APPROVAL"
  | "COMPLETED"
  | "COMPLETED_WITH_WARNINGS"
  | "FAILED"
  | "CANCELLED"
  | "ABORTED_BY_OPERATOR";

export interface StatusMeta {
  label: string;
  variant: "neutral" | "info" | "success" | "warning" | "danger";
  icon: LucideIcon;
  description: string;
}

export const RUN_STATUS_META: Record<RunStatusType, StatusMeta> = {
  QUEUED: {
    label: "Queued",
    variant: "neutral",
    icon: Clock,
    description: "Waiting in task queue for worker allocation",
  },
  PLANNING: {
    label: "Planning",
    variant: "info",
    icon: Cpu,
    description: "Synthesizing execution DAG with LLM",
  },
  RUNNING: {
    label: "Running",
    variant: "info",
    icon: PlayCircle,
    description: "Executing plan steps through sandboxed tools",
  },
  AWAITING_APPROVAL: {
    label: "Awaiting Approval",
    variant: "warning",
    icon: AlertTriangle,
    description: "Paused at human-in-the-loop checkpoint",
  },
  COMPLETED: {
    label: "Completed",
    variant: "success",
    icon: CheckCircle2,
    description: "Successfully finished with verified evidence",
  },
  COMPLETED_WITH_WARNINGS: {
    label: "Completed (Warnings)",
    variant: "warning",
    icon: AlertCircle,
    description: "Finished with partial contradictions or missing citations",
  },
  FAILED: {
    label: "Failed",
    variant: "danger",
    icon: XCircle,
    description: "Execution halted due to unrecoverable error",
  },
  CANCELLED: {
    label: "Cancelled",
    variant: "neutral",
    icon: Ban,
    description: "Cancelled upon operator request",
  },
  ABORTED_BY_OPERATOR: {
    label: "Aborted by Operator",
    variant: "neutral",
    icon: UserX,
    description: "Rejected by operator at approval checkpoint",
  },
};

export interface NavigationItem {
  name: string;
  href: string;
  iconName: string;
  badge?: number;
}

export const MAIN_NAVIGATION: NavigationItem[] = [
  { name: "Dashboard", href: "/dashboard", iconName: "LayoutDashboard" },
  { name: "New Analysis", href: "/runs/new", iconName: "PlusCircle" },
  { name: "Approvals", href: "/approvals", iconName: "ShieldAlert", badge: 1 },
  { name: "Evidence Explorer", href: "/evidence", iconName: "Database" },
  { name: "Audit Log", href: "/audit", iconName: "FileText" },
  { name: "Settings", href: "/settings", iconName: "Settings" },
];
