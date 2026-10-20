import Link from "next/link";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { listPolicies } from "@/lib/data";

export default async function PoliciesPage() {
  const policies = await listPolicies();

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Policies</h1>
        <p className="text-sm text-muted-foreground">
          Policy library from data/policies. View only.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {policies.map((policy) => (
          <Link key={policy.slug} href={`/policies/${policy.slug}`}>
            <Card className="h-full transition-colors hover:bg-muted/40">
              <CardHeader>
                <CardTitle className="text-base">{policy.title}</CardTitle>
                <CardDescription>{policy.filename}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
