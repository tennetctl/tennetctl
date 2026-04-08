import { Unlock } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";

export default function VaultUnsealPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["Vault", "Unseal"]}
        title="Unseal Vault"
        description="Provide unseal material to bring the vault online."
      />
      <PageBody>
        <Card>
          <EmptyState
            icon={<Unlock />}
            title="Unseal flow not wired yet"
            description="Depending on unseal_mode this page will either prompt for an unseal key (manual) or trigger an Azure KMS unwrap (kms_azure)."
            action={
              <Button size="sm" disabled>
                <Unlock /> Begin unseal
              </Button>
            }
          />
        </Card>
      </PageBody>
    </>
  );
}
