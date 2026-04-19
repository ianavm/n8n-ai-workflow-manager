/**
 * Single source of truth for public client signup state.
 *
 * When false, every public path that could create a new `clients` row
 * (email form, magic-link, Google OAuth first login) is blocked.
 * Admin-created clients via /api/admin/clients POST are unaffected.
 *
 * Flip to true to reopen public signups.
 */
export const PUBLIC_SIGNUPS_ENABLED = false;
