"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { UsersRound, Plus, Trash2, Users } from "lucide-react";
import { listGroups, deleteGroup } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageBody } from "@/components/shell/page-header";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { CreateGroupModal } from "@/features/iam/_components/create-group-modal";
import { GroupMembersPanel } from "@/features/iam/_components/group-members-panel";
import type { GroupData } from "@/types/api";

export default function IamGroupsPage() {
  const auth = useAuth();
  const router = useRouter();

  const [groups, setGroups] = useState<GroupData[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<GroupData | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status === "loading") return;
    if (auth.status === "unauthenticated") {
      setError("unauthenticated");
      setLoading(false);
      return;
    }
    fetchGroups();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.status]);

  function fetchGroups() {
    if (auth.status !== "authenticated") return;
    setLoading(true);
    listGroups(auth.accessToken)
      .then((res) => {
        if (res.ok) {
          setGroups(res.data.items);
          setTotal(res.data.total);
        } else {
          setError(res.error.message);
        }
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }

  async function handleDelete(group: GroupData) {
    if (auth.status !== "authenticated") return;
    if (!confirm(`Delete group "${group.name ?? group.slug}"? This cannot be undone.`)) return;
    setDeletingId(group.id);
    try {
      await deleteGroup(group.id, auth.accessToken);
      setGroups((prev) => prev?.filter((g) => g.id !== group.id) ?? null);
      setTotal((t) => t - 1);
    } catch {
      // silent
    } finally {
      setDeletingId(null);
    }
  }

  const isAuthenticated = auth.status === "authenticated";

  return (
    <>
      <PageHeader
        breadcrumb={["IAM", "Groups"]}
        title="Groups"
        description="Organise users into named groups scoped to an organisation."
        actions={
          isAuthenticated ? (
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="size-3.5" />
              New Group
            </Button>
          ) : undefined
        }
      />

      <PageBody>
        <Card>
          <CardHeader>
            <CardTitle>
              All Groups
              {total > 0 && (
                <span className="ml-2 font-normal text-foreground-muted">({total})</span>
              )}
            </CardTitle>
          </CardHeader>

          {(loading || auth.status === "loading") && (
            <div className="space-y-2 p-4">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {!loading && error === "unauthenticated" && (
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
          )}

          {!loading && error && error !== "unauthenticated" && (
            <EmptyState
              icon={<UsersRound />}
              title="Could not load groups"
              description={error}
              action={
                <Button size="sm" variant="outline" onClick={fetchGroups}>
                  Retry
                </Button>
              }
            />
          )}

          {!loading && !error && (!groups || groups.length === 0) && (
            <EmptyState
              icon={<UsersRound />}
              title="No groups yet"
              description="Create your first group to organise users."
              action={
                isAuthenticated ? (
                  <Button size="sm" onClick={() => setShowCreate(true)}>
                    <Plus className="size-3.5" />
                    New Group
                  </Button>
                ) : undefined
              }
            />
          )}

          {!loading && !error && groups && groups.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Org</TableHead>
                  <TableHead>Members</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {groups.map((g) => (
                  <TableRow key={g.id}>
                    <TableCell className="font-medium">{g.name ?? "—"}</TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">
                      {g.slug ?? "—"}
                    </TableCell>
                    <TableCell className="max-w-[120px] truncate font-mono text-[11px] text-foreground-muted">
                      {g.org_id}
                    </TableCell>
                    <TableCell>{g.member_count}</TableCell>
                    <TableCell>
                      {g.is_system ? (
                        <Badge variant="info">system</Badge>
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
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Manage members"
                          onClick={() => setSelectedGroup(g)}
                          disabled={!isAuthenticated}
                        >
                          <Users className="size-3.5 text-foreground-muted" />
                        </Button>
                        {!g.is_system && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Delete group"
                            disabled={deletingId === g.id || !isAuthenticated}
                            onClick={() => handleDelete(g)}
                          >
                            <Trash2 className="size-3.5 text-foreground-muted" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>
      </PageBody>

      {showCreate && auth.status === "authenticated" && (
        <CreateGroupModal
          accessToken={auth.accessToken}
          onCreated={(group) => {
            setGroups((prev) => (prev ? [group, ...prev] : [group]));
            setTotal((t) => t + 1);
            setShowCreate(false);
          }}
          onClose={() => setShowCreate(false)}
        />
      )}

      {selectedGroup && auth.status === "authenticated" && (
        <GroupMembersPanel
          group={selectedGroup}
          accessToken={auth.accessToken}
          onClose={() => setSelectedGroup(null)}
        />
      )}
    </>
  );
}
