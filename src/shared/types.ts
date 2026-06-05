export interface PdfInfo {
  path: string;
  pageCount: number;
  encrypted: boolean;
  hasText: boolean;
  pageSizes: Array<{ page: number; width: number; height: number }>;
}

export interface WatermarkCandidate {
  id: string;
  kind: 'text' | 'image' | 'vector' | 'artifact' | 'xobject';
  label: string;
  pages: number[];
  occurrenceCount: number;
  confidence: number;
  canAutoRemove: boolean;
  reason: string;
}

export interface DetectionResult {
  pdf: PdfInfo;
  candidates: WatermarkCandidate[];
  recommendedMode: 'object' | 'confirm' | 'image-fallback' | 'none';
  message: string;
}

export interface PreviewResult {
  page: number;
  beforePng: string;
  afterPng: string;
}

export interface ExportResult {
  outputPath: string;
  removedCount: number;
  pageCount: number;
}

export interface AppApi {
  selectPdf(): Promise<string | null>;
  selectOutputPdf(inputPath: string): Promise<string | null>;
  detectWatermarks(pdfPath: string): Promise<DetectionResult>;
  renderPreview(pdfPath: string, candidateIds: string[], page: number): Promise<PreviewResult>;
  exportPdf(pdfPath: string, candidateIds: string[], outputPath: string): Promise<ExportResult>;
  openOutputPdf(path: string): Promise<void>;
  showOutputInFolder(path: string): Promise<void>;
}

declare global {
  interface Window {
    appApi: AppApi;
  }
}
