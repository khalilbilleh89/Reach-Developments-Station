"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { workspace } from "@/lib/api/workspace";
import type { RegisterDensity } from "@/lib/api/workspace";

import { Switch } from "./Controls";

interface DensityApi {
  density: RegisterDensity;
  setDensity: (density: RegisterDensity) => void;
}

const DensityContext = createContext<DensityApi>({ density: "comfortable", setDensity: () => {} });

/**
 * How this person likes their registers drawn (design system E4), remembered
 * on the server so it follows them between browsers. The choice is written
 * onto the document as `data-density`, and the stylesheet draws every
 * register from that one attribute; no table reads the context.
 */
export function DensityProvider({ children }: { children: ReactNode }) {
  const [density, setDensityState] = useState<RegisterDensity>("comfortable");

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const preferences = await workspace.readPreferences();
        if (live) setDensityState(preferences.register_density);
      } catch {
        // A person without a stored choice, or a failed read, gets the default.
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-density", density);
  }, [density]);

  const setDensity = (next: RegisterDensity) => {
    setDensityState(next);
    void workspace.updatePreferences({ register_density: next }).catch(() => {
      // The screen already shows the choice; a failed save costs only its memory.
    });
  };

  return <DensityContext.Provider value={{ density, setDensity }}>{children}</DensityContext.Provider>;
}

export function useDensity(): DensityApi {
  return useContext(DensityContext);
}

/** The one switch a register shows for its row density. */
export function DensitySwitch() {
  const { density, setDensity } = useDensity();
  return (
    <Switch checked={density === "compact"} onChange={(compact) => setDensity(compact ? "compact" : "comfortable")}>
      Compact rows
    </Switch>
  );
}
