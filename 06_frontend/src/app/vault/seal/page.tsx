import { Lock } from "lucide-react";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";

export default function VaultSealPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["Vault", "Seal"]}
        title="Seal Vault"
        description="Manually seal the vault to revoke in-memory keys."
      />
      <PageBody>
        <Card>
          <EmptyState
            icon={<Lock />}
            title="Seal operation not wired yet"
            description="The seal endpoint will appear here. Ensure you have operator privileges before sealing — all decryption keys will be evicted until the vault is re-unsealed."
            action={
              <Button variant="danger" size="sm" disabled>
                <Lock /> Seal vault
              </Button>
            }
          />
        </Card>
      </PageBody>
    </>
  );
}
