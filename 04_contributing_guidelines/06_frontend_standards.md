# Frontend Standards

Standards for building frontend pages and components in tennetctl.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Next.js (App Router) |
| UI Library | shadcn/ui |
| Styling | Tailwind CSS |
| Forms | React Hook Form + Zod |
| Data Fetching | TanStack Query (React Query) |
| Language | TypeScript (strict mode) |
| Package Manager | npm |

---

## Directory Structure

```
frontend/src/app/features/{module}/{sub_feature}/
├── page.tsx                    # Next.js page component
├── components/                 # Sub-feature-specific components
│   ├── {Entity}List.tsx        # List/table view
│   ├── {Entity}Form.tsx        # Create/edit form
│   ├── {Entity}Detail.tsx      # Detail/show view
│   └── {Entity}Actions.tsx     # Action buttons/menus
├── hooks/                      # Custom hooks
│   └── use{Entity}.ts          # TanStack Query hooks
└── types/                      # TypeScript types
    └── index.ts                # Type definitions
```

---

## Component Standards

### Server Components by Default

Use server components unless the component needs:
- Event handlers (`onClick`, `onChange`)
- Browser APIs (`useState`, `useEffect`)
- TanStack Query hooks

Only add `"use client"` when actually needed.

### shadcn/ui Components

Use shadcn/ui for all UI primitives. Do not install additional UI libraries.

```tsx
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
```

### Component Naming

| Type | Convention | Example |
|------|-----------|---------|
| Page | `page.tsx` | `page.tsx` |
| List component | `{Entity}List.tsx` | `OrgList.tsx` |
| Form component | `{Entity}Form.tsx` | `OrgForm.tsx` |
| Detail component | `{Entity}Detail.tsx` | `OrgDetail.tsx` |
| Hook | `use{Entity}.ts` | `useOrgs.ts` |
| Type file | `index.ts` | `types/index.ts` |

---

## Data Fetching with TanStack Query

### Query Hook

```tsx
// hooks/useOrgs.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useOrgs() {
  return useQuery({
    queryKey: ["orgs"],
    queryFn: () => api.get("/v1/orgs").then(r => r.data.data),
  })
}

export function useOrg(orgId: string) {
  return useQuery({
    queryKey: ["orgs", orgId],
    queryFn: () => api.get(`/v1/orgs/${orgId}`).then(r => r.data.data),
    enabled: !!orgId,
  })
}

export function useCreateOrg() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateOrgInput) =>
      api.post("/v1/orgs", data).then(r => r.data.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] })
    },
  })
}
```

Rules:
- One hook file per sub-feature
- Query keys follow `[entity, ...params]` pattern
- Invalidate related queries on mutation success
- Handle the response envelope (`r.data.data`)

---

## Form Handling

### Zod Schema (mirrors backend Pydantic)

```tsx
import { z } from "zod"

export const createOrgSchema = z.object({
  name: z.string().min(1).max(200),
  slug: z.string().regex(/^[a-z0-9-]+$/).min(2).max(50),
})

export type CreateOrgInput = z.infer<typeof createOrgSchema>
```

### React Hook Form

```tsx
"use client"

import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { createOrgSchema, CreateOrgInput } from "../types"
import { useCreateOrg } from "../hooks/useOrgs"

export function OrgForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<CreateOrgInput>({
    resolver: zodResolver(createOrgSchema),
  })

  const createOrg = useCreateOrg()

  const onSubmit = (data: CreateOrgInput) => {
    createOrg.mutate(data)
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <Input {...register("name")} placeholder="Organisation name" />
      {errors.name && <p className="text-red-500 text-sm">{errors.name.message}</p>}

      <Input {...register("slug")} placeholder="org-slug" />
      {errors.slug && <p className="text-red-500 text-sm">{errors.slug.message}</p>}

      <Button type="submit" disabled={createOrg.isPending}>
        {createOrg.isPending ? "Creating..." : "Create Organisation"}
      </Button>
    </form>
  )
}
```

---

## TypeScript Standards

- **Strict mode** — `strict: true` in `tsconfig.json`
- **No `any`** — use proper types or `unknown` when type is genuinely unknown
- **Interface for objects, type for unions/intersections**
- **Export types from `types/index.ts`**

```tsx
// types/index.ts
export interface Org {
  id: string
  name: string
  slug: string
  status: string
  is_active: boolean
  created_at: string
}

export interface CreateOrgInput {
  name: string
  slug: string
}
```

---

## Error Handling in UI

Display errors from the API envelope:

```tsx
const createOrg = useCreateOrg()

// In the mutation
createOrg.mutate(data, {
  onError: (error) => {
    // API returns { ok: false, error: { code, message } }
    const apiError = error.response?.data?.error
    if (apiError) {
      toast.error(apiError.message)
    } else {
      toast.error("An unexpected error occurred")
    }
  },
})
```

---

## Styling

- Use Tailwind CSS utility classes
- Follow the shadcn/ui design system
- No inline styles
- No custom CSS files unless absolutely necessary
- Dark mode support via Tailwind's `dark:` prefix

---

## Checklist — Before Every Frontend PR

- [ ] Server components used by default
- [ ] `"use client"` only where necessary
- [ ] shadcn/ui components used (no extra UI libraries)
- [ ] Forms validated with Zod (mirrors backend Pydantic)
- [ ] TanStack Query for all data fetching
- [ ] No `any` types
- [ ] Error states handled and displayed
- [ ] Loading states shown during mutations
- [ ] Query invalidation on successful mutations
- [ ] TypeScript strict mode — no errors
