"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { apiDownloadBlob, triggerBlobDownload } from "@/lib/api";

/**
 * Hook for downloading PDF reports with loading state and error handling.
 *
 * @param endpoint  API path, e.g. "/api/v1/report/download"
 * @param filename  Base filename without suffix, e.g. "genewizard-report"
 */
export function useReportDownload(endpoint: string, filename: string) {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(false);

  const download = useCallback(
    async (filenameSuffix?: string) => {
      setLoading(true);
      try {
        const token = await getToken();
        const blob = await apiDownloadBlob(endpoint, token);
        const suffix = filenameSuffix ? `--${filenameSuffix}` : "";
        triggerBlobDownload(blob, `${filename}${suffix}.pdf`);
      } catch {
        alert(`Failed to download report. Please try again.`);
      } finally {
        setLoading(false);
      }
    },
    [getToken, endpoint, filename],
  );

  return { download, loading };
}
