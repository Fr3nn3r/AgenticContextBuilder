import { cn } from "../../lib/utils";

interface ExtractorBadgeProps {
  hasPdf?: boolean;
  hasImage?: boolean;
}

/**
 * Shows a badge indicating the extraction method used for the document.
 * - Azure DI: PDF documents processed with Azure Document Intelligence
 * - Vision: Image documents processed with vision models
 * - Text: Plain text documents
 */
export function ExtractorBadge({ hasPdf, hasImage }: ExtractorBadgeProps) {
  // Determine extractor type from flags
  const extractorType = hasPdf ? "pdf" : hasImage ? "image" : "text";

  const config = {
    pdf: {
      label: "Azure DI",
      color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    },
    image: {
      label: "Vision",
      color: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
    },
    text: {
      label: "Text",
      color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    },
  };

  const { label, color } = config[extractorType];

  return (
    <span className={cn("px-1.5 py-0.5 text-[10px] font-medium rounded", color)}>
      {label}
    </span>
  );
}
