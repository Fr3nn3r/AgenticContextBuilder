/**
 * Bounding box utilities for Azure DI word polygon highlighting.
 *
 * Smart Highlighting Hierarchy:
 * 1. Table cells (highest priority for tabular data)
 * 2. Lines (when evidence matches 80%+ of line span)
 * 3. Merged words (adjacent words on same line)
 * 4. Individual words (fallback)
 */

import type {
  AzureDIOutput,
  AzureDIOutputExtended,
  AzureDIWord,
  AzureDILine,
  AzureDITableCell,
  BoundingBox,
  SmartBoundingBox,
  SmartHighlightOptions,
  HighlightSource,
} from "../types";

// =============================================================================
// CONSTANTS
// =============================================================================

const DEFAULT_LINE_COVERAGE_THRESHOLD = 0.80;
const DEFAULT_WORD_GAP_THRESHOLD = 0.3;  // inches
const DEFAULT_LINE_Y_THRESHOLD = 0.05;   // inches

// =============================================================================
// HELPER TYPES
// =============================================================================

interface WordGroup {
  words: AzureDIWord[];
  avgY: number;
}

interface MergeResult {
  polygon: number[];
  avgConfidence: number;
  wordCount: number;
}

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

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Check if two spans overlap.
 * Span A overlaps with Span B if: A.start < B.end AND A.end > B.start
 */
function spanOverlaps(
  aStart: number,
  aEnd: number,
  bStart: number,
  bEnd: number
): boolean {
  return aStart < bEnd && aEnd > bStart;
}

/**
 * Get the bounding rectangle from an 8-element polygon.
 * Returns { minX, minY, maxX, maxY }
 */
function getPolygonBounds(polygon: number[]): {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
} {
  const xs = [polygon[0], polygon[2], polygon[4], polygon[6]];
  const ys = [polygon[1], polygon[3], polygon[5], polygon[7]];
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

/**
 * Get the average Y coordinate of a polygon (center Y).
 */
function getPolygonCenterY(polygon: number[]): number {
  return (polygon[1] + polygon[3] + polygon[5] + polygon[7]) / 4;
}

/**
 * Get the rightmost X coordinate of a polygon.
 */
function getPolygonRightX(polygon: number[]): number {
  return Math.max(polygon[0], polygon[2], polygon[4], polygon[6]);
}

/**
 * Get the leftmost X coordinate of a polygon.
 */
function getPolygonLeftX(polygon: number[]): number {
  return Math.min(polygon[0], polygon[2], polygon[4], polygon[6]);
}

// =============================================================================
// TABLE CELL DETECTION
// =============================================================================

/**
 * Find table cells that contain the given character range.
 * Returns cells whose spans overlap with [charStart, charEnd).
 */
export function findTableCellsInRange(
  azureDI: AzureDIOutputExtended,
  pageNumber: number,
  charStart: number,
  charEnd: number
): { cells: AzureDITableCell[]; tableIndex: number }[] {
  const tables = azureDI.raw_azure_di_output?.tables;
  if (!tables || tables.length === 0) return [];

  const results: { cells: AzureDITableCell[]; tableIndex: number }[] = [];

  tables.forEach((table, tableIndex) => {
    const matchingCells = table.cells.filter((cell) => {
      // Check if cell is on the target page
      const onPage = cell.boundingRegions?.some(
        (br) => br.pageNumber === pageNumber
      );
      if (!onPage) return false;

      // Check if any cell span overlaps with char range
      return cell.spans?.some((span) =>
        spanOverlaps(span.offset, span.offset + span.length, charStart, charEnd)
      );
    });

    if (matchingCells.length > 0) {
      results.push({ cells: matchingCells, tableIndex });
    }
  });

  return results;
}

/**
 * Check if table cells fully contain the character range.
 */
export function cellsContainRange(
  cellResults: { cells: AzureDITableCell[]; tableIndex: number }[],
  charStart: number,
  charEnd: number
): boolean {
  if (cellResults.length === 0) return false;

  // Collect all spans from all cells
  const allSpans: { start: number; end: number }[] = [];
  for (const { cells } of cellResults) {
    for (const cell of cells) {
      for (const span of cell.spans || []) {
        allSpans.push({ start: span.offset, end: span.offset + span.length });
      }
    }
  }

  // Sort spans by start position
  allSpans.sort((a, b) => a.start - b.start);

  // Check if spans fully cover the range
  let covered = charStart;
  for (const span of allSpans) {
    if (span.start > covered) {
      // Gap in coverage
      return false;
    }
    covered = Math.max(covered, span.end);
    if (covered >= charEnd) {
      return true;
    }
  }

  return covered >= charEnd;
}

// =============================================================================
// LINE-LEVEL DETECTION
// =============================================================================

/**
 * Find lines on a page that overlap with the character range.
 */
export function findLinesInRange(
  azureDI: AzureDIOutputExtended,
  pageNumber: number,
  charStart: number,
  charEnd: number
): { lines: AzureDILine[]; pageWidth: number; pageHeight: number } | null {
  const pages = azureDI.raw_azure_di_output?.pages;
  if (!pages) return null;

  const page = pages.find((p) => p.pageNumber === pageNumber);
  if (!page || !page.lines || page.lines.length === 0) return null;

  const matchingLines = page.lines.filter((line) => {
    return line.spans?.some((span) =>
      spanOverlaps(span.offset, span.offset + span.length, charStart, charEnd)
    );
  });

  if (matchingLines.length === 0) return null;

  return {
    lines: matchingLines,
    pageWidth: page.width,
    pageHeight: page.height,
  };
}

/**
 * Calculate what percentage of the char range is covered by the given lines.
 * Returns a value between 0 and 1.
 */
export function calculateLineCoverage(
  lines: AzureDILine[],
  charStart: number,
  charEnd: number
): number {
  if (lines.length === 0 || charEnd <= charStart) return 0;

  const rangeLength = charEnd - charStart;

  // Collect all spans
  const allSpans: { start: number; end: number }[] = [];
  for (const line of lines) {
    for (const span of line.spans || []) {
      allSpans.push({ start: span.offset, end: span.offset + span.length });
    }
  }

  // Sort and merge overlapping spans
  allSpans.sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number }[] = [];
  for (const span of allSpans) {
    if (merged.length === 0 || span.start > merged[merged.length - 1].end) {
      merged.push({ ...span });
    } else {
      merged[merged.length - 1].end = Math.max(
        merged[merged.length - 1].end,
        span.end
      );
    }
  }

  // Calculate coverage within the target range
  let coveredLength = 0;
  for (const span of merged) {
    const overlapStart = Math.max(span.start, charStart);
    const overlapEnd = Math.min(span.end, charEnd);
    if (overlapEnd > overlapStart) {
      coveredLength += overlapEnd - overlapStart;
    }
  }

  return coveredLength / rangeLength;
}

// =============================================================================
// WORD GROUPING & MERGING
// =============================================================================

/**
 * Group words by their Y-coordinate (vertical position on page).
 * Words within a threshold distance are considered on the same line.
 */
export function groupWordsByLine(
  words: AzureDIWord[],
  yThreshold: number = DEFAULT_LINE_Y_THRESHOLD
): WordGroup[] {
  if (words.length === 0) return [];

  // Sort words by their center Y coordinate
  const sorted = [...words].sort((a, b) => {
    const aY = getPolygonCenterY(a.polygon);
    const bY = getPolygonCenterY(b.polygon);
    return aY - bY;
  });

  const groups: WordGroup[] = [];
  let currentGroup: AzureDIWord[] = [sorted[0]];
  let currentAvgY = getPolygonCenterY(sorted[0].polygon);

  for (let i = 1; i < sorted.length; i++) {
    const word = sorted[i];
    const wordY = getPolygonCenterY(word.polygon);

    if (Math.abs(wordY - currentAvgY) <= yThreshold) {
      // Same line
      currentGroup.push(word);
      // Update average Y
      currentAvgY =
        currentGroup.reduce((sum, w) => sum + getPolygonCenterY(w.polygon), 0) /
        currentGroup.length;
    } else {
      // New line
      groups.push({ words: currentGroup, avgY: currentAvgY });
      currentGroup = [word];
      currentAvgY = wordY;
    }
  }

  // Don't forget the last group
  if (currentGroup.length > 0) {
    groups.push({ words: currentGroup, avgY: currentAvgY });
  }

  return groups;
}

/**
 * Merge consecutive word polygons into unified bounding rectangles.
 * Words must be sorted by X position and on the same line.
 */
export function mergeConsecutiveWords(
  words: AzureDIWord[],
  gapThreshold: number = DEFAULT_WORD_GAP_THRESHOLD
): MergeResult[] {
  if (words.length === 0) return [];
  if (words.length === 1) {
    return [
      {
        polygon: words[0].polygon,
        avgConfidence: words[0].confidence,
        wordCount: 1,
      },
    ];
  }

  // Sort by leftmost X coordinate
  const sorted = [...words].sort(
    (a, b) => getPolygonLeftX(a.polygon) - getPolygonLeftX(b.polygon)
  );

  const results: MergeResult[] = [];
  let currentMerge: AzureDIWord[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i++) {
    const prevWord = currentMerge[currentMerge.length - 1];
    const currWord = sorted[i];

    const prevRightX = getPolygonRightX(prevWord.polygon);
    const currLeftX = getPolygonLeftX(currWord.polygon);
    const gap = currLeftX - prevRightX;

    if (gap <= gapThreshold) {
      // Adjacent, add to current merge
      currentMerge.push(currWord);
    } else {
      // Gap too large, finalize current merge
      results.push(createMergeResult(currentMerge));
      currentMerge = [currWord];
    }
  }

  // Finalize last merge
  if (currentMerge.length > 0) {
    results.push(createMergeResult(currentMerge));
  }

  return results;
}

/**
 * Create a MergeResult from a list of words.
 */
function createMergeResult(words: AzureDIWord[]): MergeResult {
  const polygon = mergePolygons(words.map((w) => w.polygon));
  const avgConfidence =
    words.reduce((sum, w) => sum + w.confidence, 0) / words.length;
  return { polygon, avgConfidence, wordCount: words.length };
}

/**
 * Merge multiple polygons into a single bounding rectangle.
 * Takes the min/max of all coordinates to form an enclosing box.
 */
export function mergePolygons(polygons: number[][]): number[] {
  if (polygons.length === 0) return [];
  if (polygons.length === 1) return polygons[0];

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const polygon of polygons) {
    const bounds = getPolygonBounds(polygon);
    minX = Math.min(minX, bounds.minX);
    minY = Math.min(minY, bounds.minY);
    maxX = Math.max(maxX, bounds.maxX);
    maxY = Math.max(maxY, bounds.maxY);
  }

  // Return as 8-element polygon (rectangle): top-left, top-right, bottom-right, bottom-left
  return [minX, minY, maxX, minY, maxX, maxY, minX, maxY];
}

// =============================================================================
// MAIN ENTRY POINT
// =============================================================================

/**
 * Compute smart bounding boxes for evidence highlighting.
 * Uses hierarchy: table cells > lines > merged words > individual words.
 */
export function computeSmartBoundingBoxes(
  azureDI: AzureDIOutputExtended,
  pageNumber: number,
  charStart: number,
  charEnd: number,
  options?: SmartHighlightOptions
): SmartBoundingBox[] {
  const opts = {
    lineCoverageThreshold:
      options?.lineCoverageThreshold ?? DEFAULT_LINE_COVERAGE_THRESHOLD,
    wordGapThreshold: options?.wordGapThreshold ?? DEFAULT_WORD_GAP_THRESHOLD,
    lineYThreshold: options?.lineYThreshold ?? DEFAULT_LINE_Y_THRESHOLD,
    enableTableDetection: options?.enableTableDetection ?? true,
    enableLinePreference: options?.enableLinePreference ?? true,
  };

  // Early exit for invalid range
  if (charEnd <= charStart) return [];

  // Get page dimensions (needed for all bounding boxes)
  const pages = azureDI.raw_azure_di_output?.pages;
  const page = pages?.find((p) => p.pageNumber === pageNumber);
  if (!page) return [];

  const pageWidth = page.width;
  const pageHeight = page.height;

  // Step 1: Try table cell detection
  if (opts.enableTableDetection) {
    const cellResults = findTableCellsInRange(
      azureDI,
      pageNumber,
      charStart,
      charEnd
    );

    if (
      cellResults.length > 0 &&
      cellsContainRange(cellResults, charStart, charEnd)
    ) {
      // Use cell polygons
      const boxes: SmartBoundingBox[] = [];
      for (const { cells, tableIndex } of cellResults) {
        for (const cell of cells) {
          for (const br of cell.boundingRegions || []) {
            if (br.pageNumber === pageNumber && br.polygon) {
              boxes.push({
                pageNumber,
                polygon: br.polygon,
                pageWidthInches: pageWidth,
                pageHeightInches: pageHeight,
                source: "cell" as HighlightSource,
                cellRef: {
                  tableIndex,
                  rowIndex: cell.rowIndex,
                  columnIndex: cell.columnIndex,
                },
              });
            }
          }
        }
      }
      if (boxes.length > 0) return boxes;
    }
  }

  // Step 2: Try line-level detection
  if (opts.enableLinePreference) {
    const lineResult = findLinesInRange(azureDI, pageNumber, charStart, charEnd);

    if (lineResult && lineResult.lines.length > 0) {
      const coverage = calculateLineCoverage(
        lineResult.lines,
        charStart,
        charEnd
      );

      if (coverage >= opts.lineCoverageThreshold) {
        // Use line polygons
        return lineResult.lines.map((line) => ({
          pageNumber,
          polygon: line.polygon,
          pageWidthInches: pageWidth,
          pageHeightInches: pageHeight,
          source: "line" as HighlightSource,
        }));
      }
    }
  }

  // Step 3: Get words and try merging
  const wordResult = findWordsInRange(azureDI, pageNumber, charStart, charEnd);

  if (!wordResult || wordResult.words.length === 0) {
    return [];
  }

  // Group words by line
  const groups = groupWordsByLine(wordResult.words, opts.lineYThreshold);

  // Merge each group and collect results
  const boxes: SmartBoundingBox[] = [];

  for (const group of groups) {
    const mergeResults = mergeConsecutiveWords(group.words, opts.wordGapThreshold);

    for (const result of mergeResults) {
      boxes.push({
        pageNumber,
        polygon: result.polygon,
        pageWidthInches: pageWidth,
        pageHeightInches: pageHeight,
        source: result.wordCount > 1 ? "merged" : "word",
        confidence: result.avgConfidence,
      });
    }
  }

  return boxes;
}
