import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "./cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, type, ...props }, ref) {
    return (
      <input
        ref={ref}
        type={type ?? "text"}
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

export default Input;
