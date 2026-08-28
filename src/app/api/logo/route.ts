import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const isBg = searchParams.get("bg") === "true";

  const publicLogoPath = path.join(process.cwd(), "public", "logo.png");

  if (!isBg) {
    if (fs.existsSync(publicLogoPath)) {
      try {
        const fileBuffer = fs.readFileSync(publicLogoPath);
        return new NextResponse(fileBuffer, {
          headers: {
            "Content-Type": "image/png",
            "Cache-Control": "public, max-age=31536000, immutable",
          },
        });
      } catch (err) {
        return new NextResponse("Error loading logo: " + (err as Error).message, { status: 500 });
      }
    }
    
    // Return SVG fallback
    const svgFallback = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40" viewBox="0 0 120 40"><rect width="120" height="40" rx="6" fill="#0f172a"/><text x="60" y="24" font-family="sans-serif" font-size="14" font-weight="bold" fill="#38bdf8" text-anchor="middle">SIET</text></svg>`;
    return new NextResponse(svgFallback, {
      headers: {
        "Content-Type": "image/svg+xml",
        "Cache-Control": "public, max-age=3600",
      },
    });
  }

  const publicBgPath = path.join(process.cwd(), "public", "hero-bg.png");
  if (fs.existsSync(publicBgPath)) {
    try {
      const fileBuffer = fs.readFileSync(publicBgPath);
      return new NextResponse(fileBuffer, {
        headers: {
          "Content-Type": "image/png",
          "Cache-Control": "public, max-age=31536000, immutable",
        },
      });
    } catch (err) {
      console.error("Error reading background file:", err);
    }
  }

  return new NextResponse("Background image not available", { status: 404 });
}

