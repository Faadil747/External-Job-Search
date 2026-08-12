"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";

import { useAuthStore } from "@/lib/auth-store";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Wraps authenticated pages. Redirects to /login (preserving a `next`
 * redirect target) once we know for certain there's no token in
 * localStorage. Renders a lightweight skeleton while hydration is pending
 * to avoid a flash of redirect on first paint.
 */
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const hydrated = useAuthStore((s) => s.hydrated);
  const hydrate = useAuthStore((s) => s.hydrate);
  const accessToken = useAuthStore((s) => s.accessToken);

  React.useEffect(() => {
    hydrate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (hydrated && !accessToken) {
      const next = encodeURIComponent(pathname || "/dashboard");
      router.replace(`/login?next=${next}`);
    }
  }, [hydrated, accessToken, router, pathname]);

  if (!hydrated || !accessToken) {
    return (
      <div className="container py-10">
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
