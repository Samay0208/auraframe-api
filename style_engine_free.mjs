/**
 * AuraFrame Cloud Style Engine
 * Processes 35 styles across 3 tiers: local filters (Sharp), Pro (Hugging Face), and Premium (Fal.ai).
 */

import sharp from "sharp";
import { HfInference } from "@huggingface/inference";
import { fal } from "@fal-ai/client";

// Initialize Hugging Face Inference Client
const hf = new HfInference(process.env.HF_TOKEN);

// Free Instant Filters (Sharp implementation)
async function applyLocalFilter(buffer, style) {
  const image = sharp(buffer);

  switch (style) {
    case "blackwhite":
      return await image.grayscale().toBuffer();

    case "sepia":
      // Classic sepia recombination matrix
      return await image
        .recomb([
          [0.393, 0.769, 0.189],
          [0.349, 0.686, 0.168],
          [0.272, 0.534, 0.131],
        ])
        .toBuffer();

    case "highcontrast":
      // Enhances contrast using normalise and linear stretching
      return await image.normalise().linear(1.3, -15).toBuffer();

    case "warmglow":
      // Adds a golden amber warmth tint
      return await image
        .tint({ r: 255, g: 215, b: 160 })
        .toBuffer();

    case "cooltint":
      // Adds a cool blue/cyan tint
      return await image
        .tint({ r: 160, g: 195, b: 255 })
        .toBuffer();

    case "vignette": {
      // Vignette SVG overlay (soft dark edges)
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

// Pro Hugging Face Models and Prompt mappings
const HF_MAPPING = {
  sketch: {
    model: "stabilityai/stable-diffusion-xl-refiner-1.0",
    prompt: "fine line pencil sketch, beautiful hand-drawn art, clean graphite lines, paper texture",
  },
  charcoal: {
    model: "stabilityai/stable-diffusion-xl-refiner-1.0",
    prompt: "smudged charcoal sketch, fine art charcoal drawing, rich dark values, textured paper",
  },
  ink: {
    model: "stabilityai/stable-diffusion-xl-refiner-1.0",
    prompt: "elegant black ink drawing, crosshatching illustration style, graphic novel ink drawing",
  },
  watercolor: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "beautiful wet-on-wet watercolor painting, soft pigment washes, delicate floral bleed effects",
  },
  oilpainting: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "classical oil painting on canvas, visible textured brushstrokes, rich warm colors, masterpiece",
  },
  impressionist: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "impressionist painting style, light reflections, loose quick brush strokes, vibrant Claude Monet style",
  },
  vangogh: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "expressive Vincent Van Gogh painting, heavy swirling impasto brushstrokes, Starry Night sky palette",
  },
  cartoon: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "modern bold 2d vector cartoon illustration, flat colors, thick dark outlines",
  },
  anime: {
    model: "stablediffusionapi/anything-v5",
    prompt: "detailed anime illustration, beautiful animation keyframe, Studio Ghibli vibes, colorful",
  },
  popArt: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "bold pop art silkscreen print, Andy Warhol style, high contrast, vibrant blocky colors",
  },
  pixelArt: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "high quality retro 16-bit pixel art, pixelated game screen background",
  },
  ukiyoe: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "classic Japanese ukiyo-e woodblock print, Hokusai aesthetic, flat colors and fine linework",
  },
  lowpoly: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "low-poly 3D geometric mesh render, faceted shapes, papercraft aesthetic",
  },
  manga: {
    model: "runwayml/stable-diffusion-v1-5",
    prompt: "monochrome black and white manga drawing, clean screen tone shading, professional ink lines",
  },
};

// Premium Fal.ai Flux prompts
const FAL_MAPPING = {
  ghibli: "Studio Ghibli aesthetic, hand-drawn anime keyframe, rich watercolor colors, nostalgic soft lighting",
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

export async function applyStyle(imageBuffer, style, customPrompt = "") {
  console.log(`StyleEngine: Processing request for style [${style}]`);

  // 1. Check local Sharp filters (instant)
  const localStyles = ["blackwhite", "sepia", "highcontrast", "warmglow", "cooltint", "vignette", "original"];
  if (localStyles.includes(style)) {
    return await applyLocalFilter(imageBuffer, style);
  }

  // 2. Check Pro Hugging Face styles
  if (HF_MAPPING[style]) {
    if (!process.env.HF_TOKEN) {
      console.warn("HF_TOKEN missing. Falling back to local High Contrast filter.");
      return await applyLocalFilter(imageBuffer, "highcontrast");
    }

    const config = HF_MAPPING[style];
    try {
      // Resize image down slightly to ensure safe speed & payloads under free tier
      const processingBuffer = await sharp(imageBuffer)
        .resize(512, 512, { fit: "inside" })
        .jpeg({ quality: 85 })
        .toBuffer();

      const blob = new Blob([processingBuffer], { type: "image/jpeg" });
      const response = await hf.imageToImage({
        model: config.model,
        inputs: blob,
        parameters: {
          prompt: config.prompt,
          negative_prompt: "deformed, blurry, low resolution, bad hands, dark shadows, dull, ugly",
          strength: 0.6,
          guidance_scale: 7.5,
        },
      });

      const resArray = await response.arrayBuffer();
      return Buffer.from(resArray);
    } catch (err) {
      console.error(`Hugging Face styling failed for [${style}], falling back to local Sepia filter:`, err.message);
      return await applyLocalFilter(imageBuffer, "sepia");
    }
  }

  // 3. Check Premium Fal.ai styles
  if (FAL_MAPPING[style] || style === "custom") {
    if (!process.env.FAL_KEY) {
      console.warn("FAL_KEY missing. Falling back to local Warm Glow filter.");
      return await applyLocalFilter(imageBuffer, "warmglow");
    }

    const basePrompt = style === "custom" ? customPrompt : FAL_MAPPING[style];
    try {
      // Convert buffer to data URI for Fal.ai image-to-image input
      const resizedBuffer = await sharp(imageBuffer)
        .resize(1024, 600, { fit: "cover" })
        .jpeg({ quality: 90 })
        .toBuffer();

      const base64Uri = `data:image/jpeg;base64,${resizedBuffer.toString("base64")}`;

      const response = await fal.run("fal-ai/flux/schnell/image-to-image", {
        input: {
          image_url: base64Uri,
          prompt: `${basePrompt}, artistic masterpiece, highly detailed, stunning visual style`,
          strength: 0.5,
          num_inference_steps: 4,
          enable_safety_checker: true,
          sync_mode: true,
        },
      });

      if (!response.image || !response.image.url) {
        throw new Error("Fal.ai returned invalid image structure");
      }

      // Fetch the generated image url
      const fetchResponse = await fetch(response.image.url);
      const arrayBuffer = await fetchResponse.arrayBuffer();
      return Buffer.from(arrayBuffer);
    } catch (err) {
      console.error(`Fal.ai styling failed for [${style}], falling back to local Vignette filter:`, err.message);
      return await applyLocalFilter(imageBuffer, "vignette");
    }
  }

  // Fallback if styling name is unrecognizable
  return imageBuffer;
}
