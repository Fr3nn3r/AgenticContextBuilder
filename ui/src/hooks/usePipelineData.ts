/**
 * Data fetching hooks for Pipeline Control Center.
 *
 * Provides hooks for:
 * - Claims available for pipeline processing
 * - Pipeline runs with enhanced metadata
 * - Prompt configurations
 * - Audit log entries
 */

import { useCallback, useEffect, useState } from "react";
import {
  listPipelineClaims,
  listEnhancedPipelineRuns,
  listPromptConfigs,
  createPromptConfig,
  updatePromptConfig,
  deletePromptConfig,
  setDefaultPromptConfig,
  listAuditEntries,
} from "../api/client";
import type {
  PipelineClaimOption,
  EnhancedPipelineRun,
  PromptConfig,
  CreatePromptConfigRequest,
  UpdatePromptConfigRequest,
  AuditEntry,
  AuditListParams,
} from "../types";

// =============================================================================
// CLAIMS HOOK
// =============================================================================

export interface UsePipelineClaimsResult {
  claims: PipelineClaimOption[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function usePipelineClaims(): UsePipelineClaimsResult {
  const [claims, setClaims] = useState<PipelineClaimOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listPipelineClaims();
      setClaims(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { claims, isLoading, error, refetch: fetch };
}

// =============================================================================
// RUNS HOOK
// =============================================================================

export interface UsePipelineRunsResult {
  runs: EnhancedPipelineRun[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function usePipelineRuns(): UsePipelineRunsResult {
  const [runs, setRuns] = useState<EnhancedPipelineRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listEnhancedPipelineRuns();
      setRuns(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { runs, isLoading, error, refetch: fetch };
}

// =============================================================================
// PROMPT CONFIGS HOOK
// =============================================================================

export interface UsePromptConfigsResult {
  configs: PromptConfig[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  createConfig: (request: CreatePromptConfigRequest) => Promise<PromptConfig>;
  updateConfig: (id: string, request: UpdatePromptConfigRequest) => Promise<PromptConfig>;
  deleteConfig: (id: string) => Promise<void>;
  setDefault: (id: string) => Promise<PromptConfig>;
}

export function usePromptConfigs(): UsePromptConfigsResult {
  const [configs, setConfigs] = useState<PromptConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listPromptConfigs();
      setConfigs(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const create = useCallback(
    async (request: CreatePromptConfigRequest): Promise<PromptConfig> => {
      const config = await createPromptConfig(request);
      await fetch(); // Refresh list
      return config;
    },
    [fetch]
  );

  const update = useCallback(
    async (id: string, request: UpdatePromptConfigRequest): Promise<PromptConfig> => {
      const config = await updatePromptConfig(id, request);
      await fetch(); // Refresh list
      return config;
    },
    [fetch]
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await deletePromptConfig(id);
      await fetch(); // Refresh list
    },
    [fetch]
  );

  const setDef = useCallback(
    async (id: string): Promise<PromptConfig> => {
      const config = await setDefaultPromptConfig(id);
      await fetch(); // Refresh list
      return config;
    },
    [fetch]
  );

  return {
    configs,
    isLoading,
    error,
    refetch: fetch,
    createConfig: create,
    updateConfig: update,
    deleteConfig: remove,
    setDefault: setDef,
  };
}

// =============================================================================
// AUDIT LOG HOOK
// =============================================================================

export interface UseAuditLogResult {
  entries: AuditEntry[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useAuditLog(params?: AuditListParams): UseAuditLogResult {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Serialize params for dependency tracking
  const paramsKey = JSON.stringify(params || {});

  const fetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listAuditEntries(params);
      setEntries(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, [paramsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { entries, isLoading, error, refetch: fetch };
}
