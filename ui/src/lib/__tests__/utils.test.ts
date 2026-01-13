import { describe, expect, test } from "vitest";
import { cn } from "../utils";

describe("cn", () => {
  test("merges class names and resolves conflicts", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-sm", false && "hidden", "text-lg")).toBe("text-lg");
    expect(cn("px-2", undefined, "py-1")).toBe("px-2 py-1");
  });
});
