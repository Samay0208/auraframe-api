/**
 * AuraFrame Cloud Style Engine - Premium Programmatic Artistic Transformations
 * 100% Free, Instant, and Ultra-High-Fidelity Programmatic Style Pipelines
 * Bypasses unstable third-party networks using native C++ Sharp operations.
 */

import sharp from "sharp";

// Global list to hold style engine errors in a circular-safe manner
export const styleErrors = [];

// Helper: Halftone dot screen SVG generator (for Pop Art, Comics, Manga)
function generateHalftoneSvg(width, height, dotSize = 4, spacing = 8, opacity = 0.15) {
  let circles = "";
  const step = Math.max(spacing, 6);
  for (let x = step / 2; x < width; x += step) {
    for (let y = step / 2; y < height; y += step) {
      circles += `<circle cx="${x}" cy="${y}" r="${dotSize / 2}" fill="#000000" opacity="${opacity}"/>`;
    }
  }
  return `<svg width="${width}" height="${height}">${circles}</svg>`;
}

// Helper: Repeating canvas threads generator (for Oil, Acrylic, Classical Paintings)
function generateCanvasSvg(width, height, spacing = 6, opacity = 0.12) {
  let lines = "";
  const step = Math.max(spacing, 4);
  for (let i = 0; i < height; i += step) {
    lines += `<line x1="0" y1="${i}" x2="${width}" y2="${i}" stroke="#555555" stroke-width="1" opacity="${opacity}"/>`;
  }
  for (let j = 0; j < width; j += step) {
    lines += `<line x1="${j}" y1="0" x2="${j}" y2="${height}" stroke="#555555" stroke-width="1" opacity="${opacity}"/>`;
  }
  return `<svg width="${width}" height="${height}">${lines}</svg>`;
}

// Helper: Venetian blinds shadow generator (for Film Noir)
function generateVenetianBlindsSvg(width, height, opacity = 0.5) {
  let blinds = "";
  const barHeight = 45;
  const gap = 55;
  for (let i = 0; i < height; i += (barHeight + gap)) {
    blinds += `<rect x="0" y="${i}" width="${width}" height="${barHeight}" fill="#000000" opacity="${opacity}"/>`;
  }
  return `<svg width="${width}" height="${height}">${blinds}</svg>`;
}

// Helper: Cyberpunk/Vaporwave screen scanlines generator
function generateGridLinesSvg(width, height, spacing = 12, color = "#ff007f", opacity = 0.15) {
  let lines = "";
  for (let i = 0; i < height; i += spacing) {
    lines += `<line x1="0" y1="${i}" x2="${width}" y2="${i}" stroke="${color}" stroke-width="1" opacity="${opacity}"/>`;
  }
  return `<svg width="${width}" height="${height}">${lines}</svg>`;
}

// Helper: Deep vignette SVG overlay
function generateVignetteSvg(width, height, opacity = 0.95) {
  return `
    <svg width="${width}" height="${height}">
      <defs>
        <radialGradient id="vignette" cx="50%" cy="50%" r="70%">
          <stop offset="30%" stop-color="#000000" stop-opacity="0"/>
          <stop offset="100%" stop-color="#000000" stop-opacity="${opacity}"/>
        </radialGradient>
      </defs>
      <rect width="${width}" height="${height}" fill="url(#vignette)"/>
    </svg>
  `;
}

// Helper: Generates beautiful organic paper grain (for Watercolor, Charcoal, Pastel)
function generatePaperGrainSvg(width, height, opacity = 0.08) {
  let circles = "";
  const points = Math.min(300, Math.floor((width * height) / 2000));
  for (let i = 0; i < points; i++) {
    const rx = Math.random() * width;
    const ry = Math.random() * height;
    const r = Math.random() * 3 + 0.5;
    circles += `<circle cx="${rx}" cy="${ry}" r="${r}" fill="#555555" opacity="${opacity}"/>`;
  }
  return `<svg width="${width}" height="${height}">${circles}</svg>`;
}

// Helper: Neon glow border SVG (for Cyberpunk, Vaporwave)
function generateNeonBorderSvg(width, height, color = "#ff007f", thickness = 6, opacity = 0.6) {
  return `
    <svg width="${width}" height="${height}">
      <rect x="${thickness/2}" y="${thickness/2}" width="${width - thickness}" height="${height - thickness}"
        fill="none" stroke="${color}" stroke-width="${thickness}" opacity="${opacity}" rx="8"/>
    </svg>
  `;
}

// Helper: Generates black ink outlines using Laplacian edge detection
async function generateInkOutlines(buffer, intensity = 1.5, offset = -40) {
  return await sharp(buffer)
    .grayscale()
    .convolve({
      width: 3,
      height: 3,
      kernel: [
        0, -1, 0,
        -1,  4, -1,
        0, -1, 0
      ]
    })
    .negate()
    .linear(intensity, offset)
    .toBuffer();
}

// Helper: Generates embossed/raised surface texture using Sobel-like kernel
async function generateEmboss(buffer, scale = 1.0) {
  return await sharp(buffer)
    .grayscale()
    .convolve({
      width: 3,
      height: 3,
      kernel: [
        -2, -1, 0,
        -1,  1, 1,
         0,  1, 2
      ],
      scale: scale
    })
    .toBuffer();
}

/**
 * Executes a premium programmatic styling pipeline.
 * Each style uses multi-step compositing for visually stunning results.
 */
export async function applyStyle(imageBuffer, style, customPrompt = "") {
  console.log(`StyleEngine: Programmatic processing for style [${style}]`);
  try {
    const img = sharp(imageBuffer);
    const metadata = await img.metadata();
    const w = metadata.width || 1024;
    const h = metadata.height || 600;

    switch (style) {
      // ═══════════════════════════════════════════════════════════════════
      //  FREE / BASIC STYLES (user confirmed these work well — untouched)
      // ═══════════════════════════════════════════════════════════════════
      case "original":
        return imageBuffer;

      case "blackwhite":
        return await img.grayscale().toBuffer();

      case "sepia":
        return await img
          .recomb([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131],
          ])
          .toBuffer();

      case "highcontrast":
        return await img.normalise().linear(1.3, -15).toBuffer();

      case "warmglow":
        return await img.tint({ r: 255, g: 215, b: 160 }).toBuffer();

      case "cooltint":
        return await img.tint({ r: 160, g: 195, b: 255 }).toBuffer();

      case "vignette": {
        const overlay = generateVignetteSvg(w, h, 0.8);
        return await img
          .composite([{ input: Buffer.from(overlay), blend: "multiply" }])
          .toBuffer();
      }

      // ═══════════════════════════════════════════════════════════════════
      //  PRO STYLES — sketch, ink, watercolor, oilpainting confirmed good
      // ═══════════════════════════════════════════════════════════════════
      case "sketch": {
        // Color Dodge pencil sketch (Photoshop matching) — CONFIRMED GOOD
        const gray = await sharp(imageBuffer).grayscale().toBuffer();
        const invertedBlurred = await sharp(gray)
          .negate()
          .blur(14)
          .toBuffer();
        return await sharp(gray)
          .composite([{ input: invertedBlurred, blend: "color-dodge" }])
          .toBuffer();
      }

      case "ink": {
        // Deep ink outlines over high-contrast shading — CONFIRMED GOOD
        const outlines = await generateInkOutlines(imageBuffer, 1.8, -60);
        const shading = await sharp(imageBuffer)
          .grayscale()
          .linear(1.6, -30)
          .toBuffer();
        return await sharp(shading)
          .composite([{ input: outlines, blend: "multiply" }])
          .toBuffer();
      }

      case "watercolor": {
        // Wet color smoothing with saturation boost — CONFIRMED GOOD
        const smoothed = await sharp(imageBuffer)
          .blur(4)
          .recomb([
            [1.25, 0, 0],
            [0, 1.25, 0],
            [0, 0, 1.25]
          ])
          .toBuffer();
        const grain = generatePaperGrainSvg(w, h, 0.1);
        return await sharp(smoothed)
          .composite([{ input: Buffer.from(grain), blend: "multiply" }])
          .toBuffer();
      }

      case "oilpainting": {
        // Saturated impasto with canvas threads — CONFIRMED GOOD
        const richColors = await sharp(imageBuffer)
          .recomb([
            [1.3, 0.1, -0.1],
            [-0.1, 1.3, 0.1],
            [0.1, -0.1, 1.3]
          ])
          .linear(1.2, -10)
          .toBuffer();
        const canvas = generateCanvasSvg(w, h, 6, 0.15);
        return await sharp(richColors)
          .composite([{ input: Buffer.from(canvas), blend: "overlay" }])
          .toBuffer();
      }

      // ═══════════════════════════════════════════════════════════════════
      //  PRO STYLES — IMPROVED
      // ═══════════════════════════════════════════════════════════════════

      case "charcoal": {
        // Multi-layer charcoal: dark sketch + inverted soft layer + heavy paper grain
        const gray = await sharp(imageBuffer).grayscale().toBuffer();
        const darkSketch = await sharp(gray).linear(1.8, -60).toBuffer();
        const softInvert = await sharp(gray).negate().blur(8).linear(0.4, 0).toBuffer();
        const grainSvg = generatePaperGrainSvg(w, h, 0.18);
        return await sharp(darkSketch)
          .composite([
            { input: softInvert, blend: "soft-light" },
            { input: Buffer.from(grainSvg), blend: "overlay" }
          ])
          .toBuffer();
      }

      case "impressionist": {
        // Painterly: median smoothing + vivid warm saturation + emboss texture + canvas
        const painted = await sharp(imageBuffer)
          .median(7)
          .modulate({ saturation: 1.7, brightness: 1.05 })
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const canvasSvg = generateCanvasSvg(w, h, 7, 0.14);
        return await sharp(painted)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(canvasSvg), blend: "overlay" }
          ])
          .toBuffer();
      }

      case "vangogh": {
        // Dramatic swirling: median smoothing + extreme yellow/blue channel shift + emboss strokes + heavy canvas
        const paintBase = await sharp(imageBuffer)
          .median(5)
          .recomb([
            [0.7, 0.3, 0.5],
            [0.0, 1.4, 0.0],
            [0.5, -0.3, 1.6]
          ])
          .modulate({ saturation: 1.6, brightness: 1.05 })
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const canvasSvg = generateCanvasSvg(w, h, 4, 0.22);
        return await sharp(paintBase)
          .composite([
            { input: emboss, blend: "overlay" },
            { input: Buffer.from(canvasSvg), blend: "overlay" }
          ])
          .toBuffer();
      }

      case "cartoon": {
        // Bold cartoon: heavy median for flat cel-shading + super-saturated colors + thick outlines
        const outlines = await generateInkOutlines(imageBuffer, 2.2, -90);
        const celBase = await sharp(imageBuffer)
          .median(7)
          .modulate({ saturation: 1.8, brightness: 1.05 })
          .linear(1.2, -10)
          .toBuffer();
        return await sharp(celBase)
          .composite([{ input: outlines, blend: "multiply" }])
          .toBuffer();
      }

      case "anime": {
        // Anime cel-shading: median smooth + warm-cool anime palette + fine outlines + subtle vignette
        const outlines = await generateInkOutlines(imageBuffer, 1.7, -55);
        const animeBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 1.4, brightness: 1.08 })
          .recomb([
            [1.1, 0.05, -0.05],
            [-0.05, 1.1, 0.1],
            [0.0, -0.05, 1.2]
          ])
          .toBuffer();
        const vignette = generateVignetteSvg(w, h, 0.4);
        return await sharp(animeBase)
          .composite([
            { input: outlines, blend: "multiply" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "popArt": {
        // Andy Warhol: extreme saturation + posterized contrast + bold halftone dots + vivid color shift
        const warholBase = await sharp(imageBuffer)
          .modulate({ saturation: 2.5, brightness: 1.1 })
          .recomb([
            [1.8, -0.4, -0.2],
            [-0.3, 1.7, -0.2],
            [-0.2, -0.3, 1.8]
          ])
          .linear(1.5, -30)
          .toBuffer();
        const halftoneSvg = generateHalftoneSvg(w, h, 6, 12, 0.2);
        return await sharp(warholBase)
          .composite([{ input: Buffer.from(halftoneSvg), blend: "multiply" }])
          .toBuffer();
      }

      case "pixelArt": {
        // Retro pixel: downsample to tiny + saturate colors + hard upscale
        const tiny = await sharp(imageBuffer)
          .resize(64, Math.round(64 * (h / w)), { kernel: sharp.kernel.nearest })
          .modulate({ saturation: 1.6 })
          .linear(1.15, -8)
          .toBuffer();
        return await sharp(tiny)
          .resize(w, h, { kernel: sharp.kernel.nearest })
          .toBuffer();
      }

      case "ukiyoe": {
        // Japanese woodblock: flat posterized warm tones + bold outlines + subtle emboss grain
        const outlines = await generateInkOutlines(imageBuffer, 2.0, -70);
        const flatBase = await sharp(imageBuffer)
          .median(5)
          .recomb([
            [0.5, 0.7, 0.1],
            [0.3, 0.75, 0.15],
            [0.2, 0.5, 0.1],
          ])
          .modulate({ saturation: 0.7 })
          .linear(1.3, -15)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        return await sharp(flatBase)
          .composite([
            { input: outlines, blend: "multiply" },
            { input: emboss, blend: "soft-light" }
          ])
          .toBuffer();
      }

      case "lowpoly": {
        // Geometric facets: aggressive downsample + saturate + slight emboss for facet edges
        const faceted = await sharp(imageBuffer)
          .resize(40, Math.round(40 * (h / w)), { kernel: sharp.kernel.nearest })
          .modulate({ saturation: 1.3, brightness: 1.05 })
          .toBuffer();
        const upscaled = await sharp(faceted)
          .resize(w, h, { kernel: sharp.kernel.nearest })
          .toBuffer();
        const emboss = await generateEmboss(upscaled, 1.0);
        return await sharp(upscaled)
          .composite([{ input: emboss, blend: "soft-light" }])
          .toBuffer();
      }

      case "manga": {
        // Japanese manga: high-contrast B&W + bold outlines + dense screen tone dots
        const outlines = await generateInkOutlines(imageBuffer, 2.2, -80);
        const grayBase = await sharp(imageBuffer)
          .grayscale()
          .normalise()
          .linear(2.0, -60)
          .toBuffer();
        const screenTone = generateHalftoneSvg(w, h, 3, 5, 0.22);
        return await sharp(grayBase)
          .composite([
            { input: outlines, blend: "multiply" },
            { input: Buffer.from(screenTone), blend: "multiply" }
          ])
          .toBuffer();
      }

      // ═══════════════════════════════════════════════════════════════════
      //  PREMIUM STYLES — IMPROVED
      // ═══════════════════════════════════════════════════════════════════

      case "ghibli": {
        // Studio Ghibli: median painterly smooth + warm nostalgic palette + soft outlines + dreamy glow
        const outlines = await generateInkOutlines(imageBuffer, 1.4, -35);
        const ghibliBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 1.3, brightness: 1.08 })
          .recomb([
            [1.15, 0.05, -0.05],
            [0.0, 1.1, 0.05],
            [-0.05, 0.0, 0.9]
          ])
          .tint({ r: 255, g: 242, b: 218 })
          .toBuffer();
        const glow = await sharp(imageBuffer).blur(20).modulate({ brightness: 1.2 }).toBuffer();
        return await sharp(ghibliBase)
          .composite([
            { input: glow, blend: "soft-light" },
            { input: outlines, blend: "multiply" }
          ])
          .toBuffer();
      }

      case "acrylic": {
        // Modern acrylic: heavy median for thick paint + extreme saturation + emboss impasto + canvas
        const paintBase = await sharp(imageBuffer)
          .median(9)
          .modulate({ saturation: 1.9, brightness: 1.05 })
          .linear(1.3, -15)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const canvasSvg = generateCanvasSvg(w, h, 5, 0.18);
        return await sharp(paintBase)
          .composite([
            { input: emboss, blend: "overlay" },
            { input: Buffer.from(canvasSvg), blend: "overlay" }
          ])
          .toBuffer();
      }

      case "cubism": {
        // Picasso cubism: wild color channel shift + posterized contrast + emboss geometric edges + outlines
        const outlines = await generateInkOutlines(imageBuffer, 1.6, -50);
        const cubistBase = await sharp(imageBuffer)
          .median(3)
          .recomb([
            [1.0, 0.8, -0.6],
            [-0.6, 1.0, 0.8],
            [0.8, -0.6, 1.0]
          ])
          .modulate({ saturation: 1.4 })
          .linear(1.4, -25)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        return await sharp(cubistBase)
          .composite([
            { input: emboss, blend: "hard-light" },
            { input: outlines, blend: "multiply" }
          ])
          .toBuffer();
      }

      case "artnouveau": {
        // Art Nouveau: warm golden palette + soft painterly median + emboss flowing lines + vignette
        const artBase = await sharp(imageBuffer)
          .median(5)
          .recomb([
            [1.2, 0.15, -0.05],
            [0.05, 1.05, 0.05],
            [-0.1, 0.0, 0.75]
          ])
          .modulate({ saturation: 1.3, brightness: 1.05 })
          .tint({ r: 250, g: 225, b: 185 })
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const vignette = generateVignetteSvg(w, h, 0.6);
        return await sharp(artBase)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "renaissance": {
        // Rembrandt chiaroscuro: deep dark sepia + dramatic vignette + emboss surface + canvas
        const renaissanceBase = await sharp(imageBuffer)
          .median(3)
          .recomb([
            [0.45, 0.75, 0.15],
            [0.35, 0.7, 0.12],
            [0.25, 0.5, 0.1],
          ])
          .modulate({ saturation: 0.6, brightness: 0.85 })
          .linear(1.4, -35)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const canvasSvg = generateCanvasSvg(w, h, 6, 0.12);
        const vignette = generateVignetteSvg(w, h, 0.97);
        return await sharp(renaissanceBase)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(canvasSvg), blend: "overlay" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "pastel": {
        // Soft pastel chalk: desaturated soft tones + median smoothing + heavy paper grain + light blur
        const pastelBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 0.55, brightness: 1.15 })
          .blur(1.5)
          .tint({ r: 255, g: 235, b: 240 })
          .toBuffer();
        const grainSvg = generatePaperGrainSvg(w, h, 0.2);
        const emboss = await generateEmboss(imageBuffer, 1.0);
        return await sharp(pastelBase)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(grainSvg), blend: "overlay" }
          ])
          .toBuffer();
      }

      case "comicbook": {
        // Marvel/DC comic: cel-shaded median + vivid saturated colors + thick outlines + big halftone dots
        const outlines = await generateInkOutlines(imageBuffer, 2.2, -85);
        const comicBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 2.0, brightness: 1.1 })
          .linear(1.4, -20)
          .toBuffer();
        const halftoneSvg = generateHalftoneSvg(w, h, 5, 10, 0.18);
        return await sharp(comicBase)
          .composite([
            { input: outlines, blend: "multiply" },
            { input: Buffer.from(halftoneSvg), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "storybook": {
        // Magical storybook: warm soft glow + median painterly + soft outlines + dreamy vignette
        const outlines = await generateInkOutlines(imageBuffer, 1.2, -30);
        const storyBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 1.3, brightness: 1.1 })
          .tint({ r: 255, g: 232, b: 195 })
          .toBuffer();
        const glow = await sharp(imageBuffer).blur(25).modulate({ brightness: 1.3 }).toBuffer();
        const vignette = generateVignetteSvg(w, h, 0.5);
        return await sharp(storyBase)
          .composite([
            { input: glow, blend: "soft-light" },
            { input: outlines, blend: "multiply" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "cyberpunk": {
        // Neon cyberpunk: extreme magenta/cyan shift + high contrast + scanlines + neon glow border + vignette
        const neonBase = await sharp(imageBuffer)
          .recomb([
            [1.4, -0.4, 0.4],
            [-0.3, 1.2, 0.5],
            [0.5, -0.5, 1.9]
          ])
          .modulate({ saturation: 1.8, brightness: 1.05 })
          .linear(1.3, -15)
          .toBuffer();
        const scanSvg = generateGridLinesSvg(w, h, 4, "#ff007f", 0.08);
        const neonBorder = generateNeonBorderSvg(w, h, "#00ffff", 4, 0.5);
        const vignette = generateVignetteSvg(w, h, 0.7);
        return await sharp(neonBase)
          .composite([
            { input: Buffer.from(scanSvg), blend: "screen" },
            { input: Buffer.from(neonBorder), blend: "screen" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "darkfantasy": {
        // Grim dark fantasy: desaturated dark tones + emboss texture + canvas + heavy vignette
        const darkBase = await sharp(imageBuffer)
          .median(3)
          .modulate({ saturation: 0.4, brightness: 0.7 })
          .recomb([
            [0.9, 0.1, 0.1],
            [0.05, 0.85, 0.15],
            [0.1, 0.1, 0.95]
          ])
          .linear(1.5, -50)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const canvasSvg = generateCanvasSvg(w, h, 6, 0.12);
        const vignette = generateVignetteSvg(w, h, 0.98);
        return await sharp(darkBase)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(canvasSvg), blend: "overlay" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "steampunk": {
        // Victorian steampunk: copper sepia + emboss mechanical texture + mesh overlay + vignette
        const copperBase = await sharp(imageBuffer)
          .median(3)
          .recomb([
            [0.5, 0.7, 0.15],
            [0.35, 0.65, 0.12],
            [0.2, 0.45, 0.1],
          ])
          .tint({ r: 240, g: 190, b: 130 })
          .modulate({ saturation: 0.8, brightness: 0.95 })
          .linear(1.3, -20)
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const meshSvg = generateCanvasSvg(w, h, 8, 0.2);
        const vignette = generateVignetteSvg(w, h, 0.8);
        return await sharp(copperBase)
          .composite([
            { input: emboss, blend: "overlay" },
            { input: Buffer.from(meshSvg), blend: "multiply" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "vaporwave": {
        // Retro vaporwave: extreme pink/cyan shift + halftone overlay + neon gridlines + scanlines
        const vaporBase = await sharp(imageBuffer)
          .recomb([
            [1.5, -0.5, 0.6],
            [0.4, 1.2, -0.4],
            [-0.4, 0.6, 1.6]
          ])
          .modulate({ saturation: 1.8, brightness: 1.05 })
          .linear(1.2, -10)
          .toBuffer();
        const gridSvg = generateGridLinesSvg(w, h, 20, "#00ffff", 0.12);
        const scanSvg = generateGridLinesSvg(w, h, 3, "#ff69b4", 0.06);
        const neonBorder = generateNeonBorderSvg(w, h, "#ff69b4", 4, 0.45);
        return await sharp(vaporBase)
          .composite([
            { input: Buffer.from(gridSvg), blend: "screen" },
            { input: Buffer.from(scanSvg), blend: "screen" },
            { input: Buffer.from(neonBorder), blend: "screen" }
          ])
          .toBuffer();
      }

      case "filmnoir": {
        // Classic film noir: ultra-contrast B&W + dramatic venetian blinds + grain + deep vignette
        const bwNoir = await sharp(imageBuffer)
          .grayscale()
          .normalise()
          .linear(1.8, -45)
          .toBuffer();
        const blindsSvg = generateVenetianBlindsSvg(w, h, 0.5);
        const grainSvg = generatePaperGrainSvg(w, h, 0.1);
        const vignette = generateVignetteSvg(w, h, 0.96);
        return await sharp(bwNoir)
          .composite([
            { input: Buffer.from(blindsSvg), blend: "multiply" },
            { input: Buffer.from(grainSvg), blend: "overlay" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      case "custom": {
        // Concept art: warm glow + median paint + soft emboss + vignette
        const customBase = await sharp(imageBuffer)
          .median(5)
          .modulate({ saturation: 1.2, brightness: 1.05 })
          .tint({ r: 255, g: 225, b: 180 })
          .toBuffer();
        const emboss = await generateEmboss(imageBuffer, 1.0);
        const vignette = generateVignetteSvg(w, h, 0.5);
        return await sharp(customBase)
          .composite([
            { input: emboss, blend: "soft-light" },
            { input: Buffer.from(vignette), blend: "multiply" }
          ])
          .toBuffer();
      }

      default:
        return imageBuffer;
    }
  } catch (err) {
    console.error(`Programmatic styling failed for [${style}]. Returning original image.`, err.message);
    styleErrors.unshift({
      style,
      error: err.message,
      stack: err.stack,
      timestamp: new Date().toISOString()
    });
    if (styleErrors.length > 20) {
      styleErrors.pop();
    }
    return imageBuffer;
  }
}
