"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { PageFrame, SurfaceCard } from "@/components/page-frame";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiRequest } from "@/lib/api";

interface DirectoryEmployee {
  employee_id: string;
  display_name: string;
  role: string;
  balances: Record<string, number>;
}

export function PeopleDirectory() {
  const { user } = useAuth();
  const router = useRouter();
  const [employees, setEmployees] = useState<DirectoryEmployee[] | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    if (user.role !== "monitoring_admin") {
      router.replace("/");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const rows = await apiRequest<DirectoryEmployee[]>(
          "GET",
          "/api/directory",
          user.demoToken,
        );
        if (!cancelled) {
          setEmployees(rows);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error(
            error instanceof Error
              ? error.message
              : "Could not load the people directory.",
          );
          router.replace("/");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, router]);

  if (!user) {
    return null;
  }

  if (user.role !== "monitoring_admin" || employees === null) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-stone-500">
        {user.role !== "monitoring_admin" ? "Redirecting…" : "Loading…"}
      </div>
    );
  }

  return (
    <PageFrame
      eyebrow="Directory"
      title="People"
      description="Synthetic directory for monitoring admins. Tokens are hidden. View only."
    >
      <SurfaceCard className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="px-4">Name</TableHead>
              <TableHead>Employee ID</TableHead>
              <TableHead>Role</TableHead>
              <TableHead className="px-4">Balances</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {employees.map((employee) => (
              <TableRow key={employee.employee_id}>
                <TableCell className="px-4 font-medium text-stone-900">
                  {employee.display_name}
                </TableCell>
                <TableCell className="font-mono text-xs text-stone-600">
                  {employee.employee_id}
                </TableCell>
                <TableCell className="capitalize text-stone-700">
                  {employee.role.replaceAll("_", " ")}
                </TableCell>
                <TableCell className="px-4 text-sm text-stone-500">
                  {Object.keys(employee.balances).length
                    ? Object.entries(employee.balances)
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(" · ")
                    : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </SurfaceCard>
    </PageFrame>
  );
}
