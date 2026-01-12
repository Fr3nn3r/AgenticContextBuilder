import { useState, useRef, useCallback, useEffect } from "react";
import { cn } from "../lib/utils";

interface ImageViewerProps {
  url: string;
  alt?: string;
  className?: string;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 4;
const ZOOM_SENSITIVITY = 0.002;

export function ImageViewer({ url, alt = "Document", className }: ImageViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);

  // Reset state when URL changes
  useEffect(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
    setImageLoaded(false);
  }, [url]);

  // Handle mouse wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();

    const delta = -e.deltaY * ZOOM_SENSITIVITY;
    setScale(prevScale => {
      const newScale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prevScale + delta * prevScale));

      // Reset position if zooming back to 1 or below
      if (newScale <= 1) {
        setPosition({ x: 0, y: 0 });
      }

      return newScale;
    });
  }, []);

  // Handle drag start
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return; // Only allow drag when zoomed

    setIsDragging(true);
    setDragStart({
      x: e.clientX - position.x,
      y: e.clientY - position.y,
    });
  }, [scale, position]);

  // Handle drag move
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;

    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart]);

  // Handle drag end
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Handle double-click to reset
  const handleDoubleClick = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  // Handle mouse leave
  const handleMouseLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const isZoomed = scale > 1;
  const showZoomIndicator = scale !== 1;

  return (
    <div
      ref={containerRef}
      className={cn(
        "h-full w-full overflow-hidden bg-gray-100 relative",
        isZoomed ? "cursor-grab" : "cursor-zoom-in",
        isDragging && "cursor-grabbing",
        className
      )}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onDoubleClick={handleDoubleClick}
    >
      {/* Image container */}
      <div
        className="h-full w-full flex items-center justify-center"
        style={{
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          transformOrigin: "center center",
          transition: isDragging ? "none" : "transform 0.1s ease-out",
        }}
      >
        <img
          src={url}
          alt={alt}
          className="max-w-full max-h-full object-contain shadow-lg select-none"
          draggable={false}
          onLoad={() => setImageLoaded(true)}
        />
      </div>

      {/* Zoom indicator */}
      {showZoomIndicator && imageLoaded && (
        <div className="absolute bottom-4 right-4 bg-black/70 text-white px-3 py-1.5 rounded-full text-sm font-medium">
          {Math.round(scale * 100)}%
        </div>
      )}

      {/* Help text */}
      {imageLoaded && !isZoomed && (
        <div className="absolute bottom-4 left-4 text-gray-500 text-xs">
          Scroll to zoom, double-click to reset
        </div>
      )}
    </div>
  );
}
