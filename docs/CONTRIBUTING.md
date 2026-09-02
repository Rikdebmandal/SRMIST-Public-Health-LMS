# Contributing

## Adding a backend module

The platform is built so a new domain slots in without touching the plumbing.

1. **App** — `python manage.py startapp <name> apps/<name>`, then register it in
   `INSTALLED_APPS`.

2. **Models** — inherit `apps.core.models.BaseModel` for UUID keys, timestamps,
   actor tracking and soft delete. Put real constraints on the table:
   `unique_together` for natural keys, `CheckConstraint` for ranges, indexes on
   the columns your scoping queries filter by.

3. **Permissions** — add codes to `apps/core/rbac.py`: the constant on `Perm`, a
   human label in `PERMISSION_LABELS`, and the roles that hold it in
   `DEFAULT_ROLE_PERMISSIONS`. Never invent a permission string inline.

4. **Serializer** — validate business rules here, not in the view. Range checks,
   cross-field consistency, and refusing edits to locked records.

5. **Viewset** — extend `AuditedModelViewSet`:

   ```python
   class ThingViewSet(AuditedModelViewSet):
       queryset = Thing.objects.select_related("owner")
       serializer_class = ThingSerializer
       required_permission = Perm.THING_VIEW
       required_write_permission = Perm.THING_MANAGE
       audit_object_type = "thing"
       # Custom actions serving a different audience need their own permission:
       action_permissions = {"claim": Perm.THING_CLAIM}

       def get_queryset(self):
           qs = super().get_queryset()
           if self.request.user.role == Roles.STUDENT:
               qs = qs.filter(owner=self.request.user)
           return qs
   ```

   `get_queryset()` is where row-level access lives. Filter there and search,
   ordering and pagination inherit the restriction for free.

6. **Route** — register in `config/urls.py` under the versioned router.

7. **Navigation** — add an entry to `frontend/src/components/layout/navigation.ts`
   with its permission. It then appears only for roles that hold it.

8. **Tests** — at minimum: a user without the permission is refused; a user
   cannot reach another user's row; the boundary values behave.

## Rules that are not negotiable

**Never compute an academic figure outside `apps/core/calculations.py`.** No
percentage, weighted total, grade or GPA in a view, serializer or React
component. One place to read, one place to fix.

**Never hard-code a threshold.** The 75% attendance rule, grade boundaries and
risk weights are database rows. If you find yourself typing a number that an
administrator might reasonably want to change, it belongs in configuration.

**Never rely on the frontend for authorisation.** Hiding a button is a
convenience. The server check is the control.

**Never log a credential or a student identifier.** `apps/auditlogs/services.py`
has `scrub()`; use it for anything that reaches audit metadata.

**Never present the risk indicator without its factors.** The score alone is not
actionable and invites exactly the automated judgement the design refuses.

## Frontend conventions

- Use the UI kit in `src/components/ui`. If you need a new primitive, add it
  there rather than styling inline in a page.
- Every async view needs four states: loading (`LoadingState`), empty
  (`EmptyState`), error (`ErrorState`) and success. A blank screen is a bug.
- Wide tables go inside the `Table` component, which scrolls horizontally within
  its own container. The page body must never scroll sideways.
- Charts come from `src/components/charts`, so palette and axis conventions stay
  consistent and theme-aware.
- Form fields use `Field`, which wires up the label, hint, error and the
  `aria-describedby` / `aria-invalid` attributes together.
- Interactive controls need an accessible name. Icon-only buttons take
  `aria-label`; decorative icons take `aria-hidden`.

## Style

Backend follows PEP 8 with a 100-character limit. Frontend uses the Next.js
ESLint config with TypeScript strict mode; `npm run typecheck` must pass.

Write comments that explain *why*, not *what*. A comment restating the code is
noise; a comment explaining why a zero-value slice breaks Recharts, or why
`respondent` is deliberately nullable, saves the next reader an hour.

## Commits

```
feat: add curriculum prerequisite validation
fix: prevent duplicate attendance session for same period
docs: document the certificate verification endpoint
test: cover grade boundary inclusivity
refactor: extract attendance summary into the service layer
```

One logical change per commit. Run the tests before pushing:

```bash
cd backend && python manage.py test apps.core.tests
cd ../frontend && npm run typecheck && npm run build
```

## Before opening a pull request

- [ ] Tests pass and new behaviour has a test
- [ ] `makemigrations --check --dry-run` is clean
- [ ] No hard-coded threshold, formula or permission string
- [ ] New endpoints enforce permission **and** scope their queryset
- [ ] New pages handle loading, empty and error states
- [ ] Checked at 375px width for horizontal overflow
- [ ] Checked in both light and dark themes
