import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accepted for API compatibility; styling is driven by className. */
  variant?: string;
  size?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button({ className, variant: _variant, size: _size, type, ...props }, ref) {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={cn(
          "inline-flex items-center justify-center rounded-md px-4 py-2 font-medium",
          "transition-colors disabled:cursor-not-allowed disabled:opacity-60",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
          className,
        )}
        {...props}
      />
    );
  },
);

export default Button;
