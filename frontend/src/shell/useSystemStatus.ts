import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { ReadyStatus, ServiceMeta } from "../api/types";

type SystemState = {
  meta: ServiceMeta | null;
  ready: ReadyStatus | null;
  reachable: boolean;
};

export function useSystemStatus() {
  const [state, setState] = useState<SystemState>({
    meta: null,
    ready: null,
    reachable: false
  });

  useEffect(() => {
    let active = true;

    async function load() {
      const [metaResult, readyResult] = await Promise.allSettled([
        api.meta(),
        api.ready()
      ]);
      if (!active) return;

      setState({
        meta: metaResult.status === "fulfilled" ? metaResult.value : null,
        ready:
          readyResult.status === "fulfilled" ? readyResult.value : null,
        reachable: metaResult.status === "fulfilled"
      });
    }

    void load();
    return () => {
      active = false;
    };
  }, []);

  return state;
}
