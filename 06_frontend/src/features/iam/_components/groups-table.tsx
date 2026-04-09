"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UsersRound } from "lucide-react";
import { listGroups } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import type { GroupData } from "@/types/api";
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

export function GroupsTable() {
  const auth = useAuth();
  const router = useRouter();
  const [groups, setGroups] = useState<GroupData[] | null>(null);
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
    listGroups(auth.accessToken)
      .then((res) => {
        if (res.ok) setGroups(res.data.items);
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
        icon={<UsersRound />}
        title="Sign in required"
        description="Sign in to view groups."
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
        icon={<UsersRound />}
        title="Could not load groups"
        description={error}
      />
    );
  }

  if (!groups || groups.length === 0) {
    return (
      <EmptyState
        icon={<UsersRound />}
        title="No groups yet"
        description="Create your first group to organise users."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Slug</TableHead>
          <TableHead>Members</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {groups.map((g) => (
          <TableRow key={g.id}>
            <TableCell className="font-medium">{g.name ?? "—"}</TableCell>
            <TableCell className="font-mono text-[11px] text-foreground-muted">
              {g.slug ?? "—"}
            </TableCell>
            <TableCell>{g.member_count}</TableCell>
            <TableCell>
              {g.is_system ? (
                <Badge variant="outline">system</Badge>
              ) : (
                <Badge variant="outline">custom</Badge>
              )}
            </TableCell>
            <TableCell>
              {g.is_active ? (
                <Badge variant="success">active</Badge>
              ) : (
                <Badge variant="default">inactive</Badge>
              )}
            </TableCell>
            <TableCell className="font-mono text-[11px] text-foreground-muted">
              {new Date(g.created_at).toLocaleDateString()}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
