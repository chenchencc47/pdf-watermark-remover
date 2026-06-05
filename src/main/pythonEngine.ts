import { spawn } from 'node:child_process';
import path from 'node:path';
import { existsSync } from 'node:fs';
import { app } from 'electron';
import type { DetectionResult, ExportResult, PreviewResult } from '../shared/types.js';

function engineRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'engine');
  }
  return path.join(process.cwd(), 'engine');
}

function pythonExecutable() {
  if (app.isPackaged && process.platform === 'win32') {
    return path.join(process.resourcesPath, 'engine', 'pdf-watermark-engine.exe');
  }

  const localVenvPython = path.join(process.cwd(), '..', '.pdf-inspect-venv', 'Scripts', 'python.exe');
  if (process.platform === 'win32' && existsSync(localVenvPython)) {
    return localVenvPython;
  }

  return process.platform === 'win32' ? 'python' : 'python3';
}

async function runEngine<T>(args: string[]): Promise<T> {
  return new Promise((resolve, reject) => {
    const packaged = app.isPackaged;
    const command = pythonExecutable();
    const finalArgs = packaged ? args : ['-m', 'pdf_watermark_remover.cli', ...args];
    const child = spawn(command, finalArgs, {
      cwd: engineRoot(),
      env: { ...process.env, PYTHONPATH: engineRoot(), PYTHONUTF8: '1' },
      windowsHide: true
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += String(chunk); });
    child.stderr.on('data', (chunk) => { stderr += String(chunk); });
    child.on('error', reject);
    child.on('close', (code) => {
      try {
        const payload = JSON.parse(stdout);
        if (code !== 0 || payload.error) {
          reject(new Error(payload.error?.message || stderr || `Engine exited with ${code}`));
          return;
        }
        resolve(payload as T);
      } catch (error) {
        reject(new Error(`Engine returned invalid JSON: ${stdout || stderr || String(error)}`));
      }
    });
  });
}

export async function detectWatermarks(pdfPath: string): Promise<DetectionResult> {
  return runEngine<DetectionResult>(['detect', pdfPath]);
}

export async function renderPreview(pdfPath: string, candidateIds: string[], page: number): Promise<PreviewResult> {
  return runEngine<PreviewResult>(['preview', pdfPath, JSON.stringify(candidateIds), String(page)]);
}

export async function exportPdf(pdfPath: string, candidateIds: string[], outputPath: string): Promise<ExportResult> {
  return runEngine<ExportResult>(['export', pdfPath, JSON.stringify(candidateIds), outputPath]);
}
