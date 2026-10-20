import { PageFrame, SurfaceCard } from "@/components/page-frame";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listEmployees } from "@/lib/data";

export default async function PeoplePage() {
  const employees = await listEmployees();

  return (
    <PageFrame
      eyebrow="Directory"
      title="People"
      description="Synthetic directory from employees.json. Tokens are hidden. View only."
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
