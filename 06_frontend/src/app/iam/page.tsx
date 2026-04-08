import { PageHeader, PageBody } from "@/components/shell/page-header";
import { SignInForm } from "@/features/iam/_components/sign-in-form";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function IamOverviewPage() {
  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Overview"]}
        title="Identity & Access"
        description="Sign in, manage users, and inspect sessions."
      />
      <PageBody className="grid gap-6 lg:grid-cols-2">
        <SignInForm />
        <Card>
          <CardHeader>
            <CardTitle>About this module</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs text-foreground-muted">
            <p>
              IAM (feature 03) is the identity root. It manages users,
              organizations, workspaces, and sessions. Every other feature
              depends on a valid session issued here.
            </p>
            <p>
              Sign in with a bootstrapped operator account to exercise the
              other modules. Tokens are stored in localStorage and used by
              subsequent API calls.
            </p>
          </CardContent>
        </Card>
      </PageBody>
    </>
  );
}
