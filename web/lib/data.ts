import { existsSync, promises as fs } from "fs";
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

export interface PolicyDocument {
  slug: string;
  title: string;
  content: string;
  /** Markdown body with YAML frontmatter removed (for rendering). */
  body: string;
  documentId?: string;
  version?: string;
  effectiveDate?: string;
}

/**
 * DATA_DIR (Docker) wins; otherwise prefer in-app `web/data` for Vercel /
 * standalone, then monorepo sibling `../data`.
 */
function dataRoot(): string {
  if (process.env.DATA_DIR) {
    return process.env.DATA_DIR;
  }
  const inApp = path.join(process.cwd(), "data");
  if (existsSync(inApp)) {
    return inApp;
  }
  return path.join(process.cwd(), "..", "data");
}

function parseFrontmatter(content: string): {
  meta: Record<string, string>;
  body: string;
} {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) {
    return { meta: {}, body: content };
  }
  const meta: Record<string, string> = {};
  for (const line of match[1].split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key) meta[key] = value;
  }
  return { meta, body: match[2].replace(/^\r?\n/, "") };
}

function titleFromContent(
  content: string,
  meta: Record<string, string>,
  fallback: string,
): string {
  if (meta.title) return meta.title;
  const match = content.match(/^#\s+(.+)$/m);
  return match?.[1]?.trim() || fallback;
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

export async function listPolicies(): Promise<PolicySummary[]> {
  const dir = path.join(dataRoot(), "policies");
  const files = (await fs.readdir(dir))
    .filter((name) => name.endsWith(".md"))
    .sort();
  const policies: PolicySummary[] = [];
  for (const filename of files) {
    const content = await fs.readFile(path.join(dir, filename), "utf8");
    const slug = filename.replace(/\.md$/, "");
    const { meta } = parseFrontmatter(content);
    policies.push({
      slug,
      filename,
      title: titleFromContent(content, meta, slug),
    });
  }
  return policies;
}

export async function readPolicy(slug: string): Promise<PolicyDocument | null> {
  if (!/^[a-z0-9-]+$/i.test(slug)) {
    return null;
  }
  const filePath = path.join(dataRoot(), "policies", `${slug}.md`);
  try {
    const content = await fs.readFile(filePath, "utf8");
    const { meta, body } = parseFrontmatter(content);
    return {
      slug,
      title: titleFromContent(content, meta, slug),
      content,
      body,
      documentId: meta.document_id,
      version: meta.version,
      effectiveDate: meta.effective_date,
    };
  } catch {
    return null;
  }
}
