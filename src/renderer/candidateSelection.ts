import type { WatermarkCandidate } from '../shared/types';

export function getDefaultCandidateIds(candidates: WatermarkCandidate[]) {
  return candidates.filter((candidate) => candidate.canAutoRemove).map((candidate) => candidate.id);
}

export function toggleCandidateId(currentIds: string[], candidateId: string) {
  if (currentIds.includes(candidateId)) {
    return currentIds.filter((id) => id !== candidateId);
  }
  return [...currentIds, candidateId];
}
