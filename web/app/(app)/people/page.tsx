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
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">People</h1>
        <p className="text-sm text-muted-foreground">
          Synthetic directory from employees.json. Tokens are hidden. View only.
        </p>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Employee ID</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Balances</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {employees.map((employee) => (
            <TableRow key={employee.employee_id}>
              <TableCell>{employee.display_name}</TableCell>
              <TableCell className="font-mono text-xs">
                {employee.employee_id}
              </TableCell>
              <TableCell>{employee.role}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
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
    </div>
  );
}
