import { NextRequest, NextResponse } from "next/server";
import { Client } from "@gradio/client";

export const maxDuration = 60; // 60 seconds timeout for long model inferences

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;
    const mode = (formData.get("mode") as string) || "Default";
    const task = (formData.get("task") as string) || "Markdown";
    const prompt = (formData.get("prompt") as string) || "";

    if (!file) {
      return NextResponse.json({ error: "No image file provided" }, { status: 400 });
    }

    // Convert file to a Blob for Gradio Client
    const arrayBuffer = await file.arrayBuffer();
    const blob = new Blob([arrayBuffer], { type: file.type });

    // Connect to Gradio client (running locally or inside Docker)
    const gradioUrl = process.env.GRADIO_URL || "http://127.0.0.1:7873/v2/";
    const client = await Client.connect(gradioUrl);

    // Call process_image (index 2)
    // inputs: [image, mode, task, custom_prompt]
    const result = await client.predict(2, [
      blob,
      mode,
      task,
      prompt
    ]);

    const data = result.data as any[];

    if (!data || data.length < 3) {
      return NextResponse.json({ error: "Invalid response from OCR model" }, { status: 502 });
    }

    // Utility function to normalize Gradio URLs to relative paths with Next.js base path
    // e.g. "http://127.0.0.1:7873/v2/file=/tmp/gradio/..." -> "/next/v2/file=/tmp/gradio/..."
    const normalizeUrl = (url: string | null | undefined): string | null => {
      if (!url) return null;
      try {
        const parsed = new URL(url);
        // If it points to local Gradio server path, prepend /next
        if (parsed.pathname.startsWith("/v2/")) {
          return `/next${parsed.pathname}${parsed.search}`;
        }
        // Fallback for paths that might omit /v2/ in some configurations
        return `/next/v2${parsed.pathname}${parsed.search}`;
      } catch (e) {
        return url;
      }
    };


    const text = data[0] || "";
    const markdown = data[1] || "";
    const raw = data[2] || "";
    
    // Normalize bounding box image URL
    const imageUrl = data[3] ? normalizeUrl(data[3].url) : null;
    
    // Normalize cropped image URLs
    const crops = Array.isArray(data[4]) 
      ? data[4].map((item: any) => normalizeUrl(item.url)).filter(Boolean) as string[]
      : [];

    return NextResponse.json({
      text,
      markdown,
      raw,
      imageUrl,
      crops
    });
  } catch (error: any) {
    console.error("OCR Inference Error:", error);
    return NextResponse.json(
      { error: error.message || "An unexpected error occurred during OCR execution" },
      { status: 500 }
    );
  }
}
