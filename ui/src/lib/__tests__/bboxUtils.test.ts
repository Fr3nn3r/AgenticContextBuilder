import { describe, it, expect } from "vitest";
import {
  findWordsInRange,
  computeBoundingBoxes,
  transformPolygonToPixels,
} from "../bboxUtils";
import type { AzureDIOutput, AzureDIWord } from "../../types";

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
