"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { apiDownloadBlob, triggerBlobDownload } from "@/lib/api";

/**
 * Hook for downloading reports with loading state and error handling.
 *
 * @param endpoint  API path, e.g. "/api/v1/report/download"
 * @param filename  Base filename without suffix, e.g. "genewizard-report"
 * @param extension File extension including dot, defaults to ".pdf"
 */
export function useReportDownload(endpoint: string, filename: string, extension = ".pdf") {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const download = useCallback(
    async (filenameSuffix?: string) => {
      setLoading(true);
      setError(null);
      try {
        const token = await getToken();
        const blob = await apiDownloadBlob(endpoint, token);
        const suffix = filenameSuffix ? `--${filenameSuffix}` : "";
        triggerBlobDownload(blob, `${filename}${suffix}${extension}`);
      } catch {
        setError("Failed to download report. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [getToken, endpoint, filename, extension],
  );

  return { download, loading, error };
}
