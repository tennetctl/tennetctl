"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Users } from "lucide-react";
import { listUsers } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import type { UserData } from "@/types/api";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";

export function UsersTable() {
  const auth = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<UserData[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (auth.status === "loading") return;
    if (auth.status === "unauthenticated") {
      setError("unauthenticated");
      setLoading(false);
      return;
    }
    setLoading(true);
    listUsers(auth.accessToken)
      .then((res) => {
        if (res.ok) setUsers(res.data.items);
        else setError(res.error.message);
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }, [auth.status]);

  if (loading || auth.status === "loading") {
    return (
      <div className="space-y-2 p-4">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
    );
  }

  if (error === "unauthenticated") {
    return (
      <EmptyState
        icon={<Users />}
        title="Sign in required"
        description="Sign in to view users."
        action={
          <Button size="sm" onClick={() => router.push("/iam")}>
            Go to sign in
          </Button>
        }
      />
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={<Users />}
        title="Could not load users"
        description={error}
      />
    );
  }

  if (!users || users.length === 0) {
    return (
      <EmptyState
        icon={<Users />}
        title="No users yet"
        description="Create your first user to get started."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Username</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Auth</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {users.map((u) => (
          <TableRow key={u.id}>
            <TableCell className="font-medium">{u.username ?? "—"}</TableCell>
            <TableCell className="text-foreground-muted">
              {u.email ?? "—"}
            </TableCell>
            <TableCell>
              <Badge variant="outline">{u.account_type}</Badge>
            </TableCell>
            <TableCell>
              <Badge variant="outline">{u.auth_type}</Badge>
            </TableCell>
            <TableCell>
              {u.is_active ? (
                <Badge variant="success">active</Badge>
              ) : (
                <Badge variant="default">inactive</Badge>
              )}
            </TableCell>
            <TableCell className="font-mono text-[11px] text-foreground-muted">
              {new Date(u.created_at).toLocaleDateString()}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
