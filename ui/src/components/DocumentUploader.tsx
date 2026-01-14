/**
 * Drag-and-drop document upload zone with validation feedback.
 *
 * Features:
 * - Drag-drop and click-to-browse
 * - File type validation (PDF, PNG, JPG, TXT)
 * - Size limit (100MB)
 * - Upload progress display
 */

import { useCallback, useRef, useState } from 'react';
import { cn } from '../lib/utils';

const ALLOWED_TYPES = [
  'application/pdf',
  'image/png',
  'image/jpeg',
  'text/plain',
];

const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.txt'];
const MAX_SIZE_BYTES = 100 * 1024 * 1024; // 100MB

export interface DocumentUploaderProps {
  onUpload: (files: File[]) => Promise<void>;
  disabled?: boolean;
  uploading?: boolean;
  uploadProgress?: number;
}

interface ValidationError {
  filename: string;
  error: string;
}

export function DocumentUploader({
  onUpload,
  disabled = false,
  uploading = false,
  uploadProgress = 0,
}: DocumentUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFiles = useCallback((files: FileList | File[]): { valid: File[]; errors: ValidationError[] } => {
    const valid: File[] = [];
    const errors: ValidationError[] = [];

    Array.from(files).forEach((file) => {
      // Check file type
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.includes(ext)) {
        errors.push({
          filename: file.name,
          error: `Invalid type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`,
        });
        return;
      }

      // Check file size
      if (file.size > MAX_SIZE_BYTES) {
        errors.push({
          filename: file.name,
          error: `File too large. Max: 100MB`,
        });
        return;
      }

      valid.push(file);
    });

    return { valid, errors };
  }, []);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      setErrors([]);

      const { valid, errors } = validateFiles(files);
      if (errors.length > 0) {
        setErrors(errors);
      }

      if (valid.length > 0) {
        await onUpload(valid);
      }
    },
    [onUpload, validateFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled || uploading) return;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleFiles(files);
      }
    },
    [disabled, uploading, handleFiles]
  );

  const handleClick = useCallback(() => {
    if (!disabled && !uploading) {
      fileInputRef.current?.click();
    }
  }, [disabled, uploading]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        handleFiles(files);
      }
      // Reset input to allow selecting same file again
      e.target.value = '';
    },
    [handleFiles]
  );

  return (
    <div className="space-y-2">
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
          isDragging && 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20',
          !isDragging && !disabled && 'border-border hover:border-muted-foreground',
          disabled && 'border-muted bg-muted cursor-not-allowed',
          uploading && 'cursor-wait'
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled || uploading}
        />

        {uploading ? (
          <div className="space-y-3">
            <UploadIcon className="w-10 h-10 mx-auto text-blue-500 dark:text-blue-400 animate-pulse" />
            <p className="text-sm text-muted-foreground">Uploading...</p>
            <div className="w-48 mx-auto bg-muted rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{Math.round(uploadProgress)}%</p>
          </div>
        ) : (
          <div className="space-y-2">
            <UploadIcon className={cn(
              'w-10 h-10 mx-auto',
              isDragging ? 'text-blue-500 dark:text-blue-400' : 'text-muted-foreground'
            )} />
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-primary">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-muted-foreground">
              PDF, PNG, JPG, or TXT (max 100MB)
            </p>
          </div>
        )}
      </div>

      {/* Validation Errors */}
      {errors.length > 0 && (
        <div className="space-y-1">
          {errors.map((err, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded"
            >
              <ErrorIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-medium">{err.filename}:</span> {err.error}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
      />
    </svg>
  );
}

function ErrorIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}
