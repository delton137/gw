"use client";

import { useEffect } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

export default function AuthRedirect() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const router = useRouter();

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn || !user?.id) {
      router.replace("/sign-in");
      return;
    }

    const redirect = async () => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ total: number }>(
          `/api/v1/results/traits/${user.id}`,
          {},
          token
        );
        router.replace(data.total > 0 ? "/dashboard" : "/upload");
      } catch {
        router.replace("/upload");
      }
    };

    redirect();
  }, [isLoaded, isSignedIn, user, getToken, router]);

  return (
    <div className="flex items-center justify-center py-24 text-sm text-muted">
      Loading…
    </div>
  );
}
