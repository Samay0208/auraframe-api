/**
 * AuraFrame Cloud Style Engine - High-Fidelity Unified AI Pipeline
 * Routes all 28 AI styles through the premium Fal.ai FLUX engine for instant, jaw-dropping art.
 */

import sharp from "sharp";
import { fal } from "@fal-ai/client";

// Free Instant Filters (Sharp implementation)
async function applyLocalFilter(buffer, style) {
  const image = sharp(buffer);

  switch (style) {
    case "blackwhite":
      return await image.grayscale().toBuffer();

    case "sepia":
      return await image
        .recomb([
          [0.393, 0.769, 0.189],
          [0.349, 0.686, 0.168],
          [0.272, 0.534, 0.131],
        ])
        .toBuffer();

    case "highcontrast":
      return await image.normalise().linear(1.3, -15).toBuffer();

    case "warmglow":
      return await image
        .tint({ r: 255, g: 215, b: 160 })
        .toBuffer();

    case "cooltint":
      return await image
        .tint({ r: 160, g: 195, b: 255 })
        .toBuffer();

    case "vignette": {
      const metadata = await image.metadata();
      const width = metadata.width || 1024;
      const height = metadata.height || 600;

      const vignetteSvg = `
        <svg width="${width}" height="${height}">
          <defs>
            <radialGradient id="vignette" cx="50%" cy="50%" r="70%">
              <stop offset="50%" stop-color="#000000" stop-opacity="0"/>
              <stop offset="100%" stop-color="#000000" stop-opacity="0.8"/>
            </radialGradient>
          </defs>
          <rect width="${width}" height="${height}" fill="url(#vignette)"/>
        </svg>
      `;

      return await image
        .composite([{ input: Buffer.from(vignetteSvg), blend: "multiply" }])
        .toBuffer();
    }

    case "original":
    default:
      return buffer;
  }
}

// Unified High-Fidelity AI prompts mapping (FLUX and SDXL optimized)
const AI_MAPPING = {
  // Pro Styles (routed to Fal.ai for breathtaking results)
  sketch: "fine line pencil sketch, beautiful hand-drawn graphite line art, clean shading, textured paper background",
  charcoal: "textured charcoal sketch, fine art charcoal drawing, rich dark values, smudged shadows",
  ink: "elegant black ink illustration, crosshatching drawing style, graphic novel ink illustration",
  watercolor: "fluid wet-on-wet watercolor painting, soft pigment washes, delicate color bleed effects",
  oilpainting: "classical oil painting on canvas, visible thick impasto brushstrokes, rich colorful masterwork",
  impressionist: "vibrant impressionist painting, beautiful outdoor light reflections, loose quick brush strokes, Claude Monet style",
  vangogh: "Vincent Van Gogh oil painting, swirling starry night sky impasto, thick swirling yellow and blue brushstrokes",
  cartoon: "modern bold 2d vector cartoon illustration, flat clean colors, thick black outlines",
  anime: "classic retro anime aesthetic, gorgeous hand-drawn animation keyframe, colorful animation art",
  popArt: "bold pop art silkscreen print, Andy Warhol style, high contrast, vibrant blocky primary colors",
  pixelArt: "high quality retro 16-bit pixel art, pixelated game screen background, clean gaming asset",
  ukiyoe: "classic Japanese ukiyo-e woodblock print, Hokusai wave landscape aesthetic, flat colors and fine linework",
  lowpoly: "low-poly 3D geometric mesh render, faceted papercraft shapes, minimal clean digital graphics",
  manga: "japanese manga page, black and white ink line drawing, clean screen tone shading, comic book panels",

  // Premium Styles
  ghibli: "Studio Ghibli aesthetic, hand-drawn anime keyframe, rich watercolor colors, nostalgic soft warm lighting",
  acrylic: "modern abstract acrylic painting, thick textured brush strokes, vibrant canvas, contemporary art",
  cubism: "analytical cubism painting style, fractured geometric shapes, neutral color tones, Pablo Picasso aesthetic",
  artnouveau: "art nouveau illustration, elegant flowing lines, organic floral frames, Alphonse Mucha styling",
  renaissance: "renaissance master portrait, soft chiaroscuro lighting, rich dark undertones, Rembrandt paint style",
  pastel: "dreamy soft pastel sketch, chalk dust texture, delicate gentle hues",
  comicbook: "vintage pulp comic book print, saturated ink colors, retro halftone dot pattern",
  storybook: "whimsical fantasy storybook illustration, soft warm magical glow, watercolor and ink",
  cyberpunk: "futuristic cyberpunk city scene, reflections in rain puddles, vibrant purple and cyan neon glow",
  darkfantasy: "grim dark fantasy oil painting, eerie moody atmosphere, heavy shadow details, dark fantasy novel",
  steampunk: "steampunk design, brass gears, steam exhausts, industrial Victorian copper machinery, sepia tint",
  vaporwave: "surreal 1980s vaporwave aesthetic, glowing pink grids, neon gridlines, retro digital glitch",
  filmnoir: "high contrast black and white film noir photography, dramatic hard shadows, venetian blind blinds shadow casting",
  custom: "gorgeous conceptual art painting",
};

// Fallback mapper if FAL_KEY is missing (maps to the most visually matching local filter)
const FALLBACK_MAP = {
  sketch: "blackwhite",
  charcoal: "blackwhite",
  ink: "highcontrast",
  watercolor: "warmglow",
  oilpainting: "warmglow",
  impressionist: "cooltint",
  vangogh: "warmglow",
  cartoon: "highcontrast",
  anime: "cooltint",
  popArt: "highcontrast",
  pixelArt: "highcontrast",
  ukiyoe: "sepia",
  lowpoly: "cooltint",
  manga: "blackwhite",
  ghibli: "warmglow",
  acrylic: "warmglow",
  cubism: "sepia",
  artnouveau: "warmglow",
  renaissance: "sepia",
  pastel: "warmglow",
  comicbook: "highcontrast",
  storybook: "warmglow",
  cyberpunk: "cooltint",
  darkfantasy: "vignette",
  steampunk: "sepia",
  vaporwave: "cooltint",
  filmnoir: "blackwhite",
  custom: "warmglow",
};

export async function applyStyle(imageBuffer, style, customPrompt = "") {
  console.log(`StyleEngine: Processing request for style [${style}]`);

  // 1. Check local Sharp filters (instant)
  const localStyles = ["blackwhite", "sepia", "highcontrast", "warmglow", "cooltint", "vignette", "original"];
  if (localStyles.includes(style)) {
    return await applyLocalFilter(imageBuffer, style);
  }

  // 2. Process all AI styles through premium Fal.ai pipeline
  if (AI_MAPPING[style] || style === "custom") {
    // If FAL_KEY is missing in production, fall back to matching local filters dynamically
    if (!process.env.FAL_KEY) {
      const fallbackFilter = FALLBACK_MAP[style] || "highcontrast";
      console.warn(`FAL_KEY missing in environment. Falling back to local filter [${fallbackFilter}] for style [${style}].`);
      return await applyLocalFilter(imageBuffer, fallbackFilter);
    }

    const basePrompt = style === "custom" ? customPrompt : AI_MAPPING[style];
    try {
      const resizedBuffer = await sharp(imageBuffer)
        .resize(1024, 600, { fit: "cover" })
        .jpeg({ quality: 90 })
        .toBuffer();

      const base64Uri = `data:image/jpeg;base64,${resizedBuffer.toString("base64")}`;

      const response = await fal.run("fal-ai/flux/schnell/image-to-image", {
        input: {
          image_url: base64Uri,
          prompt: `${basePrompt}, gorgeous artistic masterpiece, highly detailed, stunning visual style`,
          strength: 0.55,
          num_inference_steps: 4,
          enable_safety_checker: true,
          sync_mode: true,
        },
      });

      if (!response.image || !response.image.url) {
        throw new Error("Fal.ai returned invalid image structure");
      }

      const fetchResponse = await fetch(response.image.url);
      const arrayBuffer = await fetchResponse.arrayBuffer();
      return Buffer.from(arrayBuffer);
    } catch (err) {
      console.error(`Fal.ai styling failed for [${style}].`, err.message);
      throw err;
    }
  }

  return imageBuffer;
}
