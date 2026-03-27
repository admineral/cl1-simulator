import { TextareaHTMLAttributes } from "react";
import { cn } from "@/components/ui/utils";

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("ui-textarea", className)} {...props} />;
}
