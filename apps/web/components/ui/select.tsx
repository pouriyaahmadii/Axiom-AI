import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: Array<{ value: string; label: string; disabled?: boolean }>;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, hint, options, id, ...props }, ref) => {
    const generatedId = React.useId();
    const selectId = id || generatedId;

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label
            htmlFor={selectId}
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
        <div className="relative">
          <select
            id={selectId}
            ref={ref}
            aria-invalid={!!error}
            aria-describedby={
              error
                ? `${selectId}-error`
                : hint
                  ? `${selectId}-hint`
                  : undefined
            }
            className={cn(
              "flex h-9 w-full appearance-none rounded-md border border-border bg-surface px-3 py-1.5 pr-8 text-sm text-content-primary shadow-sm focus-ring disabled:cursor-not-allowed disabled:opacity-50",
              error && "border-rose-500 focus-visible:ring-rose-500",
              className,
            )}
            {...props}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-content-muted"
            aria-hidden="true"
          />
        </div>
        {hint && !error && (
          <p id={`${selectId}-hint`} className="text-xs text-content-muted">
            {hint}
          </p>
        )}
        {error && (
          <p
            id={`${selectId}-error`}
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

Select.displayName = "Select";
