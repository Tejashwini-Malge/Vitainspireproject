import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "./cn";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Lifts on hover -- use for clickable/linked cards, not static containers. */
  interactive?: boolean;
}

/** Surface container, ledger-stock paper rather than flat white. */
export const Card = forwardRef<HTMLDivElement, CardProps>(
  function Card({ className, interactive, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-sm border border-line bg-[#FFFDF7] shadow-[0_1px_2px_rgba(42,43,38,0.05)]",
          interactive &&
            "transition-all duration-150 ease-out hover:-translate-y-0.5 hover:border-navy/40 hover:shadow-[0_8px_24px_rgba(29,43,79,0.1)]",
          className,
        )}
        {...props}
      />
    );
  },
);

export default Card;
