/**
 * Bounding box utilities for Azure DI word polygon highlighting.
 */

import type { AzureDIOutput, AzureDIWord, BoundingBox } from "../types";

/**
 * Find words that overlap with the character range [charStart, charEnd).
 * Azure DI word spans use: span.offset and span.length
 * A word overlaps if: word_start < charEnd AND word_end > charStart
 */
export function findWordsInRange(
  azureDI: AzureDIOutput,
  pageNumber: number,
  charStart: number,
  charEnd: number
): { words: AzureDIWord[]; pageWidth: number; pageHeight: number } | null {
  const pages = azureDI.raw_azure_di_output?.pages;
  if (!pages) return null;

  const page = pages.find((p) => p.pageNumber === pageNumber);
  if (!page || !page.words) return null;

  const matchingWords = page.words.filter((word) => {
    const wordStart = word.span.offset;
    const wordEnd = word.span.offset + word.span.length;
    // Overlap condition
    return wordStart < charEnd && wordEnd > charStart;
  });

  return {
    words: matchingWords,
    pageWidth: page.width,
    pageHeight: page.height,
  };
}

/**
 * Convert word matches to bounding boxes.
 */
export function computeBoundingBoxes(
  azureDI: AzureDIOutput,
  pageNumber: number,
  charStart: number,
  charEnd: number
): BoundingBox[] {
  const result = findWordsInRange(azureDI, pageNumber, charStart, charEnd);

  if (!result || result.words.length === 0) {
    return [];
  }

  return result.words.map((word) => ({
    pageNumber,
    polygon: word.polygon,
    pageWidthInches: result.pageWidth,
    pageHeightInches: result.pageHeight,
  }));
}

/**
 * Transform polygon from inches to screen pixels.
 *
 * Azure DI polygons are 8-element arrays: [x1,y1, x2,y2, x3,y3, x4,y4]
 * representing 4 corners of a quadrilateral, in inches.
 *
 * @param polygon - 8-element array in inches
 * @param pageWidthInches - page width from Azure DI
 * @param pageHeightInches - page height from Azure DI
 * @param canvasWidth - actual rendered canvas width in pixels
 * @param canvasHeight - actual rendered canvas height in pixels
 */
export function transformPolygonToPixels(
  polygon: number[],
  pageWidthInches: number,
  pageHeightInches: number,
  canvasWidth: number,
  canvasHeight: number
): number[] {
  const scaleX = canvasWidth / pageWidthInches;
  const scaleY = canvasHeight / pageHeightInches;

  // Transform each coordinate
  return polygon.map((coord, i) => {
    if (i % 2 === 0) {
      // X coordinate
      return coord * scaleX;
    } else {
      // Y coordinate
      return coord * scaleY;
    }
  });
}
