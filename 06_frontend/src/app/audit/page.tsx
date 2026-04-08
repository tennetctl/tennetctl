import { PageHeader, PageBody } from "@/components/shell/page-header";
import { EventsTable } from "@/features/audit/_components/events-table";

export default function AuditPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["Audit", "Events"]}
        title="Audit Events"
        description="Append-only event log across all modules. Filter by category, action, outcome, user, or session."
      />
      <PageBody>
        <EventsTable />
      </PageBody>
    </>
  );
}
