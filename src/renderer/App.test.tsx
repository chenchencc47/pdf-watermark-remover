import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import App from './App';
import type { AppApi, DetectionResult } from '../shared/types';

type TestAppApi = AppApi & {
  openOutputPdf: ReturnType<typeof vi.fn>;
  showOutputInFolder: ReturnType<typeof vi.fn>;
};

const detection: DetectionResult = {
  pdf: {
    path: 'sample.pdf',
    pageCount: 3,
    encrypted: false,
    hasText: true,
    pageSizes: [{ page: 1, width: 100, height: 100 }]
  },
  candidates: [
    {
      id: 'text:VolkaEnglish',
      kind: 'text',
      label: 'VolkaEnglish',
      pages: [1],
      occurrenceCount: 3,
      confidence: 0.92,
      canAutoRemove: true,
      reason: 'auto candidate'
    },
    {
      id: 'text:Volka,English',
      kind: 'text',
      label: 'Volka,English',
      pages: [2],
      occurrenceCount: 2,
      confidence: 0.72,
      canAutoRemove: false,
      reason: 'manual candidate'
    }
  ],
  recommendedMode: 'confirm',
  message: '检测到候选。'
};

function mockApi(overrides: Partial<TestAppApi> = {}) {
  const api: TestAppApi = {
    selectPdf: vi.fn().mockResolvedValue('sample.pdf'),
    selectOutputPdf: vi.fn().mockResolvedValue('sample.no-watermark.pdf'),
    detectWatermarks: vi.fn().mockResolvedValue(detection),
    renderPreview: vi.fn().mockResolvedValue({ page: 2, beforePng: 'before', afterPng: 'after' }),
    exportPdf: vi.fn().mockResolvedValue({ outputPath: 'sample.no-watermark.pdf', removedCount: 1, pageCount: 3 }),
    openOutputPdf: vi.fn().mockResolvedValue(undefined),
    showOutputInFolder: vi.fn().mockResolvedValue(undefined),
    ...overrides
  };
  window.appApi = api as unknown as AppApi;
  return api;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe('App candidate confirmation', () => {
  it('shows a desktop launch message when Electron API is unavailable', async () => {
    const user = userEvent.setup();
    delete (window as Partial<Window>).appApi;

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));

    expect(screen.getByText('请在 Electron 桌面窗口中使用选择 PDF 功能，不要直接打开浏览器页面。')).toBeInTheDocument();
  });

  it('passes the checked candidate ids to preview', async () => {
    const user = userEvent.setup();
    const api = mockApi();

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('Volka,English');

    await user.click(screen.getByRole('checkbox', { name: 'VolkaEnglish' }));
    await user.click(screen.getByRole('checkbox', { name: 'Volka,English' }));
    await user.click(screen.getByRole('button', { name: '生成预览' }));

    expect(api.renderPreview).toHaveBeenCalledWith('sample.pdf', ['text:Volka,English'], 2);
  });

  it('passes the requested page to preview', async () => {
    const user = userEvent.setup();
    const api = mockApi();

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.clear(screen.getByLabelText('预览页码'));
    await user.type(screen.getByLabelText('预览页码'), '3');
    await user.click(screen.getByRole('button', { name: '生成预览' }));

    expect(api.renderPreview).toHaveBeenCalledWith('sample.pdf', ['text:VolkaEnglish'], 3);
  });

  it('clamps requested preview page to the PDF page count', async () => {
    const user = userEvent.setup();
    const api = mockApi();

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.clear(screen.getByLabelText('预览页码'));
    await user.type(screen.getByLabelText('预览页码'), '999');
    await user.click(screen.getByRole('button', { name: '生成预览' }));

    expect(api.renderPreview).toHaveBeenCalledWith('sample.pdf', ['text:VolkaEnglish'], 3);
  });

  it('asks for an output path before exporting the selected candidates', async () => {
    const user = userEvent.setup();
    const api = mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf')
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await waitFor(() => expect(api.selectOutputPdf).toHaveBeenCalledWith('sample.pdf'));
    expect(api.exportPdf).toHaveBeenCalledWith('sample.pdf', ['text:VolkaEnglish'], 'custom-output.pdf');
  });

  it('does not export when output path selection is cancelled', async () => {
    const user = userEvent.setup();
    const api = mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue(null)
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('已取消导出。');
    expect(api.exportPdf).not.toHaveBeenCalled();
  });

  it('shows an error when export removes no watermark objects', async () => {
    const user = userEvent.setup();
    mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 0, pageCount: 3 })
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('未移除任何水印对象。');
  });

  it('clears a previous output path when a later export is cancelled', async () => {
    const user = userEvent.setup();
    const api = mockApi({
      selectOutputPdf: vi.fn()
        .mockResolvedValueOnce('first-output.pdf')
        .mockResolvedValueOnce(null),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'first-output.pdf', removedCount: 1, pageCount: 3 })
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：first-output.pdf');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('已取消导出。');
    expect(screen.queryByText('输出文件：first-output.pdf')).not.toBeInTheDocument();
    expect(api.exportPdf).toHaveBeenCalledTimes(1);
  });

  it('clears a previous output path when a later export fails', async () => {
    const user = userEvent.setup();
    mockApi({
      selectOutputPdf: vi.fn()
        .mockResolvedValueOnce('first-output.pdf')
        .mockResolvedValueOnce('second-output.pdf'),
      exportPdf: vi.fn()
        .mockResolvedValueOnce({ outputPath: 'first-output.pdf', removedCount: 1, pageCount: 3 })
        .mockRejectedValueOnce(new Error('导出失败'))
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：first-output.pdf');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('导出失败');
    expect(screen.queryByText('输出文件：first-output.pdf')).not.toBeInTheDocument();
  });

  it('disables selection and candidate actions while export is waiting for an output path', async () => {
    const user = userEvent.setup();
    const outputSelection = deferred<string | null>();
    mockApi({
      selectOutputPdf: vi.fn().mockReturnValue(outputSelection.promise)
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('正在选择输出位置...');
    expect(screen.getByRole('button', { name: '选择 PDF' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '生成预览' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '导出去水印 PDF' })).toBeDisabled();

    outputSelection.resolve(null);
    await screen.findByText('已取消导出。');
  });

  it('disables selection and export while preview is running', async () => {
    const user = userEvent.setup();
    const previewResult = deferred<{ page: number; beforePng: string; afterPng: string }>();
    mockApi({
      renderPreview: vi.fn().mockReturnValue(previewResult.promise)
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '生成预览' }));

    await screen.findByText('正在生成预览...');
    expect(screen.getByRole('button', { name: '选择 PDF' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '生成预览' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '导出去水印 PDF' })).toBeDisabled();

    previewResult.resolve({ page: 2, beforePng: 'before', afterPng: 'after' });
    await screen.findByText('预览已生成。');
  });

  it('shows open output actions after export succeeds', async () => {
    const user = userEvent.setup();
    mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 1, pageCount: 3 })
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');

    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));

    await screen.findByText('输出文件：custom-output.pdf');
    expect(screen.getByRole('button', { name: '打开文件' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开所在文件夹' })).toBeInTheDocument();
  });

  it('opens the exported PDF when clicking open file', async () => {
    const user = userEvent.setup();
    const api = mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 1, pageCount: 3 })
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');
    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：custom-output.pdf');

    await user.click(screen.getByRole('button', { name: '打开文件' }));

    expect(api.openOutputPdf).toHaveBeenCalledWith('custom-output.pdf');
  });

  it('shows the exported PDF in its folder when clicking open folder', async () => {
    const user = userEvent.setup();
    const api = mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 1, pageCount: 3 })
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');
    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：custom-output.pdf');

    await user.click(screen.getByRole('button', { name: '打开所在文件夹' }));

    expect(api.showOutputInFolder).toHaveBeenCalledWith('custom-output.pdf');
  });

  it('keeps the output path visible when opening the exported PDF fails', async () => {
    const user = userEvent.setup();
    mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 1, pageCount: 3 }),
      openOutputPdf: vi.fn().mockRejectedValue(new Error('打开失败'))
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');
    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：custom-output.pdf');

    await user.click(screen.getByRole('button', { name: '打开文件' }));

    await screen.findByText('打开失败');
    expect(screen.getByText('输出文件：custom-output.pdf')).toBeInTheDocument();
  });

  it('keeps the output path visible when showing the exported PDF in its folder fails', async () => {
    const user = userEvent.setup();
    mockApi({
      selectOutputPdf: vi.fn().mockResolvedValue('custom-output.pdf'),
      exportPdf: vi.fn().mockResolvedValue({ outputPath: 'custom-output.pdf', removedCount: 1, pageCount: 3 }),
      showOutputInFolder: vi.fn().mockRejectedValue(new Error('打开文件夹失败'))
    });

    render(<App />);
    await user.click(screen.getByRole('button', { name: '选择 PDF' }));
    await screen.findByText('VolkaEnglish');
    await user.click(screen.getByRole('button', { name: '导出去水印 PDF' }));
    await screen.findByText('输出文件：custom-output.pdf');

    await user.click(screen.getByRole('button', { name: '打开所在文件夹' }));

    await screen.findByText('打开文件夹失败');
    expect(screen.getByText('输出文件：custom-output.pdf')).toBeInTheDocument();
  });
});
