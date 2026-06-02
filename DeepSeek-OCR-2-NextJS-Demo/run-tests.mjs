import puppeteer from "puppeteer";
import path from "path";
import fs from "fs";

async function run() {
  const screenshotsDir = path.join(process.cwd(), "..", "screenshots");
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log("Launching headless browser...");
  const browser = await puppeteer.launch({
    executablePath: "/usr/bin/google-chrome",
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1024 });

  console.log("Navigating to http://localhost:7873/next ...");
  await page.goto("http://localhost:7873/next", { waitUntil: "networkidle2" });

  // 1. Initial State Screenshot
  console.log("Taking screenshot of initial state...");
  await page.screenshot({ path: path.join(screenshotsDir, "01-01-initial-state.jpg"), fullPage: true });

  // 2. Select Example Image
  console.log("Clicking the first example document thumbnail...");
  await page.waitForSelector(".example-item");
  const examples = await page.$$(".example-item");
  if (examples.length > 0) {
    await examples[0].click();
  }
  await new Promise((resolve) => setTimeout(resolve, 1500)); // wait for image preview to show

  console.log("Taking screenshot of loaded example image...");
  await page.screenshot({ path: path.join(screenshotsDir, "01-02-example-loaded.jpg"), fullPage: true });

  // 3. Perform OCR
  console.log("Clicking the 'Perform OCR' button...");
  await page.waitForSelector(".submit-btn");
  await page.click(".submit-btn");

  console.log("Waiting for OCR processing to complete (this may take 15-30 seconds)...");
  // Wait for the markdown preview pane to appear
  await page.waitForSelector(".markdown-preview", { timeout: 60000 });
  await new Promise((resolve) => setTimeout(resolve, 1000)); // wait for layout paint

  console.log("Taking screenshot of Markdown result...");
  await page.screenshot({ path: path.join(screenshotsDir, "01-03-result-markdown.jpg"), fullPage: true });

  // 4. View Bounding Boxes
  console.log("Switching to Bounding Boxes tab...");
  const tabs = await page.$$(".tab-trigger");
  let foundBoxesTab = false;
  for (const tab of tabs) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes("Bounding Boxes")) {
      await tab.click();
      foundBoxesTab = true;
      break;
    }
  }

  if (foundBoxesTab) {
    await new Promise((resolve) => setTimeout(resolve, 1000)); // wait for image to load
    console.log("Taking screenshot of Bounding Boxes result...");
    await page.screenshot({ path: path.join(screenshotsDir, "01-04-result-bounding-boxes.jpg"), fullPage: true });
  }

  // 5. View Clean Text
  console.log("Switching to Clean Text tab...");
  for (const tab of tabs) {
    const text = await page.evaluate(el => el.textContent, tab);
    if (text.includes("Clean Text")) {
      await tab.click();
      break;
    }
  }
  await new Promise((resolve) => setTimeout(resolve, 1000));

  console.log("Taking screenshot of Clean Text result...");
  await page.screenshot({ path: path.join(screenshotsDir, "01-05-result-clean-text.jpg"), fullPage: true });

  console.log("Test finished successfully!");
  await browser.close();
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
