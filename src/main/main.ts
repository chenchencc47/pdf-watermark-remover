import { BrowserWindow, app, dialog, ipcMain, shell } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { detectWatermarks, exportPdf, renderPreview } from './pythonEngine.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;
const exportedPdfPaths = new Set<string>();

function requireString(value: unknown, name: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`${name} must be a non-empty string.`);
  }
  return value;
}

function requireStringArray(value: unknown, name: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string')) {
    throw new Error(`${name} must be a string array.`);
  }
  return value;
}

function normalizePathForComparison(filePath: string) {
  const resolved = path.resolve(filePath);
  return process.platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function registerExportedPdfPath(outputPath: string) {
  exportedPdfPaths.add(normalizePathForComparison(outputPath));
}

function requireExportedPdfPath(value: unknown): string {
  const safeOutputPath = requireString(value, 'outputPath');
  if (path.extname(safeOutputPath).toLowerCase() !== '.pdf') {
    throw new Error('只能打开导出的 PDF 文件。');
  }
  if (!exportedPdfPaths.has(normalizePathForComparison(safeOutputPath))) {
    throw new Error('只能打开本次导出的 PDF 文件。');
  }
  return safeOutputPath;
}

async function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 780,
    minWidth: 980,
    minHeight: 680,
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (isDev) {
    await win.loadURL('http://127.0.0.1:5173');
  } else {
    await win.loadFile(path.join(__dirname, '../renderer/index.html'));
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.handle('dialog:selectPdf', async () => {
  const result = await dialog.showOpenDialog({
    title: '选择 PDF 文件',
    filters: [{ name: 'PDF 文件', extensions: ['pdf'] }],
    properties: ['openFile']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('dialog:selectOutputPdf', async (_event, inputPath: unknown) => {
  const safeInputPath = requireString(inputPath, 'inputPath');
  const parsedPath = path.parse(safeInputPath);
  const result = await dialog.showSaveDialog({
    title: '保存去水印 PDF',
    defaultPath: path.join(parsedPath.dir, `${parsedPath.name}.no-watermark.pdf`),
    filters: [{ name: 'PDF 文件', extensions: ['pdf'] }]
  });
  if (result.canceled || !result.filePath) return null;
  return normalizePathForComparison(result.filePath) === normalizePathForComparison(safeInputPath) ? null : result.filePath;
});

ipcMain.handle('shell:openPath', async (_event, outputPath: unknown) => {
  const safeOutputPath = requireExportedPdfPath(outputPath);
  const error = await shell.openPath(safeOutputPath);
  if (error) {
    throw new Error(error);
  }
});

ipcMain.handle('shell:showItemInFolder', (_event, outputPath: unknown) => {
  const safeOutputPath = requireExportedPdfPath(outputPath);
  shell.showItemInFolder(safeOutputPath);
});

ipcMain.handle('engine:detect', async (_event, pdfPath: string) => detectWatermarks(pdfPath));
ipcMain.handle('engine:preview', async (_event, pdfPath: string, candidateIds: string[], page: number) => renderPreview(pdfPath, candidateIds, page));
ipcMain.handle('engine:export', async (_event, pdfPath: unknown, candidateIds: unknown, outputPath: unknown) => {
  const safePdfPath = requireString(pdfPath, 'pdfPath');
  const safeCandidateIds = requireStringArray(candidateIds, 'candidateIds');
  const safeOutputPath = requireString(outputPath, 'outputPath');
  if (normalizePathForComparison(safeOutputPath) === normalizePathForComparison(safePdfPath)) {
    throw new Error('输出路径不能与原 PDF 相同。');
  }
  const result = await exportPdf(safePdfPath, safeCandidateIds, safeOutputPath);
  registerExportedPdfPath(result.outputPath);
  return result;
});
