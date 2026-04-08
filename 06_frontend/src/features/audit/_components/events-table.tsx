"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, FileClock } from "lucide-react";
import { listAuditEvents } from "@/lib/api";
import { useAuth } from "@/components/providers/auth-provider";
import type { AuditEvent, AuditFilters } from "@/types/api";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Card } from "@/components/ui/card";

const EMPTY_FILTERS: AuditFilters = {};

export function EventsTable() {
  const auth = useAuth();
  const router = useRouter();
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [draft, setDraft] = useState<AuditFilters>(EMPTY_FILTERS);
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [total, setTotal] = useState(0);
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
    listAuditEvents(auth.accessToken, { limit: 50, offset: 0, ...filters })
      .then((res) => {
        if (res.ok) {
          setEvents(res.data.items);
          setTotal(res.data.total);
          setError(null);
        } else {
          setError(res.error.message);
        }
      })
      .catch(() => setError("Network error."))
      .finally(() => setLoading(false));
  }, [auth.status, filters]);

  function apply() { setFilters(draft); }
  function clear() { setDraft(EMPTY_FILTERS); setFilters(EMPTY_FILTERS); }

  if (error === "unauthenticated") {
    return (
      <Card className="p-6">
        <EmptyState
          icon={<FileClock />}
          title="Sign in required"
          description="Sign in to view audit events."
          action={
            <Button size="sm" onClick={() => router.push("/iam")}>
              Go to sign in
            </Button>
          }
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
          <FilterField
            label="Category"
            value={draft.category ?? ""}
            onChange={(v) => setDraft({ ...draft, category: v || undefined })}
            placeholder="iam, vault, audit…"
          />
          <FilterField
            label="Action"
            value={draft.action ?? ""}
            onChange={(v) => setDraft({ ...draft, action: v || undefined })}
            placeholder="user.login"
          />
          <FilterField
            label="Outcome"
            value={draft.outcome ?? ""}
            onChange={(v) => setDraft({ ...draft, outcome: v || undefined })}
            placeholder="success / failure"
          />
          <FilterField
            label="User ID"
            value={draft.user_id ?? ""}
            onChange={(v) => setDraft({ ...draft, user_id: v || undefined })}
            placeholder="uuid"
          />
          <FilterField
            label="Session ID"
            value={draft.session_id ?? ""}
            onChange={(v) => setDraft({ ...draft, session_id: v || undefined })}
            placeholder="uuid"
          />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <p className="text-[10px] text-foreground-subtle">
            {total > 0 ? (
              <>
                <span className="font-mono text-foreground">{total}</span> events match
              </>
            ) : (
              <>No filters set shows the latest 50 events</>
            )}
          </p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={clear}>
              <X /> Clear
            </Button>
            <Button size="sm" onClick={apply}>
              <Search /> Apply
            </Button>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        {loading || auth.status === "loading" ? (
          <div className="space-y-2 p-4">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <EmptyState
            icon={<FileClock />}
            title="Could not load events"
            description={error}
          />
        ) : !events || events.length === 0 ? (
          <EmptyState
            icon={<FileClock />}
            title="No events"
            description="Adjust filters or run some operations to generate audit events."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>User</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-mono text-[11px] text-foreground-muted">
                    {new Date(e.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{e.category}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-[11px]">
                    {e.action}
                  </TableCell>
                  <TableCell>
                    {e.outcome === "success" ? (
                      <Badge variant="success">success</Badge>
                    ) : (
                      <Badge variant="danger">failure</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-foreground-muted">
                    {e.target_type ? (
                      <span className="font-mono text-[11px]">
                        {e.target_type}
                        {e.target_id ? `/${e.target_id.slice(0, 8)}…` : ""}
                      </span>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-[11px] text-foreground-muted">
                    {e.user_id ? `${e.user_id.slice(0, 8)}…` : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function FilterField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
