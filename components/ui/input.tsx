import { InputHTMLAttributes } from "react";
import { cn } from "@/components/ui/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("ui-input", className)} {...props} />;
}
