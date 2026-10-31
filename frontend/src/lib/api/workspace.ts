import { get, patch, post, put, remove } from "./client";

/** A register's filter state as the screen defines it: strings, numbers, booleans or null. */
export type ViewFilters = Record<string, string | number | boolean | null>;

export interface SavedView {
  id: string;
  screen: string;
  name: string;
  filters: ViewFilters;
  sort: string | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export type RegisterDensity = "comfortable" | "compact";

export interface Preferences {
  register_density: RegisterDensity;
}

/** The caller's own saved views and register preferences (design system F3, E4). */
export const workspace = {
  listViews: (screen: string) => get<SavedView[]>(`/me/views?screen=${encodeURIComponent(screen)}`),
  createView: (body: { screen: string; name: string; filters: ViewFilters; sort: string | null; pinned?: boolean }) =>
    post<SavedView>("/me/views", body),
  updateView: (id: string, body: { name?: string; pinned?: boolean; filters?: ViewFilters; sort?: string | null }) =>
    patch<SavedView>(`/me/views/${id}`, body),
  deleteView: (id: string) => remove(`/me/views/${id}`),
  readPreferences: () => get<Preferences>("/me/preferences"),
  updatePreferences: (body: Preferences) => put<Preferences>("/me/preferences", { register_density: body.register_density }),
};
