import { Building2 } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

export default function IamOrganizationsPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Organizations"]}
        title="Organizations"
        description="Top-level tenants. Each org owns workspaces, users, and resources."
      />
      <PageBody>
        <Card>
          <EmptyState
            icon={<Building2 />}
            title="Orgs endpoint not wired yet"
            description="Once GET /v1/orgs lands, this page will render the tenant list with active scope switching."
          />
        </Card>
      </PageBody>
    </>
  );
}
