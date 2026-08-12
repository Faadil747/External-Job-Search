import Link from "next/link";
import { Sparkles } from "lucide-react";

export function Logo({ className }: { className?: string }) {
  return (
    <Link href="/" className={`flex items-center gap-2 font-semibold text-foreground ${className || ""}`}>
      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground">
        <Sparkles className="h-4 w-4" />
      </span>
      <span className="text-base tracking-tight">
        JobMatch <span className="text-primary">AI</span>
      </span>
    </Link>
  );
}
