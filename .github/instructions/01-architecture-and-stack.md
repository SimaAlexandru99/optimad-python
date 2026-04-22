# Optimad Python — Architecture & Stack

- **Domain:** Python utilities and services for Optimad.
- **Stack:** Python, FastAPI, pytest.
- **Core Pattern:** Localized routes in app/[lang]/. Business logic in tRPC routers (server/routers/_app.ts).
- **Data Safety:** Env validation via lib/env.ts. All DB access through Prisma.

## Non-Obvious Workflows
- Use Bun for all operations.
