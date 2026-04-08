import { Plus } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UsersTable } from "@/features/iam/_components/users-table";

export default function IamUsersPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Users"]}
        title="Users"
        description="All user accounts visible to the current scope."
        actions={
          <Button size="sm" disabled>
            <Plus /> New user
          </Button>
        }
      />
      <PageBody>
        <Card className="overflow-hidden p-0">
          <UsersTable />
        </Card>
      </PageBody>
    </>
  );
}
