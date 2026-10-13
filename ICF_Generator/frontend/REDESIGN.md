# ICF AI frontend redesign

This is a frontend-only redesign of the supplied ICF Generator. Backend code, API client, request payloads, endpoint paths, application configuration, package dependencies and lockfile are preserved.

## Run

Use the existing backend environment and startup procedure from the project README. The frontend keeps `VITE_API_BASE_URL` and the unchanged default `http://127.0.0.1:8001`.

```sh
cd frontend
npm ci
npm run dev
```

Production build: `npm run build`. Pure workflow regression checks: `node tests/workflow.test.mjs`.

The delivered archive excludes installed `node_modules` and generated Python/test caches. It includes the production `dist` build. No new dependencies were introduced.

## Interface

- Eight navigation workspaces and a ten-stage pathway, with current-source completion derived from returned data.
- Clinical light palette, editorial display typography, layered paper illustration, restrained state-driven motion and reduced-motion support.
- Accessible study selector, keyboard-accessible source tabs, native file input, drag and drop, and separate text extraction through the existing processing API.
- Canonical fields, chunk controls/previews, embedding metadata, vector index, similarity evidence, RAG settings, structured facts and complete technical responses.
- Structured and patient-friendly ICF previews, actual validation findings, reviewer feedback, approval/request changes, regeneration and approved-only DOCX actions.
- Mobile navigation and stacked layouts; errors remain visible with available retries.

## Architecture and preservation

The original business state and functions remain in `src/App.jsx`. Presentation lives in `src/components/`. Additional WeakMaps associate responses with their request source and validation draft. They do not mutate response data or change API calls. These associations prevent old results from marking a new source or draft complete.

The original export check `humanReview?.review_status !== "APPROVED"` remains intact, as do both export function calls, Blob download behavior and filename construction. Download feedback appears only after the existing download function is invoked for the matching draft.

## Existing limitations found during audit

These were present in the supplied project and were left unchanged to honor the immutable API/backend requirement:

1. Patient-friendly export sends its type in the query string, while the backend's body model defaults the type to `standard` and gives that body value precedence. A patient-friendly button request can therefore return standard document content. The export buttons and original contract are preserved; this integration issue needs a separate fix before relying on that export variant.
2. Fresh generation without reviewer feedback does not reset an existing backend approval. Feedback-based regeneration does reset approval. Review records do not identify the approved draft revision.
3. The backend treats a zero chunk overlap as its default 150, despite accepting zero in request validation.
4. The backend requirements file omits several document/embedding runtime packages imported by the existing code. Use the project's already-provisioned environment.

See the accompanying `Implementation-report.md` for verification results and environment limitations.
