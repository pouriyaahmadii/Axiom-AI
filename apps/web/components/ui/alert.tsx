import * as React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "info" | "success" | "warning" | "danger";
  title?: string;
  icon?: boolean;
}

const ALERT_ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertCircle,
};

export function Alert({
  className,
  variant = "info",
  title,
  icon = true,
  children,
  ...props
}: AlertProps) {
  const IconComponent = ALERT_ICONS[variant];

  const variantStyles = {
    info: "bg-status-info-bg text-status-info-text border-status-info-border",
    success:
      "bg-status-success-bg text-status-success-text border-status-success-border",
    warning:
      "bg-status-warning-bg text-status-warning-text border-status-warning-border",
    danger:
      "bg-status-danger-bg text-status-danger-text border-status-danger-border",
  };

  return (
    <div
      role="alert"
      className={cn(
        "relative w-full rounded-lg border p-4 text-sm flex gap-3 items-start",
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {icon && (
        <IconComponent
          className="h-5 w-5 flex-shrink-0 mt-0.5"
          aria-hidden="true"
        />
      )}
      <div className="flex-1 space-y-1">
        {title && <h5 className="font-semibold leading-tight">{title}</h5>}
        <div className="text-xs leading-relaxed opacity-95">{children}</div>
      </div>
    </div>
  );
}
