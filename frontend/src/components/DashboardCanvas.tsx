import { useMemo } from "react";
import { JSONUIProvider, Renderer, type Spec } from "@json-render/react";

import { registry } from "../registry";
import { DashboardFilterBar } from "./DashboardFilterBar";
import type { SpecWithState } from "../types";

/**
 * One dashboard spec rendered under its own `JSONUIProvider`. The provider both scopes the
 * widgets' `$state` bindings to this spec AND is the coordination boundary for cross-filtering:
 * a selection written to the shared state is visible to every sibling widget here and to no
 * other dashboard. The `DashboardFilterBar` sits above the widgets as the always-present,
 * explicit controls for the dashboard's dimensions (plus the active selections and clear-all).
 *
 * A fresh state object per spec ref (one per streamed patch) makes the provider re-flatten the
 * streamed state into its store, resolving `$state` as each widget's data arrives.
 */
export function DashboardCanvas({ spec, loading }: { spec: Spec | null; loading: boolean }) {
  const stateModel = useMemo(() => {
    const state = (spec as SpecWithState | null)?.state;
    return state ? { ...state } : {};
  }, [spec]);

  return (
    <JSONUIProvider registry={registry} initialState={stateModel}>
      <DashboardFilterBar spec={spec} />
      {/* loading lets the renderer show partial trees gracefully while patches arrive */}
      <Renderer spec={spec} registry={registry} loading={loading} />
    </JSONUIProvider>
  );
}
