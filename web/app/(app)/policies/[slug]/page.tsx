import Link from "next/link";
import { notFound } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";
import { listPolicies, readPolicy } from "@/lib/data";
import { cn } from "@/lib/utils";

export async function generateStaticParams() {
  const policies = await listPolicies();
  return policies.map((policy) => ({ slug: policy.slug }));
}

export default async function PolicyDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const policy = await readPolicy(slug);
  if (!policy) {
    notFound();
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {policy.title}
          </h1>
          <p className="text-sm text-muted-foreground">View only</p>
        </div>
        <Link
          href="/policies"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          Back
        </Link>
      </div>
      <pre className="overflow-auto rounded-lg border border-border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
        {policy.content}
      </pre>
    </div>
  );
}
