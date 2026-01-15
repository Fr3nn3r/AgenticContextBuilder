/**
 * BboxOverlay - Canvas overlay for rendering Azure DI bounding boxes on PDF.
 * Supports SmartBoundingBox with source-based styling for table cells.
 */

import { useEffect, useRef } from "react";
import type { BoundingBox, SmartBoundingBox, HighlightSource } from "../types";
import { transformPolygonToPixels } from "../lib/bboxUtils";

// Style configuration by highlight source type
const HIGHLIGHT_STYLES: Record<HighlightSource, { fill: string; stroke: string }> = {
  word: { fill: "rgba(250, 204, 21, 0.5)", stroke: "rgba(250, 150, 0, 1)" },
  line: { fill: "rgba(250, 204, 21, 0.5)", stroke: "rgba(250, 150, 0, 1)" },
  merged: { fill: "rgba(250, 204, 21, 0.5)", stroke: "rgba(250, 150, 0, 1)" },
  cell: { fill: "rgba(167, 243, 208, 0.4)", stroke: "rgba(16, 185, 129, 0.8)" },  // Green for table cells
};

const DEFAULT_STYLE = HIGHLIGHT_STYLES.word;

interface BboxOverlayProps {
  bboxes: (BoundingBox | SmartBoundingBox)[];
  canvasWidth: number;
  canvasHeight: number;
}

/**
 * Check if a bounding box is a SmartBoundingBox with source property.
 */
function isSmartBbox(bbox: BoundingBox | SmartBoundingBox): bbox is SmartBoundingBox {
  return "source" in bbox;
}

export function BboxOverlay({ bboxes, canvasWidth, canvasHeight }: BboxOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size to match PDF canvas (use device pixel ratio for sharpness)
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasWidth * dpr;
    canvas.height = canvasHeight * dpr;
    canvas.style.width = `${canvasWidth}px`;
    canvas.style.height = `${canvasHeight}px`;
    ctx.scale(dpr, dpr);

    // Clear previous drawings
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    if (bboxes.length === 0) return;

    ctx.lineWidth = 2;

    for (const bbox of bboxes) {
      if (!bbox.polygon || bbox.polygon.length !== 8) continue;

      // Get style based on source type (or default for legacy BoundingBox)
      const style = isSmartBbox(bbox)
        ? HIGHLIGHT_STYLES[bbox.source] || DEFAULT_STYLE
        : DEFAULT_STYLE;

      ctx.fillStyle = style.fill;
      ctx.strokeStyle = style.stroke;

      const pixelPolygon = transformPolygonToPixels(
        bbox.polygon,
        bbox.pageWidthInches,
        bbox.pageHeightInches,
        canvasWidth,
        canvasHeight
      );

      // Draw polygon path (4 corners)
      ctx.beginPath();
      ctx.moveTo(pixelPolygon[0], pixelPolygon[1]);
      ctx.lineTo(pixelPolygon[2], pixelPolygon[3]);
      ctx.lineTo(pixelPolygon[4], pixelPolygon[5]);
      ctx.lineTo(pixelPolygon[6], pixelPolygon[7]);
      ctx.closePath();

      ctx.fill();
      ctx.stroke();
    }
  }, [bboxes, canvasWidth, canvasHeight]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        zIndex: 10, // Above text layer (z-index: 2) and annotation layer (z-index: 3)
        pointerEvents: "none", // Allow clicks to pass through to PDF
      }}
    />
  );
}
