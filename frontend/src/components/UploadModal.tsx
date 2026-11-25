import React, { useState, useRef, useEffect } from 'react';
import { X, UploadCloud, File, AlertCircle, Loader2, Cpu, Scan, Check } from 'lucide-react';
import { api } from '../api';
import { StatementItem } from '../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (statement: StatementItem) => void;
  initialOcrEngine?: string;
  initialModel?: string;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  initialOcrEngine = 'hybrid_indra',
  initialModel = 'qwen2.5:1.5b',
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [durationMonths, setDurationMonths] = useState<number | undefined>(undefined);
  const [ocrEngine, setOcrEngine] = useState<string>(initialOcrEngine);
  const [modelName, setModelName] = useState<string>(initialModel);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      api.getEngineSettings().then((settings) => {
        if (settings.ocr_engine) setOcrEngine(settings.ocr_engine);
        if (settings.local_llm_model) setModelName(settings.local_llm_model);
      }).catch(() => null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type !== 'application/pdf') {
        setError('Only PDF bank statements are supported.');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.type !== 'application/pdf') {
        setError('Only PDF bank statements are supported.');
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a PDF bank statement file.');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      // Sync user-chosen OCR engine & model
      await api.updateEngineSettings({
        ocr_engine: ocrEngine,
        local_llm_model: modelName,
      }).catch(() => null);

      const statement = await api.uploadStatement(selectedFile, durationMonths);
      onUploadSuccess(statement);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to upload statement');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#141414]/95 border border-white/[0.1] rounded-3xl w-full max-w-lg shadow-[0_20px_50px_rgba(0,0,0,0.6)] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Upload Bank Statement</h3>
            <p className="text-xs text-text-muted">3-month or 6-month PDF bank statement for salary detection</p>
          </div>
          <button
            onClick={onClose}
            disabled={uploading}
            className="h-8 w-8 rounded-full bg-white/[0.04] hover:bg-white/[0.08] text-text-muted hover:text-white flex items-center justify-center border border-white/[0.08] transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* Dropzone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 ${
              dragActive
                ? 'border-[#F15A43] bg-[#F15A43]/10 shadow-[0_0_20px_rgba(241,90,67,0.2)]'
                : selectedFile
                ? 'border-emerald-500/40 bg-emerald-500/5'
                : 'border-white/[0.1] hover:border-white/20 bg-white/[0.02]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-2">
                <div className="h-12 w-12 rounded-2xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/25">
                  <File className="h-6 w-6" />
                </div>
                <div className="text-sm font-semibold text-white">{selectedFile.name}</div>
                <div className="text-xs text-text-muted">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                </div>
                <span className="text-xs text-[#F15A43] underline mt-1">Change file</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <div className="h-12 w-12 rounded-2xl bg-[#F15A43]/15 text-[#F15A43] flex items-center justify-center border border-[#F15A43]/20 shadow-glow-accent">
                  <UploadCloud className="h-6 w-6" />
                </div>
                <div className="text-sm font-semibold text-white mt-1">
                  Drag and drop bank statement PDF
                </div>
                <div className="text-xs text-text-muted">
                  Standard digital PDFs or scanned bank statements up to 50MB
                </div>
                <span className="mt-2 inline-block px-4 py-1.5 rounded-full bg-white/[0.05] hover:bg-white/[0.08] text-xs text-text-secondary font-medium border border-white/[0.08]">
                  Browse Files
                </span>
              </div>
            )}
          </div>

          {/* Statement Expected Duration */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Statement Duration Hint (Optional)
            </label>
            <select
              value={durationMonths || ''}
              onChange={(e) => setDurationMonths(e.target.value ? Number(e.target.value) : undefined)}
              className="w-full px-4 py-2.5 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 focus:shadow-[0_0_15px_rgba(241,90,67,0.15)] transition"
            >
              <option value="">Auto-detect date range</option>
              <option value="3">3 Months (Quarterly Verification)</option>
              <option value="6">6 Months (Half-Year Verification)</option>
            </select>
          </div>

          {/* Engine & Model Selection (Quick Controls) */}
          <div className="p-3.5 rounded-2xl bg-white/[0.025] border border-white/[0.07] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-[#F15A43]" />
                Extraction Engine & Local Model
              </span>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-[10px] font-bold border border-emerald-500/20">
                Indra OCR Active
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-[11px] text-text-muted mb-1 flex items-center gap-1">
                  <Scan className="h-3 w-3 text-[#F15A43]" />
                  <span>OCR Engine</span>
                </label>
                <select
                  value={ocrEngine}
                  onChange={(e) => setOcrEngine(e.target.value)}
                  className="w-full px-3 py-2 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                >
                  <option value="hybrid_indra">Indra OCR (Hybrid Primary)</option>
                  <option value="indra">Indra OCR (Full Document)</option>
                  <option value="native">PyMuPDF Native Text Only</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-text-muted mb-1 flex items-center gap-1">
                  <Cpu className="h-3 w-3 text-[#8B7CFF]" />
                  <span>Inference Model</span>
                </label>
                <select
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  className="w-full px-3 py-2 bg-[#161616] border border-white/[0.08] rounded-xl text-xs text-text-primary focus:outline-none focus:border-[#F15A43]/50 transition"
                >
                  <option value="qwen2.5:1.5b">Qwen 2.5 1.5B (Fast, ₹0.00)</option>
                  <option value="qwen3.5-9b-uncensored:latest">Qwen 3.5 9B (External SSD)</option>
                  <option value="llama3.2:3b">Llama 3.2 3B (Balanced)</option>
                  <option value="gemma4:12b">Gemma 4 12B (Extended)</option>
                  <option value="google/gemma-4-31b-it:free">Cloud Free (OpenRouter)</option>
                </select>
              </div>
            </div>
            <div className="text-[10px] text-text-muted">
              Indra OCR runs fast native PDF parsing with CPU-native ONNX OCR fallback for scanned pages.
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={uploading}
              className="px-5 py-2.5 rounded-full text-xs font-medium text-text-secondary hover:text-white hover:bg-white/[0.04] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!selectedFile || uploading}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-[#F15A43] to-[#e04832] disabled:opacity-40 disabled:cursor-not-allowed text-xs font-semibold text-white shadow-glow-accent transition active:scale-95"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <span>Analyze Statement</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
