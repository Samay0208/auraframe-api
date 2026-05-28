/**
 * AuraFrame Cloud Style Engine - 100% Free Unified AI Pipeline
 * Routes all 28 Pro and Premium styles through the free Hugging Face Stable Diffusion v1.5 pipeline.
 */

import sharp from "sharp";
import { HfInference } from "@huggingface/inference";

// Initialize Hugging Face Inference Client
const hf = new HfInference(process.env.HF_TOKEN);

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

// Unified High-Fidelity prompts optimized for RunwayML Stable Diffusion v1.5
const AI_MAPPING = {
  // Pro Styles (Free Hugging Face)
  sketch: "fine line pencil sketch, beautiful hand-drawn graphite line art, clean shading, textured paper background",
  charcoal: "textured charcoal sketch, fine art charcoal drawing, rich dark values, smudged shadows",
  ink: "elegant black ink illustration, crosshatching drawing style, graphic novel ink illustration",
  watercolor: "fluid wet-on-wet watercolor painting, soft fluid pigment washes, delicate color bleed effects",
  oilpainting: "classical oil painting on canvas, visible thick impasto brushstrokes, rich colorful masterwork",
  impressionist: "vibrant impressionist painting, beautiful outdoor light reflections, loose quick brush strokes, Claude Monet style",
  vangogh: "Vincent Van Gogh oil painting, swirling starry night sky impasto, thick swirling yellow and blue brushstrokes",
  cartoon: "modern bold 2d vector cartoon illustration, flat clean colors, thick black outlines",
  anime: "classic retro anime aesthetic, gorgeous hand-drawn animation keyframe, colorful animation art",
  popArt: "bold pop art silkscreen print, Andy Warhol style, high contrast, vibrant blocky primary colors",
  pixelArt: "high quality retro 16-bit pixel art, pixelated game screen background, clean gaming asset",
  ukiyoe: "woodblock Japanese woodcut print in style of Hokusai, Hokusai wave aesthetic, fine ink outlines, flat solid color overlay",
  lowpoly: "low-poly 3D geometric mesh render, faceted papercraft shapes, minimal clean digital graphics",
  manga: "japanese manga page, black and white ink line drawing, clean screen tone shading, comic book panels",

  // Premium Styles (Now free Hugging Face)
  ghibli: "Studio Ghibli aesthetic, hand-drawn anime keyframe, rich watercolor colors, nostalgic soft warm lighting, Miyazaki style",
  acrylic: "modern abstract acrylic painting, thick textured brush strokes, vibrant canvas, contemporary art",
  cubism: "analytical cubism painting style, fractured geometric shapes, neutral color tones, Pablo Picasso aesthetic",
  artnouveau: "art nouveau illustration, elegant flowing lines, decorative borders, Alphonse Mucha styling",
  renaissance: "renaissance master portrait painting, soft chiaroscuro lighting, rich dark undertones, Rembrandt paint style",
  pastel: "dreamy soft pastel sketch, chalk dust texture, delicate gentle hues",
  comicbook: "vintage pulp comic book print, saturated ink colors, retro halftone dot pattern, Marvel style",
  storybook: "whimsical fantasy storybook illustration, soft warm magical glow, watercolor and ink",
  cyberpunk: "futuristic cyberpunk city scene, reflections in rain puddles, vibrant purple and cyan neon glow, tech",
  darkfantasy: "grim dark fantasy oil painting, eerie moody atmosphere, heavy shadow details, dark fantasy novel illustration",
  steampunk: "steampunk design, brass gears, steam exhausts, industrial Victorian copper machinery, sepia tint",
  vaporwave: "surreal 1980s vaporwave aesthetic, glowing pink grids, neon gridlines, retro digital glitch",
  filmnoir: "high contrast black and white film noir photography, dramatic hard shadows, venetian blind blinds shadow casting",
  custom: "gorgeous conceptual art painting",
};

// Fallback mapper if HF_TOKEN is missing or fails (maps to the most visually matching local filter)
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

  // 2. Process all AI styles through 100% FREE Hugging Face Stable Diffusion pipeline
  if (AI_MAPPING[style] || style === "custom") {
    // Fall back to matching local filters if HF_TOKEN is missing
    if (!process.env.HF_TOKEN) {
      const fallbackFilter = FALLBACK_MAP[style] || "highcontrast";
      console.warn(`HF_TOKEN missing in environment. Falling back to local filter [${fallbackFilter}] for style [${style}].`);
      return await applyLocalFilter(imageBuffer, fallbackFilter);
    }

    const basePrompt = style === "custom" ? customPrompt : AI_MAPPING[style];
    try {
      // Resize image to 512x512 for optimal Hugging Face processing speed & payload limit compliance
      const processingBuffer = await sharp(imageBuffer)
        .resize(512, 512, { fit: "inside" })
        .jpeg({ quality: 80 })
        .toBuffer();

      const blob = new Blob([processingBuffer], { type: "image/jpeg" });
      const response = await hf.imageToImage({
        model: "runwayml/stable-diffusion-v1-5",
        inputs: blob,
        parameters: {
          prompt: `${basePrompt}, highly detailed artistic masterpiece, stunning visual style`,
          negative_prompt: "deformed, blurry, low resolution, bad hands, dark shadows, dull, ugly",
          strength: 0.55,
          guidance_scale: 7.5,
        },
      });

      const resArray = await response.arrayBuffer();
      return Buffer.from(resArray);
    } catch (err) {
      console.error(`Hugging Face styling failed for [${style}]. Falling back to matching local filter.`, err.message);
      const fallbackFilter = FALLBACK_MAP[style] || "highcontrast";
      return await applyLocalFilter(imageBuffer, fallbackFilter);
    }
  }

  return imageBuffer;
}
