import { describe, it, expect } from "vitest";
import {
  findWordsInRange,
  computeBoundingBoxes,
  transformPolygonToPixels,
  findTableCellsInRange,
  cellsContainRange,
  findLinesInRange,
  calculateLineCoverage,
  groupWordsByLine,
  mergeConsecutiveWords,
  mergePolygons,
  computeSmartBoundingBoxes,
} from "../bboxUtils";
import type {
  AzureDIOutput,
  AzureDIOutputExtended,
  AzureDIWord,
  AzureDILine,
  AzureDITable,
  AzureDITableCell,
} from "../../types";

// ============================================================================
// Test Fixtures
// ============================================================================

function makeWord(
  content: string,
  offset: number,
  length: number,
  polygon: number[] = [0, 0, 1, 0, 1, 1, 0, 1]
): AzureDIWord {
  return {
    content,
    polygon,
    confidence: 0.99,
    span: { offset, length },
  };
}

function makeAzureDI(
  pages: Array<{
    pageNumber: number;
    width: number;
    height: number;
    words: AzureDIWord[];
  }>
): AzureDIOutput {
  return {
    raw_azure_di_output: {
      pages: pages.map((p) => ({
        pageNumber: p.pageNumber,
        width: p.width,
        height: p.height,
        unit: "inch",
        words: p.words,
      })),
      content: "",
    },
  };
}

// ============================================================================
// findWordsInRange
// ============================================================================

describe("findWordsInRange", () => {
  it("returns null when raw_azure_di_output is missing", () => {
    const azureDI = {} as AzureDIOutput;
    expect(findWordsInRange(azureDI, 1, 0, 10)).toBeNull();
  });

  it("returns null when pages array is missing", () => {
    const azureDI = {
      raw_azure_di_output: {},
    } as unknown as AzureDIOutput;
    expect(findWordsInRange(azureDI, 1, 0, 10)).toBeNull();
  });

  it("returns null when target page not found", () => {
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [] },
    ]);
    expect(findWordsInRange(azureDI, 2, 0, 10)).toBeNull();
  });

  it("returns empty words array when no words on page", () => {
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [] },
    ]);
    const result = findWordsInRange(azureDI, 1, 0, 10);
    expect(result).not.toBeNull();
    expect(result!.words).toEqual([]);
    expect(result!.pageWidth).toBe(8.5);
    expect(result!.pageHeight).toBe(11);
  });

  it("finds words that fully overlap character range", () => {
    // Word at offset 5, length 5 -> chars 5-10
    // Range is 5-10, so word is fully contained
    const word = makeWord("hello", 5, 5);
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [word] },
    ]);

    const result = findWordsInRange(azureDI, 1, 5, 10);
    expect(result).not.toBeNull();
    expect(result!.words).toHaveLength(1);
    expect(result!.words[0].content).toBe("hello");
  });

  it("finds words that partially overlap (word starts before range)", () => {
    // Word at offset 3, length 5 -> chars 3-8
    // Range is 5-10
    // Overlap: word starts at 3 < 10 AND word ends at 8 > 5 -> overlaps
    const word = makeWord("world", 3, 5);
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [word] },
    ]);

    const result = findWordsInRange(azureDI, 1, 5, 10);
    expect(result).not.toBeNull();
    expect(result!.words).toHaveLength(1);
    expect(result!.words[0].content).toBe("world");
  });

  it("finds words that partially overlap (word starts in range, ends after)", () => {
    // Word at offset 8, length 5 -> chars 8-13
    // Range is 5-10
    // Overlap: word starts at 8 < 10 AND word ends at 13 > 5 -> overlaps
    const word = makeWord("test", 8, 5);
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [word] },
    ]);

    const result = findWordsInRange(azureDI, 1, 5, 10);
    expect(result).not.toBeNull();
    expect(result!.words).toHaveLength(1);
    expect(result!.words[0].content).toBe("test");
  });

  it("excludes words that do not overlap", () => {
    // Word at offset 15, length 5 -> chars 15-20
    // Range is 5-10
    // No overlap: word starts at 15 >= 10
    const word = makeWord("outside", 15, 5);
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [word] },
    ]);

    const result = findWordsInRange(azureDI, 1, 5, 10);
    expect(result).not.toBeNull();
    expect(result!.words).toHaveLength(0);
  });

  it("returns pageWidth and pageHeight from matched page", () => {
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [] },
      { pageNumber: 2, width: 11, height: 17, words: [] },
    ]);

    const result1 = findWordsInRange(azureDI, 1, 0, 10);
    expect(result1!.pageWidth).toBe(8.5);
    expect(result1!.pageHeight).toBe(11);

    const result2 = findWordsInRange(azureDI, 2, 0, 10);
    expect(result2!.pageWidth).toBe(11);
    expect(result2!.pageHeight).toBe(17);
  });

  it("finds multiple overlapping words", () => {
    const words = [
      makeWord("hello", 0, 5),   // chars 0-5
      makeWord("world", 6, 5),   // chars 6-11
      makeWord("test", 12, 4),   // chars 12-16
    ];
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words },
    ]);

    // Range 0-12 should include "hello" and "world" but not "test"
    const result = findWordsInRange(azureDI, 1, 0, 12);
    expect(result!.words).toHaveLength(2);
    expect(result!.words.map((w) => w.content)).toEqual(["hello", "world"]);
  });
});

// ============================================================================
// computeBoundingBoxes
// ============================================================================

describe("computeBoundingBoxes", () => {
  it("returns empty array when no words in range", () => {
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [] },
    ]);

    const result = computeBoundingBoxes(azureDI, 1, 0, 10);
    expect(result).toEqual([]);
  });

  it("returns empty array when page not found", () => {
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [] },
    ]);

    const result = computeBoundingBoxes(azureDI, 2, 0, 10);
    expect(result).toEqual([]);
  });

  it("returns BoundingBox array with polygon and dimensions", () => {
    const polygon = [1, 2, 3, 2, 3, 4, 1, 4];
    const word = makeWord("hello", 5, 5, polygon);
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words: [word] },
    ]);

    const result = computeBoundingBoxes(azureDI, 1, 5, 10);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      pageNumber: 1,
      polygon,
      pageWidthInches: 8.5,
      pageHeightInches: 11,
    });
  });

  it("sets correct pageNumber on each bounding box", () => {
    const word = makeWord("test", 0, 4);
    const azureDI = makeAzureDI([
      { pageNumber: 3, width: 8.5, height: 11, words: [word] },
    ]);

    const result = computeBoundingBoxes(azureDI, 3, 0, 5);
    expect(result).toHaveLength(1);
    expect(result[0].pageNumber).toBe(3);
  });

  it("returns multiple bounding boxes for multiple matching words", () => {
    const words = [
      makeWord("hello", 0, 5, [0, 0, 1, 0, 1, 1, 0, 1]),
      makeWord("world", 6, 5, [2, 0, 3, 0, 3, 1, 2, 1]),
    ];
    const azureDI = makeAzureDI([
      { pageNumber: 1, width: 8.5, height: 11, words },
    ]);

    const result = computeBoundingBoxes(azureDI, 1, 0, 12);
    expect(result).toHaveLength(2);
    expect(result[0].polygon).toEqual([0, 0, 1, 0, 1, 1, 0, 1]);
    expect(result[1].polygon).toEqual([2, 0, 3, 0, 3, 1, 2, 1]);
  });
});

// ============================================================================
// transformPolygonToPixels
// ============================================================================

describe("transformPolygonToPixels", () => {
  it("transforms X coordinates using canvasWidth/pageWidth ratio", () => {
    // Page is 8.5 inches wide, canvas is 850 pixels -> scale factor 100
    // X coord of 1 inch -> 100 pixels
    const polygon = [1, 0, 2, 0, 2, 0, 1, 0]; // Only X values matter for this test
    const result = transformPolygonToPixels(polygon, 8.5, 11, 850, 1100);

    // X values at indices 0, 2, 4, 6
    expect(result[0]).toBeCloseTo(100);
    expect(result[2]).toBeCloseTo(200);
    expect(result[4]).toBeCloseTo(200);
    expect(result[6]).toBeCloseTo(100);
  });

  it("transforms Y coordinates using canvasHeight/pageHeight ratio", () => {
    // Page is 11 inches tall, canvas is 1100 pixels -> scale factor 100
    // Y coord of 1 inch -> 100 pixels
    const polygon = [0, 1, 0, 2, 0, 2, 0, 1]; // Only Y values matter for this test
    const result = transformPolygonToPixels(polygon, 8.5, 11, 850, 1100);

    // Y values at indices 1, 3, 5, 7
    expect(result[1]).toBeCloseTo(100);
    expect(result[3]).toBeCloseTo(200);
    expect(result[5]).toBeCloseTo(200);
    expect(result[7]).toBeCloseTo(100);
  });

  it("handles different X and Y scale factors", () => {
    // Page: 10x20 inches, Canvas: 500x400 pixels
    // X scale: 500/10 = 50, Y scale: 400/20 = 20
    const polygon = [2, 5, 4, 5, 4, 10, 2, 10];
    const result = transformPolygonToPixels(polygon, 10, 20, 500, 400);

    // X values: 2*50=100, 4*50=200
    // Y values: 5*20=100, 10*20=200
    expect(result).toEqual([100, 100, 200, 100, 200, 200, 100, 200]);
  });

  it("handles 8-element polygon array (4 corners)", () => {
    const polygon = [1, 1, 2, 1, 2, 2, 1, 2];
    const result = transformPolygonToPixels(polygon, 8.5, 11, 850, 1100);

    expect(result).toHaveLength(8);
  });

  it("preserves array length for non-standard polygons", () => {
    // Some polygons might have more or fewer points
    const polygon4 = [1, 1, 2, 2];
    const result4 = transformPolygonToPixels(polygon4, 10, 10, 100, 100);
    expect(result4).toHaveLength(4);

    const polygon12 = [1, 1, 2, 1, 2, 2, 1, 2, 0, 0, 3, 3];
    const result12 = transformPolygonToPixels(polygon12, 10, 10, 100, 100);
    expect(result12).toHaveLength(12);
  });

  it("handles zero values in polygon", () => {
    const polygon = [0, 0, 1, 0, 1, 1, 0, 1];
    const result = transformPolygonToPixels(polygon, 8.5, 11, 850, 1100);

    expect(result[0]).toBe(0);
    expect(result[1]).toBe(0);
  });

  it("handles fractional coordinates", () => {
    const polygon = [0.5, 0.5, 1.5, 0.5, 1.5, 1.5, 0.5, 1.5];
    const result = transformPolygonToPixels(polygon, 10, 10, 100, 100);

    // Scale factor is 10, so 0.5 -> 5, 1.5 -> 15
    expect(result[0]).toBe(5);
    expect(result[1]).toBe(5);
    expect(result[2]).toBe(15);
    expect(result[3]).toBe(5);
  });
});

// ============================================================================
// Extended Test Fixtures for Smart Highlighting
// ============================================================================

function makeLine(
  content: string,
  offset: number,
  polygon: number[] = [0, 0, 5, 0, 5, 0.2, 0, 0.2]
): AzureDILine {
  return {
    content,
    polygon,
    spans: [{ offset, length: content.length }],
  };
}

function makeTableCell(
  content: string,
  offset: number,
  rowIndex: number,
  columnIndex: number,
  pageNumber: number = 1,
  polygon: number[] = [0, 0, 2, 0, 2, 0.5, 0, 0.5]
): AzureDITableCell {
  return {
    content,
    rowIndex,
    columnIndex,
    spans: [{ offset, length: content.length }],
    boundingRegions: [{ pageNumber, polygon }],
  };
}

function makeTable(cells: AzureDITableCell[]): AzureDITable {
  const maxRow = Math.max(...cells.map((c) => c.rowIndex)) + 1;
  const maxCol = Math.max(...cells.map((c) => c.columnIndex)) + 1;
  return {
    rowCount: maxRow,
    columnCount: maxCol,
    cells,
  };
}

function makeExtendedAzureDI(options: {
  pages?: Array<{
    pageNumber: number;
    width: number;
    height: number;
    words?: AzureDIWord[];
    lines?: AzureDILine[];
  }>;
  tables?: AzureDITable[];
}): AzureDIOutputExtended {
  return {
    raw_azure_di_output: {
      pages: (options.pages || []).map((p) => ({
        pageNumber: p.pageNumber,
        width: p.width,
        height: p.height,
        unit: "inch",
        words: p.words || [],
        lines: p.lines,
      })),
      content: "",
      tables: options.tables,
    },
  };
}

// ============================================================================
// findTableCellsInRange
// ============================================================================

describe("findTableCellsInRange", () => {
  it("returns empty array when no tables in document", () => {
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
    });
    const result = findTableCellsInRange(azureDI, 1, 0, 10);
    expect(result).toEqual([]);
  });

  it("returns empty array when no cells overlap range", () => {
    const cell = makeTableCell("hello", 50, 0, 0);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
      tables: [makeTable([cell])],
    });
    const result = findTableCellsInRange(azureDI, 1, 0, 10);
    expect(result).toEqual([]);
  });

  it("finds cell that contains range", () => {
    const cell = makeTableCell("hello world", 5, 0, 0);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
      tables: [makeTable([cell])],
    });
    const result = findTableCellsInRange(azureDI, 1, 5, 15);
    expect(result).toHaveLength(1);
    expect(result[0].cells).toHaveLength(1);
    expect(result[0].cells[0].content).toBe("hello world");
  });

  it("filters to correct page number", () => {
    const cell1 = makeTableCell("page1", 0, 0, 0, 1);
    const cell2 = makeTableCell("page2", 0, 0, 0, 2);
    const azureDI = makeExtendedAzureDI({
      pages: [
        { pageNumber: 1, width: 8.5, height: 11 },
        { pageNumber: 2, width: 8.5, height: 11 },
      ],
      tables: [makeTable([cell1, cell2])],
    });

    const result1 = findTableCellsInRange(azureDI, 1, 0, 10);
    expect(result1[0].cells[0].content).toBe("page1");

    const result2 = findTableCellsInRange(azureDI, 2, 0, 10);
    expect(result2[0].cells[0].content).toBe("page2");
  });

  it("includes tableIndex in result", () => {
    const cell = makeTableCell("data", 0, 0, 0);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
      tables: [makeTable([cell])],
    });
    const result = findTableCellsInRange(azureDI, 1, 0, 10);
    expect(result[0].tableIndex).toBe(0);
  });
});

// ============================================================================
// cellsContainRange
// ============================================================================

describe("cellsContainRange", () => {
  it("returns false for empty cell results", () => {
    expect(cellsContainRange([], 0, 10)).toBe(false);
  });

  it("returns true when cell fully contains range", () => {
    const cell = makeTableCell("hello world test", 0, 0, 0);
    const cellResults = [{ cells: [cell], tableIndex: 0 }];
    expect(cellsContainRange(cellResults, 0, 10)).toBe(true);
  });

  it("returns false when cell partially covers range", () => {
    const cell = makeTableCell("hi", 0, 0, 0); // offset 0, length 2
    const cellResults = [{ cells: [cell], tableIndex: 0 }];
    expect(cellsContainRange(cellResults, 0, 10)).toBe(false);
  });

  it("returns true when multiple cells together cover range", () => {
    const cell1 = makeTableCell("hello", 0, 0, 0); // 0-5
    const cell2 = makeTableCell("world", 5, 0, 1); // 5-10
    const cellResults = [{ cells: [cell1, cell2], tableIndex: 0 }];
    expect(cellsContainRange(cellResults, 0, 10)).toBe(true);
  });
});

// ============================================================================
// findLinesInRange
// ============================================================================

describe("findLinesInRange", () => {
  it("returns null when page has no lines", () => {
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words: [] }],
    });
    const result = findLinesInRange(azureDI, 1, 0, 10);
    expect(result).toBeNull();
  });

  it("returns null when no lines overlap range", () => {
    const line = makeLine("far away", 100);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
    });
    const result = findLinesInRange(azureDI, 1, 0, 10);
    expect(result).toBeNull();
  });

  it("finds line overlapping range", () => {
    const line = makeLine("hello world", 5);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
    });
    const result = findLinesInRange(azureDI, 1, 5, 15);
    expect(result).not.toBeNull();
    expect(result!.lines).toHaveLength(1);
    expect(result!.lines[0].content).toBe("hello world");
  });

  it("returns page dimensions", () => {
    const line = makeLine("test", 0);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
    });
    const result = findLinesInRange(azureDI, 1, 0, 10);
    expect(result!.pageWidth).toBe(8.5);
    expect(result!.pageHeight).toBe(11);
  });

  it("finds multiple consecutive lines", () => {
    const lines = [
      makeLine("line one", 0),   // 0-8
      makeLine("line two", 9),   // 9-17
      makeLine("line three", 18), // 18-28
    ];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines }],
    });
    const result = findLinesInRange(azureDI, 1, 0, 20);
    expect(result!.lines).toHaveLength(3);
  });
});

// ============================================================================
// calculateLineCoverage
// ============================================================================

describe("calculateLineCoverage", () => {
  it("returns 0 for empty lines array", () => {
    expect(calculateLineCoverage([], 0, 10)).toBe(0);
  });

  it("returns 0 when charEnd <= charStart", () => {
    const line = makeLine("test", 0);
    expect(calculateLineCoverage([line], 10, 10)).toBe(0);
    expect(calculateLineCoverage([line], 10, 5)).toBe(0);
  });

  it("returns 1.0 when line fully covers range", () => {
    const line = makeLine("hello world test", 0); // 0-16
    const coverage = calculateLineCoverage([line], 0, 10);
    expect(coverage).toBe(1.0);
  });

  it("returns correct ratio for partial coverage", () => {
    const line = makeLine("hi", 0); // 0-2
    const coverage = calculateLineCoverage([line], 0, 10);
    expect(coverage).toBeCloseTo(0.2); // 2/10
  });

  it("handles multiple lines covering range", () => {
    const lines = [
      makeLine("hello", 0),  // 0-5
      makeLine("world", 6),  // 6-11
    ];
    // Range 0-10: "hello" covers 0-5 (5 chars), "world" covers 6-10 (4 chars) = 9/10
    const coverage = calculateLineCoverage(lines, 0, 10);
    expect(coverage).toBeCloseTo(0.9);
  });
});

// ============================================================================
// groupWordsByLine
// ============================================================================

describe("groupWordsByLine", () => {
  it("returns empty array for empty input", () => {
    expect(groupWordsByLine([])).toEqual([]);
  });

  it("groups single word into one group", () => {
    const word = makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.1, 0, 1.1]);
    const groups = groupWordsByLine([word]);
    expect(groups).toHaveLength(1);
    expect(groups[0].words).toHaveLength(1);
  });

  it("groups words on same Y coordinate together", () => {
    const words = [
      makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.1, 0, 1.1]),
      makeWord("world", 6, 5, [2, 1, 3, 1, 3, 1.1, 2, 1.1]),
    ];
    const groups = groupWordsByLine(words);
    expect(groups).toHaveLength(1);
    expect(groups[0].words).toHaveLength(2);
  });

  it("separates words on different lines", () => {
    const words = [
      makeWord("line1", 0, 5, [0, 1, 1, 1, 1, 1.1, 0, 1.1]),     // Y ~1
      makeWord("line2", 6, 5, [0, 2, 1, 2, 1, 2.1, 0, 2.1]),     // Y ~2
    ];
    const groups = groupWordsByLine(words);
    expect(groups).toHaveLength(2);
  });

  it("uses configurable Y threshold", () => {
    const words = [
      makeWord("a", 0, 1, [0, 1.0, 1, 1.0, 1, 1.1, 0, 1.1]),
      makeWord("b", 2, 1, [2, 1.08, 3, 1.08, 3, 1.18, 2, 1.18]), // 0.08 apart
    ];
    // Default threshold 0.05 -> should be separate
    const groupsDefault = groupWordsByLine(words, 0.05);
    expect(groupsDefault).toHaveLength(2);

    // Larger threshold 0.1 -> should be together
    const groupsLarge = groupWordsByLine(words, 0.1);
    expect(groupsLarge).toHaveLength(1);
  });
});

// ============================================================================
// mergeConsecutiveWords
// ============================================================================

describe("mergeConsecutiveWords", () => {
  it("returns empty array for empty input", () => {
    expect(mergeConsecutiveWords([])).toEqual([]);
  });

  it("returns single result for single word", () => {
    const word = makeWord("hello", 0, 5, [0, 0, 1, 0, 1, 1, 0, 1]);
    const results = mergeConsecutiveWords([word]);
    expect(results).toHaveLength(1);
    expect(results[0].wordCount).toBe(1);
    expect(results[0].polygon).toEqual([0, 0, 1, 0, 1, 1, 0, 1]);
  });

  it("merges adjacent words into one box", () => {
    const words = [
      makeWord("hello", 0, 5, [0, 0, 1, 0, 1, 0.5, 0, 0.5]),
      makeWord("world", 6, 5, [1.1, 0, 2, 0, 2, 0.5, 1.1, 0.5]),
    ];
    const results = mergeConsecutiveWords(words, 0.3); // 0.1 gap < 0.3 threshold
    expect(results).toHaveLength(1);
    expect(results[0].wordCount).toBe(2);
  });

  it("returns multiple boxes for non-adjacent words", () => {
    const words = [
      makeWord("hello", 0, 5, [0, 0, 1, 0, 1, 0.5, 0, 0.5]),
      makeWord("world", 6, 5, [3, 0, 4, 0, 4, 0.5, 3, 0.5]), // 2 inch gap
    ];
    const results = mergeConsecutiveWords(words, 0.3);
    expect(results).toHaveLength(2);
  });

  it("calculates average confidence", () => {
    const words = [
      { ...makeWord("a", 0, 1, [0, 0, 1, 0, 1, 1, 0, 1]), confidence: 0.8 },
      { ...makeWord("b", 2, 1, [1.1, 0, 2, 0, 2, 1, 1.1, 1]), confidence: 1.0 },
    ];
    const results = mergeConsecutiveWords(words, 0.3);
    expect(results[0].avgConfidence).toBeCloseTo(0.9);
  });
});

// ============================================================================
// mergePolygons
// ============================================================================

describe("mergePolygons", () => {
  it("returns empty array for empty input", () => {
    expect(mergePolygons([])).toEqual([]);
  });

  it("returns original polygon for single input", () => {
    const polygon = [0, 0, 1, 0, 1, 1, 0, 1];
    expect(mergePolygons([polygon])).toEqual(polygon);
  });

  it("computes bounding rectangle from two polygons", () => {
    const poly1 = [0, 0, 1, 0, 1, 1, 0, 1];       // 0-1 x, 0-1 y
    const poly2 = [2, 0, 3, 0, 3, 1, 2, 1];       // 2-3 x, 0-1 y
    const merged = mergePolygons([poly1, poly2]);
    // Expected: 0-3 x, 0-1 y
    expect(merged).toEqual([0, 0, 3, 0, 3, 1, 0, 1]);
  });

  it("handles overlapping polygons", () => {
    const poly1 = [0, 0, 2, 0, 2, 2, 0, 2];
    const poly2 = [1, 1, 3, 1, 3, 3, 1, 3];
    const merged = mergePolygons([poly1, poly2]);
    // Expected: 0-3 x, 0-3 y
    expect(merged).toEqual([0, 0, 3, 0, 3, 3, 0, 3]);
  });

  it("handles three or more polygons", () => {
    const polys = [
      [0, 0, 1, 0, 1, 1, 0, 1],
      [2, 2, 3, 2, 3, 3, 2, 3],
      [4, 0, 5, 0, 5, 1, 4, 1],
    ];
    const merged = mergePolygons(polys);
    expect(merged).toEqual([0, 0, 5, 0, 5, 3, 0, 3]);
  });
});

// ============================================================================
// computeSmartBoundingBoxes - Integration Tests
// ============================================================================

describe("computeSmartBoundingBoxes", () => {
  it("returns empty array for invalid range", () => {
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
    });
    expect(computeSmartBoundingBoxes(azureDI, 1, 10, 5)).toEqual([]);
    expect(computeSmartBoundingBoxes(azureDI, 1, 5, 5)).toEqual([]);
  });

  it("returns empty array when page not found", () => {
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11 }],
    });
    expect(computeSmartBoundingBoxes(azureDI, 2, 0, 10)).toEqual([]);
  });

  it("prefers table cells when they contain range", () => {
    const cell = makeTableCell("table data here", 0, 0, 0, 1, [0, 0, 3, 0, 3, 1, 0, 1]);
    const line = makeLine("table data here", 0, [0, 0, 5, 0, 5, 0.5, 0, 0.5]);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
      tables: [makeTable([cell])],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 10);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe("cell");
  });

  it("uses line boxes when coverage >= 80%", () => {
    const line = makeLine("hello world!!", 0, [0, 1, 5, 1, 5, 1.2, 0, 1.2]); // 13 chars
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
    });

    // Range 0-12 on line 0-13 = 12/12 = 100% coverage
    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 12);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe("line");
  });

  it("falls back to merged words when line coverage < 80%", () => {
    // Line only covers first 5 chars, but range is 0-20
    // Coverage = 5/20 = 25%, should fall back to words
    const line = makeLine("hello", 0); // offset 0, length 5
    const words = [
      makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2]),
      makeWord("world", 6, 5, [1.1, 1, 2, 1, 2, 1.2, 1.1, 1.2]),
      makeWord("test", 12, 4, [2.1, 1, 3, 1, 3, 1.2, 2.1, 1.2]),
    ];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words, lines: [line] }],
    });

    // Range 0-20, line only covers 0-5 = 25% coverage, should fall back to words
    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 20);
    expect(result.length).toBeGreaterThan(0);
    expect(result[0].source).toBe("merged");
  });

  it("returns merged boxes with correct source", () => {
    const words = [
      makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2]),
      makeWord("world", 6, 5, [1.1, 1, 2, 1, 2, 1.2, 1.1, 1.2]),
    ];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words }],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 12);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe("merged");
    expect(result[0].confidence).toBeDefined();
  });

  it("returns word source for single word", () => {
    const words = [makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2])];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words }],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 5);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe("word");
  });

  it("respects enableTableDetection option", () => {
    const cell = makeTableCell("data", 0, 0, 0, 1);
    const line = makeLine("data", 0);
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, lines: [line] }],
      tables: [makeTable([cell])],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 4, {
      enableTableDetection: false,
    });
    expect(result[0].source).toBe("line");
  });

  it("respects enableLinePreference option", () => {
    const line = makeLine("hello", 0);
    const words = [makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2])];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words, lines: [line] }],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 5, {
      enableLinePreference: false,
    });
    expect(result[0].source).toBe("word");
  });

  it("handles missing lines gracefully", () => {
    const words = [makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2])];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words }],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 5);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe("word");
  });

  it("sets page dimensions on all boxes", () => {
    const words = [makeWord("hello", 0, 5, [0, 1, 1, 1, 1, 1.2, 0, 1.2])];
    const azureDI = makeExtendedAzureDI({
      pages: [{ pageNumber: 1, width: 8.5, height: 11, words }],
    });

    const result = computeSmartBoundingBoxes(azureDI, 1, 0, 5);
    expect(result[0].pageWidthInches).toBe(8.5);
    expect(result[0].pageHeightInches).toBe(11);
    expect(result[0].pageNumber).toBe(1);
  });
});
