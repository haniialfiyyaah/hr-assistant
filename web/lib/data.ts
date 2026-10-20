import { promises as fs } from "fs";
import path from "path";

export interface EmployeeRecord {
  employee_id: string;
  display_name: string;
  role: string;
  balances: Record<string, number>;
}

export interface PolicySummary {
  slug: string;
  title: string;
  filename: string;
}

function dataRoot(): string {
  return process.env.DATA_DIR || path.join(process.cwd(), "..", "data");
}

export async function listEmployees(): Promise<EmployeeRecord[]> {
  const filePath = path.join(dataRoot(), "employees.json");
  const rows = JSON.parse(await fs.readFile(filePath, "utf8")) as Array<{
    employee_id: string;
    display_name: string;
    role: string;
    token?: string;
    balances?: Record<string, number>;
  }>;
  return rows.map((row) => ({
    employee_id: row.employee_id,
    display_name: row.display_name,
    role: row.role,
    balances: row.balances ?? {},
  }));
}

function titleFromMarkdown(content: string, fallback: string): string {
  const match = content.match(/^#\s+(.+)$/m);
  return match?.[1]?.trim() || fallback;
}

export async function listPolicies(): Promise<PolicySummary[]> {
  const dir = path.join(dataRoot(), "policies");
  const files = (await fs.readdir(dir))
    .filter((name) => name.endsWith(".md"))
    .sort();
  const policies: PolicySummary[] = [];
  for (const filename of files) {
    const content = await fs.readFile(path.join(dir, filename), "utf8");
    const slug = filename.replace(/\.md$/, "");
    policies.push({
      slug,
      filename,
      title: titleFromMarkdown(content, slug),
    });
  }
  return policies;
}

export async function readPolicy(
  slug: string,
): Promise<{ title: string; content: string } | null> {
  if (!/^[a-z0-9-]+$/i.test(slug)) {
    return null;
  }
  const filePath = path.join(dataRoot(), "policies", `${slug}.md`);
  try {
    const content = await fs.readFile(filePath, "utf8");
    return { title: titleFromMarkdown(content, slug), content };
  } catch {
    return null;
  }
}
