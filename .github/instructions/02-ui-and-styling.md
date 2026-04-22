# UI Architecture Constraints

- **Primitives:** components/ui/ is EXCLUDED. NEVER modify or add lint overrides there.
- **Data Fetching:** Dashboard list (RSC), Detail (async tRPC + Suspense). Use notFound()/unstable_rethrow().
- **Styling:** shadcn/ui + Tailwind. Follow existing patterns.
