"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";

import { LoaderIcon } from "@/components/icons";

function VerifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [error, setError] = useState<string | null>(null);
  const attempted = useRef(false);

  useEffect(() => {
    if (!token) {
      setError("Missing verification token.");
      return;
    }

    if (attempted.current) return;
    attempted.current = true;

    signIn("magic-link", { token, redirect: false }).then((result) => {
      if (result?.ok && !result.error) {
        router.replace("/");
      } else {
        setError("Invalid or expired link. Please request a new one.");
      }
    });
  }, [token, router]);

  if (error) {
    return (
      <div className="flex w-full max-w-md flex-col gap-6 overflow-hidden rounded-2xl px-4 text-center sm:px-16">
        <h3 className="font-semibold text-xl dark:text-zinc-50">
          Verification failed
        </h3>
        <p className="text-gray-500 text-sm dark:text-zinc-400">{error}</p>
        <a
          href="/login"
          className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          Back to sign in
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <span className="animate-spin">
        <LoaderIcon />
      </span>
      <p className="text-gray-500 text-sm dark:text-zinc-400">
        Signing you in...
      </p>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <div className="flex h-dvh w-screen items-center justify-center bg-background">
      <Suspense
        fallback={
          <div className="flex flex-col items-center gap-4">
            <span className="animate-spin">
              <LoaderIcon />
            </span>
            <p className="text-gray-500 text-sm dark:text-zinc-400">
              Loading...
            </p>
          </div>
        }
      >
        <VerifyContent />
      </Suspense>
    </div>
  );
}
