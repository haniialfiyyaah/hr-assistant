"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  authenticateDemo,
  DEMO_ACCOUNTS,
  DEMO_PASSWORD,
} from "@/lib/demo-accounts";

export default function LoginPage() {
  const { signIn, ready, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!ready || user) {
    return (
      <div className="chat-surface flex min-h-screen items-center justify-center text-sm text-stone-500">
        Loading…
      </div>
    );
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const session = authenticateDemo(email, password);
    if (!session) {
      setError("Invalid email or password. Use a demo account listed below.");
      setPending(false);
      return;
    }
    signIn(session);
    router.replace("/");
  }

  return (
    <div className="chat-surface flex min-h-svh items-center justify-center px-4 py-8 sm:py-10">
      <div className="flex w-full max-w-md flex-col gap-4 sm:gap-5">
        <div className="flex flex-col items-center gap-3 text-center">
          <BrandMark size="lg" className="rounded-2xl" />
          <div>
            <p className="text-xs font-medium tracking-[0.14em] text-teal-800/80 uppercase">
              HR Assistant
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-stone-900 sm:text-2xl">
              Policy and Leave Assistant
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-stone-500">
              Demo sign-in. Identity is still the bearer token on the API.
            </p>
          </div>
        </div>

        <div className="rounded-[1.35rem] border border-stone-200/90 bg-white/90 p-5 shadow-[0_24px_60px_-40px_oklch(0.35_0.04_220)] sm:rounded-[1.5rem] sm:p-6">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-stone-900">Sign in</h2>
            <p className="mt-1 text-sm text-stone-500">
              Password for all demo accounts:{" "}
              <code className="rounded bg-stone-100 px-1.5 py-0.5 text-xs text-stone-700">
                {DEMO_PASSWORD}
              </code>
            </p>
          </div>
          <form onSubmit={onSubmit}>
            <FieldGroup>
              <Field data-invalid={error ? true : undefined}>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  className="rounded-xl border-stone-200 bg-white"
                  required
                />
              </Field>
              <Field data-invalid={error ? true : undefined}>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  className="rounded-xl border-stone-200 bg-white"
                  required
                />
                {error ? (
                  <FieldDescription className="text-destructive">
                    {error}
                  </FieldDescription>
                ) : null}
              </Field>
              <Button
                type="submit"
                disabled={pending}
                className="mt-1 w-full rounded-full bg-teal-800 text-white hover:bg-teal-700 active:scale-[0.98]"
              >
                {pending ? "Signing in…" : "Sign in"}
              </Button>
            </FieldGroup>
          </form>
        </div>

        <div className="rounded-[1.35rem] border border-stone-200/80 bg-white/75 p-4">
          <p className="text-xs font-medium tracking-wide text-stone-500 uppercase">
            Demo accounts
          </p>
          <ul className="mt-3 flex flex-col gap-2">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left transition-colors hover:bg-stone-100 active:scale-[0.99]"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                    setError(null);
                  }}
                >
                  <span>
                    <span className="block text-sm font-medium text-stone-800">
                      {account.displayName}
                    </span>
                    <span className="block text-xs text-stone-500">
                      {account.email}
                    </span>
                  </span>
                  <span className="text-xs text-teal-800">Use</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
