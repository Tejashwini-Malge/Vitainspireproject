import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "./cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-sm border border-line bg-[#FFFDF7] px-3 py-2 text-ink placeholder:text-muted/70",
          "transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--focus)] focus:ring-offset-1",
          "disabled:cursor-not-allowed disabled:opacity-60",
          className,
        )}
        {...props}
      />
    );
  },
);

export default Textarea;
