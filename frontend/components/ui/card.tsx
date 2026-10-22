import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "./cn";

/** Surface container. Callers supply their own padding and colour via className. */
export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function Card({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn("rounded-lg border border-gray-200 bg-white shadow-sm", className)}
        {...props}
      />
    );
  },
);

export default Card;
