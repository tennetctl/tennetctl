"use client";

import { useEffect, useState } from "react";
import { UserMinus, UserPlus, X } from "lucide-react";
import { listGroupMembers, addGroupMember, removeGroupMember } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import type { GroupData, GroupMemberData } from "@/types/api";

interface GroupMembersPanelProps {
  group: GroupData;
  accessToken: string;
  onClose: () => void;
}

export function GroupMembersPanel({ group, accessToken, onClose }: GroupMembersPanelProps) {
  const [members, setMembers] = useState<GroupMemberData[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addUserId, setAddUserId] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const backdropRef = { current: null as HTMLDivElement | null };

  useEffect(() => {
    setLoading(true);
    listGroupMembers(group.id, accessToken)
      .then((res) => {
        if (res.ok) setMembers(res.data.items);
        else setError(res.error.message);
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }, [group.id, accessToken]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addUserId.trim()) return;
    setAddError(null);
    setAdding(true);
    try {
      const res = await addGroupMember(group.id, addUserId.trim(), accessToken);
      if (!res.ok) {
        setAddError(res.error.message);
        return;
      }
      setMembers((prev) => (prev ? [res.data, ...prev] : [res.data]));
      setAddUserId("");
    } catch {
      setAddError("Network error.");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(userId: string) {
    setRemovingId(userId);
    try {
      await removeGroupMember(group.id, userId, accessToken);
      setMembers((prev) => prev?.filter((m) => m.user_id !== userId) ?? null);
    } catch {
      // silent – user still sees the row
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => { if (e.target === (backdropRef.current as unknown)) onClose(); }}
      ref={(el) => { backdropRef.current = el; }}
    >
      <div className="relative flex h-[80vh] w-full max-w-2xl flex-col rounded-md border border-border bg-surface shadow-xl">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
          <div className="space-y-0.5">
            <h2 className="text-sm font-semibold">{group.name ?? group.slug}</h2>
            <p className="text-xs text-foreground-muted">Group members</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
            aria-label="Close"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Add member */}
        <div className="shrink-0 border-b border-border px-5 py-3">
          <form onSubmit={handleAdd} className="flex items-center gap-2">
            <Input
              value={addUserId}
              onChange={(e) => setAddUserId(e.target.value)}
              placeholder="User ID to add…"
              className="font-mono text-xs"
            />
            <Button type="submit" size="sm" disabled={adding || !addUserId.trim()}>
              <UserPlus className="size-3.5" />
              {adding ? "Adding…" : "Add"}
            </Button>
          </form>
          {addError && (
            <p className="mt-1.5 text-xs text-[color:var(--danger)]">{addError}</p>
          )}
        </div>

        {/* Member list */}
        <div className="min-h-0 flex-1 overflow-auto">
          {loading && (
            <div className="space-y-2 p-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {!loading && error && (
            <EmptyState
              icon={<UserMinus />}
              title="Could not load members"
              description={error}
            />
          )}

          {!loading && !error && (!members || members.length === 0) && (
            <EmptyState
              icon={<UserPlus />}
              title="No members"
              description="Add a user ID above to add the first member."
            />
          )}

          {!loading && !error && members && members.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Added</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell className="font-medium">{m.username ?? "—"}</TableCell>
                    <TableCell className="text-foreground-muted">{m.email ?? "—"}</TableCell>
                    <TableCell>
                      {m.is_active ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="default">inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-foreground-muted">
                      {new Date(m.added_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={removingId === m.user_id}
                        onClick={() => handleRemove(m.user_id)}
                        aria-label="Remove member"
                      >
                        <UserMinus className="size-3.5 text-foreground-muted" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </div>
  );
}
