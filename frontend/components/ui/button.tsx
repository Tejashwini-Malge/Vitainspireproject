import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-teal text-paper shadow-sm hover:opacity-90 hover:shadow-md",
  secondary: "border-2 border-navy text-navy hover:bg-navy hover:text-paper",
  // Alias of secondary -- kept for call sites written against a shadcn-style "outline" name.
  outline: "border-2 border-navy text-navy hover:bg-navy hover:text-paper",
  ghost: "text-navy hover:bg-navy/5",
  danger: "border-2 border-status-rejected text-status-rejected hover:bg-status-rejected hover:text-paper",
};

const SIZE: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-6 py-3 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button({ className, variant = "primary", size = "md", type, ...props }, ref) {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-sm font-display font-medium",
          "transition-all duration-150 ease-out active:scale-[0.98]",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]",
          VARIANT[variant],
          SIZE[size],
          className,
        )}
        {...props}
      />
    );
  },
);

export default Button;
