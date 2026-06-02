import { Client } from "@gradio/client";
import fs from "fs";
import path from "path";

async function run() {
  try {
    console.log("Connecting to Gradio client...");
    const client = await Client.connect("http://127.0.0.1:7873/v2/");
    console.log("Gradio client connected successfully!");

    // Load example image
    const imgPath = path.join(process.cwd(), "..", "DeepSeek-OCR-2-Demo", "examples", "1.jpg");
    const buffer = fs.readFileSync(imgPath);
    const blob = new Blob([buffer], { type: "image/jpeg" });

    console.log("Sending prediction request for process_image...");
    // process_image is at index 2 or "/process_image"
    // inputs: [image, mode, task, custom_prompt]
    const result = await client.predict(2, [
      blob,
      "Default",
      "Markdown",
      ""
    ]);

    console.log("Result received!");
    console.log("Keys in output:", Object.keys(result));
    console.log("Output structure:", JSON.stringify(result, null, 2).substring(0, 1000));
  } catch (err) {
    console.error("Error during test:", err);
  }
}

run();
