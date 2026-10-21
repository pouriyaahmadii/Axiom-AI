import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  charCount?: { current: number; max: number };
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, hint, charCount, id, ...props }, ref) => {
    const generatedId = React.useId();
    const textareaId = id || generatedId;

    return (
      <div className="w-full space-y-1.5">
        <div className="flex items-center justify-between">
          {label && (
            <label
              htmlFor={textareaId}
              className="block text-xs font-semibold text-content-secondary"
            >
              {label}
              {props.required && (
                <span className="text-rose-500 ml-1" aria-hidden="true">
                  *
                </span>
              )}
            </label>
          )}
          {charCount && (
            <span
              className={cn(
                "text-xs font-mono",
                charCount.current > charCount.max
                  ? "text-rose-500 font-bold"
                  : "text-content-muted",
              )}
            >
              {charCount.current} / {charCount.max}
            </span>
          )}
        </div>
        <textarea
          id={textareaId}
          ref={ref}
          aria-invalid={!!error}
          aria-describedby={
            error
              ? `${textareaId}-error`
              : hint
                ? `${textareaId}-hint`
                : undefined
          }
          className={cn(
            "flex min-h-[90px] w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-content-primary shadow-sm placeholder:text-content-muted/60 focus-ring disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-rose-500 focus-visible:ring-rose-500",
            className,
          )}
          {...props}
        />
        {hint && !error && (
          <p id={`${textareaId}-hint`} className="text-xs text-content-muted">
            {hint}
          </p>
        )}
        {error && (
          <p
            id={`${textareaId}-error`}
            role="alert"
            className="text-xs font-medium text-rose-600 dark:text-rose-400"
          >
            {error}
          </p>
        )}
      </div>
    );
  },
);

Textarea.displayName = "Textarea";
