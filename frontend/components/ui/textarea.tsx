import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "./cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-md border border-gray-300 bg-white px-3 py-2",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60",
          className,
        )}
        {...props}
      />
    );
  },
);

export default Textarea;
