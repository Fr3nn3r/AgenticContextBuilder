import { test, expect, Page } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";

/**
 * Evidence Highlighting Test Suite
 *
 * Tests the evidence highlighting functionality in the Claims Explorer.
 * This test is designed to run against a LOCAL backend with real data.
 *
 * Run with: E2E_TARGET=local npx playwright test evidence-highlighting
 *
 * Test scenarios:
 * 1. Login and navigate to Claims Explorer
 * 2. Select a claim and explore evidence links
 * 3. Click on evidence links (facts, checks, assessments)
 * 4. Verify highlighting appears in document viewer
 * 5. Test both PDF and image documents
 */

// Create screenshots directory
const screenshotsDir = path.join(process.cwd(), "test-screenshots", "evidence-highlighting");

interface TestResult {
  scenario: string;
  status: "pass" | "fail" | "skipped";
  details: string;
  screenshot?: string;
}

const testResults: TestResult[] = [];

function addResult(result: TestResult) {
  testResults.push(result);
  console.log(`[${result.status.toUpperCase()}] ${result.scenario}: ${result.details}`);
}

// Setup: ensure screenshots directory exists
test.beforeAll(async () => {
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
    console.log(`Created screenshots directory: ${screenshotsDir}`);
  }
});

// After all tests, print summary
test.afterAll(async () => {
  console.log("\n" + "=".repeat(80));
  console.log("EVIDENCE HIGHLIGHTING TEST SUMMARY");
  console.log("=".repeat(80));

  const passed = testResults.filter((r) => r.status === "pass");
  const failed = testResults.filter((r) => r.status === "fail");
  const skipped = testResults.filter((r) => r.status === "skipped");

  console.log(`\nResults: ${passed.length} passed, ${failed.length} failed, ${skipped.length} skipped`);

  if (passed.length > 0) {
    console.log("\n--- WHAT WORKS ---");
    passed.forEach((r) => console.log(`  [PASS] ${r.scenario}: ${r.details}`));
  }

  if (failed.length > 0) {
    console.log("\n--- WHAT DOESN'T WORK ---");
    failed.forEach((r) => console.log(`  [FAIL] ${r.scenario}: ${r.details}`));
  }

  if (skipped.length > 0) {
    console.log("\n--- SKIPPED ---");
    skipped.forEach((r) => console.log(`  [SKIP] ${r.scenario}: ${r.details}`));
  }

  console.log(`\nScreenshots saved to: ${screenshotsDir}`);
  console.log("=".repeat(80) + "\n");
});

test.describe("Evidence Highlighting - Claims Explorer", () => {
  // Skip tests in mock mode - we need real data
  test.skip(({ }, testInfo) => {
    const target = process.env.E2E_TARGET || "mock";
    if (target === "mock") {
      console.log("Skipping evidence highlighting tests in mock mode - run with E2E_TARGET=local");
      return true;
    }
    return false;
  });

  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto("/login");
    await page.waitForLoadState("networkidle");

    // Use credentials: stefano / su
    await page.getByLabel("Username").fill("stefano");
    await page.getByLabel("Password").fill("su");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Wait for redirect away from login
    await expect(page).not.toHaveURL(/\/login/, { timeout: 15000 });
    await page.waitForLoadState("networkidle");
  });

  test("1. Navigate to Claims Explorer and verify page loads", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Verify we're on the Claims Explorer page
    const heading = page.getByRole("heading", { name: /claim explorer/i });
    await expect(heading).toBeVisible({ timeout: 10000 });

    await page.screenshot({
      path: path.join(screenshotsDir, "01-claims-explorer-loaded.png"),
      fullPage: true,
    });

    addResult({
      scenario: "Claims Explorer Page Load",
      status: "pass",
      details: "Successfully loaded Claims Explorer page",
      screenshot: "01-claims-explorer-loaded.png",
    });
  });

  test("2. Select a claim and view summary", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Wait for claims heading to appear
    const claimsHeading = page.getByRole("heading", { name: "Claims" });
    await expect(claimsHeading).toBeVisible({ timeout: 10000 });

    // Take screenshot of claims list
    await page.screenshot({
      path: path.join(screenshotsDir, "02a-claims-list.png"),
      fullPage: true,
    });

    // Claims are in div elements with cursor-pointer class and contain claim IDs like "65128"
    // Look for elements that contain text like "65128", "65157", etc. (claim IDs)
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    const count = await claimItems.count();

    if (count === 0) {
      addResult({
        scenario: "Select Claim",
        status: "fail",
        details: "No claims found in the sidebar",
        screenshot: "02a-claims-list.png",
      });
      return;
    }

    // Click on the first claim
    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1000); // Give time for content to load

    await page.screenshot({
      path: path.join(screenshotsDir, "02b-claim-selected.png"),
      fullPage: true,
    });

    addResult({
      scenario: "Select Claim",
      status: "pass",
      details: `Found ${count} claims, selected first one`,
      screenshot: "02b-claim-selected.png",
    });
  });

  test("3. Find and click evidence links in Facts tab", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim - look for clickable claim items with "docs" text
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Take screenshot before looking for evidence
    await page.screenshot({
      path: path.join(screenshotsDir, "03a-before-evidence-click.png"),
      fullPage: true,
    });

    // Look for evidence links - these typically have an external link icon or "View source" text
    // or are clickable items within fact cards
    const evidenceLinks = page.locator(
      'button:has-text("Page"), button:has-text("Source"), [data-testid="evidence-link"], .cursor-pointer:has(.lucide-external-link), button:has(.lucide-external-link)'
    );

    const evidenceCount = await evidenceLinks.count();
    console.log(`Found ${evidenceCount} potential evidence links`);

    // Also look for clickable fact items (items with hover effects in fact cards)
    const factItems = page.locator('[class*="hover:bg-muted"], [class*="cursor-pointer"]:has-text(":")');
    const factItemCount = await factItems.count();
    console.log(`Found ${factItemCount} potential clickable fact items`);

    if (evidenceCount === 0 && factItemCount === 0) {
      // Try looking for any expandable field rows
      const expandableRows = page.locator('[class*="cursor-pointer"]');
      const expandableCount = await expandableRows.count();
      console.log(`Found ${expandableCount} expandable rows`);

      addResult({
        scenario: "Find Evidence Links in Facts",
        status: "skipped",
        details: `No obvious evidence links found. Expandable rows: ${expandableCount}`,
        screenshot: "03a-before-evidence-click.png",
      });
      return;
    }

    // Click on first evidence link
    if (evidenceCount > 0) {
      await evidenceLinks.first().click();
    } else {
      await factItems.first().click();
    }

    await page.waitForTimeout(1000);

    await page.screenshot({
      path: path.join(screenshotsDir, "03b-after-evidence-click.png"),
      fullPage: true,
    });

    addResult({
      scenario: "Find Evidence Links in Facts",
      status: "pass",
      details: `Found ${evidenceCount} evidence links, ${factItemCount} fact items`,
      screenshot: "03b-after-evidence-click.png",
    });
  });

  test("4. Test document viewer with PDF highlighting", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) === 0) {
      addResult({
        scenario: "PDF Highlighting",
        status: "skipped",
        details: "No claims available",
      });
      return;
    }

    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Try to find and click on a document in the documents panel or tray
    const docButtons = page.locator(
      '[data-testid="document-item"], [class*="DocumentsPanel"] button, [class*="doc-item"], .document-card'
    );

    let docCount = await docButtons.count();
    console.log(`Found ${docCount} document buttons`);

    // If no documents found via test IDs, try looking for file icons or PDF text
    if (docCount === 0) {
      const fileButtons = page.locator('button:has(.lucide-file-text), button:has-text(".pdf"), button:has-text("PDF")');
      docCount = await fileButtons.count();
      console.log(`Found ${docCount} file buttons via icons`);
    }

    // Look for any tabs that might open documents
    const docTabs = page.locator('div[role="tab"]:has-text("Document"), button:has-text("Documents")');
    if ((await docTabs.count()) > 0) {
      await docTabs.first().click();
      await page.waitForTimeout(500);
    }

    await page.screenshot({
      path: path.join(screenshotsDir, "04a-looking-for-documents.png"),
      fullPage: true,
    });

    // Check if document viewer is visible with PDF content
    const pdfViewer = page.locator('.react-pdf__Document, [data-testid="pdf-viewer"], iframe[src*="pdf"]');
    const hasPdf = (await pdfViewer.count()) > 0;

    // Check for PDF tab
    const pdfTab = page.locator('button:has-text("PDF"), [role="tab"]:has-text("PDF")');
    if ((await pdfTab.count()) > 0) {
      await pdfTab.click();
      await page.waitForTimeout(1000);

      await page.screenshot({
        path: path.join(screenshotsDir, "04b-pdf-tab-clicked.png"),
        fullPage: true,
      });
    }

    // Look for highlights (yellow/green backgrounds)
    const highlights = page.locator('.pdf-text-highlight, mark, [style*="background-color: yellow"], [style*="background-color: rgba(250, 204, 21"]');
    const highlightCount = await highlights.count();

    if (highlightCount > 0) {
      await page.screenshot({
        path: path.join(screenshotsDir, "04c-pdf-with-highlights.png"),
        fullPage: true,
      });

      addResult({
        scenario: "PDF Highlighting",
        status: "pass",
        details: `Found ${highlightCount} text highlights in PDF`,
        screenshot: "04c-pdf-with-highlights.png",
      });
    } else {
      addResult({
        scenario: "PDF Highlighting",
        status: "fail",
        details: `No highlights visible. PDF viewer present: ${hasPdf}`,
        screenshot: "04b-pdf-tab-clicked.png",
      });
    }
  });

  test("5. Test document viewer with image highlighting (bbox overlay)", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) === 0) {
      addResult({
        scenario: "Image Highlighting (Bbox)",
        status: "skipped",
        details: "No claims available",
      });
      return;
    }

    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Look for image tab
    const imageTab = page.locator('button:has-text("Image"), [role="tab"]:has-text("Image")');
    if ((await imageTab.count()) > 0) {
      await imageTab.click();
      await page.waitForTimeout(1000);

      await page.screenshot({
        path: path.join(screenshotsDir, "05a-image-tab-clicked.png"),
        fullPage: true,
      });

      // Look for bbox overlays
      const bboxOverlay = page.locator('[data-testid="bbox-overlay"], .bbox-overlay, svg rect, [class*="highlight-box"]');
      const bboxCount = await bboxOverlay.count();

      if (bboxCount > 0) {
        addResult({
          scenario: "Image Highlighting (Bbox)",
          status: "pass",
          details: `Found ${bboxCount} bounding box overlays`,
          screenshot: "05a-image-tab-clicked.png",
        });
      } else {
        addResult({
          scenario: "Image Highlighting (Bbox)",
          status: "fail",
          details: "No bounding box overlays visible on image",
          screenshot: "05a-image-tab-clicked.png",
        });
      }
    } else {
      addResult({
        scenario: "Image Highlighting (Bbox)",
        status: "skipped",
        details: "No Image tab available for selected document",
      });
    }
  });

  test("6. Test evidence click from Facts card opens document with highlight", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) === 0) {
      addResult({
        scenario: "Evidence Click Opens Highlight",
        status: "skipped",
        details: "No claims available",
      });
      return;
    }

    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Take "before" screenshot
    await page.screenshot({
      path: path.join(screenshotsDir, "06a-before-fact-click.png"),
      fullPage: true,
    });

    // Look for a clickable fact row with a source icon (ExternalLink)
    const factWithSource = page.locator('[class*="cursor-pointer"]:has(.lucide-external-link)');
    const factCount = await factWithSource.count();
    console.log(`Found ${factCount} facts with source links`);

    if (factCount === 0) {
      // Try alternative: look for any fact row that appears clickable
      const clickableFacts = page.locator('[class*="hover:bg"]:has-text("VIN"), [class*="hover:bg"]:has-text("Policy"), [class*="hover:bg"]:has-text("Vehicle")');
      const altCount = await clickableFacts.count();
      console.log(`Found ${altCount} alternative clickable facts`);

      if (altCount > 0) {
        await clickableFacts.first().click();
      } else {
        addResult({
          scenario: "Evidence Click Opens Highlight",
          status: "fail",
          details: "No facts with source links found",
          screenshot: "06a-before-fact-click.png",
        });
        return;
      }
    } else {
      await factWithSource.first().click();
    }

    await page.waitForTimeout(1500);

    // Check if a document tab opened
    const docTab = page.locator('div[class*="tab"]:has(.lucide-file-text)');
    const hasDocTab = (await docTab.count()) > 0;

    // Take "after" screenshot
    await page.screenshot({
      path: path.join(screenshotsDir, "06b-after-fact-click.png"),
      fullPage: true,
    });

    // Check for highlights
    const highlights = page.locator('.pdf-text-highlight, mark, [style*="rgba(250, 204, 21"]');
    const highlightCount = await highlights.count();

    // Check for bbox overlays
    const bboxes = page.locator('[class*="bbox"], svg rect[fill*="rgba"]');
    const bboxCount = await bboxes.count();

    if (highlightCount > 0 || bboxCount > 0) {
      addResult({
        scenario: "Evidence Click Opens Highlight",
        status: "pass",
        details: `Document opened with highlighting. Text highlights: ${highlightCount}, Bbox overlays: ${bboxCount}`,
        screenshot: "06b-after-fact-click.png",
      });
    } else if (hasDocTab) {
      addResult({
        scenario: "Evidence Click Opens Highlight",
        status: "fail",
        details: "Document tab opened but no highlights visible",
        screenshot: "06b-after-fact-click.png",
      });
    } else {
      addResult({
        scenario: "Evidence Click Opens Highlight",
        status: "fail",
        details: "Clicking fact did not open a document tab",
        screenshot: "06b-after-fact-click.png",
      });
    }
  });

  test("7. Test Assessment Checks evidence links", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) === 0) {
      addResult({
        scenario: "Assessment Checks Evidence",
        status: "skipped",
        details: "No claims available",
      });
      return;
    }

    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Look for Assessment tab
    const assessmentTab = page.locator('button:has-text("Assessment"), [role="tab"]:has-text("Assessment")');
    if ((await assessmentTab.count()) > 0) {
      await assessmentTab.click();
      await page.waitForTimeout(1000);

      await page.screenshot({
        path: path.join(screenshotsDir, "07a-assessment-tab.png"),
        fullPage: true,
      });

      // Look for check cards that can be expanded
      const checkCards = page.locator('[class*="CheckCard"], [data-testid="check-card"], button:has(.lucide-check-circle), button:has(.lucide-x-circle)');
      const checkCount = await checkCards.count();
      console.log(`Found ${checkCount} check cards`);

      if (checkCount > 0) {
        // Click to expand first check
        await checkCards.first().click();
        await page.waitForTimeout(500);

        await page.screenshot({
          path: path.join(screenshotsDir, "07b-check-expanded.png"),
          fullPage: true,
        });

        // Look for evidence links within the check
        const evidenceLinks = page.locator('button:has(.lucide-external-link):visible');
        const evidenceLinkCount = await evidenceLinks.count();
        console.log(`Found ${evidenceLinkCount} evidence links in checks`);

        if (evidenceLinkCount > 0) {
          await evidenceLinks.first().click();
          await page.waitForTimeout(1500);

          await page.screenshot({
            path: path.join(screenshotsDir, "07c-after-evidence-click.png"),
            fullPage: true,
          });

          // Check for highlighting
          const highlights = page.locator('.pdf-text-highlight, mark');
          if ((await highlights.count()) > 0) {
            addResult({
              scenario: "Assessment Checks Evidence",
              status: "pass",
              details: `Clicked evidence link and highlighting appeared. ${evidenceLinkCount} evidence links found.`,
              screenshot: "07c-after-evidence-click.png",
            });
          } else {
            addResult({
              scenario: "Assessment Checks Evidence",
              status: "fail",
              details: `Evidence link clicked but no highlighting appeared. ${evidenceLinkCount} evidence links found.`,
              screenshot: "07c-after-evidence-click.png",
            });
          }
        } else {
          addResult({
            scenario: "Assessment Checks Evidence",
            status: "fail",
            details: "No evidence links found in assessment checks",
            screenshot: "07b-check-expanded.png",
          });
        }
      } else {
        addResult({
          scenario: "Assessment Checks Evidence",
          status: "fail",
          details: "No assessment check cards found",
          screenshot: "07a-assessment-tab.png",
        });
      }
    } else {
      addResult({
        scenario: "Assessment Checks Evidence",
        status: "skipped",
        details: "No Assessment tab found",
      });
    }
  });

  test("8. Capture console errors during evidence highlighting", async ({ page }) => {
    const consoleErrors: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    page.on("pageerror", (error) => {
      consoleErrors.push(`Page error: ${error.message}`);
    });

    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) > 0) {
      await claimItems.first().click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // Try clicking on various elements
      const factWithSource = page.locator('[class*="cursor-pointer"]:has(.lucide-external-link)');
      if ((await factWithSource.count()) > 0) {
        await factWithSource.first().click();
        await page.waitForTimeout(2000);
      }
    }

    await page.screenshot({
      path: path.join(screenshotsDir, "08-console-errors-check.png"),
      fullPage: true,
    });

    if (consoleErrors.length > 0) {
      addResult({
        scenario: "Console Errors",
        status: "fail",
        details: `Found ${consoleErrors.length} console errors: ${consoleErrors.slice(0, 3).join("; ")}`,
        screenshot: "08-console-errors-check.png",
      });
    } else {
      addResult({
        scenario: "Console Errors",
        status: "pass",
        details: "No console errors during evidence highlighting interactions",
        screenshot: "08-console-errors-check.png",
      });
    }
  });

  test("9. Test NSA-specific document (if available)", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Look for NSA-related claims (typically have specific naming patterns)
    const nsaClaimPatterns = page.locator('button:has-text("NSA"), button:has-text("nsa"), button:has-text("65196")');
    const nsaCount = await nsaClaimPatterns.count();

    await page.screenshot({
      path: path.join(screenshotsDir, "09a-looking-for-nsa.png"),
      fullPage: true,
    });

    if (nsaCount > 0) {
      await nsaClaimPatterns.first().click();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1500);

      await page.screenshot({
        path: path.join(screenshotsDir, "09b-nsa-claim-selected.png"),
        fullPage: true,
      });

      // Check for documents and evidence
      const factWithSource = page.locator('[class*="cursor-pointer"]:has(.lucide-external-link)');
      if ((await factWithSource.count()) > 0) {
        await factWithSource.first().click();
        await page.waitForTimeout(2000);

        await page.screenshot({
          path: path.join(screenshotsDir, "09c-nsa-evidence-clicked.png"),
          fullPage: true,
        });

        const highlights = page.locator('.pdf-text-highlight, mark');
        if ((await highlights.count()) > 0) {
          addResult({
            scenario: "NSA Document Evidence",
            status: "pass",
            details: "NSA document evidence highlighting works",
            screenshot: "09c-nsa-evidence-clicked.png",
          });
        } else {
          addResult({
            scenario: "NSA Document Evidence",
            status: "fail",
            details: "NSA document evidence clicked but no highlighting",
            screenshot: "09c-nsa-evidence-clicked.png",
          });
        }
      } else {
        addResult({
          scenario: "NSA Document Evidence",
          status: "fail",
          details: "NSA claim found but no evidence links available",
          screenshot: "09b-nsa-claim-selected.png",
        });
      }
    } else {
      // Just select any claim and note no NSA-specific found
      const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
      if ((await claimItems.count()) > 0) {
        await claimItems.first().click();
        await page.waitForTimeout(1500);
      }

      addResult({
        scenario: "NSA Document Evidence",
        status: "skipped",
        details: "No NSA-specific claims found in the current workspace",
        screenshot: "09a-looking-for-nsa.png",
      });
    }
  });

  test("10. Test expanded field row source navigation", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select first claim
    const claimItems = page.locator('div[class*="cursor-pointer"]:has-text("docs")');
    if ((await claimItems.count()) === 0) {
      addResult({
        scenario: "Expanded Field Source Navigation",
        status: "skipped",
        details: "No claims available",
      });
      return;
    }

    await claimItems.first().click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Look for a document to open directly
    const docLinks = page.locator('[class*="document"], [data-testid*="doc"]');
    if ((await docLinks.count()) > 0) {
      await docLinks.first().click();
      await page.waitForTimeout(1000);
    }

    // Now in document view, look for field rows to expand
    const fieldRows = page.locator('[class*="border-b"]:has(.lucide-chevron-down)');
    const fieldCount = await fieldRows.count();
    console.log(`Found ${fieldCount} expandable field rows`);

    await page.screenshot({
      path: path.join(screenshotsDir, "10a-document-view.png"),
      fullPage: true,
    });

    if (fieldCount > 0) {
      // Click to expand first field
      await fieldRows.first().click();
      await page.waitForTimeout(500);

      await page.screenshot({
        path: path.join(screenshotsDir, "10b-field-expanded.png"),
        fullPage: true,
      });

      // Look for "Page X" source link in expanded content
      const pageLink = page.locator('button:has-text("Page")');
      if ((await pageLink.count()) > 0) {
        await pageLink.first().click();
        await page.waitForTimeout(1500);

        await page.screenshot({
          path: path.join(screenshotsDir, "10c-after-page-link-click.png"),
          fullPage: true,
        });

        const highlights = page.locator('.pdf-text-highlight, mark');
        if ((await highlights.count()) > 0) {
          addResult({
            scenario: "Expanded Field Source Navigation",
            status: "pass",
            details: "Page link in expanded field triggered highlighting",
            screenshot: "10c-after-page-link-click.png",
          });
        } else {
          addResult({
            scenario: "Expanded Field Source Navigation",
            status: "fail",
            details: "Page link clicked but no highlighting appeared",
            screenshot: "10c-after-page-link-click.png",
          });
        }
      } else {
        addResult({
          scenario: "Expanded Field Source Navigation",
          status: "fail",
          details: "No 'Page X' source link found in expanded field",
          screenshot: "10b-field-expanded.png",
        });
      }
    } else {
      addResult({
        scenario: "Expanded Field Source Navigation",
        status: "skipped",
        details: "No expandable field rows found in document view",
        screenshot: "10a-document-view.png",
      });
    }
  });
});
