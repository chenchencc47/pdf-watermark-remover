import { describe, expect, it } from 'vitest';
import type { WatermarkCandidate } from '../shared/types';
import { getDefaultCandidateIds, toggleCandidateId } from './candidateSelection';

function candidate(id: string, canAutoRemove: boolean): WatermarkCandidate {
  return {
    id,
    kind: 'text',
    label: id,
    pages: [1],
    occurrenceCount: 1,
    confidence: canAutoRemove ? 0.9 : 0.7,
    canAutoRemove,
    reason: 'test candidate'
  };
}

describe('candidate selection', () => {
  it('selects auto-removable candidates by default', () => {
    expect(getDefaultCandidateIds([candidate('text:VolkaEnglish', true), candidate('text:Chapter', false)])).toEqual([
      'text:VolkaEnglish'
    ]);
  });

  it('toggles a candidate without mutating the current selection', () => {
    const current = ['text:VolkaEnglish'];

    expect(toggleCandidateId(current, 'text:VolkaEnglish')).toEqual([]);
    expect(toggleCandidateId(current, 'text:Chapter')).toEqual(['text:VolkaEnglish', 'text:Chapter']);
    expect(current).toEqual(['text:VolkaEnglish']);
  });
});
