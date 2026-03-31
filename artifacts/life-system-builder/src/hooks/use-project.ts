import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import {
  getGetProjectQueryOptions,
  getListProjectStagesQueryOptions,
  getListProjectStagesQueryKey,
  type ProjectWithStages,
  StageStatus,
} from "@workspace/api-client-react";

export function useProjectWithStages(projectId: number) {
  const { data: project, isLoading: projectLoading, error: projectError } = useQuery(
    getGetProjectQueryOptions(projectId)
  );
  const { data: stages, isLoading: stagesLoading } = useQuery(
    getListProjectStagesQueryOptions(projectId)
  );

  const projectWithStages: ProjectWithStages | undefined = project
    ? { ...project, stages: stages ?? [] }
    : undefined;

  return {
    project,
    stages: stages ?? [],
    projectWithStages,
    isLoading: projectLoading || stagesLoading,
    projectError,
  };
}

export function useStagePolling(projectId: number) {
  const queryClient = useQueryClient();
  const { stages } = useProjectWithStages(projectId);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasRunning = stages.some(
    (s) => s.status === StageStatus.running
  );

  useEffect(() => {
    if (hasRunning) {
      timerRef.current = setInterval(() => {
        queryClient.invalidateQueries({
          queryKey: getListProjectStagesQueryKey(projectId),
        });
      }, 3000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [hasRunning, projectId, queryClient]);
}
