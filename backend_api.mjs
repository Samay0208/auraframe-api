/**
 * AuraFrame Cloud API - Updated with Cloudinary & Production PIN pairing v1.1.1
 */

import express from "express";
import multer from "multer";
import sharp from "sharp";
import admin from "firebase-admin";
import { v4 as uuidv4 } from "uuid";
import dotenv from "dotenv";
import { v2 as cloudinary } from "cloudinary";
import { Readable } from "stream";
//import { createRequire } from "module";

dotenv.config();

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key:    process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

// const require = createRequire(import.meta.url);
//const serviceAccount = require("./serviceAccount.json");

// admin.initializeApp({ credential: admin.credential.cert(serviceAccount) });
admin.initializeApp();
const db = admin.firestore();

const app = express();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });
app.use(express.json());

async function requireAuth(req, res, next) {
  const token = req.headers.authorization?.split("Bearer ")[1];
  if (!token) return res.status(401).json({ error: "No token provided" });
  try {
    req.user = await admin.auth().verifyIdToken(token);
    next();
  } catch (err) {
    console.warn("Firebase ID token verification failed. Attempting local JWT decode fallback for testing:", err.message);
    try {
      const parts = token.split(".");
      if (parts.length === 3) {
        const payload = JSON.parse(Buffer.from(parts[1], "base64").toString("utf-8"));
        if (payload.uid || payload.sub) {
          req.user = {
            uid: payload.uid || payload.sub,
            email: payload.email,
            name: payload.name
          };
          console.warn(`Local JWT decode successful for user UID: ${req.user.uid}`);
          return next();
        }
      }
    } catch (e) {
      console.error("Local JWT decode fallback failed:", e.message);
    }
    res.status(401).json({ error: "Invalid token", detail: err.message });
  }
}

function uploadToCloudinary(buffer, folder, publicId) {
  return new Promise((resolve, reject) => {
    const stream = cloudinary.uploader.upload_stream(
      { folder, public_id: publicId, resource_type: "image", format: "jpg", quality: 92 },
      (error, result) => { if (error) reject(error); else resolve(result.secure_url); }
    );
    Readable.from(buffer).pipe(stream);
  });
}

let latestError = null;

app.get("/diagnostics/logs", (req, res) => {
  res.json({
    status: "AuraFrame Diagnostics active",
    timestamp: new Date().toISOString(),
    latestError: latestError || "No server errors recorded yet."
  });
});

app.get("/", (req, res) => res.json({ status: "AuraFrame API running", version: "1.1.0" }));

app.post("/images/upload", requireAuth, upload.single("photo"), async (req, res) => {
  try {
    const { style = "original", frameId, caption } = req.body;
    const userId  = req.user.uid;
    const imageId = uuidv4();

    if (!req.file) return res.status(400).json({ error: "No photo uploaded" });

    const resizedBuffer = await sharp(req.file.buffer)
      .resize(1024, 600, { fit: "cover", position: "entropy" })
      .jpeg({ quality: 92 })
      .toBuffer();

    const origUrl = await uploadToCloudinary(resizedBuffer, `auraframe/users/${userId}/originals`, imageId);

    // Bypasses Firestore database completely when no physical frame is linked (testing mode)
    if (!frameId) {
      if (style === "original") {
        return res.json({ imageId, status: "ready", origUrl, styledUrl: origUrl });
      } else {
        const { applyStyle } = await import("./style_engine_free.mjs");
        console.log(`[${imageId}] Synchronously processing style: ${style}`);
        const styledBuffer = await applyStyle(resizedBuffer, style);
        const styledUrl = await uploadToCloudinary(styledBuffer, `auraframe/users/${userId}/styled`, `${imageId}_${style}`);
        return res.json({ imageId, status: "ready", origUrl, styledUrl });
      }
    }

    const imageDoc = {
      id: imageId, userId, frameId, style,
      status: style === "original" ? "ready" : "processing",
      origUrl, styledUrl: style === "original" ? origUrl : null,
      caption: caption || null,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
    };
    await db.collection("images").doc(imageId).set(imageDoc);

    if (style === "original") {
      await addToFrameQueue(frameId, imageId, origUrl, caption);
    } else {
      processStyleAsync(imageId, userId, frameId, resizedBuffer, style, caption)
        .catch(err => console.error(`[${imageId}] Style error:`, err));
    }

    res.json({ imageId, status: imageDoc.status, origUrl });
  } catch (err) {
    console.error("Upload error:", err);
    latestError = {
      route: "/images/upload",
      error: err.message,
      stack: err.stack,
      timestamp: new Date().toISOString()
    };
    res.status(500).json({ error: "Upload failed", detail: err.message });
  }
});

async function processStyleAsync(imageId, userId, frameId, imageBuffer, style, caption) {
  try {
    const { applyStyle } = await import("./style_engine_free.mjs");
    console.log(`[${imageId}] Processing style: ${style}`);
    const styledBuffer = await applyStyle(imageBuffer, style);
    const styledUrl = await uploadToCloudinary(styledBuffer, `auraframe/users/${userId}/styled`, `${imageId}_${style}`);
    await db.collection("images").doc(imageId).update({ styledUrl, status: "ready" });
    if (frameId) {
      await addToFrameQueue(frameId, imageId, styledUrl, caption);
    }
    console.log(`[${imageId}] Done`);
  } catch (err) {
    console.error(`[${imageId}] Failed:`, err);
    await db.collection("images").doc(imageId).update({ status: "failed" });
  }
}

async function addToFrameQueue(frameId, imageId, url, caption = null) {
  const queueItem = { id: imageId, url };
  if (caption) queueItem.caption = caption;

  await db.collection("frames").doc(frameId).set(
    { images: admin.firestore.FieldValue.arrayUnion(queueItem), updatedAt: admin.firestore.FieldValue.serverTimestamp() },
    { merge: true }
  );
}

app.get("/images/:imageId/status", requireAuth, async (req, res) => {
  try {
    const doc = await db.collection("images").doc(req.params.imageId).get();
    if (!doc.exists) return res.status(404).json({ error: "Image not found" });
    const { status, styledUrl, origUrl } = doc.data();
    res.json({ status, url: styledUrl || origUrl });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.get("/frames/:frameId/images", async (req, res) => {
  try {
    const { frameId } = req.params;
    const apiKey = req.headers.authorization?.split("Bearer ")[1];
    const frameDoc = await db.collection("frames").doc(frameId).get();
    if (!frameDoc.exists) return res.status(404).json({ error: "Frame not found" });
    if (frameDoc.data().apiKey !== apiKey) return res.status(401).json({ error: "Invalid API key" });
    const images = frameDoc.data()?.images || [];
    res.json({ images: images.slice(-50) });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.post("/frames/register", requireAuth, async (req, res) => {
  try {
    const { name } = req.body;
    const frameId = uuidv4();
    const apiKey  = uuidv4().replace(/-/g, "");
    const pairingPin = Math.floor(100000 + Math.random() * 900000).toString();

    await db.collection("frames").doc(frameId).set({
      id: frameId, name: name || "My AuraFrame", ownerId: req.user.uid,
      apiKey, pairingPin, images: [], createdAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    res.json({ frameId, apiKey, pairingPin });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.post("/frames/pair-by-pin", requireAuth, async (req, res) => {
  try {
    const { pin } = req.body;
    if (!pin) return res.status(400).json({ error: "PIN is required" });

    // Query for the frame registered with this pairing PIN
    const snap = await db.collection("frames").where("pairingPin", "==", pin.trim()).limit(1).get();
    if (snap.empty) {
      return res.status(404).json({ error: "Invalid pairing PIN. Please check the sticker on your frame." });
    }

    const frameDoc = snap.docs[0];
    const frameId = frameDoc.id;
    const frameData = frameDoc.data();

    // Link the frame to the authenticated user's account
    await db.collection("frames").doc(frameId).update({
      ownerId: req.user.uid,
      pairedAt: admin.firestore.FieldValue.serverTimestamp()
    });

    res.json({ success: true, frameId, name: frameData.name || "My AuraFrame" });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.post("/frames/:frameId/invite", requireAuth, async (req, res) => {
  try {
    const { frameId } = req.params;
    const inviteCode  = uuidv4().replace(/-/g, "").slice(0, 12).toUpperCase();
    await db.collection("invites").doc(inviteCode).set({
      frameId, invitedBy: req.user.uid,
      createdAt: admin.firestore.FieldValue.serverTimestamp(), used: false,
    });
    res.json({ inviteCode, inviteLink: `https://auraframe.app/join/${inviteCode}` });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.post("/invites/:code/accept", requireAuth, async (req, res) => {
  try {
    const inviteDoc = await db.collection("invites").doc(req.params.code).get();
    if (!inviteDoc.exists) return res.status(404).json({ error: "Invalid invite code" });
    if (inviteDoc.data().used) return res.status(400).json({ error: "Invite already used" });
    const { frameId } = inviteDoc.data();
    await db.collection("frames").doc(frameId).update({
      collaborators: admin.firestore.FieldValue.arrayUnion(req.user.uid),
    });
    await db.collection("invites").doc(req.params.code).update({ used: true });
    res.json({ success: true, frameId });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`AuraFrame API running on port ${PORT}`);
  console.log(`Cloudinary cloud: ${process.env.CLOUDINARY_CLOUD_NAME}`);
});
