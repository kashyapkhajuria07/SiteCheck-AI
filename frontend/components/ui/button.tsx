import { cn } from "@/lib/utils";

type Variant = "default" | "outline" | "ghost";

const variants: Record<Variant, string> = {
  default: "bg-brand-600 text-white hover:bg-brand-700",
  outline: "border border-slate-300 bg-white hover:bg-slate-50",
  ghost: "hover:bg-slate-100",
};

export function Button({
  className,
  variant = "default",
  disabled,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition disabled:opacity-50",
        variants[variant],
        className,
      )}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
