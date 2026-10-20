"use client";

import {
  createContext,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";

import type { SessionUser } from "@/lib/demo-accounts";
import { clearSession, readSession, writeSession } from "@/lib/session";

interface AuthContextValue {
  user: SessionUser | null;
  ready: boolean;
  signIn: (user: SessionUser) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function AuthRedirect({
  user,
  ready,
}: {
  user: SessionUser | null;
  ready: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!ready) {
      return;
    }
    const onLogin = pathname === "/login";
    if (!user && !onLogin) {
      router.replace("/login");
    }
    if (user && onLogin) {
      router.replace("/");
    }
  }, [ready, user, pathname, router]);

  return null;
}

function AuthProviderInner({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setUser(readSession());
    setReady(true);
  }, []);

  const signIn = useCallback((next: SessionUser) => {
    writeSession(next);
    setUser(next);
  }, []);

  const signOut = useCallback(() => {
    clearSession();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, ready, signIn, signOut }),
    [user, ready, signIn, signOut],
  );

  return (
    <AuthContext.Provider value={value}>
      <Suspense fallback={null}>
        <AuthRedirect user={user} ready={ready} />
      </Suspense>
      {children}
    </AuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={null}>
      <AuthProviderInner>{children}</AuthProviderInner>
    </Suspense>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
