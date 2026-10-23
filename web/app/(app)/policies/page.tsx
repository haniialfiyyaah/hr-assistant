import Link from "next/link";
import { ArrowUpRight, FileText } from "lucide-react";

import { PageFrame, SurfaceCard } from "@/components/page-frame";
import { listPolicies } from "@/lib/data";

export default async function PoliciesPage() {
  const policies = await listPolicies();

  return (
    <PageFrame
      eyebrow="Library"
      title="Policies"
      description="Policy library Markdown. View only."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {policies.map((policy) => (
          <Link key={policy.slug} href={`/policies/${policy.slug}`} className="group block">
            <SurfaceCard className="h-full p-4 transition-[transform,background-color] duration-200 ease-out group-hover:bg-white group-active:scale-[0.99]">
              <div className="flex items-start justify-between gap-3">
                <span className="inline-flex size-9 items-center justify-center rounded-xl bg-teal-800/10 text-teal-900">
                  <FileText className="size-4" />
                </span>
                <ArrowUpRight className="size-4 text-stone-300 transition-colors group-hover:text-teal-800" />
              </div>
              <p className="mt-3 text-base font-medium text-stone-900">
                {policy.title}
              </p>
              <p className="mt-1 font-mono text-xs text-stone-500">
                {policy.filename}
              </p>
            </SurfaceCard>
          </Link>
        ))}
      </div>
    </PageFrame>
  );
}
