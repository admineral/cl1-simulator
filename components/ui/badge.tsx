import { HTMLAttributes } from "react";
import { cn } from "@/components/ui/utils";

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  variant?: "default" | "outline" | "success";
}) {
  return <span className={cn("ui-badge", `ui-badge--${variant}`, className)} {...props} />;
}
