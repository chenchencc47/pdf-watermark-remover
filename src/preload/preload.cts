import type { AppApi } from '../shared/types.js';

const { contextBridge, ipcRenderer } = require('electron');

const api: AppApi = {
  selectPdf: () => ipcRenderer.invoke('dialog:selectPdf'),
  selectOutputPdf: (inputPath) => ipcRenderer.invoke('dialog:selectOutputPdf', inputPath),
  detectWatermarks: (pdfPath) => ipcRenderer.invoke('engine:detect', pdfPath),
  renderPreview: (pdfPath, candidateIds, page) => ipcRenderer.invoke('engine:preview', pdfPath, candidateIds, page),
  exportPdf: (pdfPath, candidateIds, outputPath) => ipcRenderer.invoke('engine:export', pdfPath, candidateIds, outputPath),
  openOutputPdf: (path) => ipcRenderer.invoke('shell:openPath', path),
  showOutputInFolder: (path) => ipcRenderer.invoke('shell:showItemInFolder', path)
};

contextBridge.exposeInMainWorld('appApi', api);
