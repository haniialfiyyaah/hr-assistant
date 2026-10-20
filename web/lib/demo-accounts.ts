/** Demo sign-in only. Maps to existing FastAPI bearer tokens. */

export interface DemoAccount {
  email: string;
  password: string;
  employeeId: string;
  displayName: string;
  role: "employee" | "monitoring_admin";
  demoToken: string;
  scenario: string;
  balances: { annual?: number; sick?: number; parental?: number };
}

export const DEMO_PASSWORD = "demo";

export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    email: "alya@demo.local",
    password: DEMO_PASSWORD,
    employeeId: "EMP-001",
    displayName: "Alya Pratama",
    role: "employee",
    demoToken: "token-alya",
    scenario: "Ask about policies, check your leave balance, and prepare a leave request.",
    balances: { annual: 8, sick: 10, parental: 60 },
  },
  {
    email: "bima@demo.local",
    password: DEMO_PASSWORD,
    employeeId: "EMP-002",
    displayName: "Bima Santoso",
    role: "employee",
    demoToken: "token-bima",
    scenario: "Compare balances and verify that cross-employee access is blocked.",
    balances: { annual: 3, sick: 10, parental: 60 },
  },
  {
    email: "admin@demo.local",
    password: DEMO_PASSWORD,
    employeeId: "ADM-001",
    displayName: "Monitoring Admin",
    role: "monitoring_admin",
    demoToken: "token-admin",
    scenario: "Inspect aggregate metrics, alerts, and redacted operational traces.",
    balances: {},
  },
];

export interface SessionUser {
  email: string;
  employeeId: string;
  displayName: string;
  role: "employee" | "monitoring_admin";
  demoToken: string;
  scenario: string;
  balances: { annual?: number; sick?: number; parental?: number };
}

export function authenticateDemo(
  email: string,
  password: string,
): SessionUser | null {
  const account = DEMO_ACCOUNTS.find(
    (row) => row.email.toLowerCase() === email.trim().toLowerCase(),
  );
  if (!account || account.password !== password) {
    return null;
  }
  return {
    email: account.email,
    employeeId: account.employeeId,
    displayName: account.displayName,
    role: account.role,
    demoToken: account.demoToken,
    scenario: account.scenario,
    balances: account.balances,
  };
}
