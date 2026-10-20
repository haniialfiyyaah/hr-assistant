"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
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
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-10">
      <div className="flex w-full max-w-md flex-col gap-4">
        <div className="flex flex-col gap-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">
            HR Policy and Leave Assistant
          </h1>
          <p className="text-sm text-muted-foreground">
            Demo sign-in. Identity is still the bearer token on the API.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>
              Use one of the demo accounts. Password for all:{" "}
              <code className="text-xs">{DEMO_PASSWORD}</code>
            </CardDescription>
          </CardHeader>
          <CardContent>
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
                    required
                  />
                  {error ? (
                    <FieldDescription className="text-destructive">
                      {error}
                    </FieldDescription>
                  ) : null}
                </Field>
                <Button type="submit" disabled={pending}>
                  {pending ? "Signing in…" : "Sign in"}
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>

        <Alert>
          <AlertTitle>Demo accounts</AlertTitle>
          <AlertDescription>
            <ul className="mt-2 flex flex-col gap-1 text-sm">
              {DEMO_ACCOUNTS.map((account) => (
                <li key={account.email}>
                  <button
                    type="button"
                    className="text-left underline-offset-2 hover:underline"
                    onClick={() => {
                      setEmail(account.email);
                      setPassword(DEMO_PASSWORD);
                      setError(null);
                    }}
                  >
                    {account.email}
                  </button>
                  {" — "}
                  {account.displayName}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      </div>
    </div>
  );
}
