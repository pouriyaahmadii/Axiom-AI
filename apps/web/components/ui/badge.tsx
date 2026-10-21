import * as React from "react";
import { cn } from "@/lib/utils";
import { RUN_STATUS_META, type RunStatusType } from "@/lib/constants";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "neutral" | "info" | "success" | "warning" | "danger" | "outline";
  status?: RunStatusType;
  showIcon?: boolean;
}

export function Badge({
  className,
  variant = "neutral",
  status,
  showIcon = true,
  children,
  ...props
}: BadgeProps) {
  // If status is provided, derive semantic meta
  if (status && RUN_STATUS_META[status]) {
    const meta = RUN_STATUS_META[status];
    const Icon = meta.icon;

    const statusVariantStyles = {
      neutral:
        "bg-status-neutral-bg text-status-neutral-text border-status-neutral-border",
      info: "bg-status-info-bg text-status-info-text border-status-info-border",
      success:
        "bg-status-success-bg text-status-success-text border-status-success-border",
      warning:
        "bg-status-warning-bg text-status-warning-text border-status-warning-border",
      danger:
        "bg-status-danger-bg text-status-danger-text border-status-danger-border",
    };

    return (
      <span
        role="status"
        aria-label={`Status: ${meta.label}`}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border select-none",
          statusVariantStyles[meta.variant],
          className,
        )}
        {...props}
      >
        {showIcon && (
          <Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
        )}
        <span>{children || meta.label}</span>
      </span>
    );
  }

  // Generic badge fallback
  const genericStyles = {
    neutral:
      "bg-status-neutral-bg text-status-neutral-text border-status-neutral-border",
    info: "bg-status-info-bg text-status-info-text border-status-info-border",
    success:
      "bg-status-success-bg text-status-success-text border-status-success-border",
    warning:
      "bg-status-warning-bg text-status-warning-text border-status-warning-border",
    danger:
      "bg-status-danger-bg text-status-danger-text border-status-danger-border",
    outline: "border-border text-content-primary bg-transparent",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border select-none",
        genericStyles[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
