import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Join class names, resolving Tailwind conflicts (last one wins). */
export function cn(...parts: ClassValue[]): string {
  return twMerge(clsx(parts));
}
