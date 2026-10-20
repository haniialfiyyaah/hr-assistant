import { NextResponse } from "next/server";

import { DEMO_ACCOUNTS } from "@/lib/demo-accounts";
import { listEmployees } from "@/lib/data";

/**
 * Directory is admin-only: leave balances across employees must not be
 * readable by a normal employee session.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  const account = DEMO_ACCOUNTS.find((row) => row.demoToken === token);
  if (!account || account.role !== "monitoring_admin") {
    return NextResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  const employees = await listEmployees();
  return NextResponse.json(employees);
}
