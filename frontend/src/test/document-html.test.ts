import { describe, expect, it } from "vitest";
import { mockApi } from "@/api/mock";

describe("saved web page documents", () => {
  for (const extension of ["html", "htm"]) {
    it(`accepts .${extension} and returns extracted text, not rendered content`, async () => {
      const document = await mockApi.uploadDocument({ file: new File(["<h1>Test Person</h1>"], `sample-cv.${extension}`, { type: "text/html" }), category: "cv" });
      expect(document.file_extension).toBe(extension);
      expect(document.mime_type).toBe("text/html");
      const text = await mockApi.getDocumentText(document.id);
      expect(text.extraction_status).toBe("succeeded");
      expect(typeof text.text).toBe("string");
    });
  }
});