import Link from "next/link";
import { notFound } from "next/navigation";

import { PageFrame, SurfaceCard } from "@/components/page-frame";
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
    <PageFrame
      eyebrow="Policy"
      title={policy.title}
      description="View only"
      className="max-w-3xl"
      actions={
        <Link
          href="/policies"
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "rounded-full border-stone-200 bg-white",
          )}
        >
          Back
        </Link>
      }
    >
      <SurfaceCard className="overflow-hidden">
        <pre className="overflow-auto p-5 text-sm leading-relaxed whitespace-pre-wrap text-stone-700">
          {policy.content}
        </pre>
      </SurfaceCard>
    </PageFrame>
  );
}
