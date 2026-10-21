import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  return (
    <nav
      aria-label="Breadcrumb navigation"
      className={cn("flex items-center text-xs text-content-muted", className)}
    >
      <ol className="flex items-center space-x-1.5 flex-wrap">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;

          return (
            <li key={index} className="flex items-center">
              {index > 0 && (
                <ChevronRight
                  className="h-3.5 w-3.5 mx-1 text-content-disabled flex-shrink-0"
                  aria-hidden="true"
                />
              )}
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  className="hover:text-content-primary transition-colors focus-ring rounded px-1 py-0.5"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    "px-1 py-0.5",
                    isLast ? "font-semibold text-content-primary" : "",
                  )}
                  aria-current={isLast ? "page" : undefined}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
