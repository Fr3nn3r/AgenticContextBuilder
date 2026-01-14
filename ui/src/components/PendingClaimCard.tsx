/**
 * Card component for a pending claim with document list.
 *
 * Features:
 * - Claim ID display with status
 * - Document list with remove buttons
 * - Drag handle for reordering (future)
 * - Error state display
 */

import { cn } from '../lib/utils';
import type { PendingDocument } from '../types';
import { DocumentUploader } from './DocumentUploader';

export interface PendingClaimCardProps {
  claimId: string;
  documents: PendingDocument[];
  onUpload: (claimId: string, files: File[]) => Promise<void>;
  onRemoveDocument: (claimId: string, docId: string) => void;
  onRemoveClaim: (claimId: string) => void;
  uploading?: boolean;
  uploadProgress?: number;
  error?: string;
}

export function PendingClaimCard({
  claimId,
  documents,
  onUpload,
  onRemoveDocument,
  onRemoveClaim,
  uploading = false,
  uploadProgress = 0,
  error,
}: PendingClaimCardProps) {
  const handleUpload = async (files: File[]) => {
    await onUpload(claimId, files);
  };

  return (
    <div className={cn(
      'border rounded-lg overflow-hidden bg-card',
      error ? 'border-red-300 dark:border-red-800' : 'border-border'
    )}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-muted border-b border-border">
        <div className="flex items-center gap-2">
          <FolderIcon className="w-5 h-5 text-muted-foreground" />
          <span className="font-medium text-foreground">{claimId}</span>
          <span className="text-sm text-muted-foreground">
            ({documents.length} {documents.length === 1 ? 'document' : 'documents'})
          </span>
        </div>
        <button
          onClick={() => onRemoveClaim(claimId)}
          className="p-1.5 text-muted-foreground hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
          title="Remove claim"
        >
          <TrashIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="px-4 py-2 bg-red-50 dark:bg-red-900/20 text-sm text-red-700 dark:text-red-400 border-b border-red-200 dark:border-red-800">
          {error}
        </div>
      )}

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Document List */}
        {documents.length > 0 && (
          <div className="space-y-2">
            {documents.map((doc) => (
              <DocumentRow
                key={doc.doc_id}
                document={doc}
                onRemove={() => onRemoveDocument(claimId, doc.doc_id)}
              />
            ))}
          </div>
        )}

        {/* Upload Zone */}
        <DocumentUploader
          onUpload={handleUpload}
          uploading={uploading}
          uploadProgress={uploadProgress}
        />
      </div>
    </div>
  );
}

interface DocumentRowProps {
  document: PendingDocument;
  onRemove: () => void;
}

function DocumentRow({ document, onRemove }: DocumentRowProps) {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (contentType: string) => {
    if (contentType === 'application/pdf') {
      return <PdfIcon className="w-4 h-4 text-red-500 dark:text-red-400" />;
    }
    if (contentType.startsWith('image/')) {
      return <ImageIcon className="w-4 h-4 text-green-500 dark:text-green-400" />;
    }
    return <FileIcon className="w-4 h-4 text-muted-foreground" />;
  };

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-muted rounded-lg group">
      {getFileIcon(document.content_type)}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate">
          {document.original_filename}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatFileSize(document.file_size)}
        </p>
      </div>
      <button
        onClick={onRemove}
        className="p-1 text-muted-foreground hover:text-red-500 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Remove document"
      >
        <XIcon className="w-4 h-4" />
      </button>
    </div>
  );
}

// Icons

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
      />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  );
}

function PdfIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function ImageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
        clipRule="evenodd"
      />
    </svg>
  );
}
