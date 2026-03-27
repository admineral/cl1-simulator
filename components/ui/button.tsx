import { ButtonHTMLAttributes } from "react";
import { cn } from "@/components/ui/utils";

type Variant = "default" | "secondary" | "outline" | "destructive";
type Size = "default" | "sm";

export function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
}) {
  return (
    <button
      className={cn(
        "ui-button",
        `ui-button--${variant}`,
        size === "sm" && "ui-button--sm",
        className
      )}
      {...props}
    />
  );
}
