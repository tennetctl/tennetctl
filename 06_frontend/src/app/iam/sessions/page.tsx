import { Activity } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

export default function IamSessionsPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Sessions"]}
        title="Active Sessions"
        description="Live sessions issued by /v1/sessions. Revoke here."
      />
      <PageBody>
        <Card>
          <EmptyState
            icon={<Activity />}
            title="Sessions list endpoint pending"
            description="Will render once GET /v1/sessions (list) is available."
          />
        </Card>
      </PageBody>
    </>
  );
}
