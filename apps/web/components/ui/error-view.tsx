import * as React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export interface ErrorViewProps {
  title?: string;
  message: string;
  correlationId?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorView({
  title = "An Operational Error Occurred",
  message,
  correlationId,
  onRetry,
  className,
}: ErrorViewProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/50 dark:bg-rose-950/20 p-6 text-center max-w-xl mx-auto my-8",
        className,
      )}
    >
      <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-full bg-rose-100 dark:bg-rose-900/40 text-rose-600 dark:text-rose-400 mb-3">
        <AlertCircle className="h-6 w-6" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-rose-900 dark:text-rose-200 mb-1">
        {title}
      </h3>
      <p className="text-xs text-rose-800/80 dark:text-rose-300/80 mb-3 leading-relaxed">
        {message}
      </p>
      {correlationId && (
        <div className="mb-4">
          <span className="text-[10px] uppercase font-bold tracking-wider text-rose-600/70 dark:text-rose-400/70">
            Correlation ID:
          </span>
          <code className="ml-1.5 font-mono text-xs bg-rose-100 dark:bg-rose-900/50 px-2 py-0.5 rounded text-rose-900 dark:text-rose-200">
            {correlationId}
          </code>
        </div>
      )}
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="border-rose-300 dark:border-rose-800 text-rose-800 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/40"
        >
          <RotateCcw className="h-3.5 w-3.5 mr-1.5" aria-hidden="true" />
          Retry Request
        </Button>
      )}
    </div>
  );
}
