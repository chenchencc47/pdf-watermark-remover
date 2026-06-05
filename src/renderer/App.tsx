import { useState } from 'react';
import type { DetectionResult, PreviewResult } from '../shared/types';
import { getDefaultCandidateIds, toggleCandidateId } from './candidateSelection';

type Status = 'idle' | 'detecting' | 'previewing' | 'exporting' | 'done' | 'error';

export default function App() {
  const [pdfPath, setPdfPath] = useState('');
  const [detection, setDetection] = useState<DetectionResult | null>(null);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [message, setMessage] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [previewPageInput, setPreviewPageInput] = useState('');
  const isBusy = status === 'detecting' || status === 'previewing' || status === 'exporting';

  async function handleSelectPdf() {
    if (isBusy) return;
    if (!window.appApi) {
      setStatus('error');
      setMessage('请在 Electron 桌面窗口中使用选择 PDF 功能，不要直接打开浏览器页面。');
      return;
    }

    const path = await window.appApi.selectPdf();
    if (!path) return;
    setPdfPath(path);
    setDetection(null);
    setPreview(null);
    setOutputPath('');
    setSelectedCandidateIds([]);
    setPreviewPageInput('');
    setStatus('detecting');
    setMessage('正在检测水印...');
    try {
      const result = await window.appApi.detectWatermarks(path);
      setDetection(result);
      setSelectedCandidateIds(getDefaultCandidateIds(result.candidates));
      setMessage(result.message);
      setStatus('idle');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handlePreview() {
    if (isBusy || !pdfPath || selectedCandidateIds.length === 0) return;
    setStatus('previewing');
    setMessage('正在生成预览...');
    try {
      const selectedCandidate = detection?.candidates.find((candidate) => selectedCandidateIds.includes(candidate.id));
      const requestedPage = Number(previewPageInput);
      const fallbackPage = selectedCandidate?.pages[0] ?? 1;
      const page = Number.isInteger(requestedPage) && requestedPage > 0
        ? Math.min(requestedPage, detection?.pdf.pageCount ?? requestedPage)
        : fallbackPage;
      const result = await window.appApi.renderPreview(pdfPath, selectedCandidateIds, page);
      setPreview(result);
      setStatus('idle');
      setMessage('预览已生成。');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleExport() {
    if (isBusy || !pdfPath || selectedCandidateIds.length === 0) return;
    setOutputPath('');
    setStatus('exporting');
    setMessage('正在选择输出位置...');
    try {
      const target = await window.appApi.selectOutputPdf(pdfPath);
      if (!target) {
        setStatus('idle');
        setMessage('已取消导出。');
        return;
      }

      setMessage('正在导出去水印 PDF...');
      const result = await window.appApi.exportPdf(pdfPath, selectedCandidateIds, target);
      if (result.removedCount <= 0) {
        throw new Error('未移除任何水印对象。');
      }
      setOutputPath(result.outputPath);
      setStatus('done');
      setMessage(`处理完成，移除对象数量：${result.removedCount}，页数：${result.pageCount}。`);
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleOpenOutputPdf() {
    if (!outputPath) return;
    try {
      await window.appApi.openOutputPdf(outputPath);
      setStatus('done');
      setMessage('已打开输出文件。');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleShowOutputInFolder() {
    if (!outputPath) return;
    try {
      await window.appApi.showOutputInFolder(outputPath);
      setStatus('done');
      setMessage('已打开输出文件所在文件夹。');
    } catch (error) {
      setStatus('error');
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <main className="app-shell">
      <section className="hero-card wide">
        <p className="eyebrow">本地处理 · 不上传云端</p>
        <h1>PDF 去水印工具</h1>
        <p className="summary">选择 PDF，自动检测水印，预览后导出去水印文件。</p>
        <button type="button" onClick={handleSelectPdf} disabled={isBusy}>
          {status === 'detecting' ? '检测中...' : '选择 PDF'}
        </button>

        {pdfPath ? <p className="selected-path">已选择：{pdfPath}</p> : null}
        {message ? <p className={`message ${status === 'error' ? 'error' : ''}`}>{message}</p> : null}

        {detection ? (
          <section className="panel">
            <h2>检测结果</h2>
            <dl className="info-grid">
              <div><dt>页数</dt><dd>{detection.pdf.pageCount}</dd></div>
              <div><dt>可提取文字</dt><dd>{detection.pdf.hasText ? '是' : '否'}</dd></div>
              <div><dt>推荐模式</dt><dd>{detection.recommendedMode}</dd></div>
            </dl>
            <h3>水印候选</h3>
            {detection.candidates.length === 0 ? <p>未检测到可自动删除的水印。</p> : null}
            {detection.candidates.map((candidate) => {
              const isSelected = selectedCandidateIds.includes(candidate.id);
              return (
                <article className={`candidate ${isSelected ? 'selected' : ''}`} key={candidate.id}>
                  <div className="candidate-header">
                    <label className="candidate-title">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          setPreview(null);
                          setSelectedCandidateIds((current) => toggleCandidateId(current, candidate.id));
                        }}
                      />
                      {candidate.label}
                    </label>
                    <span className="candidate-confidence">置信度 {(candidate.confidence * 100).toFixed(1)}%</span>
                  </div>
                  <p>{candidate.reason}</p>
                </article>
              );
            })}
            <div className="preview-controls">
              <label>
                预览页码
                <input
                  type="number"
                  min="1"
                  max={detection.pdf.pageCount}
                  placeholder="自动"
                  value={previewPageInput}
                  onChange={(event) => {
                    setPreview(null);
                    setPreviewPageInput(event.target.value);
                  }}
                />
              </label>
              <span>共 {detection.pdf.pageCount} 页；留空时使用候选所在页。</span>
            </div>
            <div className="actions">
              <button type="button" onClick={handlePreview} disabled={selectedCandidateIds.length === 0 || isBusy}>生成预览</button>
              <button type="button" onClick={handleExport} disabled={selectedCandidateIds.length === 0 || isBusy}>导出去水印 PDF</button>
            </div>
          </section>
        ) : null}

        {preview ? (
          <section className="panel">
            <h2>第 {preview.page} 页预览</h2>
            <div className="preview-grid">
              <figure><figcaption>处理前</figcaption><img src={preview.beforePng} alt="处理前预览" /></figure>
              <figure><figcaption>处理后</figcaption><img src={preview.afterPng} alt="处理后预览" /></figure>
            </div>
          </section>
        ) : null}

        {outputPath ? (
          <section className="panel">
            <p className="selected-path">输出文件：{outputPath}</p>
            <div className="actions">
              <button type="button" onClick={handleOpenOutputPdf}>打开文件</button>
              <button type="button" onClick={handleShowOutputInFolder}>打开所在文件夹</button>
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}
